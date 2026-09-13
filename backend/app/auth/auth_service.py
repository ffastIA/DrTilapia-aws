"""Módulo de autenticação do DrTilápia."""

import logging
from typing import Optional, Dict, Any
import httpx
from supabase_auth.errors import AuthApiError
from supabase import create_client, Client, ClientOptions
from app.database import (
    SUPABASE_URL,
    SUPABASE_KEY,
    supabase_admin,
    get_session_scoped_client,
    _resolve_ssl_verify,
)

logger = logging.getLogger("AuthService")


class AuthError(Exception):
    """Erro de autenticação com um código estável para o chamador decidir a resposta HTTP."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _fresh_auth_client() -> Client:
    """Cliente Supabase novo e descartável (chave anon), usado só para uma chamada GoTrue.

    Nunca reaproveitado como cliente de dados (`.table()`/`.storage()`/`.rpc()`) e
    nunca compartilhado entre requisições — evita o vazamento de estado de auth
    entre chamadas concorrentes (spec `supabase-client-isolation`).
    """
    return create_client(
        SUPABASE_URL,
        SUPABASE_KEY,
        options=ClientOptions(httpx_client=httpx.Client(verify=_resolve_ssl_verify())),
    )


def _is_email_not_confirmed(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if code == "email_not_confirmed":
        return True
    return "not confirmed" in str(exc).lower()


class AuthService:
    @staticmethod
    async def login(email: str, password: str) -> Optional[Dict[str, Any]]:
        client = _fresh_auth_client()
        try:
            logger.info("[login] iniciando autenticação para: %s", email)
            auth_response = client.auth.sign_in_with_password(
                {
                    "email": email,
                    "password": password,
                }
            )
        except AuthApiError as e:
            logger.warning("[login] AuthApiError para %s: code=%s status=%s", email, getattr(e, "code", None), getattr(e, "status", None))
            if _is_email_not_confirmed(e):
                raise AuthError(code="email_not_confirmed", message="Confirme seu e-mail antes de entrar.")
            raise AuthError(code="invalid_credentials", message="Invalid credentials")
        except Exception:
            logger.exception("[login] exceção inesperada durante login para %s", email)
            raise AuthError(code="invalid_credentials", message="Invalid credentials")

        if not auth_response.user:
            logger.warning("[login] auth_response.user vazio para: %s", email)
            raise AuthError(code="invalid_credentials", message="Invalid credentials")

        user_id = auth_response.user.id
        users_response = (
            supabase_admin.table("users")
            .select("id, email, role")
            .eq("id", user_id)
            .execute()
        )

        role = "user"
        user_email = auth_response.user.email or email

        if users_response.data and len(users_response.data) > 0:
            role = users_response.data[0].get("role", "user")
            user_email = users_response.data[0].get("email", user_email)
        else:
            logger.warning("[login] perfil não encontrado em public.users para user_id: %s", user_id)

        return {
            "access_token": auth_response.session.access_token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": user_email,
                "role": role,
            },
        }

    @staticmethod
    def signup(email: str, password: str, email_redirect_to: str) -> Dict[str, Any]:
        client = _fresh_auth_client()
        try:
            auth_response = client.auth.sign_up(
                {
                    "email": email,
                    "password": password,
                    "options": {"email_redirect_to": email_redirect_to},
                }
            )
        except AuthApiError as e:
            logger.warning("[signup] AuthApiError para %s: %s", email, e)
            raise AuthError(code="signup_failed", message=str(e))

        user = auth_response.user
        if not user:
            raise AuthError(code="signup_failed", message="Não foi possível criar o usuário.")

        return {"id": user.id, "email": user.email or email}

    @staticmethod
    def resend_confirmation(email: str, email_redirect_to: str) -> None:
        client = _fresh_auth_client()
        try:
            client.auth.resend(
                {
                    "type": "signup",
                    "email": email,
                    "options": {"email_redirect_to": email_redirect_to},
                }
            )
        except Exception:
            logger.info("[resend_confirmation] falha ao reenviar para %s (não revelado ao chamador)", email)

    @staticmethod
    def send_password_reset(email: str, redirect_to: str) -> None:
        client = _fresh_auth_client()
        try:
            client.auth.reset_password_for_email(email, {"redirect_to": redirect_to})
        except Exception:
            logger.info("[send_password_reset] falha ao enviar reset para %s (não revelado ao chamador)", email)

    @staticmethod
    def reset_password(access_token: str, refresh_token: str, new_password: str) -> None:
        try:
            session_client = get_session_scoped_client(access_token, refresh_token)
            session_client.auth.update_user({"password": new_password})
        except AuthApiError as e:
            logger.warning("[reset_password] AuthApiError: code=%s status=%s", getattr(e, "code", None), getattr(e, "status", None))
            raise AuthError(code="invalid_reset_token", message="Link inválido ou expirado. Solicite um novo.")
        except Exception as e:
            logger.exception("[reset_password] erro inesperado")
            raise AuthError(code="reset_failed", message=str(e))


auth_service = AuthService()
