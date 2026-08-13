# Mascot API v2 — integração segura do Puleiro

## Garantias desta versão

- `POST /v2/mascot/jobs` registra e armazena a entrada, mas não agenda GPU;
- aprovação de Master nunca inicia poses;
- Master e poses têm kill switches independentes e fail-closed;
- owner deriva exclusivamente do JWT verificado;
- todas as consultas e imagens são owner-scoped;
- v1 continua disponível durante a migração;
- OpenAPI é publicado automaticamente pelo FastAPI da aplicação local.

## Autenticação BFF

O Modal aceita JWT HS256 curto em `Authorization: Bearer`. Claims obrigatórias:

```text
iss=puleiro-bff
aud=gru-modal
sub=<Firebase UID verificado no BFF>
jti=<UUID>
iat=<agora>
exp=<agora + até 120 segundos>
attempt_id=<tentativa>
```

O secret `PULEIRO_BFF_JWT_SECRET` pertence ao Modal Secret `gru-mascot-puleiro-bff`. Nunca deve ser versionado. Token expirado, issuer/audience incorretos, subject ausente e attempt divergente são rejeitados.

## Endpoints

| Método | Rota | Comportamento |
|---|---|---|
| POST | `/v2/mascot/jobs` | valida, registra, persiste, responde `generationScheduled:false` |
| GET | `/v2/mascot/jobs?attempt_id=` | recupera tentativa do mesmo owner |
| GET | `/v2/mascot/jobs/{job_id}` | consulta owner-scoped |
| GET | `/v2/mascot/jobs/{job_id}/masters/{master_id}` | download privado owner-scoped |
| POST | `/v2/mascot/jobs/{job_id}/master-generations` | exige flag e idempotência; bloqueado nesta fase |
| POST | `/v2/mascot/jobs/{job_id}/masters/{master_id}/approve` | marca escolha; zero geração |
| POST | `/v2/mascot/jobs/{job_id}/pose-generations` | kill switch independente; bloqueado |

## Kill switches

```text
REGISTRATION_ENABLED=true
MASTER_GENERATION_ENABLED=false
POSE_GENERATION_ENABLED=false
```

Ausência das flags de geração equivale a `false`. `GPU_GENERATION_ENABLED` continua sendo proteção adicional legada; geração v2 exige ambas as autorizações aplicáveis.

## Testes sem GPU

```powershell
python -m pytest modal_service/tests -q -p no:cacheprovider
python -m compileall -q modal_service
```

Os testes cobrem JWT, ownership, attemptId, idempotência, registro sem custo, aprovação sem poses, bloqueios e compatibilidade v1. Eles usam coordinator/test client/análise local; não chamam o deploy ativo.

## Smoke futuro com GPU

Somente após revisão da branch, configuração do secret, deploy deliberado em ambiente isolado e limite de custo aprovado: habilitar Master apenas, usar uma foto autorizada, uma idempotency key, um correlationId, observar uma tentativa e desligar novamente. Poses continuam desabilitadas. Este procedimento não foi executado.
