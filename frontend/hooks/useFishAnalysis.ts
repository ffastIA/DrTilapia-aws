// CAMINHO: frontend/hooks/useFishAnalysis.ts
'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  uploadFishImage,
  processFishAnalysis,
  getFishAnalysisJob,
  listFishAnalyses,
  deleteFishAnalysis,
} from '@/lib/fishImageApi';
import type { FishAnalysisItem, ProcessResponse, FishError, FishAnalysisJobStatus } from '@/types/fishImage';

// Polling do job: intervalo entre consultas e teto de espera total. Acima
// do teto, o processamento provavelmente ainda está rodando (rembg pode
// demorar), mas deixamos de bloquear a UI — o usuário pode conferir o
// resultado depois na lista de análises.
const POLL_INTERVAL_MS = 2_000;
const POLL_MAX_WAIT_MS = 5 * 60 * 1000;
// Tolera algumas falhas de rede consecutivas durante o polling (ex.: blip
// momentâneo de conectividade) antes de desistir — uma falha isolada não
// deve abortar o processamento que já está rodando no backend.
const POLL_MAX_CONSECUTIVE_FAILURES = 5;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default function useFishAnalysis() {
  const [analyses, setAnalyses] = useState<FishAnalysisItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  // Estágio do job em andamento, para a UI diferenciar "na fila" de
  // "processando" enquanto isProcessing === true.
  const [processingStage, setProcessingStage] = useState<FishAnalysisJobStatus | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Evita continuar o polling (setState) depois que o componente desmontou
  // ou uma nova chamada a processImages substituiu o job em andamento.
  const pollGenerationRef = useRef(0);

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

  // ── Processar par de imagens (assíncrono: cria o job e faz polling) ───────────
  const processImages = useCallback(async (opts: {
    lateralId: string;
    superiorId: string;
    fatorLateral?: number | null;
    fatorSuperior?: number | null;
    pesoG?: number | null;
  }): Promise<ProcessResponse | null> => {
    // Invalida qualquer polling anterior ainda em voo (nova chamada
    // substitui a anterior) e reserva esta geração como a atual.
    const generation = ++pollGenerationRef.current;

    setIsProcessing(true);
    setProcessingStage('queued');
    setError(null);
    setLastResult(null);
    try {
      const created = await processFishAnalysis({
        lateral_id: opts.lateralId,
        superior_id: opts.superiorId,
        fator_lateral: opts.fatorLateral,
        fator_superior: opts.fatorSuperior,
        peso_g: opts.pesoG,
      });

      const deadline = Date.now() + POLL_MAX_WAIT_MS;
      let consecutiveFailures = 0;

      while (true) {
        if (pollGenerationRef.current !== generation) {
          // Componente desmontou ou outro processImages assumiu — para
          // silenciosamente, sem tocar mais no estado.
          return null;
        }

        let job;
        try {
          job = await getFishAnalysisJob(created.job_id);
          consecutiveFailures = 0;
        } catch (pollErr: unknown) {
          consecutiveFailures += 1;
          if (consecutiveFailures >= POLL_MAX_CONSECUTIVE_FAILURES) {
            throw pollErr;
          }
          await sleep(POLL_INTERVAL_MS);
          continue;
        }

        if (job.status === 'done') {
          if (pollGenerationRef.current !== generation) return null;
          const result = job.result as ProcessResponse;
          setLastResult(result);
          setFeedback('Análise concluída com sucesso!');
          setLateralId(null);
          setSuperiorId(null);
          return result;
        }

        if (job.status === 'error') {
          throw Object.assign(new Error(job.error || 'Erro no processamento'), {
            response: { data: { detail: job.error } },
          });
        }

        if (pollGenerationRef.current !== generation) return null;
        setProcessingStage(job.status); // 'queued' | 'processing'

        if (Date.now() >= deadline) {
          throw new Error(
            'O processamento está demorando mais que o esperado. Confira o resultado depois na lista de análises.'
          );
        }

        await sleep(POLL_INTERVAL_MS);
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      if (pollGenerationRef.current === generation) {
        setError({ message: e?.response?.data?.detail || e?.message || 'Erro no processamento' });
      }
      return null;
    } finally {
      if (pollGenerationRef.current === generation) {
        setIsProcessing(false);
        setProcessingStage(null);
      }
    }
  }, []);

  // Cancela o polling em andamento se o componente desmontar.
  useEffect(() => {
    return () => {
      pollGenerationRef.current += 1;
    };
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
    processingStage,
    isDeleting,
    isLoadingList,
    lastResult,
    feedback,
    error,
    resetFeedback,
  };
}
