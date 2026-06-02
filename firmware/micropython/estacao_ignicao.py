# ==============================================================================
#   ESTAÇÃO DE IGNIÇÃO DE FOGUETES - RECEPTOR/ATUADOR # type: ignore
#   Hardware: Raspberry Pi Pico + LoRa SX1278 (433 MHz) # type: ignore
#   Protocolo: SPI
# ==============================================================================
#
#   MAPEAMENTO DE PINOS: # type: ignore
#   ─────────────────────────────────────────────────────
#   SX1278 (LoRa)         Pico
#   ─────────────────────────────────────────────────────
#   SCK        ──────────  GP2 - 4
#   MOSI       ──────────  GP3 - 5
#   MISO       ──────────  GP0 - 1
#   NSS (CS)   ──────────  GP1 - 2
#   RESET      ──────────  GP4 - 6
#   ─────────────────────────────────────────────────────
#   Relê               ──  GP26   (Ativo em ALTO - NAO INVERTER)
#   Buzzer             ──  GP19
#   LED Vermelho       ──  GP12   (Contagem / Erro)
#   LED Amarelo        ──  GP11   (Conectado / Ativo)
#   ─────────────────────────────────────────────────────
#
#   LÓGICA DE SEGURANÇA:
#   - O Relê é inicializado em BAIXO e SÓ é ativado após
#     5 segundos contínuos de sinal "ARM_CONFIRMED".
#   - Qualquer interrupção do sinal (>500 ms) ou recepção
#     de "ABORT" reseta imediatamente a contagem.
#   - O sistema usa ticks_ms() para temporização não-bloqueante,
#     garantindo que o rádio continue sendo lido durante a contagem.
#   - A estacao inicia diretamente apos energizacao pela chave geral.
# ==============================================================================

import utime
from machine import Pin, SPI

try:
    from sx127x import SX127x
    SX127X_DRIVER_AVAILABLE = True
except Exception as exc:
    SX127X_DRIVER_AVAILABLE = False
    print("[WARN] sx127x indisponivel na Ignicao ({}) - usando driver nativo SX1278.".format(exc))

# =============================================================================
#  DEFINIÇÃO DE PINOS
# =============================================================================
SPI_SCK  = 2
SPI_MOSI = 3
SPI_MISO = 0
SPI_DIO0 = 15  # opcional no driver de biblioteca

# Pinos de controle do SX1278
LORA_CS    = Pin(1, Pin.OUT, value=1)  # NSS: HIGH = modulo desmarcado
LORA_RESET = Pin(4, Pin.OUT, value=1)  # RESET: LOW por 10ms para resetar
LORA_DIO0  = Pin(SPI_DIO0, Pin.IN)

# Ajuste para 0 caso seu modulo de rele seja acionado em nivel baixo.
RELE_ACTIVE_LEVEL    = 1
RELE_INACTIVE_LEVEL  = 0 if RELE_ACTIVE_LEVEL else 1

# Atuadores e Indicadores
PIN_RELE         = Pin(26, Pin.OUT, value=RELE_INACTIVE_LEVEL)
PIN_BUZZER       = Pin(19, Pin.OUT, value=0)
PIN_LED_VERMELHO = Pin(12, Pin.OUT, value=0)  # Vermelho: Pisca em contagem/erro, ON ignicao
PIN_LED_AMARELO  = Pin(11, Pin.OUT, value=0)  # Amarelo: ON quando conectado/ativo
PIN_LED_LINK     = Pin(25, Pin.OUT, value=0)  # LED onboard: status de conexao

def _set_rele(ligado):
    PIN_RELE.value(RELE_ACTIVE_LEVEL if ligado else RELE_INACTIVE_LEVEL)

LORA_PARAMS = {
    "frequency"         : 433e6,
    "bandwidth"         : 125e3,
    "spreading_factor"  : 7,
    "coding_rate"       : 5,
    "output_power"      : 17,
    "rx_crc"            : True,
}

# =============================================================================
#  ENDERECOS DE REGISTRADORES DO SX1278
# =============================================================================

