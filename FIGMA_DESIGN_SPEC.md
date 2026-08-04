# Gru — Figma design specification

## 1. Objetivo

Consolidar o frontend Android do Gru como companheiro operacional: simples, amigável, Material 3 e acessível.

## 2. Arquivo Figma

[Gru — Material 3 Visual Lab](https://www.figma.com/design/IxJL3CPIFbB4rDLnUVIqwX), file key `IxJL3CPIFbB4rDLnUVIqwX`.

## 3. Limitações Starter e estrutura

O plano limita o arquivo a três páginas e uma variável por modo. A organização foi adaptada para `01 — Sistema visual e componentes` e `03–10 — Fluxos e protótipos`; coleções Light/Dark equivalentes substituem modos múltiplos nativos.

## 4. Tokens e componentes

Tokens: success, attention, error, neutral, surface, on-surface e outline. Componentes: Navigation central, botões, status, Permission Card, Voice Selector, Mascot Card, Step Progress, erro recuperável e tutorial.

## 5. Telas e navegação

Os destinos são Permissões, Voz, Ligar/Desligar, Mascotes e Criar mascote. O centro abre Controle e não alterna estado. Frames: Permissões `7:3`, Voz `7:10`, Controle `7:17`, Mascotes `7:24`, Criar mascote `7:31`, Dark/200% `7:38`.

## 6. Estados, acessibilidade e movimento

Verde comunica permitido/pronto/ligado; dourado atenção/identidade; vermelho erro/bloqueio/desligado; cinza neutralidade. Texto, ícone e forma são obrigatórios além de cor. Alvos de 48dp, TalkBack, RTL, contraste, fonte 200%, claro/escuro e movimento reduzido são especificados na prancha `8:3`. Movimento é curto e sem função decorativa.

## 7. Mascote e protótipo

PNG oficial `brand/gru-brand-master.png` foi inserido com Fit nos frames `7:3`, `7:17` e `7:38` (nós `9:4`, `9:5`, `9:6`). A rota conceitual é Permissões → Voz → Controle → Mascotes → Criar mascote. Conexões clicáveis detalhadas não foram configuradas: o plano Starter e a API disponível não expõem uma rota segura para editar reações nesta rodada.

## 8. Pendências e Compose futuro

Pagamento, arquivamento, vídeo Groq e catálogo contratual de poses continuam futuros. Em Compose, mapear tokens aos papéis Material 3/Dynamic Color, usar `ContentScale.Fit`, NavigationBar com destino central seguro, `sp` e reflow para 200%, e estados reais do runtime sem inventar progresso.
