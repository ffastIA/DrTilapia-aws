## 1. Diagnóstico (reprodução real, não hipotética)

- [x] 1.1 Reproduzido o 500 no navegador (Chrome, login admin real) com 2 imagens reais fornecidas pelo usuário, em `/main/images`.
- [x] 1.2 `docker compose logs backend` durante a reprodução: encontrado `Child process [N] died` logo após `[img_proc] sem escala disponível` — crash de processo, sem traceback Python.
- [x] 1.3 Confirmado isoladamente dentro do container: `rembg==2.0.84` tem default `bria-rmbg` (~1GB); `new_session('u2net')` + `remove(..., session=...)` roda a mesma imagem sem crash.

## 2. Correção do modelo

- [x] 2.1 `image_processing_service.py`: modelo fixado via `REMBG_MODEL` (default `u2net`), sessão cacheada (`_get_rembg_session()`), `rembg_remove(image_bytes, session=...)`.
- [x] 2.2 `backend/.env.example`: documentado `REMBG_MODEL=u2net` com o histórico do problema.

## 3. Correção do timeout (2ª reprodução)

- [x] 3.1 Reproduzido de novo após 2.1 — ainda 500. Log mostrou download do `u2net.onnx` (176MB) em andamento; análise completou com sucesso no backend ~50s depois do request original (tarde demais para o cliente).
- [x] 3.2 `backend.Dockerfile`: adicionado `RUN python -c "from rembg import new_session; new_session('u2net')"` após `USER appuser` — pré-baixa o modelo no build.
- [x] 3.3 Rebuild do backend; confirmado via `docker compose exec` que o arquivo do modelo (176MB) já existe na imagem antes de qualquer requisição.

## 4. Verificação final

- [x] 4.1 **Teste real no navegador** (3ª reprodução, mesmas 2 imagens do usuário): "Análise concluída com sucesso!" — resultados exibidos (máscara verde de remoção de fundo, dimensões em px, avisos corretos de "ArUco não detectado"/"peso não informado" para os campos opcionais não preenchidos). Sem crash, sem delay perceptível.
- [x] 4.2 Suíte `pytest`: 133 passed, 0 failed, 11 skipped (sem regressão).
