from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator

class VectorFileSummary(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    original_file_id: str
    original_file_name: str
    storage_bucket: Optional[str] = None
    storage_path: Optional[str] = None
    total_chunks: int = 0
    active_chunks: int = 0
    deleted_chunks: int = 0
    deleted_at: Optional[str] = None
    last_ingested_at: Optional[str] = None
    status: str = "unknown"
    metadata: Dict[str, Any] = Field(default_factory=dict)

class VectorFileDetail(VectorFileSummary):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

class DeleteFileRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    confirmation_phrase: Optional[str] = None
    reason: Optional[str] = None
    hard_delete: bool = True
    delete_chunks: Optional[bool] = None

    @model_validator(mode="after")
    def validate_fields(self):
        if self.delete_chunks is not None and self.hard_delete is None:
            self.hard_delete = self.delete_chunks
        if not self.confirmation_phrase or self.confirmation_phrase.strip() == "":
            raise ValueError("confirmation_phrase é obrigatório para excluir um arquivo")
        if self.confirmation_phrase.strip() == "CONFIRMADO":
            self.confirmation_phrase = "CONFIRMAR_EXCLUSAO"
        return self

class DeleteFileResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    original_file_id: str
    original_file_name: str
    documents_deleted: int = 0
    storage_deleted: bool = False
    storage_bucket: Optional[str] = None
    storage_path: Optional[str] = None
    status: str
    message: str

class CleanupVectorBaseRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    confirmation_phrase: Optional[str] = None
    dry_run: Optional[bool] = None

    @model_validator(mode="after")
    def validate_fields(self):
        if not self.confirmation_phrase or self.confirmation_phrase.strip() == "":
            # Ausência de confirmação nunca autoriza a limpeza real — trata como simulação.
            self.dry_run = True
            self.confirmation_phrase = "SIMULACAO"
        elif self.confirmation_phrase.strip() == "CONFIRMADO":
            self.confirmation_phrase = "CONFIRMAR_LIMPEZA_TOTAL"
        return self

class CleanupVectorBaseResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    total_files_processed: int = 0
    total_documents_deleted: int = 0
    total_storage_deleted: int = 0
    dry_run: bool = False
    status: str
    message: str

class VectorChunk(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    id: str
    content: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    original_file_id: str
    original_file_name: str
    storage_bucket: Optional[str] = None
    storage_path: Optional[str] = None
    deleted_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    page: Optional[int] = None
    chunk_index: Optional[int] = None

class VectorChunksResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    original_file_id: str
    original_file_name: str
    total_chunks: int = 0
    active_chunks: int = 0
    deleted_chunks: int = 0
    chunks: List[VectorChunk] = Field(default_factory=list)
    status: str
    message: str

class RecoverFileContentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    original_file_id: str
    original_file_name: str
    storage_bucket: Optional[str] = None
    storage_path: Optional[str] = None
    total_chunks: int = 0
    active_chunks: int = 0
    deleted_chunks: int = 0
    content: str = ""
    chunks: List[VectorChunk] = Field(default_factory=list)
    status: str
    message: str

class RecoveryDiagnosisResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    original_file_id: str
    original_file_name: str
    total_chunks: int = 0
    active_chunks: int = 0
    deleted_chunks: int = 0
    has_table_data: bool = False
    has_storage: bool = False
    recoverable_from_table: bool = False
    recoverable_from_storage: bool = False
    recoverable_from_both: bool = False
    recoverable_from_none: bool = False
    status: str
    message: str