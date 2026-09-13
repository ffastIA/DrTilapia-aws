## 1. Calibrar os limiares contra dados reais

- [x] 1.1 **PARCIALMENTE DESBLOQUEADO (2026-08-01)** — o usuário forneceu um `BIP 2024 publicado.pdf` (`backend/docs/`). **Achado importante**: esse exemplar tem **16 páginas**, não 12 como o documentado neste `design.md` — é uma versão diferente (provavelmente a versão final "publicada", com camada de texto correta) da que originou o problema, não o mesmo arquivo quebrado. Ver task 6.2/6.3 para o que isso implica. O `Genetic and phenotypic characterization of Nile tilapia.pdf` continua indisponível.
- [x] 1.2 Extrair, para cada um dos 4 documentos, as métricas candidatas por página: palavras por página, caracteres por página, proporção de tokens com 1-2 caracteres, proporção de dígitos.
- [x] 1.3 Limiares escolhidos: `MIN_WORDS_PER_PAGE=120`, `MAX_ISOLATED_NUMBER_RATIO=0.05`, `MAX_SPARSE_PAGE_RATIO=0.5`. **Duas métricas foram testadas e descartadas** (tokens ≤2 char e de 1 char) por não discriminarem — ver decisão 3 corrigida no design. Original: escolher os limiares que separam com folga os 3 documentos íntegros (216-394 palavras/chunk) do BIP 2024 (51). **Limiares conservadores** — o alvo é falha grosseira, não caso limítrofe.
- [x] 1.4 Registrado no design (seção 'Calibração medida'). **Margem obtida**: documentos íntegros entre 0% e 25% de páginas esparsas; BIP 2024 em 92%, contra limiar de 50%.

## 2. Detecção de extração incompleta

- [x] 2.1 Criar a função de avaliação de densidade por página (palavras/página + proporção de tokens órfãos), separada de `_is_text_garbled`, que permanece intacta (decisão 4).
- [x] 2.2 Criar a avaliação em nível de documento: fração de páginas esparsas acima da qual o documento é reprovado.
- [x] 2.3 Integrar a nova avaliação ao critério de aceite de cada estágio da cascata em `_load_pdf_with_fallback` (~linha 196), que hoje aceita por "> 200 caracteres e não garbled".
- [x] 2.4 Endurecer `_validate_pdf_quality` (~linha 373), hoje "> 50 caracteres, > 0 páginas".
- [x] 2.5 **Decidido: medir ANTES da limpeza.** A avaliação roda dentro de `_load_pdf_with_fallback`, que é anterior a `clean_loaded_pages` — é o ponto certo, porque o que se julga é a saída do *extrator*, não do limpador. A remoção de linhas em branco não afeta contagem de palavras, e a de números de página remove poucos tokens. Confirmado empiricamente: os valores medidos nos PDFs reais (BIA_RAG 255, Indice 216 palavras/página) batem com os da calibração feita sobre o conteúdo já armazenado (pós-limpeza).

## 3. Limites de custo do OCR

- [x] 3.1 Adicionar `OCR_MAX_PAGES` (configurável, com default conservador) em `.env.example` e `.env`.
- [x] 3.2 Aplicar o teto ao caminho de Vision (`_extract_text_via_vision`, ~linha 312), que hoje processa páginas em laço serial sem limite algum.
- [x] 3.3 Ultrapassar o teto deve **falhar com motivo explícito**, nunca truncar silenciosamente (decisão 5).
- [x] 3.4 Adicionar timeout por página nas chamadas de Vision (hoje inexistente).
- [x] 3.5 Verificar disponibilidade do Tesseract antes de tentá-lo — o caminho do binário é hardcoded com um usuário específico (`rag_service.py:36-40`); se ausente, a cascata pula para o Vision, que é muito mais caro, e isso precisa ficar registrado em log.

## 4. Registro auditável da qualidade

- [x] 4.1 Gravar `extraction_method` para **todos** os caminhos, inclusive quando o `pypdf` primário funciona — hoje só os caminhos de OCR gravam esse campo.
- [x] 4.2 Gravar as métricas de qualidade obtidas (densidade, proporção de tokens órfãos) nos metadados do documento.
- [x] 4.3 Confirmado: cada chunk passa a carregar `extraction_method` e `extraction_quality` (páginas, palavras totais, média por página, fração de números isolados, páginas esparsas, veredito e motivo). Exemplo real gravado para `Studium.pdf`: `{"pages":1,"total_words":228,"mean_words_per_page":228.0,"mean_isolated_number_ratio":0.0,"sparse_pages":0,"adequate":true}`. **Ressalva**: os 49 chunks já existentes na base não têm esses campos — só documentos ingeridos daqui em diante.

## 5. Falha visível

