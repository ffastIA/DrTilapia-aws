// components/ui/Field.tsx
//
// Reimplementação em Tailwind de .field/.input (styles/dr-tilapia.module.css:396-422):
// raio 0, fundo surface, borda hairline, foco com anel accent.
import React from 'react';

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className = '', ...props }, ref) => (
    <input
      ref={ref}
      className={`w-full min-h-[40px] px-2.5 py-2 text-sm bg-surface text-foreground border border-border placeholder:text-muted-foreground hover:border-foreground/45 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary focus-visible:border-primary disabled:opacity-60 ${className}`}
      {...props}
    />
  )
);
Input.displayName = 'Input';

interface FieldProps {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}

export default function Field({ label, htmlFor, children }: FieldProps) {
  return (
    <div className="block mb-3.5">
      <label htmlFor={htmlFor} className="block text-xs mb-1 text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  );
}
