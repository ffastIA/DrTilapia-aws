## Context

O mockup fornecido pelo usuário ("Dr. Tilap-IA - Landing (Standalone).html") não é HTML estático — é um bundle auto-extraível exportado por uma ferramenta de design ("Industry"/"omelette"): imagens e fontes em base64, mais um script de ~280 linhas que reconstrói `blob:` URLs e injeta o template real em runtime. O template/CSS reais foram extraídos diretamente via Node (`JSON.parse` do blob `<script type="__bundler/template">` embutido no arquivo) e usados como fonte de verdade; o wrapper do bundler foi descartado por completo.

O mockup decodificado é só uma landing page: nav (wordmark + logo + links + dois botões inertes "Entrar"/"Criar conta", sem `href`/`onclick`), hero (foto + headline + subtexto + `.row` de CTA **vazio**), 3 cards de serviços, seção "Sobre" com foto em tratamento duotone, footer. Não há formulário de login nem qualquer tela de autenticação desenhada.

O app já tinha duas landing pages competindo (`/` antiga, clara, simples; `/landing` mais nova, escura, não referenciada por nada) e uma tela de login funcional mas visualmente desconectada da marca. `frontend/styles/globals.css` (ativo, importado por `layout.tsx`) define o tema escuro usado por `/main/*`; `frontend/app/globals.css` é boilerplate morto do Next.js, não importado por ninguém.

Durante o teste de ponta a ponta do login restilizado, dois problemas de ambiente pré-existentes (não causados por este trabalho) impediram qualquer verificação real:
1. `backend/requirements.txt` já pedia `supabase>=2.29.0`, mas o Python instalado tinha `2.4.0` — o backend nem subia (`TypeError: ClientOptions.__init__() got an unexpected keyword argument 'httpx_client'`).
2. Com o backend de pé, toda chamada ao Supabase (login, recuperação de senha) falhava com `SSL: CERTIFICATE_VERIFY_FAILED`. Confirmado via `openssl s_client`: o certificado apresentado pelo host do Supabase tem `issuer=... Norton Web/Mail Shield Root` — um antivírus local fazendo inspeção SSL/TLS — e nem o bundle customizado do projeto (`backend/ca-bundle-windows.pem`, 247 certificados) nem o bundle público padrão da `certifi` continham essa raiz. O erro era mascarado: o login sempre respondia "credenciais inválidas" (mesmo com senha certa) e a recuperação de senha sempre retornava sucesso ao chamador (por desenho, para não revelar se o e-mail existe) mas nunca enviava o e-mail de fato.

## Goals / Non-Goals

**Goals:**
- Home e telas de autenticação com a mesma identidade visual do mockup, sem inventar conteúdo além do que o mockup e o usuário forneceram.
- Zero mudança de comportamento nas telas de autenticação — mesmos estados, mesmas chamadas, mesmo tratamento de erro, mesmos redirecionamentos.
- Uma única landing page ativa.
- O novo sistema de design não pode vazar para `/main/*` nem para as outras telas de auth (`signup`, `callback`) que não foram pedidas.
- Ambiente local capaz de rodar login/recuperação de senha de ponta a ponta para permitir verificação manual.

**Non-Goals:**
- Redesenhar `/auth/signup` ou `/auth/callback` (fora do pedido).
- Migrar `/main/*` para o novo sistema de tokens (tema escuro atual permanece intacto).
- Resolver os conflitos de dependência secundários reportados pelo pip durante o upgrade (`gotrue`/`supafunc` esperando `httpx<0.28`, `pillow`/`wrapt`/`huggingface-hub` em versões diferentes das que `streamlit`/`instagrapi`/`transformers` esperam) — não bloquearam a subida do backend; ficam registrados como risco conhecido, não corrigidos aqui.
- Isolar o ambiente Python do backend num virtualenv dedicado — o upgrade foi aplicado no Python global por não haver venv já estabelecido; criar um venv é uma mudança maior, fora do escopo deste pedido.

## Decisions

1. **Extrair o template real do mockup via script Node, não usar o arquivo como está.** O `.html` fornecido só faz sentido executado dentro da ferramenta de design original; o HTML/CSS efetivo estava serializado como JSON dentro de um `<script>`. Decodificar programaticamente garante fidelidade byte a byte ao design (cores, espaçamentos, copy) sem transcrição manual sujeita a erro.

