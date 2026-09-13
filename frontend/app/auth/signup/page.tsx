// CAMINHO: frontend/app/auth/signup/page.tsx

'use client';

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useSignupMutation } from '@/hooks/useSignupMutation';
import Card from '@/components/ui/Card';
import Field, { Input } from '@/components/ui/Field';
import Alert from '@/components/ui/Alert';
import Button from '@/components/Button';

export default function SignupPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [validationError, setValidationError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  const signupMutation = useSignupMutation();

  const validateForm = (): boolean => {
    if (!email.trim()) {
      setValidationError('O email é obrigatório.');
      return false;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setValidationError('Por favor, insira um email válido.');
      return false;
    }
    if (!password || password.length < 6) {
      setValidationError('A senha deve ter pelo menos 6 caracteres.');
      return false;
    }
    if (password !== confirmPassword) {
      setValidationError('As senhas não coincidem.');
      return false;
    }
    setValidationError('');
    return true;
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!validateForm()) return;

    setIsSubmitting(true);
    setValidationError('');
    setSuccessMessage('');

    signupMutation.mutate(
      { email: email.trim(), password },
      {
        onSuccess: (data) => {
          setSuccessMessage(data.message);
        },
        onError: (error) => {
          setValidationError(error.message);
        },
        onSettled: () => {
          setIsSubmitting(false);
        },
      }
    );
  };

  return (
    <Card corners className="w-full max-w-md p-8">
      <div className="flex items-center gap-2 mb-6">
        <Image src="/LogoTAI.jpeg" alt="Dr. Tilap-IA" width={32} height={27} />
        <span className="font-heading font-semibold text-xl uppercase">Dr. Tilap-IA</span>
      </div>

      <h1 className="font-heading font-semibold text-2xl uppercase m-0 mb-1">Criar Conta</h1>
      <p className="text-sm text-muted-foreground mb-6">Cadastre-se no DrTilápia</p>

      <form onSubmit={handleSubmit}>
        <Field label="Email" htmlFor="email">
          <Input
            id="email"
            name="email"
            type="email"
            required
            placeholder="Digite seu email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={isSubmitting}
          />
        </Field>
        <Field label="Senha" htmlFor="password">
          <Input
            id="password"
            name="password"
            type="password"
            required
            placeholder="Pelo menos 6 caracteres"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={isSubmitting}
          />
        </Field>
        <Field label="Confirmar senha" htmlFor="confirmPassword">
          <Input
            id="confirmPassword"
            name="confirmPassword"
            type="password"
            required
            placeholder="Digite a senha novamente"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            disabled={isSubmitting}
          />
        </Field>

        {validationError && <Alert variant="error">{validationError}</Alert>}
        {successMessage && <Alert variant="success">{successMessage}</Alert>}

        <Button type="submit" variant="primary" disabled={isSubmitting} className="w-full">
          {isSubmitting ? 'Criando conta...' : 'Criar Conta'}
        </Button>
      </form>

      <div className="mt-6 pt-4 border-t border-border text-center">
        <Link href="/auth/login" className="text-sm text-primary hover:text-primary-hover">
          Já tem conta? Entrar
        </Link>
      </div>
    </Card>
  );
}
