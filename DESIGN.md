# Gru Design

## Direction

Gru é uma ferramenta Android em modo Operate: quase toda a interface desaparece depois da configuração. O pet flutuante é o foco visual e comunica estado por pose, movimento, contorno e descrição acessível.

## Visual System

- Material 3 e Dynamic Color estruturam a tela de configuração em temas claro e escuro.
- Superfícies são planas e silenciosas; não há cartões aninhados, decoração ou navegação persistente.
- A cor do sistema orienta ações e foco. Cores dos pets pertencem aos personagens, não viram decoração de página.
- Tipografia usa a escala Material e a fonte do sistema.

## Pet Language

- Lume: pequena coruja azul, calma e atenta.
- Faisca: pequena raposa coral, rápida e expressiva.
- Bip: pequeno robô verde-água, preciso e amigável.
- Pingo: pequena criatura violeta arredondada, curiosa e suave.
- O asset visual ocupa aproximadamente 40 dp dentro de uma área tocável mínima de 56 dp.
- Cada pet usa um atlas de 16 expressões dentro de um motor contínuo de movimento: respiração, peso, inclinação, salto e pouso são interpolados a cada quadro.
- O pet não usa selo de microfone, botão de fechar ou outro controle acoplado. Durante a gravação, aura coral, ondas responsivas e a faixa `OUVINDO 00:00` tornam o estado inequívoco.
- Quando o sistema remove animações, as transições são instantâneas e o estado permanece legível pela pose e pela descrição acessível.

## Interaction

- O pet aparece somente quando há, simultaneamente, um campo editável focado e o teclado visível.
- Toque inicia a gravação; o segundo toque no próprio pet encerra e transcreve; arraste reposiciona.
- O pet encaixa na borda mais próxima sem invadir barras do sistema ou o teclado.
- A personalização ocorre no aplicativo, não em menus sobrepostos.

## States

- Inativo: pet respirando, piscando e executando ações espontâneas.
- Ouvindo: inclinação atenta, aura coral pulsante e ondas corporais responsivas ao volume.
- Processando: órbita contínua do corpo e arcos de progresso.
- Sucesso: salto, pouso e comemoração.
- Erro: expressão alegre, pequeno salto de incentivo e mensagem acionável; o pet nunca demonstra tristeza ou choro.
- Sem foco: pet oculto.

## Hardening Rules

- Eventos de acessibilidade excluem mudanças de conteúdo por caractere para não degradar a digitação.
- Ações concorrentes são bloqueadas enquanto uma transcrição está ativa.
- Falhas preservam a gravação quando o motor permitir reenvio; nenhuma falha apaga o texto existente.
- Campos de senha nunca mostram o pet.
- Textos e controles acomodam traduções maiores, RTL e escala de fonte de 200%.
