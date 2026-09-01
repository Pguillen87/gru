# Modal v2 — operações assíncronas de poses

`POST /v2/mascot/jobs/{job_id}/pose-generations` é uma operação assíncrona e owner-scoped. A aprovação do Master continua separada e nunca inicia poses implicitamente.

## Reserva

O endpoint valida o JWT curto, consome o `jti`, valida ownership, estado, Master e escolhas. `job_control` executa com um container e uma entrada concorrente, tornando atômica a criação da operação e a reserva de `pose_gpu_call_id`. A operação persistida contém fingerprint, ID, status, request ID e correlation ID.

O replay com a mesma fingerprint retorna `202`, `idempotentReplay=true` e a mesma `operationId`. Mudança de escolhas depois da reserva é rejeitada. O worker não executa uma segunda transição de início.

## Resposta e headers

- status: `202 Accepted`;
- `X-Request-ID`: novo por request Modal;
- `X-Correlation-ID`: trace do Puleiro;
- `X-Operation-ID`: operação persistida, inclusive no replay.

O caminho síncrono não consulta cache e não aguarda GPU, assets ou conclusão. `POSE_GENERATION_ENABLED=false` ou `GPU_GENERATION_ENABLED=false` bloqueia antes da reserva.

## Estados da operação

`queued → running → completed` ou `failed`. A validação final exige exatamente três arquivos com checksum, os papéis `normal`, `listening`, `transcribing` e os mesmos option IDs reservados.

## Gate de consistência visual

O alpha/QC de cada PNG é necessário, mas não torna o conjunto utilizável por si só. Antes da promoção, `pose-set-visual-v3` exige canvas idêntico, margens de frame seguras, escala vertical e linha de pés compatíveis. Largura, aspecto e centro horizontal são role-aware: `normal`, `listening` e `transcribing` possuem envelopes e limites por par estáveis. Falhas como `CANVAS_DIMENSIONS_MISMATCH`, `FRAME_CROP_RISK` ou `SCALE_MISMATCH` preservam os brutos e impedem a promoção.

Esse gate detecta erros objetivos de enquadramento; a avaliação semântica (por exemplo, se o gesto realmente comunica escuta) continua revisão humana. Consulte `POSE_QC_V3.md` para a diferença v2 → v3 e para o recovery idempotente de RAWs preservados, que não é retry GPU.

## Observabilidade e privacidade

Eventos e campos são emitidos por `structured_observability.py`, que usa allowlist. Nunca registrar tokens, cookies, UID bruto, bytes, Base64, URLs privadas, filenames originais, prompts ou secrets.

## Testes sem GPU

Os testes de domínio/contrato exercitam criação, replay, owner diferente, escolha imutável, anti-replay de JTI, serialização e validação dos três papéis sem chamar `.spawn()`. Nenhum teste desta fase chama endpoint ativo, cria Master ou inicia worker GPU.
