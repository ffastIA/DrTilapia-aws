## Why

O usuário forneceu um mockup HTML ("Dr. Tilap-IA - Landing (Standalone).html", exportado de uma ferramenta de design externa) com uma nova identidade visual para o produto — paleta clara, fontes Barlow/Barlow Condensed, estética "blueprint" com cantos hairline — e pediu para aplicar esse visual na home e na tela de login.

A home atual (`frontend/app/page.tsx`) era uma landing simples em Tailwind ad-hoc (azul/cinza) sem relação com a nova identidade. Havia ainda uma **segunda landing concorrente** (`frontend/app/landing/page.tsx`, rota `/landing`, tema escuro/glassmorphism) que não era referenciada por nada na aplicação — puro código morto competindo com a home real. A tela de login também usava Tailwind ad-hoc (gradiente azul/índigo), sem qualquer relação visual com a marca nova, embora sua lógica de autenticação (mutations, redirect, tratamento de erro) estivesse correta e não devesse ser tocada.

O mockup fornecido é só uma peça de marketing — não contém formulário de login algum (os botões "Entrar"/"Criar conta" do mockup são decorativos, sem destino). Para cumprir o pedido foi necessário desenhar as telas de autenticação (login e, por extensão solicitada depois, "esqueci minha senha") do zero, seguindo a mesma linguagem visual, mas sem alterar nada do comportamento.

Durante a verificação de ponta a ponta do login (necessária para confirmar que o restyle não quebrou o fluxo), descobriram-se dois problemas pré-existentes e não relacionados ao redesign em si, que impediam qualquer teste real:
- O backend não subia: o ambiente Python tinha `supabase==2.4.0` instalado, mas o código usa uma API (`ClientOptions(httpx_client=...)`) que só existe a partir de `supabase>=2.29.0` — exatamente o que `requirements.txt` já exigia. O ambiente estava fora de sincronia com o próprio manifesto do projeto.
- Mesmo com o backend de pé, login e recuperação de senha falhavam sempre: um antivírus local (Norton) faz inspeção SSL/TLS nas conexões, e o bundle de certificados usado pelo backend para confiar nesse proxy (`backend/ca-bundle-windows.pem`) estava desatualizado, sem o certificado raiz atual do Norton. O erro de TLS era mascarado como "credenciais inválidas" no login, e como sucesso silencioso (sem envio real de e-mail) na recuperação de senha.

Ambos os problemas foram corrigidos para viabilizar o teste do trabalho principal, e o usuário confirmou por teste manual que login e recuperação de senha voltaram a funcionar de ponta a ponta.

## What Changes

- Nova home (`frontend/app/page.tsx`) no visual "Dr. Tilap-IA": nav com logo real, hero com foto e headline, 3 cards de serviços, seção "Sobre" com tratamento duotone, footer — conteúdo extraído literalmente do mockup fornecido (o arquivo é um bundle auto-extraível de uma ferramenta de design; o HTML/CSS real foi decodificado do blob embutido, não copiado do wrapper).
- Rota `/landing` (segunda landing, código morto, tema escuro) removida por completo.
- Tela de login (`frontend/app/auth/login/page.tsx`) e tela de "esqueci minha senha" (`frontend/app/auth/forgot-password/page.tsx`) redesenhadas com a mesma identidade visual — **toda a lógica existente preservada byte a byte** (estados, mutations, tratamento de erro, redirecionamentos).
- Novo sistema de design (`frontend/styles/dr-tilapia.module.css`, CSS Module) com os tokens extraídos do mockup, escopado para não vazar para `/main/*` (que continua no tema escuro/Poppins existente) nem colidir com `frontend/styles/globals.css`.
- Fontes Barlow/Barlow Condensed adicionadas via `next/font/google` em `frontend/lib/fonts.ts`, aplicadas só nas rotas novas.
- Duas imagens fornecidas pelo usuário (`LogoTAI.jpeg`, `ImagemSite01.png`) movidas para `frontend/public/` e usadas como logo e foto do hero/seção "Sobre".
- **Fora do escopo do pedido original, mas necessário para viabilizar o teste**: `backend/requirements.txt` reinstalado/sincronizado no ambiente Python (upgrade de `supabase` 2.4.0 → 2.31.0 e dependências relacionadas); `backend/ca-bundle-windows.pem` regenerado a partir do certificate store do Windows + bundle público da `certifi`.

## Capabilities

### New Capabilities
- `dr-tilapia-visual-identity`: garante que a home e as telas de autenticação (login, esqueci minha senha) compartilhem a mesma identidade visual do mockup fornecido, sem alterar o comportamento de autenticação subjacente, e que não exista mais que uma landing page ativa.

### Modified Capabilities
Nenhuma. `backend-tls-verification` continua descrevendo o mesmo comportamento observável (mecanismo de override de CA via `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE`, verificação nunca desabilitada) — o que mudou foi apenas o **conteúdo** do arquivo de bundle local, um dado de ambiente, não o mecanismo especificado.

## Impact

- `frontend/app/page.tsx`, `frontend/app/auth/login/page.tsx`, `frontend/app/auth/forgot-password/page.tsx` — reescritos (visual apenas nas telas de auth; conteúdo completo na home).
- `frontend/app/landing/page.tsx` — removido.
- `frontend/styles/dr-tilapia.module.css` — novo.
- `frontend/lib/fonts.ts` — adiciona `barlow`/`barlowCondensed`, sem remover `inter`/`poppins`.
- `frontend/public/LogoTAI.jpeg`, `frontend/public/ImagemSite01.png` — novos.
- `backend/requirements.txt` já existia; ambiente Python local reinstalado para condizer com ele (afeta qualquer outro projeto que compartilhe esse mesmo Python global, já que não há virtualenv dedicado em `backend/`).
- `backend/ca-bundle-windows.pem` — conteúdo regenerado (arquivo local, fora do controle de versão).
- `FRONTEND_URL=http://localhost:3000` (`backend/.env`) não foi alterado — em vez disso, o app concorrente que ocupava a porta 3000 nesta máquina de desenvolvimento foi encerrado para liberar a porta padrão.
