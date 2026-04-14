# 36 — Exportação e Arquivamento de Projeto (v1)

## Objetivo

Criar um fluxo seguro para congelar o estado de um projeto e permitir:

1. **Baixar Pacote Projeto**
   - exportar um pacote completo do projeto para armazenamento externo (SGQ)
   - conter snapshot de banco + arquivos + versões + logs relacionados

2. **Arquivar Projeto**
   - gerar o mesmo pacote
   - marcar o projeto como arquivado no sistema
   - remover acesso operacional do projeto para perfis não-admin
   - preservar possibilidade futura de recuperação/importação

---

## Conceito central

A exportação deve ser tratada como um **snapshot lógico portátil** do projeto, não como cópia crua da instalação inteira.

Isso significa que o pacote precisa conter:
- identidade estável do projeto
- dados normalizados do projeto
- documentos/cards do projeto
- dependências
- notas de revisão
- versões de documento
- auditoria relevante do projeto
- anexos/arquivos físicos do projeto
- manifesto do pacote

---

## Formato do pacote

### Recomendação v1
Usar **ZIP**.

Motivos:
- nativo e simples para usuários Windows
- suportado facilmente em Python padrão
- suficiente para snapshot inicial
- evita dependência externa como `rar`

### Nome sugerido

```text
projectdashboard-project-<project_slug_or_id>-<timestamp>.zip
```

Exemplo:

```text
projectdashboard-project-2-2026-04-14T18-00-00Z.zip
```

---

## Estrutura interna do pacote

```text
manifest.json
project/project.json
project/documents.json
project/document_versions.json
project/review_notes.json
project/dependencies.json
project/audit_logs.json
files/documents/...
files/uploads/...
files/docs_repo/...
```

---

## Conteúdo mínimo do `manifest.json`

```json
{
  "format": "projectdashboard.project-export.v1",
  "exported_at": "2026-04-14T18:00:00Z",
  "project": {
    "id": 2,
    "slug": null,
    "name": "Projeto Novo"
  },
  "source": {
    "app_version": "build-or-commit",
    "schema_version": "current"
  },
  "counts": {
    "documents": 0,
    "document_versions": 0,
    "review_notes": 0,
    "audit_logs": 0,
    "files": 0
  },
  "integrity": {
    "sha256": {}
  }
}
```

---

## Regra de identidade e import futuro

Para evitar conflito de IDs entre instalações diferentes:

### Regra v1
- o pacote exporta o **ID original** apenas como referência histórica
- a futura importação **não deve reutilizar automaticamente IDs internos**
- a importação deve criar:
  - novo `project.id` local
  - mapeamento entre IDs antigos e novos
  - preservação do `source_project_id` no manifesto/import log

### Consequência
A importação futura será feita por **remapeamento**, não por restauração cega de PKs.

Isso evita:
- colisão de IDs
- sobrescrita acidental de dados locais
- quebra de integridade em outra instalação do ProjectDashboard

---

## Arquivamento de projeto

### Ação "Arquivar Projeto"
Deve executar:

1. gerar pacote ZIP do projeto
2. salvar pacote em área de export/archive
3. marcar projeto como `archived=1`
4. restringir visibilidade do projeto a admin
5. impedir edição operacional, criação de cards e avanço normal

### Regra de acesso sugerida
- `admin`: pode ver, baixar pacote, futuramente restaurar ou excluir definitivamente
- demais perfis: projeto arquivado não aparece nas telas operacionais padrão

---

## Mudanças de dados sugeridas

### Tabela `projects`
Adicionar:
- `archived INTEGER NOT NULL DEFAULT 0`
- `archived_at TEXT NOT NULL DEFAULT ''`
- `archived_by TEXT NOT NULL DEFAULT ''`
- `archive_package_path TEXT NOT NULL DEFAULT ''`

### Futuro opcional
Criar tabela `project_exports`:
- `id`
- `project_id`
- `exported_at`
- `exported_by`
- `package_path`
- `package_sha256`
- `mode` (`manual_export` | `archive`)
- `manifest_json`

---

## Backend v1, escopo inicial

### Endpoint 1
`POST /api/projects/<id>/export`

Retorna:
- sucesso
- caminho/arquivo gerado
- URL de download, se aplicável

### Endpoint 2
`POST /api/projects/<id>/archive`

Executa:
- export
- flag de arquivamento
- auditoria

### Módulo sugerido
`backend/projects/export_service.py`

Responsabilidades:
- montar manifesto
- coletar dados relacionais do projeto
- copiar arquivos do projeto para staging temporário
- gerar ZIP final
- calcular checksums
- registrar auditoria

---

## Frontend v1, escopo inicial

Tela alvo inicial:
- `kanban.html`
- bloco lateral dentro da área de resumo do projeto

### Bloco sugerido
**ARQUIVOS E ANDAMENTO**

Botões:
- `Baixar Pacote Projeto`
- `Arquivar Projeto`

### Comportamento v1
- botão de baixar chama export e inicia download
- botão de arquivar exige confirmação forte
- feedback claro de sucesso/erro

---

## Cuidados importantes

1. **Não exportar o banco inteiro**
   - exportar apenas recortes relacionados ao projeto

2. **Não depender de IDs fixos para reimportação**
   - usar remapeamento futuro

3. **Auditoria obrigatória**
   - quem exportou
   - quando
   - qual modo

4. **Integridade do pacote**
   - checksums dos arquivos exportados

5. **Projeto arquivado não é projeto apagado**
   - continua preservado
   - apenas sai da operação normal

---

## Ordem recomendada de implementação

### Fase 1
- modelagem de dados de arquivamento
- serviço backend de exportação ZIP
- endpoint de export
- botão `Baixar Pacote Projeto`

### Fase 2
- endpoint de arquivamento
- botão `Arquivar Projeto`
- bloqueio de acesso operacional para não-admin

### Fase 3
- listagem de projetos arquivados para admin
- download de pacotes anteriores
- base para import futuro

---

## Recomendação executiva

Começar com **ZIP + manifesto + export recortado por projeto + flag de arquivamento**.

Isso já entrega valor para SGQ e preserva o caminho correto para uma futura importação segura sem colisão de IDs.
