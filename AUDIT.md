# Auditoria pós-refatoração

Data: 1º de agosto de 2026.

## Pontuação

| Dimensão | Nota | Evidência principal |
| --- | ---: | --- |
| Acessibilidade | 3/4 | Fonte 200% sem sobreposição, controles Material e estado de download anunciado; TalkBack real não executado. |
| Desempenho | 1/4 | UI e download responsivos, mas Large V3 Turbo Q5 é inviável no A55. |
| Aparência e tema | 4/4 | Material 3, Dynamic Color e temas claro/escuro. |
| Conformidade Android | 4/4 | Componentes nativos, edge-to-edge, abas simples, Keystore e suporte a páginas de 16 KB. |
| Adaptatividade | 2/4 | Rolagem e fonte grande funcionam no telefone; tablet, paisagem e foldable não foram executados. |
| **Total** | **14/20** | **Bom, com bloqueio de desempenho no modo local.** |

## Achados

### P0 — Large V3 Turbo Q5 inviável no Galaxy A55

Uma gravação de 11,58 segundos não concluiu dentro de 15 minutos. O processo alcançou cerca de 923 MiB de PSS. O modelo não foi trocado porque a decisão exige recomendação e aprovação antes de reduzir qualidade. Evidências completas estão em `BENCHMARK.md`.

### P2 — Validação de acessibilidade incompleta

Fonte de 200% e árvore semântica foram verificadas. TalkBack e redução de animações não foram executados fisicamente.

### P2 — Validação adaptativa incompleta

O layout usa uma coluna rolável e não sobrepôs conteúdo no A55. RTL forçado não entrou em vigor sem reinício; tablet, paisagem, multiwindow e foldable não foram executados.

### P2 — Fluxos externos incompletos

Não havia chave Groq no pacote de teste, então a mesma gravação não foi comparada online. Gboard, WebView, Flutter e React Native não foram revalidados nesta rodada.

### P3 — Avisos de lint não bloqueantes

O lint terminou sem erro e com avisos de versões disponíveis, sugestões KTX, construtores de Views usadas apenas por código e formato do ícone redondo. Nenhum aviso bloqueia compilação ou o fluxo principal.

## Correções feitas durante a auditoria

- NDK atualizado para r28c e STL ligado estaticamente após falha de compatibilidade com páginas de 16 KB.
- Download verificado em arquivo temporário, retomada após rede e limpeza no cancelamento.
- Chave Groq cifrada e migração legada validada em aparelho.
- Toques repetidos não criam duas transcrições.
- Toque durante processamento cancela a sessão e remove o WAV.
- Estados do download usam região semântica dinâmica.
- JARs locais órfãos de Sherpa ONNX e ONNX Runtime removidos do workspace.

## Auditoria de legado

Não há módulos, dependências ou código executável de FlorisBoard, IME, Wear OS, Room, histórico, prompts, Smartbar, dicionários, mídia, estatísticas ou Sherpa ONNX. Permanecem apenas atribuições legais e um teste negativo que comprova a ausência de `BIND_INPUT_METHOD`.
