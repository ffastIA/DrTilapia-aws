<#
.SYNOPSIS
    Builda as imagens do backend e do frontend, tageia cada uma como "latest"
    e envia pro ECR. Roda na máquina Windows onde o build já acontece hoje.

    O backend builda com `docker buildx build` passando o BuildKit secret do
    CA bundle corporativo (mesmo mecanismo usado antes via docker-compose,
    agora compatível com multi-arch).
    O frontend builda com `docker buildx build` passando BACKEND_INTERNAL_URL
    apontando para o IP privado real da EC2 do backend em produção - valor
    congelado na imagem no momento do build (ver frontend.Dockerfile e a
    change `fix-frontend-backend-buildtime-url`).

    Ambas as imagens são geradas para linux/amd64 e linux/arm64 e enviadas
    diretamente ao ECR via --push (sem docker tag / docker push separados).

    Pré-requisitos (uma vez só):
      - AWS CLI configurado (`aws configure`) com permissão de push nos 2
        repositórios ECR abaixo.
      - Os repositórios ECR já criados (ver deploy/README.md, passo 1).
      - Docker Desktop com suporte a buildx (já incluso nas versões recentes).
      - Preencher as 7 variáveis abaixo com os valores reais.

    Uso: .\deploy\build-and-push.ps1
#>

$ErrorActionPreference = "Stop"

# ---- Preencher com os valores reais antes de usar ----
$AwsAccountId              = "759328201443"
$AwsRegion                 = "sa-east-1"
$EcrRepoBackend            = "759328201443.dkr.ecr.sa-east-1.amazonaws.com/drtilapia-aws-backend"
$EcrRepoFrontend           = "759328201443.dkr.ecr.sa-east-1.amazonaws.com/drtilapia-aws-frontend"
$BackendInternalUrl        = "http://10.1.20.128:8000"
$NextPublicSupabaseUrl     = "https://tfdripphcwbjiveksuet.supabase.co"
$NextPublicSupabaseAnonKey = "sb_publishable_vtjWKBmND6gJMXgCH55pNw_5BICznza"
# --------------------------------------------------------

# Validar que nenhuma variável ficou com placeholder
$PlaceholderPattern = "^<.*>$"
$FilledVars = @{
    AwsAccountId              = $AwsAccountId
    AwsRegion                 = $AwsRegion
    EcrRepoBackend            = $EcrRepoBackend
    EcrRepoFrontend           = $EcrRepoFrontend
    BackendInternalUrl        = $BackendInternalUrl
    NextPublicSupabaseUrl     = $NextPublicSupabaseUrl
    NextPublicSupabaseAnonKey = $NextPublicSupabaseAnonKey
}
foreach ($name in $FilledVars.Keys) {
    if ($FilledVars[$name] -match $PlaceholderPattern) {
        throw "Variável `$$name` ainda está com o placeholder padrão ($($FilledVars[$name])) - preencha com o valor real antes de rodar este script."
    }
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Tag = "latest"
if ((git status --porcelain) -ne $null) {
    Write-Warning "Há mudanças não commitadas - a imagem 'latest' vai carregar esse código não commitado. Considere commitar antes de buildar para produção."
}

$EcrRegistry  = "$AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com"
$BackendImage  = "${EcrRepoBackend}:$Tag"
$FrontendImage = "${EcrRepoFrontend}:$Tag"

# ---- CA bundle corporativo (opcional, só define se o arquivo existir) ----
$CaBundlePath = Join-Path $RepoRoot "backend\ca-bundle-windows.pem"
if (Test-Path $CaBundlePath) {
    $env:AWS_CA_BUNDLE = $CaBundlePath
}

# ---- Autenticar no ECR ----
Write-Host "==> Autenticando no ECR ($EcrRegistry)" -ForegroundColor Cyan
(aws ecr get-login-password --region $AwsRegion) |
    docker login --username AWS --password-stdin $EcrRegistry

# ---- Criar/reutilizar builder multi-arch ----
Write-Host "==> Configurando builder multi-arch" -ForegroundColor Cyan
$builderExists = docker buildx inspect multi-arch-builder 2>$null
if ($LASTEXITCODE -ne 0) {
    docker buildx create --name multi-arch-builder --use
    docker buildx inspect --bootstrap multi-arch-builder
} else {
    docker buildx use multi-arch-builder
}

# ---- Build do backend ----
Write-Host "==> Build do backend (buildx multi-arch, com CA bundle secret)" -ForegroundColor Cyan
$env:DOCKER_BUILDKIT = "1"

if (Test-Path $CaBundlePath) {
    docker buildx build `
        --platform linux/amd64,linux/arm64 `
        --secret "id=ca_bundle,src=$CaBundlePath" `
        -t $BackendImage `
        --push `
        -f backend/backend.Dockerfile .
} else {
    docker buildx build `
        --platform linux/amd64,linux/arm64 `
        -t $BackendImage `
        --push `
        -f backend/backend.Dockerfile .
}

# ---- Build do frontend ----
Write-Host "==> Build do frontend (buildx multi-arch, com BACKEND_INTERNAL_URL de produção)" -ForegroundColor Cyan
# `next build` baixa o Google Fonts; atrás de proxy/antivírus com inspeção TLS
# precisa do mesmo CA bundle secret do backend (ver frontend.Dockerfile). Sem o
# arquivo, o build roda sem o secret, como antes.
$FrontendSecretArgs = @()
if (Test-Path $CaBundlePath) {
    $FrontendSecretArgs = @("--secret", "id=ca_bundle,src=$CaBundlePath")
}

docker buildx build `
    --platform linux/amd64,linux/arm64 `
    @FrontendSecretArgs `
    --build-arg BACKEND_INTERNAL_URL=$BackendInternalUrl `
    --build-arg NEXT_PUBLIC_SUPABASE_URL=$NextPublicSupabaseUrl `
    --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=$NextPublicSupabaseAnonKey `
    -t $FrontendImage `
    --push `
    -f frontend.Dockerfile .

Write-Host ""
Write-Host "Pronto. Imagens publicadas:" -ForegroundColor Green
Write-Host "  $BackendImage"
Write-Host "  $FrontendImage"
Write-Host ""
Write-Host "Nas instâncias EC2, autentique no ECR e rode:" -ForegroundColor Yellow
Write-Host "  docker pull <imagem>"
Write-Host "  docker stop <container> && docker rm <container>"
Write-Host "  docker run -d --name <container> --restart always -p <porta> <imagem>"