REG_FIFO            = 0x00
REG_OP_MODE         = 0x01
REG_FRF_MSB         = 0x06
REG_FRF_MID         = 0x07
REG_FRF_LSB         = 0x08
REG_PA_CONFIG       = 0x09
REG_LNA             = 0x0C
REG_FIFO_ADDR_PTR   = 0x0D
REG_FIFO_TX_BASE    = 0x0E
REG_FIFO_RX_BASE    = 0x0F
REG_FIFO_RX_CURRENT = 0x10
REG_IRQ_FLAGS       = 0x12
REG_RX_NB_BYTES     = 0x13
REG_MODEM_CONFIG1   = 0x1D
REG_MODEM_CONFIG2   = 0x1E
REG_PREAMBLE_MSB    = 0x20
REG_PREAMBLE_LSB    = 0x21
REG_PAYLOAD_LENGTH  = 0x22
REG_MODEM_CONFIG3   = 0x26
REG_SYNC_WORD       = 0x39
REG_DIO_MAPPING1    = 0x40
REG_VERSION         = 0x42

# Modos de operacao do SX1278
MODE_SLEEP   = 0x00
MODE_STDBY   = 0x01
MODE_TX      = 0x03
MODE_RX_CONT = 0x05
MODE_LORA    = 0x80  # Bit 7 = 1 habilita modo LoRa

# Mascaras de flag de interrupcao (registrador IRQ_FLAGS)
IRQ_RX_DONE = 0x40  # Pacote recebido com sucesso
IRQ_TX_DONE = 0x08  # Transmissao concluida

# =============================================================================
#  INICIALIZACAO DO BARRAMENTO SPI
# =============================================================================

spi = SPI(0,
          baudrate=1_000_000,
          polarity=0,
          phase=0,
          sck=Pin(SPI_SCK),
          mosi=Pin(SPI_MOSI),
          miso=Pin(SPI_MISO))

lora_driver = None
lora_backend = "native"

# =============================================================================
#  FUNCOES SPI DE BAIXO NIVEL
# =============================================================================

def _spi_write(reg, value):
    # Bit 7 = 1 indica operacao de escrita no SX1278
    LORA_CS.value(0)
    spi.write(bytes([reg | 0x80, value]))
    LORA_CS.value(1)

def _spi_read(reg):
    # Bit 7 = 0 indica operacao de leitura
    LORA_CS.value(0)
    spi.write(bytes([reg & 0x7F]))
    result = spi.read(1)
    LORA_CS.value(1)
    return result[0]

def _spi_read_buf(reg, length):
    # Leitura de multiplos bytes consecutivos do FIFO
    LORA_CS.value(0)
    spi.write(bytes([reg & 0x7F]))
    result = spi.read(length)
    LORA_CS.value(1)
    return result


def _toggle_pin(pin):
    """Alterna pinos de forma compativel com firmwares sem Pin.toggle()."""
    pin.value(0 if pin.value() else 1)

def _sx127x_legacy_transfer(pin, address, value=0x00):
    response = bytearray(1)
    pin.value(0)
    spi.write(bytes([address]))
    spi.write_readinto(bytes([value]), response)
    pin.value(1)
    return response

def _init_legacy_sx127x(frequency):
    params = {
        "frequency"      : int(frequency),
        "tx_power_level" : int(LORA_PARAMS["output_power"]),
        "signal_bandwidth": int(LORA_PARAMS["bandwidth"]),
        "spreading_factor": int(LORA_PARAMS["spreading_factor"]),
        "coding_rate"    : int(LORA_PARAMS["coding_rate"]),
        "preamble_length" : 8,
        "implicitHeader" : False,
        "sync_word"      : 0x12,
        "enable_CRC"     : bool(LORA_PARAMS["rx_crc"]),
    }

    radio = SX127x(parameters=params)
    radio.pin_ss = LORA_CS
    radio.pin_RxDone = None
    radio.transfer = _sx127x_legacy_transfer
    if hasattr(radio, "init"):
        radio.init()
    return radio

def _sx127x_packet_available():
    if not lora_driver:
        return False

    if hasattr(lora_driver, "received_packet"):
        return bool(lora_driver.received_packet())

    if hasattr(lora_driver, "receivedPacket"):
        return bool(lora_driver.receivedPacket())

    return False

def _sx127x_read_payload():
    if not lora_driver or not hasattr(lora_driver, "read_payload"):
        return None

    try:
        return lora_driver.read_payload(with_header=False)
    except TypeError:
        return lora_driver.read_payload()

# =============================================================================
#  DRIVER DO MODULO LORA SX1278
# =============================================================================

def lora_reset():
    # Pulso de reset por hardware conforme datasheet do SX1278 (minimo 100us)
    LORA_RESET.value(0)
    utime.sleep_ms(10)
    LORA_RESET.value(1)
    utime.sleep_ms(10)

