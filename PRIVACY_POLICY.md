# Política de Privacidade do Gru

**Vigência e última atualização:** 31 de julho de 2026

Esta política descreve o comportamento do aplicativo Android **Gru**, identificador `com.pguillen.gru`, mantido neste [repositório](https://github.com/Pguillen87/gru).

## Resumo

- O Gru não opera servidor próprio, não exibe anúncios e não contém telemetria ou rastreamento.
- O áudio gravado é enviado diretamente do aparelho para a Groq usando a chave do próprio usuário.
- Áudio e transcrição não são mantidos em histórico pelo Gru.
- Preferências e chave da Groq ficam no armazenamento privado do aplicativo.
- O serviço de Acessibilidade não registra o que o usuário digita.

## Dados processados

### Áudio

O Gru grava somente após um toque no pet. A captura é escrita como `gru_audio.wav` no cache privado do aplicativo. Quando a gravação termina, o arquivo é enviado por HTTPS para a API de transcrição da Groq e apagado após sucesso ou falha. Cancelar a sessão também remove a captura temporária.

### Transcrição

O texto retornado pela Groq é inserido no campo editável que estiver focado. O Gru não cria banco de dados nem histórico para esse texto.

### Chave e preferências

A chave de API da Groq, pet, tamanho, transparência e estado de ativação são armazenados em `SharedPreferences` privadas. O backup Android está desativado. A chave é enviada somente à Groq no cabeçalho de autenticação da solicitação feita pelo usuário.

## Provedor externo

O único provedor integrado é a **Groq**. Áudio e dados associados à solicitação são tratados de acordo com os termos e a [política de privacidade da Groq](https://groq.com/privacy-policy/). O mantenedor do Gru não recebe essas solicitações. O usuário deve avaliar os termos da Groq antes de usar o serviço.

## Acessibilidade

O serviço de Acessibilidade é necessário para:

- verificar se há um campo editável focado;
- verificar se o teclado está visível;
- posicionar o pet fora da área do teclado;
- inserir a transcrição no cursor ou substituir a seleção.

O pet é ocultado em campos de senha. O Gru não possui teclado próprio, não registra teclas e não transmite o texto já existente no campo para a Groq.

## Permissões

| Permissão ou acesso | Finalidade |
| --- | --- |
| Microfone | Capturar a fala somente durante uma sessão iniciada pelo usuário. |
| Internet | Enviar o WAV temporário à Groq e receber a transcrição. |
| Notificações | Informar claramente quando a gravação está ativa. |
| Serviço em primeiro plano de microfone | Manter a gravação iniciada pelo usuário compatível com as regras recentes do Android. |
| Acessibilidade | Detectar o destino e inserir o texto, conforme descrito acima. |

## Retenção e exclusão

O arquivo de áudio temporário é apagado ao final ou cancelamento da sessão. Preferências e chave permanecem até serem substituídas, limpas pelos ajustes do Android ou removidas com a desinstalação. Eventual retenção pela Groq segue a política e os termos da conta do usuário.

## Segurança

As solicitações usam HTTPS e tráfego sem criptografia está desativado no Manifest. O aplicativo não registra chaves, áudio, transcrições ou conteúdo de tela em logs. Nenhum método de armazenamento ou transmissão elimina todos os riscos; o Gru reduz a exposição ao não operar backend próprio nem manter histórico.

## Crianças e transferências internacionais

O Gru não é direcionado a crianças. A Groq pode impor requisitos de idade e processar dados em outros países conforme seus próprios termos.

## Alterações e contato

Mudanças materiais serão publicadas neste arquivo com uma nova data. Dúvidas e solicitações devem ser abertas na seção [Issues do repositório](https://github.com/Pguillen87/gru/issues).
