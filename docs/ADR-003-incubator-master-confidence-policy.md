# ADR-003: política conservadora de confiança para Master da Incubadora

O ranking SigLIP só pode selecionar automaticamente quando os três Masters
passarem os hard gates existentes, `top1 >= 0.82` e a margem para o segundo
for `>= 0.04`. A política é `master-ranker-policy-v1`; os limiares são
provisórios e versionados, não uma afirmação de calibração estatística.

Caso contrário, o job fica em `AWAITING_MASTER_APPROVAL` com decisão
`NEEDS_HUMAN_SELECTION`. Esse estado não falha, não reserva poses e não pode
ser avançado pelo reconciliador. A seleção humana owner-scoped grava
`selectionSource=human` e reutiliza o job e a operação de poses existentes.

Embeddings não são persistidos. A telemetria contém apenas versão, decisão,
top1, top2, margem e motivo sanitizado. Com auto-ranking desligado, o fluxo
continua em shadow mode e não seleciona nem enfileira poses.
