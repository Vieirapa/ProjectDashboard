# 30 — UI Modernization Direction (Sprint B2 + B3)

## Objetivo

Definir a direção de modernização visual e estrutural da interface do ProjectDashboard para que o produto evolua de uma aplicação administrativa funcional para uma experiência com aparência mais sólida, coerente e profissional de SaaS.

O foco desta fase não é “deixar bonito” de forma superficial. O foco é criar:

- consistência visual
- sensação de produto real
- melhor hierarquia de informação
- base reutilizável para futuras telas
- ganho perceptível sem reescrever todo o frontend

---

## Estado atual

A interface atual já possui:

- layout com sidebar
- header por página
- dashboard inicial com KPIs
- Kanban operacional
- páginas dedicadas para edição, usuários, perfil, projetos e configurações
- CSS global único (`web/styles.css`)
- JS por página (`dashboard.js`, `app.js`, `edit.js`, etc.)

Essa base é suficiente para seguir evoluindo de forma incremental. Não há necessidade de reescrita total nesta sprint.

---

## Princípios visuais

### 1. Clareza acima de ornamento
A interface deve parecer profissional e útil. Evitar excesso de enfeite, cor sem função ou composição “de showcase”.

### 2. Consistência acima de improviso
A mesma intenção visual deve produzir o mesmo componente visual em todo o sistema.

### 3. Hierarquia acima de volume
Mais informação não significa melhor tela. O layout deve deixar claro:
- o que é principal
- o que é secundário
- o que exige ação
- o que é apenas contexto

### 4. Produto operacional, não landing page
O usuário precisa sentir que está dentro de uma ferramenta de trabalho séria.

### 5. Modernidade sóbria
A estética desejada é moderna, mas sem exageros. Preferir uma linguagem próxima de SaaS B2B pragmático:
- limpa
- legível
- confiável
- organizada

---

## Princípios de UX

1. **Estado da tela sempre claro**
   - loading, vazio, erro e sucesso devem ser compreensíveis.

2. **Ação principal sempre evidente**
   - o usuário não deve “caçar” o próximo passo.

3. **Contexto atual sempre visível**
   - especialmente projeto atual, perfil do usuário e área ativa.

4. **Leitura rápida primeiro, detalhamento depois**
   - dashboard, listas e cards devem favorecer escaneabilidade.

5. **Baixa surpresa**
   - componentes similares devem agir de forma similar.

---

## UI Foundation proposta

A base visual desta sprint deve consolidar os seguintes elementos:

### Tokens básicos
- escala de espaçamento
- raio de borda
- sombra/elevação
- paleta de neutros
- cores funcionais (primária, sucesso, alerta, perigo, info)
- tipografia e pesos

### Componentes base
- botão primário
- botão secundário
- botão de perigo
- badges/status chips
- cards de conteúdo
- cards de métrica
- header de página
- bloco de seção
- tabela/lista base
- feedback inline
- estado vazio
- estado de erro
- estado de carregamento

### Padrões estruturais
- app shell autenticado
- sidebar consistente
- topbar/header consistente
- área principal com largura e espaçamento previsíveis
- blocos internos com padding e hierarquia padronizados

---

## App shell autenticado

O shell autenticado é a camada mais importante da percepção de produto.

### Objetivos do shell
- dar sensação de ambiente de trabalho profissional
- reforçar navegação clara
- destacar projeto/contexto atual
- dar consistência entre páginas

### Elementos esperados
- sidebar limpa e estável
- agrupamento visual melhor entre navegação workspace/admin
- área de contexto do projeto atual
- header com título e ações principais
- melhor uso de espaço em telas largas
- comportamento razoável em larguras menores

---

## Direção para o dashboard

O dashboard é a principal vitrine do produto após login.

### O que o dashboard deve transmitir
- visão rápida do que importa
- sensação de controle operacional
- clareza de prioridades
- leitura executiva + operacional

### Estrutura recomendada

#### Bloco 1 — KPIs principais
- total de projetos visíveis
- itens sob responsabilidade do usuário
- itens concluídos
- tempo médio/resolução

#### Bloco 2 — Painel operacional principal
- projetos com mais atividade
- pendências/revisões/atrasos
- itens que exigem atenção rápida

#### Bloco 3 — Contexto complementar
- resumo por projeto
- próximos passos
- navegação para Kanban / Projetos

### Qualidade visual esperada
- cards mais coesos
- melhor separação entre KPI e conteúdo tabular
- hierarquia visual evidente
- leitura limpa sem excesso de caixas concorrendo entre si

---

## Direção para `projects` como próxima tela de referência

Depois do dashboard, a página de projetos deve ser a segunda referência visual do produto.

### Objetivos
- consolidar padrão de listagem
- reforçar consistência da navegação
- tornar seleção e leitura de projetos mais claras

### A página deve servir como referência para:
- cabeçalho de tela
- filtros/listas
- ações principais
- status e indicadores visuais

---

## Direção para o Kanban

O Kanban já é uma tela central de valor, mas nesta sprint ele não precisa ser totalmente redesenhado.

### Nesta fase, o Kanban deve:
- herdar a nova fundação visual
- ficar mais consistente com shell e dashboard
- preservar a funcionalidade atual

### Evitar agora
- reinventar a interação do board inteiro
- fazer mudança estrutural grande que comprometa velocidade da sprint

---

## Estratégia técnica de frontend

A modernização desta sprint deve seguir evolução incremental.

### Fazer agora
- reorganizar `styles.css` por seções
- introduzir tokens e utilitários leves
- padronizar classes base
- melhorar markup quando necessário nas páginas-alvo
- reduzir visual ad hoc em dashboard/shell

### Não fazer agora
- migração completa para framework SPA
- introdução de build system complexo sem necessidade
- redesenho total de todas as telas

---

## Ordem recomendada de execução

### Fase B2.1 — Fundação visual
1. reorganizar `styles.css`
2. definir tokens
3. padronizar botões, cards, badges, feedbacks
4. definir headers e containers principais

### Fase B2.2 — Shell
5. modernizar sidebar
6. modernizar header/topbar
7. melhorar área de contexto do projeto atual

### Fase B3.1 — Dashboard
8. redesenhar composição do dashboard
9. melhorar cards e seções
10. revisar clareza de métricas e ações

### Fase B3.2 — Próxima tela de referência
11. preparar `projects` para seguir a nova direção

---

## Critérios de aceite da modernização de UI

Considerar esta frente bem-sucedida quando:

- o produto parecer mais moderno e profissional sem perder sobriedade
- dashboard e shell transmitirem sensação clara de SaaS utilizável
- houver menos variação visual arbitrária entre páginas
- componentes base estiverem mais previsíveis
- o código CSS estiver mais organizado e sustentável

---

## Checklist visual de validação

Após cada entrega visual, validar:

1. a tela parece software de trabalho real?
2. há hierarquia visual clara?
3. a ação principal está evidente?
4. a densidade está equilibrada?
5. o layout está consistente com as demais telas?
6. a modernização melhorou o produto ou só trocou a pintura?

---

## Próximo passo recomendado

Após este documento:

1. reorganizar `web/styles.css`
2. modernizar shell autenticado
3. aplicar a nova fundação ao dashboard
4. preparar `projects` como próxima tela de referência visual
