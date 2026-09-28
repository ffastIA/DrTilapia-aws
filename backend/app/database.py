# CAMINHO: backend/app/database.py

import json
import logging
import os
import httpx
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client, ClientOptions


logger = logging.getLogger(__name__)


DEFAULT_SECRET_ID = 'tilapia/backend'
DEFAULT_AWS_REGION = 'sa-east-1'


def _load_secrets_from_aws() -> str:
    """Carrega os segredos do AWS Secrets Manager para `os.environ`.

    Só é chamado fora de desenvolvimento. Os valores do secret prevalecem sobre
    o que já estiver no ambiente — um valor antigo num `env_file` da instância
    não pode sobrepor silenciosamente o segredo vigente. Qualquer falha aborta
    a inicialização com uma mensagem clara; nunca cai para um estado parcial.
    Retorna o id do secret usado (nunca os valores).
    """
    secret_id = os.getenv('SECRET_ID') or DEFAULT_SECRET_ID
    region = os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION') or DEFAULT_AWS_REGION
    try:
        import boto3  # import tardio: dev não precisa da dependência nem do custo de memória

        client = boto3.client('secretsmanager', region_name=region)
        secret_string = client.get_secret_value(SecretId=secret_id)['SecretString']
        secrets = json.loads(secret_string)
        if not isinstance(secrets, dict):
            raise ValueError('o secret deve ser um objeto JSON chave/valor')
    except Exception as exc:
        raise RuntimeError(
            f"Não foi possível carregar o secret '{secret_id}' do AWS Secrets Manager "
            f"(região {region}): {type(exc).__name__}: {exc}. Verifique a role IAM da instância "
            f"(secretsmanager:GetSecretValue), o nome do secret (SECRET_ID) e a região (AWS_REGION)."
        ) from exc

    for key, value in secrets.items():
        os.environ[key] = str(value)
    return secret_id


# Ordem importa: o .env é carregado primeiro (sem sobrescrever variáveis já
# exportadas; não faz nada se o arquivo não existe, como na imagem de produção),
# porque é ele que define ENVIRONMENT=development no ambiente local.
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

_ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')
if _ENVIRONMENT == 'development':
    secrets_source = f'.env ({env_path})'
else:
    secrets_source = f'AWS Secrets Manager (secret {_load_secrets_from_aws()})'


# Lê as variáveis de ambiente obrigatórias
_MISSING_HINT = 'Configure-a no backend/.env (desenvolvimento) ou no secret do AWS Secrets Manager (produção)'

SUPABASE_URL = os.getenv('SUPABASE_URL')
if not SUPABASE_URL:
    raise ValueError(f'SUPABASE_URL é obrigatória. {_MISSING_HINT}')

SUPABASE_KEY = os.getenv('SUPABASE_KEY')
if not SUPABASE_KEY:
    raise ValueError(f'SUPABASE_KEY é obrigatória para autenticação comum. {_MISSING_HINT}')

SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
if not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError(
        'SUPABASE_SERVICE_ROLE_KEY é obrigatória para upload no Storage e operações administrativas. '
        'Sem ela, o cliente admin falhará silenciosamente em operações privilegiadas. '
        f'{_MISSING_HINT}'
    )


# Logs informativos seguros (sem expor segredos)
logger.info('Segredos carregados de: %s', secrets_source)
logger.info('Tipo de chave para supabase_auth: default_key')
logger.info('Tipo de chave para supabase_admin: service_role')


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
