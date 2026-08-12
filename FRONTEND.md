# Frontend do GRU Android

Guia de arquitetura e manutenção do frontend. A referência visual normativa está em [`DESIGN.md`](DESIGN.md); este documento explica onde o comportamento vive e como evoluir a interface sem quebrar o runtime.

## 1. Escopo

> Direção vigente: o Android não gera mais mascotes. O quinto destino é **Puleiro do Gru** e importa por código um pacote pronto com exatamente três poses. As seções históricas sobre criação por foto permanecem abaixo apenas como registro da integração desacoplada e não descrevem uma rota acessível na interface atual.

O frontend é um app Android em Kotlin/Jetpack Compose com um serviço de acessibilidade que desenha o pet flutuante sobre o teclado. Ele não substitui o teclado e não mantém histórico de ditado.

Responsabilidades da UI:

- onboarding e escolha do motor de transcrição;
- permissões, status operacional e configuração;
- seleção de mascote built-in ou personalizado;
- importação de mascote pronto por código;
- persistência local, retomada e fallback offline;
- resolução visual do pet nos estados de execução.

Fora do escopo da UI:

- inferência de imagem no aparelho;
- execução de GPU em runtime;
- armazenamento de token Modal ou credencial administrativa;
- alteração do contrato do servidor sem compatibilidade documentada.

## 2. Mapa de arquivos

| Área | Arquivo | Responsabilidade |
| --- | --- | --- |
| Composição | `app/src/gru/kotlin/com/pguillen/gru/GruActivity.kt` | Scaffold, marca, abas e roteamento de alto nível. |
| Geral | `GruGeneralScreen.kt` | Estado geral, permissões e saúde do overlay. |
| Transcrição | `GruTranscriptionScreen.kt` | Online/Groq, Privado/Whisper e configuração do modelo. |
| Mascote | `GruMascotScreen.kt` | Galerias, aparência, criação, aprovação e recuperação. |
| Puleiro | `GruPerchScreen.kt` | Código, estados de resolução, confirmação e instalação. |
| Importação | `mascot/importing/` | Contrato v1, resolvedor, downloader, verificador, coordenador e telemetria. |
| Preferências | `GruPreferences.kt` | Estado persistente pequeno: seleção, tamanho, opacidade e job pendente. |
| Fonte visual | `mascot/MascotVisualResolver.kt` | Mapeia fonte + estado de runtime para atlas/arquivo local. |
| Pacotes locais | `mascot/CustomMascotStore.kt` | Manifest, checksum, staging, promoção atômica, nomes e remoção. |
| API | `mascot/MascotApi.kt` | DTOs, headers de autenticação/App Check e erros estruturados. |
| Orquestração | `mascot/MascotCreation.kt` | Repository, polling, idempotência, estados e mensagens de recuperação. |
| Foto | `mascot/MascotPhotoPreparer.kt` | Leitura, validação, orientação, escala e preparação para upload. |
| Overlay | `overlay/GruPetOverlayController.kt` | Janela flutuante, posição, tamanho e estado do pet. |
| Renderização | `overlay/LivingPetView.kt` | Atlas, imagem personalizada, animação e geometria proporcional. |

## 3. Navegação e lifecycle

`GruActivity` observa o motor configurado:

1. Sem motor: mostra `GruTranscriptionScreen` em modo de primeiro uso.
2. Com motor: mostra `PrimaryTabRow` com `GENERAL`, `TRANSCRIPTION` e `MASCOT`.
3. `onResume` incrementa `permissionRefresh` para atualizar permissões e saúde do serviço.

As telas recebem o padding do `Scaffold`, aplicam `verticalScroll` quando necessário e não devem assumir uma altura fixa. O Back do sistema é tratado pela Activity/Compose; uma tela não deve capturar o gesto para impedir o retorno nativo.

## 4. Catálogo da interface atual

Esta seção é um inventário do que existe hoje. Ela descreve a distribuição atual, não uma recomendação de redesign. A próxima remodelação pode mover responsabilidades, mas deve preservar os contratos de estado e as regras de segurança descritas depois.

### Cabeçalho compartilhado

Presente nas três áreas depois do onboarding:

- `TopAppBar` com o ícone completo do Gro em 48dp e o nome `Gru`.
- `PrimaryTabRow` com três destinos: `Geral`, `Transcrição` e `Mascote`.
- Aba selecionada indicada pelo componente Material; o conteúdo recebe o padding do `Scaffold`.
- No primeiro uso, as abas ainda não aparecem: a pessoa permanece na configuração inicial de Transcrição.

