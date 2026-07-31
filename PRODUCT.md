# Product

<!-- impeccable:product-schema 1 -->

## Platform

android

## Users

Pessoas que preferem manter seu teclado Android habitual, especialmente o Samsung Keyboard, e querem ditar texto rapidamente em qualquer aplicativo sem trocar de teclado.

## Product Purpose

Gru oferece uma única ação: tocar em um pet flutuante, falar e inserir a transcrição no campo de texto atualmente focado. Sucesso significa que o fluxo funciona com um toque, sem atrasar a digitação normal.

## Positioning

O pet é simultaneamente o acionador, o indicador de gravação e o feedback da transcrição. O aplicativo não tenta substituir o teclado nem expor a complexidade do motor de voz.

## Operating Context

O Gru funciona sobre aplicativos como mensageiros e navegadores enquanto outro teclado permanece ativo. Após uma configuração inicial de microfone e acessibilidade, o usuário interage principalmente com o pet sobreposto.

## Capabilities and Constraints

- Detectar apenas campos de texto focados por meio de um serviço de acessibilidade opcional.
- Gravar, detectar silêncio, transcrever e inserir o resultado na posição do cursor.
- Oferecer quatro pets, três tamanhos, transparência, arraste e encaixe na borda.
- Conservar o motor de transcrição do Dictate Keyboard e remover as superfícies de teclado, dicionário, temas, extensões, mídia e Wear OS.
- Manter a licença Apache 2.0 e as atribuições do código original.
- Não registrar texto ditado, conteúdo da tela, áudio ou chaves de provedor em logs.

## Brand Commitments

O nome visível é Gru. A personalidade vem de pets originais, animados e discretos; eles podem ser expressivos, mas nunca devem competir com o campo de texto.

## Evidence on Hand

A base técnica é o commit 7047202 do repositório DevEmperor/DictateKeyboard. Não há mascotes anteriores a preservar; os quatro pets do Gru serão assets originais.

## Product Principles

- Uma ação principal, sem navegação desnecessária.
- O teclado escolhido pelo usuário permanece intacto e responsivo.
- Feedback visual imediato em todas as etapas do ditado.
- Privacidade e permissões explicadas antes da ativação.
- Recuperação clara quando microfone, rede, provedor ou campo falharem.

## Accessibility & Inclusion

Alvos de toque têm no mínimo 48 dp, textos respeitam escala do sistema, estados não dependem apenas de cor, animações respeitam a configuração de remoção de animações e todos os pets possuem descrições para leitor de tela.
