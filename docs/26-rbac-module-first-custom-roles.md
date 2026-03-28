# 26 - RBAC module-first para roles custom (cards/edição)

## Contexto

Ao criar roles novas (ex.: `diretor`) no catálogo de roles, o usuário conseguia abrir páginas e ver cards, mas encontrava bloqueios parciais no fluxo de edição (campos/botões inconsistentes, incluindo casos em que o formulário mudava e o botão **Salvar alterações** não concluía o fluxo esperado).

## Problema raiz

Havia uma divergência entre os dois modelos de autorização:

1. **Legacy por role fixa** (listas hardcoded como `admin`, `member`, `desenhista`, etc.).
2. **Novo modelo por módulo** (`role_module_permissions`, ex.: `projects.cards_list`).

Partes do frontend/backend ainda usavam o modelo legado de role fixa para habilitar ações, o que quebrava a experiência para roles custom criadas no novo catálogo.

## Decisão técnica

Adotado o princípio:

- Para o domínio de cards/edição, a autorização deve ser **module-first**.
- Se a role tiver o módulo `projects.cards_list`, ela deve conseguir executar o fluxo completo do módulo (respeitando validações de negócio e escopo de projeto).

## Implementação

### Backend (`app.py`)

No fluxo de cards, permissões passaram a aceitar:

- regra legada por role **OU**
- módulo `projects.cards_list` habilitado

Cobertura aplicada para:

- criar card
- editar card
- upload de documento
- adicionar nota de revisão
- resolver status de nota de revisão

### Frontend (`web/app.js`, `web/edit.js`)

- remoção de dependência exclusiva de listas hardcoded de roles para habilitar ações de cards;
- uso de `/api/me/permissions` + `allowedModules` para habilitação de ações;
- correção de consistência na área de dependências (checkboxes respeitando estado de edição do módulo).

## Resultado esperado

Quando `projects.cards_list` estiver habilitado para uma role custom:

- usuário consegue editar campos de card normalmente;
- botão **Salvar alterações** funciona conforme o fluxo do módulo;
- ações relacionadas ao módulo (incluindo revisão/upload) seguem as mesmas regras de módulo;
- não há comportamento “aleatório” entre campos habilitados/bloqueados.

## Evidência de entrega

- Commit: `acfce56`
- Mensagem: `fix(rbac): allow custom roles with cards module to edit card flows`
- Branch: `develop`

## Regressão recomendada (rápida)

1. Login com usuário de role custom (ex.: `diretor`) com módulo `projects.cards_list` ativo.
2. Abrir card em `edit.html`.
3. Alterar descrição/status/prioridade/responsável/prazo.
4. Clicar **Salvar alterações**.
5. Confirmar persistência no retorno ao kanban.
6. Validar upload/review note conforme permissões do módulo.