### Aba Geral

Arquivo: `GruGeneralScreen.kt`.

Objetivo atual: mostrar se o aplicativo está operacional e resolver permissões necessárias ao pet/transcrição.

| Bloco atual | Informação exibida | Ações |
| --- | --- | --- |
| Resumo de status | Motor configurado, Acessibilidade, serviço conectado, microfone e saúde do overlay | Nenhuma ação direta; orienta a próxima pendência. |
| Permissões | Acessibilidade, microfone e notificações (Android 13+) | Abrir Configurações de Acessibilidade ou solicitar permissão do sistema. |
| Estado do pet/runtime | Situação do serviço e primeiro quadro renderizado | Tentar novamente quando o overlay falha. |

Responsabilidades que não devem ser duplicadas aqui no estado atual: galeria de mascotes, criação por foto, nome personalizado, tamanho e opacidade. Esses controles pertencem à aba Mascote.

### Aba Transcrição

Arquivo: `GruTranscriptionScreen.kt`.

Objetivo atual: escolher e preparar o motor que será usado pela sessão de ditado.

| Bloco atual | Informação exibida | Ações |
| --- | --- | --- |
| Motor atual | Online/Groq ou Privado/Whisper, com estado de preparação | Trocar de motor quando os pré-requisitos estiverem prontos. |
| Escolha Online | Benefícios, exigência de internet e status da chave | Abrir configuração da chave Groq. |
| Chave Groq | Chave presente/ausente e aviso de privacidade | Criar chave no site oficial, colar, salvar, alterar ou remover. |
| Escolha Privado | Processamento local, armazenamento e bateria | Baixar, ativar ou remover o modelo local. |
| Modelo offline | Nome, tamanho, origem e estado: não instalado, baixando, verificando, instalado ou erro | Iniciar, cancelar, repetir download, ativar ou remover. |
| Diálogo da chave | Campo protegido, colar após ação explícita e confirmação | Salvar somente valor não vazio ou cancelar. |

Regra de transição: Online sem chave não é ativado; Privado sem modelo verificado não é ativado. Não existe fallback silencioso entre eles.

### Aba Mascote

Arquivo: `GruMascotScreen.kt`.

Objetivo atual: selecionar o visual ativo, gerenciar mascotes personalizados e iniciar uma criação por foto.

| Bloco atual | Informação exibida | Ações |
| --- | --- | --- |
| Meu mascote | Preview do mascote ativo, nome/tipo e status de ativação | Ativar/desativar o pet. |
| Meus mascotes | Cards dos personalizados aprovados, nome e imagem de preview | Selecionar um; abrir caneta para editar somente o nome. |
| Mascotes do Gru | Lume, Faísca, Bip, Pingo e Pudim | Selecionar um built-in sem apagar personalizados. |
| Criar meu mascote | Texto explicativo e painel variável por estado | Escolher foto, confirmar, acompanhar, aprovar Master, cancelar ou tentar novamente. |
| Escolha de Master | Grade dinâmica de opções retornadas pelo Modal | Selecionar uma opção visual; informar nome obrigatório; aprovar. |
| Aparência | Pequeno, Médio, Grande e slider de opacidade | Alterar escala e transparência persistidas. |
| Poses | Texto de disponibilidade do pacote | Preparado para lista dinâmica; depende de poses instaladas. |

#### Estados visíveis do painel de criação

| Estado | Significado para a pessoa | Ações disponíveis |
| --- | --- | --- |
| `Idle` | Nenhuma foto selecionada | Escolher foto. |
| `PhotoSelected` | Foto pronta para confirmação | Usar esta foto, escolher outra ou cancelar. |
| `Submitting` | Foto sendo validada/enviada | Aguardar. |
| `GenerationPaused` | Job salvo, geração aguardando habilitação/continuação | Continuar quando permitido ou cancelar. |
| `Tracking` | Modal processando o job | Acompanhar ou cancelar. |
| `AwaitingMasterApproval` | Opções de Master disponíveis | Escolher, nomear e aprovar; descartar opções. |
| `PosePreparationPending` | Master aprovado, poses ainda pendentes | Criar outro mascote. |
| `InstallingMascot` | Resultado baixando e sendo validado localmente | Aguardar. |
| `Completed` | Pacote promovido e mascote selecionável | Continuar usando o app. |
| `NetworkUnavailable` | A conexão local falhou, job preservado | Tentar acompanhar novamente ou cancelar. |
| `RemoteFailed` | Servidor recusou/falhou | Escolher outra foto ou tentar novamente conforme o erro. |
| `InstallFailed` | Download/checksum/promoção local falhou | Repetir instalação sem criar novo job. |
| `CancelPending` / `Canceled` | Cancelamento aguardando confirmação ou concluído | Tentar sincronizar ou escolher nova foto. |

