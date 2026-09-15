## Context

`FishImageService.upload_image` (`backend/app/services/fish_image_service.py`) faz uma única tentativa de `self.supabase_admin.storage.from_(self.bucket).upload(...)`, sem tratamento de erro nessa linha específica — qualquer exceção sobe até `main.py`, que a converte num 500 genérico (`error-response-sanitization`, já aplicada). Investigação ao vivo (logs + `pg_stat_activity` no projeto Supabase) confirmou que o erro observado (`429 too_many_connections`) é transitório e do lado do Supabase, não um vazamento de conexão nem um bug de lógica nosso.

## Goals / Non-Goals

**Goals:**
- Um blip transitório do Storage (429/5xx) não deve mais exigir que o usuário clique em "Processar" de novo manualmente — o backend absorve isso com um retry curto.
- Erros genuinamente não-transitórios continuam falhando imediatamente, sem atraso artificial.

**Non-Goals:**
- Não aplicar o mesmo padrão a `video_service.py`/`vector_admin_repository.py` nesta mudança (fora de escopo, ver `proposal.md`).
- Não adicionar uma biblioteca de retry (`tenacity` ou similar) — o caso de uso é simples o suficiente para um loop manual, e o projeto não usa nenhuma lib assim hoje.
- Não mudar o comportamento de `_signed_url` (leitura, não upload) nem do insert na tabela `fish_images` — só a chamada de Storage em `upload_image`.

## Decisions

1. **Retry só na chamada de Storage, não no método inteiro.** Envolver todo `upload_image` (incluindo o insert na tabela) num retry seria mais arriscado — reexecutar o insert por engano em caso de sucesso parcial poderia duplicar metadados. O escopo do retry fica estritamente na chamada HTTP que falhou.
2. **Lista fixa de status retryable (`429, 500, 502, 503, 504`).** São os códigos convencionalmente transitórios (rate limit + erros de servidor); `403`/`404`/`413`/`422` (permissão, não encontrado, tamanho, validação) nunca são transitórios e não entram na lista.
3. **`file_obj.seek(0)` antes de cada tentativa.** O arquivo já é um handle local aberto via `with open(file_path, "rb") as f`, então é seguro e barato reler do início a cada tentativa (sem re-ler do disco em si, só resetar o ponteiro do arquivo já aberto).
4. **Backoff fixo curto (0.5s/1.5s/3s), não exponencial configurável.** O caso observado se resolveu em segundos; um backoff mais longo ou configurável via env seria over-engineering para o problema real observado.

## Risks / Trade-offs

- **[Risco de latência]** No pior caso (falha persistente), o usuário espera ~5s a mais antes de ver o erro, em vez de falhar imediatamente. Aceitável frente ao benefício de absorver o caso comum (blip de poucos segundos).
- **[Risco de mascarar um problema real]** Se o 429/5xx virar persistente (não transitório), o retry só atrasa a falha em ~5s — não esconde o erro indefinidamente, nem impede que ele seja investigado (o log de cada tentativa fica registrado via `logger.warning`).
