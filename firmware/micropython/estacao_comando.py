"""
ESTACAO DE COMANDO - SISTEMA DE IGNICAO LoRa

Pinagem SX1278 -> Raspberry Pi Pico
- MOSI: GP3 (pino fisico 5)
- MISO: GP0 (pino fisico 1)
- SCK: GP2 (pino fisico 4)
- CS: GP1 (pino fisico 2)
- RESET: GP4 (pino fisico 6)
- DIO0: GP15 (pino fisico 20)

Perifericos
- LED amarelo: GP11
- LED vermelho: GP12
- Buzzer: GP19
- Botao de ignicao: GP13 (pull-up interno)
"""

from machine import Pin, SPI
import utime


# ─────────────────────────────────────────────────────────────────
#  Driver LoRa (SX127x): prioridade para biblioteca externa,
#  com fallback para driver nativo em SPI se sx127x.py nao existir.
# ─────────────────────────────────────────────────────────────────
USE_SX127X_DRIVER = False

if USE_SX127X_DRIVER:
    try:
        from sx127x import SX127x
        SX127X_DRIVER_AVAILABLE = True
    except Exception as exc:
        SX127X_DRIVER_AVAILABLE = False
        print("[WARN] sx127x indisponivel ({}) - usando driver nativo SX1278.".format(exc))
else:
    SX127X_DRIVER_AVAILABLE = False
    print("[BOOT] Driver nativo SX1278 selecionado (sx127x desativado).")


# ╔══════════════════════════════════════════════════════════════╗
# ║                     CONFIGURAÇÕES                           ║
# ╚══════════════════════════════════════════════════════════════╝

# ── Pinos SPI / LoRa ─────────────────────────────────────────────
PIN_MOSI  = 3
PIN_MISO  = 0
PIN_SCK   = 2
PIN_CS    = 1
PIN_RESET = 4
PIN_DIO0  = 15

# ── Periféricos ──────────────────────────────────────────────────
PIN_LED_YELLOW = 11  # status de conexao e armamento
PIN_LED_RED    = 12  # acende fixo ao receber ACK
PIN_BUZZER     = 19  # bipes de alerta
PIN_BUTTON     = 13  # botao momentaneo (active-low, pull-up)
PIN_LED_LINK   = 25  # LED onboard: indica status de link LoRa

# ── Tempos (ms) ──────────────────────────────────────────────────
HOLD_REQUIRED_MS   = 5_000   # tempo que o botão deve ficar pressionado
DEBOUNCE_MS        = 50      # janela de debounce
BLINK_INTERVAL_MS  = 250     # cadência do LED amarelo / buzzer
ACK_TIMEOUT_MS     = 2_000   # aguarda ACK por este tempo após ARM_CONFIRMED
RETRANSMIT_MS      = 200     # intervalo entre re-envios do ARM_CONFIRMED
PING_INTERVAL_MS   = 1_000   # intervalo de PING para teste de conexao
LINK_TIMEOUT_MS    = 3_000   # sem PONG neste tempo = sem conexao
LINK_BLINK_MS      = 250     # pisca LED de link enquanto desconectado
FINALIZE_DELAY_MS  = 3_000   # espera apos ignicao concluida

# ── Mensagens LoRa ───────────────────────────────────────────────
MSG_ARM    = "ARM_CONFIRMED"
MSG_ABORT  = "ABORT"
MSG_ACK    = "ACK"
MSG_DONE   = "IGNITION_COMPLETE"
MSG_PING   = "PING"
MSG_PONG   = "PONG"

# ── Parâmetros LoRa (SX1278 @ 433 MHz) ──────────────────────────
LORA_PARAMS = {
    "frequency"         : 433e6,
    "bandwidth"         : 125e3,
    "spreading_factor"  : 7,
    "coding_rate"       : 5,        # 4/5
    "output_power"      : 17,       # dBm (máx 20)
    "rx_crc"            : True,
}

# ── Registradores e flags do SX1278 (fallback nativo) ──────────
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
REG_VERSION         = 0x42

MODE_SLEEP   = 0x00
MODE_STDBY   = 0x01
MODE_TX      = 0x03
MODE_RX_CONT = 0x05
MODE_LORA    = 0x80

IRQ_RX_DONE           = 0x40
IRQ_TX_DONE           = 0x08
IRQ_PAYLOAD_CRC_ERROR = 0x20


