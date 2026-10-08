## Why

Dois relatos de bug do usuário, investigados nesta sessão, têm a mesma causa raiz em `frontend/middleware.ts` (regra 3, L116-142):

1. **"Ao logar no sistema, o usuário só deve ser redirecionado para a tela de cadastro caso seja o primeiro acesso, caso contrário entra no hub principal."** Hoje, na primeira vez que um usuário autenticado com perfil incompleto tenta acessar `/main/*` (exceto `/main/profile`), ele é corretamente redirecionado uma vez para `/main/profile` (`profileGateSeen=1`). Mas na **segunda** tentativa de sair de `/main/profile` sem ter completado o cadastro, o sistema **força logout** (`clearSessionCookies` + redirect para `/auth/login`) em vez de simplesmente deixar entrar no hub — não é isso que o usuário espera ("caso contrário entra no hub").
2. **"Botão voltar do cadastro não funciona."** `BackButton` (`frontend/components/ui/BackButton.tsx`) em `/main/profile` faz `router.back()` ou `router.push('/main/hub')`; qualquer uma das duas navegações reentra no middleware, que (pelo mesmo motivo do item 1) força o logout em vez de voltar — por isso "Voltar" parece não fazer nada (na real, desloga silenciosamente).

**Nota de escopo importante:** o comportamento atual (forçar logout na segunda tentativa) é uma decisão de produto **deliberada e já especificada** em `openspec/specs/profile-onboarding-gate/spec.md`, requirement "Abandonar o cadastro após o redirecionamento inicial encerra a sessão" (introduzida pela change arquivada `add-profile-onboarding-gate`). Esta proposta **reverte essa decisão** a pedido explícito do usuário — não é a correção de um bug acidental, é uma mudança de comportamento consciente, documentada aqui para ficar revisável antes de implementar.

Achado secundário (higiene, não a causa principal): `frontend/store/authStore.ts` `clearAuth()` — usado no logout normal (botão sair em `/main/hub`, interceptor 401 em `lib/api.ts`) — não limpa os cookies `profileGateSeen`/`profileComplete`, só `clearSessionCookies` (caminho de logout forçado) limpa. Isso deixa estado de gate obsoleto sobreviver a um logout normal dentro da mesma sessão de navegador.

## What Changes

- `frontend/middleware.ts`: remover o branch de logout forçado da regra 3. Quando `profileGateSeen` já é `'1'` e o perfil continua incompleto, deixar a navegação seguir normalmente (ex.: para `/main/hub`) em vez de limpar cookies de sessão e redirecionar para `/auth/login`. O gate de onboarding passa a ser um aviso de uma única vez, não um bloqueio recorrente.
- `frontend/store/authStore.ts` `clearAuth()`: também remover os cookies `profileGateSeen` e `profileComplete` (paridade com o que `clearSessionCookies` já faz), para que um logout normal não deixe estado de gate obsoleto para a próxima sessão de login.
- Nenhuma mudança no comportamento de "primeiro acesso" (continua redirecionando para `/main/profile` na primeira vez) nem no salvamento do cadastro (continua liberando o hub normalmente).

## Capabilities

### Modified Capabilities
- `profile-onboarding-gate`: o requirement "Abandonar o cadastro após o redirecionamento inicial encerra a sessão" é substituído por um novo comportamento — tentar sair de `/main/profile` sem completar o cadastro, depois do redirecionamento inicial, permite acesso normal ao restante de `/main/*` (sem logout).

## Impact

- **Código afetado**: `frontend/middleware.ts` (regra 3), `frontend/store/authStore.ts` (`clearAuth`).
- **Comportamento observável**: um usuário com perfil incompleto que ignore o redirecionamento inicial para `/main/profile` (navegando para outra página ou clicando "Voltar") passa a ter acesso normal ao hub, em vez de ser deslogado. O cadastro deixa de ser tecnicamente obrigatório — vira um lembrete de uma vez só. Essa é exatamente a troca pedida pelo usuário.
- **Risco assumido**: usuários podem nunca completar o cadastro se ignorarem o primeiro aviso. Aceito conscientemente (ver `design.md`).
