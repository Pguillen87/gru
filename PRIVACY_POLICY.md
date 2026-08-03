# Política de Privacidade do Gru

**Vigência e última atualização:** 1º de agosto de 2026

Esta política descreve o aplicativo Android **Gru**, identificador `com.pguillen.gru`, mantido neste [repositório](https://github.com/Pguillen87/gru).

## Resumo

- O Gru não opera servidor próprio, não exibe anúncios e não contém telemetria.
- No modo **Online**, o áudio é enviado diretamente à Groq.
- No modo **Privado**, áudio e transcrição permanecem no aparelho e nunca há fallback automático para Groq.
- Áudio e transcrição não são mantidos em histórico.
- A chave Groq é criptografada com uma chave do Android Keystore.

## Áudio e transcrição

O Gru grava somente após um toque no pet. A captura é escrita como WAV no cache privado. Depois da transcrição, falha ou cancelamento, o arquivo temporário é apagado. O texto resultante é inserido no campo focado e não é salvo em banco de dados.

### Online — Groq

O WAV temporário é enviado por HTTPS à API da Groq usando a chave do usuário. O tratamento pela Groq segue seus [termos e política de privacidade](https://groq.com/privacy-policy/). O mantenedor do Gru não recebe a solicitação.

### Privado — Whisper local

O WAV é processado pelo `whisper.cpp` dentro do aparelho. O Gru não envia áudio ou texto à Groq e não realiza fallback online quando a inferência local falha. Mudar para Online exige ação explícita.

## Modelo offline

O modelo não faz parte do APK ou AAB. Quando o usuário solicita o download, o Gru acessa uma revisão fixa do repositório oficial `ggerganov/whisper.cpp` no Hugging Face. O modelo Small Q5_1 possui `190.085.487` bytes e checksum SHA-256 fixado.

O download usa um arquivo `.part` controlado pelo aplicativo, pode ser retomado após interrupção de rede e só é promovido após validação. O modelo final fica em `filesDir/whisper-models`, armazenamento privado removido automaticamente na desinstalação. O usuário também pode removê-lo pela tela `Transcrição`.

## Chave e preferências

A chave Groq é cifrada com AES-GCM. A chave criptográfica não é exportável e fica no Android Keystore; apenas o texto cifrado fica em `SharedPreferences` privadas. Instalações antigas com chave em texto simples são migradas e a cópia antiga é removida após confirmação. Pet, tamanho, transparência e escolha do motor permanecem em preferências privadas. O backup Android está desativado.

## Acessibilidade

O serviço de Acessibilidade verifica campo focado e teclado visível, posiciona o pet e insere a transcrição. O pet é ocultado em senhas. O Gru não possui teclado próprio, não registra teclas e não transmite o texto já existente no campo.

## Permissões e rede

| Permissão ou acesso | Finalidade |
| --- | --- |
| Microfone | Capturar fala durante sessão iniciada pelo usuário. |
| Internet | Usar Groq no Online ou baixar o modelo após solicitação no Privado. |
| Notificações | Informar quando a gravação está ativa. |
| Serviço em primeiro plano | Manter a gravação compatível com as regras do Android. |
| Acessibilidade | Detectar o destino e inserir o texto. |

## Segurança e retenção

Tráfego sem criptografia está desativado. O Gru não registra chaves, áudio, transcrições ou conteúdo de tela. WAV e arquivos de download inválidos são removidos; uma parte interrompida por rede permanece somente para retomada controlada. Preferências, chave cifrada e modelo permanecem até remoção pelo usuário, limpeza dos dados ou desinstalação.

## Alterações e contato

Mudanças materiais serão publicadas neste arquivo. Dúvidas e solicitações podem ser abertas nas [Issues do repositório](https://github.com/Pguillen87/gru/issues).
