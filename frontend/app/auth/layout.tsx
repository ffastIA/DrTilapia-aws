// `/auth/login` e `/auth/forgot-password` pintam seu próprio fundo opaco
// (styles/dr-tilapia.module.css .authScreen) por cima deste layout, então esta
// cor só é visível atrás de `/auth/signup` e `/auth/callback` — mesma paleta
// clara da identidade Dr. Tilap-IA, sem depender do CSS Module da landing.
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-background">
      {children}
    </div>
  );
}