'use client';

import { ChangeEvent, useRef, useState } from 'react';
import { useAuthStore } from '@/store/authStore';
import useVideos from '@/hooks/useVideos';
import useVideoAdmin from '@/hooks/useVideoAdmin';
import type { VideoItem } from '@/types/video';
import PageHeader from '@/components/ui/PageHeader';
import BackButton from '@/components/ui/BackButton';
import Card from '@/components/ui/Card';
import Field, { Input } from '@/components/ui/Field';
import Alert from '@/components/ui/Alert';
import Button from '@/components/Button';
import Modal from '@/components/ui/Modal';

// ── Categorias ────────────────────────────────────────────────────────────────

const VIDEO_CATEGORIES = [
  { value: 'geral',        label: 'Geral'        },
  { value: 'nutricao',     label: 'Nutrição'      },
  { value: 'genetica',     label: 'Genética'      },
  { value: 'manejo',       label: 'Manejo'        },
  { value: 'sanidade',     label: 'Sanidade'      },
  { value: 'pos-colheita', label: 'Pós-colheita'  },
] as const;

type CategoryValue = typeof VIDEO_CATEGORIES[number]['value'];

// ── Rótulo por categoria — o design é mono-accent (sem gradiente por cor),
// então cada categoria só varia o texto do badge, não a cor. ──────────────────

const CATEGORY_LABEL: Record<string, string> = {
  geral:          'Geral',
  nutricao:       'Nutrição',
  genetica:       'Genética',
  manejo:         'Manejo',
  sanidade:       'Sanidade',
  'pos-colheita': 'Pós-colheita',
};

