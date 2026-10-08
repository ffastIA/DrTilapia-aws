## Context

`frontend/middleware.ts` regra 3 implementa o gate de onboarding descrito em `openspec/specs/profile-onboarding-gate/spec.md`. O requirement "Abandonar o cadastro após o redirecionamento inicial encerra a sessão" foi uma decisão deliberada da change original (`add-profile-onboarding-gate`, arquivada em 2026-08-09): a intenção era tornar o cadastro efetivamente obrigatório, punindo com logout quem tentasse "escapar" do formulário depois do primeiro aviso.

O usuário reportou dois sintomas (redirecionamento incorreto pós-login; botão "Voltar" do cadastro "não funciona") que, investigados, são consequências diretas desse mesmo requirement — não bugs de implementação isolados. O pedido do usuário ("primeiro acesso → cadastro, caso contrário → hub", sem menção a logout) contradiz diretamente esse requirement específico; os demais requirements da capability (primeiro acesso silencioso, liberação após completar o cadastro, saudação com nome do perfil) continuam corretos e não são alterados.

## Goals / Non-Goals

**Goals:**
- Depois do redirecionamento silencioso de primeiro acesso, qualquer tentativa subsequente de sair de `/main/profile` sem completar o cadastro leva ao destino pedido (ex.: hub), nunca a um logout forçado.
- O botão "Voltar" em `/main/profile` volta a se comportar como em qualquer outra página do app (navegação normal), sem efeito colateral de sessão.
- Logout normal (botão sair, expiração de token via interceptor 401) limpa o mesmo conjunto de cookies que o logout forçado já limpava, evitando estado de gate inconsistente entre sessões de login no mesmo navegador.

**Non-Goals:**
- Não mexer no requirement de "primeiro acesso redireciona automaticamente" (continua correto e intacto).
- Não mexer no fluxo de salvamento do cadastro nem no redirecionamento pós-salvamento.
- Não adicionar um lembrete visual/persistente (banner, badge) de "cadastro incompleto" no hub — fora do escopo pedido pelo usuário; pode ser uma change futura separada se o produto quiser reforçar o lembrete sem reintroduzir o bloqueio.

## Decisions

1. **Remover o branch de logout, não substituí-lo por um redirecionamento repetido para `/main/profile`.** Uma alternativa seria, na segunda tentativa, redirecionar de novo (silenciosamente) para `/main/profile` em vez de deixar passar — mas isso ainda contradiria o pedido explícito do usuário ("caso contrário entra no hub"), então foi descartada.
2. **Manter `profileGateSeen` no código**, mesmo que seu único efeito remanescente seja decidir se o redirecionamento de primeiro acesso já ocorreu (não mais gatilho de punição). Continua útil para não repetir o redirecionamento de primeiro acesso a cada navegação.
3. **`clearAuth()` também limpa `profileGateSeen`/`profileComplete`** — mesmo com o branch de logout removido, deixar esses cookies obsoletos sobreviverem a um logout normal poderia causar um usuário que completou o cadastro (mas cujo `profileComplete` ficou desatualizado por algum motivo) a passar por uma checagem `hasCompletedProfile()` desnecessária no próximo login. Baixo risco, mas é a paridade correta com `clearSessionCookies`.

## Risks / Trade-offs

- **[Risco de produto]** O cadastro deixa de ser tecnicamente obrigatório — um usuário pode nunca completá-lo. Este é exatamente o comportamento pedido pelo usuário ("caso contrário entra no hub"), então é uma troca consciente, não um efeito colateral escondido. Se o produto quiser reforçar isso de outra forma (lembrete recorrente não bloqueante, por exemplo), fica para uma change futura.
- **[Risco de regressão]** Nenhuma mudança na lógica de "primeiro acesso" ou no salvamento do cadastro — o escopo é estritamente o branch de logout forçado e a paridade de limpeza de cookies.