#### Diálogos e confirmações

- **Confirmação da foto:** preview, dica sobre a imagem, `Usar esta foto`, `Escolher outra foto` e `Cancelar`.
- **Escolha do Master:** grade com preview real quando disponível; sem imagem, o card não é selecionável.
- **Nome do mascote:** obrigatório na aprovação; normalizado e limitado a 32 caracteres.
- **Editar nome:** diálogo aberto pela caneta do card; salva apenas `displayName` no manifest local.

### Overlay fora da Activity

O pet flutuante não é uma quarta aba. Ele é desenhado pelo `GruAccessibilityService` quando há campo editável focado, teclado visível e motor pronto.

| Estado de runtime | Visual resolvido |
| --- | --- |
| `IDLE` | Pose normal escolhida. |
| `RECORDING` | Pose ouvindo e sinal de gravação. |
| `TRANSCRIBING` | Pose processando. |
| Sucesso/erro | Feedback curto do atlas built-in, quando aplicável. |

O overlay funciona sem rede depois que o pacote personalizado foi promovido. A troca de pose não chama Modal.

### Posição segura e ocultação por conversa

`OverlayPlacementPolicy` mantém o pet dentro dos insets e fora do IME e do editor focado. Uma posição escolhida pelo usuário é reutilizada quando segura; caso teclado, rotação, tamanho ou editor criem colisão, o controller move o pet uma vez para o ponto válido mais próximo.

O arraste possui uma máquina visual separada do ditado. Durante o gesto, uma segunda janela não tocável mostra “Ocultar nesta conversa”; soltar dentro da zona adiciona uma chave opaca ao `ConversationSuppressionSession`. `prefs.enabled`, motor e `GruDictationState` não são modificados. Gravação e transcrição bloqueiam o gesto de ocultação.

`StructuralConversationContextResolver` não lê texto, título, contato nem mensagem. Quando há IDs estruturais estáveis, a chave pode distinguir o retorno ao mesmo contexto; sem isso, usa identidade efêmera por geração de janela e não finge precisão. Todo o estado é somente em memória e é limpo quando o serviço reinicia. Controle expõe apenas contador e “Mostrar novamente”, sem nomes de aplicativos ou pessoas.

## 5. Biblioteca de mascotes

`GruMascotScreen` segue a galeria aprovada no Stitch e organiza a tela nesta ordem:

1. **Mascote atual:** preview com proporção preservada, nome e origem.
2. **Mascotes do Gru:** Lume, Faísca, Bip, Pingo e Pudim. São os cinco assets oficiais existentes, sempre offline, selecionáveis e nunca removíveis. A grade de três colunas já comporta o sexto mascote planejado, mas nenhum placeholder é exibido enquanto o asset oficial não existir.
3. **Meus mascotes:** somente pacotes com `source = code_import`, trazidos pelo Puleiro. Legados permanecem no armazenamento e não são misturados automaticamente.
4. **Aparência:** Pequeno, Médio, Grande e transparência de 40% a 100%; ambas as preferências atualizam o preview e o overlay real.

Favorito e ordem manual são metadados independentes. A ordem persiste em arquivo privado próprio, não renomeia imagens e não é alterada ao favoritar. O menu de cada importado permite mover para antes/depois e remover, inclusive por TalkBack. Se a remoção do mascote ativo falhar, a seleção anterior é restaurada.

## 6. Fluxo do Puleiro

A criação pesada de mascotes não acontece no Android. O fluxo móvel é:

```text
Código do mascote
  -> resolução do manifesto v1
  -> prévia e confirmação
  -> download das três poses
  -> verificação de bytes, MIME, imagem e SHA-256
  -> promoção atômica
  -> Meus mascotes
```

Os estados são explícitos (`Idle`, `Resolving`, `PreviewReady`, `Downloading`, `Verifying`, `Installing`, `Installed` e falhas recuperáveis). O clipboard só é lido após toque em “Colar código”, e o download nunca começa apenas por colar ou buscar.

Nesta versão, `UnavailableMascotCodeResolver` retorna `NotConfigured`: a UI e o protocolo estão prontos, mas ainda não existe serviço Web/endpoint de produção. Fakes existem somente em testes.

## 7. Rede e infraestrutura histórica