# ╔══════════════════════════════════════════════════════════════╗
# ║                    ESTADOS DA MÁQUINA                       ║
# ╚══════════════════════════════════════════════════════════════╝
class State:
    # Estado inicial: aguardando a pressão do botão de ignição.
    IDLE        = "IDLE"
    # Estado de armamento: o botão está pressionado e o sistema conta 5 segundos.
    ARMING      = "ARMING"
    # Estado de transmissão: envia repetidamente o comando de armamento.
    TRANSMITTING = "TRANSMITTING"
    # Estado de confirmação: ignicao concluida no receptor.
    CONFIRMED   = "CONFIRMED"
    # Estado de aborto: envia ABORT para o receptor e retorna a IDLE.
    ABORTING    = "ABORTING"


# ╔══════════════════════════════════════════════════════════════╗
# ║                  DRIVER LoRa (wrapper)                      ║
# ╚══════════════════════════════════════════════════════════════╝
class LoRaRadio:
    """
    Abstracao sobre o radio SX1278.

    Ordem de tentativa:
    1) Driver externo sx127x.py (se instalado);
    2) Driver nativo por registradores SPI;
    3) Modo mock (sem transmissao real).
    """

    def __init__(self):
        self._lora = None
        self._backend = "mock"

        self._spi = SPI(
            0,
            baudrate=1_000_000,
            polarity=0,
            phase=0,
            sck=Pin(PIN_SCK),
            mosi=Pin(PIN_MOSI),
            miso=Pin(PIN_MISO),
        )
        self._cs = Pin(PIN_CS, Pin.OUT, value=1)
        self._reset = Pin(PIN_RESET, Pin.OUT, value=1)
        self._dio0 = Pin(PIN_DIO0, Pin.IN)

        if SX127X_DRIVER_AVAILABLE:
            try:
                self._lora = SX127x(
                    self._spi,
                    pins={
                        "cs"    : self._cs,
                        "reset" : self._reset,
                        "dio0"  : self._dio0,
                    },
                    parameters=LORA_PARAMS,
                )
                self._backend = "sx127x"
                print("[LoRa] SX1278 inicializado em 433 MHz (driver sx127x).")
                return
            except Exception as exc:
                if "unexpected keyword argument 'pins'" in str(exc):
                    print("[INFO] API sx127x legada detectada - tentando compatibilidade.")
                else:
                    print(f"[WARN] Falha no sx127x padrao ({exc}) - tentando compatibilidade.")
                try:
                    self._lora = self._init_legacy_sx127x()
                    self._backend = "sx127x"
                    print("[LoRa] SX1278 inicializado em 433 MHz (sx127x legacy compat).")
                    return
                except Exception as legacy_exc:
                    print(f"[WARN] Falha na compatibilidade sx127x ({legacy_exc}) - fallback nativo.")

        if self._init_native():
            self._backend = "native"
            print("[LoRa] SX1278 inicializado em 433 MHz (driver nativo SPI).")
        else:
            print("[LoRa] Modo MOCK ativo (sem resposta do SX1278).")

    def _legacy_transfer(self, pin, address, value=0x00):
        response = bytearray(1)
        pin.value(0)
        self._spi.write(bytes([address]))
        self._spi.write_readinto(bytes([value]), response)
        pin.value(1)
        return response

    def _init_legacy_sx127x(self):
        legacy_params = {
            "frequency"      : int(LORA_PARAMS["frequency"]),
            "tx_power_level" : int(LORA_PARAMS["output_power"]),
            "signal_bandwidth": int(LORA_PARAMS["bandwidth"]),
            "spreading_factor": int(LORA_PARAMS["spreading_factor"]),
            "coding_rate"    : int(LORA_PARAMS["coding_rate"]),
            "preamble_length" : 8,
            "implicitHeader" : False,
            "sync_word"      : 0x12,
            "enable_CRC"     : bool(LORA_PARAMS["rx_crc"]),
        }

        radio = SX127x(parameters=legacy_params)
        radio.pin_ss = self._cs
        radio.pin_RxDone = None
        radio.transfer = self._legacy_transfer
        if hasattr(radio, "init"):
            radio.init()
        return radio

    def _sx_received_packet(self):
        if not self._lora:
            return False

        if hasattr(self._lora, "received_packet"):
            return bool(self._lora.received_packet())

        if hasattr(self._lora, "receivedPacket"):
            return bool(self._lora.receivedPacket())

        return False

    def _sx_read_payload(self):
        if not self._lora or not hasattr(self._lora, "read_payload"):
            return None

        try:
            return self._lora.read_payload(with_header=False)
        except TypeError:
            return self._lora.read_payload()

    def _native_write_reg(self, reg, value):
        self._cs.value(0)
        self._spi.write(bytes([reg | 0x80, value & 0xFF]))
        self._cs.value(1)

    def _native_read_reg(self, reg):
        self._cs.value(0)
        self._spi.write(bytes([reg & 0x7F]))
        result = self._spi.read(1)
        self._cs.value(1)
        return result[0]

    def _native_read_buf(self, reg, length):
        self._cs.value(0)
        self._spi.write(bytes([reg & 0x7F]))
        result = self._spi.read(length)
        self._cs.value(1)
        return result

    def _native_write_fifo(self, payload):
        self._cs.value(0)
        self._spi.write(bytes([REG_FIFO | 0x80]))
        self._spi.write(payload)
        self._cs.value(1)

    def _native_reset(self):
        self._reset.value(0)
        utime.sleep_ms(10)
        self._reset.value(1)
        utime.sleep_ms(10)

    def _init_native(self):
        self._native_reset()

        version = self._native_read_reg(REG_VERSION)
        if version != 0x12:
            print(f"[WARN] SX1278 nao detectado no driver nativo (REG_VERSION=0x{version:02X}).")
            return False

        self._native_write_reg(REG_OP_MODE, MODE_LORA | MODE_SLEEP)
        utime.sleep_ms(10)

        frf = int((int(LORA_PARAMS["frequency"]) * (1 << 19)) / 32_000_000)
        self._native_write_reg(REG_FRF_MSB, (frf >> 16) & 0xFF)
        self._native_write_reg(REG_FRF_MID, (frf >> 8) & 0xFF)
        self._native_write_reg(REG_FRF_LSB, frf & 0xFF)

        self._native_write_reg(REG_PA_CONFIG, 0x8F)
        self._native_write_reg(REG_LNA, 0x23)
        self._native_write_reg(REG_MODEM_CONFIG1, 0x72)
        self._native_write_reg(REG_MODEM_CONFIG2, 0x74)
        self._native_write_reg(REG_MODEM_CONFIG3, 0x04)
        self._native_write_reg(REG_PREAMBLE_MSB, 0x00)
        self._native_write_reg(REG_PREAMBLE_LSB, 0x08)
        self._native_write_reg(REG_SYNC_WORD, 0x12)
        self._native_write_reg(REG_FIFO_TX_BASE, 0x00)
        self._native_write_reg(REG_FIFO_RX_BASE, 0x00)

        self._native_write_reg(REG_OP_MODE, MODE_LORA | MODE_RX_CONT)
        utime.sleep_ms(10)
        return True

    def _native_send_packet(self, payload):
        if not payload:
            return

        self._native_write_reg(REG_OP_MODE, MODE_LORA | MODE_STDBY)
        self._native_write_reg(REG_FIFO_ADDR_PTR, 0x00)
        self._native_write_reg(REG_PAYLOAD_LENGTH, len(payload))
        self._native_write_fifo(payload)
        self._native_write_reg(REG_IRQ_FLAGS, 0xFF)

        self._native_write_reg(REG_OP_MODE, MODE_LORA | MODE_TX)

        t0 = utime.ticks_ms()
        tx_done = False
        while utime.ticks_diff(utime.ticks_ms(), t0) < 300:
            if self._native_read_reg(REG_IRQ_FLAGS) & IRQ_TX_DONE:
                tx_done = True
                break
            utime.sleep_ms(1)

        self._native_write_reg(REG_IRQ_FLAGS, 0xFF)
        self._native_write_reg(REG_OP_MODE, MODE_LORA | MODE_RX_CONT)

        if not tx_done:
            print("[WARN] Timeout aguardando TX_DONE no SX1278.")

    def _native_receive_packet(self):
        flags = self._native_read_reg(REG_IRQ_FLAGS)
        if not (flags & IRQ_RX_DONE):
            return None

        self._native_write_reg(REG_IRQ_FLAGS, 0xFF)

        if flags & IRQ_PAYLOAD_CRC_ERROR:
            return None

        nb_bytes = self._native_read_reg(REG_RX_NB_BYTES)
        current_addr = self._native_read_reg(REG_FIFO_RX_CURRENT)
        self._native_write_reg(REG_FIFO_ADDR_PTR, current_addr)
        raw = self._native_read_buf(REG_FIFO, nb_bytes)

        try:
            return raw.decode("utf-8", "ignore").strip()
        except Exception:
            return None

    def send(self, message):
        """Transmite uma mensagem pela interface LoRa e mostra log local."""
        try:
            if self._backend == "sx127x":
                self._lora.println(message)
            elif self._backend == "native":
                self._native_send_packet(message.encode("utf-8"))
        except Exception as exc:
            print(f"[WARN] Falha no envio LoRa ({self._backend}): {exc}")
        print(f"[LoRa TX] → {message}")

    @property
    def backend(self):
        return self._backend

    def receive(self):
        """
        Lê um pacote LoRa não bloqueante, se houver.

        Retorna a mensagem decodificada ou None quando não há nenhum pacote.
        """
        try:
            if self._backend == "sx127x" and self._sx_received_packet():
                payload = self._sx_read_payload()
                if payload is None:
                    return None
                msg = bytes(payload).decode("utf-8", "ignore").strip()
                print(f"[LoRa RX] ← {msg}")
                return msg

            if self._backend == "native":
                msg = self._native_receive_packet()
                if msg:
                    print(f"[LoRa RX] ← {msg}")
                    return msg
        except Exception as exc:
            print(f"[WARN] Falha na leitura LoRa ({self._backend}): {exc}")
        return None


