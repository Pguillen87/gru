# Implementação do frontend Compose

## Escopo

Implementação da Parte 3 na branch `feature/frontend-redesign-compose`, derivada do SHA-base `2a1cab011ef77a33a25e4e211420dbf0c03d3429`. A camada visual foi ligada aos estados já existentes; não foram alterados backend, APIs, Firebase, Modal, Groq, Whisper, JNI, CMake ou o overlay.

## Navegação

`GruActivity` agora usa `NavigationBar` Material 3 com cinco destinos: Permissões, Voz, Ligar/Desligar, Mascotes e Puleiro do Gru. O item central tem tratamento visual maior, semântica de aba e abre Controle; ele nunca chama `setEnabled` diretamente.

## Mapeamento de telas

- `GruGeneralScreen`: Permissões, com resumo de conclusão e reavaliação no retorno da tela de Configurações.
- `GruTranscriptionScreen`: Voz, preservando a seleção transacional Online/Groq e Privado/Whisper.
- `GruControlScreen`: estado operacional derivado de `GruPreferences`, permissão de Acessibilidade, microfone, motor e saúde do overlay. Ligar/desligar usa somente `prefs.setEnabled`.
- `GruMascotScreen`: galeria fiel ao Stitch, mascote atual, cinco built-ins reais, importados do Puleiro, ordem persistente, favoritos, remoção com rollback, tamanho e transparência.
- `GruPerchScreen`: entrada por código, resolução versionada, prévia e instalação local de três poses prontas.

## Componentes e acessibilidade

Foram reutilizados os componentes Material 3 existentes e adicionada uma navegação inferior sem alvos menores que 48dp. O item central, estados de Controle e seleção de mascotes expõem semântica de seleção/estado. As telas usam rolagem, `sp`, tema Material 3 com esquemas Light/Dark próprios e RTL. O Dynamic Color foi desativado nesta rodada porque alterava os acentos ciano, dourado e semânticos aprovados no Stitch; a decisão pode ser reavaliada por superfície quando houver equivalência visual. A imagem oficial `brand/gru-brand-master.png` foi empacotada como `gru_brand_master` e renderizada com `ContentScale.Fit`.

## Estados preservados

Não há router paralelo. A segurança da troca de motor continua em `GruPreferences`/`TranscriptionSelectionPolicy`. As classes históricas de criação remota permanecem para preservar contratos e dados, mas nenhuma tela atual instancia `MascotRepository`, retoma ou consulta jobs antigos. Eles permanecem preservados até existir uma política explícita de migração.

## Limitações e pendências

- A versão anterior foi instalada no Samsung A55, mas revelou a falha de layout registrada pelo usuário. A correção final `fcc54e1` foi validada no emulador Android 16 com páginas de 16 KB; o A55 não estava disponível no ADB após a correção e ainda precisa receber este APK.
- Não foram criados vídeos ou screenshots falsos para os tutoriais.
- Pagamento, poses remotas antecipadas e arquivamento continuam fora do escopo.
- O protótipo Figma foi consultado somente em leitura nos nós aprovados (`6:20`, `6:24`, `7:3`, `7:10`, `7:17`, `7:24`, `7:31`, `7:38`, `8:3`, `9:4–9:6`).
- O sexto mascote built-in continua pendente do asset oficial; nenhum item falso ou duplicado foi criado.
- `UnavailableMascotCodeResolver` continua sendo o resolvedor de produção. O Android está preparado para importar, mas ainda não existe serviço real configurado que transforme um código em `MascotImportManifest`.

## Biblioteca de mascotes

A tela usa como referência visual a tela Stitch `0eea9dbbf15e4a24b4eb6d2dea734102` do projeto `Gru Visual Lab`: grade compacta de três colunas no tamanho normal, cards tonais de 12dp, seleção ciano com check e grupos visualmente separados. Em fonte a partir de 150%, a grade passa para duas colunas para preservar nomes, ações e alvos de 48dp.

`Mascotes do Gru` contém somente os cinco recursos oficiais existentes. `Meus mascotes` filtra estritamente `source = code_import`; entradas legadas continuam preservadas no `CustomMascotStore`. Instalação, favorito, reordenação e remoção publicam um novo snapshot por `Flow`, de modo que o retorno do Puleiro atualiza a tela imediatamente. A ordem manual é metadata privada separada do favorito e sobrevive ao reinício do processo.

Na remoção ativa, a seleção muda para Faísca antes do I/O. Se a exclusão não concluir, a seleção customizada anterior é restaurada e o diálogo permanece com uma mensagem recuperável. O overlay e seu mapeamento `IDLE/RECORDING/TRANSCRIBING` não foram alterados.

## Verificação

