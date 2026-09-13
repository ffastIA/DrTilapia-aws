// CAMINHO: frontend/app/auth/forgot-password/page.tsx

'use client';

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useForgotPasswordMutation } from '@/hooks/useForgotPasswordMutation';
import { barlow, barlowCondensed } from '@/lib/fonts';
import styles from '@/styles/dr-tilapia.module.css';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [validationError, setValidationError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  const forgotPasswordMutation = useForgotPasswordMutation();

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
    setValidationError('');
    return true;
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!validateForm()) return;

    setIsSubmitting(true);
    setValidationError('');
    setSuccessMessage('');

    forgotPasswordMutation.mutate(
      { email: email.trim() },
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

        <h1 className={styles.cardTitle}>Esqueci Minha Senha</h1>
        <p className={styles.cardSub}>Informe seu email para receber um link de redefinição</p>

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

          {validationError && (
            <div className={`${styles.messageBox} ${styles.messageError}`}>{validationError}</div>
          )}

          {successMessage && (
            <div className={`${styles.messageBox} ${styles.messageSuccess}`}>{successMessage}</div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className={`${styles.btn} ${styles.btnPrimary} ${styles.btnBlock}`}
          >
            {isSubmitting ? 'Enviando...' : 'Enviar link de redefinição'}
          </button>

          <div className={styles.cardFooter}>
            <p className={styles.backLink} style={{ margin: 0 }}>
              Lembrou sua senha? <Link href="/auth/login">Entrar</Link>
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}