- [x] 5.1 Quando a cascata se esgotar sem qualidade adequada, retornar erro de ingestão com a causa identificada como qualidade de extração.
- [x] 5.2 Garantir que **nenhum chunk** do documento seja gravado nesse caso — hoje a ingestão não é transacional e uma falha parcial deixa chunks órfãos (a correção definitiva de transacionalidade é da mudança de robustez; aqui basta não gravar quando a extração reprova, o que acontece antes de qualquer escrita).
- [x] 5.3 Propagar a mensagem até a resposta de `POST /admin/upload`, para que o usuário saiba que o documento não entrou e por quê.

## 6. Verificação

- [x] 6.1 **Não-regressão VERIFICADA nos 3 PDFs disponíveis** (`BIA_RAG`, `Indice volumetrico abate`, `Studium`): todos aceitos pelo caminho primário `pypdf`, **sem acionar OCR**, com 216-255 palavras/página. O `Genetic characterization` não pôde ser testado (PDF ausente do repositório), mas sua avaliação sobre o conteúdo armazenado dá 639 palavras/página e 25% de esparsas — bem dentro do aceito. Original: **Não-regressão (o mais importante)**: os 3 documentos íntegros (`Genetic characterization`, `BIA_RAG`, `Indice volumetrico abate`) devem continuar sendo extraídos pelo caminho primário, **sem acionar OCR**. Falso positivo aqui custa tempo e dinheiro em toda ingestão futura.
- [x] 6.2 **RESOLVIDO DE FORMA DIFERENTE DO PREVISTO (2026-08-01).** O exemplar fornecido pelo usuário não reproduz a extração ruim original: rodado via `rag_service.ingest_pdf` real (após apagar os 12 chunks antigos e quebrados da base — `documents_deleted: 12`), a ingestão foi aceita **pelo `pypdf` primário, sem acionar nenhum fallback**: 16 páginas, 26 chunks, 10.351 palavras, 646.9 palavras/página, 25% de páginas esparsas (limiar 50%), `adequate: true`. Conteúdo verificado por amostragem (página 3: texto corrido e legível do artigo, rodapé "3/16" consistente). Isso confirma que o detector **aceita corretamente** um documento bom real — reforça 6.1 — mas não prova que ele **rejeita** o caso especificamente quebrado, porque este exemplar não é esse caso.
- [ ] 6.3 **AINDA EM ABERTO — questão mais importante da mudança permanece sem resposta.** Como o exemplar disponível não reproduz a extração ruim, o cenário "Vision recupera as linhas da Table 1" não foi exercitado com conteúdo real (só com o PDF sintético da 6.5). Seria necessário o exemplar *original*, especificamente o que gerou os 12 chunks de ~51 palavras cada — se esse arquivo não existir mais, a questão fica estruturalmente sem como ser respondida com este documento, e passa a depender de outro documento real que reproduza extração ruim.
- [x] 6.4 Testado com `OCR_MAX_PAGES=2` sobre um PDF maior: levanta `ExtractionCostLimitExceeded` **antes de processar qualquer página** (o `pdf.close()` acontece antes do laço), com mensagem indicando o número de páginas e o limite. Nenhuma gravação parcial.
- [x] 6.5 Coberto indiretamente pelo teste de falha visível: um PDF sintético esparso percorreu a cascata inteira (`pypdf` → `pdfplumber` → Tesseract → **Vision OCR executou de fato**) antes de ser rejeitado. Confirma que o caminho de OCR está funcional. **Ressalva**: o binário do Tesseract não está instalado (só o wrapper Python), então esse estágio falha graciosamente e escala para o Vision — que é mais caro. Vale instalar o binário se o custo importar.
- [x] 6.6 `Studium.pdf`: aceito pelo `pypdf` com 228 palavras/página e 0% de páginas esparsas — decisão sensata, nenhum OCR desnecessário.
- [ ] 6.7 **Ainda não medido em documento real** — sem o cenário de 6.3 exercitado, não há OCR real a instrumentar. Permanece pendente, mesma causa de 6.3.

## 7. Reingestão do documento afetado

- [x] 7.1 **FEITO (2026-08-01), fora da ordem originalmente prevista.** A reingestão não aconteceu via `restore-embedding-and-chunking-quality` como o plano original previa — aconteceu diretamente nesta sessão, com o código desta mudança já aplicado: os 12 chunks antigos foram apagados (`vector_admin_repository.delete_file`) e o documento foi reingerido via `rag_service.ingest_pdf` com o exemplar fornecido pelo usuário. Resultado em 6.2. A base agora tem uma versão boa do BIP 2024 (26 chunks, extração adequada) em vez da quebrada.
- [x] 7.2 **FEITO (2026-08-01).** Adicionadas 5 perguntas sobre o BIP 2024 ao `golden_set.yaml` (2 quantitativas, 1 conceitual, 1 metodológica, 1 follow-up), todas com `expected_passages` extraídos literalmente dos chunks reais armazenados. `python -m evaluation.validate_golden_set` confirmou: 63 chunks na base, 28 perguntas, 40 trechos checados, todos presentes — "OK, todos os trechos esperados existem na base".
