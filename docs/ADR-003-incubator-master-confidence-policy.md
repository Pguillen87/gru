# ADR-003: política conservadora de confiança para Master da Incubadora

O ranking SigLIP só pode selecionar automaticamente quando houver dois ou
três Masters elegíveis após os hard gates existentes, `top1 >= 0.82` e a
margem para o segundo for `>= 0.04`. A política é
`master-ranker-policy-v1`; os limiares são provisórios e versionados, não uma
afirmação de calibração estatística. Um único Master elegível continua
requerendo escolha humana: a falta de concorrência não é evidência de
confiança.

Sem nenhum Master elegível, a política retorna `RANKING_FAILED` e o job falha
de forma terminal, sem reservar poses. Nos demais casos não confiantes, o job
fica em `AWAITING_MASTER_APPROVAL` com decisão `NEEDS_HUMAN_SELECTION`. Esse
estado não falha, não reserva poses e não pode ser avançado pelo
reconciliador. A seleção humana owner-scoped grava
`selectionSource=human` e reutiliza o job e a operação de poses existentes.

Embeddings não são persistidos. A telemetria contém apenas versão, decisão,
top1, top2, margem e motivo sanitizado. Com auto-ranking desligado, o fluxo
continua em shadow mode e não seleciona nem enfileira poses.