Na rodada final da biblioteca foram executados com sucesso: `:app:compileDebugKotlin`, `:app:testReleaseUnitTest` (105 testes), `:app:assembleDebug`, `:app:assembleRelease`, `:app:assembleAndroidTest`, `:app:lintDebug`, `git diff --check` e `zipalign -c -P 16 -v 4`. Os quatro testes Compose de `GruMascotScreenTest` também foram executados em aparelho físico, incluindo fonte 200%, RTL, semântica de seleção e ações do mascote importado. O APK de depuração final foi instalado e aberto pelo ADB; está em `app/build/outputs/apk/debug/app-debug.apk`, SHA-256 `2EB8498EB6950E1BC5B6525E465CF7C848ED751109E924163270F7669E2C3498`. Nenhuma autorização de Acessibilidade foi automatizada.

## Correção visual após auditoria

O commit `fcc54e1` corrige a superfície raiz sem `fillMaxSize`, causa da tela vazia com a Navigation Bar no centro. Também traduz as telas atuais do projeto Stitch `Gru Visual Lab` para um shell escuro coerente: cabeçalho com marca, cartões grafite, dourado de identidade, ciano de seleção, cores semânticas, seletor Online/Privado, Controle com a coruja oficial, galeria de mascotes e navegação flutuante com item central elevado. Nenhuma máquina de estado ou contrato de runtime foi duplicado.

## Correções pós-implementação

- Permissões pendentes usam atenção/dourado; sucesso permanece verde e erro real usa vermelho.
- Voz distingue motor solicitado/preparando do motor realmente ativo. A política transacional continua impedindo fallback silencioso para Groq.
- A navegação principal passa a depender da conclusão persistida do onboarding, não da existência momentânea de um motor ativo. Assim, preparar o modo Privado não desmonta o rodapé.
- O tutorial de Acessibilidade apresenta quatro passos e obtém o nome `Pet flutuante do Gru` do mesmo recurso usado pelo Manifest.
- O tutorial Groq possui passos escritos, espaço explicitamente reservado ao vídeo oficial, link oficial e leitura do clipboard somente após toque em `Colar chave`.

## Observabilidade de criação de mascote

Cada nova tentativa recebe um `creationTraceId` aleatório, curto e independente do UID. `MascotTelemetry` centraliza os eventos e usa relógio monotônico para durações. Eventos detalhados de preparação, autenticação, App Check, HTTP e polling são emitidos apenas em `BuildConfig.DEBUG`; início, conclusão, falha, cancelamento e instalação permanecem sanitizados e adequados a produção.

Esta seção registra a rodada histórica de diagnóstico. A rota móvel correspondente foi posteriormente desacoplada pelo Puleiro do Gru; nenhum relatório com dados temporários de criação integra a entrega nova.

## Puleiro do Gru

A estratégia posterior substitui a rota móvel de geração pelo `GruPerchScreen`. O Android agora contém contratos e armazenamento para importar um pacote pronto por código; a criação pesada foi movida para uma futura aplicação Web. O destino antigo deixou de ser roteado, mas as classes históricas de API/geração foram preservadas sem uso para evitar apagar contratos úteis antes da etapa Web.

O resolvedor de produção é deliberadamente indisponível até existir configuração real. A tela responde “O Puleiro ainda está sendo preparado”, sem localhost, domínio inventado ou sucesso falso. Fakes existem apenas nos testes.

`MascotImportCoordinator` concentra e serializa os estados; `MascotPackageInstaller` baixa e verifica três poses; `CustomMascotStore` promove atomicamente, detecta duplicidade, persiste favoritos sem tocar nas imagens e permite remoção segura com fallback para Faísca quando o pacote estava ativo. A chave local usa SHA-256 do par `mascotId + packageVersion`, sem colisões por sanitização. URLs locais/privadas, credenciais embutidas, portas alternativas e redirects inseguros são recusados. A telemetria `GruPerch` registra apenas trace aleatório, evento, duração e resultado estrutural — nunca código, URL ou imagem.

## Ocultar nesta conversa

O overlay agora resolve uma `OverlayEnvironment` com insets, IME e limites do editor, e aplica uma política pura de posicionamento seguro. O gesto de arraste mostra uma zona visual separada acima do teclado; entrar combina ícone, texto, tint vermelho e haptic único. A máquina `OverlayInteractionState` permanece independente de `GruDictationState`.

O contexto usa apenas metadados estruturais e uma chave SHA-256 salgada por sessão. Não são lidos ou registrados contato, título, mensagem ou texto digitado. IDs suficientes geram identidade estrutural estável; caso contrário, a geração da janela produz fallback efêmero para evitar ocultar todo um aplicativo. `ConversationSuppressionSession` não persiste em disco e é reiniciado junto com o serviço. Controle mostra somente contador e ação global de recuperação.
