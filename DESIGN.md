# Gru Design

## Direction

Gru é uma ferramenta Android cuja interface principal desaparece depois da configuração. O pet flutuante é acionador e indicador de estado; movimento, contorno, texto e descrição acessível comunicam o que está acontecendo.

## Visual System

- Material 3 e Dynamic Color estruturam a tela em temas claro e escuro.
- A tela usa áreas abertas, sem cartões aninhados ou decoração sem função.
- A hierarquia é: estado atual, ação pendente, prévia do pet e personalização.
- Tipografia e espaçamento seguem os tokens Material e a escala de fonte do sistema.
- Cores semânticas distinguem gravação, sucesso e erro; nenhum estado depende apenas de cor.

## Components

- `SetupStatus`: mostra o estado geral e a próxima ação necessária.
- `PermissionRow`: explica e abre Acessibilidade, microfone ou notificação.
- `PetPreview`: apresenta o pet e sua descrição acessível.
- `PetSelector`: escolhe Lume, Faísca, Bip, Pingo ou Pudim.
- `PetSignalView`: desenha aura e sinal de estado sem provocar relayout.
- `LivingPetView`: anima pose, respiração, inclinação e resposta ao áudio.

## Pet Language

- Lume: coruja azul, calma e atenta.
- Faísca: raposa coral, rápida e expressiva.
- Bip: robô verde-água, preciso e amigável.
- Pingo: criatura violeta, curiosa e suave.
- Pudim: cão branco e caramelo, alegre e atento.

Cada pet usa um atlas de poses com movimento interpolado. Não há selo de microfone nem botão de fechar. Durante a gravação, aura coral, resposta ao volume e a faixa `● OUVINDO 00:00` tornam o estado inequívoco.

## Interaction

- O pet aparece somente com campo editável focado e teclado visível.
- Campos de senha nunca mostram o pet.
- Um toque inicia a gravação; o segundo encerra e inicia a transcrição.
- Arrastar reposiciona; soltar encaixa na borda sem invadir teclado ou barras do sistema.
- A personalização acontece apenas no aplicativo de configuração.

## Motion States

- `Idle`: respiração e piscada discretas.
- `Recording`: reação imediata, aura e intensidade ligadas ao nível do áudio.
- `Transcribing`: movimento contínuo e controlado.
- `Success`: confirmação curta e alegre.
- `Error`: indicação clara e amigável, sem tristeza.
- Entrada e saída: escala e opacidade rápidas, sem alterar layout.

Quando animações do sistema estão desativadas, as transições são instantâneas e o estado continua legível por texto, pose e descrição acessível.

## Tokens

- Tamanhos do pet: pequeno, médio e grande.
- Transparência: 40% a 100%.
- Alvo mínimo: 48 dp.
- Entrada: 150 ms.
- Saída: 110 ms.
- Confirmação de sucesso: 1.200 ms.
- Easing: desaceleração suave, sem elasticidade excessiva.

## Hardening Rules

- Eventos de acessibilidade são limitados aos necessários para foco, seleção e janelas.
- Uma sessão bloqueia novos toques enquanto transcreve.
- Fechar o teclado ou perder o campo cancela uma gravação ativa.
- Nenhuma falha altera o texto já presente no campo.
- Textos e controles acomodam RTL, telas pequenas e escala de fonte de 200%.
