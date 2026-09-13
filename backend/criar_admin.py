from dotenv import load_dotenv
import os
from supabase import create_client, Client
import argparse


def get_supabase_client() -> Client:
    load_dotenv()
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(supabase_url, supabase_service_key)


def iter_auth_users(admin):
    page = 1
    max_per_page = 100
    while True:
        users_resp = None
        try:
            # Try list_users with pagination params
            try:
                users_resp = admin.list_users(page=page, per_page=max_per_page)
            except TypeError:
                try:
                    users_resp = admin.list_users(page=page, perPage=max_per_page)
                except TypeError:
                    pass
            if users_resp is None and page == 1:
                # Fallback to no params for first page
                try:
                    users_resp = admin.list_users()
                except TypeError:
                    pass
            if users_resp is None:
                break

            # Extract users robustly
            users = []
            if hasattr(users_resp, 'users'):
                users = getattr(users_resp, 'users', [])
            elif hasattr(users_resp, 'data'):
                data = getattr(users_resp, 'data', None)
                if isinstance(data, list):
                    users = data
                elif hasattr(data, 'users'):
                    users = getattr(data, 'users', [])
            elif isinstance(users_resp, list):
                users = users_resp

            for user in users:
                if hasattr(user, 'id') and hasattr(user, 'email'):
                    yield user

            if len(users) < max_per_page:
                break
            page += 1
        except Exception:
            break


def find_user_by_email(client, email):
    admin = client.auth.admin
    for user in iter_auth_users(admin):
        if user.email == email:
            return user
    return None


def create_auth_user(client, email, password, name=None):
    admin = client.auth.admin
    data = {
        'email': email,
        'password': password
    }
    if name:
        data['user_metadata'] = {'name': name}
    resp = admin.create_user(**data)
    # Extract user robustly
    user = None
    if hasattr(resp, 'user') and resp.user:
        user = resp.user
    elif hasattr(resp, 'data') and resp.data and hasattr(resp.data, 'user') and resp.data.user:
        user = resp.data.user
    if not user or not hasattr(user, 'id'):
        raise ValueError('Falha ao extrair usuário criado')
    return user


def upsert_user_profile(client, user, role):
    data = {
        'id': user.id,
        'email': user.email,
        'role': role
    }
    client.table('users').upsert(data, on_conflict='id').execute()


def main():
    parser = argparse.ArgumentParser(description='Criar ou atualizar admin no Supabase')
    parser.add_argument('--email', required=True, help='Email do admin')
    parser.add_argument('--password', required=True, help='Senha do admin')
    parser.add_argument('--name', help='Nome opcional do admin')
    parser.add_argument('--role', default='admin', help='Role do usuário (default: admin)')
    args = parser.parse_args()

    try:
        client = get_supabase_client()
        print('Cliente Supabase carregado.')

        existing_user = find_user_by_email(client, args.email)
        if existing_user:
            print(f'Usuário encontrado: {existing_user.email} (ID: {existing_user.id})')
            user = existing_user
        else:
            user = create_auth_user(client, args.email, args.password, args.name)
            print(f'Usuário criado: {user.email} (ID: {user.id})')

        upsert_user_profile(client, user, args.role)
        print(f'Perfil upsertado em public.users com role: {args.role}')
    except Exception as e:
        print(f'Erro: {e}')
        exit(1)

if __name__ == '__main__':
    main()
