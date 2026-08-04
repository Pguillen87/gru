# Gru — revisão das direções visuais (Parte 2A)

> **Status:** exploração para decisão. Nada nesta página é especificação aprovada ou instrução de implementação.
>
> **Escopo:** direção visual do novo frontend Android. Não altera Kotlin, Compose, runtime, APIs, backend, contratos, `DESIGN.md` ou o arquivo Figma consolidado.

## Contexto e critérios inegociáveis

O mapa de experiência de `FRONTEND_REDESIGN_PLAN.md` é a fonte de verdade: Permissões, Voz, Controle, Mascotes e Criar são destinos diferentes da Navigation Bar. O item central abre o Controle; **nunca** liga ou desliga o runtime pelo toque na barra.

As propostas preservam estes fatos do produto:

- Online usa Groq, exige internet e chave; Privado processa no aparelho e não tem fallback automático para Groq.
- Download e criação só podem comunicar estados reais; não há porcentagem inventada.
- Arquivar, pagamento e a escolha antecipada das três poses são propostas futuras, não capacidades prontas.
- O aplicativo continua Android nativo em Material 3, com Dynamic Color quando apropriado, claro/escuro, fonte 200%, RTL, TalkBack, movimento reduzido e alvos de ao menos 48dp.

As três explorações foram produzidas como pranchas com as mesmas seis amostras: Permissões, Voz, Controle, Mascotes, primeira etapa de Criar e anatomia da Navigation Bar. Elas são referências de hierarquia, forma e comportamento; não são HTML para reutilizar.

## Direção A — Calma e premium

**Tese:** uma companhia silenciosa e confiável. Espaço negativo, ritmo editorial e superfícies tonais deixam a tarefa de ditar ocupar o centro, enquanto o mascote aparece como presença, não decoração repetida.

- **Hierarquia e densidade:** títulos fortes, resumos curtos e uma ação por bloco. Ritmo de 8/16/24/32dp, margens confortáveis e poucos contêineres.
- **Formas e superfícies:** cartões grandes, discretos e de baixa elevação tonal; cantos suaves, sem sombra pesada. Base quente/neutra compatível com papéis semânticos do Material 3, com azul e dourado apenas como acentos do Gru.
- **Navegação e Controle:** o destino central é um “portal” elevado, largo o bastante para ícone e rótulo/estado. Na tela Controle, o estado textual `GRU LIGADO`/`GRU DESLIGADO`, ícone e pose do mascote chegam antes do botão deliberado `Ligar`/`Desligar`.
- **Permissões e Voz:** checklist aberto, explicações humanas e ações em linha; seletor Online/Privado é segmentado e tem ícone, contorno e texto para a seleção, não somente cor.
- **Mascotes e Criar:** retrato maior do atual; galeria pessoal horizontal com espaço para respirar; o fluxo de criação parece páginas calmas, com `1 de 6` explícito.
- **Movimento:** fade-through/shared-axis de 150–200ms; com animações reduzidas, troca instantânea ou fade mínimo sem perda de informação.

**Ponto de atenção:** espaço demais pode esconder a próxima ação sob fonte 200% se a tela não usar reflow e seções progressivas. A consolidação deve assegurar que o estado e o CTA apareçam antes de ilustrações grandes.

## Direção B — Lúdica e viva

**Tese:** o Gru é um pequeno personagem pessoal. A interface usa o mascote, formas assimétricas suaves e estados ilustrados para tornar configuração e criação mais acolhedoras sem virar jogo.

- **Hierarquia e densidade:** composição mais expressiva; blocos de estado visual e áreas de personagem quebram a coluna tradicional. Continua uma ação principal por tela.
- **Formas e superfícies:** círculos, squircle e campos tonais coloridos em papéis Material semânticos. O contraste e o texto continuam carregando a informação.
- **Navegação e Controle:** o destino central mora em um “ninho”/base própria, visualmente ligado à cena do Controle. O controle usa mascote atento/descansando, texto e ícone para tornar Ligado/Desligado instantâneo.
- **Permissões e Voz:** cada requisito recebe um marcador ilustrado e um status verbal; Online e Privado usam o mesmo seletor com posição, rótulo, ícone e contorno persistentes.
- **Mascotes e Criar:** coleção mais rica, com cards de personalidade e estados selecionados explícitos; criação com páginas que parecem ser folheadas, pontos + texto de etapa.
- **Movimento:** acomodação leve de 180–240ms em escolhas e mudança de página; reduzir movimento troca a cena instantaneamente.

