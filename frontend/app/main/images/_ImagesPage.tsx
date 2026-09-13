'use client';
// CAMINHO: frontend/app/main/images/_ImagesPage.tsx

import { ChangeEvent, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { BarChart2Icon } from 'lucide-react';
import useFishAnalysis from '@/hooks/useFishAnalysis';
import type { ProcessResponse } from '@/types/fishImage';
import PageHeader from '@/components/ui/PageHeader';
import BackButton from '@/components/ui/BackButton';
import Card from '@/components/ui/Card';
import Field, { Input } from '@/components/ui/Field';
import Alert from '@/components/ui/Alert';
import Button from '@/components/Button';

// ── helpers ───────────────────────────────────────────────────────────────────

function fmt(v: number | null | undefined, decimals = 2): string {
  if (v == null) return '—';
  return v.toFixed(decimals);
}

// ── Janela de upload individual ───────────────────────────────────────────────
// FIX: fatorValue e onFatorChange são controlados pelo pai para que o valor
// esteja sempre disponível no momento de clicar em "Processar",
// independentemente de quando o usuário digitou o fator.

interface UploadWindowProps {
  label: string;
  tag: 'lateral' | 'superior';
  imageId: string | null;
  preview: string | null;
  isUploading: boolean;
  fatorValue: string;
  onFatorChange: (v: string) => void;
  onUpload: (file: File, tag: 'lateral' | 'superior') => void;
}

function UploadWindow({
  label, tag, imageId, preview, isUploading,
  fatorValue, onFatorChange, onUpload,
}: UploadWindowProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    onUpload(file, tag);
    e.target.value = '';
  };

  return (
    <Card className={`flex flex-col gap-2 ${imageId ? 'border-primary' : ''}`}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">{label}</span>
        {imageId && (
          <span className="text-xs bg-success-bg text-success px-2 py-0.5 border border-success/35">✓ Pronta</span>
        )}
      </div>

      {/* Preview */}
      <div className="w-full aspect-video bg-surface flex items-center justify-center overflow-hidden border border-border">
        {preview ? (
          <img src={preview} alt={label} className="max-h-full max-w-full object-contain" />
        ) : (
          <span className="text-muted-foreground text-xs text-center px-2">
            Selecione uma imagem<br />do disco local
          </span>
        )}
      </div>

      {/* Fator de conversão — controlado pelo pai */}
      <Field label="Fator px/cm (opcional — usa ArUco se vazio)" htmlFor={`fator-${tag}`}>
        <Input
          id={`fator-${tag}`}
          type="number"
          step="0.01"
          min="0"
          placeholder="ex: 56.00"
          value={fatorValue}
          onChange={(e) => onFatorChange(e.target.value)}
        />
      </Field>

      {/* Botão upload */}
      <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={handleFile} />
      <Button onClick={() => inputRef.current?.click()} disabled={isUploading} variant="primary" className="w-full">
        {isUploading ? 'Enviando…' : 'Selecionar Imagem'}
      </Button>
    </Card>
  );
}

// ── Painel de resultados ──────────────────────────────────────────────────────

function MetricCard({
  label, valueCm, valuePx, unit = 'cm',
}: {
  label: string;
  valueCm: string;
  valuePx?: string;
  unit?: string;
}) {
  return (
    <div className="bg-surface border border-border p-4">
      <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-heading font-semibold mt-1">
        {valueCm} <span className="text-sm font-normal text-muted-foreground">{unit}</span>
      </p>
      {valuePx != null && (
        <p className="text-xs text-muted-foreground mt-1">{valuePx} px</p>
      )}
    </div>
  );
}

