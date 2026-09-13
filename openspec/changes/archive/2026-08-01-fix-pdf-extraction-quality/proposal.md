## Why

Um dos 4 documentos da base vetorial foi ingerido praticamente vazio, e o sistema tratou isso como sucesso.

O `BIP 2024 publicado.pdf` — artigo científico de 12 páginas — produziu 12 chunks somando cerca de 600 palavras. A página 3, que contém os resultados zootécnicos, virou 265 caracteres de esqueleto:

```
...oxygen and transparency ( p
p
Zootechnical performance
p
(p
p  
found in survival.2
2
2 2, 
2 as 
and survival.
Table 1.
Treatment Weight gain (g) Final Biomass (g) FCR Survival (%)
```

O cabeçalho da tabela está lá, **sem nenhuma linha de dados**. Os `p` soltos são p-values que perderam os números; os `2` soltos são expoentes de R². Comparado aos outros documentos, o contraste é gritante: 51 palavras por chunk contra 216-394 dos demais, e 15% de dígitos contra 1,4-6%.

A ingestão **tem** uma cascata de resgate (pdfplumber → Tesseract → GPT-4o Vision) que muito provavelmente recuperaria esse conteúdo. Ela nunca foi acionada, porque o gatilho é cego a esse tipo de falha: `_is_text_garbled` só reprova texto com menos de 50 caracteres ou mais de 4% de `?`. Esse conteúdo tem 265 caracteres e zero `?` — passou.

O efeito prático é o pior possível: o documento consta na base, aparece na administração como ingerido com sucesso, ocupa espaço no índice e é recuperável em buscas — mas não contém a informação que o usuário acredita ter carregado. Uma falha visível seria muito melhor que este sucesso aparente.

## What Changes

- A validação de extração passa a detectar **texto extraído de forma incompleta**, e não apenas texto ausente ou com encoding quebrado. Densidade anormalmente baixa de conteúdo por página passa a ser sinal de falha.
- A avaliação passa a considerar o **documento como um todo**, não só páginas isoladas: um documento cuja maioria das páginas é esparsa aciona o resgate, mesmo que nenhuma página isolada seja extrema o bastante.
- A cascata de resgate existente (pdfplumber → Tesseract → Vision) passa a ser acionada nesses casos — o mecanismo já existe e não muda.
- Cada documento passa a registrar **como foi extraído e com que qualidade**, de modo que uma extração ruim seja auditável depois do fato, em vez de invisível.
- Uma extração que permanece pobre após esgotar a cascata passa a ser **reportada como falha ao usuário**, em vez de gravada silenciosamente como sucesso.
- **BREAKING** (operacional): documentos que hoje seriam aceitos passarão a ser rejeitados ou a percorrer o caminho de OCR, que é mais lento e tem custo por página. Por isso, esta mudança inclui um teto de páginas e um limite de tempo para o OCR por Vision, hoje inexistentes.

## Capabilities

### New Capabilities
- `pdf-extraction-quality`: detecção de extração incompleta, acionamento do resgate por OCR, registro auditável da qualidade de extração e limites de custo do OCR.

### Modified Capabilities
Nenhuma. `rag-ingestion-quality` (chunking e embeddings) trata do que acontece **depois** que o texto foi extraído; esta mudança trata de garantir que exista texto para processar.

## Impact

- `backend/app/services/rag_service.py`: `_is_text_garbled` (linha ~969), `_validate_pdf_quality` (~373), `_load_pdf_with_fallback` (~196) e o registro de metadados da ingestão.
- `backend/app/utils/pdf_cleaning.py`: a limpeza remove todas as linhas em branco, o que apaga um sinal estrutural útil para medir densidade — precisa ser avaliada em conjunto.
- Custo: acionar Vision mais vezes aumenta o custo de ingestão (~US$ 0,002-0,01 por página, hoje sem teto). O limite de páginas introduzido aqui é o que torna a mudança segura.
- Latência de ingestão: documentos que caírem no OCR levarão minutos em vez de segundos. A ingestão já é bloqueante (`ingest_pdf` é `async def` sem `await`), então isso agrava um problema existente — tratado na mudança de robustez, não aqui.
- **Dependência externa**: o `BIP 2024 publicado.pdf` **não está disponível no repositório** (só 3 dos 4 PDFs estão em `backend/docs/`). Sem ele não é possível verificar a correção contra o caso real que a motivou.