**Ponto de atenção:** a camada de personagem deve ter orçamento rigoroso. Em Permissões e Voz, ela não pode deslocar conteúdo crítico, competir com alertas de privacidade ou depender de animação.

## Direção C — Utilitária com personalidade

**Tese:** velocidade e compreensão primeiro; a personalidade mora em pontos memoráveis, e não em cada linha. É a direção mais próxima de uma ferramenta Android bem resolvida, mas evita parecer Configurações do sistema.

- **Hierarquia e densidade:** listas e faixas de estado de leitura imediata, CTA claro e alta visibilidade da próxima pendência. Menos área decorativa e menos rolagem para chegar à ação.
- **Formas e superfícies:** componentes Material 3 disciplinados, contornos e tonalidade para agrupar; marca do Gru pequena no app bar e prévia do personagem concentrada no Controle.
- **Navegação e Controle:** cápsula central contornada e rotulada como destino. A tela Controle privilegia estado, bloqueio/ação e confirmação; o mascote é sinal afetivo secundário.
- **Permissões e Voz:** linhas orientadas a ação e mensagens curtas; estados do modelo local aparecem como estados textuais (`Não instalado`, `Baixando`, `Verificando`, `Pronto`, `Ativo`, `Erro`), sem barra fictícia.
- **Mascotes e Criar:** grade confiável para coleção, atual destacado primeiro; criação sequencial sem checkout agressivo e com progresso textual.
- **Movimento:** quase nenhum além de confirmação de estado (~120ms) e transições Android padrão; reduzido é instantâneo.

**Ponto de atenção:** se faixas de status, contornos e listas compactas forem exagerados, a direção escorrega para painel administrativo/Configurações. O mascote e a cópia humana precisam quebrar essa rigidez.

## Comparação ponderada

Pontuação de 1 (fraco) a 5 (muito forte). A pontuação avalia a direção para o Gru, não “beleza” isolada.

| Critério | Peso | A — Calma | B — Lúdica | C — Utilitária | Leitura |
| --- | ---: | ---: | ---: | ---: | --- |
| Compreensão imediata | 15% | 4 | 4 | 5 | C expõe ação e pendência com menos interpretação. |
| Personalidade sem infantilizar | 12% | 4 | 5 | 3 | B transforma o personagem em linguagem de produto; A é mais contida. |
| Clareza de permissões e voz | 12% | 4 | 4 | 5 | C favorece checklist, custos e estados verificáveis. |
| Acessibilidade / TalkBack / não depender de cor | 12% | 4 | 4 | 5 | C exige menos elementos simultâneos; todas precisam de rótulos e estado textual. |
| Fonte 200% e RTL | 10% | 4 | 3 | 5 | C tem mais espaço semântico para reflow; B requer cuidado com cenas e galerias. |
| Claro, escuro e Dynamic Color | 8% | 5 | 4 | 5 | A e C dependem menos de cores de marca fixas. |
| Navigation Bar e botão central | 10% | 4 | 5 | 5 | B cria o gesto mais memorável; C torna mais evidente que é destino, não toggle. |
| Tela Voz | 8% | 4 | 5 | 5 | B dá identidade ao seletor; C comunica trade-offs mais rapidamente. |
| Mascotes e Criar | 6% | 4 | 5 | 3 | B melhor sustenta coleção pessoal e jornada especial. |
| Implementação Material 3 / Compose | 4% | 5 | 3 | 5 | A/C reutilizam padrões M3 com menos exceções. |
| Escalabilidade para telas futuras | 3% | 5 | 3 | 5 | A/C acomodam estados adicionais sem aumentar ruído. |
| **Total ponderado / 5** | **100%** | **4,16** | **4,15** | **4,70** | C vence por operação; não é decisão final. |

## Diferenças estruturais relevantes

| Aspecto | A — Calma | B — Lúdica | C — Utilitária |
| --- | --- | --- | --- |
| Papel do mascote | Companhia e retrato | Personagem que organiza estados | Assinatura pontual e preview focal |
| Topologia | Coluna editorial espaçada | Cenas e blocos expressivos | Lista/ação, leitura rápida |
| Galeria | Carrossel de retratos | Coleção de personagens | Grade operacional |
| Centro da barra | Portal tonal ancorado | Ninho visual conectado à cena | Cápsula contornada e inequívoca |
| Criar | Folhear páginas calmas | Jornada de personagem | Assistente objetivo por etapa |
| Movimento | Discreto | Expressivo, mas opcional | Mínimo e funcional |

## Acessibilidade que deve ser consolidada, qualquer que seja a escolha

