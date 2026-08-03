# Gru Design

## Direction

Gru é uma ferramenta Android cuja interface principal desaparece depois da configuração. O pet flutuante é acionador e indicador de estado; movimento, contorno, texto e descrição acessível comunicam o que está acontecendo.

## Visual System

- Material 3 e Dynamic Color estruturam a tela em temas claro e escuro.
- A tela usa áreas abertas, sem cartões aninhados ou decoração sem função.
- A navegação possui somente duas abas: `Geral` e `Transcrição`.
- Em Geral, a hierarquia é: estado atual, ação pendente, prévia do pet e personalização.
- Em Transcrição, a hierarquia é: motor atual, escolha Online/Privado e configuração necessária.
- Tipografia e espaçamento seguem os tokens Material e a escala de fonte do sistema.
- Cores semânticas distinguem gravação, sucesso e erro; nenhum estado depende apenas de cor.

## Components

- `SetupStatus`: mostra o estado geral e a próxima ação necessária.
- `PermissionRow`: explica e abre Acessibilidade, microfone ou notificação.
- `PetPreview`: apresenta o pet e sua descrição acessível.
- `PetSelector`: escolhe Lume, Faísca, Bip, Pingo ou Pudim.
- `PetSignalView`: desenha aura e sinal de estado sem provocar relayout.
- `LivingPetView`: anima pose, respiração, inclinação e resposta ao áudio.
- `EngineChoice`: compara Online e Privado sem esconder internet, privacidade, armazenamento ou bateria.
- `LocalModelSettings`: comunica não instalado, preparando, baixando, verificando, instalado e erro.
- `GroqKeyDialog`: salva a chave somente após confirmação e não mantém entrada parcial.

## Transcription Experience

- O primeiro uso mostra somente a escolha entre Online e Privado; as abas aparecem depois que um motor está realmente ativo.
- Cada opção resume benefícios e custos em um único card de 8 dp, com uma ação principal.
- Online usa o ícone de nuvem e a promessa “Mais rápido e leve”.
- Privado usa o ícone de cadeado e a promessa “Seu áudio não sai do celular”.
- Solicitar Privado não o ativa antes de existir um modelo válido.
- Solicitar Online não o ativa antes de existir uma chave salva.
- A chave Groq pode ser criada pelo link oficial e lida do clipboard somente após toque explícito em `Colar chave`.
- Progresso de download é determinado por bytes reais; não há progresso inventado.
- Movimento é reservado ao progresso indeterminado, progresso determinado e mudança de estado.

## Pet Language

- Lume: coruja azul, calma e atenta.
- Faísca: raposa coral, rápida e expressiva.
- Bip: robô verde-água, preciso e amigável.
- Pingo: criatura violeta, curiosa e suave.
- Pudim: cão branco e caramelo, alegre e atento.

Cada pet usa um atlas de poses com movimento contínuo do corpo e troca nítida de pose, sem misturar duas imagens completas. Não há selo de microfone nem botão de fechar. Durante a gravação, aura coral, resposta ao volume e a faixa `● OUVINDO 00:00` tornam o estado inequívoco.

## Interaction

- O pet aparece somente com campo editável focado e teclado visível.
- Campos de senha nunca mostram o pet.
- Um toque inicia a gravação; o segundo encerra e inicia a transcrição.
- Durante o processamento, um toque cancela a transcrição e remove o WAV temporário.
- Arrastar reposiciona; soltar encaixa na borda sem invadir teclado ou barras do sistema.
- A personalização acontece apenas no aplicativo de configuração.

## Motion States

- `Idle`: respiração e piscada discretas.
- `Recording`: reação imediata, aura e intensidade ligadas ao nível do áudio.
- `Transcribing`: movimento contínuo e controlado.
- `Success`: confirmação curta e alegre.
- `Error`: indicação clara e amigável, sem tristeza.
- Entrada e saída: anexação e remoção imediatas, sem animação de opacidade que possa ocultar o primeiro quadro.

Quando animações do sistema estão desativadas, as transições são instantâneas e o estado continua legível por texto, pose e descrição acessível.

## Tokens

- Tamanhos do pet: pequeno, médio e grande.
- Transparência: 40% a 100%.
- Alvo mínimo: 48 dp.
- Watchdog do primeiro quadro: 750 ms.
- Reconstrução: até duas tentativas automáticas, separadas por 120 ms.
- Confirmação de sucesso: 1.200 ms.
- Easing: desaceleração suave, sem elasticidade excessiva.

## Hardening Rules

- Eventos de acessibilidade são limitados aos necessários para foco, seleção e janelas.
- Uma sessão bloqueia novos toques enquanto transcreve.
- Fechar o teclado ou perder o campo cancela uma gravação ativa.
- Nenhuma falha altera o texto já presente no campo.
- Textos e controles acomodam RTL, telas pequenas e escala de fonte de 200%.
- O overlay percorre `Detached`, `Attaching`, `Visible` e `Failed`; somente um quadro realmente desenhado confirma `Visible`.
- O serviço publica seu estado de conexão enquanto ativo, permitindo diferenciar permissão concedida, serviço ativo e pet já verificado.
