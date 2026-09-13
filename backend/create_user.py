from dotenv import load_dotenv
import os
from supabase import create_client, Client
import argparse

def get_supabase_client():
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise ValueError("Faltam SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY no .env")
    return create_client(url, key)

def iter_auth_users(client):
    page = 1
    while True:
        try:
            response = client.auth.admin.list_users(page=page, per_page=1000)
            users = getattr(response, 'users', [])
        except AttributeError:
            # Compatibilidade com assinaturas antigas da SDK
            response = client.auth.admin.list_users(per_page=1000, page=page)
            users = getattr(response, 'users', [])
        if not users:
            break
        for user in users:
            yield user
        page += 1

def find_user_by_email(client, email):
    for user in iter_auth_users(client):
        if user.email == email:
            return user
    return None

def create_auth_user(client, email, password, name=None):
    data = {
        "email": email,
        "password": password,
        "email_confirm": True
    }
    if name:
        data["user_metadata"] = {"name": name}
    response = client.auth.admin.create_user(data)
    return response.user

def upsert_user_profile(client, user, role):
    data = {
        "id": user.id,
        "email": user.email,
        "role": role
    }
    client.table("users").upsert(data, on_conflict="id").execute()

def main():
    parser = argparse.ArgumentParser(description="Criar usuário comum no projeto DrTilápia")
    parser.add_argument("--email", required=True, help="Email do usuário")
    parser.add_argument("--password", required=True, help="Senha do usuário")
    parser.add_argument("--name", help="Nome do usuário (opcional)")
    parser.add_argument("--role", default="user", help="Role do usuário (padrão: user)")
    args = parser.parse_args()

    try:
        client = get_supabase_client()
        print("Cliente Supabase carregado.")

        user = find_user_by_email(client, args.email)
        if user:
            print(f"Usuário encontrado: {user.email} (ID: {user.id})")
        else:
            user = create_auth_user(client, args.email, args.password, args.name)
            print(f"Usuário criado: {user.email} (ID: {user.id})")

        upsert_user_profile(client, user, args.role)
        print("Perfil do usuário upsertado na tabela public.users.")
    except Exception as e:
        print(f"Erro: {str(e)}")

if __name__ == '__main__':
    main()
