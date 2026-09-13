'use client';
// CAMINHO: frontend/app/main/images/dashboard/_DashboardPage.tsx

import { useEffect, useState, useCallback } from 'react';
import { listFishAnalyses, listFishImages } from '@/lib/fishImageApi';
import type { FishAnalysisItem, FishImageItem } from '@/types/fishImage';
import PageHeader from '@/components/ui/PageHeader';
import BackButton from '@/components/ui/BackButton';
import Card from '@/components/ui/Card';
import Button from '@/components/Button';

// ── Utilitários ───────────────────────────────────────────────────────────────

function fmt(v: number | null | undefined, d = 4): string {
  if (v == null) return '—';
  return v.toFixed(d);
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(iso));
  } catch {
    return iso;
  }
}

// ── Export para Excel (sem dependência externa) ────────────────────────────────
function exportCsv(filename: string, headers: string[], rows: (string | number | null | undefined)[][]) {
  const bom = '﻿';   // BOM para UTF-8 — Excel reconhece acentos
  const sep = ';';
  const lines = [
    headers.join(sep),
    ...rows.map((r) => r.map((c) => (c == null ? '' : String(c).replace(/;/g, ','))).join(sep)),
  ];
  const blob = new Blob([bom + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Mini gráfico de linha (SVG puro — sem dependência externa) ─────────────────

interface LineChartProps {
  data: { x: string; y: number }[];
  label: string;
}

function LineChart({ data, label }: LineChartProps) {
  if (data.length === 0) return <p className="text-muted-foreground text-sm text-center py-8">Sem dados</p>;

  const W = 320, H = 160, PAD = 32;
  const ys = data.map((d) => d.y);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const rangeY = maxY - minY || 1;

  const toX = (i: number) => PAD + (i / Math.max(data.length - 1, 1)) * (W - PAD * 2);
  const toY = (v: number) => PAD + ((maxY - v) / rangeY) * (H - PAD * 2);

  const points = data.map((d, i) => `${toX(i)},${toY(d.y)}`).join(' ');

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 180 }}>
      {/* Eixos */}
      <line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke="var(--color-border)" strokeWidth="1" />
      <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke="var(--color-border)" strokeWidth="1" />
      {/* Linha */}
      <polyline points={points} fill="none" stroke="var(--color-primary)" strokeWidth="2" strokeLinejoin="round" />
      {/* Pontos */}
      {data.map((d, i) => (
        <circle key={i} cx={toX(i)} cy={toY(d.y)} r="3" fill="var(--color-primary)">
          <title>{`${d.x}: ${d.y.toFixed(4)}`}</title>
        </circle>
      ))}
      {/* Labels eixo Y */}
      <text x={PAD - 4} y={PAD + 4} textAnchor="end" fontSize="9" fill="var(--color-muted-foreground)">{maxY.toFixed(2)}</text>
      <text x={PAD - 4} y={H - PAD + 4} textAnchor="end" fontSize="9" fill="var(--color-muted-foreground)">{minY.toFixed(2)}</text>
      {/* Título */}
      <text x={W / 2} y={12} textAnchor="middle" fontSize="10" fill="var(--color-muted-foreground)">{label}</text>
    </svg>
  );
}

// ── Componente de dashboard individual ────────────────────────────────────────

interface DashboardPanelProps {
  title: string;
  headers: string[];
  rows: (string | number | null | undefined)[][];
  chartData: { x: string; y: number }[];
  chartLabel: string;
  isLoading: boolean;
  exportFilename: string;
}

