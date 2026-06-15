# Changelog

Baseado em [Keep a Changelog](https://keepachangelog.com) e [Versionamento Semântico](https://semver.org).

## [Unreleased]

### Planejado
- Firmware validado
- Testes de campo
- Cases 3D

## [1.0.0] - 2026-04-21

### Adicionado
- **Hardware**: BOM e pinagem para ESP32-C3 SuperMini (Estação de Ignição)
- **Firmware**: `estacao_ignicao_esp.py` para ESP32-C3
- **Protocolo**: Documentação simplificada com diagrama de estados
- **Documentação**: Repositório refatorado (arquivos renomeados, índice consolidado)

### Alterado
- **BOM**: Comando usa Raspberry Pi Pico; Ignição usa ESP32-C3 SuperMini
- **Estrutura**: docs/ renomeado para padrão consistente

## [0.1.0] - 2024-11-14

### Adicionado
- Estrutura inicial do repositório
- Documentação de arquitetura
- BOM e pinagem Raspberry Pi Pico
- Protocolo LoRa 433 MHz
- Guias de instalação e troubleshooting
- Plano de testes