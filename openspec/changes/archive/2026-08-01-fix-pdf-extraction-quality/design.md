## Context

O gatilho atual (`rag_service.py:969-974`):

```python
def _is_text_garbled(self, text: str, threshold: float = 0.04) -> bool:
    if not text or len(text) < 50:
        return True
    ratio = text.count('?') / len(text)
    return ratio > threshold
```

Detecta exatamente dois casos: texto quase ausente e mojibake (`?` de caracteres não decodificados). O modo de falha real observado — extração que produz *estrutura sem conteúdo* — não se parece com nenhum dos dois.

`_validate_pdf_quality` (`:373`) é ainda mais frouxa: "> 50 caracteres, > 0 páginas".

A cascata em `_load_pdf_with_fallback` (`:196-263`) é PyPDFLoader → pdfplumber → Tesseract (`por+eng`, render a ~180 DPI) → GPT-4o-mini Vision (~150 DPI, `detail: high`). Cada estágio é aceito se produzir > 200 caracteres e não for "garbled". A maquinaria existe e é adequada; o problema é exclusivamente o critério de decisão.

Evidência quantitativa do acervo atual:

| Documento | Chunks | Palavras/chunk | % dígitos |
|---|---|---|---|
| Indice volumetrico abate | 6 | 216 | 1,4% |
| BIA_RAG | 5 | 255 | 4,4% |
| Genetic characterization | 26 | 394 | 6,0% |
| **BIP 2024 publicado** | 12 | **51** | **15,0%** |

A causa provável da falha é o layout: o BIP 2024 é um artigo de duas colunas com tabelas embutidas, caso conhecido de fragilidade do `pypdf`, que lê a camada de texto na ordem interna do arquivo e intercala as colunas.

## Goals / Non-Goals

**Goals:**
- Detectar extração incompleta antes que o documento entre na base.
- Acionar o resgate por OCR nesses casos, usando a cascata que já existe.
- Tornar a qualidade da extração auditável depois do fato.
- Falhar visivelmente quando o resgate não resolver, em vez de gravar lixo silenciosamente.
- Limitar o custo do OCR, que hoje é ilimitado.

**Non-Goals:**
- Não reescreve o parsing nem troca de biblioteca. O objetivo é acionar corretamente o que já existe.
- Não trata extração de tabelas como dado estruturado (`extract_tables()` do pdfplumber nunca é chamado). É uma melhoria real, mas separável — aqui basta que o texto da tabela exista.
- Não resolve o bloqueio do event loop durante o OCR (mudança de robustez).
- Não reingere o BIP 2024 automaticamente; a reingestão é operação da mudança de ingestão.

## Decisions

1. **Medir densidade de conteúdo por página, não apenas presença de texto.** O sinal que separa o BIP 2024 dos demais com folga é palavras por página. Um artigo científico tem tipicamente centenas de palavras por página; algumas dezenas indicam extração parcial. O limiar deve ser conservador — o objetivo é pegar falhas grosseiras como esta (51 vs 216-394), não afinar casos limítrofes.

2. **Avaliar o documento inteiro, além de página a página.** Uma capa ou uma página de referências legitimamente tem pouco texto; reprovar por página isolada geraria falsos positivos. O critério é a *fração* de páginas esparsas: um documento majoritariamente esparso está mal extraído, mesmo que nenhuma página isolada seja conclusiva.

3. **Combinar densidade com proporção de números isolados.** ~~Alta proporção de tokens muito curtos (≤2 caracteres) é sinal independente da densidade.~~ **CORRIGIDO durante a implementação — a formulação original estava errada.** A calibração contra os 4 documentos reais mostrou que a fração de tokens curtos **não discrimina**: o `Indice volumetrico abate.pdf`, íntegro, tem 0,335 contra 0,304 do BIP 2024 quebrado. A métrica estava medindo **idioma**, não qualidade — português é cheio de palavras de 1-2 caracteres (`de`, `a`, `o`, `em`, `no`). O mesmo vale para tokens de exatamente 1 caractere (0,163 no íntegro contra 0,157 no quebrado) e para a fração de palavras longas (sem separação).

   O sinal que de fato discrimina é a **fração de tokens puramente numéricos isolados**: 0,082 no BIP 2024 contra 0,005-0,023 nos três íntegros (separação de 3,5× a 16×). Faz sentido: são exatamente os `2` órfãos de R² e expoentes, e os números de p-values que perderam seu rótulo. Este é o segundo sinal, junto com a densidade de palavras.

   Lição registrada: a intuição sobre a assinatura do problema (`p` e `2` soltos) estava certa, mas a métrica escolhida para captá-la estava errada. Medir antes de implementar evitou embutir um detector que reprovaria documentos em português.

4. **Preservar `_is_text_garbled` como está e adicionar a nova verificação ao lado.** A detecção de mojibake funciona para o que se propõe; substituí-la seria trocar um problema por outro. A função nova é complementar, não substituta.

5. **Teto de páginas para o OCR por Vision, com falha explícita ao ultrapassar.** Hoje não há limite: um PDF de 300 páginas geraria 300 chamadas seriais a US$ 0,002-0,01 cada. Como esta mudança *aumenta* a frequência com que o Vision é acionado, o teto deixa de ser opcional. Ultrapassar o teto deve reportar o motivo ao usuário, não truncar silenciosamente.
   - Alternativa considerada: processar só as N primeiras páginas. Rejeitada — entregaria um documento parcial rotulado como completo, exatamente o problema que esta mudança combate.

