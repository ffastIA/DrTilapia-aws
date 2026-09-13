"""
Services module for DrTilápia RAG system
Exports: RAGService, VectorAdminService
"""

import logging

logger = logging.getLogger(__name__)

# Explicit imports to resolve IDE references
from app.services.rag_service import RAGService, rag_service

# Vector admin service with graceful error handling
try:
    from app.services.vector_admin_service import VectorAdminService, vector_admin_service
except Exception as e:
    logger.warning(f"Failed to import VectorAdminService: {e}")
    VectorAdminService = None
    vector_admin_service = None

__all__ = [
    'RAGService',
    'rag_service',
    'VectorAdminService',
    'vector_admin_service',
]
