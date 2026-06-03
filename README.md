# Serra Rocketry Ignitor

Sistema de ignicao remota para foguetes experimentais.

## Visao Geral

Duas estacoes independentes se comunicam via LoRa 433 MHz:

| Estacao | Funcao | MCU |
| --- | --- | --- |
| Comando | Operacao remota e seguranca | Raspberry Pi Pico |
| Ignicao | Acionamento do ignitor | ESP32-C3 SuperMini ou Raspberry Pi Pico |

## Sequencia de Ignicao

1. Operador segura o botao por 5 s.
2. Comando transmite `ARM_CONFIRMED` continuamente.
3. Ignicao executa contagem regressiva (5 bipes).
4. Rele aciona por 2 s.
5. Ignicao envia `IGNITION_COMPLETE`.

## Comece Aqui

| Passo | Guia |
| --- | --- |
| 1. Montar | [docs/INSTALL.md](./docs/INSTALL.md) |
| 2. Gravar firmware | [docs/README_ENVIO.md](./docs/README_ENVIO.md) |
| 3. Testar | [test/README.md](./test/README.md) |
| 4. Diagnosticar problemas | [docs/troubleshooting.md](./docs/troubleshooting.md) |

## Estrutura do Repositorio

```text
ignitor/
├── docs/                 # Guias e referencias
├── firmware/
│   ├── micropython/      # Scripts oficiais (.py)
│   └── data/             # Arquivos web/auxiliares
├── hardware/             # BOM, pinagem e materiais fisicos
├── software/             # Legado/compatibilidade
└── test/                 # Scripts e procedimentos de teste
```

## Componentes Principais

| Qtd | Componente | Uso |
| --- | --- | --- |
| 1 | Raspberry Pi Pico | Estacao de Comando |
| 1 | ESP32-C3 SuperMini | Estacao de Ignicao (principal) |
| 2 | Modulo LoRa SX1278 | Comunicacao 433 MHz |
| 2 | LED amarelo 5mm | Status de link |
| 2 | LED vermelho 5mm | Status de ignicao |
| 2 | Buzzer ativo 5V | Feedback sonoro |
| 1 | Botao de ignicao 22 mm | Acionamento |
| 1 | Rele/MOSFET | Saida para ignitor |
| 2 | Modulo TP4056 | Carga de bateria |

Pinagem completa e BOM: [hardware/README.md](./hardware/README.md).

## Regras de Seguranca

- Botao de ignicao deve ser momentaneo (sem trava).
- O comando precisa ser mantido pelos 5 s completos.
- Perda de sinal por mais de 500 ms deve abortar.
- Sempre usar carga dummy antes de ignitor real.
- Sempre conectar antena LoRa antes de energizar.
- Manter distancia minima de 10 m entre operador e foguete.

## Projeto

Projeto da [Serra Rocketry](https://github.com/Serra-Rocketry).
