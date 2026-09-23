<#
    Builda as imagens do backend e do frontend, tageia cada uma com o SHA
    curto do commit atual e envia pro ECR. Roda na máquina Windows onde o
    build já acontece hoje.

    O backend builda a partir do docker-compose.yml de desenvolvimento (o
    mesmo usado localmente, com o BuildKit secret do CA bundle corporativo).
    O frontend builda com `docker build` direto (não via `docker compose
    build`) para poder passar BACKEND_INTERNAL_URL apontando para o IP
    privado real da EC2 do backend em produção — se usássemos `docker
    compose build`, herdaríamos o valor de desenvolvimento
    (`http://backend:8000`, hostname que só existe na rede Docker local),
    já que esse valor é congelado na imagem no momento do build (ver
    frontend.Dockerfile e a change `fix-frontend-backend-buildtime-url`).

    Pré-requisitos (uma vez só):
      - AWS CLI configurado (`aws configure`) com permissão de push nos 2
        repositórios ECR abaixo.
      - Os repositórios ECR já criados (ver deploy/README.md, passo 1).
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
$NextPublicSupabaseAnonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRmZHJpcHBoY3diaml2ZWtzdWV0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgwMjQxODUsImV4cCI6MjA5MzYwMDE4NX0.zXWNIEqFGR8kb6_xzF20MSHNds911TGyxIu7JVWdsA0"

# --------------------------------------------------------

$PlaceholderPattern = "^<.*>$"
$FilledVars = @{
    AwsAccountId              = $AwsAccountId
    AwsRegion                 = $AwsRegion
    EcrRepoBackend             = $EcrRepoBackend
    EcrRepoFrontend            = $EcrRepoFrontend
    BackendInternalUrl        = $BackendInternalUrl
    NextPublicSupabaseUrl     = $NextPublicSupabaseUrl
    NextPublicSupabaseAnonKey = $NextPublicSupabaseAnonKey
}
foreach ($name in $FilledVars.Keys) {
    if ($FilledVars[$name] -match $PlaceholderPattern) {
        throw "Variável `$$name` ainda está com o placeholder padrão ($($FilledVars[$name])) — preencha com o valor real antes de rodar este script."
    }
}

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
$BackendImage = "${EcrRepoBackend}:$Tag"
$FrontendImage = "${EcrRepoFrontend}:$Tag"

Write-Host "==> Build do backend (docker compose build)" -ForegroundColor Cyan
$env:DOCKER_BUILDKIT = "1"
docker compose build backend

Write-Host "==> Build do frontend (docker build direto, com BACKEND_INTERNAL_URL de produção)" -ForegroundColor Cyan
docker build -f frontend.Dockerfile `
    --build-arg BACKEND_INTERNAL_URL=$BackendInternalUrl `
    --build-arg NEXT_PUBLIC_SUPABASE_URL=$NextPublicSupabaseUrl `
    --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=$NextPublicSupabaseAnonKey `
    -t drtilapia-aws-frontend:latest .

Write-Host "==> Tageando imagens com $Tag" -ForegroundColor Cyan
docker tag drtilapia-aws-backend:latest $BackendImage
docker tag drtilapia-aws-frontend:latest $FrontendImage

Write-Host "==> Autenticando no ECR ($EcrRegistry)" -ForegroundColor Cyan
# Máquinas atrás do proxy corporativo de inspeção TLS precisam deste CA bundle
# para a CLI da AWS validar api.ecr.*.amazonaws.com (mesmo arquivo host-only
# usado pelo docker-compose.yml para o backend; ver comentário lá). Ausente
# em máquinas fora do proxy, então só define a variável se o arquivo existir.
$CaBundlePath = Join-Path $RepoRoot "backend\ca-bundle-windows.pem"
if (Test-Path $CaBundlePath) {
    $env:AWS_CA_BUNDLE = $CaBundlePath
}
(aws ecr get-login-password --region $AwsRegion) | docker login --username AWS --password-stdin $EcrRegistry

Write-Host "==> Enviando imagens para o ECR" -ForegroundColor Cyan
docker push $BackendImage
docker push $FrontendImage

Write-Host ""
Write-Host "Pronto. Imagens publicadas:" -ForegroundColor Green
Write-Host "  $BackendImage"
Write-Host "  $FrontendImage"
Write-Host ""
Write-Host "Atualize IMAGE_TAG no deploy/.env de cada EC2 (frontend e backend) com esta tag ($Tag) antes de fazer o pull." -ForegroundColor Yellow
