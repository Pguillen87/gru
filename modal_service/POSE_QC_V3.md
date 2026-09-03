# Pose-set visual QC v3

`pose-set-visual-v3` substitui o v2 para a promoção de poses, preservando o
v2 como `pose_set_visual_consistency_qc_v2()` para auditoria de falhas
históricas.

## Por que mudou

O catálogo `web-poses-v1` define três papéis com composições diferentes:
`normal` é naturalmente mais frontal/estreito; `listening` pode abrir o corpo
na lateral; `transcribing` pode abrir asas, acessórios ou objeto de trabalho.
O v2 aplicava um único delta min/max de largura, aspecto e centro X aos três,
como se fossem a mesma fotografia.

Na amostra preservada que motivou a revisão, o pós-alpha QC mediu:

| Papel | Largura | Altura | Ocupação | Aspecto | Centro X |
| --- | ---: | ---: | ---: | ---: | ---: |
| normal | 0.552734 | 0.872070 | 0.482023 | 0.633819 | 0.490234 |
| listening | 0.697266 | 0.831055 | 0.579466 | 0.839013 | 0.570313 |
| transcribing | 0.721680 | 0.890625 | 0.642746 | 0.810307 | 0.523926 |

O v2 falhava somente nos sinais horizontais globais. O conjunto mantém
altura, ocupação, baseline, frame e canvas aceitáveis após o pipeline oficial
`remove_connected_flat_background(..., crop=False)` e alpha QC.

## Política estável

V3 usa envelopes fixos por papel e limites fixos por par para `width`,
`aspect_ratio` e `center_x`. As constantes estão em
`image_processing.py`; não são calculadas a partir de dados de produção.
Diferenças horizontais legítimas passam, mas deslocamento extremo, largura
realmente incompatível e proporção visível extrema continuam falhando.

## Invariante de prontidão

`COMPLETED` não é, sozinho, `READY_TO_HATCH`. A projeção pública só pode
expor prontidão quando o Master aprovado é verificável e existem exatamente
as três roles operacionais (`normal`, `listening`, `transcribing`) promovidas,
com manifest e checksums íntegros, alpha QC aprovado e `pose-set-visual-v3`
aprovado. Qualquer evidência ausente ou inconsistente permanece fail-closed.

## Gates preservados

V3 continua fail-closed para:

- papéis ausentes/duplicados, alpha QC e metadados de frame;
- canvas diferente e risco de crop;
- escala vertical, ocupação, centro vertical e baseline dos pés;
- cenário dominante/foreground inconsistente;
- centro horizontal e geometria horizontal realmente extremos.

## Recuperação de RAW preservado

`RECOVER_POSES_FROM_PRESERVED_RAWS` é uma operação interna, owner-scoped e
idempotente. Ela é permitida somente para `FAILED` com
`VISUAL_POSE_CONSISTENCY_FAILED`, com Master, operação e GPU call históricos
já registrados e `pose_operation_status=failed`.

A recuperação lê exatamente os três RAWs reservados, reexecuta em CPU o mesmo
pós-processamento, alpha QC e QC visual v3, promove o diretório de poses de
forma atômica e preserva `recoveredFromErrorCode` e a versão do QC no registro.
Ela não chama provider, não reserva worker, não cria GPU call e não altera
Master, choices ou operation id. Falha por RAW faltando, alpha inválido ou QC
v3 inválido interrompe a promoção.

O recovery do job QA real só pode ocorrer após auditoria e merge/deploy do PR.
