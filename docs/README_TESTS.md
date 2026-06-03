# Resultados de Testes

## Matriz de Testes

| ID | Tipo | Descrição | Critério | Status |
|----|------|---------|---------|--------|
| LORA-01 | LoRa | PING/PONG bidirecional | PONG < 500 ms | Pendente |
| LORA-02 | LoRa | RSSI a 50 m | RSSI > -80 dBm | Pendente |
| LORA-03 | LoRa | RSSI a 500 m | RSSI > -120 dBm | Pendente |
| IGN-01 | Ignição | Sequência completa (5 s) | Relé aciona após 5 s | Pendente |
| IGN-02 | Ignição | Contagem de apitos | 5 apitos audíveis | Pendente |
| IGN-03 | Ignição | LEDs | Vermelho pisca → sólido | Pendente |
| ABORT-01 | Segurança | Abort manual | Botão solto cancela | Pendente |
| ABORT-02 | Segurança | Abort por timeout | Perda > 500 ms cancela | Pendente |

**Status**: Pendente | Passou | Falhou

## Registro de Sessões

| Data | ID | Resultado | Distância | RSSI | Observações |
|------|----|---------|---------|------|-----------|
| - | - | - | - | - | - |

- Logs salvos em `test/logs/` (não versionado)
- Vídeos/fotos grandes linkados externamente

## Procedimento

Após cada sessão:

1. Preencher registro acima
2. Salvar logs em `test/logs/sessao_YYYYMMDD.csv`
3. Linkar evidências no registro

Consulte [test/README.md](../test/README.md) para procedimentos detalhados.