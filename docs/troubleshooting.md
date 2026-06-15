# Troubleshooting

## Problemas Comuns

| Sintoma | Causa provavel | Acao recomendada |
| --- | --- | --- |
| Nao conecta (`PING/PONG`) | Antena ausente/solta | Reconectar as duas antenas e reiniciar |
| Link instavel | Sinal fraco/interferencia | Aproximar estacoes e medir RSSI |
| Buzzer sem som | Pino incorreto ou buzzer danificado | Verificar pino da placa e testar buzzer |
| Botao nao responde | Ligacao/pull-up | Validar continuidade e pino de entrada |
| Ignitor nao aciona | Rele/MOSFET ou pino de saida | Testar saida com carga dummy |
| Contagem aborta | Perda de `ARM_CONFIRMED` | Melhorar enlace e reduzir distancia |

## Checklist Rapido

1. Bateria ok e alimentacao estavel.
2. Antenas conectadas antes de energizar.
3. Firmware correto gravado em cada estacao.
4. Frequencia e pinagem conferidas em `firmware/micropython/estacao_*.py`.
5. Cabo USB de dados para programacao/logs.

## Diagnostico por Serial

Abrir monitor serial em 115200 baud.

Exemplo de fluxo esperado:

```text
[LoRa] SX1278 inicializado em 433 MHz.
[CMD] Link com ignicao: OK
[LoRa TX] -> PING
[LoRa RX] <- PONG
```

## Casos Especificos

### Nao recebe `ARM_CONFIRMED`

1. Confirmar que a estacao de comando esta em estado conectado.
2. Conferir frequencia em ambas as placas.
3. Conferir antena e conexoes SPI.

### Aborta no meio da contagem

1. Manter botao pressionado durante os 5 s.
2. Validar qualidade de sinal (RSSI).
3. Evitar interferencia e aumentar robustez (ex.: SF maior, se necessario).

### Ignitor nao aciona no fim

1. Validar pino de saida com LED/carga dummy.
2. Regravar firmware de ignicao.
3. Revisar acionamento do rele/MOSFET.

## Coleta de Logs

```bash
screen -L /dev/ttyACM0 115200
```

Ou:

```bash
cat /dev/ttyACM0 | tee logs/session_$(date +%Y%m%d_%H%M%S).log
```

## Suporte

Ao abrir issue, incluir:

- Versao do firmware.
- Trecho de configuracao usado.
- Ultimas linhas de log serial.
- Distancia entre estacoes e RSSI.
- Fotos das conexoes.
