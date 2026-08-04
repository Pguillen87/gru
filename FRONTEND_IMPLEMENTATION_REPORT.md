# Implementação do frontend Compose

## Escopo

Implementação da Parte 3 na branch `feature/frontend-redesign-compose`, derivada do SHA-base `2a1cab011ef77a33a25e4e211420dbf0c03d3429`. A camada visual foi ligada aos estados já existentes; não foram alterados backend, APIs, Firebase, Modal, Groq, Whisper, JNI, CMake ou o overlay.

## Navegação

`GruActivity` agora usa `NavigationBar` Material 3 com cinco destinos: Permissões, Voz, Ligar/Desligar, Mascotes e Criar mascote. O item central tem tratamento visual maior, semântica de aba e abre Controle; ele nunca chama `setEnabled` diretamente.

## Mapeamento de telas

- `GruGeneralScreen`: Permissões, com resumo de conclusão e reavaliação no retorno da tela de Configurações.
- `GruTranscriptionScreen`: Voz, preservando a seleção transacional Online/Groq e Privado/Whisper.
- `GruControlScreen`: estado operacional derivado de `GruPreferences`, permissão de Acessibilidade, microfone, motor e saúde do overlay. Ligar/desligar usa somente `prefs.setEnabled`.
- `GruMascotScreen(MascotFocus.LIBRARY)`: biblioteca, seleção, edição de nome, tamanho e opacidade.
- `GruMascotScreen(MascotFocus.CREATE)`: mesma state machine/repositório de criação, exibida como jornada separada.

## Componentes e acessibilidade

Foram reutilizados os componentes Material 3 existentes e adicionada uma navegação inferior sem alvos menores que 48dp. O item central, estados de Controle e seleção de mascotes expõem semântica de seleção/estado. As telas usam rolagem, `sp`, tema Material 3 e Dynamic Color já existente, mantendo claro/escuro e RTL. A imagem oficial `brand/gru-brand-master.png` foi empacotada como `gru_brand_master` e renderizada com `ContentScale.Fit`.

## Estados preservados

Não há router paralelo. A segurança da troca de motor continua em `GruPreferences`/`TranscriptionSelectionPolicy`; a criação continua em `MascotRepository` e `MascotCreationState`, incluindo retomada, retry, cancelamento e idempotência.

## Limitações e pendências

- Não foi feita validação física no Samsung A55 nesta execução.
- Não foram criados vídeos ou screenshots falsos para os tutoriais.
- Pagamento, poses remotas antecipadas e arquivamento continuam fora do escopo.
- O protótipo Figma foi consultado somente em leitura nos nós aprovados (`6:20`, `6:24`, `7:3`, `7:10`, `7:17`, `7:24`, `7:31`, `7:38`, `8:3`, `9:4–9:6`).

## Verificação

Executados com sucesso: `:app:compileDebugKotlin`, `:app:testReleaseUnitTest` e `git diff --check`. Builds release/debug completos, lint, validação 16 KB e teste físico devem ser executados no ambiente de auditoria antes da publicação final.
