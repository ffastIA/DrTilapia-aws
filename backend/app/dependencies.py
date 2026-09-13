# CAMINHO: backend/app/dependencies.py
# ARQUIVO: dependencies.py

import logging

from app.database import supabase
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase_auth.errors import AuthApiError
from typing import Any

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict:
    """
    Dependência para obter o usuário atual autenticado via token JWT do Supabase.
    Valida o token, consulta a tabela 'users' e retorna os dados do usuário.
    """
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de acesso não fornecido")

    access_token = credentials.credentials

    try:
        # Validar o token com Supabase Auth
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado")

        user_id = user.id

        # Consultar a tabela 'users' para obter id, email e role
        response = supabase.table('users').select('id, email, role').eq('id', user_id).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Usuário não encontrado na tabela 'users'")

        user_data = response.data[0]

        # Retornar dicionário com os dados necessários
        return {
            'id': user_data['id'],
            'email': user_data['email'],
            'role': user_data['role'],
            'access_token': access_token
        }

    except HTTPException:
        # Repropagar exceções HTTP
        raise
    except AuthApiError as e:
        # Token expirado/revogado/malformado: o Supabase rejeita a chamada
        # `auth.get_user` levantando `AuthApiError` (ex.: 403 Forbidden) em
        # vez de devolver uma resposta com `user=None` — sem este catch,
        # caía no `except Exception` genérico abaixo e virava 500, mascarando
        # um problema de autenticação (sessão expirada) como erro de servidor.
        logger.warning(
            "[get_current_user] AuthApiError: code=%s status=%s",
            getattr(e, "code", None), getattr(e, "status", None),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado")
    except Exception as e:
        # Para erros genuinamente inesperados, retornar 500 — mas logar,
        # senão a causa raiz fica invisível para sempre.
        logger.exception("[get_current_user] erro inesperado ao validar token")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno do servidor")


async def get_current_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Dependência para verificar se o usuário atual é administrador.
    Retorna o usuário se for admin, caso contrário lança 403.
    """
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Acesso negado: apenas administradores podem acessar este recurso")

    return current_user