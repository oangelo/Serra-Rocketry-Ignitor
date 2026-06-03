# Envio de Firmware para Pico e ESP32-C3

Este guia mostra como enviar os scripts MicroPython para as placas do projeto.

## Arquivos por Placa

### Pico da Estacao de Comando

- `firmware/micropython/estacao_comando.py` (salvar como `main.py`)
- `firmware/micropython/sx127x.py` (opcional)
- `firmware/micropython/config_lora.py` (opcional)

### Pico da Estacao de Ignicao

- `firmware/micropython/estacao_ignicao.py` (salvar como `main.py`)
- `firmware/micropython/sx127x.py` (opcional)
- `firmware/micropython/config_lora.py` (opcional)

### ESP32-C3 da Estacao de Ignicao

- `firmware/micropython/estacao_ignicao_esp.py` (salvar como `main.py`)
- `firmware/micropython/sx127x.py` (opcional, existe fallback nativo)

## 1. Descobrir Porta Serial

```bash
ls /dev/ttyACM* /dev/ttyUSB*
```

Exemplo comum:

- Comando: `/dev/ttyACM0`
- Ignicao Pico: `/dev/ttyACM1`
- Ignicao ESP32-C3: `/dev/ttyUSB0`

## 2. Envio com ampy

### 2.1 Estacao de Comando (Pico)

```bash
ampy --port /dev/ttyACM0 put firmware/micropython/estacao_comando.py main.py
ampy --port /dev/ttyACM0 ls
```

### 2.2 Estacao de Ignicao (Pico)

```bash
ampy --port /dev/ttyACM1 put firmware/micropython/estacao_ignicao.py main.py
ampy --port /dev/ttyACM1 ls
```

### 2.3 Estacao de Ignicao (ESP32-C3)

```bash
ampy --port /dev/ttyUSB0 put firmware/micropython/estacao_ignicao_esp.py main.py
ampy --port /dev/ttyUSB0 ls
```

## 3. Envio com Thonny

1. Abrir Thonny.
2. Selecionar interpretador MicroPython da placa.
3. Abrir arquivo em `firmware/micropython/`.
4. Salvar no dispositivo como `main.py`.

## 4. Logs Seriais

```bash
screen /dev/ttyACM0 115200
```

Trocar a porta conforme a placa conectada.

## 5. Regra Importante de Antena

Antes de energizar ou testar, confirme as duas antenas LoRa conectadas e apertadas. Sem antena, o radio pode inicializar, mas o enlace PING/PONG nao fecha de forma confiavel.

## 6. Erros Comuns

### Permissao negada na serial

```bash
sudo usermod -aG dialout $USER
```

Depois, encerre e reabra a sessao.

### Placa nao aparece em `/dev/ttyACM*` ou `/dev/ttyUSB*`

- Trocar cabo USB (dados, nao apenas carga).
- Testar outra porta USB.
- Regravar MicroPython na placa.

## Creditos da Biblioteca LoRa

Projeto baseado/adaptado de:

- [SX127x driver for (Micro)Python on ESP8266/ESP32/Raspberry_Pi](https://github.com/Wei1234c/SX127x_driver_for_MicroPython_on_ESP8266)

Arquivos locais relacionados:

- `firmware/micropython/sx127x.py`
- `firmware/micropython/config_lora.py`
