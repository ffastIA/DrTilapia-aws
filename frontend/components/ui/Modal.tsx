// components/ui/Modal.tsx
//
// Overlay + painel baseado em .card (styles/dr-tilapia.module.css:434-441):
// raio 0, zero box-shadow, borda hairline. Usado pelos modais de vídeo e admin.
import React from 'react';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export default function Modal({ open, onClose, title, children, className = '' }: ModalProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 p-4"
      onClick={onClose}
    >
      <div
        className={`relative w-full max-w-lg max-h-[85vh] overflow-y-auto bg-card border border-border p-6 ${className}`}
        onClick={(e) => e.stopPropagation()}
      >
        {title && (
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-heading font-semibold text-lg uppercase tracking-wide m-0">{title}</h2>
            <button
              type="button"
              onClick={onClose}
              aria-label="Fechar"
              className="text-muted-foreground hover:text-foreground text-xl leading-none"
            >
              ×
            </button>
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
