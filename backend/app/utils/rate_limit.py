# CAMINHO: backend/app/utils/rate_limit.py
"""Auxiliares de rate limit para as rotas de autenticação (SEC-03).

- `client_ip`: IP do cliente sem confiar em entradas forjáveis de X-Forwarded-For.
- `EmailRateLimiter`: janela deslizante em memória, por e-mail, por processo.
"""

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from slowapi.util import get_remote_address

# Quantos proxies confiáveis anexam um IP a X-Forwarded-For antes do backend.
# Cadeia de produção: cliente → CloudFront → Nginx → Next.js (route handler
# /api-proxy, que repassa o header recebido) → FastAPI. CloudFront anexa o IP do
# visitante e o Nginx anexa o do CloudFront: o IP real é a 2ª entrada contada da
# DIREITA. Tudo à esquerda é enviado pelo cliente e pode ser forjado.
TRUSTED_PROXY_HOPS = int(os.getenv("TRUSTED_PROXY_HOPS", "2"))


def client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for and TRUSTED_PROXY_HOPS > 0:
        parts = [p.strip() for p in forwarded_for.split(",") if p.strip()]
        if len(parts) >= TRUSTED_PROXY_HOPS:
            return parts[-TRUSTED_PROXY_HOPS]
    return get_remote_address(request)


class EmailRateLimiter:
    """Conta eventos por chave (e-mail normalizado) numa janela deslizante.

    Em memória e por processo (uvicorn --workers N → o teto efetivo é até N
    vezes maior); complementa, não substitui, o limite por IP e os limites
    nativos do Supabase Auth.
    """

    def __init__(self, max_events: int, window_seconds: int):
        self.max_events = max_events
        self.window = window_seconds
        self._events: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, q: deque, now: float) -> None:
        while q and now - q[0] > self.window:
            q.popleft()

    def is_limited(self, email: str) -> bool:
        key = (email or "").strip().lower()
        now = time.monotonic()
        with self._lock:
            q = self._events.get(key)
            if q is None:
                return False
            self._prune(q, now)
            if not q:
                del self._events[key]
                return False
            return len(q) >= self.max_events

    def hit(self, email: str) -> None:
        key = (email or "").strip().lower()
        now = time.monotonic()
        with self._lock:
            q = self._events[key]
            self._prune(q, now)
            q.append(now)