O Puleiro não possui endpoint real configurado e não inventa backend, localhost ou sucesso. Quando o serviço Web existir, a implementação de `MascotCodeResolver` deverá usar HTTPS, timeout, erros estruturados, política de origem e o `schemaVersion` já definido.

`MascotApi`, Firebase Auth/App Check e as classes da antiga geração móvel permanecem apenas como infraestrutura histórica desacoplada da navegação e da tela Mascotes. A biblioteca não abre polling, não retoma jobs e não chama esse backend.

## 8. Persistência e offline

`GruPreferences` guarda apenas IDs e preferências pequenas. Imagens e manifests ficam em `filesDir/mascots/<poseSetId>/`:

```text
manifest.json
master.png                 # fallback antes das poses, quando disponível
pose_01.png ... pose_N.png
```

`CustomMascotStore` escreve em staging, valida nomes, IDs e SHA-256 e promove atomicamente. O pacote antigo continua ativo se qualquer download, checksum ou gravação falhar. Depois da promoção, `MascotVisualResolver` resolve tudo localmente; trocar entre `IDLE`, `RECORDING` e `TRANSCRIBING` nunca usa rede.

## 9. Tamanhos e overlay

`GruPetSize` é a única escala compartilhada:

| Opção | Escala | Uso |
| --- | ---: | --- |
| Pequeno | 0,78 | overlay e preview |
| Médio | 1,00 | baseline |
| Grande | 1,24 | overlay e preview |

O overlay usa caixa-base média de 120dp e conteúdo de 108dp. `LivingPetView` mantém `ContentScale.Fit` para imagens personalizadas e centraliza/ancora conforme a geometria da imagem. Se uma imagem customizada faltar ou falhar no checksum, o resolver recua para Faísca como built-in seguro.

## 10. Acessibilidade e qualidade

- Áreas de toque têm no mínimo 48dp.
- Cards usam semântica de seleção/radio button.
- Imagens informativas têm descrição; imagens decorativas não repetem texto.
- Testar TalkBack, claro/escuro, fonte 200%, RTL e telas compactas.
- Não comunicar estados apenas por cor; combinar texto, pose e affordance.
- Respeitar animações reduzidas: transições devem ser instantâneas ou discretas.

## 11. Testes e validação

Comandos principais:

```powershell
.\gradlew.bat :app:assembleDebug
.\gradlew.bat :app:testReleaseUnitTest
git diff --check
```

Testes unitários cobrem API, DTOs, erros, idempotência, retomada, ownership local, checksum, promoção atômica, resolver visual e fallback. Testes instrumentados devem validar navegação, seleção e comportamento em dispositivo real quando houver aparelho conectado.

Antes de alterar uma tela, validar:

1. estado vazio e estado carregado;
2. loading, retry, cancelamento e erro;
3. fonte 200% e modo escuro;
4. rolagem sob a barra de abas e barras do sistema;
5. mascote atual preservado quando uma criação nova falhar.

## 12. Regras de evolução

### Puleiro do Gru

- `MascotImportCode` normaliza a entrada sem expor a composição do catálogo remoto.
- `MascotImportManifest` exige `schemaVersion = 1`, identidade estável e as funções `NORMAL`, `LISTENING` e `TRANSCRIBING`.
- `UnavailableMascotCodeResolver` é a implementação de produção enquanto não houver endpoint real; a UI informa que o Puleiro está em preparação.
- Downloads aceitam somente HTTPS, MIME de imagem permitido, limite de 8 MiB por asset, bytes esperados, SHA-256 e imagem decodificável.
- As três poses são verificadas em memória e promovidas em conjunto pelo `CustomMascotStore`; falha em uma impede instalação parcial.
- Pacotes locais antigos continuam legíveis. Favorito é sidecar local e não regrava imagens.
- A biblioteca observa mudanças do `CustomMascotStore`; uma instalação concluída no Puleiro aparece em “Meus mascotes” sem reiniciar Activity ou processo.
- Remover o mascote ativo seleciona Faísca antes de apagar o pacote; se a exclusão falhar, restaura a seleção anterior. Built-ins nunca oferecem remoção.

- Não mover lógica de criação para `GruActivity`.
- Não duplicar seleção/tamanho/opacidade em Geral e Mascote.
- Não hardcodar seis poses na UI; renderizar a lista do manifest.
- Não acoplar o runtime visual a nomes de drawable ou ao provider remoto.
- Não adicionar logging de foto, áudio, texto ditado, token ou URL assinada.
- Toda mudança visual deve atualizar `DESIGN.md` quando alterar tokens, componentes ou guardrails.