2. **CSS Module dedicado (`dr-tilapia.module.css`) em vez de estender `styles/globals.css` ou o `tailwind.config.ts`.** `/main/*` depende dos tokens de tema escuro já definidos globalmente; misturar um segundo sistema de cores no mesmo arquivo global arriscaria colisão de nomes de classe e regressão visual em telas não pedidas. Um CSS Module dá isolamento real de nomes e pode ser importado só onde é usado.

3. **Fontes Barlow/Barlow Condensed aplicadas via `className` no wrapper de cada página nova, não no `layout.tsx` raiz.** `next/font/google` gera variáveis CSS que funcionam em qualquer ponto da árvore onde a classe é aplicada — aplicá-las no layout raiz vazaria a fonte para `/main/*` (que usa Poppins). Escopar por página evita isso sem duplicar a configuração de fontes.

4. **CTA extra no hero (`.row`, vazio no mockup) removido a pedido do usuário após a primeira entrega**, mantendo só os botões de nav ("Entrar"/"Criar conta") — o mockup deixava esse espaço propositalmente em aberto; a decisão de preenchê-lo ou não era do usuário, não uma escolha de design a ser imposta.

5. **Reaproveitar a mesma foto (`ImagemSite01.png`) no hero e na seção "Sobre", com crops e tratamento (duotone) diferentes.** Só havia uma foto real fornecida; o próprio mockup já desenhava a seção "Sobre" com tratamento duotone especificamente para permitir esse reaproveitamento sem parecer repetido.

6. **Regenerar `ca-bundle-windows.pem` a partir do certificate store do Windows (Root + CA, LocalMachine + CurrentUser) em vez de desabilitar a verificação TLS.** O mecanismo de override já existia e é o comportamento especificado (`backend-tls-verification`); o problema era só o **conteúdo** do bundle estar desatualizado em relação ao certificado atual do Norton. Desabilitar verificação (`verify=False`) violaria a spec existente e é exatamente o que ela proíbe.

7. **Upgrade de dependências via `pip install -r requirements.txt --upgrade`, sem criar virtualenv novo.** O requirements.txt já especificava as versões corretas; o ambiente é que estava desalinhado. Criar isolamento (venv/Docker) resolveria a causa raiz de forma mais robusta, mas é uma mudança de infraestrutura maior que não foi pedida — fica registrada como risco/trabalho futuro.

8. **Liberar a porta 3000 encerrando o processo concorrente, em vez de alterar `FRONTEND_URL`.** `FRONTEND_URL=http://localhost:3000` é o valor correto de convenção do projeto (usado nos links de e-mail do Supabase); mudar essa configuração para acomodar uma porta ocupada por outro app local seria consertar o ambiente de teste alterando configuração de produção. O usuário confirmou explicitamente essa opção.

## Risks / Trade-offs

- **[Risco] Upgrade de dependências no Python global, não num virtualenv.** Outros projetos que compartilhem esse mesmo Python podem ser afetados pelas versões novas de `langchain`, `fastapi`, `pydantic`, etc. Mitigação: nenhuma aplicada agora; registrado aqui como item para isolar em venv/Docker depois.
- **[Risco] Conflitos de dependência secundários reportados pelo pip** (`gotrue`, `supafunc`, `pillow`, `wrapt`, `huggingface-hub`) não foram investigados a fundo — o backend sobe e os fluxos testados (login, reset de senha) funcionam, mas outras partes do backend que dependam dessas bibliotecas em versões específicas podem quebrar silenciosamente.
- **[Trade-off] `ca-bundle-windows.pem` é um artefato de máquina local**, não versionado — a correção vale para esta máquina; qualquer outro ambiente de desenvolvimento atrás do mesmo tipo de proxy de inspeção precisará regenerar o bundle da mesma forma (não há script automatizado para isso no repositório).
- **[Observação] A cobertura de teste foi manual**, feita pelo próprio usuário testando login e recuperação de senha na UI — não há teste automatizado novo cobrindo o restyle nem a correção de ambiente.

## Migration Plan

Não aplicável a dados — mudança é de frontend (arquivos novos/reescritos) e de ambiente local (dependências, certificado, porta). Não há passo de rollback de schema; reverter é `git revert` dos arquivos de frontend listados no `proposal.md` e reinstalar a versão anterior de `supabase` no Python, se necessário.

## Open Questions

- Vale a pena migrar o backend para um virtualenv dedicado (ou Docker Compose local) para eliminar o risco de o Python global ficar desalinhado de novo? Não decidido — registrado como possível próximo passo.
- `/auth/signup` e `/auth/callback` devem receber o mesmo tratamento visual em algum momento? Não pedido nesta rodada.
