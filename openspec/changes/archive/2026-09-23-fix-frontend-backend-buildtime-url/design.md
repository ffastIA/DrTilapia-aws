## Context

`frontend/next.config.js` resolve o destino do proxy `/api-proxy/*` dentro de `rewrites()`:

```js
const backendUrl =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  'http://localhost:8000';
```

Em `output: 'standalone'`, essa função roda durante `next build` e o resultado é congelado em
`.next/routes-manifest.json` — já documentado no próprio `frontend.Dockerfile:20-25`. O
`docker-compose.yml` da raiz passa `BACKEND_INTERNAL_URL: http://backend:8000` como build arg (linha
76), valor que só faz sentido dentro da rede Docker de desenvolvimento local (`dr_tilapia_net`,
resolução por DNS de serviço do Compose). `deploy/build-and-push.ps1` builda a imagem de produção do
frontend chamando `docker compose build frontend` (linha 42 do script atual), herdando exatamente
esse valor de desenvolvimento — a imagem publicada no ECR para produção sairia com o proxy apontando
para um hostname que não existe fora do host de desenvolvimento.

## Goals / Non-Goals

**Goals:**
- Garantir que a imagem de produção do frontend seja buildada com `BACKEND_INTERNAL_URL` apontando
  para o endereço real do backend na VPC (IP privado da EC2 do backend, decisão já fechada com o
  usuário: IP direto, não DNS privado).
- Manter o build de desenvolvimento (`docker-compose.yml` raiz, `docker compose build` local)
  inalterado — continua usando `http://backend:8000`.

**Non-Goals:**
- Não introduz Route 53/DNS privado para o backend (decisão já tomada: IP direto — ver
  `add-two-ec2-deploy-topology`).
- Não altera `frontend/next.config.js` nem `frontend.Dockerfile` — o mecanismo de leitura do build
  arg já está correto.
- Não automatiza a obtenção do IP privado do backend (ex. via AWS CLI) — o valor é preenchido
  manualmente no script, no mesmo padrão já usado para `$AwsAccountId`/`$AwsRegion`.

## Decisions

### D1 — Build do frontend via `docker build` direto, não mais via `docker compose build`
`docker compose build frontend` sempre lê os `args:` declarados em `docker-compose.yml`
(`services.frontend.build.args`), que são fixos para o valor de desenvolvimento — não há como
sobrescrevê-los por variável de ambiente do host sem também editar o `docker-compose.yml` (o que
quebraria a paridade local). Chamar `docker build -f frontend.Dockerfile --build-arg
BACKEND_INTERNAL_URL=...` diretamente no script de produção desacopla completamente o build de
produção do arquivo de desenvolvimento. Alternativa descartada: usar `docker compose build` com um
`docker-compose.override.yml` de produção só para os build args — mais um arquivo para manter
sincronizado, sem ganho sobre passar os args diretamente no `docker build`.

### D2 — Variáveis de preenchimento manual no topo do script, mesmo padrão já existente
O script já tem um bloco `# ---- Preencher com os valores reais antes de usar ----` para
`$AwsAccountId`/`$AwsRegion`/`$EcrRepoBackend`/`$EcrRepoFrontend`. Adicionar
`$BackendInternalUrl`/`$NextPublicSupabaseUrl`/`$NextPublicSupabaseAnonKey` ao mesmo bloco mantém
consistência — sem introduzir um mecanismo novo (ex. ler de um `.env` separado) só para este caso.

## Risks / Trade-offs

- **[Risco] Se a EC2 do backend for recriada, o IP privado muda e a imagem do frontend já publicada
  no ECR fica com o proxy apontando para um IP morto.** → Mitigação: nenhuma automática (trade-off
  já aceito na decisão de usar IP direto em vez de DNS privado); documentar em
  `deploy/build-and-push.ps1` e em `deploy/README.md` (da change `add-two-ec2-deploy-topology`) que
  qualquer recriação da EC2 do backend exige rebuildar e republicar a imagem do frontend.
- **[Risco] Esquecer de preencher `$BackendInternalUrl` antes de rodar o script publica uma imagem
  quebrada.** → Mitigação: manter o padrão `<...>` como placeholder (igual às demais variáveis do
  script) e o `throw`/validação já existente no script para o SHA do commit pode ser estendido para
  validar que nenhuma variável ficou com o placeholder — tratado como tarefa de implementação.

## Migration Plan

1. Editar `deploy/build-and-push.ps1` com as novas variáveis e o novo comando de build do frontend.
2. Preencher `$BackendInternalUrl` com o IP privado real da EC2 do backend (definido/validado na
   change `add-two-ec2-deploy-topology`).
3. Rodar o script uma vez e inspecionar a imagem gerada (`docker run --rm
   drtilapia-aws-frontend:latest cat .next/routes-manifest.json` ou equivalente) para confirmar que
   o destino do rewrite aponta para o IP correto antes de publicar no ECR.

**Rollback**: como o script só afeta como a imagem é *buildada* (não o runtime), reverter é apenas
usar a imagem anteriormente publicada no ECR (tag anterior) via `IMAGE_TAG` no `deploy/.env` da EC2.

## Open Questions

Nenhuma — decisão de IP direto vs. DNS privado já fechada com o usuário antes desta change.