# ╔══════════════════════════════════════════════════════════════╗
# ║                 ESTAÇÃO DE COMANDO                          ║
# ╚══════════════════════════════════════════════════════════════╝
class CommandStation:
    """
    Máquina de estados para a estação de comando.

    Esta classe controla o ciclo de armamento e transmissão de mensagens
    de ignição via LoRa, usando um botão físico e indicadores visuais.

    Fluxo de estados:
    IDLE -> ARMING -> TRANSMITTING -> CONFIRMED -> IDLE
    """

    def __init__(self):
        # Inicializa os componentes físicos e o rádio LoRa.
        self.led_yellow = Pin(PIN_LED_YELLOW, Pin.OUT, value=0)
        self.led_red    = Pin(PIN_LED_RED,    Pin.OUT, value=0)
        self.buzzer     = Pin(PIN_BUZZER,     Pin.OUT, value=0)
        self.led_link   = Pin(PIN_LED_LINK,   Pin.OUT, value=0)
        self.button     = Pin(PIN_BUTTON,     Pin.IN,  Pin.PULL_UP)
        self.lora       = LoRaRadio()
        print(f"[CMD] Backend LoRa ativo: {self.lora.backend}")

        # Estado atual da máquina e estado anterior reservado para futura expansão.
        self.state       = State.IDLE
        self._prev_state = None

        # Tempos de controle usados para armamento, piscar e transmissão.
        self._press_start_ms  = 0    # instante em que o botão foi pressionado
        self._last_blink_ms   = 0    # instante do último piscar do LED/buzzer
        self._last_tx_ms      = 0    # instante do último envio de ARM_CONFIRMED
        self._tx_start_ms     = 0    # instante do início da fase de transmissão
        self._finalize_start_ms = 0  # inicio da janela de finalizacao
        self._ack_received = False

        # Debounce do botão para evitar leituras falsas.
        self._last_btn_change_ms = 0
        self._btn_stable_state   = True   # True significa botão solto (pull-up ativo)

        # Estado de toggle para o efeito de piscar.
        self._blink_on = False

        # Estado de link com a estacao de ignicao.
        self._link_ok = False
        self._last_ping_ms = 0
        self._last_pong_ms = None
        self._last_no_link_warn_ms = 0
        self._last_link_blink_ms = 0
        self._link_led_on = False
        self._last_mock_warn_ms = 0

    # ─────────────────────────────────────────
    #  LEITURA COM DEBOUNCE
    # ─────────────────────────────────────────
    def _button_pressed(self) -> bool:
        """
        Retorna True se o botão está estável e pressionado.
        Implementa debounce por tempo: só atualiza o estado estável
        após DEBOUNCE_MS ms de sinal constante.
        """
        raw = self.button.value() == 0   # active-low
        now = utime.ticks_ms()

        if raw != self._btn_stable_state:
            if utime.ticks_diff(now, self._last_btn_change_ms) >= DEBOUNCE_MS:
                self._btn_stable_state   = raw
                self._last_btn_change_ms = now

        return self._btn_stable_state

    # ─────────────────────────────────────────
    #  CONTROLE DE SAÍDAS
    # ─────────────────────────────────────────
    def _all_off(self):
        """Desliga todos os indicadores visuais e sonoros."""
        self.led_yellow.value(0)
        self.led_red.value(0)
        self.buzzer.value(0)
        self._blink_on = False

    def _refresh_link(self, now):
        """Mantem o teste de conexao ativo com PING/PONG."""
        if utime.ticks_diff(now, self._last_ping_ms) >= PING_INTERVAL_MS:
            self._last_ping_ms = now
            self.lora.send(MSG_PING)

        incoming = self.lora.receive()
        if incoming == MSG_PING:
            self.lora.send(MSG_PONG)
            self._last_pong_ms = now
        elif incoming == MSG_PONG:
            self._last_pong_ms = now

        link_was_ok = self._link_ok
        if self._last_pong_ms is None:
            self._link_ok = False
        else:
            self._link_ok = utime.ticks_diff(now, self._last_pong_ms) <= LINK_TIMEOUT_MS
        if self._link_ok != link_was_ok:
            status = "OK" if self._link_ok else "PERDIDO"
            print(f"[CMD] Link com ignicao: {status}")
        if self._link_ok:
            self.led_link.value(1)
            self._link_led_on = True
        elif utime.ticks_diff(now, self._last_link_blink_ms) >= LINK_BLINK_MS:
            self._last_link_blink_ms = now
            self._link_led_on = not self._link_led_on
            self.led_link.value(1 if self._link_led_on else 0)

    def _blink_tick(self):
        """Alterna LED amarelo e buzzer em BLINK_INTERVAL_MS."""
        now = utime.ticks_ms()
        if utime.ticks_diff(now, self._last_blink_ms) >= BLINK_INTERVAL_MS:
            self._last_blink_ms = now
            self._blink_on = not self._blink_on
            self.led_yellow.value(self._blink_on)
            self.buzzer.value(self._blink_on)

    # ─────────────────────────────────────────
    #  TRANSIÇÕES DE ESTADO
    # ─────────────────────────────────────────
    def _enter_idle(self):
        self._all_off()
        if self._link_ok:
            self.led_yellow.value(1)
        self.state = State.IDLE
        print("[CMD] Estado: IDLE — aguardando botão.")

    def _enter_arming(self): 
        self._press_start_ms = utime.ticks_ms()
        self._last_blink_ms  = self._press_start_ms
        self._last_tx_ms     = utime.ticks_add(self._press_start_ms, -RETRANSMIT_MS)
        self._ack_received   = False
        self.state = State.ARMING
        print("[CMD] Estado: ARMING — mantenha o botão por 5 s...")

    def _enter_transmitting(self):
        self._tx_start_ms = utime.ticks_ms()
        self._last_tx_ms  = 0
        self.led_red.value(1 if self._ack_received else 0)
        self.state = State.TRANSMITTING
        print("[CMD] Estado: TRANSMITTING — mantendo ARM_CONFIRMED ativo.")

    def _enter_confirmed(self):
        self._all_off()
        self.led_red.value(1)
        self._finalize_start_ms = utime.ticks_ms()
        self.state = State.CONFIRMED
        print("[CMD] Estado: CONFIRMED — IGNITION_COMPLETE recebido.")

    def _enter_aborting(self):
        self.lora.send(MSG_ABORT)
        self._all_off()
        self.state = State.ABORTING
        print("[CMD] Estado: ABORTING — ABORT enviado.")
        # Retorna imediatamente ao IDLE (sem lógica adicional necessária)
        self._enter_idle()

    # ─────────────────────────────────────────
    #  HANDLERS DE CADA ESTADO
    # ─────────────────────────────────────────
    def _handle_idle(self):
        # Apenas aguarda o início do armamento quando o botão é pressionado.
        now = utime.ticks_ms()
        self._refresh_link(now)

        if self.lora.backend == "mock" and utime.ticks_diff(now, self._last_mock_warn_ms) >= 3000:
            self._last_mock_warn_ms = now
            print("[CMD] RADIO EM MOCK: verifique cabos SPI/energia do SX1278 no comando.")

        if self._link_ok:
            self.led_yellow.value(1)

        if self._button_pressed():
            if not self._link_ok:
                if utime.ticks_diff(now, self._last_no_link_warn_ms) >= 1_000:
                    self._last_no_link_warn_ms = now
                    print("[CMD] Sem link LoRa ativo. Armamento bloqueado.")
                return
            self._enter_arming()

    def _handle_arming(self):
        # Se o botão for solto antes de 5 segundos, o processo é cancelado.
        if not self._button_pressed():
            print("[CMD] Botao solto antes dos 5 s - enviando ABORT.")
            self._enter_aborting()
            return

        now = utime.ticks_ms()

        # Enquanto o botao estiver pressionado, mantem o receptor em contagem.
        if utime.ticks_diff(now, self._last_tx_ms) >= RETRANSMIT_MS:
            self._last_tx_ms = now
            self.lora.send(MSG_ARM)

        incoming = self.lora.receive()
        if incoming == MSG_ACK:
            if not self._ack_received:
                self._ack_received = True
                self.led_red.value(1)
                print("[CMD] ACK recebido da base de ignicao.")
        elif incoming == MSG_DONE:
            self._enter_confirmed()
            return
        elif incoming == MSG_PING:
            self.lora.send(MSG_PONG)
        elif incoming == MSG_PONG:
            self._last_pong_ms = now
            self._link_ok = True

        # Enquanto o botão estiver pressionado, pisca LED amarelo e buzzer.
        self._blink_tick()

        elapsed = utime.ticks_diff(now, self._press_start_ms)
        remaining = max(0, (HOLD_REQUIRED_MS - elapsed) // 1000)

        # Exibe uma atualização de tempo a cada segundo.
        if elapsed // 1000 != (elapsed - 50) // 1000:
            print(f"[CMD] Armando... {remaining} s restantes.")

        # Se o tempo minimo for atingido, continua transmitindo ate o DONE.
        if elapsed >= HOLD_REQUIRED_MS:
            self._enter_transmitting()

    def _handle_transmitting(self):
        # Se o botão soltar durante a transmissão, aborta imediatamente.
        if not self._button_pressed():
            print("[CMD] Botão solto durante transmissão — ABORT.")
            self._enter_aborting()
            return

        now = utime.ticks_ms()

        # Reenvia o comando de armamento periodicamente.
        if utime.ticks_diff(now, self._last_tx_ms) >= RETRANSMIT_MS:
            self._last_tx_ms = now
            self.lora.send(MSG_ARM)

        # Verifica se o receptor devolveu o ACK.
        incoming = self.lora.receive()
        if incoming == MSG_ACK:
            if not self._ack_received:
                self._ack_received = True
                self.led_red.value(1)
                print("[CMD] ACK recebido da base de ignicao.")
        elif incoming == MSG_DONE:
            self._enter_confirmed()
            return
        elif incoming == MSG_PING:
            self.lora.send(MSG_PONG)
        elif incoming == MSG_PONG:
            self._last_pong_ms = now
            self._link_ok = True

        # Se não receber ACK dentro do tempo, reinicia a janela de espera.
        if utime.ticks_diff(now, self._tx_start_ms) >= ACK_TIMEOUT_MS:
            print("[CMD] Timeout aguardando ACK — continuando a transmitir.")
            self._tx_start_ms = now

    def _handle_confirmed(self):
        # Aguarda a janela de seguranca final e emite dois bipes curtos.
        if utime.ticks_diff(utime.ticks_ms(), self._finalize_start_ms) >= FINALIZE_DELAY_MS:
            print("[CMD] Ciclo concluido. Emitindo bipes de finalizacao.")
            for _ in range(2):
                self.buzzer.value(1)
                utime.sleep_ms(120)
                self.buzzer.value(0)
                utime.sleep_ms(120)
            self._enter_idle()

    # ─────────────────────────────────────────
    #  LOOP PRINCIPAL
    # ─────────────────────────────────────────
    def run(self):
        # Exibe cabeçalho de inicialização do sistema.
        print("=" * 60)
        print("  ESTAÇÃO DE COMANDO — Sistema de Ignição LoRa 433 MHz")
        print("=" * 60)
        self._enter_idle()

        while True:
            if self.state == State.IDLE:
                self._handle_idle()
            elif self.state == State.ARMING:
                self._handle_arming()
            elif self.state == State.TRANSMITTING:
                self._handle_transmitting()
            elif self.state == State.CONFIRMED:
                self._handle_confirmed()

            # Pequena pausa para manter a execução responsiva sem bloquear demais.
            utime.sleep_ms(10)


# ╔══════════════════════════════════════════════════════════════╗
# ║                    PONTO DE ENTRADA                         ║
# ╚══════════════════════════════════════════════════════════════╝
if __name__ == "__main__":
    station = CommandStation()
    station.run()
