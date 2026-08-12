---
name: Gru — Material 3 Companion
description: Um companheiro Android simples, caloroso e operacional para falar e escrever.
colors:
  brand-cyan: "#20B8FF"
  brand-gold: "#FFD84D"
  success: "#31E6A1"
  danger: "#FF4D57"
  dark-background: "#050607"
  dark-surface: "#111416"
  dark-surface-high: "#191D20"
  dark-outline: "#30363A"
  light-background: "#FBF9F1"
  light-surface: "#FFFBF4"
  light-surface-variant: "#F0ECE4"
  light-text: "#191C1D"
  light-text-secondary: "#444749"
typography:
  headline-large:
    fontFamily: "sans-serif"
    fontSize: "32sp"
    fontWeight: 700
    lineHeight: "38sp"
  headline-medium:
    fontFamily: "sans-serif"
    fontSize: "28sp"
    fontWeight: 700
    lineHeight: "34sp"
  headline-small:
    fontFamily: "sans-serif"
    fontSize: "22sp"
    fontWeight: 600
    lineHeight: "28sp"
  title:
    fontFamily: "sans-serif"
    fontSize: "20sp"
    fontWeight: 600
    lineHeight: "26sp"
  body:
    fontFamily: "sans-serif"
    fontSize: "16sp"
    fontWeight: 400
    lineHeight: "24sp"
  label:
    fontFamily: "sans-serif"
    fontSize: "14sp"
    fontWeight: 600
    lineHeight: "20sp"
rounded:
  small: "10dp"
  medium: "16dp"
  large: "24dp"
  navigation: "28dp"
  circular: "999dp"
spacing:
  xs: "8dp"
  sm: "16dp"
  md: "24dp"
  lg: "32dp"
components:
  button-primary:
    backgroundColor: "{colors.brand-cyan}"
    textColor: "{colors.dark-background}"
    typography: "{typography.label}"
    rounded: "{rounded.circular}"
    padding: "12dp 24dp"
    height: "48dp"
  card-standard:
    backgroundColor: "{colors.dark-surface}"
    textColor: "#F3F4F5"
    rounded: "{rounded.medium}"
    padding: "16dp"
  navigation-bottom:
    backgroundColor: "{colors.dark-surface}"
    textColor: "#B5BDC2"
    rounded: "{rounded.navigation}"
    padding: "8dp 12dp"
  status-success:
    backgroundColor: "{colors.success}"
    textColor: "{colors.dark-background}"
    rounded: "{rounded.circular}"
    padding: "8dp 12dp"
  status-attention:
    backgroundColor: "{colors.brand-gold}"
    textColor: "#211B00"
    rounded: "{rounded.circular}"
    padding: "8dp 12dp"
---

# Design System: Gru — Material 3 Companion

## Overview

**Creative North Star: "Companheiro Operacional"**

O Gru é um pequeno companheiro Android que ajuda a pessoa a falar e escrever. A interface combina clareza operacional, presença moderada da coruja oficial e respiro editorial. Material 3 é a base nativa; a identidade aparece no ciano de seleção, no dourado caloroso, nas superfícies suaves e na linguagem humana.

O produto deve parecer pessoal sem virar jogo, simples sem parecer uma tela genérica de configurações e visual sem virar dashboard. O mascote apoia a compreensão em Controle, ajuda, sucesso e estados vazios, sempre com proporção preservada e `ContentScale.Fit`.

**Key Characteristics:**

- Navegação inferior com cinco destinos e Controle central protagonista.
- Hierarquia direta, uma ação principal por contexto e superfícies com bastante respiro.
- Estados comunicados por texto, ícone, forma e cor semântica.
- Claro, escuro, fonte 200%, TalkBack, RTL e movimento reduzido como requisitos estruturais.
- Comportamento Android nativo e integração com estados reais do runtime.

## Colors

A paleta combina ciano elétrico para orientação, dourado para identidade e atenção, verde para conclusão e vermelho para falhas reais ou ações destrutivas.

### Primary

- **Ciano de orientação** (`brand-cyan`): seleção, destino ativo, foco e ação operacional prioritária.

### Secondary

- **Dourado Gru** (`brand-gold`): marca, pendência, progresso e ação recomendada.

### Tertiary

- **Verde pronto** (`success`): permitido, instalado, configurado, ligado e concluído.
- **Vermelho de bloqueio** (`danger`): erro, falha, bloqueio e remoção destrutiva.

### Neutral

- **Noite profunda** (`dark-background`): fundo do tema escuro.
- **Painel acolhedor** (`dark-surface`): superfícies principais no tema escuro.
- **Papel quente** (`light-background`): fundo do tema claro.
- **Superfície marfim** (`light-surface`): cards e barras no tema claro.

**The Semantic State Rule.** Verde significa pronto, dourado significa atenção, vermelho significa erro ou destruição e cinza significa neutralidade. Nenhum estado depende somente da cor.

**The Brand Restraint Rule.** Ciano e dourado orientam a experiência; não tingem indiscriminadamente todas as superfícies.

## Typography

**Display Font:** Sans Serif do sistema Android

**Body Font:** Sans Serif do sistema Android

