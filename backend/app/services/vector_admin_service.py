import logging
import os
import tempfile
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

CONFIRMAR_REINDEXACAO = 'CONFIRMAR_REINDEXACAO'


class VectorAdminService:
    def __init__(self):
        self.repository = None
        self._repository_loaded = False
        self._load_repository()

    def _load_repository(self):
        """Lazy load repository to avoid import errors at service instantiation"""
        if self._repository_loaded:
            return

        try:
            import app.vector_admin_repository as repo_module
            if hasattr(repo_module, 'VectorAdminRepository'):
                self.repository = repo_module.VectorAdminRepository()
            elif hasattr(repo_module, 'vector_admin_repository'):
                self.repository = repo_module.vector_admin_repository
            else:
                self.repository = repo_module()
            self._repository_loaded = True
        except ImportError as e:
            logger.warning(f"vector_admin_repository not found (will attempt lazy load): {e}")
            self._repository_loaded = False
        except Exception as e:
            logger.warning(f"Error loading repository (will attempt lazy load): {e}")
            self._repository_loaded = False

    def _ensure_repository(self):
        """Ensure repository is loaded, raise if not available"""
        if not self._repository_loaded:
            self._load_repository()
        if not self.repository:
            raise RuntimeError("vector_admin_repository not available")

    def _call_repo_method(self, method_names: List[str], *args, **kwargs) -> Any:
        self._ensure_repository()
        for name in method_names:
            if hasattr(self.repository, name):
                method = getattr(self.repository, name)
                return method(*args, **kwargs)
        raise NotImplementedError(f"No compatible method found in repository for: {method_names}")

    def get_files(self) -> Any:
        return self._call_repo_method(['get_files', 'list_files', 'list_vector_files', 'fetch_files'])

    def get_file(self, original_file_id: str) -> Any:
        return self._call_repo_method(['get_file', 'fetch_file', 'get_file_detail'], original_file_id)

    def get_file_chunks(self, original_file_id: str) -> Any:
        return self._call_repo_method(['get_file_chunks', 'fetch_file_chunks', 'list_chunks'], original_file_id)

    def get_file_content(self, original_file_id: str) -> Any:
        return self._call_repo_method(['get_file_content', 'recover_file_content', 'fetch_file_content'],
                                      original_file_id)

    def get_file_diagnosis(self, original_file_id: str) -> Any:
        return self._call_repo_method(
            ['get_file_diagnosis', 'diagnose_file_recovery', 'diagnose_file', 'get_diagnosis'], original_file_id
        )

    def delete_file(self, original_file_id: str, confirmation_phrase: Union[str, bool] = True,
                    reason: Optional[str] = None, hard_delete: bool = True) -> Any:
        if isinstance(confirmation_phrase, bool):
            raise ValueError(
                "delete_file exige uma frase de confirmação explícita (string); "
                "um valor booleano não pode ser usado para autorizar a exclusão."
            )
        return self._call_repo_method(['delete_file', 'remove_file'], original_file_id, confirmation_phrase, reason,
                                      hard_delete)

    def cleanup(self, confirmation_phrase: Union[str, bool] = True) -> Any:
        if isinstance(confirmation_phrase, bool):
            if confirmation_phrase:
                return self._call_repo_method(['preview_cleanup'])
            raise ValueError(
                "cleanup exige uma frase de confirmação explícita (string) para executar a limpeza real; "
                "um valor booleano não pode autorizar a exclusão."
            )
        return self._call_repo_method(['cleanup', 'cleanup_vector_base', 'clear_vector_base'], confirmation_phrase)

    def cleanup_vector_base(self, confirmation_phrase: str) -> Any:
        return self.cleanup(confirmation_phrase)

    async def reindex_files(
        self, confirmation_phrase: str, original_file_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Reprocessa (nova extração + chunking + embeddings) um ou mais
        arquivos já indexados, a partir do PDF original salvo no Storage.

        Não depende de o conteúdo ter mudado — reindexar serve justamente
        para aplicar uma extração/chunking/embedding atualizado ao MESMO
        arquivo. Por isso ingere com `force=True` (ignora a checagem de
        duplicata por hash de conteúdo) e só remove os chunks antigos
        DEPOIS que a nova ingestão for confirmada bem-sucedida — se a
        reingestão falhar, os chunks antigos permanecem intactos (sem
        janela de perda de dados).
        """
        if confirmation_phrase != CONFIRMAR_REINDEXACAO:
            raise ValueError('Frase de confirmação inválida para reindexação')

        self._ensure_repository()

        if original_file_ids:
            targets: List[Dict[str, Any]] = []
            for file_id in original_file_ids:
                try:
                    targets.append(self.repository.get_file(file_id))
                except ValueError:
                    targets.append({'original_file_id': file_id, 'original_file_name': None, '_not_found': True})
        else:
            targets = self.repository.list_files()

        # Import tardio (mesmo motivo do resto do arquivo): evita erro de
        # import na instanciação deste serviço se as envs do RAG faltarem.
        from app.services.rag_service import get_rag_service
        rag_service = get_rag_service()

        results: List[Dict[str, Any]] = []
        processed_files = 0
        failed_files = 0
        total_chunks_created = 0

        for file_info in targets:
            original_file_id = file_info['original_file_id']
            original_file_name = file_info.get('original_file_name') or original_file_id

            if file_info.get('_not_found'):
                failed_files += 1
                results.append({
                    'original_file_id': original_file_id,
                    'original_file_name': None,
                    'status': 'failed',
                    'message': 'Arquivo não encontrado',
                    'chunks_created': 0,
                    'chunks_removed': 0,
                })
                continue

            storage_bucket = file_info.get('storage_bucket')
            storage_path = file_info.get('storage_path')
            if not storage_bucket or not storage_path:
                failed_files += 1
                results.append({
                    'original_file_id': original_file_id,
                    'original_file_name': original_file_name,
                    'status': 'failed',
                    'message': 'Arquivo original não está no Storage — não é possível reindexar.',
                    'chunks_created': 0,
                    'chunks_removed': 0,
                })
                continue

            old_chunks = self.repository.get_file_chunks(original_file_id).get('chunks', [])
            old_chunk_ids = [c['id'] for c in old_chunks]
            # Preserva a data da PRIMEIRA ingestão através desta reindexação:
            # usa o `first_ingested_at` já gravado (se um reindex anterior já
            # tiver acontecido) ou, na ausência dele, o `created_at` do chunk
            # mais antigo (primeira ingestão de verdade).
            first_ingested_at = min(
                (c.get('first_ingested_at') or c.get('created_at') for c in old_chunks if c.get('created_at')),
                default=None,
            )

            temp_path: Optional[str] = None
            try:
                file_bytes = self.repository.download_storage_object(storage_bucket, storage_path)
                ext = os.path.splitext(storage_path)[1] or '.pdf'
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
                    temp_path = temp_file.name
                    temp_file.write(file_bytes)

                ingest_result = await rag_service.ingest_pdf(
                    temp_path, original_file_name, force=True, first_ingested_at=first_ingested_at
                )

                if ingest_result.get('status') != 'success':
                    failed_files += 1
                    results.append({
                        'original_file_id': original_file_id,
                        'original_file_name': original_file_name,
                        'status': 'failed',
                        'message': ingest_result.get('message', 'Falha na reingestão'),
                        'chunks_created': 0,
                        'chunks_removed': 0,
                    })
                    continue

                chunks_removed = self.repository.delete_document_rows(old_chunk_ids)
                chunks_created = ingest_result.get('chunks', 0)

                processed_files += 1
                total_chunks_created += chunks_created
                results.append({
                    'original_file_id': original_file_id,
                    'original_file_name': original_file_name,
                    'status': 'success',
                    'message': 'Arquivo reindexado com sucesso',
                    'chunks_created': chunks_created,
                    'chunks_removed': chunks_removed,
                })
            except Exception as exc:
                logger.exception('[reindex_files] falha ao reindexar %s', original_file_id)
                failed_files += 1
                results.append({
                    'original_file_id': original_file_id,
                    'original_file_name': original_file_name,
                    'status': 'failed',
                    'message': str(exc),
                    'chunks_created': 0,
                    'chunks_removed': 0,
                })
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)

        if not targets:
            status = 'success'
            message = 'Nenhum arquivo para reindexar.'
        elif failed_files == 0:
            status = 'success'
            message = f'{processed_files} arquivo(s) reindexado(s) com sucesso.'
        elif processed_files > 0:
            status = 'partial_failure'
            message = f'{processed_files} arquivo(s) reindexado(s), {failed_files} falha(s).'
        else:
            status = 'error'
            message = f'Todas as {failed_files} reindexações falharam.'

        return {
            'processed_files': processed_files,
            'failed_files': failed_files,
            'total_chunks_created': total_chunks_created,
            'results': results,
            'status': status,
            'message': message,
        }


# Singleton - instantiated but with lazy repository loading
vector_admin_service = VectorAdminService()