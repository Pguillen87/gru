# Worker Qwen persistente no Modal

## Objetivo

Reduzir latência e segundos faturados de GPU sem alterar modelo, revisão, LoRA, BF16, scheduler, prompt, quatro steps, seeds, resolução, pós-processamento ou contrato Android. Esta arquitetura mantém Firebase Auth, App Check, idempotência, ownership, limites, cancelamento e kill switch.

## Arquitetura anterior

Cada chamada de `generate_master` reconstruía o transformer, scheduler e pipeline, carregava o LoRA e transferia tudo para CUDA antes de gerar os três Masters. O Volume evitava novo download da internet quando o cache estava preenchido, mas não evitava reconstrução e transferência a cada job.

## Arquitetura nova

```text
API protegida
  -> valida cache em função CPU
  -> reserva custo/idempotência
  -> enfileira QwenMasterWorker.generate(job_id)

container QwenMasterWorker
  -> @modal.enter: valida cache, monta pipeline, carrega LoRA e move para CUDA uma vez
  -> generate job 1: foto + seeds 0/1/2 + resultados
  -> generate job 2: reutiliza o mesmo pipeline
  -> @modal.exit: registra encerramento
```

`PersistentPipelineRuntime` garante carregamento único e conta jobs concluídos. Uma exceção dentro da inferência marca o runtime como não confiável; chamadas posteriores não reutilizam o pipeline. Falhas posteriores à geração, como persistência de resultado, são classificadas separadamente como falhas locais do job.

## Congelamento de qualidade

O hash `inference_config_hash` cobre modelo, revisões, LoRA, dtype, scheduler, prompt, negative prompt, steps, CFG e seeds. Os valores continuam:

- `Qwen/Qwen-Image-Edit-2511` na revisão `6f3ccc0b56e431dc6a0c2b2039706d7d26f22cb9`;
- `lightx2v/Qwen-Image-Edit-2511-Lightning` na revisão `d74eba145674fd7e31b949324e148e21e7118abd`;
- LoRA `Qwen-Image-Edit-2511-Lightning-4steps-V1.0-fp32.safetensors`;
- BF16, quatro steps e seeds 0, 1 e 2;
- mesmo prompt, scheduler, resolução derivada e pós-processamento PNG.

O benchmark visual não exige igualdade binária, pois kernels CUDA podem não ser bitwise determinísticos. A aprovação exige equivalência estrutural e visual com as mesmas entradas e configurações.

## Cache formal

O Volume `gru-mascot-models` continua sendo a fonte persistente. A operação administrativa CPU `prepare_model_cache` baixa somente revisões fixas, inventaria os arquivos e publica atomicamente:

```text
/gru-models/
  active.json
  READY
  manifests/<cache_revision>.json
  models--.../snapshots/...
```

O manifesto registra schema, IDs, revisões, arquivo LoRA, arquivos esperados, tamanhos e estado `complete`. `READY` e `active.json` são publicados somente depois do inventário completo. Revisões anteriores não são removidas.

Uma criação com GPU habilitada consulta `model_cache_status` antes da reserva de custo. Cache ausente, parcial, incompatível ou corrompido retorna `MODEL_CACHE_NOT_READY`; o worker de usuário nunca chama Hugging Face e usa somente caminhos locais com `local_files_only=True`.

## Lifecycle e autoscaling

- GPU: H100, sem alteração nesta rodada.
- `min_containers=0`: nenhuma GPU permanente.
- `buffer_containers=0`: nenhuma capacidade ociosa antecipada.
- `scaledown_window=45`: compromisso inicial entre reaproveitar bursts curtos e não faturar longos períodos ociosos.
- Todos os ambientes desta branch: `max_containers=1` até decisão econômica posterior.
- Concorrência: `@modal.concurrent(max_inputs=1)`; um job por GPU.

Staging permanece em um container. Produção não é promovida nesta entrega e qualquer aumento futuro exige autorização posterior.

## Estado, fila e cancelamento

`gru-mascot-jobs`, `gru-mascot-idempotency` e `gru-mascot-usage` continuam como fontes de verdade. O container guarda apenas pipeline e contadores efêmeros. Morte, scaledown ou substituição do container não remove jobs, assets, reservas ou identificadores de chamada.

O fluxo continua usando `JobCoordinator` para transições atômicas. Retry com a mesma chave não agenda uma segunda geração. Cancelamento usa o `gpu_call_id` persistido e permanece confirmado pelo servidor.

## Isolamento

- a foto é lida do diretório exclusivo do job;
- cada seed cria um `torch.Generator("cuda")` novo;
- outputs e buffers são locais à chamada;
- imagens PIL são fechadas mesmo em falha;
- nenhuma foto, output ou generator permanece em `self`;
- `torch.cuda.empty_cache()` não é chamado sem benchmark;
- o pipeline é a única estrutura compartilhada e recebe uma entrada por vez.

## Falhas

- `MODEL_CACHE_NOT_READY`: falha recuperável anterior à GPU; preparar ou ativar cache.
- `JOB_LOCAL_FAILURE`: falha após pipeline confiável, como commit/persistência.
- `WORKER_CORRUPTED`: falha durante inferência; o runtime não aceita reutilização.
- Falhas de domínio e estados terminais continuam sob `JobCoordinator`.

Nenhuma falha habilita fallback, ignora Auth/App Check ou transforma erro em sucesso.

## Observabilidade

`InferenceObserver` emite JSON sanitizado com `trace_id` derivado por hash do `job_id`, sem expor job ou UID. Eventos incluem container, cache, load, pipeline, LoRA, CUDA, fila, job, Masters, pós-processamento, escrita, falha e shutdown.

Latências dentro de um processo usam `time.perf_counter()`. O Modal não expõe diretamente no código atual `gpu_billed_seconds`, queue depth ou o instante monotônico comum entre API e worker; esses valores devem vir do painel/telemetria Modal e nunca ser inventados. Os timestamps de `job_queued` e `job_started` permitem calcular espera aproximada no relatório.

São proibidos nos logs: imagem, bytes/Base64, Firebase UID, tokens, Authorization, cookies, credenciais, prompt com conteúdo pessoal, URLs privadas e paths pessoais.

## Custo

A política inicial privilegia custo variável: escala a zero e janela de 45 segundos. A economia vem da reutilização quando dois ou mais jobs chegam ao mesmo container. O cold start continua honesto e inclui Volume -> RAM -> VRAM.

Qualquer número posterior deve indicar se é faturado ou estimado. Métricas históricas não são tratadas como benchmark novo.

## Rollback

1. Manter manifestos e artefatos anteriores no Volume.
2. Reapontar `active.json` com `activate_model_cache_revision` quando compatível com o deployment.
3. Para rollback de código/modelo, usar uma versão Modal anterior e o manifesto correspondente.
4. Confirmar `/health`, cache e kill switch antes de liberar geração.
5. Production nunca é promovida automaticamente.

## Rollout

1. Development com geração desligada: importar app, testes, status do cache e guardas.
2. Preparar cache administrativamente sem GPU.
3. Solicitar autorização para benchmark H100.
4. Executar cold, warm 1, warm 2 e scaledown/cold.
5. Comparar custo, latência, falhas e qualidade.
6. Promover a staging somente após auditoria.
7. Production exige nova autorização, evidência e plano de rollback.

## Pontos de extensão futuros

H200/B200, `torch.compile`, batching e GPU Memory Snapshot ficam fora desta entrega. Eles só podem ser avaliados depois que a persistência básica estiver medida e aprovada.
