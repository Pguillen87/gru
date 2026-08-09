# Implementação do frontend Compose

## Escopo

Implementação da Parte 3 derivada do SHA-base `2a1cab011ef77a33a25e4e211420dbf0c03d3429`. A camada visual foi ligada aos estados existentes sem alterar Firebase, Groq, Whisper, JNI, CMake ou o overlay. A rodada posterior do catálogo visual ampliou de três para 12 as poses geradas pelo worker Modal, preservando autenticação, endpoints, idempotência e o mapeamento final de três arquivos do runtime.

## Navegação

`GruActivity` agora usa `NavigationBar` Material 3 com cinco destinos: Permissões, Voz, Ligar/Desligar, Mascotes e Criar mascote. O item central tem tratamento visual maior, semântica de aba e abre Controle; ele nunca chama `setEnabled` diretamente.

## Mapeamento de telas

- `GruGeneralScreen`: Permissões, com resumo de conclusão e reavaliação no retorno da tela de Configurações.
- `GruTranscriptionScreen`: Voz, preservando a seleção transacional Online/Groq e Privado/Whisper.
- `GruControlScreen`: estado operacional derivado de `GruPreferences`, permissão de Acessibilidade, microfone, motor e saúde do overlay. Ligar/desligar usa somente `prefs.setEnabled`.
- `GruMascotScreen(MascotFocus.LIBRARY)`: biblioteca, seleção, edição de nome, tamanho e opacidade.
- `GruMascotScreen(MascotFocus.CREATE)`: mesma state machine/repositório de criação, exibida como jornada separada.

## Componentes e acessibilidade

Foram reutilizados os componentes Material 3 existentes e adicionada uma navegação inferior sem alvos menores que 48dp. O item central, estados de Controle e seleção de mascotes expõem semântica de seleção/estado. As telas usam rolagem, `sp`, tema Material 3 com esquemas Light/Dark próprios e RTL. O Dynamic Color foi desativado nesta rodada porque alterava os acentos ciano, dourado e semânticos aprovados no Stitch; a decisão pode ser reavaliada por superfície quando houver equivalência visual. A imagem oficial `brand/gru-brand-master.png` foi empacotada como `gru_brand_master` e renderizada com `ContentScale.Fit`.

## Estados preservados

Não há router paralelo. A segurança da troca de motor continua em `GruPreferences`/`TranscriptionSelectionPolicy`; a criação continua em `MascotRepository` e `MascotCreationState`, incluindo retomada, retry, cancelamento e idempotência.

## Limitações e pendências

- A versão anterior foi instalada no Samsung A55, mas revelou a falha de layout registrada pelo usuário. A correção final `fcc54e1` foi validada no emulador Android 16 com páginas de 16 KB; o A55 não estava disponível no ADB após a correção e ainda precisa receber este APK.
- Não foram criados vídeos ou screenshots falsos para os tutoriais.
- Pagamento, poses remotas antecipadas e arquivamento continuam fora do escopo.
- O protótipo Figma foi consultado somente em leitura nos nós aprovados (`6:20`, `6:24`, `7:3`, `7:10`, `7:17`, `7:24`, `7:31`, `7:38`, `8:3`, `9:4–9:6`).

## Verificação

Executados com sucesso: `:app:compileDebugKotlin`, `:app:testReleaseUnitTest` (82 testes), `:app:assembleDebug`, `:app:assembleRelease`, `:app:lintDebug`, `git diff --check` e `zipalign -c -P 16 -v 4`. O APK final de depuração está em `app/build/outputs/apk/debug/app-debug.apk`, SHA-256 `3162D107A6CC749B82DD93A26D45CBE06266C682E848221B148E54FBCF4E325A`. A validação visual final foi feita no emulador `sdk_gphone16k_x86_64`; nenhuma autorização de Acessibilidade foi automatizada.

## Correção visual após auditoria

O commit `fcc54e1` corrige a superfície raiz sem `fillMaxSize`, causa da tela vazia com a Navigation Bar no centro. Também traduz as telas atuais do projeto Stitch `Gru Visual Lab` para um shell escuro coerente: cabeçalho com marca, cartões grafite, dourado de identidade, ciano de seleção, cores semânticas, seletor Online/Privado, Controle com a coruja oficial, galeria de mascotes e navegação flutuante com item central elevado. Nenhuma máquina de estado ou contrato de runtime foi duplicado.

## Catálogo visual de poses

O fluxo aprovado passou a separar identidade e movimento: foto → três Masters → escolha explícita → geração das 12 poses → nome → seleção visual de pose normal, ouvindo e transcrevendo → instalação. O Modal gera quatro imagens finais por papel uma única vez; o Android valida os 12 checksums, apresenta as galerias e promove somente as três escolhas para o armazenamento privado e para o runtime. A barra de carregamento é indeterminada, acompanhada de etapa real e estimativa inicial de 2–4 minutos; nenhuma porcentagem fictícia é exibida. O polling também cobre a preparação de poses, preservando retomada, cancelamento e idempotência.
