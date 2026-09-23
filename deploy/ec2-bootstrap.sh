#!/usr/bin/env bash
# Roda UMA VEZ numa instância EC2 Ubuntu recém-criada, a partir deste mesmo
# diretório `deploy/` (copiado pra EC2 via scp/rsync — não precisa do resto
# do repositório). Pré-requisitos antes de rodar (ver deploy/README.md):
#   - Instance profile IAM anexado à instância, com permissão de leitura no
#     ECR (não usa chave estática — autentica via metadata da instância).
#   - `deploy/.env` criado a partir de `deploy/.env.prod.example`, preenchido.
#   - `backend/.env` de produção criado (ver deploy/README.md) neste mesmo
#     diretório, dentro de uma pasta `backend/`.
#
# Uso: sudo ./ec2-bootstrap.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

for f in .env docker-compose.prod.yml backend/.env; do
    if [ ! -f "$f" ]; then
        echo "ERRO: '$f' não encontrado em $SCRIPT_DIR — veja deploy/README.md antes de rodar este script." >&2
        exit 1
    fi
done

echo "==> Instalando Docker Engine + Compose plugin (se ainda não instalado)"
if ! command -v docker >/dev/null 2>&1; then
    apt-get update
    apt-get install -y ca-certificates curl
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin awscli
else
    echo "Docker já instalado, pulando."
fi

echo "==> Habilitando Docker no boot"
systemctl enable --now docker

echo "==> Configurando rotação de log do Docker (evita disco cheio)"
DAEMON_JSON=/etc/docker/daemon.json
if [ ! -f "$DAEMON_JSON" ] || ! grep -q '"max-size"' "$DAEMON_JSON" 2>/dev/null; then
    cat > "$DAEMON_JSON" <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
    systemctl restart docker
else
    echo "Rotação de log já configurada, pulando."
fi

echo "==> Autenticando no ECR (via instance profile IAM da própria instância)"
set -a
source .env
set +a
AWS_REGION="$(echo "$ECR_REGISTRY" | sed -E 's/.*\.dkr\.ecr\.([a-z0-9-]+)\.amazonaws\.com/\1/')"
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "==> Pull das imagens"
docker compose -f docker-compose.prod.yml --env-file .env pull

echo "==> Subindo os containers"
docker compose -f docker-compose.prod.yml --env-file .env up -d

echo ""
echo "Pronto. Verifique com:"
echo "  docker compose -f docker-compose.prod.yml --env-file .env ps"
echo "  curl -s http://localhost:8000/health"
