#!/usr/bin/env python3
"""UserPromptSubmit-Hook: macht Kontextgröße und Sitzungskosten sichtbar.

Hintergrund (Messung 2026-08-15): 67 % des Token-Verbrauchs sind
Wieder-Einlesen von Kontext, nicht erzeugter Text. Die Hauptsitzung lief mit
im Mittel 320k Kontext und 658 Modell-Anfragen je Ticket — jede Anfrage
bezahlt den gesamten bisherigen Kontext erneut, und die Hauptsitzungen
verursachten damit 55 % des Gesamtverbrauchs bei nur einem Drittel der
Anfragen. Der laufende Verbrauch war für beide Seiten unsichtbar, deshalb
wurde nie gegengesteuert.

Dieser Hook gibt bei jeder Nutzereingabe eine Zeile aus, sobald der Kontext
eine Schwelle überschreitet — sonst schweigt er (kostet dann null Token).

Immer exit 0 — darf eine Eingabe niemals blockieren.
"""

import json
import sys
from pathlib import Path

# Schwellen in Token. HINWEIS: ab hier lohnt /clear beim nächsten Themenwechsel.
# DRINGEND: ab hier kostet jeder weitere Schritt mehr als der Themenwechsel.
SCHWELLE_HINWEIS = 180_000
SCHWELLE_DRINGEND = 260_000

# Preise USD je Mio. Token (Stand 2026-08): Opus 5 / Sonnet 5 / Haiku 4.5.
# Reihenfolge: (input, cache_write, cache_read, output)
PREISE = {
    "opus": (5.0, 6.25, 0.50, 25.0),
    "sonnet": (3.0, 3.75, 0.30, 15.0),
    "haiku": (1.0, 1.25, 0.10, 5.0),
}


def _familie(model: str) -> str:
    m = (model or "").lower()
    for k in ("opus", "sonnet", "haiku"):
        if k in m:
            return k
    return "opus"


def _auswerten(transcript: Path):
    """Liefert (aktueller Kontext, kumulierte Kosten der Sitzung in USD).

    Kontext = letzte beobachtete Anfrage (input + cache_read + cache_write).
    Kosten  = Summe über alle Anfragen dieser Transcript-Datei.
    """
    ctx = 0
    kosten = 0.0
    try:
        with transcript.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"usage"' not in line:
                    continue
                try:
                    eintrag = json.loads(line)
                except ValueError:
                    continue
                msg = eintrag.get("message") or {}
                u = msg.get("usage")
                if not isinstance(u, dict):
                    continue
                ein = u.get("input_tokens", 0) or 0
                schreib = u.get("cache_creation_input_tokens", 0) or 0
                lese = u.get("cache_read_input_tokens", 0) or 0
                aus = u.get("output_tokens", 0) or 0
                gesamt = ein + schreib + lese
                if gesamt > 0:
                    ctx = gesamt  # letzte gewinnt
                p_ein, p_schreib, p_lese, p_aus = PREISE[_familie(msg.get("model"))]
                kosten += (
                    ein * p_ein + schreib * p_schreib + lese * p_lese + aus * p_aus
                ) / 1e6
    except OSError:
        return 0, 0.0
    return ctx, kosten


def main() -> int:
    try:
        eingabe = json.load(sys.stdin)
    except Exception:
        return 0

    pfad = eingabe.get("transcript_path")
    if not pfad:
        return 0

    ctx, kosten = _auswerten(Path(pfad))
    if ctx < SCHWELLE_HINWEIS:
        return 0  # Normalfall: keine Ausgabe, keine Kosten

    kctx = ctx // 1000
    if ctx >= SCHWELLE_DRINGEND:
        print(
            f"⚑ Kontext {kctx}k · diese Sitzung bisher ~${kosten:.0f}. "
            f"Jeder weitere Schritt bezahlt diese {kctx}k erneut. "
            f"Ist das laufende Ticket abgeschlossen, JETZT `/clear` vorschlagen — "
            f"nicht auf Nachfrage warten. Bis dahin: Bash-Aufrufe bündeln, "
            f"breite Suchen an einen Subagenten geben, gezielt statt ganze Dateien lesen."
        )
    else:
        print(
            f"⚑ Kontext {kctx}k · diese Sitzung bisher ~${kosten:.0f}. "
            f"Beim nächsten Themenwechsel `/clear` vorschlagen."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
