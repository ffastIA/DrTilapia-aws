// CAMINHO: frontend/hooks/useFishAnalysis.ts
'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  uploadFishImage,
  processFishAnalysis,
  listFishAnalyses,
  deleteFishAnalysis,
} from '@/lib/fishImageApi';
import type { FishAnalysisItem, ProcessResponse, FishError } from '@/types/fishImage';

export default function useFishAnalysis() {
  const [analyses, setAnalyses] = useState<FishAnalysisItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // IDs das imagens carregadas na sessão atual
  const [lateralId, setLateralId] = useState<string | null>(null);
  const [superiorId, setSuperiorId] = useState<string | null>(null);

  // Resultado do último processamento
  const [lastResult, setLastResult] = useState<ProcessResponse | null>(null);

  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<FishError | null>(null);

  const resetFeedback = useCallback(() => {
    setFeedback(null);
    setError(null);
  }, []);

  // ── Upload de imagem individual ──────────────────────────────────────────────
  const uploadImage = useCallback(async (
    file: File,
    tag: 'lateral' | 'superior',
    fatorConversao?: number | null,
  ): Promise<string | null> => {
    setIsUploading(true);
    setError(null);
    try {
      const result = await uploadFishImage(file, tag, fatorConversao);
      if (tag === 'lateral') setLateralId(result.id);
      else setSuperiorId(result.id);
      return result.id;
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setError({ message: e?.response?.data?.detail || e?.message || 'Erro no upload' });
      return null;
    } finally {
      setIsUploading(false);
    }
  }, []);

  // ── Processar par de imagens ──────────────────────────────────────────────────
  const processImages = useCallback(async (opts: {
    lateralId: string;
    superiorId: string;
    fatorLateral?: number | null;
    fatorSuperior?: number | null;
    pesoG?: number | null;
  }): Promise<ProcessResponse | null> => {
    setIsProcessing(true);
    setError(null);
    setLastResult(null);
    try {
      const result = await processFishAnalysis({
        lateral_id: opts.lateralId,
        superior_id: opts.superiorId,
        fator_lateral: opts.fatorLateral,
        fator_superior: opts.fatorSuperior,
        peso_g: opts.pesoG,
      });
      setLastResult(result);
      setFeedback('Análise concluída com sucesso!');
      // Limpar IDs da sessão após processamento bem-sucedido
      setLateralId(null);
      setSuperiorId(null);
      return result;
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setError({ message: e?.response?.data?.detail || e?.message || 'Erro no processamento' });
      return null;
    } finally {
      setIsProcessing(false);
    }
  }, []);

  // ── Listar análises ───────────────────────────────────────────────────────────
  const refreshAnalyses = useCallback(async (filters?: {
    date_from?: string;
    date_to?: string;
    kvol_min?: number;
    kvol_max?: number;
  }) => {
    setIsLoadingList(true);
    try {
      const data = await listFishAnalyses(filters);
      setAnalyses(data.items);
      setTotal(data.total);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setError({ message: e?.response?.data?.detail || e?.message || 'Erro ao carregar análises' });
    } finally {
      setIsLoadingList(false);
    }
  }, []);

  useEffect(() => { refreshAnalyses(); }, [refreshAnalyses]);

  // ── Excluir análise ───────────────────────────────────────────────────────────
  const deleteAnalysis = useCallback(async (analysisId: string): Promise<boolean> => {
    setIsDeleting(true);
    try {
      await deleteFishAnalysis(analysisId);
      setAnalyses((prev) => prev.filter((a) => a.id !== analysisId));
      setTotal((prev) => prev - 1);
      setFeedback('Análise excluída com sucesso');
      return true;
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setError({ message: e?.response?.data?.detail || e?.message || 'Erro ao excluir análise' });
      return false;
    } finally {
      setIsDeleting(false);
    }
  }, []);

  return {
    // Estado da sessão de upload
    lateralId,
    superiorId,
    setLateralId,
    setSuperiorId,
    // Operações
    uploadImage,
    processImages,
    deleteAnalysis,
    refreshAnalyses,
    // Dados históricos
    analyses,
    total,
    // Status
    isUploading,
    isProcessing,
    isDeleting,
    isLoadingList,
    lastResult,
    feedback,
    error,
    resetFeedback,
  };
}
