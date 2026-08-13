# Modal v2 staging sem GPU

Ambiente Modal: `gru-mascot-v2-staging`.

O script `deploy_v2_staging.ps1` fixa app, recursos, secrets e flags próprios. Ele nunca usa os nomes `gru-mascot-*` de produção para Volumes ou Dicts e mantém `GPU_GENERATION_ENABLED`, `MASTER_GENERATION_ENABLED` e `POSE_GENERATION_ENABLED` como `false`.

Antes do deploy, o ambiente precisa conter exclusivamente:

- `gru-mascot-v2-staging-puleiro-bff`: `PULEIRO_BFF_JWT_SECRET`;
- `gru-mascot-v2-staging-firebase-admin`: placeholder isolado de `FIREBASE_ADMIN_CREDENTIALS_JSON`; nenhuma credencial de produção é copiada. Firebase é inicializado sob demanda apenas se uma rota v1 for chamada.

O contrato v2 usa JWT curto do BFF. A criação registra e persiste, mas não chama `_schedule_master` nem `.spawn()`. Aprovação não chama poses.

## Deploy

```powershell
.\modal_service\deploy_v2_staging.ps1
```

Nunca execute o script com outro environment, não altere as três flags de geração e não use rotas v1 nesta validação.

URL atual: `https://automacao-guillenia-gru-mascot-v2-staging--gru-mascot-v2-d25cd0.modal.run`.

O probe reproduzível exige a URL e o secret no ambiente local, sem imprimir o secret:

```powershell
python -m modal_service.tools.probe_v2_staging
```

Ele registra uma imagem sintética, repete a mesma idempotency key, consulta e retoma o job e confirma que Master/poses retornam `409`. O probe nunca habilita flags e nunca chama uma função GPU.

Validação de 2026-08-13: registro `202/registered`, `generationScheduled=false`, replay no mesmo `jobId`, leitura/retomada `200`, outro owner `404`, Master `409 GENERATION_DISABLED` e poses `409 POSE_GENERATION_DISABLED`. Após o ensaio, os métodos `QwenMasterWorker.generate` e `generate_poses` apresentaram zero runners e zero inputs.

## Rollback

Pare apenas o app `gru-mascot-v2-staging` no environment homônimo. Não toque no app `gru-mascot` do environment `main`. Volumes e Dicts de staging podem ser preservados para auditoria ou removidos posteriormente com autorização explícita.
