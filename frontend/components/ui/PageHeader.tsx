// components/ui/PageHeader.tsx
//
// Reimplementação em Tailwind de .kicker/.captionRule/.splitTitle
// (styles/dr-tilapia.module.css), para o cabeçalho de páginas internas.
import React from 'react';

interface PageHeaderProps {
  kicker?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
}

export default function PageHeader({ kicker, title, description, actions }: PageHeaderProps) {
  return (
    <div className="mb-6">
      {kicker && (
        <span className="block text-xs leading-3 tracking-widest uppercase font-semibold text-primary-active mb-1.5">
          {kicker}
        </span>
      )}
      <hr className="border-0 h-px bg-border mb-3" />
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-heading font-semibold text-2xl uppercase tracking-wide m-0">{title}</h1>
          {description && <p className="text-sm text-muted-foreground mt-1">{description}</p>}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}