def lora_init(frequency=433_000_000):
    global lora_driver, lora_backend

    if SX127X_DRIVER_AVAILABLE:
        try:
            params = dict(LORA_PARAMS)
            params["frequency"] = float(frequency)
            lora_driver = SX127x(
                spi,
                pins={
                    "cs": LORA_CS,
                    "reset": LORA_RESET,
                    "dio0": LORA_DIO0,
                },
                parameters=params,
            )
            lora_backend = "sx127x"
            return True
        except Exception as exc:
            if "unexpected keyword argument 'pins'" in str(exc):
                print("[INFO] API sx127x legada detectada na Ignicao - tentando compatibilidade.")
            else:
                print("[WARN] Falha no sx127x padrao da Ignicao ({}). Tentando compatibilidade.".format(exc))
            try:
                lora_driver = _init_legacy_sx127x(frequency)
                lora_backend = "sx127x"
                print("[BOOT] SX1278 inicializado em modo sx127x legacy compat.")
                return True
            except Exception as legacy_exc:
                print("[WARN] Falha na compatibilidade sx127x da Ignicao ({}). Fallback nativo.".format(legacy_exc))
                lora_driver = None
                lora_backend = "native"

    # Inicializa o SX1278 em modo LoRa
    lora_reset()

    # Verifica identidade do chip: SX1276/77/78/79 retornam 0x12
    version = _spi_read(REG_VERSION)
    if version != 0x12:
        return False  # SPI com defeito ou modulo nao conectado

    # Entra em Sleep com LoRa ativado
    _spi_write(REG_OP_MODE, MODE_LORA | MODE_SLEEP)
    utime.sleep_ms(10)

    # Calcula e grava os registradores de frequencia
    frf = int((frequency * (1 << 19)) / 32_000_000)
    _spi_write(REG_FRF_MSB, (frf >> 16) & 0xFF)
    _spi_write(REG_FRF_MID, (frf >> 8)  & 0xFF)
    _spi_write(REG_FRF_LSB,  frf        & 0xFF)

    # Potencia de saida via PA_BOOST: 17 dBm
    _spi_write(REG_PA_CONFIG, 0x8F)

    # LNA: ganho maximo automatico com boost para banda HF (433 MHz)
    _spi_write(REG_LNA, 0x23)

    # Modem Config 1: BW=125kHz, CodingRate=4/5, Header explicito
    _spi_write(REG_MODEM_CONFIG1, 0x72)

    # Modem Config 2: SF=7, CRC habilitado
    _spi_write(REG_MODEM_CONFIG2, 0x74)

    # Modem Config 3: AGC automatico habilitado
    _spi_write(REG_MODEM_CONFIG3, 0x04)

    # Preambulo de 8 simbolos (minimo recomendado)
    _spi_write(REG_PREAMBLE_MSB, 0x00)
    _spi_write(REG_PREAMBLE_LSB, 0x08)

    # Sync Word privado: 0x12
    _spi_write(REG_SYNC_WORD, 0x12)

    # Enderecos base do FIFO para TX e RX (sem sobreposicao)
    _spi_write(REG_FIFO_TX_BASE, 0x00)
    _spi_write(REG_FIFO_RX_BASE, 0x00)

    # Volta ao Standby antes de iniciar recepcao
    _spi_write(REG_OP_MODE, MODE_LORA | MODE_STDBY)
    utime.sleep_ms(10)

    lora_backend = "native"
    return True

def lora_receive_mode():
    if lora_backend == "sx127x":
        return
    _spi_write(REG_OP_MODE, MODE_LORA | MODE_RX_CONT)

def lora_packet_available():
    if lora_backend == "sx127x":
        try:
            return _sx127x_packet_available()
        except Exception:
            return False

    flags = _spi_read(REG_IRQ_FLAGS)
    return bool(flags & IRQ_RX_DONE)

def lora_read_packet():
    if lora_backend == "sx127x":
        try:
            payload = _sx127x_read_payload()
            if payload is None:
                return None
            return bytes(payload).decode("utf-8", "ignore").strip()
        except Exception:
            return None

    flags = _spi_read(REG_IRQ_FLAGS)
    _spi_write(REG_IRQ_FLAGS, 0xFF)

    if flags & 0x20:
        return None  # Descarta pacote com CRC invalido

    nb_bytes     = _spi_read(REG_RX_NB_BYTES)
    current_addr = _spi_read(REG_FIFO_RX_CURRENT)

    _spi_write(REG_FIFO_ADDR_PTR, current_addr)
    raw = _spi_read_buf(REG_FIFO, nb_bytes)

    try:
        return raw.decode("utf-8").strip()
    except Exception:
        return None

