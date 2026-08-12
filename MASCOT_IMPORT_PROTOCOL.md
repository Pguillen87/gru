# Protocolo de importação — Puleiro do Gru

## Decisão de produto

A criação de mascotes acontecerá futuramente na Web. O Android não envia foto, não executa geração e não oferece pagamento. Ele importa por código um pacote pronto com exatamente três poses operacionais.

## Código

`MascotImportCode` é uma referência curta, normalizada e opaca. O formato aceito pelo aplicativo não codifica nome nem números de pose como contrato. Um exemplo humano como `BOB-12-15-16` não define a API futura.

## Manifesto v1

`MascotImportManifest` contém:

- `schemaVersion = 1`;
- `mascotId` e `packageVersion` independentes do nome exibido;
- `displayName` e `visibility` (`PUBLIC` ou `PRIVATE`);
- referência de prévia;
- exatamente três assets com funções `NORMAL`, `LISTENING` e `TRANSCRIBING`;
- metadados opcionais não operacionais.

Cada asset informa `poseId`, URL HTTPS, SHA-256, bytes esperados, MIME e dimensões opcionais. Versões incompatíveis resultam em `UnsupportedManifest`. Códigos privados poderão futuramente resultar em `AUTH_REQUIRED`/`ACCESS_DENIED`, sem criar login nesta rodada.

## Resolução

`MascotCodeResolver` separa a UI do serviço futuro. A implementação de produção atual, `UnavailableMascotCodeResolver`, não chama rede e informa que o Puleiro está em preparação. Não existe endpoint falso, localhost, Supabase, VPS ou Firebase Storage novo. Implementações fake são restritas aos testes.

Jobs pendentes do fluxo móvel anterior não são apagados. A Biblioteca não instancia mais o repositório remoto, não retoma polling e não promove resultados invisivelmente; qualquer migração futura desses jobs exige uma política separada.

## Download e integridade

O usuário confirma `Baixar mascote`; colar ou buscar nunca inicia download automaticamente. O instalador baixa somente as três poses escolhidas, uma vez cada, e valida:

- HTTP bem-sucedido e HTTPS;
- até 8 MiB por asset;
- MIME `image/png`, `image/jpeg` ou `image/webp`;
- número exato de bytes;
- SHA-256;
- imagem decodificável;
- dimensões quando declaradas.

URLs precisam ser HTTPS públicas, sem credenciais, fragmentos, porta alternativa ou host local/privado. Redirects são validados e limitados. Quando o serviço real existir, o downloader aceita uma política de origem injetável para restringir os hosts autorizados.

Nenhum pacote é promovido se uma pose falhar. Os bytes verificados são entregues juntos ao armazenamento, que usa staging, troca atômica e restaura backup em falha.

## Armazenamento e migração

O armazenamento privado existente em `filesDir/mascots` foi evoluído; não existe uma segunda biblioteca. Pacotes antigos continuam legíveis porque os novos campos possuem defaults compatíveis. Um importado usa uma chave local derivada de `mascotId + packageVersion`, enquanto o manifesto preserva ambos separadamente.

Metadados mínimos: identidade, versão, nome, origem, três poses, favorito, ordem da biblioteca e instante de instalação. Favorito usa arquivo sidecar e não altera imagens. A ordem manual usa metadata privada própria e não compete com favorito. Duplicidade compara `mascotId`, `packageVersion` e checksums.

Depois da promoção atômica, o `CustomMascotStore` notifica seus observadores. Assim, navegar do Puleiro para Mascotes mostra imediatamente o novo item em `Meus mascotes`, sem reiniciar o aplicativo. Essa seção aceita apenas `source = code_import`; pacotes históricos continuam preservados, mas não são classificados como importações por código.

## Runtime e remoção

O overlay permanece inalterado:

- `IDLE → NORMAL`;
- `RECORDING → LISTENING`;
- `TRANSCRIBING → TRANSCRIBING`.

Ao remover o pacote ativo, a UI seleciona Faísca antes da exclusão. Se o I/O falhar, restaura a seleção anterior. Recursos built-in não oferecem remoção. Arquivos temporários, staging e pacote parcial nunca se tornam a fonte ativa.

## Estados

O coordenador usa estados explícitos: `Idle`, `InvalidCode`, `Resolving`, `NotConfigured`, `NotFound`, `AccessDenied`, `NetworkUnavailable`, `UnsupportedManifest`, `PreviewReady`, `Downloading`, `Verifying`, `Installing`, `Installed`, `AlreadyInstalled`, `DownloadFailed`, `IntegrityFailed` e `InstallFailed`. Buscas e instalações são serializadas para impedir resultados fora de ordem.

## Segurança e observabilidade

A tag `GruPerch` registra trace aleatório, evento, duração e resultado estrutural. Não registra código, URL, imagem, bytes, token ou dado pessoal. O clipboard só é lido após toque em **Colar código**.

## Fora desta rodada

Não foram implementados Web Studio, IA, doze poses no Android, catálogo global, Supabase, Appwrite, VPS, pagamentos, login, QR Scanner, compartilhamento nem publicação pública/privada.
