// components/ui/BackButton.tsx
//
// handleBack() centralizado — antes duplicado em hub, dashboard, consultoria,
// admin, profile e videos, cada um com um estilo de botão diferente.
'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeftIcon } from 'lucide-react';

export default function BackButton({ fallbackHref = '/main/hub' }: { fallbackHref?: string }) {
  const router = useRouter();

  const handleBack = () => {
    if (window.history.length > 1) {
      router.back();
    } else {
      router.push(fallbackHref);
    }
  };

  return (
    <button
      type="button"
      onClick={handleBack}
      className="inline-flex items-center gap-1.5 text-sm text-foreground hover:text-primary"
    >
      <ArrowLeftIcon className="w-4 h-4" />
      Voltar
    </button>
  );
}
