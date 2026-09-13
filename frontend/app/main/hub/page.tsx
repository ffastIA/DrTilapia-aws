'use client';

import React from 'react';
import Link from 'next/link';
import { MessageSquareTextIcon, UploadCloudIcon, BarChart2Icon, UserIcon, VideoIcon, ScanSearchIcon } from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { useRouter } from 'next/navigation';
import Card from '@/components/ui/Card';
import CornerMarks from '@/components/ui/CornerMarks';
import { useProfile } from '@/hooks/useProfile';

const FeatureCard: React.FC<{
  icon: React.ElementType;
  title: string;
  description: string;
  href: string;
  disabled?: boolean;
}> = ({ icon: Icon, title, description, href, disabled }) => (
  <Link href={href} className={`block h-full ${disabled ? 'pointer-events-none opacity-50' : ''}`}>
    <Card corners className="flex flex-col items-center text-center h-full hover:bg-surface">
      <CornerMarks />
      <Icon size={40} className="text-primary mb-4" />
      <h3 className="font-heading font-semibold text-lg uppercase mb-2">{title}</h3>
      <p className="text-muted-foreground text-sm">{description}</p>
    </Card>
  </Link>
);

export default function HubPage() {
  const user = useAuthStore((state) => state.user);
  const clearAuth = useAuthStore((state) => state.clearAuth);
  const isAdmin = user?.role === 'admin';
  const router = useRouter();
  // Só para popular user.name a partir do perfil (efeito colateral em setUserName);
  // a página não usa `profile` diretamente.
  useProfile();

  const handleLogout = () => {
    clearAuth();
    router.replace('/');
  };

  return (
    <div>
      <div className="flex justify-between items-start mb-8">
        <div>
          <h1 className="font-heading font-semibold text-3xl uppercase mb-2">Bem-vindo, {user?.name || user?.email}!</h1>
          <p className="text-muted-foreground">
            Explore as funcionalidades do Dr. Tilápia, seu assistente de IA para piscicultura.
          </p>
        </div>
        <button
          onClick={handleLogout}
          className="text-sm font-heading font-semibold uppercase text-destructive border border-destructive/35 px-4 py-2 hover:bg-destructive-bg"
        >
          Sair
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <FeatureCard
          icon={MessageSquareTextIcon}
          title="Consultoria de IA"
          description="Obtenha respostas instantâneas e insights especializados sobre piscicultura."
          href="/main/consultoria"
        />

        <FeatureCard
          icon={BarChart2Icon}
          title="Dashboard de Métricas"
          description="Visualize dados e métricas importantes para otimizar sua produção."
          href="/main/dashboard"
        />

        {isAdmin ? (
          <FeatureCard
            icon={UploadCloudIcon}
            title="Administração RAG"
            description="Gerencie e faça upload de documentos para a base de conhecimento da IA."
            href="/main/admin"
          />
        ) : (
          <FeatureCard
            icon={UploadCloudIcon}
            title="Administração RAG"
            description="Funcionalidade exclusiva para administradores."
            href="#"
            disabled
          />
        )}

        <FeatureCard
          icon={VideoIcon}
          title="Biblioteca de Vídeos"
          description="Acesse nossa galeria de vídeos instrutivos e tutoriais sobre piscicultura."
          href="/main/videos"
        />

        <FeatureCard
          icon={ScanSearchIcon}
          title="Análise de Imagens por IA"
          description="Faça upload de imagens do peixe para calcular biometria, Kvol e acompanhar a evolução do plantel."
          href="/main/images"
        />

        <FeatureCard
          icon={UserIcon}
          title="Meu Perfil"
          description="Visualize e edite suas informações de usuário e preferências."
          href="/main/profile"
        />
      </div>

      <div className="mt-12">
        <h2 className="font-heading font-semibold text-xl uppercase mb-4">Atividades Recentes</h2>
        <Card>
          <p className="text-muted-foreground">Nenhuma atividade recente para exibir.</p>
        </Card>
      </div>
    </div>
  );
}
