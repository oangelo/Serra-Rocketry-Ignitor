"""
Teste de conexao LoRa via PING/PONG para MicroPython.

Como usar em duas placas:
- Placa A: ROLE = "initiator"
- Placa B: ROLE = "responder"

Tambem e possivel usar ROLE = "both" em ambas para diagnostico rapido.
"""

import utime
from machine import Pin

from mp_lora_radio import LoRaRadio


# "initiator", "responder" ou "both"
ROLE = "initiator"

PING_INTERVAL_MS = 1_000
PING_TIMEOUT_MS = 3_000
SUMMARY_INTERVAL_MS = 5_000


radio = LoRaRadio()
led_link = Pin(25, Pin.OUT, value=0)

seq = 0
sent_ping = 0
recv_pong = 0
timeouts = 0
rtt_total_ms = 0
rtt_count = 0

pending = {}  # seq(str) -> ticks_ms

last_ping_ms = utime.ticks_add(utime.ticks_ms(), -PING_INTERVAL_MS)
last_summary_ms = utime.ticks_ms()


def blink_led():
    led_link.value(1)
    utime.sleep_ms(40)
    led_link.value(0)


def handle_message(message):
    global recv_pong
    global rtt_total_ms
    global rtt_count

    if not message:
        return

    parts = message.split("|")
    command = parts[0]

    if command == "PING":
        incoming_seq = parts[1] if len(parts) > 1 else "0"
        radio.send("PONG|{}|{}".format(incoming_seq, utime.ticks_ms()))
        print("[RX] PING seq={} -> PONG".format(incoming_seq))
        blink_led()
        return

    if command == "PONG":
        recv_pong += 1
        pong_seq = parts[1] if len(parts) > 1 else None
        if pong_seq and pong_seq in pending:
            start_ms = pending.pop(pong_seq)
            rtt_ms = utime.ticks_diff(utime.ticks_ms(), start_ms)
            rtt_total_ms += rtt_ms
            rtt_count += 1
            print("[RX] PONG seq={} rtt={} ms".format(pong_seq, rtt_ms))
        else:
            print("[RX] PONG sem correlacao: {}".format(message))
        blink_led()
        return

    print("[RX] {}".format(message))


print("=" * 60)
print("Teste de conexao LoRa (PING/PONG)")
print("ROLE={} | backend={}".format(ROLE, radio.backend))
print("=" * 60)

while True:
    now_ms = utime.ticks_ms()

    incoming = radio.receive()
    if incoming:
        handle_message(incoming)

    if ROLE in ("initiator", "both"):
        if utime.ticks_diff(now_ms, last_ping_ms) >= PING_INTERVAL_MS:
            last_ping_ms = now_ms
            seq += 1
            seq_str = str(seq)
            pending[seq_str] = now_ms
            radio.send("PING|{}|{}".format(seq_str, now_ms))
            sent_ping += 1
            print("[TX] PING seq={}".format(seq_str))

    expired = []
    for seq_key in pending:
        started_ms = pending[seq_key]
        if utime.ticks_diff(now_ms, started_ms) > PING_TIMEOUT_MS:
            expired.append(seq_key)

    for seq_key in expired:
        pending.pop(seq_key, None)
        timeouts += 1
        print("[WARN] timeout aguardando PONG seq={}".format(seq_key))

    if utime.ticks_diff(now_ms, last_summary_ms) >= SUMMARY_INTERVAL_MS:
        last_summary_ms = now_ms
        success_rate = (recv_pong * 100.0 / sent_ping) if sent_ping else 0.0
        avg_rtt = (rtt_total_ms / rtt_count) if rtt_count else 0.0
        print(
            "[SUMMARY] sent={} recv={} timeout={} success={:.1f}% avg_rtt={:.1f} ms".format(
                sent_ping,
                recv_pong,
                timeouts,
                success_rate,
                avg_rtt,
            )
        )

    utime.sleep_ms(10)