function getLabel(category: string): string {
  return CATEGORY_LABEL[category] ?? CATEGORY_LABEL['geral'];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatSize(bytes?: number | null): string {
  if (!bytes) return '';
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

// ── Componente ────────────────────────────────────────────────────────────────

export default function VideosPage() {
  const user    = useAuthStore((state) => state.user);
  const isAdmin = user?.role === 'admin';

  // Data & operations
  const { videos, isLoading, error: listError, refresh } = useVideos();
  const {
    isUploading,
    isDeleting,
    feedback,
    error: adminError,
    uploadVideo,
    deleteVideo,
    resetFeedback,
  } = useVideoAdmin(refresh);

  // Player
  const [selectedVideo, setSelectedVideo] = useState<VideoItem | null>(null);

  // Upload modal
  const [showUpload,     setShowUpload]     = useState(false);
  const [uploadTitle,    setUploadTitle]    = useState('');
  const [uploadDesc,     setUploadDesc]     = useState('');
  const [uploadCategory, setUploadCategory] = useState<CategoryValue>('geral');
  const [uploadFile,     setUploadFile]     = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // ── Handlers ───────────────────────────────────────────────────────────────

  function resetForm() {
    setUploadTitle('');
    setUploadDesc('');
    setUploadCategory('geral');
    setUploadFile(null);
    if (fileRef.current) fileRef.current.value = '';
  }

  function openUpload() {
    resetFeedback();
    setShowUpload(true);
  }

  function closeUpload() {
    setShowUpload(false);
    resetForm();
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    setUploadFile(e.target.files?.[0] ?? null);
  }

  async function handleUploadSubmit() {
    if (!uploadFile || !uploadTitle.trim()) return;
    const ok = await uploadVideo(uploadFile, uploadTitle.trim(), uploadDesc, uploadCategory);
    if (ok) closeUpload();
  }

  async function handleDelete(video: VideoItem) {
    if (!window.confirm(`Excluir "${video.title}" permanentemente? Esta ação não pode ser desfeita.`)) return;
    await deleteVideo(video.id);
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div>
      <PageHeader
        kicker="Biblioteca"
        title="Biblioteca de Vídeos"
        actions={
          <>
            {isAdmin && (
              <Button onClick={openUpload} variant="primary" size="sm">
                + Enviar Vídeo
              </Button>
            )}
            <BackButton />
          </>
        }
      />

      {/* Feedback (admin) */}
      {feedback && (
        <Alert variant="success" className="relative pr-10">
          {feedback}
          <button onClick={resetFeedback} className="absolute top-2 right-2.5 text-lg leading-none">×</button>
        </Alert>
      )}
      {adminError?.message && (
        <Alert variant="error" className="relative pr-10">
          {adminError.message}
          <button onClick={resetFeedback} className="absolute top-2 right-2.5 text-lg leading-none">×</button>
        </Alert>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex justify-center items-center py-28">
          <div className="animate-spin rounded-full h-14 w-14 border-b-2 border-primary border-t-transparent" />
        </div>
      )}

      {/* Erro de listagem */}
      {!isLoading && listError && (
        <div className="text-center py-28">
          <p className="text-destructive text-lg mb-6">{listError.message}</p>
          <Button onClick={() => void refresh()} variant="secondary">
            Tentar novamente
          </Button>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !listError && videos.length === 0 && (
        <div className="text-center py-28">
          <div className="text-6xl mb-6">🎬</div>
          <p className="text-muted-foreground text-xl font-heading font-semibold mb-2">Nenhum vídeo disponível</p>
          {isAdmin && (
            <p className="text-muted-foreground text-sm">
              Clique em <span className="text-primary font-semibold">+ Enviar Vídeo</span> para adicionar o primeiro.
            </p>
          )}
        </div>
      )}

      {/* Grid */}
      {!isLoading && !listError && videos.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {videos.map((video) => {
            const hasUrl = Boolean(video.url);
            return (
              <Card key={video.id} className="p-0 overflow-hidden flex flex-col">
                {/* Thumbnail */}
                <div className="relative h-44 bg-surface flex items-center justify-center border-b border-border">
                  <button
                    onClick={() => { if (hasUrl) setSelectedVideo(video); }}
                    disabled={!hasUrl}
                    className="w-16 h-16 bg-primary/10 hover:bg-primary/20 disabled:opacity-30 disabled:cursor-not-allowed border border-primary/40 flex items-center justify-center"
                    title={hasUrl ? 'Assistir' : 'URL indisponível'}
                  >
                    <span className="text-3xl ml-1 text-primary">▶</span>
                  </button>
                  {video.file_size ? (
                    <span className="absolute bottom-2 right-2 text-xs bg-foreground/70 text-background px-2 py-0.5">
                      {formatSize(video.file_size)}
                    </span>
                  ) : null}
                </div>

                {/* Body */}
                <div className="p-5 flex flex-col flex-1">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <h3 className="font-heading font-semibold text-base leading-snug flex-1">
                      {video.title}
                    </h3>
                    <span className="text-xs px-2 py-1 border border-border font-medium whitespace-nowrap text-muted-foreground">
                      {getLabel(video.category)}
                    </span>
                  </div>

                  {video.description ? (
                    <p className="text-muted-foreground text-sm leading-relaxed mb-3 line-clamp-2">
                      {video.description}
                    </p>
                  ) : null}

                  <div className="mt-auto pt-3 flex items-center gap-2">
                    <Button
                      onClick={() => { if (hasUrl) setSelectedVideo(video); }}
                      disabled={!hasUrl}
                      variant="secondary"
                      className="flex-1"
                    >
                      ▶ Assistir
                    </Button>
                    {isAdmin && (
                      <button
                        onClick={() => void handleDelete(video)}
                        disabled={isDeleting}
                        className="p-2 border border-destructive/40 hover:bg-destructive-bg disabled:opacity-40 disabled:cursor-not-allowed text-destructive text-sm"
                        title="Excluir vídeo"
                      >
                        🗑
                      </button>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Modal: Player */}
      <Modal open={selectedVideo !== null} onClose={() => setSelectedVideo(null)} className="max-w-4xl p-0">
        {selectedVideo && (
          <>
            <div className="flex items-center justify-between px-5 py-4 border-b border-border gap-4">
              <div className="flex-1 min-w-0">
                <h3 className="font-heading font-semibold text-lg truncate">{selectedVideo.title}</h3>
                <span className="inline-block text-xs px-2 py-0.5 border border-border mt-1 text-muted-foreground">
                  {getLabel(selectedVideo.category)}
                </span>
              </div>
              <button
                onClick={() => setSelectedVideo(null)}
                className="text-muted-foreground hover:text-foreground text-3xl font-light w-10 h-10 flex items-center justify-center shrink-0"
              >
                ×
              </button>
            </div>

            {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
            <video
              src={selectedVideo.url}
              controls
              autoPlay
              className="w-full max-h-[65vh] bg-foreground"
            />

            {selectedVideo.description ? (
              <p className="px-5 py-3 text-muted-foreground text-sm border-t border-border">
                {selectedVideo.description}
              </p>
            ) : null}
          </>
        )}
      </Modal>

      {/* Modal: Upload (admin) */}
      <Modal open={showUpload && isAdmin} onClose={closeUpload} title="Enviar Vídeo">
        {adminError?.message && <Alert variant="error">{adminError.message}</Alert>}

        <Field label="Título *" htmlFor="video-title">
          <Input
            id="video-title"
            type="text"
            value={uploadTitle}
            onChange={(e) => setUploadTitle(e.target.value)}
            maxLength={120}
            placeholder="Nome descritivo do vídeo"
          />
        </Field>

        <Field label="Descrição" htmlFor="video-desc">
          <textarea
            id="video-desc"
            value={uploadDesc}
            onChange={(e) => setUploadDesc(e.target.value)}
            maxLength={400}
            rows={3}
            placeholder="Descrição breve (opcional)"
            className="w-full px-2.5 py-2 text-sm bg-surface text-foreground border border-border placeholder:text-muted-foreground hover:border-foreground/45 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary focus-visible:border-primary resize-none"
          />
        </Field>

        <Field label="Categoria" htmlFor="video-category">
          <select
            id="video-category"
            value={uploadCategory}
            onChange={(e) => setUploadCategory(e.target.value as CategoryValue)}
            className="w-full px-2.5 py-2 text-sm bg-surface text-foreground border border-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary focus-visible:border-primary cursor-pointer"
          >
            {VIDEO_CATEGORIES.map((cat) => (
              <option key={cat.value} value={cat.value}>{cat.label}</option>
            ))}
          </select>
        </Field>

        <Field label="Arquivo * (MP4, WebM, MOV)" htmlFor="video-file">
          <input
            ref={fileRef}
            id="video-file"
            type="file"
            accept=".mp4,.webm,.mov,video/mp4,video/webm,video/quicktime"
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="w-full py-2 px-3 bg-surface border border-dashed border-border text-sm text-left hover:bg-primary/5"
          >
            {uploadFile ? (
              <span className="text-success">
                ✓ {uploadFile.name} <span className="font-normal">({formatSize(uploadFile.size)})</span>
              </span>
            ) : (
              <span className="text-muted-foreground">Clique para selecionar o arquivo...</span>
            )}
          </button>
        </Field>

        <Button
          onClick={() => void handleUploadSubmit()}
          disabled={isUploading || !uploadFile || !uploadTitle.trim()}
          variant="primary"
          className="w-full"
        >
          {isUploading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-current border-t-transparent" />
              Enviando...
            </span>
          ) : (
            'Enviar Vídeo'
          )}
        </Button>
      </Modal>
    </div>
  );
}
