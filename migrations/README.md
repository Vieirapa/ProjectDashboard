# Migrations

Esta pasta marca o início da estratégia de migrations versionadas do ProjectDashboard.

## Objetivo nesta fase

Ainda não substituir totalmente o bootstrap do `app.py`, mas criar a base para:

- versionamento explícito do schema
- evolução previsível do banco
- menor dependência de migrações implícitas espalhadas no código

## Estado atual

- `schema_migrations` é garantida no bootstrap
- novas migrations poderão ser registradas por versão
- o bootstrap atual continua coexistindo nesta fase de transição
