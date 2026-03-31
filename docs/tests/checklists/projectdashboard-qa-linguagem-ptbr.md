# ProjectDashboard — Checklist de QA de Linguagem PT-BR

Objetivo: validar clareza, consistência e qualidade textual antes de release ou fechamento de sprint.

## 1. Terminologia
- [ ] O mesmo conceito usa o mesmo termo em todas as telas.
- [ ] Não há mistura desnecessária entre PT-BR e inglês na UI.
- [ ] Labels de ação estão consistentes (ex.: Salvar, Excluir, Restaurar, Atualizar).
- [ ] Termos técnicos inevitáveis estão compreensíveis para o usuário alvo.

## 2. Ortografia e gramática
- [ ] Sem erros de ortografia evidentes.
- [ ] Acentuação correta.
- [ ] Concordância verbal e nominal adequada.
- [ ] Mensagens curtas sem ambiguidade desnecessária.

## 3. Feedbacks de sistema
- [ ] Mensagens de sucesso são claras e objetivas.
- [ ] Mensagens de erro orientam próxima ação.
- [ ] Mensagens de confirmação deixam explícito o impacto da ação.
- [ ] Não há mensagens genéricas demais quando há contexto suficiente.

## 4. Áreas prioritárias para revisão
- [ ] Login
- [ ] Dashboard/Home
- [ ] Projetos
- [ ] Kanban
- [ ] Edit/Detalhe
- [ ] Usuários/Invites
- [ ] Perfil
- [ ] Configurações
- [ ] Backup/Restore
- [ ] Diagnóstico
- [ ] Documentos recuperáveis

## 5. Consistência operacional
- [ ] Ações perigosas usam linguagem de alerta proporcional.
- [ ] Ações reversíveis não parecem destrutivas demais.
- [ ] Placeholders ajudam sem competir com labels.
- [ ] Subtítulos e textos de apoio explicam a finalidade da seção.

## 6. Critério de aprovação
- [ ] UI compreensível para usuário operacional sem apoio técnico contínuo.
- [ ] Não há inconsistência textual crítica nas telas principais.
- [ ] Ajustes remanescentes, se existirem, são cosméticos e não bloqueantes.
