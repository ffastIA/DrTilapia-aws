// CAMINHO: frontend/app/main/layout.tsx
//
// Shell compartilhado por toda a área autenticada (/main/*): nav com a marca
// e o wrapper de largura máxima da identidade Dr. Tilap-IA. O botão "Voltar"
// (components/ui/BackButton) fica a critério de cada página — o hub, por ser
// a raiz de /main/*, não usa um.
import Link from 'next/link';
import Image from 'next/image';

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <nav className="flex items-center gap-4 px-edge py-3 border-b border-border">
        <Link href="/main/hub" className="inline-flex items-center gap-2 font-heading font-semibold text-lg uppercase">
          <Image src="/LogoTAI.jpeg" alt="Dr. Tilap-IA" width={28} height={23} />
          Dr. Tilap-IA
        </Link>
      </nav>
      <main className="max-w-wrap mx-auto px-edge py-8">{children}</main>
    </div>
  );
}