- Cada item de navegação, ícone de edição e ação tem alvo físico de 48×48dp ou maior; rótulo visível não é substituído por tooltip.
- Seleção usa posição, ícone/indicador, rótulo e estado semântico, além de cor. `Ligar` e `Desligar` continuam verbos explícitos.
- A Navigation Bar é reavaliada em fonte 200%: rótulos podem quebrar em duas linhas, compactar de modo controlado ou seguir uma decisão de nomenclatura aprovada; nenhum destino pode ficar sem nome.
- TalkBack anuncia destino, selecionado, estado do Gru, permissão ausente, modo de voz e progresso/erro real. Ordem de foco e ordem lógica respeitam RTL.
- Light/dark usam papéis Material (`surface`, `onSurface`, `primary`, `error`, etc.) e contrastes verificados; Dynamic Color recebe fallback estático do Gru.
- Movimento nunca é a única confirmação. Redução de movimento usa corte/fade curto e preserva texto, ícone e pose.

## Referências pontuais do 21st.dev

Nenhuma referência foi incorporada nesta rodada: o conector 21st.dev não estava exposto nesta sessão e a exploração solicitada já tinha respostas diretas no Material 3 e no Stitch. Não foi copiado código web.

Quando o conector estiver disponível, as consultas úteis — somente como referência conceitual — são:

| Ideia a pesquisar | Por que serve | Tradução futura para Compose |
| --- | --- | --- |
| Ação central de navegação | Contrastar portal, ninho e cápsula sem criar FAB genérico | `NavigationBarItem`/contêiner M3 customizado; toque abre Controle. |
| Segmented control animável | Escolher Online/Privado de modo óbvio | `SingleChoiceSegmentedButtonRow`, estado/ícone/texto persistentes. |
| Galeria de personagens | Comparar carrossel e grade com seleção clara | `LazyRow` ou `LazyVerticalGrid`, sem código web. |
| Etapas e sucesso | Afinar a criação sem barra de progresso falsa | indicador textual/pontos e estados do job real. |

## Resultados no Stitch

Projeto reutilizado: [Gru Visual Lab](https://stitch.withgoogle.com/projects/3165238598565468510) (`3165238598565468510`). Nenhum projeto novo foi criado.

| Direção | Tela Stitch | ID | Link |
| --- | --- | --- | --- |
| A — Calma e premium | `GRU Redesign — Direction A` | `0fd3794592b946ba840ea9c2d2781bd7` | [Abrir projeto](https://stitch.withgoogle.com/projects/3165238598565468510) |
| B — Lúdica e viva | `GRU Redesign — Direction B` | ID não retornado pela indexação/listagem do MCP após a geração | [Abrir projeto](https://stitch.withgoogle.com/projects/3165238598565468510) |
| C — Utilitária com personalidade | `GRU Redesign — Direction C` | `538db6cb501e4cc8804574aa8bb7b2f1` | [Abrir projeto](https://stitch.withgoogle.com/projects/3165238598565468510) |

### Limitações observadas nas gerações

1. Stitch retornou pranchas verticais de exploração, não uma biblioteca editável nem telas nativas finais. A consolidação aprovada pertence à Parte 2B no Figma.
2. A API `list_screens` retornou vazia mesmo após gerações concluídas. Por isso o MCP não permitiu recuperar o ID de B nesta sessão; a prancha deve permanecer acessível pelo projeto/canvas.
3. A e C exibem alguns rótulos/estrutura genéricos produzidos pelo gerador (por exemplo, `Settings`), inadequados para a cópia em português do Gru. Eles são defeitos conhecidos da exploração, não decisão de conteúdo.
4. As pranchas anotam intenção de fonte ampliada, RTL e tema, mas não substituem validação de layout em Compose nem auditoria TalkBack no dispositivo.
5. Não há vídeo oficial para o tutorial Groq, ativos novos aprovados, pagamento, arquivamento persistente ou catálogo contratual de poses. Foram mantidos como placeholders/propostas.

## Recomendação do Codex — pendente de aprovação

Recomendo uma combinação **C como espinha operacional + B como camada de personalidade**, com a contenção espacial de A:

- manter de C a checklist, a leitura de estados da Voz, a cápsula central explicitamente navegacional e a robustez para fonte 200%;
- adotar de B o tratamento de personagem no Controle, a coleção de Mascotes e o ritmo de “folhear” em Criar;
- aplicar de A a redução de cartões, a hierarquia editorial e o movimento discreto.

Isto é uma recomendação, não uma seleção. A Parte 2B só começa depois da aprovação explícita de A, B, C ou dessa combinação. Até lá, `DESIGN.md` e o arquivo Figma permanecem inalterados.
