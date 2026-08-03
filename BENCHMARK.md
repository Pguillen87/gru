# Benchmark do Whisper local

## Ambiente

- Data: 1º e 2 de agosto de 2026.
- Aparelho: Samsung Galaxy A55 (`SM-A556E`).
- Android: 16, API 36.
- SoC: Exynos `s5e8845`, GPU Xclipse 530.
- RAM física reportada: 7.606.428 KiB.
- Runtime: whisper.cpp v1.8.6, quatro threads.
- Áudio: PCM16 mono, 16 kHz, 11,58 segundos.
- Frase: "Olá, este é um teste privado de transcrição no celular. O Gru transforma a fala em texto sem enviar o áudio para a internet."

RTF abaixo de 1 significa processamento mais rápido que a duração do áudio. PSS é a memória proporcional observada no processo de teste e inclui o aplicativo, runtime e modelo.

## Histórico

O primeiro APK de depuração compilava o código nativo sem `-O3`. Com o Large V3 Turbo Q5_0, a inferência não terminou dentro de 15 minutos. O PSS chegou a 945.532 KiB, a bateria foi de 100% para 96% mesmo no USB e a temperatura foi de aproximadamente 22,5 °C para 28,6 °C. Esse resultado motivou a correção do build e a comparação controlada dos modelos.

## CPU genérica otimizada

| Modelo | Tamanho | Tempo | RTF | PSS | Texto |
| --- | ---: | ---: | ---: | ---: | --- |
| Large V3 Turbo Q5_0 | 574.041.195 bytes | 41.660 ms | 3,598 | 874.450 KiB | Correto |
| Medium Q5_0 | 539.212.467 bytes | 28.151 ms | 2,431 | 984.372 KiB | Correto |
| Small Q5_1 | 190.085.487 bytes | 9.020 ms | 0,779 | 515.872 KiB | Correto |
| Base Q5_1 | 59.707.625 bytes | 2.961 ms | 0,256 | 317.298 KiB | Correto |

## Vulkan

Os logs confirmaram uso real da GPU Xclipse 530, mas o backend foi mais lento e consumiu mais memória neste aparelho.

| Modelo | Tempo | RTF | PSS |
| --- | ---: | ---: | ---: |
| Base Q5_1 | 18.917 ms | 1,634 | 543.951 KiB |
| Small Q5_1 | 59.404 ms | 5,131 | 757.517 KiB |
| Large V3 Turbo Q5_0 | 324.682 ms | 28,043 | 1.161.484 KiB |

No teste Large Vulkan, a temperatura foi de 26,7 °C para 27,4 °C. O APK Vulkan debug media aproximadamente 111,3 MB. O backend foi rejeitado e não faz parte do produto.

## ARM selecionado em runtime

O APK final contém três variantes CPU ARM64: baseline ARMv8.0, `dotprod` e `dotprod+fp16`. O runtime selecionou `libggml-cpu-android_armv8.2_2.so` no A55.

Resultado validado do Small Q5_1:

- Carregamento observado: 220 a 495 ms.
- Inferência observada: 7.021 a 8.368 ms.
- RTF observado: 0,606 a 0,723.
- PSS observado: 515.294 a 517.502 KiB.
- Temperatura: 27,5 °C para 27,6 °C.
- Bateria: 100% para 100% durante a rodada observada, com USB conectado.
- Texto: correto e equivalente ao esperado.
- APK debug: 30.279.479 bytes.

## Decisão

O Small Q5_1 foi inicialmente escolhido por qualidade, mas um teste posterior de uso real mostrou 11,4 segundos de espera para 4,08 segundos de áudio. A latência não se manteve adequada para frases curtas com outros processos ativos no A55.

Em 3 de agosto, o Base Q5_1 foi repetido com prioridade normal e o mesmo WAV padronizado:

| Threads | Inferência | RTF | Resultado |
| ---: | ---: | ---: | --- |
| 4 | 2.507 ms | 0,217 | Correto |
| 6 | 2.603 ms | 0,225 | Correto |
| 8 | superior a 120 s | inadequado | Interrompido |

O Base Q5_1 com quatro threads passou a ser o padrão. Ele reduz a latência, o download e a memória, aceitando a possível perda de precisão em fala difícil em favor de uma experiência interativa. Medium, Large e Vulkan continuam inadequados neste aparelho.

O modelo é baixado sob ação do usuário, não entra no APK/AAB e é validado por tamanho e SHA-256 antes da ativação. A revisão fixada é `5359861c739e955e79d9a303bcbc70fb988958b1`.

## Download e Groq

- Large pela Wi-Fi do aparelho: 26 segundos até validação, medição histórica.
- Small pela Wi-Fi do aparelho: 13,4 segundos, do toque até o estado instalado e verificado.
- Base: download de produção ainda não cronometrado; o arquivo fixado possui 59.707.625 bytes.
- Groq com a chave cifrada já configurada pelo usuário: 901 ms para a mesma gravação e texto equivalente.

O teste Groq não registrou nem alterou a chave. As medições variam com rede, temperatura e carga do aparelho.