6. **Registrar a qualidade da extração nos metadados do documento.** Método usado (`pypdf`/`pdfplumber`/`tesseract`/`vision`) e as métricas de densidade obtidas. Hoje `extraction_method` só é gravado nos caminhos de OCR, então é impossível distinguir "extraído bem pelo pypdf" de "extraído mal pelo pypdf" olhando a base. Foi exatamente essa cegueira que permitiu o problema passar despercebido por meses.

7. **Falha de extração é erro, não sucesso silencioso.** Se após a cascata a qualidade continuar abaixo do limiar, a ingestão deve retornar erro e **não gravar nada** — em vez de gravar chunks inúteis que poluem o índice e produzem recuperações enganosas.

## Calibração medida (2026-07-27)

Medida sobre o conteúdo já armazenado na base, que é exatamente a saída da extração — portanto é o dado certo para calibrar o detector.

| Documento | Palavras/chunk | Tokens ≤2 char | 1 caractere | **Números isolados** | Palavras ≥5 char |
|---|---|---|---|---|---|
| **BIP 2024 publicado** (quebrado) | **51** (27-124) | 0,304 | 0,157 | **0,082** | 0,542 |
| Indice volumetrico abate | 216 (165-260) | 0,335 | 0,163 | 0,005 | 0,473 |
| BIA_RAG | 255 (91-421) | 0,263 | 0,081 | 0,023 | 0,582 |
| Genetic characterization | 394 (104-610) | 0,165 | 0,036 | 0,008 | 0,556 |

**Sinais adotados** (os únicos que separam):
- **Palavras por chunk**: 51 contra 216-394 — separação de ~4×.
- **Fração de números isolados**: 0,082 contra 0,005-0,023 — separação de 3,5× a 16×.

**Sinais descartados**: tokens ≤2 caracteres, tokens de 1 caractere e palavras longas — todos com sobreposição entre documento bom e ruim (ver decisão 3).

**Observação sobre o nível de avaliação**: no nível de *chunk* as faixas se sobrepõem (BIA_RAG desce a 91 palavras; BIP sobe a 124). No nível de *documento* a separação é limpa (51 contra 216+). Isso confirma a decisão 2: o julgamento precisa ser do documento como um todo, não de páginas isoladas.

## Risks / Trade-offs

- **[Risco] Falso positivo em documentos legitimamente esparsos** (apresentações, planilhas exportadas, documentos com muitas figuras) → Mitigação: exigir os dois sinais (densidade + tokens órfãos) e avaliar a fração do documento, não páginas isoladas. Limiares conservadores, calibrados contra os 4 documentos conhecidos, sendo 3 bons e 1 ruim.
- **[Risco] Custo do OCR sobe** ao acionar Vision com mais frequência → Mitigação: o teto de páginas faz parte desta mudança, não de uma futura. Sem ele, a mudança é irresponsável.
- **[Risco] Ingestão fica muito mais lenta** para documentos que caem no OCR (minutos, bloqueando o event loop) → Aceito nesta mudança e sinalizado: o bloqueio é pré-existente e pertence à mudança de robustez. Vale registrar que a combinação (detecção mais sensível + ingestão bloqueante) piora a experiência antes de melhorar.
- **[Risco] Tesseract tem caminho de binário hardcoded** com um usuário específico (`rag_service.py:36-40`) → Se o Tesseract não estiver disponível, a cascata pula direto para o Vision, que é bem mais caro. Verificar disponibilidade e registrar qual estágio foi de fato usado.
- **[Bloqueio de verificação] O `BIP 2024 publicado.pdf` não está no repositório.** Sem ele, não há como confirmar que a correção resolve o caso que a motivou. O `Studium.pdf`, presente em `backend/docs/` e ausente da base, pode servir de caso de teste adicional, mas não substitui o original.
- **[Incerteza] Não está provado que o OCR resgata este documento.** A hipótese é forte (Vision lê layout de duas colunas muito melhor que `pypdf`), mas não foi testada. Se o resgate não funcionar, a mudança ainda entrega valor — o documento passa a falhar visivelmente em vez de entrar corrompido —, porém o conteúdo continuará indisponível.

## Migration Plan

Aditivo do ponto de vista de esquema: nenhuma alteração de banco. O impacto é comportamental, na ingestão.

1. Implementar a detecção e os limites, sem alterar documentos já ingeridos.
2. Verificar contra os 3 documentos íntegros que **não** há falso positivo (nenhum deles deve passar a acionar OCR).
3. Verificar contra o BIP 2024, quando disponível, que a falha é detectada.
4. A reingestão do BIP 2024 acontece na mudança de ingestão, que já prevê limpar e recarregar a base.

Rollback: reverter por git. Documentos já ingeridos não são afetados.

## Open Questions

- Se o resgate por Vision também não recuperar as tabelas do BIP 2024, vale implementar `pdfplumber.extract_tables()` como estágio dedicado? Fica em aberto até haver o teste com o arquivo real — decidir antes seria especular sobre uma falha ainda não observada.
