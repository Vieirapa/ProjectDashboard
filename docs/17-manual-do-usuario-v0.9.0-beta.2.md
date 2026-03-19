# 17 — Manual do Usuário (v0.9.0-beta.2)

Este manual descreve, de forma simples e completa, as funcionalidades disponíveis na versão **instalada no cliente**.

---

## 1) Objetivo do sistema

O **ProjectDashboard** é um sistema web estilo Kanban para gerenciar documentos/cards por projeto, com:

- autenticação de usuários
- controle de acesso por perfil (RBAC)
- organização por projetos
- histórico de revisões de arquivos
- notas de revisão
- trilha de auditoria

---

## 2) Perfis de acesso

## `admin`
- Acesso total a todas as áreas.
- Pode gerenciar usuários/convites, configurações, projetos e cards.

## `lider_projeto`
- Acesso operacional amplo: Início, Projetos, Kanban e Meu Perfil.
- **Não** acessa Usuários/Convites nem Configurações.

## `member`
- Cria/edita cards e atua no fluxo operacional.
- Sem acesso a painel administrativo.

## `desenhista` / `colaborador`
- Pode editar cards, anexar revisões e atuar na resolução de notas.

## `revisor`
- Pode registrar notas de revisão (conforme estágio/regra de negócio).

## `cliente`
- Acesso restrito conforme configuração de papéis permitidos no projeto.

> Observação: além do perfil do usuário, o acesso também depende da configuração de cada projeto (papéis permitidos por projeto).

---

## 3) Navegação principal

Menu lateral (varia por perfil):

- **Início** (`/`) — visão geral com KPIs por projetos acessíveis
- **Projetos** (`/projects.html`) — gestão de cadastro de projetos (admin/líder)
- **Kanban** (`/kanban.html?project_id=...`) — operação diária dos cards
- **Usuários & Convites** (`/admin-users.html`) — somente admin
- **Configurações** (`/settings.html`) — somente admin
- **Meu perfil** (`/profile.html`) — dados do usuário e preferências
- **Logout**

---

## 4) Funcionalidades por tela

## 4.1 Início (Home)

Exibe resumo dos projetos com acesso do usuário:

- total de projetos
- quantidade de cards do usuário
- quantidade de cards concluídos
- média de tempo de resolução
- tabela por projeto com ação rápida para abrir no Kanban

**Importante:** projetos marcados como template não entram nos KPIs da Home.

---

## 4.2 Projetos (admin e líder de projeto)

Permite administrar projetos do sistema:

- criar novo projeto
- editar projeto existente
- marcar projeto como **template**
- definir data de início e notas
- configurar perfis permitidos no projeto (checkbox)
- filtrar lista por tipo (todos/template/não-template)
- clonar projeto a partir de template
- apagar projeto
- visualizar lista de cards do projeto selecionado

---

## 4.3 Kanban

Área principal de trabalho dos cards/documentos:

- visualização dos cards por status
- criação de card/documento
- edição rápida de status e prioridade
- filtros e busca
- abertura da página de detalhes para edição completa
- resumo superior do projeto selecionado:
  - nome do projeto
  - data de início
  - total de colaboradores (owners distintos)
  - contadores e percentuais por status

---

## 4.4 Detalhes do card/documento

Na tela de detalhes (`/edit.html?slug=...`):

- edição completa dos dados do documento/card
- upload de arquivo
- histórico de revisões (r1, r2, r3...)
- registro e acompanhamento de notas de revisão

---

## 4.5 Usuários & Convites (somente admin)

Recursos administrativos:

- criação direta de usuário
- geração de link de convite
- envio opcional de convite por e-mail
- personalização da mensagem padrão de convite
- listagem de usuários cadastrados
- log de auditoria de ações sensíveis

Regras de segurança de usuários:

- exclusão de usuário só por admin
- admin não pode excluir a si mesmo
- admin não pode excluir outro admin (política do sistema)

---

## 4.6 Configurações (somente admin)

### a) SMTP / E-mail
- host, porta, usuário, senha, remetente, TLS
- mensagem padrão de convite
- envio de teste SMTP

### b) Comportamento do sistema
- prazo padrão em dias para documentos/cards

### c) Backup
- habilitar backup automático interno
- caminho de saída dos backups
- dias da semana e horário da execução
- executar backup manual (“rodar agora”)

### d) Diagnóstico do sistema
- configurar repositório/branch de comparação de versão
- rodar diagnóstico manual

### e) Documentos apagados
- configurar retenção (dias)
- listar itens apagados para restauração
- limpeza definitiva após retenção

### f) Relatórios periódicos
- criar relatórios agendados por dias da semana/horário
- escolher statuses/prioridades/roles destinatários
- definir mensagem do relatório
- visualizar lista e prévia de envio

---

## 4.7 Meu Perfil

Cada usuário pode:

- atualizar dados pessoais (e-mail, telefone, ramal, área, notas)
- alterar senha
- configurar comportamento visual pessoal:
  - habilitar/desabilitar cor de fundo por prioridade
  - personalizar cores por nível (Baixa, Média, Alta, Urgente)

---

## 5) Funcionalidades de segurança e rastreabilidade

- autenticação por login
- autorização por perfil + escopo de projeto
- proteção contra edição fora de contexto de projeto
- auditoria de operações críticas
- checagens críticas no backend (não apenas na interface)

---

## 6) Fluxo recomendado de uso (time)

1. Admin cria projetos e ajusta perfis permitidos por projeto.
2. Admin cria usuários ou envia convites.
3. Time opera o dia a dia no Kanban.
4. Revisões e anexos são tratados na tela de detalhes do card.
5. Admin acompanha auditoria, backups, diagnósticos e relatórios.

---

## 7) Limites e observações desta versão

- Versão de referência: **v0.9.0-beta.2**
- O sistema usa banco **SQLite** nesta instalação.
- A lista de itens exibida no menu depende do perfil do usuário.

---

## 8) Checklist rápido para validação com cliente

- [ ] Login funcionando para cada perfil principal
- [ ] Home exibindo KPIs por projetos permitidos
- [ ] Kanban abrindo por `project_id` correto
- [ ] Criação/edição de cards funcionando
- [ ] Upload e revisão funcionando na tela de detalhes
- [ ] Projetos: CRUD e papéis permitidos por projeto
- [ ] Usuários/Convites (admin)
- [ ] SMTP e teste de e-mail
- [ ] Backup manual e backup agendado
- [ ] Diagnóstico e relatórios periódicos

---

Se quiser, a próxima etapa é gerar uma versão **“Manual rápido em 1 página”** para treinamento de usuário final (sem detalhes técnicos).