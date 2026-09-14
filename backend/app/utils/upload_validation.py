# CAMINHO: backend/app/utils/upload_validation.py
"""Validação de uploads: limite de tamanho, tipo real (magic bytes) e nome seguro.

Usado pelos três endpoints de upload (`/admin/upload`, `/videos/upload`,
`/fish/images/upload`) — ver `openspec/specs/upload-validation-and-limits/spec.md`.
"""

import os
import re
import unicodedata
from typing import Optional

from fastapi import UploadFile

try:
    import magic  # python-magic (binding para libmagic)
except ImportError:  # pragma: no cover - ambiente sem libmagic instalado
    magic = None


class PayloadTooLargeError(Exception):
    """Levantado quando um upload excede o limite de tamanho configurado."""


# Limites por tipo de upload, configuráveis via env (megabytes).
MAX_UPLOAD_SIZE_PDF_MB = float(os.getenv("MAX_UPLOAD_SIZE_PDF_MB", "25"))
MAX_UPLOAD_SIZE_VIDEO_MB = float(os.getenv("MAX_UPLOAD_SIZE_VIDEO_MB", "200"))
MAX_UPLOAD_SIZE_IMAGE_MB = float(os.getenv("MAX_UPLOAD_SIZE_IMAGE_MB", "10"))

_CHUNK_SIZE = 1024 * 1024  # 1 MB


async def read_limited(upload_file: UploadFile, max_bytes: int) -> bytes:
    """Lê o corpo do upload em chunks, abortando assim que exceder `max_bytes`.

    Não confia em Content-Length (pode ser omitido/forjado pelo cliente) — o
    limite é aplicado sobre o que é efetivamente lido, chunk a chunk.
    """
    chunks = []
    total = 0
    while True:
        chunk = await upload_file.read(_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise PayloadTooLargeError(
                f"Arquivo excede o limite de {int(max_bytes)} bytes"
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _detect_via_signatures(content: bytes) -> Optional[str]:
    """Fallback manual quando `python-magic`/libmagic não está disponível.

    Cobre só os tipos hoje aceitos pela aplicação (PDF, JPEG/PNG/WEBP/BMP,
    MP4/WEBM/MOV) — não é um detector de tipo genérico.
    """
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"BM"):
        return "image/bmp"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if len(content) > 12 and content[4:8] == b"ftyp":
        # Contêiner MP4/QuickTime — sem libmagic não dá para distinguir
        # .mp4 de .mov com segurança; tratado como "video/mp4" (o chamador
        # decide se aceita com base no conjunto de tipos permitidos).
        return "video/mp4"
    if content.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    return None


def detect_real_content_type(content: bytes) -> Optional[str]:
    """Detecta o tipo real do conteúdo pelos magic bytes (não pela extensão)."""
    if magic is not None:
        try:
            detected = magic.from_buffer(content, mime=True)
            if detected:
                return detected
        except Exception:
            pass
    return _detect_via_signatures(content)


_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._ -]+")


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Normaliza e restringe o nome do arquivo a um allowlist de caracteres.

    Não afeta o *path* de storage (gerado separadamente via uuid4 em cada
    service) — só o valor persistido como metadado/reexibido na UI.
    """
    normalized = unicodedata.normalize("NFKC", name or "")
    normalized = "".join(ch for ch in normalized if ch.isprintable())
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", normalized).strip(" ._")
    if not cleaned:
        cleaned = "arquivo"
    return cleaned[:max_length]
