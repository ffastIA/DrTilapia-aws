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

[CmdletBinding()]
param(
    # Qual imagem buildar/enviar.
    [ValidateSet("all", "backend", "frontend")]
    [string]$Target = "all",
    # "both" = amd64 + arm64 (uma plataforma por vez, depois junta num manifest);
    # amd64/arm64 = só uma plataforma (mais leve; amd64 roda nativo, sem QEMU).
    [ValidateSet("both", "amd64", "arm64")]
    [string]$Platform = "both",
    # "lowmem-builder" = container BuildKit com max-parallelism=1 (menos memória),
    # mas NÃO confia na CA do proxy corporativo (x509 unknown authority ao falar
    # com o Docker Hub). "desktop-linux" usa o engine do Docker Desktop, que
    # confia. Use este se o lowmem-builder der erro de certificado.
    [ValidateSet("lowmem-builder", "desktop-linux")]
    [string]$Builder = "lowmem-builder"
)

$ErrorActionPreference = "Stop"

# ---- Preencher com os valores reais antes de usar ----
$AwsAccountId              = "759328201443"
$AwsRegion                 = "sa-east-1"
$EcrRepoBackend            = "759328201443.dkr.ecr.sa-east-1.amazonaws.com/drtilapia-aws-backend"
$EcrRepoFrontend           = "759328201443.dkr.ecr.sa-east-1.amazonaws.com/drtilapia-aws-frontend"
$BackendInternalUrl        = "http://10.1.2.22:8000"
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

# ---- Criar/reutilizar builder de baixo consumo de memória ----
# max-parallelism=1 (deploy/buildkitd.toml) + uma plataforma por vez evitam os
# picos de memória que derrubavam o build no Docker Desktop.
Write-Host "==> Configurando builder lowmem-builder" -ForegroundColor Cyan
if ($Builder -eq "desktop-linux") {
    docker buildx use desktop-linux
} else {
    $null = docker buildx inspect lowmem-builder 2>&1
    if ($LASTEXITCODE -ne 0) {
        docker buildx create --name lowmem-builder --driver docker-container `
            --buildkitd-config (Join-Path $PSScriptRoot "buildkitd.toml") --use
        if ($LASTEXITCODE -ne 0) { throw "Falha ao criar o builder." }
    } else {
        docker buildx use lowmem-builder
    }
}
$env:DOCKER_BUILDKIT = "1"

$Platforms = if ($Platform -eq "both") { @("amd64", "arm64") } else { @($Platform) }

# Builda+envia uma imagem, uma plataforma por vez. Com mais de uma plataforma,
# cada uma vai para "<imagem>-<arch>" e no fim um manifest multi-arch é criado
# em "<imagem>" (latest) sem rebuildar nada.
function Build-Image {
    param([string]$Image, [string]$Dockerfile, [string[]]$ExtraArgs)

    foreach ($arch in $Platforms) {
        $archTag = if ($Platforms.Count -gt 1) { "$Image-$arch" } else { $Image }
        Write-Host "    -> linux/$arch" -ForegroundColor DarkCyan
        docker buildx build --platform "linux/$arch" @ExtraArgs -t $archTag --push -f $Dockerfile .
        if ($LASTEXITCODE -ne 0) { throw "Build falhou ($Image, linux/$arch)." }
        # Libera cache/memória do builder antes da próxima plataforma/imagem.
        docker buildx prune --builder $Builder --force --filter "until=1h" | Out-Null
    }
    if ($Platforms.Count -gt 1) {
        docker buildx imagetools create -t $Image ($Platforms | ForEach-Object { "$Image-$_" })
        if ($LASTEXITCODE -ne 0) { throw "Falha ao criar o manifest multi-arch de $Image." }
    }
}

$SecretArgs = @()
if (Test-Path $CaBundlePath) {
    $SecretArgs = @("--secret", "id=ca_bundle,src=$CaBundlePath")
}

if ($Target -in @("all", "backend")) {
    Write-Host "==> Build do backend ($Platform)" -ForegroundColor Cyan
    Build-Image -Image $BackendImage -Dockerfile "backend/backend.Dockerfile" -ExtraArgs $SecretArgs
}

if ($Target -in @("all", "frontend")) {
    Write-Host "==> Build do frontend ($Platform, com BACKEND_INTERNAL_URL de produção)" -ForegroundColor Cyan
    # `next build` baixa o Google Fonts; atrás de proxy/antivírus com inspeção TLS
    # precisa do mesmo CA bundle secret do backend (ver frontend.Dockerfile).
    Build-Image -Image $FrontendImage -Dockerfile "frontend.Dockerfile" -ExtraArgs ($SecretArgs + @(
        "--build-arg", "BACKEND_INTERNAL_URL=$BackendInternalUrl",
        "--build-arg", "NEXT_PUBLIC_SUPABASE_URL=$NextPublicSupabaseUrl",
        "--build-arg", "NEXT_PUBLIC_SUPABASE_ANON_KEY=$NextPublicSupabaseAnonKey"))
}

Write-Host ""
Write-Host "Pronto. Imagens publicadas:" -ForegroundColor Green
if ($Target -in @("all", "backend"))  { Write-Host "  $BackendImage" }
if ($Target -in @("all", "frontend")) { Write-Host "  $FrontendImage" }
Write-Host ""
Write-Host "Nas instâncias EC2, autentique no ECR e rode:" -ForegroundColor Yellow
Write-Host "  docker pull <imagem>"
Write-Host "  docker stop <container> && docker rm <container>"
Write-Host "  docker run -d --name <container> --restart always -p <porta> <imagem>"