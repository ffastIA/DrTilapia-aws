# CAMINHO: backend/app/database.py

import logging
import os
import httpx
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client, ClientOptions


logger = logging.getLogger(__name__)


# Carrega o arquivo .env do backend
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


# Lê as variáveis de ambiente obrigatórias
SUPABASE_URL = os.getenv('SUPABASE_URL')
if not SUPABASE_URL:
    raise ValueError('SUPABASE_URL é obrigatória. Configure-a no backend/.env')

SUPABASE_KEY = os.getenv('SUPABASE_KEY')
if not SUPABASE_KEY:
    raise ValueError('SUPABASE_KEY é obrigatória para autenticação comum. Configure-a no backend/.env')

SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
if not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError(
        'SUPABASE_SERVICE_ROLE_KEY é obrigatória para upload no Storage e operações administrativas. '
        'Sem ela, o cliente admin falhará silenciosamente em operações privilegiadas. '
        'Configure-a no backend/.env'
    )


# Variáveis expostas para depuração e compatibilidade
supabase_env_path = str(env_path)
supabase_auth_key_type = 'default_key'
supabase_admin_key_type = 'service_role'


# Logs informativos seguros (sem expor segredos)
logger.info(f'Arquivo .env carregado: {supabase_env_path}')
logger.info(f'Tipo de chave para supabase_auth: {supabase_auth_key_type}')
logger.info(f'Tipo de chave para supabase_admin: {supabase_admin_key_type}')


def _resolve_ssl_verify():
    """Resolve o valor de verificação TLS para os clientes httpx.

    Por padrão, verifica o certificado do servidor normalmente (`True`).
    Se o ambiente estiver atrás de um proxy corporativo de inspeção TLS,
    define `SSL_CERT_FILE` ou `REQUESTS_CA_BUNDLE` apontando para o CA
    bundle do proxy — nunca desabilite a verificação por completo.
    """
    return os.getenv('SSL_CERT_FILE') or os.getenv('REQUESTS_CA_BUNDLE') or True


_ssl_options = ClientOptions(httpx_client=httpx.Client(verify=_resolve_ssl_verify()))

# Cria os clientes Supabase
supabase_auth: Client = create_client(SUPABASE_URL, SUPABASE_KEY, options=_ssl_options)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, options=_ssl_options)

# Alias legado para compatibilidade com código existente
supabase: Client = supabase_admin


def get_user_scoped_client(access_token: str) -> Client:
    """Cria um cliente Supabase novo, autenticado como o usuário chamador.

    Usa a chave `anon` (baixo privilégio) e autentica as requisições
    PostgREST subsequentes com o access_token do próprio usuário, ativando
    Row Level Security. Cada chamada cria um cliente descartável — nunca
    reaproveita um cliente compartilhado entre requisições/usuários
    diferentes (mesmo padrão usado para isolar o login nesta sessão).
    """
    client = create_client(
        SUPABASE_URL,
        SUPABASE_KEY,
        options=ClientOptions(httpx_client=httpx.Client(verify=_resolve_ssl_verify())),
    )
    client.postgrest.auth(access_token)
    return client


def get_session_scoped_client(access_token: str, refresh_token: str) -> Client:
    """Cria um cliente Supabase novo com sessão GoTrue completa.

    Diferente de `get_user_scoped_client` (que só autentica consultas
    PostgREST), este estabelece uma sessão de auth completa via
    `client.auth.set_session(...)` — necessário para chamadas que mutam o
    próprio usuário autenticado (ex.: `update_user` ao redefinir senha).
    """
    client = create_client(
        SUPABASE_URL,
        SUPABASE_KEY,
        options=ClientOptions(httpx_client=httpx.Client(verify=_resolve_ssl_verify())),
    )
    client.auth.set_session(access_token, refresh_token)
    return client
