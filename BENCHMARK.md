# Benchmark do Whisper local

## Ambiente

- Data: 1º de agosto de 2026.
- Aparelho: Samsung Galaxy A55 (`SM-A556E`).
- Android: 16, API 36.
- SoC: `s5e8845`.
- RAM física reportada: 7.606.428 KiB.
- Runtime: whisper.cpp v1.8.6, CPU, quatro threads.
- Modelo: Large V3 Turbo Q5_0, 574.041.195 bytes.
- Áudio: português, PCM16 mono, 16 kHz, 11,58 segundos.

## Download

- Rede: Wi-Fi do aparelho.
- Tempo observado até arquivo final verificado: 26 segundos.
- Fluxo observado: `.part` → tamanho esperado → SHA-256 → promoção para arquivo final.

## Inferência local

- Limite do teste: 15 minutos.
- Resultado: não concluiu o ciclo de benchmark dentro do limite.
- PSS observado antes do encerramento: 945.532 KiB, cerca de 923 MiB.
- Temperatura da bateria: aproximadamente 22,5 °C antes e 28,6 °C depois.
- Bateria: 100% antes e 96% depois, com USB conectado.
- Tempo de carregamento e inferência separados: indisponíveis porque a primeira rodada não concluiu.
- Razão de tempo real: superior a 77,7x no limite observado (`900 s / 11,58 s`).

## Groq

A comparação com a Groq não foi executada porque o pacote de teste não possuía chave configurada. Nenhuma chave foi copiada ou criada para o benchmark.

## Conclusão

O Large V3 Turbo Q5_0 não oferece experiência interativa aceitável no Galaxy A55 com o runtime CPU atual. Conforme a decisão de produto, ele não foi substituído silenciosamente. Antes de mudar o modelo, recomenda-se avaliar explicitamente uma variante menor e comparar qualidade em português, latência, RAM e bateria com a mesma gravação.