**Label Font:** Sans Serif do sistema Android

**Character:** Tipografia nativa, direta e calorosa. Pesos fortes criam orientação sem depender de tipografia ornamental ou fontes externas.

### Hierarchy

- **Headline Large** (700, 32sp/38sp): estados centrais e títulos de alta importância.
- **Headline Medium** (700, 28sp/34sp): títulos das cinco áreas.
- **Headline Small** (600, 22sp/28sp): títulos de seção e mensagens operacionais.
- **Title** (600, 20sp/26sp): cards principais e escolhas.
- **Body** (400, 16sp/24sp): explicações em linguagem simples.
- **Label** (600, 14sp/20sp): botões, estados e navegação.

**The Full Meaning Rule.** Rótulos essenciais podem quebrar em duas linhas em fonte 200%; nunca devem ser abreviados nem reduzidos abaixo da escala Material para caber.

## Layout

O ritmo usa 8/16/24/32dp, com 16dp como espaçamento interno padrão. Conteúdo principal é rolável, respeita barras do sistema e IME, e preserva alvos mínimos de 48dp. Em telas compactas e fonte ampliada, grades reduzem colunas e ações passam para fluxo vertical.

A Navigation Bar inferior contém **Permissões**, **Voz**, **Ligar/Desligar**, **Mascotes** e **Puleiro do Gru**. O item central é maior e abre Controle; nunca alterna o runtime diretamente. `Puleiro do Gru` pode ocupar duas linhas.

O overlay evita IME, editor focado, barras e recortes quando existe posição segura. Posições manuais permanecem quando ainda são válidas. Durante o arraste, a zona “Ocultar nesta conversa” aparece acima do teclado sem bloquear a edição.

## Elevation & Depth

O sistema usa principalmente camadas tonais e bordas discretas. Sombras são reservadas à Navigation Bar e a superfícies realmente elevadas; cards comuns permanecem próximos ao plano de fundo.

**The Tonal First Rule.** Profundidade nasce primeiro da diferença entre fundo, superfície e superfície elevada; sombra não substitui hierarquia.

## Shapes

As formas são amigáveis e adultas: 10dp em controles compactos, 16dp em cards, 24dp em superfícies grandes e 28dp na navegação. Botões de ação e indicadores podem usar cápsulas ou círculos, sempre mantendo área de toque mínima.

## Components

### Buttons

- **Shape:** cápsula ou canto grande, com altura mínima de 48dp.
- **Primary:** ciano com contraste forte e texto de ação explícito.
- **Secondary:** tonal ou contornado; nunca compete com a ação principal.
- **Disabled:** cinza neutro mais texto explicando o pré-requisito quando necessário.

### Cards / Containers

- **Corner Style:** 16dp para cards operacionais; 24dp para superfícies de destaque.
- **Background:** superfície tonal Light/Dark.
- **Border:** outline discreto; seleção usa 2dp, check e texto selecionado.
- **Internal Padding:** 16dp, expandindo para 24dp em cards principais.

### Inputs / Fields

- **Style:** Material 3, rótulo persistente e alvo mínimo de 48dp.
- **Focus:** ciano de orientação, sem depender apenas da borda.
- **Error:** vermelho somente para falha real; pendência usa dourado.

### Navigation

A barra inferior usa superfície elevada de 28dp de raio. O destino selecionado combina ciano, forma e semântica `selected`. O Controle central usa ícone circular maior, mas o toque apenas abre a tela de Controle.

### Status

Indicadores combinam ícone, texto e papel semântico: sucesso, atenção, erro ou neutro. Preparando e baixando são atenção; ativo e pronto são sucesso.

### Mascot Card

Cards usam imagem em `Fit`, nome legível, seleção explícita e ações com descrição TalkBack. `Mascotes do Gru` contém built-ins; `Meus mascotes` contém apenas itens importados pelo Puleiro.

### Conversation Suppression Target

Durante o arraste do pet, uma superfície temporária “Ocultar nesta conversa” aparece acima do teclado. Entrar na zona combina ícone, texto, vermelho semântico e um único feedback tátil. Soltar oculta apenas o contexto atual da sessão. Controle oferece contador e “Mostrar novamente”.

## Do's and Don'ts

### Do:

- **Do** preservar Material 3, comportamento nativo e estados reais do runtime.
- **Do** usar a coruja oficial moderadamente e sempre sem recorte ou recoloração.
- **Do** testar claro, escuro, fonte 200%, TalkBack, RTL e movimento reduzido.
- **Do** manter Permissões, Voz, Controle, Mascotes e Puleiro como áreas distintas.
- **Do** comunicar falhas com recuperação acionável e linguagem não técnica.

### Don't:

- **Don't** transformar o Gru em dashboard administrativo ou jogo infantil.
- **Don't** usar amarelo para erro, vermelho para mera pendência ou verde para motor ainda preparando.
- **Don't** esconder ou ligar/desligar o pet por toque direto na Navigation Bar.
- **Don't** ler conteúdo de conversa, nome de contato ou clipboard sem ação explícita.
- **Don't** cortar rótulos essenciais, reduzir tipografia para fazê-los caber ou depender apenas de animação.