def lora_send(message):
    if lora_backend == "sx127x":
        if not lora_driver:
            return
        try:
            lora_driver.println(message)
        except Exception:
            pass
        return

    _spi_write(REG_OP_MODE, MODE_LORA | MODE_STDBY)
    utime.sleep_ms(5)

    _spi_write(REG_FIFO_ADDR_PTR, 0x00)
    encoded = message.encode("utf-8")
    for byte in encoded:
        _spi_write(REG_FIFO, byte)
    _spi_write(REG_PAYLOAD_LENGTH, len(encoded))

    _spi_write(REG_OP_MODE, MODE_LORA | MODE_TX)

    timeout = utime.ticks_add(utime.ticks_ms(), 3000)
    while not (_spi_read(REG_IRQ_FLAGS) & IRQ_TX_DONE):
        if utime.ticks_diff(timeout, utime.ticks_ms()) <= 0:
            break
        utime.sleep_ms(1)

    _spi_write(REG_IRQ_FLAGS, 0xFF)
    lora_receive_mode()

# =============================================================================
#  SINALIZACAO (LED E BUZZER)
# =============================================================================

def buzzer_bip(duracao_ms=100):
    PIN_BUZZER.value(1)
    utime.sleep_ms(duracao_ms)
    PIN_BUZZER.value(0)

def sinalizar_erro(n=3):
    # Estado Erro: Amarelo OFF, Vermelho PISCA
    PIN_LED_AMARELO.value(0)
    for _ in range(n):
        PIN_LED_VERMELHO.value(1)
        buzzer_bip(150)
        utime.sleep_ms(150)
        PIN_LED_VERMELHO.value(0)
        utime.sleep_ms(150)

def desligar_tudo():
    # Estado Desligado: Todos os atuadores e LEDs OFF
    _set_rele(False)
    PIN_BUZZER.value(0)
    PIN_LED_VERMELHO.value(0)
    PIN_LED_AMARELO.value(0)
    PIN_LED_LINK.value(0)

# =============================================================================
#  MAQUINA DE ESTADOS - LOGICA PRINCIPAL
# =============================================================================

ESTADO_AGUARDANDO = "AGUARDANDO"  # Aguarda "ARM_CONFIRMED"
ESTADO_CONTAGEM   = "CONTAGEM"   # Contagem regressiva de 5s
ESTADO_IGNICAO    = "IGNICAO"    # Rele acionado por 2s
ESTADO_COMPLETO   = "COMPLETO"   # Ciclo concluido

TEMPO_CONTAGEM_MS   = 5000
TEMPO_IGNICAO_MS    = 2000
TIMEOUT_SINAL_MS    = 500
TIMEOUT_LINK_LED_MS = 3000
INTERVALO_PISCA_MS  = 250
INTERVALO_BUZZER_MS = 500
INTERVALO_PING_BOOT_MS = 700
INTERVALO_PISCA_LINK_MS = 500

MSG_ARM   = "ARM_CONFIRMED"
MSG_ABORT = "ABORT"
MSG_ACK   = "ACK"
MSG_DONE  = "IGNITION_COMPLETE"

