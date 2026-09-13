import os
import re
import time
import json
import hashlib
import logging
import asyncio
import unicodedata
import httpx
from typing import TypedDict, Dict, Any, List, Literal, Optional, Tuple, NamedTuple

logger = logging.getLogger(__name__)
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_community.document_loaders import PyPDFLoader
try:
    import pdfplumber
    _PDFPLUMBER_AVAILABLE = True
except ImportError:
    _PDFPLUMBER_AVAILABLE = False

try:
    import fitz as _fitz  # PyMuPDF — renderização de páginas para Vision OCR / Tesseract
    _PYMUPDF_AVAILABLE = True
except ImportError:
    _PYMUPDF_AVAILABLE = False

try:
    import pytesseract as _pytesseract
    _PYTESSERACT_AVAILABLE = True
except ImportError:
    _PYTESSERACT_AVAILABLE = False

# Locais comuns do Tesseract no Windows
_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\usuario\AppData\Local\Tesseract-OCR\tesseract.exe",
]
from langgraph.graph import StateGraph, END
from app.database import supabase_admin, _resolve_ssl_verify
from app.utils.pdf_cleaning import clean_loaded_pages, is_editorial_or_low_value, contains_scientific_signal
from app.utils.extraction_quality import assess_extraction, ExtractionQuality
from app.utils.chunking import split_pages_continuous
from app.utils.answer_quality import looks_like_empty_skeleton, find_unsupported_numbers
from app.utils.rag_config import (
    EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, CHUNK_SIZE, CHUNK_OVERLAP,
    RETRIEVAL_K, RETRIEVAL_K_RETRY, REFUSAL_FLOOR_SIMILARITY,
    PRIMARY_RPC_SIMILARITY_THRESHOLD,
    CONTEXT_MIN_CHUNKS, CONTEXT_MAX_CHUNKS, CONTEXT_CHAR_BUDGET,
    CONTEXT_RELATIVE_MARGIN, CONTEXT_ABSOLUTE_FLOOR, CITATION_MAX_FILES,
    GENERATION_MODEL, UTILITY_MODEL,
    DATA_COMPANION_ENABLED, DATA_COMPANION_MAX_TOTAL,
    HYBRID_SEARCH_ENABLED, RRF_K, LEXICAL_DISCRIMINATIVE_MAX_DOC_FREQ,
    MULTI_QUERY_EXPANSION_ENABLED, MULTI_QUERY_VARIANT_COUNT,
)


# Bucket dedicado aos PDFs originais — persistidos para reprocessamento/
# auditoria futuros, já que a extração/chunking pode mudar e o arquivo
# temporário de upload é descartado logo após a ingestão.
RAG_SOURCE_PDFS_BUCKET = os.getenv("RAG_SOURCE_PDFS_BUCKET", "rag-source-pdfs")

# Limites do OCR por página (custo ~US$ 0,002-0,01/página no Vision).
# Sem teto, um PDF de centenas de páginas gera centenas de chamadas pagas.
OCR_MAX_PAGES = int(os.getenv("OCR_MAX_PAGES", "40"))
OCR_PAGE_TIMEOUT_SECONDS = float(os.getenv("OCR_PAGE_TIMEOUT_SECONDS", "60"))


class ExtractionCostLimitExceeded(Exception):
    """OCR por página excederia o teto configurado.

    Levantada em vez de truncar: entregar um documento parcial rotulado como
    completo é o problema que a detecção de extração se propõe a evitar.
    """


class State(TypedDict):
    question: str
    context: str
    answer: str
    evaluation: str
    language: str
    history: List[List[str]]   # pares [pergunta_humano, resposta_ai]
    question_type: str         # quantitative | conceptual | comparative | methodological
    insufficient_context: bool  # True quando nenhum chunk atinge o piso de recusa
    source_docs: List[Dict[str, Any]]  # metadata leve dos chunks usados, para citação
    context_confidence: str    # strong | partial — ver `_select_context_docs`/design.md
    effective_type: str        # question_type efetivo usado na geração (pode divergir do original)
    unsupported_numbers: List[str]  # números da resposta ausentes do contexto — ver `verify_numeric`
    numeric_regen_count: int   # tentativas de regeneração por `verify_numeric` (máx. 1)
    context_sufficiency: str   # sufficient | partial | insufficient — ver `grade_context`
    retrieval_query: str       # pergunta condensada (follow-up + histórico), usada na busca
    reformulation_count: int   # tentativas de reformulação de query (máx. 1) — ver `reformulate_and_retrieve`


class AnswerResult(NamedTuple):
    """Retorno de `get_answer`: a resposta e as fontes reais que a embasaram.

    Fontes vêm vazias em caso de recusa (nenhum chunk confiável o suficiente).
    """
    answer: str
    sources: List[Dict[str, Any]]
    # Campos internos para consumo do harness de avaliação (ex.: `context`, o
    # texto exato enviado à chamada de geração) — não é contrato de API
    # pública, produção (`main.py`) não deve depender deste campo. `None` em
    # vez de `{}` como default: um dict mutável compartilhado entre todas as
    # instâncias que não passam `debug=` seria um risco real de mutação
    # cruzada entre chamadas.
    debug: Optional[Dict[str, Any]] = None


