# 19 — Backlog Executável (Próxima Sprint)

Objetivo da sprint: elevar confiabilidade operacional e qualidade de uso em ambiente real de cliente, com entregas de alto impacto e baixo risco.

## Escopo fechado da sprint

1. Filtros em **Documentos Apagados**
2. Paginação em **Documentos Apagados**
3. Botão **Testar permissões de backup**
4. **Badge de saúde** no Diagnóstico
5. **Teste E2E** de regressão (login → primeiro carregamento do Kanban)
6. **QA de linguagem PT-BR** (microcopy e consistência)

---

## Ordem de execução (sequência recomendada)

- **Fase 1 (base técnica):** itens 1 e 2
- **Fase 2 (operação/admin):** itens 3 e 4
- **Fase 3 (qualidade):** itens 5 e 6
- **Fase 4 (fechamento):** documentação + validação final

---

## Item 1 — Filtros em Documentos Apagados

### Objetivo
Permitir localizar rapidamente documentos apagados por diferentes critérios.

### Escopo técnico
- Backend: estender endpoint de listagem de deletados com filtros opcionais:
  - `q` (nome/slug)
  - `deleted_by`
  - `deleted_from` e `deleted_to` (intervalo de data)
- Frontend (`settings.html` / `settings.js`):
  - adicionar campos de filtro
  - botão “Filtrar” e “Limpar”
  - refletir estado de filtro na renderização da lista

### Critérios de aceite
- [ ] Filtrar por nome/slug retorna itens corretos.
- [ ] Filtrar por usuário que apagou retorna itens corretos.
- [ ] Filtrar por intervalo de datas retorna itens corretos.
- [ ] Combinação de filtros funciona sem quebrar paginação.
- [ ] Sem filtros, comportamento atual é preservado.

### Estimativa
- **Médio** (4–6 horas)

---

## Item 2 — Paginação em Documentos Apagados

### Objetivo
Evitar listas longas e melhorar desempenho/usabilidade em clientes com maior volume.

### Escopo técnico
- Backend: paginação por `page` e `page_size` (com limite máximo seguro).
- Resposta deve incluir metadados:
  - `total`
  - `page`
  - `page_size`
  - `total_pages`
- Frontend:
  - controles de próxima/anterior
  - exibição da página atual
  - manutenção dos filtros ao navegar páginas

### Critérios de aceite
- [ ] Navegação de páginas funciona corretamente.
- [ ] Metadados batem com total real de itens.
- [ ] Filtros continuam aplicados durante paginação.
- [ ] Lista mantém desempenho estável com volume alto.

### Estimativa
- **Médio** (3–5 horas)

---

## Item 3 — Teste de permissões do caminho de backup

### Objetivo
Permitir validação preventiva de escrita no diretório de backup.

### Escopo técnico
- Backend: novo endpoint de diagnóstico de caminho de backup:
  - valida existência
  - valida permissão de escrita
  - retorna mensagem de remediação quando falhar
- Frontend (Configurações > Backup):
  - botão “Testar permissões do caminho”
  - feedback claro de sucesso/erro

### Critérios de aceite
- [ ] Caminho válido e gravável retorna sucesso.
- [ ] Caminho inválido ou sem permissão retorna erro claro.
- [ ] Mensagem orienta remediação (mkdir/chown/chmod quando aplicável).
- [ ] Não altera política de backup existente ao apenas testar.

### Estimativa
- **Pequeno/Médio** (2–4 horas)

---

## Item 4 — Badge de saúde no Diagnóstico

### Objetivo
Traduzir diagnóstico técnico em status visual simples para usuários de negócio.

### Escopo técnico
- Definir regra de classificação de saúde:
  - **Verde**: checks críticos OK
  - **Amarelo**: warnings sem impacto imediato
  - **Vermelho**: falhas críticas (serviço indisponível, sem acesso a recurso essencial etc.)
- Frontend: renderizar badge com cor + texto + resumo curto.
- Backend: padronizar payload de diagnóstico com severidade.

### Critérios de aceite
- [ ] Badge aparece após execução do diagnóstico.
- [ ] Cor/status condiz com resultado dos checks.
- [ ] Usuário entende rapidamente o estado (texto simples).
- [ ] Mantém saída detalhada para suporte técnico.

### Estimativa
- **Médio** (3–5 horas)

---

## Item 5 — Teste E2E de regressão (login → primeiro Kanban)

### Objetivo
Prevenir retorno do problema de carregamento inicial vazio no Kanban.

### Escopo técnico
- Criar teste automatizado cobrindo fluxo:
  1. Login
  2. Seleção/validação de projeto
  3. Primeiro carregamento do Kanban
  4. Verificação de cards e componentes críticos visíveis
- Integrar ao ciclo de regressão (script de testes existente/documentado).

### Critérios de aceite
- [ ] Teste falha quando o Kanban inicial não renderiza dados esperados.
- [ ] Teste passa no fluxo estável atual.
- [ ] Execução documentada no guia de testes.

### Estimativa
- **Médio** (3–5 horas)

---

## Item 6 — QA de linguagem PT-BR (microcopy)

### Objetivo
Melhorar clareza e consistência textual para uso real no cliente.

### Escopo técnico
- Revisar telas principais:
  - Home, Kanban, Projetos, Perfil, Usuários/Convites, Configurações
- Corrigir:
  - ortografia, acentuação, terminologia
  - consistência de rótulos e mensagens de erro/sucesso
- Criar checklist curto de revisão linguística para próximas releases.

### Critérios de aceite
- [ ] Textos críticos revisados e padronizados.
- [ ] Sem mistura inconsistente de termos para mesma ação/conceito.
- [ ] Checklist de QA linguístico salvo em `docs/tests/checklists/`.

### Estimativa
- **Pequeno/Médio** (2–4 horas)

---

## Definição de pronto (DoD) da sprint

Para cada item, considerar concluído apenas quando:

- [ ] implementação concluída (backend/frontend quando aplicável)
- [ ] teste manual objetivo executado
- [ ] teste automatizado criado/ajustado quando fizer sentido
- [ ] documentação atualizada (docs e/ou checklist)
- [ ] sem regressão evidente nas telas principais

---

## Plano de validação final (go/no-go)

1. Rodar checklist de navegação existente.
2. Validar fluxo admin completo (Configurações/Backup/Diagnóstico).
3. Validar fluxo operacional (Kanban + Detalhes).
4. Validar perfis (admin, lider_projeto, member/revisor).
5. Registrar resultado da sprint em documento de fechamento.

---

## Riscos e mitigação

- **Risco:** filtros + paginação aumentarem complexidade de estado na UI.
  - **Mitigação:** centralizar estado (filtros/página) e cobrir com testes.
- **Risco:** falso positivo no badge de saúde.
  - **Mitigação:** regra explícita de severidade + exemplos de mapeamento.
- **Risco:** mudanças de texto quebrarem entendimento operacional.
  - **Mitigação:** checklist de microcopy + validação com usuário-chave.

---

## Entregáveis esperados ao final

- Melhor governança de “Documentos Apagados” (filtro + paginação)
- Operação de backup mais segura (teste de permissão)
- Diagnóstico mais legível para gestão (badge de saúde)
- Regressão crítica coberta por E2E
- Interface mais clara em PT-BR para usuários do cliente