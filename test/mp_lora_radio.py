"""
Utilitario LoRa para testes MicroPython com SX1278 (433 MHz).

Compatibilidade:
- Tenta usar biblioteca sx127x (API moderna e legada).
- Se nao conseguir, usa driver nativo via registradores SPI.
"""

import utime
from machine import Pin, SPI

try:
    from sx127x import SX127x
    SX127X_AVAILABLE = True
except Exception as exc:
    SX127X_AVAILABLE = False
    SX127X_IMPORT_ERROR = exc
else:
    SX127X_IMPORT_ERROR = None


# Pinagem padrao do projeto (Raspberry Pi Pico)
PIN_MISO = 0
PIN_CS = 1
PIN_SCK = 2
PIN_MOSI = 3
PIN_RESET = 4
PIN_DIO0 = 15


LORA_PARAMS = {
    "frequency": 433_000_000,
    "bandwidth": 125_000,
    "spreading_factor": 7,
    "coding_rate": 5,
    "output_power": 17,
    "rx_crc": True,
}


# Registradores do SX1278 (modo LoRa)
REG_FIFO = 0x00
REG_OP_MODE = 0x01
REG_FRF_MSB = 0x06
REG_FRF_MID = 0x07
REG_FRF_LSB = 0x08
REG_PA_CONFIG = 0x09
REG_LNA = 0x0C
REG_FIFO_ADDR_PTR = 0x0D
REG_FIFO_TX_BASE = 0x0E
REG_FIFO_RX_BASE = 0x0F
REG_FIFO_RX_CURRENT = 0x10
REG_IRQ_FLAGS = 0x12
REG_RX_NB_BYTES = 0x13
REG_MODEM_CONFIG1 = 0x1D
REG_MODEM_CONFIG2 = 0x1E
REG_PREAMBLE_MSB = 0x20
REG_PREAMBLE_LSB = 0x21
REG_PAYLOAD_LENGTH = 0x22
REG_MODEM_CONFIG3 = 0x26
REG_SYNC_WORD = 0x39
REG_VERSION = 0x42

MODE_SLEEP = 0x00
MODE_STDBY = 0x01
MODE_TX = 0x03
MODE_RX_CONT = 0x05
MODE_LORA = 0x80

IRQ_RX_DONE = 0x40
IRQ_TX_DONE = 0x08
IRQ_PAYLOAD_CRC_ERROR = 0x20