class RAGService:
    def __init__(
            self,
            openai_api_key: str,
            supabase_url: str,
            supabase_key: str,
    ):
        # Verificação TLS por padrão; use SSL_CERT_FILE/REQUESTS_CA_BUNDLE para
        # apontar o CA bundle de um proxy corporativo de inspeção TLS, se necessário.
        _ssl_verify = _resolve_ssl_verify()
        _http_client = httpx.Client(verify=_ssl_verify)
        _http_async_client = httpx.AsyncClient(verify=_ssl_verify)

        self.embeddings = OpenAIEmbeddings(
            openai_api_key=openai_api_key,
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
            http_client=_http_client,
            http_async_client=_http_async_client,
        )
        # Modelo de geração final (só o nó `generate`) separado do modelo
        # utilitário (expansão de query, condensação de follow-up, Vision
        # OCR) — a chamada de geração é o gargalo de qualidade mais isolável
        # para Q&A científico com números/tabelas; ver design.md de
        # restore-rag-answer-quality.
        self.llm_generation = ChatOpenAI(
            model=GENERATION_MODEL,
            temperature=0,
            openai_api_key=openai_api_key,
            http_client=_http_client,
            http_async_client=_http_async_client,
        )
        self.llm_utility = ChatOpenAI(
            model=UTILITY_MODEL,
            temperature=0,
            openai_api_key=openai_api_key,
            http_client=_http_client,
            http_async_client=_http_async_client,
        )
        # REFATORAÇÃO: Usar supabase_admin centralizado em vez de criar novo cliente
        self.supabase_admin = supabase_admin
        self.vectorstore = SupabaseVectorStore(
            client=self.supabase_admin,
            embedding=self.embeddings,
            table_name="documents"
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
            add_start_index=True,
        )
        self.similarity_threshold = PRIMARY_RPC_SIMILARITY_THRESHOLD
        logger.info(
            "[RAGService] embedding_model=%s embedding_dimensions=%s "
            "chunk_size=%s chunk_overlap=%s similarity_threshold=%.2f "
            "retrieval_k=%s retrieval_k_retry=%s refusal_floor_similarity=%.2f "
            "generation_model=%s utility_model=%s",
            EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, CHUNK_SIZE, CHUNK_OVERLAP,
            self.similarity_threshold,
            RETRIEVAL_K, RETRIEVAL_K_RETRY, REFUSAL_FLOOR_SIMILARITY,
            GENERATION_MODEL, UTILITY_MODEL,
        )
        self.graph = self._build_graph()

    # MÉTODO MODIFICADO: ingest_pdf com duplicação + validação (Etapa 1)
    async def ingest_pdf(self, file_path: str, original_filename: str) -> dict:
        """Ingestão de PDF com detecção de duplicação e validação de qualidade.

        Identidade por conteúdo (SHA-256 dos bytes do arquivo, não do nome),
        PDF original persistido no Storage, e limpeza automática se qualquer
        etapa de escrita falhar no meio — ver `harden-pdf-ingestion`.
        """
        storage_path: Optional[str] = None
        original_file_id: Optional[str] = None
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            # Hash do CONTEÚDO, não do nome — dois arquivos com nomes iguais
            # e conteúdos diferentes não colidem; o mesmo arquivo reenviado
            # com outro nome é reconhecido como já ingerido.
            original_file_id = hashlib.sha256(file_bytes).hexdigest()

            if self._check_file_exists(original_file_id):
                return {
                    "status": "already_exists",
                    "message": "Arquivo já foi ingestado",
                    "original_file_id": original_file_id,
                    "original_file_name": original_filename,
                }

            # Cascata de extração fora do event loop — pode envolver OCR
            # (Tesseract/Vision) demorando minutos; sem isso, uma ingestão
            # longa travaria outras requisições (ex.: chat) no mesmo processo.
            try:
                raw_docs, extraction_method, quality = await asyncio.to_thread(
                    self._load_pdf_with_fallback, file_path, original_filename
                )
            except ExtractionCostLimitExceeded as exc:
                return {
                    "status": "extraction_cost_limit",
                    "message": str(exc),
                    "original_file_id": original_file_id,
                    "original_file_name": original_filename,
                }

            # Extração inadequada é erro, não sucesso silencioso: nada é gravado.
            if not quality.adequate:
                logger.error(
                    "[ingest] '%s' rejeitado por qualidade de extração — %s",
                    original_filename, quality.reason,
                )
                return {
                    "status": "extraction_failed",
                    "message": (
                        f"A extração de texto deste PDF ficou incompleta e o documento "
                        f"não foi ingerido. Detalhe: {quality.reason}."
                    ),
                    "extraction_method": extraction_method,
                    "extraction_quality": quality.as_metadata(),
                    "original_file_id": original_file_id,
                    "original_file_name": original_filename,
                }

            # Validar qualidade do PDF antes de qualquer processamento
            if not self._validate_pdf_quality(raw_docs):
                return {
                    "status": "invalid_pdf",
                    "message": "PDF vazio ou corrompido",
                    "original_file_id": original_file_id,
                    "original_file_name": original_filename,
                }

            # Limpar páginas (remove ruído: números de página, copyright, linhas vazias)
            cleaned_docs = clean_loaded_pages(raw_docs)

            original_file_name = original_filename

            # Split contínuo ao longo do documento inteiro (não por página),
            # preservando a atribuição de página de cada chunk via mapa de
            # offsets — ver app.utils.chunking.split_pages_continuous.
            splits = split_pages_continuous(cleaned_docs, self.text_splitter)
            chunks_before_filter = len(splits)

            # Filtrar chunks de baixo valor
            splits = self._filter_chunks(splits)

            # A partir daqui começamos a escrever de verdade (Storage + banco).
            # Se qualquer etapa falhar, `_cleanup_failed_ingestion` desfaz o
            # que já tiver sido gravado, para não deixar lixo nem bloquear
            # uma nova tentativa como falso "already_exists".
            try:
                storage_path = await asyncio.to_thread(
                    self._upload_source_pdf, file_bytes, original_file_id, original_filename
                )
            except Exception as exc:
                logger.error(
                    "[ingest] falha ao enviar PDF original ao Storage: %s", exc, exc_info=True
                )
                return {
                    "status": "error",
                    "message": f"Falha ao salvar o PDF original: {exc}",
                    "original_file_id": original_file_id,
                    "original_file_name": original_filename,
                }

            # Adicionar metadados normalizados ANTES de salvar.
            # `extraction_method` é gravado para TODOS os caminhos (inclusive o
            # pypdf primário), junto das métricas que justificaram o aceite —
            # sem isso é impossível distinguir depois, olhando só a base, um
            # documento bem extraído de um mal extraído.
            # `chunk_index` é atribuído DEPOIS do filtro, para ficar sequencial
            # sem lacunas por arquivo.
            quality_metadata = quality.as_metadata()
            for idx, split in enumerate(splits):
                split.metadata['original_file_id'] = original_file_id
                split.metadata['original_file_name'] = original_file_name
                split.metadata['extraction_method'] = extraction_method
                split.metadata['extraction_quality'] = quality_metadata
                split.metadata['chunk_index'] = idx

            try:
                # `_persist_chunks` faz a chamada de embeddings (rede síncrona,
                # um lote por `add_documents`) + o backfill — fora do event
                # loop pelo mesmo motivo da extração: um documento com dezenas
                # de chunks não pode travar outras requisições (ex.: chat)
                # enquanto espera a OpenAI responder.
                await asyncio.to_thread(
                    self._persist_chunks, splits, original_file_id, original_file_name, storage_path
                )
            except Exception:
                self._cleanup_failed_ingestion(original_file_id, storage_path)
                raise

            return {
                "status": "success",
                "message": "PDF ingerido com sucesso",
                "chunks": len(splits),
                "chunks_before_filter": chunks_before_filter,
                "chunks_filtered_out": chunks_before_filter - len(splits),
                "pages_loaded": len(raw_docs),
                "extraction_method": extraction_method,
                "extraction_quality": quality_metadata,
                "file_path": file_path,
                "original_file_id": original_file_id,
                "original_file_name": original_file_name,
                "storage_bucket": RAG_SOURCE_PDFS_BUCKET,
                "storage_path": storage_path,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "file_path": file_path,
            }

    def _persist_chunks(
        self,
        splits: List[Document],
        original_file_id: str,
        original_file_name: str,
        storage_path: Optional[str],
    ) -> None:
        """Grava os chunks no vectorstore (embeddings + JSONB) e faz o
        backfill das colunas top-level. Chamado via `asyncio.to_thread` —
        `add_documents` bate na API de embeddings da OpenAI de forma síncrona."""
        row_ids = self.vectorstore.add_documents(splits)
        # Popular também as colunas top-level que vector_admin_repository
        # já espera ler (page, chunk_index, original_file_id,
        # original_file_name, storage_bucket, storage_path) — o
        # SupabaseVectorStore do LangChain só escreve JSONB, então
        # isso exige um passo próprio.
        self._backfill_top_level_columns(
            row_ids, splits, original_file_id, original_file_name, storage_path
        )

    def _upload_source_pdf(self, file_bytes: bytes, original_file_id: str, original_filename: str) -> str:
        """Envia o PDF original ao Storage. Nome do objeto é o hash de
        conteúdo (não o nome original) — evita problemas com espaços/acentos
        no nome do arquivo e garante unicidade real."""
        ext = os.path.splitext(original_filename)[1] or ".pdf"
        storage_path = f"{original_file_id}{ext}"
        self.supabase_admin.storage.from_(RAG_SOURCE_PDFS_BUCKET).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf"},
        )
        return storage_path

    def _cleanup_failed_ingestion(self, original_file_id: str, storage_path: Optional[str]) -> None:
        """Remove qualquer rastro de uma ingestão que falhou no meio — chunks
        já inseridos e o PDF já enviado ao Storage — para que uma nova
        tentativa não fique bloqueada como `already_exists` nem deixe linhas
        órfãs na base."""
        try:
            resp = (
                self.supabase_admin.table("documents")
                .select("id")
                .filter("metadata->>original_file_id", "eq", original_file_id)
                .execute()
            )
            ids = [row["id"] for row in (resp.data or [])]
            if ids:
                self.supabase_admin.table("documents").delete().in_("id", ids).execute()
                logger.warning(
                    "[ingest] limpeza pós-falha: %d chunks removidos (original_file_id=%s)",
                    len(ids), original_file_id,
                )
        except Exception as exc:
            logger.error("[ingest] falha ao limpar chunks após erro: %s", exc, exc_info=True)

        if storage_path:
            try:
                self.supabase_admin.storage.from_(RAG_SOURCE_PDFS_BUCKET).remove([storage_path])
                logger.warning("[ingest] limpeza pós-falha: PDF removido do Storage (%s)", storage_path)
            except Exception as exc:
                logger.error("[ingest] falha ao limpar PDF do Storage: %s", exc, exc_info=True)

    # NOVO MÉTODO: Verificação de duplicação
    def _check_file_exists(self, original_file_id: str) -> bool:
        """Verifica se original_file_id já existe em public.documents.

        Usa filtro JSONB (metadata->>original_file_id) porque a coluna
        original_file_id não é populada pelo SupabaseVectorStore do LangChain.
        O operador ->> extrai o valor como texto e faz comparação simples (eq),
        mais confiável que .contains() para JSONB no supabase-py.
        """
        try:
            response = (
                self.supabase_admin.table("documents")
                .select("id")
                .filter("metadata->>original_file_id", "eq", original_file_id)
                .limit(1)
                .execute()
            )
            found = len(response.data) > 0
            logger.info(
                "[_check_file_exists] original_file_id=%s → found=%s",
                original_file_id, found,
            )
            return found
        except Exception as e:
            logger.error(
                "[_check_file_exists] ERRO ao verificar duplicata: %s",
                e, exc_info=True,
            )
            return False

    def _backfill_top_level_columns(
        self,
        row_ids: List[str],
        splits: List[Document],
        original_file_id: str,
        original_file_name: str,
        storage_path: Optional[str] = None,
    ) -> None:
        """Popula page/chunk_index/original_file_id/original_file_name/
        storage_bucket/storage_path como colunas reais, além do JSONB que o
        SupabaseVectorStore já grava.

        `add_documents` retorna os IDs inseridos na mesma ordem da lista de
        entrada (upsert de lote único, RETURNING preserva ordem — mas não é
        contrato formal da API). Se o tamanho não bater, pula o backfill em
        vez de arriscar gravar page/chunk_index no chunk errado; o JSONB
        continua correto de qualquer forma, então nada se perde.
        """
        if len(row_ids) != len(splits):
            logger.error(
                "[ingest] add_documents retornou %d ids para %d splits — "
                "pulando backfill de colunas top-level (JSONB continua correto)",
                len(row_ids), len(splits),
            )
            return
        update_rows = [
            {
                "id": row_id,
                "page": split.metadata.get("page"),
                "chunk_index": split.metadata.get("chunk_index"),
                "original_file_id": original_file_id,
                "original_file_name": original_file_name,
                "storage_bucket": RAG_SOURCE_PDFS_BUCKET if storage_path else None,
                "storage_path": storage_path,
            }
            for row_id, split in zip(row_ids, splits)
        ]
        try:
            self.supabase_admin.table("documents").upsert(update_rows, on_conflict="id").execute()
        except Exception as exc:
            logger.error(
                "[ingest] falha ao popular colunas top-level: %s — JSONB continua correto",
                exc, exc_info=True,
            )

    def _accept_extraction(self, docs: List[Document], method: str) -> Optional[ExtractionQuality]:
        """Decide se a extração de um estágio é aceitável.

        Combina os dois critérios: encoding quebrado (`_is_text_garbled`, que
        cobre mojibake) e extração incompleta (`assess_extraction`, que cobre
        estrutura sem conteúdo). Retorna a qualidade se aceitável, senão None.
        """
        if not docs:
            return None
        combined = " ".join(d.page_content for d in docs)
        if self._is_text_garbled(combined):
            logger.warning("[ingest] %s: texto com encoding quebrado", method)
            return None
        quality = assess_extraction([d.page_content for d in docs])
        if not quality.adequate:
            logger.warning("[ingest] %s: extração incompleta — %s", method, quality.reason)
            return None
        return quality

    def _load_pdf_with_fallback(
        self, file_path: str, original_filename: str
    ) -> Tuple[List[Document], str, ExtractionQuality]:
        """Carrega PDF com cadeia de fallbacks progressivos:
        1. PyPDFLoader  (rápido, sem custo)
        2. pdfplumber   (melhor para alguns encodings e layouts)
        3. Tesseract OCR
        4. Vision OCR   (GPT-4o-mini + PyMuPDF — último recurso, com custo por página)

        Cada estágio é aceito apenas se a extração for adequada — não basta ter
        texto, é preciso ter conteúdo. Retorna (documentos, método, qualidade).
        Quando nenhum estágio produz qualidade adequada, devolve a melhor
        tentativa com `quality.adequate == False`, para o chamador falhar
        explicitamente em vez de gravar conteúdo inútil.
        """
        # ── 1. PyPDFLoader ────────────────────────────────────────────────────
        loader = PyPDFLoader(file_path)
        raw_docs = loader.load()
        for doc in raw_docs:
            doc.metadata['source'] = original_filename

        quality = self._accept_extraction(raw_docs, "pypdf")
        if quality:
            logger.info("[ingest] pypdf OK — %.0f palavras/página", quality.mean_words_per_page)
            return raw_docs, "pypdf", quality

        # ── 2. pdfplumber ─────────────────────────────────────────────────────
        if _PDFPLUMBER_AVAILABLE:
            try:
                import pdfplumber
                plumber_docs: List[Document] = []
                with pdfplumber.open(file_path) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        text = page.extract_text() or ""
                        plumber_docs.append(Document(
                            page_content=text,
                            metadata={"source": original_filename, "page": page_num},
                        ))
                quality = self._accept_extraction(plumber_docs, "pdfplumber")
                if quality:
                    logger.info("[ingest] pdfplumber OK — %.0f palavras/página",
                                quality.mean_words_per_page)
                    return plumber_docs, "pdfplumber", quality
            except Exception as exc:
                logger.warning("[ingest] pdfplumber falhou (%s)", exc)

        # ── 3. Tesseract OCR via PyMuPDF + pytesseract ───────────────────────
        if _PYMUPDF_AVAILABLE and _PYTESSERACT_AVAILABLE:
            try:
                tesseract_docs = self._extract_text_via_tesseract(file_path, original_filename)
                quality = self._accept_extraction(tesseract_docs, "tesseract_ocr")
                if quality:
                    logger.info("[ingest] Tesseract OCR OK — %.0f palavras/página",
                                quality.mean_words_per_page)
                    return tesseract_docs, "tesseract_ocr", quality
            except Exception as exc:
                logger.warning("[ingest] Tesseract OCR falhou (%s)", exc)
        else:
            # Sem Tesseract a cascata pula direto para o Vision, que custa por
            # página — vale deixar registrado por que o custo subiu.
            logger.warning(
                "[ingest] Tesseract indisponível (pymupdf=%s, pytesseract=%s) — "
                "cascata seguirá para Vision OCR, que tem custo por página",
                _PYMUPDF_AVAILABLE, _PYTESSERACT_AVAILABLE,
            )

        # ── 4. Vision OCR via GPT-4o-mini + PyMuPDF (último recurso) ─────────
        if _PYMUPDF_AVAILABLE:
            try:
                vision_docs = self._extract_text_via_vision(file_path, original_filename)
                quality = self._accept_extraction(vision_docs, "vision_ocr")
                if quality:
                    logger.info("[ingest] Vision OCR OK — %.0f palavras/página",
                                quality.mean_words_per_page)
                    return vision_docs, "vision_ocr", quality
            except ExtractionCostLimitExceeded:
                raise
            except Exception as exc:
                logger.error("[ingest] Vision OCR falhou (%s)", exc)

        # Nenhum estágio produziu qualidade adequada. Devolve a primeira
        # tentativa com o veredito negativo — o chamador deve falhar, não gravar.
        final_quality = assess_extraction([d.page_content for d in raw_docs])
        logger.error("[ingest] cascata esgotada sem qualidade adequada — %s", final_quality.reason)
        return raw_docs, "pypdf", final_quality

    def _extract_text_via_tesseract(self, file_path: str, original_filename: str) -> List[Document]:
        """Extrai texto via Tesseract OCR (PyMuPDF renderiza → PIL → pytesseract).

        Requer Tesseract instalado no sistema.
        Usa idiomas 'por+eng' (português + inglês) para cobrir artigos bilíngues.
        """
        import io
        import fitz as pymupdf
        import pytesseract
        from PIL import Image

        # Configurar path do Tesseract se não estiver no PATH
        if not pytesseract.pytesseract.tesseract_cmd or pytesseract.pytesseract.tesseract_cmd == "tesseract":
            for path in _TESSERACT_PATHS:
                import os
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    logger.info("[tesseract] Encontrado em: %s", path)
                    break

        docs: List[Document] = []
        pdf = pymupdf.open(file_path)
        total = len(pdf)
        logger.info("[tesseract] iniciando OCR de %d páginas: %s", total, original_filename)

        for page_num, page in enumerate(pdf):
            mat = pymupdf.Matrix(2.5, 2.5)  # ~180 DPI — bom para OCR
            pix = page.get_pixmap(matrix=mat, colorspace=pymupdf.csRGB)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            try:
                text = pytesseract.image_to_string(img, lang="por+eng")
                if text.strip():
                    docs.append(Document(
                        page_content=text,
                        metadata={
                            "source": original_filename,
                            "page": page_num,
                            "extraction_method": "tesseract_ocr",
                        },
                    ))
                    logger.info("[tesseract] página %d/%d: %d chars", page_num + 1, total, len(text))
            except Exception as exc:
                logger.warning("[tesseract] página %d falhou: %s", page_num, exc)

        pdf.close()
        return docs

    def _extract_text_via_vision(self, file_path: str, original_filename: str) -> List[Document]:
        """Extrai texto de PDF via GPT Vision (PyMuPDF renderiza páginas → base64 → OpenAI).

        Funciona mesmo em PDFs com fontes customizadas onde todo extrator de texto falha.
        Custo: ~$0.002–0.01 por página (gpt-4o-mini com detail=high).
        """
        import base64
        import fitz as pymupdf

        prompt_text = (
            "You are a scientific document transcription tool. "
            "Extract ALL text from this page EXACTLY as it appears. "
            "Include: all numbers, table values, column headers, row labels, "
            "statistical notation (±, p-values, %, n=, confidence intervals), "
            "and all body paragraphs. "
            "For tables: preserve structure using | to separate columns, one row per line. "
            "Example table row: 'T1 (100%) | 45.2 ± 3.1 | 312.5 | 1.82 | 98.3'. "
            "Do NOT summarize, skip values, or add commentary. "
            "Transcribe every character you see."
        )

        docs: List[Document] = []
        pdf = pymupdf.open(file_path)
        total_pages = len(pdf)

        # Teto de custo: cada página é uma chamada de API paga. Ultrapassar o
        # limite falha explicitamente — processar só as N primeiras entregaria
        # um documento parcial rotulado como completo.
        if total_pages > OCR_MAX_PAGES:
            pdf.close()
            raise ExtractionCostLimitExceeded(
                f"O documento tem {total_pages} páginas e exigiria OCR por página, "
                f"acima do limite configurado de {OCR_MAX_PAGES} (OCR_MAX_PAGES). "
                f"Nenhuma página foi processada."
            )

        logger.info("[vision_ocr] iniciando OCR de %d páginas: %s", total_pages, original_filename)

        for page_num, page in enumerate(pdf):
            # Renderizar em ~150 DPI (fator 2.08) — equilibra qualidade e tamanho
            mat = pymupdf.Matrix(2.08, 2.08)
            pix = page.get_pixmap(matrix=mat, colorspace=pymupdf.csRGB)
            img_b64 = base64.b64encode(pix.tobytes("png")).decode()

            try:
                message = HumanMessage(content=[
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_b64}",
                            "detail": "high",
                        },
                    },
                    {"type": "text", "text": prompt_text},
                ])
                # Timeout por página: sem ele, uma chamada travada bloqueia a
                # ingestão inteira indefinidamente.
                resp = self.llm_utility.invoke([message], timeout=OCR_PAGE_TIMEOUT_SECONDS)
                extracted = resp.content.strip()
                if extracted:
                    docs.append(Document(
                        page_content=extracted,
                        metadata={
                            "source": original_filename,
                            "page": page_num,
                            "extraction_method": "vision_ocr",
                        },
                    ))
                logger.info("[vision_ocr] página %d/%d: %d chars", page_num + 1, total_pages, len(extracted))
            except Exception as exc:
                logger.warning("[vision_ocr] página %d falhou: %s", page_num, exc)

        pdf.close()
        return docs

    def _validate_pdf_quality(self, docs: List[Document]) -> bool:
        """Valida se o PDF extraído tem conteúdo utilizável.

        O critério de densidade fica em `assess_extraction`, aplicado durante a
        cascata em `_load_pdf_with_fallback` — aqui resta apenas a checagem
        estrutural de que existe documento e texto. Manter as duas separadas
        evita avaliar a mesma coisa duas vezes com limiares divergentes.
        """
        if not docs:
            return False
        total_chars = sum(len(doc.page_content) for doc in docs)
        return total_chars > 50

    def _filter_chunks(self, docs: List[Document]) -> List[Document]:
        """Remove chunks muito curtos ou sem valor científico."""
        filtered = []
        for doc in docs:
            content = doc.page_content.strip()
            if not content or len(content) < 120:
                continue
            if is_editorial_or_low_value(content) and not contains_scientific_signal(content):
                continue
            filtered.append(doc)
        return filtered

    def get_answer(self, question: str, history: Optional[List[List[str]]] = None) -> AnswerResult:
        """Ponto de entrada: invoca grafo com pergunta, histórico e tipo detectado.

        Devolve a resposta e as fontes reais (arquivo + páginas) que a
        embasaram — vazias em caso de recusa, nunca inventadas.
        """
        lang = self._detect_question_language(question)
        question_type = self._detect_question_type(question)
        logger.info("[get_answer] lang=%s question_type=%s pergunta='%s...'",
                    lang, question_type, question[:60])
        input_state = {
            "question": question,
            "context": "",
            "answer": "",
            "evaluation": "",
            "language": lang,
            "history": history or [],
            "question_type": question_type,
            "insufficient_context": False,
            "source_docs": [],
            "context_confidence": "strong",
            "effective_type": question_type,
            "unsupported_numbers": [],
            "numeric_regen_count": 0,
            "context_sufficiency": "",
            "retrieval_query": "",
            "reformulation_count": 0,
        }
        t0 = time.perf_counter()
        result = self.graph.invoke(input_state)
        elapsed = time.perf_counter() - t0

        logger.info(
            "[metrics] type=%-14s lang=%-5s reformulations=%d sufficiency=%-12s answer_len=%4d eval=%-12s time=%.2fs",
            question_type,
            lang,
            result.get("reformulation_count", 0),
            result.get("context_sufficiency", "?"),
            len(result.get("answer", "")),
            result.get("evaluation", "?"),
            elapsed,
        )
        sources = self._build_sources(result.get("source_docs", []))
        debug = {"context": result.get("context", "")}
        return AnswerResult(answer=result["answer"], sources=sources, debug=debug)

    def _build_sources(self, source_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Agrupa os chunks usados na resposta por arquivo de origem, com a
        lista de páginas DISCRETAS realmente presentes nos chunks do
        contexto final — não mais um span min/max sobre tudo que foi
        recuperado (produzia citações como "página 0 a 15" para uma
        resposta que na verdade usou 2 chunks específicos, uma vez que a
        seleção incluía companions e/ou dezenas de candidatos da zona
        fraca). Chunks sem `original_file_name` são ignorados — melhor
        omitir uma fonte do que mostrar uma entrada vazia ou enganosa.

        Chunks de companion (`doc["companion"]`) NÃO introduzem um arquivo
        novo sozinhos: um chunk trazido só por densidade de dígitos nunca
        justificou, sozinho, citar um documento que a busca semântica não
        recuperou — só contam se o arquivo já foi citado por um chunk de
        ranking genuíno.

        Arquivos ordenados pela primeira aparição em `source_docs` (que
        preserva a ordem de rank — companions são sempre appendados no
        final da lista de docs, então nunca vêm antes do chunk genuíno que
        os torna elegíveis), limitado a `CITATION_MAX_FILES`.
        """
        pages_by_file: Dict[str, set] = {}
        order: List[str] = []
        has_genuine_chunk: Dict[str, bool] = {}

        for doc in source_docs:
            file_name = doc.get("original_file_name")
            if not file_name:
                continue
            if file_name not in pages_by_file:
                pages_by_file[file_name] = set()
                order.append(file_name)
                has_genuine_chunk[file_name] = False
            if not doc.get("companion", False):
                has_genuine_chunk[file_name] = True

            page_start = doc.get("page_start")
            page_end = doc.get("page_end")
            if page_start is not None and page_end is not None:
                pages_by_file[file_name].update(range(page_start, page_end + 1))
            elif page_start is not None:
                pages_by_file[file_name].add(page_start)

        results = [
            {"file": file_name, "pages": sorted(pages_by_file[file_name])}
            for file_name in order
            if has_genuine_chunk[file_name]
        ]
        return results[:CITATION_MAX_FILES]

    def _extract_source_doc_info(self, docs: List[Document]) -> List[Dict[str, Any]]:
        """Extrai de cada chunk recuperado só o necessário para citação
        (arquivo + páginas + se é companion), leve o bastante para viver no
        estado do grafo sem carregar os `Document`s inteiros até o retorno final."""
        return [
            {
                "original_file_name": d.metadata.get("original_file_name"),
                "page_start": d.metadata.get("page_start", d.metadata.get("page")),
                "page_end": d.metadata.get("page_end", d.metadata.get("page")),
                "companion": bool(d.metadata.get("companion", False)),
            }
            for d in docs
        ]

    def _build_graph(self) -> Any:
        """Grafo com retrieve -> generate -> evaluate -> (conditional retry ou END)."""
        workflow = StateGraph(State)

        def retrieve(state: State) -> Dict[str, Any]:
            """Nó: recupera docs e monta context.

            Para perguntas conceptuais, adiciona data companions (chunks mais
            ricos em dados do mesmo arquivo) para garantir que tabelas e métricas
            específicas estejam presentes no contexto mesmo sem alta similaridade semântica.

            Perguntas de follow-up são condensadas com o histórico antes da busca —
            embutir só "E qual a margem por unidade?" sozinho não recupera nada
            relevante; precisa do turno anterior para virar uma busca autocontida.
            """
            retrieval_query = self._condense_followup_question(
                state["question"], state.get("history", []), state["language"]
            )
            trace: Dict[str, Any] = {}
            docs = self._retrieve_docs_via_rpc(retrieval_query, k=RETRIEVAL_K, trace_out=trace)
            # Confiança derivada da similaridade ANTES de companions/preenchimento
            # mínimo — o que importa é se o match semântico original foi forte,
            # não se a seleção foi completada por outro mecanismo.
            top_similarity = trace.get("top_similarity_raw", 0.0)
            context_confidence = "strong" if top_similarity >= self.similarity_threshold else "partial"
            question_type = state.get("question_type", "conceptual")
            if question_type in ("conceptual", "quantitative"):
                docs = self._add_data_companion_chunks(docs)
            if not docs:
                logger.warning(
                    "[retrieve] nenhum chunk atingiu o piso de recusa — sem contexto"
                )
                return {
                    "context": "", "insufficient_context": True, "source_docs": [],
                    "context_confidence": context_confidence, "retrieval_query": retrieval_query,
                }
            context = "\n\n".join(doc.page_content for doc in docs)
            return {
                "context": context,
                "insufficient_context": False,
                "source_docs": self._extract_source_doc_info(docs),
                "context_confidence": context_confidence,
                "retrieval_query": retrieval_query,
            }

        def grade_context(state: State) -> Dict[str, Any]:
            """Nó (MODO OBSERVAÇÃO — grupo 2 de `add-rag-self-correction-loop`):
            julga se o contexto recuperado é suficiente para responder à
            pergunta, ANTES de gastar uma chamada de geração nele.

            Ainda não altera o fluxo do grafo — o resultado é só logado e
            gravado no State para calibração contra o golden set adversarial
            (task 3). A reformulação condicionada a `insufficient`
            (substituindo `retrieve_retry`) é a task 4.

            Usa `retrieval_query` (condensada com histórico por `retrieve`),
            não `state["question"]` cru — bug encontrado na calibração
            inicial: as 4 perguntas de follow-up do golden set (ex.: "E qual
            teve o menor?") eram julgadas `insufficient` mesmo com o contexto
            correto, porque a pergunta crua é ininteligível sem o turno
            anterior. `generate` não tem esse problema porque recebe o
            histórico completo como mensagens; `grade_context` não carrega
            histórico (mais barato), então precisa da versão já
            autocontida.
            """
            if state.get("insufficient_context"):
                # Já não há contexto algum (piso de recusa por similaridade) —
                # nada para julgar semanticamente, e `generate` já vai recusar.
                return {"context_sufficiency": "insufficient"}

            question_for_grading = state.get("retrieval_query") or state["question"]
            sufficiency = self._grade_context_verdict(question_for_grading, state["context"])
            logger.info(
                "[grade_context] sufficiency=%s (modo observação, não altera o fluxo)",
                sufficiency,
            )
            return {"context_sufficiency": sufficiency}

        def generate(state: State) -> Dict[str, Any]:
            """Nó: gera resposta em prosa contínua, com ênfase adaptada ao
            tipo de pergunta e ressalva explícita quando a confiança da
            recuperação é parcial.

            Quando não há contexto suficiente (recusa), devolve a mensagem de
            recusa direto, sem chamar o LLM — economiza custo e elimina a
            chance de o modelo "resgatar" um contexto ruim com confiança. Se
            o contexto existe mas o modelo mesmo assim conclui que não pode
            responder, ele sinaliza isso com `NO_ANSWER_SENTINEL`, detectado
            abaixo e convertido na mesma mensagem de recusa.
            """
            lang = state["language"]
            if state.get("insufficient_context"):
                logger.info("[generate] contexto insuficiente — recusando sem chamar o LLM")
                return {
                    "answer": self._build_refusal_message(lang),
                    "evaluation": "REFUSED",
                    "source_docs": [],
                }

            history = state.get("history", [])
            question_type = state.get("question_type", "conceptual")

            # Se o tipo é quantitativo mas o contexto é pobre/garbled,
            # usa ênfase conceptual para evitar resposta toda vazia.
            effective_type = question_type
            if question_type == "quantitative" and self._is_context_poor(state.get("context", "")):
                effective_type = "conceptual"
                logger.info("[generate] contexto pobre — degradando quantitative→conceptual")

            answer = self._generate_answer_text(
                question=state["question"],
                context=state["context"],
                language=lang,
                effective_type=effective_type,
                context_confidence=state.get("context_confidence", "strong"),
                history=history,
            )

            # Substring, não igualdade exata: apesar da instrução pedir
            # "exatamente X e nada mais", o modelo às vezes escreve uma
            # explicação primeiro e só então acrescenta o sentinela no
            # final — observado ao vivo (`oos-dieta-restritiva`: resposta
            # em prosa explicando a ausência de dados, sentinela ao fim).
            # Igualdade exata deixava esse caso passar como resposta válida,
            # citando fontes que não sustentavam nada — exatamente o
            # sintoma que esta change existe para eliminar.
            if self.NO_ANSWER_SENTINEL in answer:
                logger.info(
                    "[generate] modelo sinalizou que não pode responder com o contexto disponível"
                )
                return {
                    "answer": self._build_refusal_message(lang),
                    "evaluation": "REFUSED",
                    "source_docs": [],
                }

            return {"answer": answer, "effective_type": effective_type}

        def verify_numeric(state: State) -> Dict[str, Any]:
            """Nó: confere que todo número citado na resposta aparece no
            contexto — sinal determinístico e de custo zero (regex, sem
            LLM) contra o pior modo de falha num corpus inteiro
            quantitativo: um valor inventado com aparência de dado real.

            Roda depois de `generate`, antes de `evaluate`. Recusa não tem
            números para verificar. No máximo 1 regeneração, com instrução
            de correção citando os valores específicos não suportados —
            uma segunda falha é aceita sem 3ª tentativa (pode ser
            aritmética legitimamente derivada do contexto, não uma
            invenção — ver risco aceito em design.md).
            """
            if state.get("evaluation") == "REFUSED":
                return {"unsupported_numbers": []}

            context = state.get("context", "")
            unsupported = find_unsupported_numbers(state["answer"], context)

            if not unsupported:
                return {"unsupported_numbers": []}

            if state.get("numeric_regen_count", 0) >= 1:
                logger.warning(
                    "[verify_numeric] resposta regenerada ainda cita números fora do "
                    "contexto: %s — aceitando (sem 3ª tentativa)",
                    unsupported,
                )
                return {"unsupported_numbers": unsupported}

            logger.info(
                "[verify_numeric] números fora do contexto: %s — regenerando com correção",
                unsupported,
            )
            lang = state["language"]
            correction_instruction = (
                "CORRECTION REQUIRED: your previous answer cited the following numeric "
                "value(s), which do NOT appear anywhere in the provided context: "
                f"{', '.join(unsupported)}. Remove or correct each of them — state only "
                "numbers that are explicitly present in the context above."
            )
            regenerated = self._generate_answer_text(
                question=state["question"],
                context=context,
                language=lang,
                effective_type=state.get("effective_type", state.get("question_type", "conceptual")),
                context_confidence=state.get("context_confidence", "strong"),
                history=state.get("history", []),
                correction_instruction=correction_instruction,
            )
            next_regen_count = state.get("numeric_regen_count", 0) + 1

            if self.NO_ANSWER_SENTINEL in regenerated:
                logger.info("[verify_numeric] regeneração resultou em sentinela — recusando")
                return {
                    "answer": self._build_refusal_message(lang),
                    "evaluation": "REFUSED",
                    "source_docs": [],
                    "unsupported_numbers": [],
                    "numeric_regen_count": next_regen_count,
                }

            still_unsupported = find_unsupported_numbers(regenerated, context)
            return {
                "answer": regenerated,
                "unsupported_numbers": still_unsupported,
                "numeric_regen_count": next_regen_count,
            }

        def evaluate(state: State) -> Dict[str, str]:
            """Nó: avalia qualidade da resposta — não vazia, relevante à
            pergunta, e não um esqueleto de "sem dados" disfarçado de
            resposta.

            Não depende mais de cabeçalho de seção por tipo de pergunta —
            o formato de resposta é prosa contínua (ver
            `_build_system_prompt`), então checagens como `"COMPARISON:" in
            answer` não têm mais objeto e reprovariam toda resposta válida.
            Essa remoção elimina de quebra o descasamento entre
            `question_type` e o tipo efetivamente usado na geração
            (`effective_type`, quando `generate` degrada quantitative→
            conceptual por contexto pobre): antes o `evaluate` continuava
            cobrando cabeçalhos do tipo original mesmo quando `generate`
            usava outro, gerando 2 retries garantidamente inúteis.
            """
            # Recusa já foi decidida em `generate` — não reavaliar como se fosse
            # uma resposta normal (uma recusa é curta de propósito).
            if state.get("evaluation") == "REFUSED":
                return {"evaluation": "REFUSED"}

            answer = state["answer"]
            question = state["question"]

            is_empty = not answer.strip()
            is_relevant = self._is_answer_relevant(question, answer)
            is_skeleton = looks_like_empty_skeleton(answer)

            if is_empty or not is_relevant or is_skeleton:
                reason = (
                    "resposta vazia" if is_empty
                    else "sem relevância" if not is_relevant
                    else "esqueleto sem conteúdo real"
                )
                logger.info("[evaluate] LOW_QUALITY (%s) len=%d", reason, len(answer))
                return {"evaluation": "LOW_QUALITY"}

            logger.info("[evaluate] HIGH_QUALITY len=%d", len(answer))
            return {"evaluation": "HIGH_QUALITY"}

        def route_after_grade_context(state: State) -> Literal["reformulate", "generate", "give_up"]:
            """Condicional: só `insufficient` desvia do caminho direto para
            `generate` — `sufficient`/`partial` vão direto (`partial` já
            carrega a ressalva via `context_confidence`, tratada em
            `generate`). No máximo 1 reformulação: uma 2ª tentativa também
            `insufficient` desiste, não tenta uma 3ª vez (design.md, decisão
            3 — dados do programa mostram que mais tentativas não melhoram
            o resultado)."""
            if state["context_sufficiency"] != "insufficient":
                return "generate"
            if state.get("reformulation_count", 0) < 1:
                return "reformulate"
            return "give_up"

        def reformulate_and_retrieve(state: State) -> Dict[str, Any]:
            """Nó: substitui `retrieve_retry`. Reformula `retrieval_query`
            (condensada, não a pergunta crua — task 4.3) via
            `_expand_query_for_retry` e recupera de novo, passando pelo
            MESMO `_select_context_docs`/piso de recusa da tentativa
            original (`_retrieve_docs_via_rpc` não tem mais nenhum
            parâmetro de bypass desde a task 4.1) — nunca resgata com
            contexto abaixo do piso que a tentativa original já teria
            recusado. Volta para `grade_context` (loop), que julga de novo
            com o novo contexto; `route_after_grade_context` usa
            `reformulation_count` para nunca reformular uma 2ª vez.
            """
            reformulated = self._expand_query_for_retry(state["retrieval_query"])
            trace: Dict[str, Any] = {}
            docs = self._retrieve_docs_via_rpc(
                reformulated, k=RETRIEVAL_K_RETRY, use_llm_expansion=False, trace_out=trace
            )
            top_similarity = trace.get("top_similarity_raw", 0.0)
            context_confidence = "strong" if top_similarity >= self.similarity_threshold else "partial"
            question_type = state.get("question_type", "conceptual")
            if question_type in ("conceptual", "quantitative"):
                docs = self._add_data_companion_chunks(docs)

            reformulation_count = state.get("reformulation_count", 0) + 1
            logger.info(
                "[reformulate_and_retrieve] tentativa=%d query=%r ndocs=%d",
                reformulation_count, reformulated, len(docs),
            )
            if not docs:
                return {
                    "context": "", "insufficient_context": True, "source_docs": [],
                    "context_confidence": context_confidence,
                    "retrieval_query": reformulated, "reformulation_count": reformulation_count,
                }
            context = "\n\n".join(doc.page_content for doc in docs)
            return {
                "context": context,
                "insufficient_context": False,
                "source_docs": self._extract_source_doc_info(docs),
                "context_confidence": context_confidence,
                "retrieval_query": reformulated,
                "reformulation_count": reformulation_count,
            }

        def refuse_insufficient_context(state: State) -> Dict[str, Any]:
            """Nó: a tentativa reformulada também foi `insufficient` —
            recusa, sem 3ª tentativa (task 4.5). Reaproveita o caminho de
            recusa gratuito que `generate` já tem via `insufficient_context`
            (nunca chama o LLM de geração para um contexto que o próprio
            sistema já julgou insuficiente duas vezes)."""
            return {"insufficient_context": True, "context": "", "source_docs": []}

        workflow.add_node("retrieve", retrieve)
        workflow.add_node("grade_context", grade_context)
        workflow.add_node("reformulate_and_retrieve", reformulate_and_retrieve)
        workflow.add_node("refuse_insufficient_context", refuse_insufficient_context)
        workflow.add_node("generate", generate)
        workflow.add_node("verify_numeric", verify_numeric)
        workflow.add_node("evaluate", evaluate)
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "grade_context")
        workflow.add_conditional_edges(
            "grade_context",
            route_after_grade_context,
            {
                "reformulate": "reformulate_and_retrieve",
                "generate": "generate",
                "give_up": "refuse_insufficient_context",
            },
        )
        workflow.add_edge("reformulate_and_retrieve", "grade_context")
        workflow.add_edge("refuse_insufficient_context", "generate")
        workflow.add_edge("generate", "verify_numeric")
        workflow.add_edge("verify_numeric", "evaluate")
        workflow.add_edge("evaluate", END)
        return workflow.compile()

    def _grade_context_verdict(self, question: str, context: str) -> str:
        """Chama `llm_utility` com `_GRADE_CONTEXT_SYSTEM_PROMPT` e devolve
        um veredito normalizado (`sufficient`/`partial`/`insufficient`).

        Método próprio (não só um closure dentro de `_build_graph`) para ser
        reaproveitado tanto pelo nó `grade_context` quanto pelo script de
        calibração contra o golden set adversarial (task 2.3/3.x) — as duas
        chamadas precisam do mesmo parsing, para a calibração nunca medir um
        comportamento diferente do que roda em produção.
        """
        messages = [
            SystemMessage(content=self._GRADE_CONTEXT_SYSTEM_PROMPT),
            HumanMessage(content=f"**QUESTION:**\n{question}\n\n**CONTEXT:**\n{context}"),
        ]
        response = self.llm_utility.invoke(messages)
        raw = response.content.strip().upper()
        if "INSUFFICIENT" in raw:
            return "insufficient"
        if "PARTIAL" in raw:
            return "partial"
        if "SUFFICIENT" in raw:
            return "sufficient"
        # Resposta fora do formato esperado — mesma postura conservadora do
        # resto do pipeline: não assume sufficient sem sinal claro.
        logger.warning("[grade_context] resposta fora do formato esperado: %r", raw)
        return "partial"

    def _generate_answer_text(
        self,
        *,
        question: str,
        context: str,
        language: str,
        effective_type: str,
        context_confidence: str,
        history: List[List[str]],
        correction_instruction: Optional[str] = None,
    ) -> str:
        """Monta o prompt e chama `llm_generation`, devolvendo o texto bruto
        da resposta (sentinela de recusa ainda não tratado pelo chamador).

        Compartilhado entre o nó `generate` e a regeneração de
        `verify_numeric` — as duas chamadas precisam montar exatamente a
        mesma mensagem (system prompt + ressalva de confiança parcial +
        histórico + contexto/pergunta), diferindo só pela instrução de
        correção opcional, para nunca divergirem silenciosamente.
        """
        lang_instruction = (
            "Responda COMPLETAMENTE em português (pt-BR)."
            if language == "pt-BR"
            else "Respond COMPLETELY in English."
        )
        system_content = self._build_system_prompt(effective_type, lang_instruction)

        # Confiança parcial: instrui o modelo a abrir sinalizando a
        # incerteza em linguagem natural, em vez de responder com a mesma
        # certeza de um contexto fortemente relacionado — implementa a
        # postura escolhida (ressalva, não recusa, na zona de incerteza).
        if context_confidence == "partial":
            system_content += (
                "\n\nThe retrieved context has only partial/moderate relevance to this "
                "question. Open your answer by briefly signaling that uncertainty in "
                "natural language (e.g. \"the available documents do not directly address "
                "this, but the closest related information indicates...\"), and clearly "
                "mark any part of the answer that is inference from related material "
                "rather than a direct match."
            )

        if correction_instruction:
            system_content += f"\n\n{correction_instruction}"

        messages = [SystemMessage(content=system_content)]

        for pair in history:
            if len(pair) >= 1 and pair[0]:
                messages.append(HumanMessage(content=pair[0]))
            if len(pair) >= 2 and pair[1]:
                messages.append(AIMessage(content=pair[1]))

        current_message = f"**CONTEXT:**\n{context}\n\n**QUESTION:** {question}"
        messages.append(HumanMessage(content=current_message))

        response = self.llm_generation.invoke(messages)
        return response.content.strip()

    def _embed_query(self, text: str) -> List[float]:
        """Gera embedding da query."""
        return self.embeddings.embed_query(text)

    def _search_rpc(self, query_vector: List[float], limit: int = 20) -> List[Dict[str, Any]]:
        """Busca via RPC no Supabase."""
        response = self.supabase_admin.rpc(
            "rpc_vector_search",
            {"query_vector": query_vector, "limit_count": limit},
        ).execute()
        return response.data or []

    def _normalize_match_doc(self, match: Dict[str, Any]) -> Document:
        """Normaliza resultado RPC em Document."""
        metadata_raw = match.get("metadata")
        if isinstance(metadata_raw, dict):
            metadata = dict(metadata_raw)
        elif isinstance(metadata_raw, str):
            metadata = json.loads(metadata_raw) if metadata_raw else {}
        elif metadata_raw is None:
            metadata = {}
        else:
            metadata = {}
        metadata["db_id"] = match["id"]
        metadata["similarity"] = match["similarity"]
        return Document(
            page_content=match["content"],
            metadata=metadata,
        )

    def _search_lexical_rpc(self, query_terms: str, limit: int = 40) -> List[Dict[str, Any]]:
        """Busca léxica via `rpc_lexical_search` — paralela a `_search_rpc`,
        `rpc_vector_search` permanece intocada (ver design.md)."""
        response = self.supabase_admin.rpc(
            "rpc_lexical_search",
            {"query_terms": query_terms, "limit_count": limit},
        ).execute()
        return response.data or []

    def _normalize_lexical_match_doc(self, match: Dict[str, Any]) -> Document:
        """Normaliza resultado de `rpc_lexical_search` em Document.

        Não seta `similarity` — um doc encontrado só pela via léxica não tem
        cosseno comparável (ver `_rrf_fuse`, que decide o que fazer com
        isso); setar aqui um valor arbitrário arriscaria vazar para o piso
        de recusa antes da hora.
        """
        metadata_raw = match.get("metadata")
        if isinstance(metadata_raw, dict):
            metadata = dict(metadata_raw)
        elif isinstance(metadata_raw, str):
            metadata = json.loads(metadata_raw) if metadata_raw else {}
        else:
            metadata = {}
        metadata["db_id"] = match["id"]
        metadata["lexical_score_raw"] = match.get("lexical_rank")
        return Document(
            page_content=match["content"],
            metadata=metadata,
        )

    def _make_retrieval_dedup_key(self, doc: Document) -> str:
        """Gera chave para deduplicação."""
        db_id = doc.metadata.get("db_id")
        if db_id is not None:
            return f"db_id:{db_id}"
        source = doc.metadata.get("source", "")
        page = doc.metadata.get("page", "")
        strong_key = f"{source}:{page}".strip()
        if strong_key:
            return f"meta:{hashlib.sha256(strong_key.encode('utf-8')).hexdigest()[:12]}"
        content_hash = hashlib.sha256(doc.page_content.encode('utf-8')).hexdigest()[:20]
        return f"content:{content_hash}"

    def _detect_question_language(self, question: str) -> str:
        """Detecção de idioma: pt-BR ou en."""
        q_lower = question.lower()
        pt_words = {'como', 'qual', 'quais', 'não', 'tilápia', 'restrição', 'alimentar', 'viveiro', 'crescimento',
                    'alevinos', 'qual', 'o que', 'por que'}
        en_words = {'what', 'how', 'which', 'feed', 'restriction', 'restricted', 'diet', 'under', 'growth',
                    'fingerlings', 'why', 'describe'}
        pt_accents = any(c in 'áéíóúãõçÁÉÍÓÚÃÕÇ' for c in question)
        pt_score = sum(1 for w in pt_words if w in q_lower) + (2 if pt_accents else 0)
        en_score = sum(1 for w in en_words if w in q_lower)
        return 'pt-BR' if pt_score >= en_score else 'en'

    def _detect_question_type(self, question: str) -> str:
        """Detecta o tipo da pergunta para selecionar o prompt adequado.

        Retorna: 'quantitative' | 'conceptual' | 'comparative' | 'methodological'

        Quantitativo exige indicadores numéricos EXPLÍCITOS — nunca é o default.
        Default seguro = conceptual.
        """
        q_lower = question.lower()

        # Indicadores positivos de pergunta quantitativa: pede valor/medida específica
        quantitative = {
            'quanto pesa', 'quanto pesam', 'quanto foi', 'quanto cresceu', 'quanto mede',
            'qual o valor', 'qual foi o valor', 'qual a taxa', 'qual foi a taxa',
            'qual o percentual', 'qual a porcentagem', 'qual o índice',
            'qual o ganho de peso', 'qual foi o ganho', 'qual a média', 'qual o fcr',
            'qual a conversão alimentar', 'qual a sobrevivência', 'qual foi a sobrevivência',
            'qual a biomassa', 'qual o peso final', 'qual o comprimento',
            'quantos gramas', 'quantos cm', 'quantos dias', 'quantas semanas',
            'how much', 'how many', 'what is the rate', 'what is the value',
            'what percentage', 'what was the growth', 'what were the values',
            'survival rate', 'feed conversion ratio', 'specific growth rate',
        }

        conceptual = {
            'o que é', 'o que são', 'como funciona', 'como funcionam', 'explique',
            'defina', 'definição', 'por que', 'porque', 'o que significa',
            'descreva', 'qual a importância', 'qual é a importância',
            # consequências / efeitos / impactos → sempre conceptual
            'consequencia', 'consequências', 'consequência', 'consequencias',
            'efeito', 'efeitos', 'impacto', 'impactos',
            'benefício', 'benefícios', 'vantagem', 'vantagens',
            'desvantagem', 'desvantagens',
            # verbos de causa-efeito (ex: "O que acarreta a restrição alimentar?")
            'acarreta', 'acarretam', 'provoca', 'provocam', 'causa ', 'causam',
            'implica', 'implicam', 'resulta', 'resultam', 'ocorre', 'acontece',
            'leva a', 'levam a', 'afeta', 'afetam', 'influencia', 'influenciam',
            'prejudica', 'prejudicam', 'interfere', 'interferecem',
            # padrão inglês
            'what is a ', 'what is an ', 'what are', 'how does', 'how do', 'explain',
            'define', 'definition', 'why', 'what does', 'describe',
            'consequences', 'effects', 'impacts', 'benefits', 'advantages',
        }
        comparative = {
            'compare', 'comparação', 'diferença', 'diferenças', 'melhor que',
            'pior que', 'versus', ' vs ', 'entre os', 'entre as', 'comparar',
            'qual é melhor', 'comparison', 'difference', 'differences',
            'better than', 'worse than', 'between', 'which is better',
        }
        methodological = {
            'metodologia', 'método', 'métodos', 'delineamento', 'procedimento',
            'protocolo', 'como foi conduzido', 'como foi realizado', 'como foi feito',
            'materiais e métodos', 'methodology', 'method', 'methods', 'procedure',
            'experimental design', 'protocol', 'how was conducted', 'how was performed',
            'materials and methods',
        }

        quantitative_score = sum(1 for t in quantitative if t in q_lower)
        conceptual_score = sum(1 for t in conceptual if t in q_lower)
        comparative_score = sum(1 for t in comparative if t in q_lower)
        methodological_score = sum(1 for t in methodological if t in q_lower)

        # "o que" no início = pedido de explicação/definição → bônus conceptual
        if q_lower.startswith('o que ') or q_lower.startswith('quais '):
            conceptual_score += 1

        # Tipos de domínio específicos primeiro
        if comparative_score > 0 and comparative_score >= methodological_score:
            return 'comparative'
        if methodological_score > 0:
            return 'methodological'

        # Quantitativo só vence se tiver indicador EXPLÍCITO e nenhum conceptual
        if quantitative_score > 0 and quantitative_score > conceptual_score:
            return 'quantitative'

        # Qualquer sinal conceptual → conceptual (inclui "o que acarreta", "o que provoca", etc.)
        if conceptual_score > 0:
            return 'conceptual'

        # Default seguro: conceptual — o template é flexível e não exige seções rígidas
        return 'conceptual'

    # Sentinela devolvido pelo modelo quando o contexto não permite responder
    # — detectado em `generate` e substituído pela mensagem de recusa real.
    # Ver design.md, decisão 4: cobre o caso em que o contexto EXISTE mas,
    # mesmo com ressalva, não é suficiente — algo que o prompt antigo
    # proibia expressar (forçava preencher seções com "não disponível").
    NO_ANSWER_SENTINEL = "SEM_RESPOSTA_NO_CONTEXTO"

    # Prompt de `grade_context` — julga suficiência semântica ANTES de gerar,
    # porque similaridade de cosseno provadamente não separa in/out-of-corpus
    # neste corpus (uma pergunta fora do escopo mediu 0.620, acima de
    # perguntas legítimas em 0.539-0.544). Três estados, não dois — um
    # binário reproduziria o mesmo problema do threshold escalar. Em modo
    # observação (task 2), o resultado só é logado/gravado no State.
    #
    # Calibração (task 3, `run_grade_context_calibration.py`) contra as 35
    # perguntas do golden set adversarial: 34/35 (97.1%) — 11/11 (100%) nos
    # negativos fora do escopo, incluindo os dois marcados como mais difíceis
    # no design.md (`oos-fis-carpa`, `oos-rpl-streptococcus` — mesmo
    # vocabulário técnico e métrica do corpus, espécie/patógeno diferentes);
    # 23/24 (95.8%) nas perguntas respondíveis. A única divergência,
    # `fu-gen-menor-valor`, é uma das 4 perguntas de "maior e menor" já
    # sinalizadas no design.md como candidatas à decomposição condicional do
    # grupo 6 — não ajustado aqui de propósito, para não fazer o prompt
    # "decorar" o conjunto de teste.
    #
    # Uma iteração real de calibração ocorreu: a primeira rodada julgava as 4
    # perguntas de follow-up como `insufficient` (0/4) mesmo com contexto
    # correto — não era o prompt, era a pergunta errada sendo julgada. O nó
    # usava `state["question"]` (a pergunta crua, ex. "E qual teve o
    # menor?"), ininteligível sem o turno anterior; `generate` não tem esse
    # problema porque recebe o histórico completo como mensagens. Corrigido
    # trocando para `state["retrieval_query"]` (condensada por `retrieve`,
    # novo campo no `State`) — subiu de 31.4% para 97.1% de acurácia geral.
    _GRADE_CONTEXT_SYSTEM_PROMPT = (
        "You are grading whether retrieved document excerpts are sufficient to "
        "answer a specific question, for a Q&A system about tilapia, other "
        "fish species, or crustaceans (covering topics such as nutrition, "
        "genetics, health and disease, production, husbandry, water quality, "
        "economics, processing, or any related subject).\n\n"
        "Judge STRICTLY whether the context specifically addresses what the "
        "question asks — not whether it is merely topically related. The most "
        "important failure mode to catch: context that shares vocabulary, "
        "metrics, or structure with the question but is actually about a "
        "DIFFERENT subject — a different species, population, study, product, "
        "or entity than the one the question asks about. That is INSUFFICIENT "
        "even when it looks similar on the surface.\n\n"
        "Respond with exactly one word:\n\n"
        "SUFFICIENT — the context directly contains the specific information "
        "needed to answer the question completely.\n\n"
        "PARTIAL — the context is genuinely related to the question's subject "
        "and contains some relevant information, but does not fully or "
        "directly answer it.\n\n"
        "INSUFFICIENT — the context does not address the question's actual "
        "subject, including when it discusses a superficially similar topic "
        "about a different species, pathogen, study, or entity.\n\n"
        "Answer with ONLY one word: SUFFICIENT, PARTIAL, or INSUFFICIENT. No "
        "explanation, no punctuation."
    )

    _QUESTION_TYPE_EMPHASIS = {
        "quantitative": (
            "This question calls for precision on numeric data: include exact figures, "
            "n=, ±, %, p-values, and confidence intervals wherever the context provides them."
        ),
        "comparative": (
            "This question calls for a comparison: organize the answer contrastively, "
            "setting the compared items, groups, or treatments directly against each other."
        ),
        "methodological": (
            "This question calls for methodology: follow the natural order of the experiment "
            "or procedure as described in the context (design, procedures, measurements, analysis)."
        ),
        "conceptual": (
            "This question calls for a conceptual explanation: explain what the concept means, "
            "then its practical or biological relevance."
        ),
    }

    def _build_system_prompt(self, question_type: str, lang_instruction: str) -> str:
        """System prompt: uma base única em prosa contínua + uma linha de
        ênfase por tipo de pergunta.

        Os 4 templates antigos (um por `question_type`, cada um com seus
        próprios cabeçalhos de seção obrigatórios) eram ~90% estrutura
        repetida — regras de fundamentação, instrução de idioma, instrução
        de fidelidade — com um layout de seção diferente. Colapsados aqui
        numa base + 4 linhas de ênfase (ver design.md de
        restore-rag-answer-quality). Sem cabeçalho obrigatório: uma resposta
        sem dado para uma seção antes virava um placeholder formal
        ("Dados numéricos não disponíveis no contexto"), que é exatamente o
        sintoma de "resposta vazia" que motivou esta mudança.
        """
        emphasis = self._QUESTION_TYPE_EMPHASIS.get(
            question_type, self._QUESTION_TYPE_EMPHASIS["conceptual"]
        )
        return (
            f"You are an expert in tilapia aquaculture and fisheries science. {lang_instruction}\n\n"
            f"Answer the question directly and specifically, using ONLY the scientific context "
            f"provided, with maximum fidelity to the original data.\n\n"
            f"Write in continuous prose, organized in paragraphs — do not divide the answer into "
            f"labeled sections or a fixed template. Use a bulleted or numbered list only where the "
            f"content is a genuine enumeration (e.g. a sequence of steps, several parallel items) "
            f"and a list genuinely aids readability — never as a mandatory structure applied "
            f"regardless of content.\n\n"
            f"Weave numeric values into the prose as you discuss them (e.g. \"the PRO+MOS treatment "
            f"showed the highest relative protection level, 64.10%, against 21.02% for MOS\") rather "
            f"than listing them in a separate data section. If an aspect of the question has no data "
            f"in the context, address that briefly in a sentence or omit it — never as an empty "
            f"labeled section or a placeholder value.\n\n"
            f"GROUNDING RULES (mandatory):\n"
            f"  • Name populations, treatments, or stocks individually — never write \"some populations\"\n"
            f"  • Do NOT add general aquaculture knowledge not present in the context\n"
            f"  • Prefer \"the study found X=Y\" over \"X is generally important for Y\"\n"
            f"  • Do not extrapolate beyond what the authors conclude\n\n"
            f"{emphasis}\n\n"
            f"If the provided context does not contain the information needed to answer the "
            f"question, respond with exactly the text `{self.NO_ANSWER_SENTINEL}` and nothing else "
            f"— no partial answer, no apology, no explanation."
        )

    def _rewrite_query(self, question: str, lang: str) -> str:
        """Reescrita bilíngue da query."""
        q_lower = question.lower()
        rewritten = question
        if lang == 'pt-BR' and 'tilápia' in q_lower and 'nilo' in q_lower:
            rewritten += ' Oreochromis niloticus'
        elif lang == 'en' and ('oreochromis' in q_lower or 'niloticus' in q_lower):
            rewritten += ' tilápia do nilo'
        restriction_terms = [
            'restrição alimentar',
            'dieta restrita',
            'restrição dieta',
            'feed restriction',
            'restricted diet',
        ]
        if any(term in q_lower for term in restriction_terms):
            if lang == 'pt-BR':
                rewritten += ' feed restriction'
            elif lang == 'en':
                rewritten += ' restrição alimentar'
        if lang == 'pt-BR' and 'metabolismo' in q_lower:
            rewritten += ' metabolism'
        elif lang == 'en' and 'metabolism' in q_lower:
            rewritten += ' metabolismo'
        return rewritten.strip()

    def _expand_query_with_llm(self, question: str, lang: str) -> str:
        """Usa o LLM para expandir a query com sinônimos e termos bilíngues científicos.

        Faz uma chamada barata ao GPT-4o-mini. Em caso de falha, faz fallback para
        a reescrita por regras (_rewrite_query).
        """
        try:
            prompt = (
                f"You are a search query optimizer for scientific literature on tilapia aquaculture.\n\n"
                f"Original question: {question}\n"
                f"Language: {lang}\n\n"
                f"Return ONLY the original question followed by 4-6 relevant scientific synonyms "
                f"and bilingual equivalents (Portuguese and English) that improve document retrieval. "
                f"Do not add explanations or punctuation between terms. "
                f"Keep the original question first.\n\n"
                f"Example:\n"
                f"Input: 'Qual o ganho de peso de tilápias com restrição alimentar?'\n"
                f"Output: 'Qual o ganho de peso de tilápias com restrição alimentar? "
                f"weight gain feed restriction Oreochromis niloticus compensatory growth "
                f"crescimento compensatório desempenho zootécnico'"
            )
            response = self.llm_utility.invoke([HumanMessage(content=prompt)])
            expanded = response.content.strip()
            # Validação mínima: resposta maior que a pergunta e contém termos da pergunta
            q_start = question[:20].lower()
            if len(expanded) > len(question) and q_start in expanded.lower():
                logger.info("[expand_query] '%s...' → '%s...'", question[:40], expanded[len(question):60])
                return expanded
            logger.warning("[expand_query] resposta LLM inválida — usando reescrita local")
        except Exception as exc:
            logger.warning("[expand_query] falha LLM (%s) — usando reescrita local", exc)
        return self._rewrite_query(question, lang)

    def _generate_technical_paraphrase(self, question: str, lang: str) -> Optional[str]:
        """Reescreve a pergunta no registro técnico/científico do corpus,
        numa chamada LLM dedicada (mesmo padrão de chamada única e foco
        estreito de `_expand_query_with_llm`/`_condense_followup_question`).

        Retorna `None` em caso de falha/resposta inválida — o chamador
        decide o fallback (`_expand_query_multi_variant` simplesmente não
        inclui essa variante, sem quebrar as outras).
        """
        try:
            prompt = (
                "You are a domain expert in tilapia and other fish/crustacean "
                "aquaculture science.\n\n"
                f"Question (possibly phrased informally): {question}\n"
                f"Language: {lang}\n\n"
                "Reword this question the way it would be phrased in a "
                "scientific paper on the subject, using precise technical "
                "terminology instead of colloquial wording. Do NOT add facts "
                "that are not in the original question. Do NOT answer the "
                "question — only reword it. Return ONLY the reworded "
                "question, no explanations, no quotes."
            )
            response = self.llm_utility.invoke([HumanMessage(content=prompt)])
            paraphrase = response.content.strip().strip('"')
            if paraphrase and len(paraphrase) >= 5:
                return paraphrase
            logger.warning("[technical_paraphrase] resposta LLM inválida")
        except Exception as exc:
            logger.warning("[technical_paraphrase] falha LLM (%s)", exc)
        return None

    def _expand_query_multi_variant(self, question: str, lang: str) -> List[str]:
        """Gera múltiplas formulações da pergunta para busca vetorial em leque
        (multi-query fan-out).

        Ataca o caso em que o usuário não conhece a terminologia exata dos
        documentos: uma única string embutida (pergunta + sinônimos
        apendados, como em `_expand_query_with_llm`) pode não cruzar o piso
        de recusa por cosseno mesmo quando a pergunta é genuinamente
        respondível. Buscar com várias formulações dá mais chances de uma
        delas casar com o registro em que o corpus foi escrito — a fusão por
        MÁXIMO de similaridade entre variantes (`_retrieve_docs_via_rpc`)
        preserva a calibração existente do piso, só aumenta as chances de
        cruzá-lo com a formulação certa.

        Reaproveita `_expand_query_with_llm` (chamada dedicada, já validada
        em produção) em vez de pedir a mesma expansão numa única chamada
        combinada com a paráfrase. Medido na validação desta change: uma
        chamada só pedindo 3 saídas de uma vez (original/sinônimos/paráfrase)
        gera uma lista de sinônimos com mais variância/qualidade inferior à
        chamada dedicada — ao ponto de o MÁXIMO entre as variantes separadas
        ficar ABAIXO do que a chamada única de hoje já alcançava sozinha
        (caso `col-gen-fis-extremos`, ver tasks.md). Duas chamadas utilitárias
        (baratas, gpt-4o-mini) em vez de uma garantem que este método nunca
        fica pior que `_expand_query_with_llm` sozinho — só adiciona chance,
        nunca subtrai.

        Retorna sempre a pergunta original como 1ª variante. Se a paráfrase
        falhar, a lista ainda tem 2 variantes (original + expansão por
        sinônimos) — nunca cai abaixo do comportamento de query única.
        """
        variants = [question, self._expand_query_with_llm(question, lang)]
        paraphrase = self._generate_technical_paraphrase(question, lang)
        if paraphrase:
            variants.append(paraphrase)

        deduped: List[str] = []
        seen = set()
        for v in variants:
            key = v.strip().lower()
            if key and key not in seen:
                seen.add(key)
                deduped.append(v)

        logger.info(
            "[expand_query_multi] '%s...' → %d variantes", question[:40], len(deduped)
        )
        return deduped[:MULTI_QUERY_VARIANT_COUNT] or [question]

    def _condense_followup_question(
        self, question: str, history: List[List[str]], lang: str
    ) -> str:
        """Produz uma versão autocontida da pergunta para a busca vetorial.

        Sem isso, uma pergunta de follow-up ("E qual a margem por unidade?")
        é embutida sozinha, sem o turno anterior — confirmado como causa de
        recall baixo nas perguntas de follow-up do golden set. Só a QUERY DE
        BUSCA muda; `state["question"]` original permanece intacto para
        exibição e para o prompt de geração (que já recebe o histórico completo).
        """
        if not history:
            return question
        last_pair = history[-1]
        last_question = last_pair[0] if len(last_pair) >= 1 else ""
        last_answer = last_pair[1] if len(last_pair) >= 2 else ""
        try:
            prompt = (
                "Reescreva a PERGUNTA DE ACOMPANHAMENTO abaixo como uma pergunta "
                "completa e autocontida, incorporando o contexto necessário do "
                "turno anterior. Devolva APENAS a pergunta reescrita, sem "
                "explicações nem aspas.\n\n"
                f"Pergunta anterior: {last_question}\n"
                f"Resposta anterior: {last_answer[:500]}\n"
                f"Pergunta de acompanhamento: {question}\n\n"
                "Pergunta reescrita:"
            )
            response = self.llm_utility.invoke([HumanMessage(content=prompt)])
            condensed = response.content.strip().strip('"')
            if condensed and len(condensed) >= 5:
                logger.info(
                    "[condense_followup] '%s' -> '%s'", question, condensed[:80]
                )
                return condensed
            logger.warning("[condense_followup] resposta LLM inválida — usando fallback mecânico")
        except Exception as exc:
            logger.warning("[condense_followup] falha LLM (%s) — usando fallback mecânico", exc)
        return f"{last_question} {question}".strip()

    def _build_refusal_message(self, lang: str) -> str:
        """Mensagem de recusa honesta quando nenhum chunk atinge o piso mínimo
        de similaridade — usada no lugar de responder com o melhor match
        disponível, por mais fraco que seja."""
        if lang == "pt-BR":
            return (
                "Não encontrei informações suficientes na base de documentos "
                "disponível para responder a essa pergunta com confiança. "
                "Posso ajudar com outra pergunta relacionada aos temas cobertos "
                "pela base de conhecimento?"
            )
        return (
            "I couldn't find enough relevant information in the available "
            "documents to answer this question confidently. Feel free to ask "
            "something else related to the topics covered in the knowledge base."
        )

    # ── Auxiliares de avaliação de qualidade ──────────────────────────────────

    def _is_answer_relevant(self, question: str, answer: str) -> bool:
        """Verifica se ao menos um termo significativo da pergunta aparece na resposta.

        Normaliza acentos antes de comparar para evitar falsos negativos em pt-BR:
        ex.: "indice" (pergunta sem acento) deve bater em "índice" (resposta com acento).
        """
        import unicodedata

        def _norm(s: str) -> str:
            """Remove diacríticos e converte para ASCII minúsculo."""
            return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii').lower()

        stopwords = {
            'o', 'a', 'os', 'as', 'um', 'uma', 'de', 'da', 'do', 'em', 'para',
            'com', 'por', 'que', 'foi', 'the', 'an', 'of', 'in', 'for', 'is',
            'are', 'was', 'what', 'how', 'which', 'qual', 'como', 'quais',
        }
        words = [
            w.lower().strip('?.,!():')
            for w in question.split()
            if len(w) > 4 and w.lower().strip('?.,!():') not in stopwords
        ]
        if not words:
            return True
        answer_normalized = _norm(answer)
        return any(_norm(w) in answer_normalized for w in words)

    # ── Auxiliar de retry ──────────────────────────────────────────────────────

    def _expand_query_for_retry(self, question: str) -> str:
        """Expande a query para o 2º retry: aplica reescrita bilíngue e adiciona
        termos gerais de aquicultura de tilápia caso ainda não estejam presentes."""
        lang = self._detect_question_language(question)
        expanded = self._rewrite_query(question, lang)
        q_lower = expanded.lower()
        if 'tilápia' not in q_lower and 'tilapia' not in q_lower:
            expanded += ' tilapia tilápia'
        if 'oreochromis' not in q_lower:
            expanded += ' Oreochromis niloticus'
        logger.info("[retry] query expandida: %s", expanded)
        return expanded.strip()

    # Reaproveitada por `_build_lexical_query` (add-hybrid-lexical-vector-search)
    # — o antigo bônus de reranking manual que também a usava
    # (`_get_rerank_terms`/`_score_doc_bonus`/`_rerank_docs`) foi removido:
    # a fusão RRF é a versão correta e limitada do mesmo princípio (dar peso
    # a casamento léxico), sem o problema do bônus antigo (somava até
    # +0.2/+0.3 sem limite contra uma banda de decisão de 0.12, e casava por
    # substring sem respeitar fronteira de palavra — "mos" casava dentro de
    # "mostrar"). Ver design.md, decisão 6.
    _RERANK_STOPWORDS = {
        'o', 'a', 'os', 'as', 'um', 'uma', 'de', 'da', 'do', 'dos', 'das',
        'em', 'no', 'na', 'nos', 'nas', 'para', 'com', 'por', 'que', 'foi',
        'qual', 'quais', 'como', 'quando', 'onde', 'quanto', 'quantos',
        'the', 'an', 'of', 'in', 'for', 'is', 'are', 'was', 'what', 'how',
        'which', 'and', 'or', 'to', 'from', 'this', 'that', 'with',
    }

    # Preserva `.` entre dígitos para que "64.10"/"1.26" sobrevivam como um
    # único token (não dois) — a busca vetorial já dilui esses valores; a
    # léxica só ajuda se eles chegarem inteiros ao `to_tsquery`.
    _LEXICAL_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)*")

    def _build_lexical_query(self, question: str, rewritten_question: str) -> str:
        """Constrói os termos para `rpc_lexical_search`, unidos por `|`
        (OR) — nunca `&` (AND). `websearch_to_tsquery`/`plainto_tsquery`
        uniriam por AND por padrão, o que faria uma pergunta com vários
        termos não bater com nada a menos que TODOS os termos estivessem no
        mesmo chunk (ver design.md, decisão 4).

        NFKD + remoção de diacríticos antes de tokenizar — mitigação parcial
        de acentuação do lado Python (`unaccent` completo é melhoria
        futura, não-goal deste change). Reaproveita `_RERANK_STOPWORDS` em
        vez de manter uma segunda lista.

        Limiar de tamanho mínimo é 2, não >4 como no antigo bônus de
        reranking — siglas do domínio como "KV", "FIS", "RPL" são
        exatamente os termos que esta busca existe para capturar, e um
        limiar de 4+ as excluiria todas.
        """
        combined = f"{question} {rewritten_question}".lower()
        normalized = unicodedata.normalize("NFKD", combined)
        stripped = "".join(c for c in normalized if not unicodedata.combining(c))
        tokens = self._LEXICAL_TOKEN_RE.findall(stripped)
        terms = [t for t in tokens if len(t) >= 2 and t not in self._RERANK_STOPWORDS]
        if not terms:
            return ""
        # Preserva ordem de primeira aparição, remove duplicatas — a ordem
        # não afeta o ranking (`to_tsquery` com `|` é comutativo), mas uma
        # query menor é mais barata de parsear no Postgres.
        deduped_terms = list(dict.fromkeys(terms))
        return " | ".join(deduped_terms)

    def _rrf_fuse(
        self,
        vector_docs: List[Document],
        lexical_docs: List[Document],
        rrf_k: int = RRF_K,
    ) -> List[Document]:
        """Funde duas listas rankeadas (vetorial + léxica) via Reciprocal
        Rank Fusion: `score += 1/(rrf_k + rank)` por lista, usando só a
        POSIÇÃO de cada doc em cada lista — cosseno e `ts_rank_cd` vivem em
        escalas incompatíveis, RRF evita ter que normalizá-las (ver
        design.md, decisão 3).

        Docs encontrados só pela via léxica (ausentes de `vector_docs`)
        carregam `metadata["lexical_rank"]` — usado por `_select_context_docs`
        para excluí-los do piso de recusa por cosseno, que eles não têm
        (ver design.md, decisão 5, e grupo 4 de tasks.md).
        """
        scores: Dict[str, float] = {}
        doc_by_key: Dict[str, Document] = {}
        vector_keys = set()

        for rank, doc in enumerate(vector_docs):
            key = self._make_retrieval_dedup_key(doc)
            vector_keys.add(key)
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)
            doc_by_key[key] = doc

        for rank, doc in enumerate(lexical_docs):
            key = self._make_retrieval_dedup_key(doc)
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)
            if key not in vector_keys:
                doc.metadata["lexical_rank"] = rank
                doc_by_key[key] = doc
            # Já visto pela via vetorial: mantém o Document original (com
            # `similarity` real), só a fusão do score conta esse rank também.

        return sorted(
            doc_by_key.values(),
            key=lambda d: scores[self._make_retrieval_dedup_key(d)],
            reverse=True,
        )

    def _is_text_garbled(self, text: str, threshold: float = 0.04) -> bool:
        """Detecta texto com problema de encoding: muitos '?' indicam caracteres não decodificados."""
        if not text or len(text) < 50:
            return True
        ratio = text.count('?') / len(text)
        return ratio > threshold

    def _is_context_poor(self, context: str) -> bool:
        """Retorna True se o contexto recuperado é insuficiente para resposta quantitativa."""
        if not context or len(context.strip()) < 200:
            return True
        return self._is_text_garbled(context)

    def _add_data_companion_chunks(self, docs: List[Document]) -> List[Document]:
        """Injeta os chunks mais ricos em dados (tabelas/métricas) que
        ficaram fora da busca semântica — hoje a única fonte de certas
        tabelas (FIS, RPL) que a busca vetorial sozinha não recupera bem
        (ver design.md de restore-rag-answer-quality). Limitado, não
        removido: teto TOTAL (`DATA_COMPANION_MAX_TOTAL`, não por arquivo —
        o comportamento antigo por arquivo podia injetar até 5×N chunks de
        arquivos irrelevantes), elegibilidade restrita a arquivos já
        presentes no top-3 do ranking, e conta contra
        `CONTEXT_CHAR_BUDGET` (o orçamento já é calculado sobre `docs`
        antes desta chamada).
        """
        if not DATA_COMPANION_ENABLED or not docs:
            return docs

        present_ids = {d.metadata.get("db_id") for d in docs}
        eligible_file_ids = {
            d.metadata.get("original_file_id")
            for d in docs[:3]
            if d.metadata.get("original_file_id")
        }
        if not eligible_file_ids:
            return docs

        used_chars = sum(len(d.page_content) for d in docs)
        remaining_budget = max(CONTEXT_CHAR_BUDGET - used_chars, 0)

        candidates: List[Dict[str, Any]] = []
        for file_id in eligible_file_ids:
            try:
                resp = (
                    self.supabase_admin.table("documents")
                    .select("id, content, metadata")
                    .filter("metadata->>original_file_id", "eq", file_id)
                    .execute()
                )
                candidates.extend(resp.data or [])
            except Exception as exc:
                logger.warning("[data_companion] falha ao buscar chunks de %s: %s", file_id, exc)

        # Ordenar globalmente por densidade de dígitos — chunks de tabelas
        # têm muitos números. Pool único entre os arquivos elegíveis: o
        # teto é sobre o total, não garantido por arquivo.
        def digit_density(row: Dict[str, Any]) -> float:
            c = row.get("content", "")
            return sum(1 for ch in c if ch.isdigit()) / max(len(c), 1)

        candidates.sort(key=digit_density, reverse=True)

        companions: List[Document] = []
        for row in candidates:
            if len(companions) >= DATA_COMPANION_MAX_TOTAL:
                break
            db_id = row["id"]
            if db_id in present_ids:
                continue
            content = row.get("content", "")
            if len(content) > remaining_budget:
                continue
            meta = dict(row.get("metadata") or {})
            meta["db_id"] = db_id
            meta["similarity"] = 0.0   # não veio da busca semântica
            meta["companion"] = True
            companions.append(Document(page_content=content, metadata=meta))
            present_ids.add(db_id)
            remaining_budget -= len(content)

        if companions:
            logger.info(
                "[data_companion] adicionando %d/%d chunks de dados ao contexto (%d arquivos elegíveis)",
                len(companions), DATA_COMPANION_MAX_TOTAL, len(eligible_file_ids),
            )
        return docs + companions

    def _has_discriminative_lexical_match(self, question: str, rewritten_question: str) -> bool:
        """Verifica se ALGUM termo discriminativo da pergunta casa
        lexicalmente no corpus — segundo sinal de recusa, independente da
        similaridade de cosseno (ver design.md, decisão 5).

        "Discriminativo" exclui termos genéricos do domínio (frequência de
        documento acima de `LEXICAL_DISCRIMINATIVE_MAX_DOC_FREQ`) que
        casam com quase todo chunk e não ajudam a distinguir uma pergunta
        dentro do escopo de uma fora — medido: "tilapia" aparece em 64.5%
        dos chunks, "rpl" em 1.6%.

        Postura conservadora nas bordas: sem termos para checar, ou se a
        consulta de frequência falhar, não bloqueia (devolve True) — este
        é um sinal COMPLEMENTAR ao piso de cosseno, nunca deve ser a única
        fonte de uma recusa por causa de uma falha de infraestrutura.
        """
        lexical_query = self._build_lexical_query(question, rewritten_question)
        if not lexical_query:
            return True

        terms = lexical_query.split(" | ")
        try:
            response = self.supabase_admin.rpc(
                "rpc_lexical_term_doc_freq",
                {"terms": terms},
            ).execute()
            freqs = response.data or []
        except Exception:
            logger.warning(
                "[lexical_coverage] falha ao consultar frequência de termos — não bloqueia",
                exc_info=True,
            )
            return True

        for row in freqs:
            total = row.get("total_docs") or 0
            doc_count = row.get("doc_count") or 0
            if total <= 0:
                continue
            freq = doc_count / total
            if 0 < freq <= LEXICAL_DISCRIMINATIVE_MAX_DOC_FREQ:
                return True
        return False

    def _retrieve_docs_via_rpc(
        self,
        question: str,
        k: int = RETRIEVAL_K,
        use_llm_expansion: bool = True,
        trace_out: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """Recuperação via RPC com k variável.

        Sempre passa pelo piso de recusa (`_select_context_docs`) — não há
        mais um parâmetro de bypass. O antigo `skip_threshold` existia só
        para o caminho de retry (`retrieve_retry`), removido em
        `add-rag-self-correction-loop`: a nova tentativa de reformulação
        (`grade_context` → reformular query) passa pelo MESMO piso de
        recusa da tentativa original, nunca o ignora — ver design.md.

        Args:
            use_llm_expansion: se True, usa LLM para expandir a query (recuperação inicial).
                               Retries usam expansão por regras para evitar dupla chamada.
            trace_out:         se um dict for passado, é preenchido com métricas da
                               decisão de seleção (candidate_count, top_similarity_raw —
                               ANTES do gate, ao contrário do que os chamadores veem no
                               retorno — selected_count, context_chars, selection_reason).
                               Usado pelo harness de avaliação; produção não precisa passar isso.
        """
        lang = self._detect_question_language(question)
        query_variants: List[str] = []

        if use_llm_expansion and MULTI_QUERY_EXPANSION_ENABLED:
            # Fan-out multi-query (add-multi-query-retrieval-expansion): busca
            # com várias formulações da pergunta em vez de uma só, fundindo
            # os candidatos por MÁXIMO de cosseno por chunk (não RRF — todas
            # as buscas vivem no mesmo espaço vetorial, então isso preserva
            # a calibração existente do piso de recusa sem recalibrar nada).
            query_variants = self._expand_query_multi_variant(question, lang)
            rewritten_question = " ".join(query_variants)
            seen: Dict[str, Document] = {}
            for variant in query_variants:
                variant_vector = self._embed_query(variant)
                variant_matches = self._search_rpc(variant_vector, k)
                for m in variant_matches:
                    doc = self._normalize_match_doc(m)
                    key = self._make_retrieval_dedup_key(doc)
                    current_sim = doc.metadata.get("similarity", 0)
                    if key not in seen or current_sim > seen[key].metadata.get("similarity", 0):
                        seen[key] = doc
            vector_docs = sorted(
                seen.values(),
                key=lambda d: d.metadata.get("similarity", 0),
                reverse=True,
            )
        else:
            if use_llm_expansion:
                rewritten_question = self._expand_query_with_llm(question, lang)
            else:
                rewritten_question = self._rewrite_query(question, lang)
            query_vector = self._embed_query(rewritten_question)
            matches = self._search_rpc(query_vector, k)
            docs = [self._normalize_match_doc(m) for m in matches]
            seen = {}
            for doc in docs:
                key = self._make_retrieval_dedup_key(doc)
                current_sim = doc.metadata.get("similarity", 0)
                if key not in seen or current_sim > seen[key].metadata.get("similarity", 0):
                    seen[key] = doc
            vector_docs = sorted(
                seen.values(),
                key=lambda d: d.metadata.get("similarity", 0),
                reverse=True,
            )

        # Capturado ANTES do gate e ANTES da fusão híbrida — a decisão de
        # recusa e esta métrica de observabilidade usam sempre o cosseno
        # bruto da busca vetorial pura, nunca o ranking fundido por RRF
        # (ver `_select_context_docs`/design.md de
        # add-hybrid-lexical-vector-search, decisão 5).
        candidate_count = len(vector_docs)
        top_similarity_raw = vector_docs[0].metadata.get("similarity", 0) if vector_docs else 0.0

        if HYBRID_SEARCH_ENABLED:
            lexical_query = self._build_lexical_query(question, rewritten_question)
            lexical_docs: List[Document] = []
            if lexical_query:
                lexical_matches = self._search_lexical_rpc(lexical_query, k)
                lexical_docs = [self._normalize_lexical_match_doc(m) for m in lexical_matches]
            ranked = self._rrf_fuse(vector_docs, lexical_docs, rrf_k=RRF_K)
            logger.info(
                "[retrieve] híbrida: %d vetoriais, %d léxicos, %d fundidos",
                len(vector_docs), len(lexical_docs), len(ranked),
            )
        else:
            ranked = vector_docs

        selected, selection_reason = self._select_context_docs(ranked)

        # Sinal complementar de recusa (grupo 5 de add-hybrid-lexical-vector-search):
        # só roda na zona intermediária (entre o piso de recusa e o limiar
        # de confiança alta), onde o cosseno sozinho provadamente não
        # separa in/out-of-corpus (ver design.md). Nunca roda quando a
        # decisão de cosseno já recusou (nada a reforçar) nem quando a
        # similaridade já está acima do limiar de confiança (um match
        # lexical não pode "resgatar" uma recusa por cosseno, nem a
        # ausência de um pode enfraquecer uma confiança já alta).
        if (
            HYBRID_SEARCH_ENABLED
            and selection_reason != "refused"
            and REFUSAL_FLOOR_SIMILARITY <= top_similarity_raw < PRIMARY_RPC_SIMILARITY_THRESHOLD
            and not self._has_discriminative_lexical_match(question, rewritten_question)
        ):
            logger.warning(
                "[retrieve] zona intermediária (score=%.3f) sem termo discriminativo "
                "casando lexicalmente — recusando (sinal complementar de cobertura léxica)",
                top_similarity_raw,
            )
            selected = []
            selection_reason = "refused_no_lexical_coverage"

        if selection_reason in ("refused", "refused_no_lexical_coverage"):
            logger.warning(
                "[retrieve] Nenhum doc atinge o piso de recusa %.2f (melhor score=%.3f) — recusando",
                REFUSAL_FLOOR_SIMILARITY, top_similarity_raw,
            )
        else:
            logger.info(
                "[retrieve] seleção=%s: %d/%d candidatos (melhor score=%.3f, %d chars)",
                selection_reason, len(selected), candidate_count, top_similarity_raw,
                sum(len(d.page_content) for d in selected),
            )

        if trace_out is not None:
            trace_out.update({
                "candidate_count": candidate_count,
                "top_similarity_raw": top_similarity_raw,
                "selected_count": len(selected),
                "context_chars": sum(len(d.page_content) for d in selected),
                "selection_reason": selection_reason,
                "multi_query_enabled": MULTI_QUERY_EXPANSION_ENABLED,
                "query_variants": query_variants,
            })

        return selected

    def _select_context_docs(self, ranked: List[Document]) -> Tuple[List[Document], str]:
        """Seleciona o contexto final por ranking, com piso mínimo e teto
        máximo de chunks e orçamento de caracteres.

        Substitui o regime binário antigo (só chunks acima do threshold de
        confiança alta, ou TODOS os candidatos na "zona fraca"). Medido no
        golden set: esse regime nunca selecionava algo entre 7 e 39 chunks —
        só fome (1-6, causa da maioria das falhas reais) ou inundação (40,
        ~48% do corpus inteiro em caracteres). Ver design.md.

        Retorna (docs_selecionados, motivo), onde motivo é usado só para
        observabilidade/trace, não para decisão de chamador.
        """
        if not ranked:
            return [], "refused"

        # Piso de recusa e janela relativa usam sempre o cosseno bruto do
        # melhor candidato ENTRE OS QUE VIERAM DA BUSCA VETORIAL — nunca a
        # posição no ranking fundido por RRF (quando a busca híbrida está
        # ativa), e nunca a similaridade de um doc léxico-only (sinalizado
        # por `metadata["lexical_rank"]`, que não tem cosseno comparável).
        # O piso foi calibrado contra cosseno puro; um score fundido não
        # tem calibração equivalente (ver design.md de
        # add-hybrid-lexical-vector-search, decisão 5 e riscos). Quando a
        # busca híbrida está desligada, `ranked` nunca contém docs
        # léxico-only, então isto reduz exatamente ao comportamento
        # anterior (top = similaridade do primeiro candidato).
        vector_similarities = [
            d.metadata.get("similarity", 0.0)
            for d in ranked
            if "lexical_rank" not in d.metadata
        ]
        top = max(vector_similarities) if vector_similarities else 0.0
        if top < REFUSAL_FLOOR_SIMILARITY:
            return [], "refused"

        # Janela relativa ao melhor score — controla a FORMA da seleção.
        # Docs léxico-only nunca são cortados por este piso de cosseno (não
        # têm um score comparável) — sua posição no ranking fundido já
        # reflete a relevância léxica deles.
        floor = max(CONTEXT_ABSOLUTE_FLOOR, top - CONTEXT_RELATIVE_MARGIN)
        selected = [
            d for d in ranked
            if "lexical_rank" in d.metadata or d.metadata.get("similarity", 0.0) >= floor
        ]
        reason = "relative_window"

        # Preenchimento mínimo — nunca deixa a pergunta faminta, mesmo que a
        # janela relativa tenha produzido poucos candidatos.
        if len(selected) < CONTEXT_MIN_CHUNKS:
            selected = ranked[:CONTEXT_MIN_CHUNKS]
            reason = "min_fill"

        # Teto — nunca deixa a pergunta afogada, mesmo com muitos candidatos fortes.
        selected = selected[:CONTEXT_MAX_CHUNKS]

        # Orçamento de caracteres, nunca cortando abaixo do mínimo garantido.
        budgeted: List[Document] = []
        used_chars = 0
        for i, doc in enumerate(selected):
            doc_chars = len(doc.page_content)
            if used_chars + doc_chars > CONTEXT_CHAR_BUDGET and i >= CONTEXT_MIN_CHUNKS:
                break
            budgeted.append(doc)
            used_chars += doc_chars

        return budgeted, reason

    def retrieve_for_eval(
        self,
        question: str,
        history: Optional[List[List[str]]] = None,
        k: int = RETRIEVAL_K,
        use_llm_expansion: bool = True,
    ) -> Tuple[List[Document], Dict[str, Any]]:
        """Recuperação com condensação de follow-up, para o harness de avaliação.

        Não é API de produção — existe para que `evaluation/run_eval.py` exercite
        exatamente o mesmo caminho de condensação que o nó `retrieve` do grafo usa
        (via `_condense_followup_question`), em vez de medir a pergunta crua e
        reportar recall artificialmente baixo em perguntas de follow-up. Não expor
        via `main.py`/HTTP.
        """
        lang = self._detect_question_language(question)
        retrieval_query = self._condense_followup_question(question, history or [], lang)
        trace: Dict[str, Any] = {}
        docs = self._retrieve_docs_via_rpc(
            retrieval_query, k=k, use_llm_expansion=use_llm_expansion, trace_out=trace
        )
        trace["retrieval_query"] = retrieval_query
        return docs, trace


_rag_service_instance = None


def get_rag_service():
    """Get or create RAG service instance lazily."""
    global _rag_service_instance
    if _rag_service_instance is None:
        _OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        _SUPABASE_URL = os.getenv("SUPABASE_URL")
        _SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
        if not _OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY environment variable is not set. "
                "Please set it before using RAG service."
            )
        if not _SUPABASE_URL:
            raise ValueError(
                "SUPABASE_URL environment variable is not set. "
                "Please set it before using RAG service."
            )
        if not _SUPABASE_KEY:
            raise ValueError(
                "SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY environment variable is not set. "
                "Please set it before using RAG service."
            )
        _rag_service_instance = RAGService(_OPENAI_API_KEY, _SUPABASE_URL, _SUPABASE_KEY)
    return _rag_service_instance


class _RagServiceProxy:
    """Proxy that lazily instantiates rag_service on first access"""

    def __getattr__(self, name):
        return getattr(get_rag_service(), name)


rag_service = _RagServiceProxy()