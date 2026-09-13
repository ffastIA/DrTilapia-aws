// CAMINHO: frontend/app/main/admin/page.tsx

'use client';

import { ChangeEvent, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import useRagAdmin from '@/hooks/useRagAdmin';
import PageHeader from '@/components/ui/PageHeader';
import BackButton from '@/components/ui/BackButton';
import Card from '@/components/ui/Card';
import Alert from '@/components/ui/Alert';
import Button from '@/components/Button';
import Modal from '@/components/ui/Modal';

function formatDate(value: Date | null | undefined, hasValid?: boolean): string {
  if (hasValid === false || !value || isNaN(value.getTime())) {
    return 'Data indisponível';
  }
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(value);
}

function getChunks(metadata?: Record<string, any>): number {
  return Number(metadata?.total_chunks ?? metadata?.active_chunks ?? 0);
}

function safeSource(item: any): string {
  const source = item.metadata?.source || item.title;
  if (source.includes('AppData') || source.includes('Temp') || source.includes('tmp')) {
    return item.title;
  }
  return source;
}

export default function AdminPage() {
  const router  = useRouter();
  const user    = useAuthStore((state) => state.user);
  const loading = useAuthStore((state) => state.isLoading);

  // Defesa em profundidade: redireciona no cliente mesmo se o middleware falhar
  useEffect(() => {
    if (!loading && user && user.role !== 'admin') {
      router.replace('/main/hub');
    }
  }, [user, loading, router]);

  // Aguarda carregamento da sessão; middleware já bloqueou antes do JS rodar
  if (loading || !user || user.role !== 'admin') return null;

  const {
    items,
    isLoadingList,
    isUploading,
    isDeleting,
    isClearing,
    selectedItem,
    isDeleteModalOpen,
    operationMessage,
    operationError,
    refreshList,
    uploadFiles,
    openDeleteModal,
    closeDeleteModal,
    deleteSelectedItem,
    clearDatabase,
    resetFeedback,
  } = useRagAdmin();

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      uploadFiles(files);
      e.target.value = '';
    }
  };

  const handleClear = () => {
    if (window.confirm('Tem certeza que deseja limpar DEFINITIVAMENTE todos os documentos da base RAG? Esta ação é irreversível.')) {
      clearDatabase(true);
    }
  };

  return (
    <div>
      <PageHeader kicker="Base de conhecimento" title="Administração RAG" actions={<BackButton />} />

      {operationMessage && (
        <Alert variant="success" className="relative pr-10">
          {operationMessage}
          <button onClick={resetFeedback} className="absolute top-2 right-2.5 text-lg leading-none">
            ×
          </button>
        </Alert>
      )}
      {operationError?.message && (
        <Alert variant="error" className="relative pr-10">
          {operationError.message}
          <button onClick={resetFeedback} className="absolute top-2 right-2.5 text-lg leading-none">
            ×
          </button>
        </Alert>
      )}

      <Card className="mb-6">
        <h2 className="font-heading font-semibold uppercase mb-4">Upload de PDFs</h2>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          multiple
          onChange={handleUpload}
          className="hidden"
        />
        <Button onClick={() => fileInputRef.current?.click()} disabled={isUploading} variant="primary">
          {isUploading ? 'Enviando...' : 'Selecionar PDFs'}
        </Button>
      </Card>

      <div className="flex flex-wrap gap-3 mb-6">
        <Button onClick={refreshList} disabled={isLoadingList} variant="secondary">
          {isLoadingList ? 'Atualizando...' : 'Atualizar Lista'}
        </Button>
        <Button onClick={handleClear} disabled={isClearing} variant="secondary" className="!text-destructive !border-destructive/40 hover:!bg-destructive-bg">
          {isClearing ? 'Limpando...' : 'Limpeza Definitiva'}
        </Button>
      </div>

      <Card className="p-0 overflow-hidden">
        {isLoadingList ? (
          <div className="p-12 text-center text-muted-foreground">Carregando lista...</div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground">Nenhum documento indexado no momento.</div>
        ) : (
          <div className="divide-y divide-border">
            {items.map((item) => (
              <div key={item.id} className="p-6">
                <div className="flex justify-between items-start mb-4 gap-4">
                  <h3 className="font-heading font-semibold flex-1 truncate">{item.title}</h3>
                  <Button onClick={() => openDeleteModal(item)} disabled={isDeleting} variant="secondary" size="sm" className="!text-destructive !border-destructive/40 hover:!bg-destructive-bg">
                    Excluir
                  </Button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-muted-foreground">
                  <p><strong className="text-foreground">ID:</strong> {item.id}</p>
                  <p><strong className="text-foreground">Inserido em:</strong> {formatDate(item.createdAt, item.metadata?.hasValidCreatedAt)}</p>
                  <p><strong className="text-foreground">Atualizado em:</strong> {formatDate(item.updatedAt, item.metadata?.hasValidUpdatedAt)}</p>
                  <p><strong className="text-foreground">Source:</strong> {safeSource(item)}</p>
                  <p className="md:col-span-2"><strong className="text-foreground">Chunks:</strong> {getChunks(item.metadata)}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Modal open={isDeleteModalOpen && !!selectedItem} onClose={closeDeleteModal} title="Confirmar Exclusão">
        <p className="text-foreground mb-6">
          Deseja excluir o documento <strong>{selectedItem?.title}</strong> permanentemente?
        </p>
        <div className="flex justify-end gap-3">
          <Button onClick={closeDeleteModal} variant="secondary">
            Cancelar
          </Button>
          <Button onClick={deleteSelectedItem} disabled={isDeleting} variant="primary" className="!bg-destructive !border-destructive hover:!bg-destructive/90">
            {isDeleting ? 'Excluindo...' : 'Excluir'}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
