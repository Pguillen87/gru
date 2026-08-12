# Product

<!-- impeccable:product-schema 1 -->

## Platform

android

## Users

Pessoas que querem ditar texto sem trocar o teclado Android que já utilizam, incluindo Samsung Keyboard e Gboard.

## Product Purpose

Gru oferece uma ação: tocar em um pet flutuante, falar e inserir a transcrição no campo editável focado. O aplicativo não substitui o teclado, não mantém histórico e permite escolher entre Groq Online e Whisper Privado no aparelho.

## Operating Context

O pet aparece somente quando há um campo editável focado e o teclado está visível. Campos de senha são excluídos. O primeiro uso começa pela escolha do motor e segue para as permissões necessárias.

## Transcription Modes

- `ONLINE_GROQ`: exige internet e chave; envia o áudio temporário à Groq.
- `PRIVATE_LOCAL`: exige modelo verificado; processa offline e proíbe fallback automático para Groq.
- A escolha fica centralizada no `TranscriptionEngineRouter` e é capturada no início de cada sessão.
- A troca é transacional: um destino pronto é ativado em uma única operação; Online sem chave mantém o Privado atual até a configuração terminar.
- Solicitar Privado desativa imediatamente qualquer Online quando o modelo local ainda não estiver pronto.
- Uma única máquina de estados atende aos dois motores.

## Capabilities and Constraints

- Detectar campo editável focado e teclado visível pela Acessibilidade.
- Gravar WAV temporário, detectar fala, transcrever e inserir no cursor ou na seleção.
- Baixar o modelo local somente após ação explícita, validar tamanho e SHA-256 e armazená-lo em área privada.
- Oferecer cinco pets, três tamanhos, transparência, arraste e encaixe na borda.
- Manter o pet fora do teclado e do campo editável; permitir ocultá-lo temporariamente no contexto atual sem desligar o Gru.
- Comunicar os estados inativo, ouvindo, processando, sucesso e erro.
- Não oferecer teclado, dicionário, autocorreção, histórico, prompts, reescrita, mídia, extensões ou Wear OS.
- Não registrar áudio, texto ditado, conteúdo da tela ou chave.
- A identidade de conversa usa somente estrutura da janela e do editor, transformada em chave opaca da sessão. Silenciamentos não sobrevivem ao reinício do serviço.
- O Small Q5_1 é o modelo local em avaliação para priorizar precisão em português. Ele substitui o Base Q5_1 após relatos de muitas palavras incorretas; sua latência precisa ser validada novamente em aparelho físico antes da decisão definitiva.
- O Large V3 Turbo Q5_0 permanece apenas no histórico de benchmark e não é baixado pelo aplicativo.

## Product Principles

- A privacidade escolhida é literal: no Privado, o áudio não sai do aparelho.
- Sem fallback silencioso entre motores.
- Download grande sempre consciente, verificável e cancelável.
- O teclado escolhido pelo usuário permanece intacto.
- Feedback imediato durante gravação e processamento.
- Falhas curtas, diretas e recuperáveis.

## Accessibility & Inclusion

Alvos de toque têm no mínimo 48 dp, textos respeitam a escala do sistema, estados não dependem apenas de cor e controles possuem nomes acessíveis. Material 3 e Dynamic Color atendem aos temas claro e escuro.

## Provenance

A referência histórica é o commit `7047202ecf0aaee0393f93c1d7c98eddf1631c7a` do Dictate Keyboard. O runtime local usa `whisper.cpp` v1.8.6 sob licença MIT. Atribuições permanecem em `NOTICE`, `LICENSE` e no diretório vendorizado.
