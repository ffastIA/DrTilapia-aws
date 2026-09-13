// components/Button.tsx
//
// Reimplementação em Tailwind de .btn/.btnPrimary/.btnSecondary/.btnGhost/.btnBlock
// (styles/dr-tilapia.module.css:348-393): raio 0, zero box-shadow, zero transition.
import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md';
  isLoading?: boolean;
  children: React.ReactNode;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      isLoading = false,
      disabled = false,
      children,
      className = '',
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center gap-1.5 font-heading font-semibold uppercase tracking-wide cursor-pointer disabled:opacity-45 disabled:cursor-not-allowed';

    const sizes = {
      sm: 'text-xs px-3 py-1.5',
      md: 'text-sm px-4 py-2',
    };

    const variants = {
      primary: 'bg-primary text-primary-foreground border border-primary hover:bg-primary-hover active:bg-primary-active',
      secondary: 'bg-transparent text-foreground border border-border hover:bg-foreground/[0.07]',
      ghost: 'bg-transparent text-primary border border-transparent hover:bg-primary/10',
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={`${baseStyles} ${sizes[size]} ${variants[variant]} ${className}`}
        {...props}
      >
        {isLoading ? (
          <>
            <div className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
            Carregando...
          </>
        ) : (
          children
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';

export default Button;
