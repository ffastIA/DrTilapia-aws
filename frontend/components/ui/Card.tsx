// components/ui/Card.tsx
//
// Reimplementação em Tailwind de .card/.cellFrame (styles/dr-tilapia.module.css:207-228,434-441):
// superfície plana, borda hairline de 1px, raio 0, zero box-shadow.
import React from 'react';
import CornerMarks from './CornerMarks';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  corners?: boolean;
  children: React.ReactNode;
}

export default function Card({ corners = false, children, className = '', ...props }: CardProps) {
  return (
    <div className={`relative border border-border bg-card p-6 ${className}`} {...props}>
      {corners && <CornerMarks />}
      {children}
    </div>
  );
}
