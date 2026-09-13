// CAMINHO: frontend/app/main/dashboard/page.tsx

'use client';

import useAuth from '@/hooks/useAuth';
import PageHeader from '@/components/ui/PageHeader';
import BackButton from '@/components/ui/BackButton';
import Card from '@/components/ui/Card';

export default function Dashboard() {
  const { user } = useAuth();

  return (
    <div>
      <PageHeader
        kicker="Painel de controle"
        title="Dashboard"
        description="Acompanhe métricas e estatísticas em tempo real do seu painel de controle DrTilápia."
        actions={<BackButton />}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10">
        <Card>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">
            Usuário Logado
          </h2>
          <p className="text-xl font-heading font-semibold text-foreground break-all">
            {user?.email || 'N/A'}
          </p>
        </Card>

        <Card>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">Status</h2>
          <p className="text-xl font-heading font-semibold text-success">Online</p>
        </Card>

        <Card>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">
            Permissão
          </h2>
          <p className="text-xl font-heading font-semibold text-primary capitalize">
            {user?.role || 'N/A'}
          </p>
        </Card>
      </div>

      <Card className="text-center py-12">
        <h2 className="font-heading font-semibold text-xl uppercase mb-4">Em Desenvolvimento</h2>
        <p className="text-muted-foreground max-w-2xl mx-auto leading-relaxed">
          Esta dashboard está em fase de desenvolvimento ativo. Novas funcionalidades, gráficos
          interativos, relatórios avançados e integrações serão adicionadas em breve para elevar sua
          experiência!
        </p>
      </Card>
    </div>
  );
}
