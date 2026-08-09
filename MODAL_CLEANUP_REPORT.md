# Auditoria e limpeza do Modal

Data: 2026-08-09

## Ambiente canônico

O APK usa `https://automacao-guillenia--gru-mascot-api.modal.run`, publicado no ambiente Modal `main` com a configuração interna `GRU_MASCOT_ENV=development`. A aplicação canônica é `gru-mascot`. O cache Qwen/LoRA desse ambiente foi formalizado e validado na revisão `64e407a71c14cb60` antes da atualização do endpoint.

## Removido ou desativado

- Aplicação duplicada `gru-mascot-development` no ambiente Modal `development`: parada.
- Implantação incompleta `gru-mascot` criada acidentalmente no ambiente `development`: parada.
- Volume duplicado `gru-mascot-models` do ambiente `development`: removido depois que o cache canônico do `main` foi validado. O conteúdo era reconstruível e não continha jobs nem imagens do usuário.

## Preservado deliberadamente

- `main/gru-mascot-models`: cache canônico ativo.
- `main/gru-mascot-assets`: originais, Masters e resultados usados pelo endpoint canônico.
- Dicts `gru-mascot-jobs`, `gru-mascot-idempotency` e `gru-mascot-usage` do `main`: estado, retomada, idempotência e limites.
- `main/gru-mascot-firebase-admin`: segredo ativo; o conteúdo não foi lido, copiado ou registrado.
- `development/gru-mascot-assets` e seus três Dicts: preservados porque contêm criações e histórico de jobs. Excluí-los seria perda de dados, não limpeza segura.

## Custo e segurança

Nenhuma função GPU foi chamada durante a auditoria, preparação do cache, deploy, limpeza ou instalação Android. A preparação do cache foi administrativa/CPU e reutilizou os artefatos existentes. Firebase Auth, App Check, idempotência, limites e kill switch foram preservados.

## Próxima retenção

Os assets e Dicts históricos de `development` podem ser removidos em uma rodada futura somente depois de definir prazo de retenção e confirmar que nenhuma criação precisa ser recuperada. A exclusão deve ocorrer por ambiente e por nome exato, nunca por padrão amplo.
