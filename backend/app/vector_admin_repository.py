import logging
import json
import os.path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Optional
from app.database import supabase_admin
import hashlib
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class VectorAdminRepository:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.CONFIRMAR_EXCLUSAO = 'CONFIRMAR_EXCLUSAO'
        self.CONFIRMAR_LIMPEZA_TOTAL = 'CONFIRMAR_LIMPEZA_TOTAL'

    def _safe_metadata(self, metadata: Any) -> Dict[str, Any]:
        if metadata is None:
            return {}
        if isinstance(metadata, dict):
            return metadata
        if isinstance(metadata, str):
            try:
                return json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                pass
        return {}

    def _get_first_non_empty(self, *values: Any) -> Optional[str]:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _normalize_datetime(self, dt: Any) -> Optional[datetime]:
        if isinstance(dt, datetime):
            return dt
        if isinstance(dt, str):
            dt_str = dt.replace('Z', '+00:00')
            try:
                return datetime.fromisoformat(dt_str)
            except ValueError:
                pass
        return None

    def _datetime_to_iso(self, dt: Optional[datetime]) -> Optional[str]:
        return dt.isoformat() if dt else None

    def _coerce_int(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    # ===== MÉTODO 1 CORRIGIDO: _extract_document_fields =====
    def _extract_document_fields(self, row: dict) -> dict:
        """
        Extract and normalize all fields from a Supabase document row.
        """
        import os
        import hashlib

        metadata = self._safe_metadata(row.get('metadata', {}))
        source = metadata.get('source', '')
        title = metadata.get('title', '')

        # Fonte primária: campos explícitos no metadata JSON (mais confiável)
        metadata_original_name = metadata.get('original_file_name', '')
        metadata_original_id = metadata.get('original_file_id', '')

        # Detect temporary path (fallback quando metadata não tem os campos)
        temp_indicators = ['Temp', 'tmp', 'AppData', 'Local']
        is_temp = any(indicator in source for indicator in temp_indicators)

        # Determine original file name (metadata JSON tem prioridade)
        if metadata_original_name:
            original_file_name = metadata_original_name
        elif source:
            basename = os.path.basename(source)
            if is_temp and title:
                original_file_name = title
            else:
                original_file_name = basename if basename else 'unknown'
        else:
            original_file_name = 'unknown'

        # Compute MD5 hash (usa o do metadata se disponível, evita recomputação)
        if metadata_original_id:
            original_file_id = metadata_original_id
        else:
            original_file_id = hashlib.md5(original_file_name.encode('utf-8')).hexdigest()

        # Build result dictionary
        result = {
            'id': row.get('id'),
            'original_file_id': original_file_id,
            'original_file_name': original_file_name,
            'content': row.get('content', ''),
            'metadata': metadata,
            'created_at': self._normalize_datetime(row.get('created_at')),
            'updated_at': self._normalize_datetime(row.get('updated_at')),
            'deleted_at': self._normalize_datetime(row.get('deleted_at')),
            'last_ingested_at': self._normalize_datetime(row.get('last_ingested_at')),
            'page': row.get('page'),
            'chunk_index': row.get('chunk_index'),
            'storage_bucket': row.get('storage_bucket'),
            'storage_path': row.get('storage_path')
        }
        return result

    # ===== MÉTODO 2 CORRIGIDO: _group_valid_rows_by_file =====
    def _group_valid_rows_by_file(self, rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Agrupa linhas por original_file_id sem filtro rigoroso."""
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            extracted = self._extract_document_fields(row)
            file_id = extracted.get('original_file_id') or 'unknown'
            groups[file_id].append(extracted)
        return dict(groups)

    # ===== MÉTODO 3 CORRIGIDO: _build_file_summary =====
    def _build_file_summary(self, file_id: str, chunks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Constrói resumo correto do arquivo."""
        if not chunks:
            return None

        total_chunks = len(chunks)
        active_chunks_count = sum(1 for chunk in chunks if chunk.get('deleted_at') is None)
        deleted_chunks = total_chunks - active_chunks_count

        first = chunks[0]

        # Encontra máximo last_ingested_at
        max_last_ingested = None
        max_deleted_at = None
        for chunk in chunks:
            if chunk.get('last_ingested_at') and (
                    max_last_ingested is None or chunk['last_ingested_at'] > max_last_ingested):
                max_last_ingested = chunk['last_ingested_at']
            if chunk.get('deleted_at') and (max_deleted_at is None or chunk['deleted_at'] > max_deleted_at):
                max_deleted_at = chunk['deleted_at']

        status = 'active' if active_chunks_count > 0 else 'deleted'

        summary_metadata = {
            'source': first.get('original_file_name'),
            'total_chunks': total_chunks,
            'active_chunks': active_chunks_count,
            'deleted_chunks': deleted_chunks,
        }

        return {
            'original_file_id': file_id,
            'original_file_name': first.get('original_file_name'),
            'storage_bucket': first.get('storage_bucket'),
            'storage_path': first.get('storage_path'),
            'total_chunks': total_chunks,
            'active_chunks': active_chunks_count,
            'deleted_chunks': deleted_chunks,
            'deleted_at': self._datetime_to_iso(max_deleted_at),
            'last_ingested_at': self._datetime_to_iso(max_last_ingested),
            'status': status,
            'metadata': summary_metadata,
        }

    # ===== RESTO DOS MÉTODOS (MANTÉM IGUAL AO ORIGINAL) =====
    def _fetch_all_documents(self) -> List[Dict[str, Any]]:
        response = supabase_admin.table('documents').select('*').execute()
        return response.data or []

    def list_files(self) -> List[Dict[str, Any]]:
        """
        Returns a list with ONE summary per unique file.
        Groups all chunks by original_file_id and aggregates their data.
        """
        all_docs = self._fetch_all_documents()

        if not all_docs:
            return []

        grouped = self._group_valid_rows_by_file(all_docs)

        summaries = []
        for file_id, chunks in grouped.items():
            summary = self._build_file_summary(file_id, chunks)
            if summary:
                summaries.append(summary)

        summaries.sort(key=lambda s: s.get('last_ingested_at', '') or '', reverse=True)

        return summaries

    def get_file(self, original_file_id: str) -> Dict[str, Any]:
        files = self.list_files()
        for f in files:
            if f['original_file_id'] == original_file_id:
                return f
        raise ValueError(f'Arquivo não encontrado: {original_file_id}')

    def get_file_chunks(self, original_file_id: str) -> Dict[str, Any]:
        all_docs = self._fetch_all_documents()
        extracted = []
        for row in all_docs:
            ext = self._extract_document_fields(row)
            if ext['original_file_id'] == original_file_id:
                extracted.append(ext)

        def chunk_sort_key(c):
            return (
                (0 if c['chunk_index'] is not None else 1, c['chunk_index'] or 0),
                (0 if c['page'] is not None else 1, c['page'] or 0),
                (0 if c['created_at'] is not None else 1, c['created_at'].timestamp() if c['created_at'] else 0)
            )

        extracted.sort(key=chunk_sort_key)
        total_chunks = len(extracted)
        active_chunks_count = sum(1 for c in extracted if c['deleted_at'] is None)
        deleted_chunks = total_chunks - active_chunks_count
        original_file_name = extracted[0]['original_file_name'] if extracted else None
        chunks = [self._build_chunk_item(c) for c in extracted]

        return {
            'original_file_id': original_file_id,
            'original_file_name': original_file_name,
            'total_chunks': total_chunks,
            'active_chunks': active_chunks_count,
            'deleted_chunks': deleted_chunks,
            'chunks': chunks,
            'status': 'success',
            'message': 'Chunks recuperados com sucesso'
        }

    def _build_chunk_item(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'id': str(chunk['id']),
            'content': chunk['content'],
            'metadata': chunk['metadata'],
            'original_file_id': chunk['original_file_id'],
            'original_file_name': chunk['original_file_name'],
            'storage_bucket': chunk['storage_bucket'],
            'storage_path': chunk['storage_path'],
            'deleted_at': self._datetime_to_iso(chunk['deleted_at']),
            'created_at': self._datetime_to_iso(chunk['created_at']),
            'updated_at': self._datetime_to_iso(chunk['updated_at']),
            'page': chunk['page'],
            'chunk_index': chunk['chunk_index'],
        }

    def recover_file_content(self, original_file_id: str) -> Dict[str, Any]:
        chunk_data = self.get_file_chunks(original_file_id)
        active_chunks = [c for c in chunk_data['chunks'] if c['deleted_at'] is None]
        if active_chunks:
            recovered_content = '\n\n'.join(c['content'] for c in active_chunks)
        else:
            recovered_content = '\n\n'.join(c['content'] for c in chunk_data['chunks'])
        return {
            'original_file_id': original_file_id,
            'original_file_name': chunk_data['original_file_name'],
            'recovered_content': recovered_content,
            'status': 'success',
            'message': 'Conteúdo do arquivo recuperado com sucesso.'
        }

    def diagnose_file_recovery(self, original_file_id: str) -> Dict[str, Any]:
        chunk_data = self.get_file_chunks(original_file_id)
        chunks = chunk_data['chunks']
        total_chunks = len(chunks)
        active_chunks_count = sum(1 for c in chunks if c['deleted_at'] is None)
        deleted_chunks = total_chunks - active_chunks_count
        has_table_data = total_chunks > 0
        has_storage = bool(chunk_data.get('storage_bucket') and chunk_data.get('storage_path'))
        recoverable_from_table = active_chunks_count > 0
        recoverable_from_storage = has_storage
        recoverable_from_both = recoverable_from_table and recoverable_from_storage
        recoverable_from_none = not recoverable_from_table and not recoverable_from_storage

        return {
            'original_file_id': original_file_id,
            'original_file_name': chunk_data['original_file_name'],
            'total_chunks': total_chunks,
            'active_chunks': active_chunks_count,
            'deleted_chunks': deleted_chunks,
            'has_table_data': has_table_data,
            'has_storage': has_storage,
            'recoverable_from_table': recoverable_from_table,
            'recoverable_from_storage': recoverable_from_storage,
            'recoverable_from_both': recoverable_from_both,
            'recoverable_from_none': recoverable_from_none,
            'status': 'success',
            'message': 'Diagnóstico recuperado com sucesso'
        }

    def delete_file(self, original_file_id: str, confirmation_phrase: str, reason: Optional[str] = None,
                    hard_delete: bool = True) -> Dict[str, Any]:
        if confirmation_phrase != self.CONFIRMAR_EXCLUSAO:
            raise ValueError('Frase de confirmação inválida')

        file_summary = self.get_file(original_file_id)

        # Coluna original_file_id é null (LangChain não a popula).
        # Obtém os UUIDs reais dos chunks via get_file_chunks e apaga por ID.
        chunk_data = self.get_file_chunks(original_file_id)
        chunk_ids = [c['id'] for c in chunk_data.get('chunks', [])]
        if chunk_ids:
            response = supabase_admin.table('documents').delete().in_('id', chunk_ids).execute()
            documents_deleted = len(response.data or [])
        else:
            documents_deleted = 0

        storage_deleted = False
        storage_bucket = file_summary.get('storage_bucket')
        storage_path = file_summary.get('storage_path')
        if hard_delete and storage_bucket and storage_path:
            try:
                resp_storage = supabase_admin.storage.from_(storage_bucket).remove([storage_path])
                storage_deleted = 'error' not in str(resp_storage)
                self.logger.info(f'Storage deletado: {storage_path} de {storage_bucket}')
            except Exception as e:
                self.logger.error(f'Falha ao deletar storage {storage_path}: {e}')
                storage_deleted = False

        message = f'Arquivo deletado. {documents_deleted} documentos.'
        if storage_deleted:
            message += ' Storage removido.'

        return {
            'original_file_id': original_file_id,
            'original_file_name': file_summary.get('original_file_name'),
            'documents_deleted': documents_deleted,
            'storage_deleted': storage_deleted,
            'storage_bucket': storage_bucket,
            'storage_path': storage_path,
            'status': 'success',
            'message': message
        }

    def preview_cleanup(self) -> Dict[str, Any]:
        """Calcula, sem apagar nada, o que uma limpeza total removeria."""
        files = self.list_files()
        total_files_processed = len(files)
        total_documents_deleted = sum(f['total_chunks'] for f in files)
        total_storage_deleted = sum(
            1 for f in files if f.get('storage_bucket') and f.get('storage_path')
        )
        message = (
            f'Simulação concluída. Seriam processados: {total_files_processed} arquivos, '
            f'removidos: {total_documents_deleted} docs, '
            f'{total_storage_deleted} storages. Nenhum dado foi apagado.'
        )

        return {
            'total_files_processed': total_files_processed,
            'total_documents_deleted': total_documents_deleted,
            'total_storage_deleted': total_storage_deleted,
            'dry_run': True,
            'status': 'success',
            'message': message
        }

    def cleanup_vector_base(self, confirmation_phrase: str) -> Dict[str, Any]:
        if confirmation_phrase != self.CONFIRMAR_LIMPEZA_TOTAL:
            raise ValueError('Frase de confirmação inválida para limpeza total')

        files = self.list_files()
        total_files_processed = len(files)
        total_documents_deleted = 0
        total_storage_deleted = 0

        for file_info in files:
            try:
                del_resp = self.delete_file(
                    file_info['original_file_id'],
                    self.CONFIRMAR_EXCLUSAO,
                    hard_delete=True
                )
                total_documents_deleted += del_resp['documents_deleted']
                if del_resp['storage_deleted']:
                    total_storage_deleted += 1
            except Exception as e:
                self.logger.error(f'Falha ao deletar arquivo {file_info["original_file_id"]}: {e}')

        message = (
            f'Limpeza total concluída. '
            f'Processados: {total_files_processed} arquivos, '
            f'deletados: {total_documents_deleted} docs, '
            f'{total_storage_deleted} storages.'
        )

        return {
            'total_files_processed': total_files_processed,
            'total_documents_deleted': total_documents_deleted,
            'total_storage_deleted': total_storage_deleted,
            'dry_run': False,
            'status': 'success',
            'message': message
        }


vector_admin_repository = VectorAdminRepository()