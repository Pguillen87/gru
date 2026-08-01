# Gru

**Fale. O Gru escreve.**

Gru é um aplicativo Android de ditado por voz com pet flutuante. Ele mantém o teclado habitual do usuário e aparece somente quando há um campo editável focado e o teclado está visível.

## Modos de transcrição

### Online — Groq

- Exige internet e uma chave de API da Groq.
- Envia o WAV temporário diretamente à Groq.
- Usa menos CPU e memória do celular.
- A chave é criptografada com AES-GCM por uma chave do Android Keystore.

### Privado — Whisper local

- Funciona offline depois da instalação do modelo.
- Não exige chave da Groq.
- Áudio e texto não são enviados para a internet.
- Nunca usa a Groq como fallback automático.
- O modelo é opcional, fica no armazenamento privado e é removido com a desinstalação.

O modelo fixado é `ggml-large-v3-turbo-q5_0.bin`, da revisão `5359861c739e955e79d9a303bcbc70fb988958b1` do repositório oficial `ggerganov/whisper.cpp`. Ele possui `574.041.195` bytes e SHA-256 `394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2`.

> **Limitação medida:** no Samsung A55, o Large V3 Turbo Q5 não concluiu uma transcrição de 11,58 segundos dentro do limite de 15 minutos. O modelo permanece como alvo solicitado, mas não é recomendado para uso interativo nesse aparelho. Consulte [BENCHMARK.md](BENCHMARK.md).

## Funcionalidades

- Gravação iniciada e encerrada pelo pet.
- Inserção no cursor ou substituição do texto selecionado.
- Estados inativo, ouvindo, processando, sucesso e erro.
- Cinco pets: Lume, Faísca, Bip, Pingo e Pudim.
- Tamanho, transparência, arraste e posição por aplicativo.
- Campos de senha ignorados.
- Interface em português do Brasil e inglês.

O Gru não contém teclado próprio, histórico, prompts, reescrita, dicionários, autocorreção, mídia, anúncios, telemetria ou rastreamento.

## Primeiro uso

1. Abra `Transcrição` e escolha Online ou Privado.
2. No Online, salve a chave da Groq. No Privado, inicie conscientemente o download e ative o modo depois da verificação.
3. Em `Geral`, permita Acessibilidade, microfone e notificação.
4. Ative o pet flutuante.
5. Abra outro aplicativo, toque em um campo de texto e toque no pet para falar.
6. Durante a transcrição, toque no pet para cancelar.

## Arquitetura

- `TranscriptionEngineRouter`: seleciona um único gateway no início da sessão.
- `GroqTranscriptionGateway`: integração HTTPS com a Groq.
- `LocalWhisperTranscriptionGateway`: transcrição privada pelo runtime local.
- `WhisperModelManager`: download retomável, espaço, progresso, SHA-256 e promoção atômica.
- `WhisperRuntime`: fila nativa única, carregamento, inferência, métricas e cancelamento.
- `GruSessionCoordinator`: máquina `Idle → Recording → Transcribing → Success/Error` compartilhada pelos motores.
- `GruAccessibilityService`: foco, teclado visível e inserção.
- `GruPetOverlayController`: ciclo de vida e interação do pet.

O núcleo CPU de `whisper.cpp` v1.8.6 é compilado para `arm64-v8a` e `x86_64`. O APK não contém modelo.

## Compilação e testes

Requisitos: JDK 21, Android SDK, NDK `28.2.13676358`, CMake `3.22.1` e `local.properties` configurado.

```powershell
.\gradlew.bat :app:assembleDebug
.\gradlew.bat :app:testDebugUnitTest
.\gradlew.bat :app:lintDebug
.\gradlew.bat :app:assembleRelease
.\gradlew.bat :app:connectedDebugAndroidTest
```

O APK debug é criado em `app/build/outputs/apk/debug/app-debug.apk`. A compilação usa NDK r28 e alinhamento ELF compatível com páginas de 16 KB.

## Origem e licenças

Gru deriva historicamente do [Dictate Keyboard](https://github.com/DevEmperor/DictateKeyboard), referência `7047202ecf0aaee0393f93c1d7c98eddf1631c7a`, e inclui um subconjunto CPU do [whisper.cpp](https://github.com/ggml-org/whisper.cpp). Consulte [NOTICE](NOTICE), [LICENSE](LICENSE) e a licença MIT vendorizada.
