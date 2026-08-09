# Gru Design

## Creative North Star

Gru é um companheiro Android para ditar texto com clareza operacional, presença calorosa da coruja oficial e respiro editorial. Material 3 é a base; a personalidade não pode transformar a experiência em dashboard ou jogo.

## Navigation

Navigation Bar inferior: **Permissões**, **Voz**, **Ligar/Desligar**, **Mascotes** e **Puleiro do Gru**. O item central é maior e abre Controle; nunca alterna o runtime por toque na barra. Em fonte 200%, `Puleiro do Gru` pode reflow em duas linhas, sem abreviar o significado.

## Tokens and components

- Tokens semânticos: success/enabled, attention, error, neutral, surface, on-surface e outline, em coleções Light/Dark no Figma; Dynamic Color usa estes papéis e fallback estático.
- Verde = permitido/pronto/ligado; dourado = identidade/atenção; vermelho = erro/bloqueio/desligado; cinza = neutro/indisponível. Todo estado combina texto, ícone, forma e rótulo acessível.
- Componentes: Navigation central, botões principal/secundário, status, Permission Card, Voice Selector, Mascot Card, Step Progress, erro recuperável e tutorial.
- Formas suaves, elevação tonal e espaçamento 8/16/24/32dp; alvos de toque mínimos de 48dp.

## Screens and states

- Permissões: checklist Acessibilidade, Microfone, Notificações e recuperação guiada.
- Voz: Online — Groq e Privado — no aparelho, com custos/privacidade explícitos e estados reais de chave/modelo.
- Controle: Gru ligado, desligado, bloqueado ou em configuração; ação deliberada Ligar/Desligar.
- Mascotes: atual, meus mascotes, oficiais, aparência e arquivados futuro.
- Puleiro do Gru: entrada simples por código, prévia antes do download e estados honestos. A criação de mascotes acontece futuramente na Web; o Android instala apenas três poses prontas.

## Mascot, motion and accessibility

A coruja oficial é usada em cabeçalho, Controle, ajuda e sucesso com proporção preservada e referência futura `ContentScale.Fit`. Movimento só explica troca Online/Privado, ligar/desligar, seleção, etapa, progresso, sucesso e erro; com movimento reduzido, a troca é instantânea/fade curto. TalkBack anuncia destino, seleção, estado, pendência, progresso e erro; RTL preserva ordem lógica. Claro, escuro e fonte 200% são requisitos de primeira classe.
