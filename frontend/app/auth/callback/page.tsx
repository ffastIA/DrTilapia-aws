// CAMINHO: frontend/app/auth/callback/page.tsx
//
// Landing única para os dois links que o Supabase envia por email:
//  - confirmação de cadastro: #access_token=...&type=signup
//  - redefinição de senha:    #access_token=...&refresh_token=...&type=recovery
//
// O Supabase já confirma/autentica no servidor antes de redirecionar aqui —
// esta página só lê o fragmento da URL (nunca chega ao servidor) e decide
// o que mostrar. Tokens de recovery ficam em estado local do componente,
// nunca em authStore/cookies (não é uma sessão logada real).

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useResetPasswordMutation } from '@/hooks/useResetPasswordMutation';
import Card from '@/components/ui/Card';
import Field, { Input } from '@/components/ui/Field';
import Alert from '@/components/ui/Alert';
import Button from '@/components/Button';

type CallbackState = 'loading' | 'confirmed' | 'recovery' | 'invalid';

export default function AuthCallbackPage() {
  const [state, setState] = useState<CallbackState>('loading');
  const [accessToken, setAccessToken] = useState('');
  const [refreshToken, setRefreshToken] = useState('');

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [validationError, setValidationError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  const resetPasswordMutation = useResetPasswordMutation();

  useEffect(() => {
    const hash = window.location.hash.startsWith('#')
      ? window.location.hash.slice(1)
      : window.location.hash;
    const params = new URLSearchParams(hash);
    const type = params.get('type');
    const token = params.get('access_token');
    const refresh = params.get('refresh_token');

    if (type === 'signup' || type === 'email_change') {
      setState('confirmed');
    } else if (type === 'recovery' && token && refresh) {
      setAccessToken(token);
      setRefreshToken(refresh);
      setState('recovery');
    } else {
      setState('invalid');
    }
  }, []);

  const validateForm = (): boolean => {
    if (!newPassword || newPassword.length < 6) {
      setValidationError('A senha deve ter pelo menos 6 caracteres.');
      return false;
    }
    if (newPassword !== confirmPassword) {
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

    resetPasswordMutation.mutate(
      { access_token: accessToken, refresh_token: refreshToken, new_password: newPassword },
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

      {state === 'loading' && <p className="text-sm text-muted-foreground">Verificando link...</p>}

      {state === 'confirmed' && (
        <>
          <h1 className="font-heading font-semibold text-2xl uppercase m-0 mb-1">Email Confirmado!</h1>
          <p className="text-sm text-muted-foreground mb-2">
            Sua conta foi confirmada com sucesso. Já pode entrar no sistema.
          </p>
        </>
      )}

      {state === 'invalid' && (
        <>
          <h1 className="font-heading font-semibold text-2xl uppercase m-0 mb-1">Link Inválido</h1>
          <p className="text-sm text-muted-foreground mb-2">Este link é inválido ou já expirou.</p>
        </>
      )}

      {state === 'recovery' && !successMessage && (
        <>
          <h1 className="font-heading font-semibold text-2xl uppercase m-0 mb-1">Redefinir Senha</h1>
          <p className="text-sm text-muted-foreground mb-6">Digite sua nova senha</p>
        </>
      )}

      {state === 'recovery' && !successMessage && (
        <form onSubmit={handleSubmit}>
          <Field label="Nova senha" htmlFor="newPassword">
            <Input
              id="newPassword"
              name="newPassword"
              type="password"
              required
              placeholder="Pelo menos 6 caracteres"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              disabled={isSubmitting}
            />
          </Field>
          <Field label="Confirmar nova senha" htmlFor="confirmPassword">
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

          <Button type="submit" variant="primary" disabled={isSubmitting} className="w-full">
            {isSubmitting ? 'Redefinindo...' : 'Redefinir Senha'}
          </Button>
        </form>
      )}

      {successMessage && <Alert variant="success" className="mt-2">{successMessage}</Alert>}

      {(state === 'confirmed' || state === 'invalid' || successMessage) && (
        <div className="mt-6 pt-4 border-t border-border flex flex-col items-center gap-2">
          <Link href="/auth/login" className="text-sm text-primary hover:text-primary-hover">
            Ir para o login
          </Link>
          {state === 'invalid' && (
            <>
              <Link href="/auth/signup" className="text-sm text-primary hover:text-primary-hover">
                Criar uma conta
              </Link>
              <Link href="/auth/forgot-password" className="text-sm text-primary hover:text-primary-hover">
                Pedir novo link de redefinição
              </Link>
            </>
          )}
        </div>
      )}
    </Card>
  );
}