function ResultPanel({ result }: { result: ProcessResponse }) {
  const lat = result.lateral_metrics as Record<string, unknown> | null ?? {};
  const sup = result.superior_metrics as Record<string, unknown> | null ?? {};

  // Comprimento → bbox_width da lateral
  const comprPx  = lat['bbox_width_px']  != null ? fmt(lat['bbox_width_px']  as number, 0) : undefined;
  // Altura → bbox_height da lateral
  const altPx    = lat['bbox_height_px'] != null ? fmt(lat['bbox_height_px'] as number, 0) : undefined;
  // Largura → bbox_height da superior
  const largPx   = sup['bbox_height_px'] != null ? fmt(sup['bbox_height_px'] as number, 0) : undefined;
  // Área máscara
  const areLatPx = lat['mask_area_px']   != null ? fmt(lat['mask_area_px']   as number, 0) : undefined;
  const areSupPx = sup['mask_area_px']   != null ? fmt(sup['mask_area_px']   as number, 0) : undefined;
  const areLatCm = lat['mask_area_cm2']  != null ? fmt(lat['mask_area_cm2']  as number, 2) : '—';
  const areSupCm = sup['mask_area_cm2']  != null ? fmt(sup['mask_area_cm2']  as number, 2) : '—';
  // Fator
  const fatorLat = lat['fator_conversao'] != null ? fmt(lat['fator_conversao'] as number, 2) : '—';
  const fatorSup = sup['fator_conversao'] != null ? fmt(sup['fator_conversao'] as number, 2) : '—';

  return (
    <Card className="space-y-6">
      <h2 className="font-heading font-semibold text-xl uppercase">Resultados da Análise</h2>

      {result.warnings.length > 0 && (
        <div className="bg-primary/5 border border-primary/40 p-3 space-y-1">
          {result.warnings.map((w, i) => (
            <p key={i} className="text-primary text-sm">⚠ {w}</p>
          ))}
        </div>
      )}

      {/* Métricas principais — cm + px na mesma card */}
      <div>
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">Dimensões</h3>
        <div className="grid grid-cols-2 gap-4">
          <MetricCard label="Comprimento" valueCm={fmt(result.comprimento_cm)} valuePx={comprPx} />
          <MetricCard label="Altura"      valueCm={fmt(result.altura_cm)}      valuePx={altPx} />
          <MetricCard label="Largura"     valueCm={fmt(result.largura_cm)}     valuePx={largPx} />
          {result.kvol != null ? (
            <MetricCard label="Kvol" valueCm={fmt(result.kvol, 6)} unit="" />
          ) : (
            <div className="bg-surface border border-border p-4">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">Kvol</p>
              <p className="text-muted-foreground text-sm mt-2">Peso não informado</p>
            </div>
          )}
        </div>
      </div>

      {/* Área da máscara */}
      <div>
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">Área da Máscara</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-surface border border-border p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wide">Lateral</p>
            <p className="text-xl font-heading font-semibold mt-1">{areLatCm} <span className="text-sm font-normal text-muted-foreground">cm²</span></p>
            {areLatPx && <p className="text-xs text-muted-foreground mt-1">{areLatPx} px²</p>}
          </div>
          <div className="bg-surface border border-border p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wide">Superior</p>
            <p className="text-xl font-heading font-semibold mt-1">{areSupCm} <span className="text-sm font-normal text-muted-foreground">cm²</span></p>
            {areSupPx && <p className="text-xs text-muted-foreground mt-1">{areSupPx} px²</p>}
          </div>
        </div>
      </div>

      {/* Fatores de escala usados */}
      <div className="bg-surface border border-border p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">Fator de Escala Usado</h3>
        <div className="grid grid-cols-2 gap-4 text-sm text-muted-foreground">
          <p>Lateral: <span className="text-foreground font-mono">{fatorLat} px/cm</span></p>
          <p>Superior: <span className="text-foreground font-mono">{fatorSup} px/cm</span></p>
        </div>
      </div>
    </Card>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────

export default function ImagesPage() {
  const router = useRouter();
  const {
    lateralId, superiorId,
    uploadImage, processImages, resetFeedback,
    isUploading, isProcessing,
    lastResult, feedback, error,
  } = useFishAnalysis();

  // Previews locais
  const [lateralPreview,  setLateralPreview]  = useState<string | null>(null);
  const [superiorPreview, setSuperiorPreview] = useState<string | null>(null);

  // FIX: fatores controlados pelo pai — sempre refletem o valor atual do campo
  const [fatorLateralStr,  setFatorLateralStr]  = useState<string>('');
  const [fatorSuperiorStr, setFatorSuperiorStr] = useState<string>('');

  const [pesoG, setPesoG] = useState<string>('');

  const canProcess = !!lateralId && !!superiorId && !isProcessing;

  const handleUpload = async (file: File, tag: 'lateral' | 'superior') => {
    const url = URL.createObjectURL(file);
    if (tag === 'lateral') setLateralPreview(url);
    else setSuperiorPreview(url);
    // FIX: fator NÃO é capturado aqui — será lido em handleProcess
    await uploadImage(file, tag, null);
  };

  const handleProcess = async () => {
    if (!lateralId || !superiorId) return;
    // lê os fatores do estado do pai no momento do clique — sempre atualizado
    const fatorLateral  = fatorLateralStr  ? parseFloat(fatorLateralStr)  : null;
    const fatorSuperior = fatorSuperiorStr ? parseFloat(fatorSuperiorStr) : null;
    const result = await processImages({
      lateralId,
      superiorId,
      fatorLateral,
      fatorSuperior,
      pesoG: pesoG ? parseFloat(pesoG) : null,
    });
    // Substitui previews pelas imagens processadas (máscara + bbox)
    if (result?.lateral_viz_b64) {
      setLateralPreview(`data:image/jpeg;base64,${result.lateral_viz_b64}`);
    }
    if (result?.superior_viz_b64) {
      setSuperiorPreview(`data:image/jpeg;base64,${result.superior_viz_b64}`);
    }
  };

  return (
    <div>
      <PageHeader
        kicker="Biometria"
        title="Análise de Imagens por IA"
        actions={
          <>
            <Button onClick={() => router.push('/main/images/dashboard')} variant="secondary" size="sm" className="!inline-flex !items-center !gap-1.5">
              <BarChart2Icon size={16} />
              Dashboards
            </Button>
            <BackButton />
          </>
        }
      />

      {feedback && (
        <Alert variant="success" className="relative pr-10">
          {feedback}
          <button onClick={resetFeedback} className="absolute top-2 right-2.5 text-lg leading-none">×</button>
        </Alert>
      )}
      {error && (
        <Alert variant="error" className="relative pr-10">
          {error.message}
          <button onClick={resetFeedback} className="absolute top-2 right-2.5 text-lg leading-none">×</button>
        </Alert>
      )}

      {/* Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(220px,320px)_1fr] gap-6 items-start">

        {/* ── Coluna esquerda: uploads ── */}
        <aside className="flex flex-col gap-4">
          <UploadWindow
            label="Imagem Lateral"
            tag="lateral"
            imageId={lateralId}
            preview={lateralPreview}
            isUploading={isUploading}
            fatorValue={fatorLateralStr}
            onFatorChange={setFatorLateralStr}
            onUpload={handleUpload}
          />

          <UploadWindow
            label="Imagem Superior"
            tag="superior"
            imageId={superiorId}
            preview={superiorPreview}
            isUploading={isUploading}
            fatorValue={fatorSuperiorStr}
            onFatorChange={setFatorSuperiorStr}
            onUpload={handleUpload}
          />

          <Card>
            <Field label="Peso do peixe (g)" htmlFor="peso">
              <Input
                id="peso"
                type="number"
                step="0.1"
                min="0"
                placeholder="ex: 250.0"
                value={pesoG}
                onChange={(e) => setPesoG(e.target.value)}
              />
            </Field>
            <p className="text-xs text-muted-foreground -mt-2 mb-3">Necessário para calcular Kvol</p>

            <Button onClick={handleProcess} disabled={!canProcess} variant="primary" className="w-full">
              {isProcessing ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                  </svg>
                  Processando…
                </span>
              ) : '▶ Processar'}
            </Button>

            {!lateralId && (
              <p className="text-xs text-muted-foreground text-center mt-3">
                Faça upload das 2 imagens para habilitar o processamento
              </p>
            )}
          </Card>
        </aside>

        {/* ── Área direita: resultados ── */}
        <main>
          {lastResult ? (
            <ResultPanel result={lastResult} />
          ) : (
            <Card className="flex flex-col items-center justify-center text-center text-muted-foreground py-20">
              <div className="text-6xl mb-4">🐟</div>
              <p className="text-lg font-heading font-semibold text-foreground">Nenhuma análise ainda</p>
              <p className="text-sm mt-2 max-w-sm">
                Faça upload das imagens lateral e superior, informe o fator px/cm
                (ou use o marcador ArUco) e clique em <strong className="text-foreground">▶ Processar</strong>.
              </p>
            </Card>
          )}
        </main>
      </div>
    </div>
  );
}
