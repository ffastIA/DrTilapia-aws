// components/ui/Alert.tsx
//
// Reimplementação em Tailwind de .messageBox/.messageError/.messageSuccess
// (styles/dr-tilapia.module.css:501-518).
import React from 'react';

interface AlertProps {
  variant: 'error' | 'success';
  children: React.ReactNode;
  className?: string;
}

const VARIANTS = {
  error: 'text-destructive bg-destructive-bg border-destructive/35',
  success: 'text-success bg-success-bg border-success/35',
};

export default function Alert({ variant, children, className = '' }: AlertProps) {
  return (
    <div className={`text-xs p-2.5 mb-3.5 border ${VARIANTS[variant]} ${className}`}>
      {children}
    </div>
  );
}
