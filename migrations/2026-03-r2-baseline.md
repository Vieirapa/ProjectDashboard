# Migration Baseline — 2026-03-r2-baseline

Esta marca representa a linha de base formal do schema após a consolidação do Sprint R2.

## O que ela significa

- a tabela `schema_migrations` já existe
- o bootstrap atual do `app.py` garante o schema funcional mínimo
- esta versão registra o estado base a partir do qual migrations futuras podem ser explicitamente controladas

## Importante

Esta baseline **não substitui** o bootstrap existente. Ela serve para:

- iniciar controle explícito de versão de schema
- reduzir ambiguidade sobre o estado estrutural da aplicação
- preparar o caminho para migrations reais em etapas futuras
