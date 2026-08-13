"""Geteilte GSM-7-Zeichensatz-Pruefung fuer ALLE SMS-Pfade (Issue #1533 S4).

Extrahiert aus ``tests/tdd/test_compare_sms_gsm7_charset.py:82-141`` (#1362
S5b), damit Compare-, Trip-Briefing- und amtlicher-Alarm-Waechter gegen
DIESELBE Definition pruefen. Zwei getrennt gepflegte Tabellen koennen beide
gruen sein und trotzdem verschiedene Welten pruefen.

Fuehrender Unterstrich: Test-Helfer, kein pytest-Testfall (Vorbild
``tests/tdd/_hiking_window_fixtures.py``).

Warum ueberhaupt: sobald ein einziges GSM-7-fremdes Zeichen in der SMS steht,
kodiert der Betreiber die GANZE Nachricht in UCS-2 -- dort passen nur 67
Zeichen je Teil statt 153 (SMS-Verkettung, 3GPP TS 23.040). Eine STILLE
Kostenverdopplung, die keine reine Laengenpruefung sieht.
"""
from __future__ import annotations

# GSM 03.38 / 3GPP TS 23.038 Abschnitt 6.2.1 (Default Alphabet).
_GSM7_BASIC = (
    "@£$¥èéùìòÇ\nØø\rÅå"
    "Δ_ΦΓΛΩΠΨΣΘΞÆæßÉ"
    " !\"#¤%&'()*+,-./"
    "0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"
    "¿abcdefghijklmnopqrstuvwxyzäöñüà"
)

# 128 Codepunkte (0x00-0x7F) minus ESC (0x1B, kein eigenes Zeichen, leitet
# nur zur Extension-Tabelle um) = 127 druckbare/Steuer-Zeichen.
assert len(_GSM7_BASIC) == len(set(_GSM7_BASIC)) == 127, (
    f"GSM7-Basisalphabet-Tabelle falsch abgetippt oder mit Duplikaten: "
    f"erwartet 127 verschiedene Zeichen, gezaehlt {len(_GSM7_BASIC)} "
    f"({len(set(_GSM7_BASIC))} verschieden)."
)

# Die Extension-Tabelle (Form-Feed, ^ { } \ [ ~ ] | €) ist zwar GSM-7-KODIERBAR,
# kostet beim Versand aber ZWEI Septets je Zeichen (ESC-Fluchtsequenz) -- die
# Budget-Herleitung (channel_layout.py) geht von GENAU EINEM Septet je Zeichen
# aus. Ein einziges Extension-Zeichen verletzt die Budget-Zusage also STILL,
# ohne dass eine reine "ist GSM-7-kodierbar?"-Pruefung das saehe. Deshalb ist
# die Tabelle bewusst NICHT Teil von `_GSM7_CHARSET`.
GSM7_EXTENDED_TWO_SEPTET_CHARS = "\x0c^{}\\[~]|€"

_GSM7_CHARSET = frozenset(_GSM7_BASIC)  # OHNE Extension-Tabelle, s.o.


def _first_non_gsm7_char(text: str) -> str | None:
    """Erstes Zeichen in `text`, das NICHT im GSM-7-Zeichensatz steht, oder
    `None`, wenn der gesamte Text GSM-7-kodierbar ist."""
    for ch in text:
        if ch not in _GSM7_CHARSET:
            return ch
    return None


def assert_gsm7_clean(text: str, context: str) -> None:
    bad = _first_non_gsm7_char(text)
    assert bad is None, (
        f"GSM-7-Verstoss in {context}: Zeichen {bad!r} (U+{ord(bad):04X}) ist "
        f"nicht im GSM-7-Zeichensatz (GSM 03.38) -- die SMS wechselt dadurch "
        f"in UCS-2 (67 statt 153 Zeichen je Teil bei Verkettung, 3GPP TS "
        f"23.040) -- STILLE Kostenverdopplung. Text: {text!r}"
    )
