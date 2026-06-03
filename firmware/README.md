# Firmware - Serra Rocketry Ignitor

Repositorio de firmware e arquivos auxiliares do projeto.

## Estrutura Atual

```text
firmware/
├── micropython/
│   ├── estacao_comando.py
│   ├── estacao_ignicao.py
│   ├── estacao_ignicao_esp.py
│   ├── sx127x.py
│   └── config_lora.py
└── data/
    ├── index.html
    ├── script.js
    ├── style.css
    └── hammer.min.js
```

## Firmware Oficial (MicroPython)

| Estacao | Arquivo | Placa alvo | Salvar como |
| --- | --- | --- | --- |
| Comando | [micropython/estacao_comando.py](./micropython/estacao_comando.py) | Raspberry Pi Pico | `main.py` |
| Ignicao (principal) | [micropython/estacao_ignicao_esp.py](./micropython/estacao_ignicao_esp.py) | ESP32-C3 SuperMini | `main.py` |
| Ignicao (legado) | [micropython/estacao_ignicao.py](./micropython/estacao_ignicao.py) | Raspberry Pi Pico | `main.py` |

Arquivos de suporte:

- [micropython/sx127x.py](./micropython/sx127x.py)
- [micropython/config_lora.py](./micropython/config_lora.py)

Pinagem completa e BOM:

- [../hardware/README.md](../hardware/README.md#pinagem)

## Pasta data

A pasta [data](./data) contem arquivos web auxiliares para experimentos e interfaces locais.
Ela nao substitui os scripts MicroPython de operacao das estacoes.

## Gravacao nas Placas

Guia rapido de envio:

- [../docs/README_ENVIO.md](../docs/README_ENVIO.md)

Guia de instalacao completo:

- [../docs/INSTALL.md](../docs/INSTALL.md#4-gravar-firmware)

## Debug Serial

```bash
screen /dev/ttyACM0 115200
```

Exemplo de logs esperados:

```text
[LoRa] SX1278 inicializado em 433 MHz.
[CMD] Link com ignicao: OK
[CMD] ACK recebido da base de ignicao.
[CMD] IGNITION_COMPLETE recebido.
```

## Seguranca

- Sempre conectar antena LoRa antes de energizar.
- Testar primeiro com carga dummy (LED/lampada).
- Manter distancia segura durante qualquer teste operacional.
