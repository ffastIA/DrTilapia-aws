## Why

As duas maiores alavancas de qualidade de um RAG — o modelo de embedding e o tamanho do chunk — foram movidas na direção errada, por acidente, e o histórico do git registra a consequência.

| | `ea807e2` (versão anterior) | Hoje |
|---|---|---|
| Embeddings | `text-embedding-3-small` | `ada-002` (default silencioso) |
| chunk_size | 1000 | **4000** |
| chunk_overlap | 200 | 500 |

O modelo caiu para `ada-002` porque o argumento `model=` sumiu de `OpenAIEmbeddings()` na migração para LangGraph (`e8d0d5f`) — ninguém escolheu `ada-002`, ele é apenas o default da biblioteca. É um modelo de 2022, pior **e mais caro** que os da geração v3.

O `chunk_size` quadruplicou em `e8a8459`, commit cuja própria mensagem diz **"Piorou a qualidade da resposta"**. Chunks de 4000 caracteres diluem o sinal: um único vetor tenta representar ~1000 tokens cobrindo vários assuntos, então a similaridade fica morna para tudo e específica para nada. É a causa direta da recuperação imprecisa.

Somam-se dois defeitos estruturais da ingestão: o chunking é feito **por página**, então nenhum chunk atravessa a quebra de página e o overlap nunca cruza essa fronteira (conteúdo dividido entre duas páginas fica órfão); e os chunks não registram `chunk_index` nem `page` de forma utilizável, o que impede rastrear e citar a origem.

## What Changes

- Modelo de embedding passa a ser **explícito e configurável**, adotando um modelo da geração v3 com qualidade de recuperação superior — nunca mais dependendo de um default implícito da biblioteca.
- Tamanho e sobreposição de chunk voltam a uma ordem de grandeza adequada para recuperação, e passam a ser **configuráveis por ambiente**.
- O chunking passa a ser **contínuo ao longo do documento** em vez de reiniciar a cada página, preservando trechos que atravessam a quebra de página.
- Cada chunk passa a registrar sua **posição no documento e a(s) página(s) de origem**, tanto no metadado quanto em colunas consultáveis — pré-requisito para citação de fontes.
- **BREAKING**: trocar o modelo de embedding invalida todos os vetores existentes. A base precisa ser limpa e os documentos reingeridos. Vetores de modelos diferentes não são comparáveis entre si — misturá-los produziria similaridades sem sentido.

## Capabilities

### New Capabilities
- `rag-ingestion-quality`: garantias sobre o modelo de embedding, a estratégia de fragmentação e os metadados de rastreabilidade produzidos na ingestão.

### Modified Capabilities
Nenhuma spec existente muda de contrato. `rag-chat-vector-search` continua válida — o que muda é a qualidade do que ela recupera, não seu comportamento especificado.

## Impact

- `backend/app/services/rag_service.py`: construção de `OpenAIEmbeddings` e do `RecursiveCharacterTextSplitter`, pipeline de `ingest_pdf` e metadados por chunk.
- `backend/app/services/clean_reindex_service.py`: duplica hoje os mesmos parâmetros de chunking e constrói seu próprio `OpenAIEmbeddings` sem o cliente HTTP do projeto — precisa passar a compartilhar a mesma configuração, sob pena de reintroduzir a divergência.
- `backend/.env` / `.env.example`: novas variáveis de modelo e chunking.
- Banco: colunas de rastreabilidade (`page`, `chunk_index`) que o repositório de administração já espera ler e que hoje não existem.
- **Operacional**: exige limpar a base e reingerir os 4 documentos. O usuário confirmou ter todos os PDFs originais — sem eles, a mudança não seria executável, porque o sistema não guarda os arquivos originais.
- Custo: reingestão completa é desprezível neste volume; a mudança de modelo reduz o custo por token de embedding em relação ao `ada-002` atual.
