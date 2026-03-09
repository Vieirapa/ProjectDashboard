# 18 — Manual Prático para Usuários (v0.9.0-beta.2)

Guia rápido para uso no dia a dia, com foco em **como cada tipo de usuário trabalha no sistema**.

> Público-alvo: usuários finais e líderes que vão operar o ProjectDashboard no cliente.

---

## 1) Visão rápida do sistema

No ProjectDashboard, o trabalho acontece em 3 áreas principais:

1. **Início**: visão geral dos projetos e indicadores.
2. **Kanban**: operação diária dos cards/documentos.
3. **Detalhes do card**: edição completa, anexos, revisões e notas.

Áreas administrativas (Usuários/Convites e Configurações) aparecem apenas para quem tem permissão.

---

## 2) Diferenças de acesso por tipo de usuário

## Matriz de acesso (resumo)

- **admin**
  - Acessa: Início, Projetos, Kanban, Usuários & Convites, Configurações, Meu Perfil.
  - Pode: gerenciar usuários, convites, regras do sistema, backup e diagnóstico.

- **lider_projeto**
  - Acessa: Início, Projetos, Kanban, Meu Perfil.
  - Não acessa: Usuários & Convites, Configurações.
  - Pode: coordenar operação e governança de projeto sem administração global do sistema.

- **member**
  - Acessa: Início, Kanban, Meu Perfil (e recursos operacionais conforme projeto).
  - Pode: criar e editar cards/documentos.

- **desenhista** / **colaborador**
  - Acessa: operação de cards no Kanban + detalhes.
  - Pode: editar conteúdo, anexar revisões e atuar em ajustes solicitados.

- **revisor**
  - Acessa: operação de revisão.
  - Pode: registrar notas de revisão e orientar ajustes.

- **cliente**
  - Acesso restrito por projeto e por papel permitido no projeto.

> Importante: além do perfil global, o acesso depende do que foi configurado em **Projetos → Acessível por**.

---

## 3) Fluxos práticos por perfil (com exemplos)

## 3.1 Exemplo: Admin configurando operação inicial

**Objetivo:** preparar o ambiente para o time começar.

1. Acessar **Projetos**.
2. Criar projeto “Cliente X - Implantação”.
3. Definir quais perfis podem acessar esse projeto (ex.: member, desenhista, revisor, cliente).
4. Ir em **Usuários & Convites** e:
   - criar usuários internos, ou
   - gerar convite e enviar por e-mail.
5. Ir em **Configurações** e ajustar:
   - SMTP (para convites e relatórios),
   - backup automático,
   - relatórios periódicos.

Resultado: ambiente pronto para operação com segurança e rastreabilidade.

---

## 3.2 Exemplo: Líder de Projeto acompanhando execução

**Objetivo:** acompanhar status e organizar fila de trabalho.

1. Abrir **Início** para visão geral dos KPIs por projeto.
2. Abrir **Projetos** para validar escopo e detalhes do projeto ativo.
3. Entrar no **Kanban** do projeto correto.
4. Usar filtros (status, prioridade, busca) para priorizar demandas.
5. Cobrar atualização dos cards e andamento com o time.

Resultado: visão de progresso sem precisar acessar recursos de administração global.

---

## 3.3 Exemplo: Member criando e movendo cards

**Objetivo:** executar trabalho operacional.

1. Entrar no **Kanban** do projeto.
2. Criar novo card/documento com dados iniciais.
3. Ajustar status e prioridade conforme evolução.
4. Abrir **Detalhes** do card para edição completa quando necessário.

Resultado: card rastreável durante todo o ciclo.

---

## 3.4 Exemplo: Desenhista/Colaborador atualizando revisão

**Objetivo:** entregar nova versão após apontamentos.

1. Abrir card em **Detalhes**.
2. Anexar arquivo atualizado (nova revisão).
3. Consultar notas de revisão existentes.
4. Realizar ajustes e registrar atualização.

Resultado: histórico de revisões organizado (r1, r2, r3...) e fácil de auditar.

---

## 3.5 Exemplo: Revisor abrindo apontamentos

**Objetivo:** garantir qualidade antes de conclusão.

1. Abrir card no fluxo de revisão.
2. Inserir notas de revisão objetivas (o que corrigir).
3. Devolver para ajuste quando necessário.

Resultado: processo de revisão formalizado e rastreável.

---

## 3.6 Exemplo: Cliente consultando andamento

**Objetivo:** acompanhar entregas sem acesso técnico amplo.

1. Entrar no projeto permitido.
2. Consultar cards e seus status.
3. Acompanhar evolução e itens concluídos.

Resultado: transparência do andamento com acesso controlado.

---

## 4) O que cada área da tela faz (resumo rápido)

- **Início**: KPIs e resumo dos projetos acessíveis.
- **Projetos**: cadastro e governança de projetos (admin/líder).
- **Kanban**: quadro de trabalho diário dos cards.
- **Detalhes**: edição completa + upload/revisões/notas.
- **Usuários & Convites**: gestão de acesso de pessoas (admin).
- **Configurações**: SMTP, backup, diagnóstico, retenção, relatórios (admin).
- **Meu Perfil**: dados pessoais, troca de senha e preferências visuais.

---

## 5) Boas práticas para uso no cliente

1. Sempre confirmar o **projeto selecionado** antes de editar cards.
2. Manter título/descrição dos cards claros e objetivos.
3. Usar prioridade com critério (evitar “urgente” em excesso).
4. Registrar revisões no card correto para preservar histórico.
5. Para dúvidas de acesso, validar primeiro o perfil do usuário e depois as permissões do projeto.

---

## 6) Dúvidas comuns (FAQ curto)

## “Não vejo a tela de Configurações. É erro?”
Não. Somente `admin` enxerga Configurações.

## “Sou líder de projeto e não vejo Usuários & Convites.”
Comportamento esperado: `lider_projeto` não acessa essa área.

## “Um usuário tem perfil correto mas não vê o projeto.”
Verificar em **Projetos** se o papel desse usuário está marcado em “Acessível por”.

## “Posso confiar só no que aparece no menu?”
O menu ajuda, mas a segurança real é validada no backend.

---

## 7) Checklist rápido para treinamento de usuários

- [ ] Explicar diferença entre Admin, Líder e Operacionais
- [ ] Mostrar fluxo: Início → Kanban → Detalhes
- [ ] Simular criação e atualização de card
- [ ] Simular revisão com nota e nova revisão de arquivo
- [ ] Validar que cada perfil só vê o que deve ver

---

Se quiser, no próximo passo eu monto uma versão **“treinamento por perfil”** com roteiro de 30 minutos (admin, líder e usuário operacional), pronta para apresentação ao cliente.