function DashboardPanel({
  title, headers, rows, chartData, chartLabel, isLoading, exportFilename,
}: DashboardPanelProps) {
  return (
    <Card className="p-0 overflow-hidden">
      <div className="px-4 py-3 flex items-center justify-between border-b border-border bg-surface">
        <h2 className="font-heading font-semibold uppercase">{title}</h2>
        <button
          onClick={() => exportCsv(exportFilename, headers, rows)}
          className="text-xs border border-border px-3 py-1 hover:bg-primary/10"
        >
          ⬇ Exportar CSV
        </button>
      </div>

      {isLoading ? (
        <div className="p-8 text-center text-muted-foreground">Carregando…</div>
      ) : rows.length === 0 ? (
        <div className="p-8 text-center text-muted-foreground">Nenhum dado disponível</div>
      ) : (
        <div className="flex flex-col md:flex-row">
          {/* Tabela */}
          <div className="flex-1 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface">
                <tr>
                  {headers.map((h) => (
                    <th key={h} className="text-left px-3 py-2 text-muted-foreground font-medium text-xs whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((row, i) => (
                  <tr key={i} className="hover:bg-surface">
                    {row.map((cell, j) => (
                      <td key={j} className="px-3 py-2 text-foreground text-xs whitespace-nowrap">
                        {cell == null ? '—' : String(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Gráfico */}
          <div className="w-full md:w-72 p-4 border-t md:border-t-0 md:border-l border-border">
            <LineChart data={chartData} label={chartLabel} />
          </div>
        </div>
      )}
    </Card>
  );
}

// ── Página de dashboards ──────────────────────────────────────────────────────

export default function DashboardPage() {
  const [analyses, setAnalyses] = useState<FishAnalysisItem[]>([]);
  const [lateralImgs, setLateralImgs] = useState<FishImageItem[]>([]);
  const [superiorImgs, setSuperiorImgs] = useState<FishImageItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [analysesData, lateralData, superiorData] = await Promise.all([
        listFishAnalyses(),
        listFishImages({ tag: 'lateral' }),
        listFishImages({ tag: 'superior' }),
      ]);
      setAnalyses(analysesData.items);
      setLateralImgs(lateralData.items.filter((i) => i.processing_status === 'done'));
      setSuperiorImgs(superiorData.items.filter((i) => i.processing_status === 'done'));
    } catch (e) {
      console.error('Erro ao carregar dashboards', e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // ── KVol ──────────────────────────────────────────────────────────────────
  const kvolRows = analyses
    .filter((a) => a.kvol != null)
    .map((a) => [
      formatDate(a.created_at),
      fmt(a.kvol, 6),
      fmt(a.comprimento_cm),
      fmt(a.altura_cm),
      fmt(a.largura_cm),
      fmt(a.peso_g, 1),
    ]);

  const kvolChart = analyses
    .filter((a) => a.kvol != null)
    .reverse()
    .map((a) => ({ x: formatDate(a.created_at), y: a.kvol as number }));

  // ── Comprimento (lateral) ─────────────────────────────────────────────────
  const comprRows = lateralImgs
    .filter((i) => i.bbox_width_cm != null)
    .map((i) => [formatDate(i.uploaded_at), fmt(i.bbox_width_cm), fmt(i.bbox_width_px, 0), fmt(i.fator_conversao)]);

  const comprChart = [...comprRows].reverse().map((r, idx) => ({
    x: String(r[0]),
    y: parseFloat(String(comprRows[comprRows.length - 1 - idx]?.[1]) || '0') || 0,
  }));

  // ── Altura (lateral) ──────────────────────────────────────────────────────
  const altRows = lateralImgs
    .filter((i) => i.bbox_height_cm != null)
    .map((i) => [formatDate(i.uploaded_at), fmt(i.bbox_height_cm), fmt(i.bbox_height_px, 0), fmt(i.fator_conversao)]);

  const altChart = lateralImgs
    .filter((i) => i.bbox_height_cm != null)
    .reverse()
    .map((i) => ({ x: formatDate(i.uploaded_at), y: i.bbox_height_cm as number }));

  // ── Largura (superior) ────────────────────────────────────────────────────
  const largRows = superiorImgs
    .filter((i) => i.bbox_height_cm != null)
    .map((i) => [formatDate(i.uploaded_at), fmt(i.bbox_height_cm), fmt(i.bbox_height_px, 0), fmt(i.fator_conversao)]);

  const largChart = superiorImgs
    .filter((i) => i.bbox_height_cm != null)
    .reverse()
    .map((i) => ({ x: formatDate(i.uploaded_at), y: i.bbox_height_cm as number }));

  return (
    <div>
      <PageHeader
        kicker="Biometria"
        title="Dashboards Biométricos"
        actions={
          <>
            <Button onClick={loadData} variant="secondary" size="sm">↺ Atualizar</Button>
            <BackButton />
          </>
        }
      />

      <div className="space-y-6">
        {/* KVol */}
        <DashboardPanel
          title="Kvol — Índice Volumétrico"
          headers={['Data', 'Kvol', 'Compr. (cm)', 'Altura (cm)', 'Largura (cm)', 'Peso (g)']}
          rows={kvolRows}
          chartData={kvolChart}
          chartLabel="Evolução do Kvol"
          isLoading={isLoading}
          exportFilename="kvol.csv"
        />

        {/* Comprimento */}
        <DashboardPanel
          title="Comprimento — Imagens Laterais"
          headers={['Data', 'Comprimento (cm)', 'Comprimento (px)', 'Fator px/cm']}
          rows={comprRows}
          chartData={comprChart}
          chartLabel="Evolução do Comprimento"
          isLoading={isLoading}
          exportFilename="comprimento.csv"
        />

        {/* Altura */}
        <DashboardPanel
          title="Altura — Imagens Laterais"
          headers={['Data', 'Altura (cm)', 'Altura (px)', 'Fator px/cm']}
          rows={altRows}
          chartData={altChart}
          chartLabel="Evolução da Altura"
          isLoading={isLoading}
          exportFilename="altura.csv"
        />

        {/* Largura */}
        <DashboardPanel
          title="Largura — Imagens Superiores"
          headers={['Data', 'Largura (cm)', 'Largura (px)', 'Fator px/cm']}
          rows={largRows}
          chartData={largChart}
          chartLabel="Evolução da Largura"
          isLoading={isLoading}
          exportFilename="largura.csv"
        />
      </div>
    </div>
  );
}
