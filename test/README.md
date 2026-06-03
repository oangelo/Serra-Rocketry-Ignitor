# Plano de Testes

## Objetivos

- Validar comunicacao LoRa bidirecional entre as estacoes.
- Confirmar sequencia de seguranca com botao mantido por 5 s.
- Testar feedback visual (LEDs) e sonoro (buzzers).
- Verificar abort manual e abort por timeout.

## Requisito Inicial

Antes de qualquer teste, confirme as duas antenas LoRa conectadas e apertadas.

## Testes Prioritarios

### 1. Comunicacao LoRa Basica

Objetivo: confirmar `PING/PONG` de forma estavel.

Checklist:

- [ ] Comando envia `PING` e ignicao responde `PONG`.
- [ ] LED amarelo acende nas duas estacoes quando conectadas.
- [ ] Ao desligar uma estacao, timeout de link ocorre conforme esperado.

Procedimento:

1. Ligar as duas estacoes a 1 m.
2. Observar serial e LEDs.
3. Repetir em 10 m, 50 m, 100 m e 500 m.
4. Registrar RSSI e perdas.

### 2. Sequencia de Ignicao Completa

Objetivo: validar contagem e acionamento final.

Checklist:

- [ ] Botao mantido por 5 s.
- [ ] LED vermelho pisca durante contagem.
- [ ] Buzzer da ignicao emite 5 apitos.
- [ ] Saida de ignicao aciona por 2 s.
- [ ] Comando recebe `IGNITION_COMPLETE`.

Procedimento:

1. Conectar carga dummy na saida de ignicao.
2. Segurar botao de ignicao por 5 s.
3. Confirmar acionamento apenas no final da contagem.

### 3. Abort Manual

Objetivo: garantir cancelamento ao soltar o botao.

Checklist:

- [ ] Botao solto antes de 5 s envia `ABORT`.
- [ ] Contagem para imediatamente.
- [ ] Ignitor nao e acionado.

Procedimento:

1. Iniciar contagem.
2. Soltar no 2o ou 3o apito.
3. Repetir cinco vezes.

### 4. Abort por Timeout

Objetivo: abortar em perda de `ARM_CONFIRMED`.

Checklist:

- [ ] Durante contagem, interromper link/comando.
- [ ] Ignicao detecta timeout (> 500 ms).
- [ ] Estado de erro e sinalizado.
- [ ] Ignitor nao e acionado.

### 5. Alcance em Campo

Objetivo: determinar alcance confiavel do enlace.

Checklist:

- [ ] Executar testes em linha de visao.
- [ ] Avaliar 50 m, 100 m, 200 m, 500 m e 1 km.
- [ ] Registrar taxa de sucesso e RSSI.

## Scripts de Bancada

Arquivos da pasta `test/`:

- `mp_lora_radio.py`: modulo comum de radio.
- `mp_teste_conexao.py`: link `PING/PONG` com estatisticas.
- `mp_teste_envio_dados.py`: envio `DATA` com `ACK` e retry.

Uso em duas placas:

1. Copiar `mp_lora_radio.py` e o script desejado.
2. Ajustar `ROLE` no topo.
3. `initiator` e `responder` para teste de conexao.
4. `tx` e `rx` para teste de envio de dados.

Os scripts seguem a configuracao de radio em `firmware/micropython/`.

## Execucao

### Testes Automatizados

```bash
cd test
python run_tests.py --all
python run_tests.py --lora
python run_tests.py --ignition
```

### Testes Manuais

Seguir os procedimentos acima e registrar resultado em `docs/README_TESTS.md`.

## Seguranca

- Nunca usar ignitor real em bancada.
- Sempre usar carga dummy.
- Manter pessoas a pelo menos 10 m.
- Usar EPI adequado durante testes energizados.
