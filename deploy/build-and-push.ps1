<#
    Builda as imagens do backend e do frontend a partir do docker-compose.yml
    de desenvolvimento (o mesmo usado localmente, com o BuildKit secret do CA
    bundle corporativo), tageia cada uma com o SHA curto do commit atual e
    envia pro ECR. Roda na máquina Windows onde o build já acontece hoje.

    Pré-requisitos (uma vez só):
      - AWS CLI configurado (`aws configure`) com permissão de push nos 2
        repositórios ECR abaixo.
      - Os repositórios ECR já criados (ver deploy/README.md, passo 1).
      - Preencher as 4 variáveis abaixo com os valores reais.

    Uso: .\deploy\build-and-push.ps1
#>

$ErrorActionPreference = "Stop"

# ---- Preencher com os valores reais antes de usar ----
$AwsAccountId      = "<AWS_ACCOUNT_ID>"
$AwsRegion         = "<AWS_REGION>"
$EcrRepoBackend    = "<ECR_REPO_BACKEND>"
$EcrRepoFrontend   = "<ECR_REPO_FRONTEND>"
# --------------------------------------------------------

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Tag = (git rev-parse --short HEAD).Trim()
if ([string]::IsNullOrWhiteSpace($Tag)) {
    throw "Não foi possível obter o SHA do commit atual (git rev-parse falhou)."
}
if ((git status --porcelain) -ne $null) {
    Write-Warning "Há mudanças não commitadas — a imagem vai carregar código diferente do que 'git rev-parse' está tageando. Considere commitar antes de buildar para produção."
}

$EcrRegistry = "$AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com"
$BackendImage = "$EcrRegistry/${EcrRepoBackend}:$Tag"
$FrontendImage = "$EcrRegistry/${EcrRepoFrontend}:$Tag"

Write-Host "==> Build das imagens (docker compose build)" -ForegroundColor Cyan
$env:DOCKER_BUILDKIT = "1"
docker compose build backend frontend

Write-Host "==> Tageando imagens com $Tag" -ForegroundColor Cyan
docker tag drtilapia-aws-backend:latest $BackendImage
docker tag drtilapia-aws-frontend:latest $FrontendImage

Write-Host "==> Autenticando no ECR ($EcrRegistry)" -ForegroundColor Cyan
(aws ecr get-login-password --region $AwsRegion) | docker login --username AWS --password-stdin $EcrRegistry

Write-Host "==> Enviando imagens para o ECR" -ForegroundColor Cyan
docker push $BackendImage
docker push $FrontendImage

Write-Host ""
Write-Host "Pronto. Imagens publicadas:" -ForegroundColor Green
Write-Host "  $BackendImage"
Write-Host "  $FrontendImage"
Write-Host ""
Write-Host "Atualize deploy/docker-compose.prod.yml com esta tag ($Tag) antes de fazer o pull na EC2." -ForegroundColor Yellow
