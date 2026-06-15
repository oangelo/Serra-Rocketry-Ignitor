# Documentacao do Ignitor

Guias praticos para montar, operar, testar e manter o sistema.

## Fluxo Recomendado

Montar hardware -> Gravar firmware -> Testar -> Operar.

| Etapa | Documento |
| --- | --- |
| Montagem | [INSTALL.md](./INSTALL.md#3-montagem-de-hardware) |
| Envio de firmware | [README_ENVIO.md](./README_ENVIO.md) |
| Testes de bancada/campo | [../test/README.md](../test/README.md) |
| Troubleshooting | [troubleshooting.md](./troubleshooting.md) |
| Protocolo | [README_API.md](./README_API.md) |
| Registro de resultados | [README_TESTS.md](./README_TESTS.md) |

## Referencias Rapidas

- Pinagem: [../hardware/README.md#pinagem](../hardware/README.md#pinagem)
- BOM: [../hardware/README.md#lista-de-componentes-bom](../hardware/README.md#lista-de-componentes-bom)
- Sequencia operacional: [../hardware/README.md#sequencia-de-operacao](../hardware/README.md#sequencia-de-operacao)

## Avisos Importantes

- Sempre usar carga dummy (lampada/LED) durante testes.
- Nunca energizar modulo LoRa sem antena conectada.
- Manter distancia minima de 10 m do foguete em testes de campo.
