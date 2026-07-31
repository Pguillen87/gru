# Gru

**Fale. O Gru escreve.**

Gru e um aplicativo Android de ditado por voz com um pet flutuante. O pet aparece somente quando existe um campo de texto focado e o teclado esta visivel. Um toque inicia a gravacao; ao terminar, a transcricao e inserida diretamente no campo selecionado.

## Funcionalidades

- Mantem o teclado preferido do usuario, incluindo o Teclado Samsung.
- Pet flutuante visivel apenas durante a digitacao.
- Transcricao de voz diretamente no campo com foco.
- Sinalizacao clara durante gravacao e processamento.
- Cinco pets animados: Lume, Faisca, Bip, Pingo e Pudim.
- Tamanho e transparencia configuraveis.
- Interface principal em portugues do Brasil.

## Privacidade

O servico de Acessibilidade e usado para detectar o campo editavel focado e inserir a transcricao. Campos de senha sao ignorados. Consulte [PRIVACY_POLICY.md](PRIVACY_POLICY.md) para os detalhes do tratamento de dados e dos provedores de transcricao.

## Compilacao

Requisitos:

- Android SDK configurado em `local.properties`.
- JDK compativel com a versao do Gradle Wrapper do projeto.
- Bash e Python 3 para preparar as bibliotecas nativas de transcricao local.

Em um clone novo, baixe as dependencias nativas reproduziveis:

```bash
bash tools/fetch-sherpa-onnx.sh
```

No Windows, gere o APK de depuracao com:

```powershell
.\gradlew.bat :app:assembleDebug --no-daemon --max-workers=1
```

O APK sera criado em `app/build/outputs/apk/debug/app-debug.apk`.

Para executar os testes do modulo de ditado:

```powershell
.\gradlew.bat :app:testDebugUnitTest --tests "dev.patrickgold.florisboard.dictate.*" --no-daemon --max-workers=1
```

## Projeto de origem

Gru e uma adaptacao de codigo aberto do [Dictate Keyboard](https://github.com/DevEmperor/DictateKeyboard), construido sobre o [FlorisBoard](https://github.com/florisboard/florisboard). Os avisos de autoria e a licenca Apache 2.0 foram preservados em [LICENSE](LICENSE) e [NOTICE](NOTICE).

Este repositorio e um fork independente e nao representa uma versao oficial dos projetos originais.
