# CAMINHO: backend/app/utils/log_safety.py
"""Auxiliares para não registrar dados sensíveis em logs (SEC-12)."""


def mask_email(email: str) -> str:
    """'maria@exemplo.com' -> 'm***@exemplo.com'."""
    if not email or "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"
