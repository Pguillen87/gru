# Product

<!-- impeccable:product-schema 1 -->

## Platform

android

## Users

Pessoas que querem ditar texto sem trocar o teclado Android que já utilizam, incluindo Samsung Keyboard e Gboard.

## Product Purpose

Gru oferece uma única ação: tocar em um pet flutuante, falar e inserir a transcrição no campo editável focado. O aplicativo não substitui o teclado e não mantém histórico de ditados.

## Operating Context

Após configurar Acessibilidade, microfone, notificação e uma chave da Groq, o usuário interage com o pet sobre outros aplicativos. O pet aparece somente quando há um campo editável focado e o teclado está visível. Campos de senha são excluídos.

## Capabilities and Constraints

- Detectar campo editável focado e teclado visível pelo serviço de Acessibilidade.
- Gravar áudio WAV temporário, detectar fala, transcrever pela Groq e inserir no cursor ou substituir a seleção.
- Oferecer cinco pets, três tamanhos, transparência, arraste e encaixe na borda.
- Comunicar os estados inativo, ouvindo, processando, sucesso e erro.
- Usar somente o provedor Groq com chave fornecida pelo usuário.
- Não oferecer teclado, dicionário, autocorreção, histórico, prompts, reescrita, mídia, extensões ou Wear OS.
- Não registrar em logs áudio, texto ditado, conteúdo da tela ou chave do provedor.

## Brand Commitments

O nome visível é Gru. Lume, Faísca, Bip, Pingo e Pudim são pets animados, discretos e sempre amigáveis. O estado de erro não usa tristeza ou punição.

## Provenance

A referência histórica é o commit `7047202ecf0aaee0393f93c1d7c98eddf1631c7a` do projeto Dictate Keyboard. A licença Apache 2.0 e as atribuições do código original permanecem em `LICENSE` e `NOTICE`.

## Product Principles

- Uma ação principal, sem navegação desnecessária.
- O teclado escolhido pelo usuário permanece intacto.
- Feedback imediato e inequívoco durante a gravação.
- Permissões explicadas antes da ativação.
- Falhas curtas, diretas e recuperáveis.

## Accessibility & Inclusion

Alvos de toque têm no mínimo 48 dp, textos respeitam a escala do sistema, estados não dependem apenas de cor, animações respeitam a configuração de remoção de animações e os estados do pet possuem descrições para leitor de tela.