def executar():
    # --- SETUP -------------------------------------------------------------
    print("[BOOT] Inicializando Estacao de Ignicao...")
    desligar_tudo()  # Estado "Desligado" na tabela

    print("[BOOT] Sinalizando energia...")
    buzzer_bip(500)

    print("[BOOT] Inicializando modulo LoRa SX1278...")
    if not lora_init(frequency=433_000_000):
        print("[ERRO] Modulo LoRa nao detectado! Verifique o cabeamento SPI.")
        # Trava indicando estado de Erro (Amarelo OFF, Vermelho PISCA)
        while True:
            sinalizar_erro(5)
            utime.sleep_ms(1000)

    print("[BOOT] LoRa OK. Modo de recepcao ativo.")
    lora_receive_mode()

    print("[BOOT] Chave geral ativa. Prosseguindo com auto-inicializacao.")

    # --- TESTE DE CONEXAO --------------------------------------------------
    print("[TESTE] Iniciando handshake com a Base (PING/PONG)...")

    t_inicio_teste = utime.ticks_ms()
    t_ultimo_ping  = utime.ticks_add(t_inicio_teste, -INTERVALO_PING_BOOT_MS)
    t_ultimo_pisca_link = t_inicio_teste
    led_link_estado = False
    PIN_LED_LINK.value(0)
    conexao_ok     = False

    while utime.ticks_diff(utime.ticks_ms(), t_inicio_teste) < 5000:
        agora_teste = utime.ticks_ms()

        if utime.ticks_diff(agora_teste, t_ultimo_pisca_link) >= INTERVALO_PISCA_LINK_MS:
            t_ultimo_pisca_link = agora_teste
            led_link_estado = not led_link_estado
            PIN_LED_LINK.value(1 if led_link_estado else 0)

        if utime.ticks_diff(agora_teste, t_ultimo_ping) >= INTERVALO_PING_BOOT_MS:
            t_ultimo_ping = agora_teste
            lora_send("PING")

        if lora_packet_available():
            msg = lora_read_packet()
            if msg == "PING":
                # Se a Base alcancou esta estacao, ja existe link de controle.
                lora_send("PONG")
                conexao_ok = True
                print("[TESTE] PING recebido da Base, PONG enviado.")
                break

            if msg == "PONG":
                conexao_ok = True
                print("[TESTE] PONG recebido da Base.")
                break

        utime.sleep_ms(10)

    if conexao_ok:
        # Estado "Conectado": Amarelo ON, Vermelho OFF
        PIN_LED_AMARELO.value(1)
        PIN_LED_LINK.value(1)
        led_link_estado = True
        buzzer_bip(200)
        print("[OK] Conexao com a Base estabelecida.")
    else:
        # Estado "Erro": Amarelo OFF, Vermelho PISCA
        sinalizar_erro(4)
        print("[AVISO] Sem resposta da Base. Continuando sem confirmacao de link.")

    # --- VARIAVEIS DE ESTADO -----------------------------------------------
    estado               = ESTADO_AGUARDANDO
    t_inicio_contagem    = 0
    t_ultimo_arm         = 0
    t_ultimo_link        = utime.ticks_ms() if conexao_ok else None
    t_inicio_ignicao     = 0
    t_ultimo_pisca       = 0
    t_ultimo_buz         = 0
    led_vermelho_estado  = False
    link_reportado_ok    = None

    print("[LOOP] Aguardando ARM_CONFIRMED...")

    # --- LOOP PRINCIPAL ----------------------------------------------------
    while True:
        agora = utime.ticks_ms()

        mensagem_recebida = None
        if lora_packet_available():
            mensagem_recebida = lora_read_packet()
            if mensagem_recebida:
                t_ultimo_link = agora
                print("[RX] '{}' | Estado: {}".format(mensagem_recebida, estado))

        if mensagem_recebida == "PING":
            lora_send("PONG")
            t_ultimo_link = agora
            mensagem_recebida = None

        link_ok = (
            t_ultimo_link is not None
            and utime.ticks_diff(agora, t_ultimo_link) <= TIMEOUT_LINK_LED_MS
        )
        if link_ok != link_reportado_ok:
            link_reportado_ok = link_ok
            if link_ok:
                print("[LINK] Conexao com a Base: OK")
            else:
                print("[LINK] Conexao com a Base: PERDIDA")

        if link_ok:
            PIN_LED_LINK.value(1)
            led_link_estado = True
        elif utime.ticks_diff(agora, t_ultimo_pisca_link) >= INTERVALO_PISCA_LINK_MS:
            t_ultimo_pisca_link = agora
            led_link_estado = not led_link_estado
            PIN_LED_LINK.value(1 if led_link_estado else 0)

        # ------------------------------------------------------------------
        #  ESTADO: AGUARDANDO (Conectado)
        # ------------------------------------------------------------------
        if estado == ESTADO_AGUARDANDO:
            PIN_LED_AMARELO.value(1)   # Amarelo ON
            PIN_LED_VERMELHO.value(0)  # Vermelho OFF
            PIN_BUZZER.value(0)

            if mensagem_recebida == MSG_ARM:
                lora_send(MSG_ACK)
                print("[ARM] Sinal recebido! Iniciando contagem de 5s...")
                t_inicio_contagem = agora
                t_ultimo_arm      = agora
                t_ultimo_pisca    = agora
                t_ultimo_buz      = agora
                estado = ESTADO_CONTAGEM

        # ------------------------------------------------------------------
        #  ESTADO: CONTAGEM REGRESSIVA (Ignição Iminente)
        # ------------------------------------------------------------------
        elif estado == ESTADO_CONTAGEM:
            PIN_LED_AMARELO.value(1)  # Amarelo ON

            if mensagem_recebida == MSG_ARM:
                t_ultimo_arm = agora

            sinal_perdido  = utime.ticks_diff(agora, t_ultimo_arm) > TIMEOUT_SINAL_MS
            abort_recebido = (mensagem_recebida == MSG_ABORT)

            if abort_recebido or sinal_perdido:
                motivo = "ABORT recebido" if abort_recebido else "Sinal perdido (>500ms)"
                print("[SEGURANCA] {}! Resetando contagem.".format(motivo))
                desligar_tudo()
                
                # Entra no estado de Erro (Amarelo OFF, Vermelho PISCA)
                sinalizar_erro(6)
                
                estado = ESTADO_AGUARDANDO
                continue

            # Pisca o LED Vermelho
            if utime.ticks_diff(agora, t_ultimo_pisca) >= INTERVALO_PISCA_MS:
                led_vermelho_estado = not led_vermelho_estado
                PIN_LED_VERMELHO.value(led_vermelho_estado)
                t_ultimo_pisca = agora

            if utime.ticks_diff(agora, t_ultimo_buz) >= INTERVALO_BUZZER_MS:
                _toggle_pin(PIN_BUZZER)
                t_ultimo_buz = agora

            decorrido = utime.ticks_diff(agora, t_inicio_contagem)
            restante  = max(0, TEMPO_CONTAGEM_MS - decorrido)
            if decorrido % 1000 < 50:
                print("[CONTAGEM] {}s restantes...".format(restante // 1000 + 1))

            if decorrido >= TEMPO_CONTAGEM_MS:
                if lora_packet_available():
                    msg_final = lora_read_packet()
                    if msg_final == MSG_ABORT:
                        print("[SEGURANCA] ABORT no instante final. Ignicao cancelada.")
                        desligar_tudo()
                        sinalizar_erro(6)
                        estado = ESTADO_AGUARDANDO
                        continue

                if utime.ticks_diff(agora, t_ultimo_arm) > TIMEOUT_SINAL_MS:
                    print("[SEGURANCA] Sinal perdido no instante final. Ignicao cancelada.")
                    desligar_tudo()
                    sinalizar_erro(6)
                    estado = ESTADO_AGUARDANDO
                    continue

                print("[IGNICAO] Contagem completa! Acionando rele...")
                PIN_BUZZER.value(0)
                
                # Ignição Ativa: Amarelo ON, Vermelho ON
                PIN_LED_VERMELHO.value(1)
                PIN_LED_AMARELO.value(1)
                
                _set_rele(True)
                t_inicio_ignicao = agora
                estado = ESTADO_IGNICAO

        # ------------------------------------------------------------------
        #  ESTADO: IGNICAO (Ignição Ativa)
        # ------------------------------------------------------------------
        elif estado == ESTADO_IGNICAO:
            decorrido_ignicao = utime.ticks_diff(agora, t_inicio_ignicao)

            if decorrido_ignicao >= TEMPO_IGNICAO_MS:
                _set_rele(False)
                print("[IGNICAO] Rele desligado. Enviando telemetria...")

                lora_send(MSG_DONE)
                print("[TX] '{}' enviado para a Base.".format(MSG_DONE))

                for _ in range(5):
                    _toggle_pin(PIN_LED_VERMELHO)
                    buzzer_bip(80)
                    utime.sleep_ms(80)
                PIN_LED_VERMELHO.value(0)

                estado = ESTADO_COMPLETO
                print("[OK] Sequencia de ignicao concluida.")

        # ------------------------------------------------------------------
        #  ESTADO: COMPLETO
        # ------------------------------------------------------------------
        elif estado == ESTADO_COMPLETO:
            _set_rele(False)
            utime.sleep_ms(3000)
            desligar_tudo()  # Volta pro estado Desligado antes de resetar
            estado = ESTADO_AGUARDANDO
            print("[RESET] Sistema pronto para nova sequencia.")

        utime.sleep_ms(5)


# =============================================================================
#  PONTO DE ENTRADA
# =============================================================================
if __name__ == "__main__":
    executar()
