## Context

`ImageProcessingService.remove_background` (`backend/app/services/image_processing_service.py`) sempre chamou `rembg.remove(image_bytes)` sem `session=`, confiando no modelo default da biblioteca. `requirements.txt` pina `rembg[cpu]>=2.0.50` sem teto superior — um `pip install` novo (imagem rebuildada) pode trazer uma versão bem mais nova que muda esse default silenciosamente, como de fato aconteceu (`2.0.84`, default = `bria-rmbg`).

Diagnóstico ao vivo:
1. `docker compose logs backend` durante uma reprodução real mostrou `Child process [N] died` logo após `[img_proc] sem escala disponível` — o worker morre dentro da chamada ao `rembg`, sem traceback Python (crash nativo do onnxruntime).
2. Testado isoladamente dentro do container: `bria-rmbg` (1GB) trava/derruba o processo; `u2net` (176MB) roda a mesma imagem sem erro.
3. Depois de fixar `u2net`, uma nova reprodução ainda deu 500 — mas o log mostrou o download do modelo (`Downloading data from '...u2net.onnx'`) em andamento, e a análise terminava com sucesso ~50s depois, tempo suficiente para o cliente já ter desistido.

## Goals / Non-Goals

**Goals:**
- `remove_background` nunca mais depende do modelo default (móvel) de uma lib externa — modelo fixado explicitamente, configurável via env.
- Nenhuma requisição real paga o custo de download do modelo — isso acontece uma vez, no build da imagem.

**Non-Goals:**
- Não trocar de biblioteca de remoção de fundo (rembg continua adequado; o problema era o default não fixado, não a lib em si).
- Não investigar por que `bria-rmbg` especificamente crasha (memória, incompatibilidade de opset do onnxruntime, etc.) — fora do escopo; a mitigação (não usar esse modelo) já resolve o problema observado.
- Não adicionar um mecanismo genérico de fallback/retry para modelos de ML — esse pipeline já é síncrono e best-effort (`hasScale=False` já é tratado como aviso, não erro).

## Decisions

1. **Fixar `u2net`, não simplesmente "qualquer modelo mais leve que bria-rmbg".** É o modelo que o docstring da classe sempre disse usar ("rembg (U2Net)") — a correção restaura a intenção original, não introduz uma nova.
2. **`REMBG_MODEL` como env var, com `u2net` de default** — mesmo padrão já usado para `ARUCO_MARKER_SIZE_CM`/`ARUCO_DICT` no mesmo arquivo. Permite trocar o modelo deliberadamente no futuro (com teste antes), sem exigir mudança de código.
3. **Sessão cacheada em variável de módulo (`_rembg_session`), não recriada a cada chamada.** Evita reabrir o arquivo do modelo do disco a cada imagem processada — custo de I/O desnecessário, já que o modelo não muda entre chamadas.
4. **Pré-download no `Dockerfile`, não um script de start-up/entrypoint.** Baking no build garante que o modelo já está pronto assim que o container starta (consistente com o próprio comentário do Dockerfile sobre o `HEALTHCHECK` ter um `start-period` generoso para os workers "reimportarem toda a cadeia pesada") — nenhuma lógica de entrypoint adicional, nenhum risco de dois workers tentarem baixar o mesmo arquivo ao mesmo tempo na primeira requisição real.

## Risks / Trade-offs

- **[Tamanho de imagem]** +176MB na imagem do backend. Aceitável frente ao ganho de confiabilidade (sem isso, a mesma classe de problema — crash ou timeout — se repete a cada deploy/restart).
- **[Build requer rede]** Já era o caso (`pip install` de dependências pesadas como `torch`/`onnxruntime`); um download a mais do GitHub não muda o perfil de risco do build.
