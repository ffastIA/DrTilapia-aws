# Arquitetura de bucket S3 (AWS) — uso complementar ao Supabase Storage

## 1. Contexto

Hoje **todo o armazenamento persistente de arquivos do DrTilapIA já está no Supabase Storage**, não na AWS:

| Bucket (Supabase) | Conteúdo | Serviço responsável |
|---|---|---|
| `fish-images` (privado) | Fotos de peixe enviadas para análise de imagem | `backend/app/services/fish_image_service.py` |
| `videos` (privado) | Vídeos administrativos | `backend/app/services/video_service.py` |
| `rag-source-pdfs` (`RAG_SOURCE_PDFS_BUCKET`) | PDFs fonte do RAG, usados para reprocessamento/reindexação | `backend/app/services/rag_service.py` |

Não há nenhuma integração AWS/boto3/S3 no código, e nenhuma variável de ambiente relacionada em `backend/.env` / `.env.example` (hoje só `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`, etc.).

Este documento **não propõe substituir o Supabase Storage**. Ele mapeia a estrutura de diretórios do projeto para identificar onde um (ou mais) bucket S3 complementar faz sentido, e propõe a estrutura de pastas/prefixos que cada bucket teria — para você decidir a arquitetura final na AWS.

## 2. Estrutura de diretórios relevante para armazenamento

### Backend (`backend/`)

```
backend/
├── app/
│   ├── services/
│   │   ├── rag_service.py           # ingestão/processamento de PDF do RAG
│   │   ├── fish_image_service.py    # upload/download/signed URL de fotos de peixe
│   │   ├── video_service.py         # upload/download de vídeos
│   │   └── vector_admin_service.py
│   ├── main.py                      # usa tempfile.NamedTemporaryFile para uploads (PDF/imagem/vídeo)
│   │                                 # antes de enviar ao Supabase — nunca persiste em disco local
│   ├── uploads/, temp_uploads/      # vazios, não usados (legado)
├── docs/                            # PDFs fonte do corpus RAG, versionados no Git
│   ├── BIA_RAG.pdf
│   ├── BIP 2024 publicado.pdf
│   ├── Genetic and phenotypic characterization of Nile tilapia.pdf
│   ├── Indice volumetrico abate.pdf
│   └── Studium.pdf
├── evaluation/
│   └── runs/*.json                  # resultados de avaliação do RAG, JSON local com timestamp
├── uploaded_files/, uploads/        # vazios, não usados (legado, raiz do backend)
└── .env / .env.example              # sem variáveis AWS hoje
```

### Frontend (`frontend/`, Next.js App Router)

```
frontend/
├── app/main/
│   ├── admin/     # upload de PDF (.pdf) → POST /admin/upload → backend → Supabase "rag-source-pdfs"
│   ├── images/    # upload de foto de peixe (image/*) → backend → Supabase "fish-images"
│   ├── videos/    # upload de vídeo (.mp4/.webm/.mov) → backend → Supabase "videos"
│   └── profile/   # sem upload de avatar
├── public/        # assets estáticos locais: logo, imagens de hero/dashboard, favicon
└── lib/ragAdminApi.ts  # já modela storage_bucket/storage_path retornado pelo backend
```

Nenhuma referência a S3/AWS/CloudFront no frontend hoje.

## 3. Candidatos a uso complementar de S3

Cada linha abaixo é independente — escolha só o(s) que fizer(em) sentido para o seu caso.

### 3.1 Backup/arquivamento dos PDFs fonte do RAG

- **Origem:** `backend/docs/*.pdf` — hoje versionados no Git.
- **Bucket sugerido:** `drtilapia-rag-docs-backup`
- **Prefixos:**
  ```
  drtilapia-rag-docs-backup/
  └── source-pdfs/
      └── <nome-original>.pdf
  ```
- **Acesso:** privado (sem acesso público).
- **Motivo:** ter um repositório de disaster recovery fora do Git e do Supabase para os documentos-fonte do RAG.

### 3.2 Histórico de avaliação do RAG

- **Origem:** `backend/evaluation/runs/*.json` — hoje só local, sem persistência centralizada.
- **Bucket sugerido:** `drtilapia-eval-artifacts`
- **Prefixos:**
  ```
  drtilapia-eval-artifacts/
  └── runs/
      └── <timestamp>/
          └── run.json
  ```
- **Acesso:** privado.
- **Motivo:** manter histórico de qualidade do RAG (golden set, métricas) acessível entre máquinas/ambientes, sem depender do disco local de quem rodou a avaliação.

### 3.3 Arquivamento de logs de aplicação (opcional)

- **Origem:** hoje o logging é só `stdout` (`logging.basicConfig` em `backend/app/main.py`), sem persistência.
- **Bucket sugerido:** `drtilapia-app-logs`
- **Prefixos:**
  ```
  drtilapia-app-logs/
  └── backend/
      └── <ano>/<mes>/<dia>/
          └── <arquivo-de-log>
  ```
- **Acesso:** privado.
- **Motivo:** só relevante se decidir centralizar logs (ex.: para auditoria/observabilidade); hoje não há necessidade funcional, é opcional.

### 3.4 Hospedagem de assets estáticos do frontend via CDN (opcional)

- **Origem:** `frontend/public/` — logo, imagens de hero/dashboard, favicon.
- **Bucket sugerido:** `drtilapia-static-assets`
- **Prefixos:**
  ```
  drtilapia-static-assets/
  └── public/
      ├── images/
      └── icons/
  ```
- **Acesso:** público (via S3 + CloudFront), leitura apenas.
- **Motivo:** só relevante se quiser servir esses assets fora do deploy do Next.js (ex.: CDN dedicado); hoje o Next.js já serve `public/` diretamente, então isso é puramente opcional/performance.

## 4. Resumo

| Bucket S3 | Conteúdo | Origem no repo | Acesso | Prioridade |
|---|---|---|---|---|
| `drtilapia-rag-docs-backup` | PDFs fonte do RAG | `backend/docs/*.pdf` | Privado | Recomendado |
| `drtilapia-eval-artifacts` | Resultados de avaliação do RAG | `backend/evaluation/runs/*.json` | Privado | Recomendado |
| `drtilapia-app-logs` | Logs de aplicação | (não persistido hoje) | Privado | Opcional |
| `drtilapia-static-assets` | Assets estáticos do frontend | `frontend/public/` | Público (leitura) | Opcional |

Nenhuma dessas propostas requer alterar os buckets do Supabase Storage já em uso (`fish-images`, `videos`, `rag-source-pdfs`) — eles continuam sendo a fonte primária de armazenamento da aplicação.
