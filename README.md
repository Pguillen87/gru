# Gru

**Fale. O Gru escreve.**

Gru é um aplicativo Android de ditado por voz com pet flutuante. Ele mantém o teclado habitual do usuário e aparece somente quando há um campo editável focado e o teclado está visível.

## Funcionalidades

- Gravação iniciada e encerrada pelo pet.
- Transcrição pela API da Groq.
- Inserção no cursor ou substituição do texto selecionado.
- Estados visuais: inativo, ouvindo, processando, sucesso e erro.
- Cinco pets: Lume, Faísca, Bip, Pingo e Pudim.
- Tamanho, transparência, arraste e posição por aplicativo.
- Campos de senha ignorados.
- Interface em português do Brasil e inglês.

O Gru não contém teclado próprio, histórico de ditados, prompts, reescrita, dicionários, autocorreção, mídia, anúncios, telemetria ou rastreamento.

## Primeiro uso

1. Abra o Gru e ative o serviço de Acessibilidade.
2. Permita microfone e notificações.
3. Informe uma chave de API da Groq.
4. Ative o pet flutuante.
5. Abra outro aplicativo e toque em um campo de texto.
6. Toque no pet para falar e toque novamente para transcrever.

## Privacidade

O serviço de Acessibilidade é usado para detectar o campo focado e inserir a transcrição. O áudio é salvo temporariamente no cache privado, enviado diretamente do aparelho para a Groq e apagado ao final da sessão. A chave fica no armazenamento privado do aplicativo. Consulte [PRIVACY_POLICY.md](PRIVACY_POLICY.md).

## Arquitetura

- `GruActivity`: configuração e onboarding.
- `GruAccessibilityService`: foco, teclado visível e inserção.
- `GruPetOverlayController`: ciclo de vida e interação do overlay.
- `GruSessionCoordinator`: máquina de estados da sessão.
- `AndroidAudioRecorder`: captura PCM e arquivo WAV temporário.
- `GroqTranscriptionClient`: requisição HTTPS para a Groq.

O projeto possui somente o módulo Android `:app`.

## Compilação e testes

Requisitos: JDK 21, Android SDK e `local.properties` configurado.

```powershell
.\gradlew.bat :app:assembleDebug
.\gradlew.bat :app:testDebugUnitTest
.\gradlew.bat :app:lintDebug
.\gradlew.bat :app:assembleRelease
```

O APK debug é criado em `app/build/outputs/apk/debug/app-debug.apk`.

Para testes instrumentados com um aparelho ou emulador conectado:

```powershell
.\gradlew.bat :app:connectedDebugAndroidTest
```

## Projeto de origem

Gru é uma adaptação independente do [Dictate Keyboard](https://github.com/DevEmperor/DictateKeyboard), historicamente baseado no [FlorisBoard](https://github.com/florisboard/florisboard). A referência de origem declarada é o commit `7047202ecf0aaee0393f93c1d7c98eddf1631c7a`.

Este projeto não é uma versão oficial dos projetos originais. Consulte [NOTICE](NOTICE) e [LICENSE](LICENSE).
