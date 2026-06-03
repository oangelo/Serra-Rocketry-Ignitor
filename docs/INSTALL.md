# Guia de Instalacao

Resumo: monte -> grave -> teste -> opere.

## Indice

| Secao | Topico |
| --- | --- |
| [1](#1-pre-requisitos) | Pre-requisitos |
| [2](#2-preparar-ambiente) | Preparar ambiente |
| [3](#3-montagem-de-hardware) | Montagem de hardware |
| [4](#4-gravar-firmware) | Gravar firmware |
| [5](#5-validar-operacao) | Validar operacao |
| [6](#6-integracao-com-ignitor-real) | Integracao com ignitor real |
| [7](#7-troubleshooting) | Troubleshooting |

## 1. Pre-requisitos

### Software

- Python 3.8+.
- Dependencias do projeto: `pip install -r requirements.txt`.
- Thonny IDE (recomendado) ou VS Code com extensao MicroPython.

### Hardware

- Multimetro.
- Fonte/bateria adequada.
- Ferramentas de montagem (ferro de solda, estanho, etc.).

## 2. Preparar Ambiente

```bash
git clone https://github.com/Serra-Rocketry/ignitor.git
cd ignitor
pip install -r requirements.txt
```

## 3. Montagem de Hardware

### 3.1 Estacao de Comando

- 1x Raspberry Pi Pico.
- 1x SX1278 433 MHz.
- 2x LEDs + resistores.
- 1x buzzer.
- 1x botao de ignicao.

Pinagem detalhada: [../hardware/README.md](../hardware/README.md#pinagem).

### 3.2 Estacao de Ignicao

- 1x ESP32-C3 SuperMini (ou Pico, variante legada).
- 1x SX1278 433 MHz.
- 2x LEDs + resistores.
- 1x buzzer.
- 1x rele/MOSFET para ignitor.

Pinagem detalhada: [../hardware/README.md](../hardware/README.md#pinagem).

### 3.3 Checklist Antes de Energizar

1. Verificar curto e polaridade com multimetro.
2. Confirmar conexoes SPI.
3. Confirmar antenas LoRa conectadas e apertadas.
4. Nao energizar SX1278 sem antena.

## 4. Gravar Firmware

Scripts oficiais:

- `firmware/micropython/estacao_comando.py`
- `firmware/micropython/estacao_ignicao.py` (Pico)
- `firmware/micropython/estacao_ignicao_esp.py` (ESP32-C3)
- `firmware/micropython/sx127x.py` (compatibilidade)
- `firmware/micropython/config_lora.py` (compatibilidade)

### 4.1 Envio com `ampy`

```bash
# Estacao de Comando (Pico)
ampy --port /dev/ttyACM0 put firmware/micropython/estacao_comando.py main.py

# Estacao de Ignicao (Pico)
ampy --port /dev/ttyACM1 put firmware/micropython/estacao_ignicao.py main.py

# Estacao de Ignicao (ESP32-C3)
ampy --port /dev/ttyUSB0 put firmware/micropython/estacao_ignicao_esp.py main.py
```

## 5. Validar Operacao

1. Ligar estacao de comando.
2. Ligar estacao de ignicao.
3. Confirmar `PING/PONG` no serial e LED amarelo de link.
4. Executar teste com carga dummy no lugar do ignitor.

Se o enlace nao subir, checar antena primeiro.

## 6. Integracao com Ignitor Real

Realizar apenas em ambiente seguro e com procedimento validado.

1. Confirmar continuidade do ignitor.
2. Confirmar antena conectada antes de energizar.
3. Posicionar operador a distancia segura (>= 10 m).
4. Executar sequencia completa.

## 7. Troubleshooting

| Problema | Possivel causa | Acao |
| --- | --- | --- |
| Sem link LoRa | Antena ausente/solta | Reapertar antenas e reiniciar |
| Buzzer sem som | Ligacao incorreta | Verificar pino de buzzer da placa |
| Ignitor nao aciona | Rele/MOSFET | Testar saida com carga dummy |

Detalhes: [troubleshooting.md](./troubleshooting.md).
