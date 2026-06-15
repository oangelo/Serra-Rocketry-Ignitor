"""
Teste de envio de dados LoRa com ACK para MicroPython.

Como usar em duas placas:
- Placa A: ROLE = "tx"
- Placa B: ROLE = "rx"

Tambem e possivel usar ROLE = "both" para laboratorio rapido.
"""

import utime
from machine import Pin

from mp_lora_radio import LoRaRadio


# "tx", "rx" ou "both"
ROLE = "tx"

SEND_INTERVAL_MS = 1_200
ACK_TIMEOUT_MS = 1_200
MAX_RETRIES = 3
SUMMARY_INTERVAL_MS = 5_000


radio = LoRaRadio()
led_link = Pin(25, Pin.OUT, value=0)

seq = 0
last_send_ms = utime.ticks_add(utime.ticks_ms(), -SEND_INTERVAL_MS)
last_summary_ms = utime.ticks_ms()

pending_seq = None
pending_payload = None
pending_since_ms = 0
pending_attempt = 0

tx_ok = 0
tx_fail = 0
rx_data = 0
ack_sent = 0
duplicate_data = 0
last_rx_seq = None


def blink_led():
    led_link.value(1)
    utime.sleep_ms(40)
    led_link.value(0)


def build_payload(seq_id, now_ms):
    # Payload simples e deterministico para facilitar comparacao de logs.
    temp_c = 24 + (seq_id % 7)
    bat_mv = 3700 + ((seq_id * 11) % 140)
    return "DATA|{}|{}|temp_c={}.0,bat_mv={}".format(seq_id, now_ms, temp_c, bat_mv)


def send_data(payload):
    radio.send(payload)
    blink_led()


def handle_message(message):
    global tx_ok
    global pending_seq
    global pending_payload
    global pending_since_ms
    global pending_attempt
    global rx_data
    global ack_sent
    global duplicate_data
    global last_rx_seq

    if not message:
        return

    parts = message.split("|", 3)
    kind = parts[0]

    if kind == "PING":
        ping_seq = parts[1] if len(parts) > 1 else "0"
        radio.send("PONG|{}|{}".format(ping_seq, utime.ticks_ms()))
        return

    if kind == "DATA":
        if ROLE not in ("rx", "both"):
            return

        if len(parts) < 2:
            print("[WARN] DATA invalido: {}".format(message))
            return

        seq_id = parts[1]
        payload_text = parts[3] if len(parts) > 3 else ""

        if last_rx_seq == seq_id:
            duplicate_data += 1
        last_rx_seq = seq_id

        rx_data += 1
        radio.send("ACK|{}|{}".format(seq_id, utime.ticks_ms()))
        ack_sent += 1

        print("[RX] DATA seq={} payload={}".format(seq_id, payload_text))
        blink_led()
        return

    if kind == "ACK":
        if ROLE not in ("tx", "both"):
            return

        if len(parts) < 2:
            print("[WARN] ACK invalido: {}".format(message))
            return

        ack_seq = parts[1]
        if pending_seq is not None and ack_seq == pending_seq:
            rtt_ms = utime.ticks_diff(utime.ticks_ms(), pending_since_ms)
            tx_ok += 1
            print("[TX] ACK seq={} rtt={} ms tentativas={}".format(ack_seq, rtt_ms, pending_attempt))
            pending_seq = None
            pending_payload = None
            pending_since_ms = 0
            pending_attempt = 0
            blink_led()
        return

    print("[RX] {}".format(message))


print("=" * 60)
print("Teste de envio de dados LoRa com ACK")
print("ROLE={} | backend={}".format(ROLE, radio.backend))
print("=" * 60)

while True:
    now_ms = utime.ticks_ms()

    incoming = radio.receive()
    if incoming:
        handle_message(incoming)

    if ROLE in ("tx", "both"):
        if pending_seq is None and utime.ticks_diff(now_ms, last_send_ms) >= SEND_INTERVAL_MS:
            seq += 1
            pending_seq = str(seq)
            pending_payload = build_payload(seq, now_ms)
            pending_since_ms = now_ms
            pending_attempt = 1
            send_data(pending_payload)
            last_send_ms = now_ms
            print("[TX] DATA seq={} tentativa=1".format(pending_seq))

        if pending_seq is not None and utime.ticks_diff(now_ms, pending_since_ms) >= ACK_TIMEOUT_MS:
            if pending_attempt < MAX_RETRIES:
                pending_attempt += 1
                pending_since_ms = now_ms
                send_data(pending_payload)
                print("[TX] RETRY seq={} tentativa={}".format(pending_seq, pending_attempt))
            else:
                tx_fail += 1
                print("[TX] FAIL seq={} sem ACK apos {} tentativas".format(pending_seq, pending_attempt))
                pending_seq = None
                pending_payload = None
                pending_since_ms = 0
                pending_attempt = 0
                last_send_ms = now_ms

    if utime.ticks_diff(now_ms, last_summary_ms) >= SUMMARY_INTERVAL_MS:
        last_summary_ms = now_ms
        closed_cycles = tx_ok + tx_fail
        success_rate = (tx_ok * 100.0 / closed_cycles) if closed_cycles else 0.0
        print(
            "[SUMMARY] tx_ok={} tx_fail={} success={:.1f}% rx_data={} ack_sent={} dup={} pending={}".format(
                tx_ok,
                tx_fail,
                success_rate,
                rx_data,
                ack_sent,
                duplicate_data,
                pending_seq if pending_seq is not None else "none",
            )
        )

    utime.sleep_ms(10)