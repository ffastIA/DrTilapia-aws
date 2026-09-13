## 1. Extração do mockup

- [x] 1.1 Decodificar o bundle (`Dr. Tilap-IA - Landing (Standalone).html`) via script Node: parsear o JSON do `<script type="__bundler/template">`, reconstruir o HTML/CSS real, descartar o wrapper do bundler.
- [x] 1.2 Confirmar dimensões reais das duas imagens fornecidas (`LogoTAI.jpeg` 1080×894, `ImagemSite01.png` 1024×1536) via leitura binária dos headers PNG/JPEG.

## 2. Sistema de design

- [x] 2.1 Criar `frontend/styles/dr-tilapia.module.css` com os tokens (cores, espaçamento, tipografia) e classes de layout traduzidos do mockup, escopado via CSS Module.
- [x] 2.2 Adicionar `barlow`/`barlowCondensed` em `frontend/lib/fonts.ts` via `next/font/google`, sem remover `inter`/`poppins` existentes.
- [x] 2.3 Mover `LogoTAI.jpeg` e `ImagemSite01.png` da raiz do repo para `frontend/public/`.

## 3. Home

- [x] 3.1 Reescrever `frontend/app/page.tsx` como Server Component com o conteúdo completo do mockup (nav, hero, 3 cards de serviço, seção "Sobre", footer), copy extraído literalmente.
- [x] 3.2 Ligar os botões de nav a `/auth/login` e `/auth/signup`.
- [x] 3.3 Remover o bloco de CTA duplicado abaixo do hero (`.row`) a pedido do usuário, mantendo só os botões do nav.
- [x] 3.4 Remover `frontend/app/landing/page.tsx` (rota `/landing`, código morto sem referências) e o diretório vazio resultante.

## 4. Telas de autenticação

- [x] 4.1 Restilizar `frontend/app/auth/login/page.tsx` com o novo sistema de design, preservando cada estado, handler e chamada de hook (`useLoginMutation`, `useResendConfirmationMutation`, redirect para `/main/hub`) sem alteração de lógica.
- [x] 4.2 Restilizar `frontend/app/auth/forgot-password/page.tsx` da mesma forma, preservando `useForgotPasswordMutation` e o fluxo de validação/mensagens existente.

## 5. Verificação do redesign

- [x] 5.1 `tsc --noEmit` sem novos erros nos arquivos alterados (erros pré-existentes em outras áreas do app não relacionados permanecem, fora de escopo).
- [x] 5.2 Dev server local: `/`, `/auth/login`, `/auth/forgot-password`, `/auth/signup` respondendo 200; `/landing` respondendo 404; sem warnings/erros de compilação no log.
- [x] 5.3 Conferir por inspeção do payload RSC/bundle compilado que o conteúdo, classes e imagens novas aparecem corretamente (sem acesso a browser interativo nesta sessão).

## 6. Ambiente local (backend) — necessário para viabilizar o teste do login

- [x] 6.1 Diagnosticar por que o backend não subia: `supabase==2.4.0` instalado vs `supabase>=2.29.0` exigido por `requirements.txt`.
- [x] 6.2 `pip install -r requirements.txt --upgrade` para realinhar o ambiente Python ao manifesto do projeto.
- [x] 6.3 Diagnosticar a falha de login/reset (mascarada como "credenciais inválidas" e "sucesso" silencioso): `SSL: CERTIFICATE_VERIFY_FAILED`, causado por inspeção TLS de antivírus local (Norton) cujo certificado raiz não estava em `backend/ca-bundle-windows.pem`. Confirmado via `openssl s_client`.
- [x] 6.4 Regenerar `backend/ca-bundle-windows.pem` a partir do certificate store do Windows (Root + CA, LocalMachine + CurrentUser) combinado com o bundle público da `certifi`.
- [x] 6.5 Reiniciar o backend e confirmar que o handshake TLS com o Supabase passa a funcionar (login retorna o erro real do Supabase em vez de erro de certificado; `POST /auth/v1/recover` retorna 200 vindo do próprio Supabase).
- [x] 6.6 Encerrar o processo concorrente que ocupava a porta 3000 e subir o frontend nela (porta padrão esperada por `FRONTEND_URL` no e-mail de recuperação de senha).
- [x] 6.7 Usuário testou manualmente login e recuperação de senha de ponta a ponta e confirmou funcionamento.
