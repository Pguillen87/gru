# Modal v2 staging sem GPU

Ambiente Modal: `gru-mascot-v2-staging`.

O script `deploy_v2_staging.ps1` fixa app, recursos, secrets e flags próprios. Ele nunca usa os nomes `gru-mascot-*` de produção para Volumes ou Dicts e mantém `GPU_GENERATION_ENABLED`, `MASTER_GENERATION_ENABLED` e `POSE_GENERATION_ENABLED` como `false`.

Antes do deploy, o ambiente precisa conter exclusivamente:

- `gru-mascot-v2-staging-puleiro-bff`: `PULEIRO_BFF_JWT_SECRET`;
- `gru-mascot-v2-staging-firebase-admin`: `FIREBASE_ADMIN_CREDENTIALS_JSON` para compatibilidade v1 e validações Firebase futuras.

O contrato v2 usa JWT curto do BFF. A criação registra e persiste, mas não chama `_schedule_master` nem `.spawn()`. Aprovação não chama poses.

## Deploy

```powershell
.\modal_service\deploy_v2_staging.ps1
```

Nunca execute o script com outro environment, não altere as três flags de geração e não use rotas v1 nesta validação.

## Rollback

Pare apenas o app `gru-mascot-v2-staging` no environment homônimo. Não toque no app `gru-mascot` do environment `main`. Volumes e Dicts de staging podem ser preservados para auditoria ou removidos posteriormente com autorização explícita.