class LoRaRadio:
    """Camada de abstracao para envio/recepcao de mensagens LoRa em texto."""

    def __init__(self, frequency=433_000_000):
        self.frequency = int(frequency)
        self._backend = "mock"
        self._lora = None
        self._sx_error = None

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

        if SX127X_AVAILABLE and self._init_sx127x():
            self._backend = "sx127x"
            print("[LoRa] backend=sx127x")
            return

        if not SX127X_AVAILABLE:
            print("[LoRa] sx127x indisponivel: {}".format(SX127X_IMPORT_ERROR))
        elif self._sx_error is not None:
            print("[LoRa] sx127x falhou, usando fallback nativo: {}".format(self._sx_error))

        if self._init_native():
            self._backend = "native"
            print("[LoRa] backend=native")
        else:
            print("[LoRa] backend=mock (chip nao detectado)")

    @property
    def backend(self):
        return self._backend

    def _legacy_transfer(self, pin, address, value=0x00):
        response = bytearray(1)
        pin.value(0)
        self._spi.write(bytes([address]))
        self._spi.write_readinto(bytes([value]), response)
        pin.value(1)
        return response

    def _init_sx127x(self):
        params = {
            "frequency": float(self.frequency),
            "bandwidth": float(LORA_PARAMS["bandwidth"]),
            "spreading_factor": int(LORA_PARAMS["spreading_factor"]),
            "coding_rate": int(LORA_PARAMS["coding_rate"]),
            "output_power": int(LORA_PARAMS["output_power"]),
            "rx_crc": bool(LORA_PARAMS["rx_crc"]),
        }

        # Tentativa com API moderna.
        try:
            self._lora = SX127x(
                self._spi,
                pins={"cs": self._cs, "reset": self._reset, "dio0": self._dio0},
                parameters=params,
            )
            return True
        except Exception as exc:
            self._sx_error = exc

        # Tentativa com API legada (config_lora + transfer).
        legacy_params = {
            "frequency": int(self.frequency),
            "tx_power_level": int(LORA_PARAMS["output_power"]),
            "signal_bandwidth": int(LORA_PARAMS["bandwidth"]),
            "spreading_factor": int(LORA_PARAMS["spreading_factor"]),
            "coding_rate": int(LORA_PARAMS["coding_rate"]),
            "preamble_length": 8,
            "implicitHeader": False,
            "sync_word": 0x12,
            "enable_CRC": bool(LORA_PARAMS["rx_crc"]),
        }

        try:
            radio = SX127x(parameters=legacy_params)
            radio.pin_ss = self._cs
            radio.pin_RxDone = None
            radio.transfer = self._legacy_transfer
            if hasattr(radio, "init"):
                radio.init()
            self._lora = radio
            return True
        except Exception as exc:
            self._sx_error = exc
            self._lora = None
            return False

    def _write_reg(self, reg, value):
        self._cs.value(0)
        self._spi.write(bytes([reg | 0x80, value & 0xFF]))
        self._cs.value(1)

    def _read_reg(self, reg):
        self._cs.value(0)
        self._spi.write(bytes([reg & 0x7F]))
        data = self._spi.read(1)
        self._cs.value(1)
        return data[0]

    def _read_buf(self, reg, length):
        self._cs.value(0)
        self._spi.write(bytes([reg & 0x7F]))
        data = self._spi.read(length)
        self._cs.value(1)
        return data

    def _write_fifo(self, payload):
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
        version = self._read_reg(REG_VERSION)
        if version != 0x12:
            return False

        self._write_reg(REG_OP_MODE, MODE_LORA | MODE_SLEEP)
        utime.sleep_ms(10)

        frf = int((self.frequency * (1 << 19)) / 32_000_000)
        self._write_reg(REG_FRF_MSB, (frf >> 16) & 0xFF)
        self._write_reg(REG_FRF_MID, (frf >> 8) & 0xFF)
        self._write_reg(REG_FRF_LSB, frf & 0xFF)

        # Configuracao equivalente a BW=125kHz, SF7, CR 4/5.
        self._write_reg(REG_PA_CONFIG, 0x8F)
        self._write_reg(REG_LNA, 0x23)
        self._write_reg(REG_MODEM_CONFIG1, 0x72)
        self._write_reg(REG_MODEM_CONFIG2, 0x74)
        self._write_reg(REG_MODEM_CONFIG3, 0x04)
        self._write_reg(REG_PREAMBLE_MSB, 0x00)
        self._write_reg(REG_PREAMBLE_LSB, 0x08)
        self._write_reg(REG_SYNC_WORD, 0x12)
        self._write_reg(REG_FIFO_TX_BASE, 0x00)
        self._write_reg(REG_FIFO_RX_BASE, 0x00)

        self._write_reg(REG_IRQ_FLAGS, 0xFF)
        self._write_reg(REG_OP_MODE, MODE_LORA | MODE_RX_CONT)
        utime.sleep_ms(10)
        return True

    def _native_send(self, payload):
        if not payload:
            return

        self._write_reg(REG_OP_MODE, MODE_LORA | MODE_STDBY)
        self._write_reg(REG_FIFO_ADDR_PTR, 0x00)
        self._write_reg(REG_PAYLOAD_LENGTH, len(payload))
        self._write_fifo(payload)
        self._write_reg(REG_IRQ_FLAGS, 0xFF)
        self._write_reg(REG_OP_MODE, MODE_LORA | MODE_TX)

        t0 = utime.ticks_ms()
        while utime.ticks_diff(utime.ticks_ms(), t0) < 500:
            if self._read_reg(REG_IRQ_FLAGS) & IRQ_TX_DONE:
                break
            utime.sleep_ms(1)

        self._write_reg(REG_IRQ_FLAGS, 0xFF)
        self._write_reg(REG_OP_MODE, MODE_LORA | MODE_RX_CONT)

    def _sx_packet_available(self):
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

    def send(self, message):
        if not isinstance(message, str):
            message = str(message)

        if self._backend == "sx127x":
            try:
                self._lora.println(message)
            except Exception as exc:
                print("[WARN] erro de envio sx127x: {}".format(exc))
            return

        if self._backend == "native":
            self._native_send(message.encode("utf-8"))
            return

        print("[MOCK TX] {}".format(message))

    def receive(self):
        if self._backend == "sx127x":
            try:
                if not self._sx_packet_available():
                    return None

                payload = self._sx_read_payload()
                if payload is None:
                    return None
                return bytes(payload).decode("utf-8", "ignore").strip()
            except Exception:
                return None

        if self._backend == "native":
            flags = self._read_reg(REG_IRQ_FLAGS)
            if not (flags & IRQ_RX_DONE):
                return None

            self._write_reg(REG_IRQ_FLAGS, 0xFF)
            if flags & IRQ_PAYLOAD_CRC_ERROR:
                return None

            nb_bytes = self._read_reg(REG_RX_NB_BYTES)
            current_addr = self._read_reg(REG_FIFO_RX_CURRENT)
            self._write_reg(REG_FIFO_ADDR_PTR, current_addr)
            raw = self._read_buf(REG_FIFO, nb_bytes)
            try:
                return raw.decode("utf-8", "ignore").strip()
            except Exception:
                return None

        return None