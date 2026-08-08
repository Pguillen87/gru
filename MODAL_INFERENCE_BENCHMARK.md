# Benchmark de inferência Modal

## Estado

**Benchmark development executado em 2026-08-08; staging e production não foram alterados.**

Foi usada uma imagem sintética não pessoal de 1024 x 1024, H100, a revisão de cache `64e407a71c14cb60` e o hash de inferência `7ab183e4522e165e`. Modelo, LoRA, scheduler, quatro steps, seeds, prompt, resolução e compressão permaneceram inalterados.

## Resultado real

| Cenário | Cold/Warm | Load + CUDA aproximado | Generate 3 Masters | Worker total | Estado final |
| --- | --- | ---: | ---: | ---: | --- |
| Tentativa diagnóstica | Cold | concluído | não iniciado | 96,5 s de chamada | `FAILED`, asset ainda não visível |
| Benchmark A | Cold | ~40 s | ~7 s | 76,864 s | `AWAITING_MASTER_APPROVAL` |
| Benchmark B | Warm | 0 s de reload | ~7 s | 19,995 s | `AWAITING_MASTER_APPROVAL` |

O warm foi 73,99% mais rápido que o cold pelo tempo de parede do worker. A meta estrita era `< 20 s`; o resultado de `19,995 s` passou por aproximadamente 5 ms. A inferência consumiu cerca de 7 s nos dois cenários; no warm, aproximadamente 13 s ainda ficam em coordenação, pós-processamento PNG, commit do Volume e atualização de estado.

Custos faturados no relatório horário do Modal:

- app `gru-mascot-development`: `US$ 0,33819917`;
- preparação efêmera CPU/cache: `US$ 0,02362190`;
- total development consolidado: `US$ 0,36182107`.

O teto estimado informado era `US$ 0,20`. Ele foi ultrapassado em `US$ 0,16182107` porque a primeira tentativa consumiu o carregamento H100 antes de falhar por falta de `assets.reload()` e a cobrança das inicializações H100 consolidou com atraso no relatório horário. Nenhum teste adicional foi executado depois da confirmação do custo.

Os valores abaixo marcados como históricos vieram do benchmark anterior e servem apenas para comparação.

## Baseline histórica

| Cenário | Cold/Warm | Load | Generate | Total | GPU seconds | Custo |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Primeira tentativa, cache frio e falha | Cold | não segmentado | não concluiu | ~193 s | ~193 s | ~US$ 0,212 estimado histórico |
| Worker atual, cache preenchido, 3 Masters | Cold por job | ~37–40 s aproximados | ~2–7 s por Master | ~50 s | ~50 s | ~US$ 0,055–0,060 estimado histórico |

## Cenários restantes

Todos usarão a mesma imagem de benchmark não pessoal e aprovada, exatamente o mesmo hash de configuração e um lote de três Masters.

| Teste | Condição | Jobs | Evidência esperada |
| --- | --- | ---: | --- |
| A — Cold | concluído | 1 | 76,864 s |
| B — Warm imediato | concluído | 1 | 19,995 s, sem novo model load |
| C — Warm repetido | mesmo container | 1 | `jobs_in_container=3` e sem reload |
| D — Scaledown/cold | esperar mais de 45 s | 1 | novo container e novo load |

## Métricas a registrar

- `queue_ms` aproximado pelos timestamps correlacionados;
- `container_start_ms` medido do início do lifecycle até `worker_ready`;
- `cache_validation_ms`;
- `model_read_ms`;
- `pipeline_build_ms`;
- `lora_load_ms`;
- `cuda_transfer_ms`;
- geração de cada Master;
- `postprocess_ms` e `result_write_ms`;
- `total_worker_ms`;
- memória máxima alocada;
- jobs por container;
- segundos de GPU faturados, quando o Modal fornecer;
- custo faturado ou estimado, identificado explicitamente.

## Metas

- Warm abaixo de 20 segundos para três Masters.
- Redução de pelo menos 30% dos segundos de GPU por job quente.
- Pipeline carregado uma única vez por container.
- Zero diferença intencional de qualidade.
- Zero geração duplicada adicional.
- Zero alteração de Auth, App Check, ownership, idempotência ou limites.

## Plano de custo para autorização

- GPU pretendida: uma H100.
- Jobs: quatro lotes, total de doze candidatos Master.
- Concorrência: uma geração por GPU.
- Estimativa conservadora: até 240 segundos faturados de GPU para os quatro cenários.
- Pela tarifa histórica usada no relatório anterior (`US$ 0,001097/s`), isso seria aproximadamente `US$ 0,263`, mais CPU/memória auxiliares.
- Teto operacional sugerido para autorização: `US$ 0,35`.

A tarifa deve ser confirmada no Modal antes do teste. Se a estimativa vigente superar o teto, o benchmark não começa.

## Parada obrigatória

Não executar C, D, staging ou production sem nova autorização explícita. O primeiro lote autorizado terminou e o custo real excedeu a estimativa inicial.
