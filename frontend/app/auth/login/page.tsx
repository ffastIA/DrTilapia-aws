// CAMINHO: frontend/app/auth/login/page.tsx

'use client';

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { useLoginMutation } from '@/hooks/useLoginMutation';
import { useResendConfirmationMutation } from '@/hooks/useResendConfirmationMutation';
import { barlow, barlowCondensed } from '@/lib/fonts';
import styles from '@/styles/dr-tilapia.module.css';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [validationError, setValidationError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [showResendConfirmation, setShowResendConfirmation] = useState(false);
  const [resendMessage, setResendMessage] = useState('');

  const router = useRouter();
  const loginMutation = useLoginMutation();
  const resendConfirmationMutation = useResendConfirmationMutation();

  const validateForm = (): boolean => {
    if (!email.trim()) {
      setValidationError('O email é obrigatório.');
      return false;
    }
    if (!password) {
      setValidationError('A senha é obrigatória.');
      return false;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setValidationError('Por favor, insira um email válido.');
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
    setShowResendConfirmation(false);
    setResendMessage('');

    loginMutation.mutate(
      { email: email.trim(), password },
      {
        onSuccess: () => {
          setSuccessMessage('Login realizado com sucesso! Redirecionando...');
          setTimeout(() => {
            router.push('/main/hub');
          }, 2000);
        },
        onError: (error) => {
          setValidationError(error.message);
          setShowResendConfirmation(error.code === 'email_not_confirmed');
        },
        onSettled: () => {
          setIsSubmitting(false);
        },
      }
    );
  };

  const handleResendConfirmation = () => {
    setResendMessage('');
    resendConfirmationMutation.mutate(
      { email: email.trim() },
      {
        onSuccess: (data) => {
          setResendMessage(data.message);
        },
      }
    );
  };

  return (
    <div className={`${barlow.variable} ${barlowCondensed.variable} ${styles.theme} ${styles.authScreen}`}>
      <div className={styles.card}>
        <i className={`${styles.cardCorner} ${styles.cardCornerTl}`} />
        <i className={`${styles.cardCorner} ${styles.cardCornerTr}`} />
        <i className={`${styles.cardCorner} ${styles.cardCornerBl}`} />
        <i className={`${styles.cardCorner} ${styles.cardCornerBr}`} />

        <div className={styles.cardBrand}>
          <Image src="/LogoTAI.jpeg" alt="Dr. Tilap-IA" width={32} height={27} />
          <span>Dr. Tilap-IA</span>
        </div>

        <h1 className={styles.cardTitle}>Entrar no Sistema</h1>
        <p className={styles.cardSub}>Acesse sua conta DrTilápia</p>

        <form onSubmit={handleSubmit}>
          <div className={styles.field}>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              required
              className={styles.input}
              placeholder="Digite seu email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="password">Senha</label>
            <input
              id="password"
              name="password"
              type="password"
              required
              className={styles.input}
              placeholder="Digite sua senha"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isSubmitting}
            />
          </div>

          {validationError && (
            <div className={`${styles.messageBox} ${styles.messageError}`}>
              <p style={{ margin: 0 }}>{validationError}</p>
              {showResendConfirmation && (
                <button
                  type="button"
                  onClick={handleResendConfirmation}
                  disabled={resendConfirmationMutation.isPending}
                  className={`${styles.btn} ${styles.btnGhost}`}
                  style={{ marginTop: 'var(--space-2)', padding: 0 }}
                >
                  {resendConfirmationMutation.isPending ? 'Reenviando...' : 'Reenviar confirmação'}
                </button>
              )}
            </div>
          )}

          {resendMessage && (
            <div className={`${styles.messageBox} ${styles.messageSuccess}`}>{resendMessage}</div>
          )}

          {successMessage && (
            <div className={`${styles.messageBox} ${styles.messageSuccess}`}>{successMessage}</div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className={`${styles.btn} ${styles.btnPrimary} ${styles.btnBlock}`}
          >
            {isSubmitting ? 'Entrando...' : 'Entrar no Sistema'}
          </button>

          <div className={styles.cardFooter}>
            <div className={styles.cardFooterRow}>
              <Link href="/auth/signup" className={styles.btnGhost} style={{ display: 'inline' }}>
                Criar conta
              </Link>
              <Link href="/auth/forgot-password" className={styles.btnGhost} style={{ display: 'inline' }}>
                Esqueci minha senha
              </Link>
            </div>
          </div>
        </form>

        <p className={styles.backLink}>
          <Link href="/">← Voltar ao Início</Link>
        </p>
      </div>
    </div>
  );
}
