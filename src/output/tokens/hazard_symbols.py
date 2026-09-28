"""Einziger SMS-Kuerzel-Katalog fuer amtliche Warnungen (Issue #1318).

SPEC: docs/specs/modules/sms_official_alert_tokens.md Abschnitt 1/1b
WIRE: docs/reference/sms_format.md §3.4c

Konsumenten: `output/renderers/sms_trip.py` (Trip-Briefing-SMS `!`-Warn-Block),
`output/renderers/alert/official_alerts.py` (`_HAZARD_DISPLAY`, Standalone-
Warn-SMS). Zwei Nachrichtentypen, EIN Kuerzel je Gefahr — derselbe Nutzer darf
fuer dieselbe Gefahr nicht zwei verschiedene Codes bekommen.
"""
from __future__ import annotations

# hazard -> internationales SMS-Kuerzel. Die Reihenfolge ist zugleich die
# Sortier-Reihenfolge bei gleicher Warnstufe (Spec Abschnitt 2).
# Issue #2417 AC-27: TS/FO/RA/WG/AB statt TH/FL/HR/W/CL -- die alten Kuerzel
# glichen Wetter-Kuerzeln bzw. dem Meteo-France-Baustein (ein Kuerzel = eine
# Bedeutung, ueberall).
HAZARD_SMS_SYMBOLS: dict[str, str] = {
    "thunderstorm": "TS",
    "flood": "FO",
    "rain": "RA",
    "wind_gust": "WG",
    "snow": "SN",
    "black_ice": "IC",
    "extreme_heat": "HT",
    "extreme_cold": "CD",
    "wildfire_risk": "FR",
    "access_ban": "AB",
}

# Issue #2417 AC-23: EINZIGE Definitionsstelle der Bedeutung je Warn-Kuerzel
# (Schluessel = hazard wie oben) -- CODES (en) und KUERZEL (de) lesen hier.
HAZARD_BEDEUTUNG_EN: dict[str, str] = {
    "thunderstorm": "storm", "flood": "flood", "rain": "heavy rain",
    "wind_gust": "wind", "snow": "snow", "black_ice": "ice",
    "extreme_heat": "heat", "extreme_cold": "cold", "wildfire_risk": "fire",
    "access_ban": "closure",
}
HAZARD_BEDEUTUNG_DE: dict[str, str] = {
    "thunderstorm": "Gewitter", "flood": "Hochwasser", "rain": "Starkregen",
    "wind_gust": "Wind", "snow": "Schnee", "black_ice": "Glätte",
    "extreme_heat": "Hitze", "extreme_cold": "Kälte", "wildfire_risk": "Waldbrand",
    "access_ban": "Sperrung",
}

# Katalog-Reihenfolge als Sortier-Index (Gleichstand bei der Warnstufe).
HAZARD_ORDER: dict[str, int] = {h: i for i, h in enumerate(HAZARD_SMS_SYMBOLS)}

# Amtliche Stufe -> L/M/H der bestehenden Skala (tokens/metrics.py LEVELS).
# `L` (gelb) bleibt strukturell erhalten, ist durch MIN_SMS_LEVEL aber nie
# sichtbar (Known Limitation der Spec).
LEVEL_LETTERS: dict[int, str] = {2: "L", 3: "M", 4: "H"}
# Issue #2417: Bedeutung der Stufen-Buchstaben (Werte, keine Kuerzel).
STUFE_BEDEUTUNG_EN: dict[str, str] = {"L": "low", "M": "mid", "H": "high"}
STUFE_BEDEUTUNG_DE: dict[str, str] = {"L": "niedrig", "M": "mittel", "H": "hoch"}

# Sicherheits-Filter: nur orange (3) und rot (4) erreichen SMS/Telegram.
MIN_SMS_LEVEL = 3


def sms_symbol_for(hazard: str) -> str:
    """hazard -> SMS-Kuerzel; unbekannt -> erste 2 ASCII-Grossbuchstaben, sonst
    ``XX``. EINZIGE Fallback-Quelle beider SMS-Pfade (Trip-Briefing-Warnblock
    und Standalone-Warn-SMS) — ein neuer amtlicher hazard-Typ darf nirgends
    still verschwinden (Praezedenz: fehlendes `wildfire_risk`-Mapping, #1239).

    Das Fallback-Kuerzel darf NIE mit einem der 9 Katalog-Kuerzel kollidieren:
    `thunder_squall` als `TH` sieht im SMS-Text aus wie eine Gewitterwarnung —
    eine Warnung, die sich als eine andere Gefahr ausgibt, ist eine
    Fehlinformation in einer Sicherheitsmeldung. Bei Kollision wird
    deterministisch auf 3 Buchstaben verlaengert (Katalog-Kuerzel sind alle
    1-2 Zeichen, koennen also strukturell nicht mehr kollidieren); reicht das
    nicht, wird `X` angehaengt.
    """
    symbol = HAZARD_SMS_SYMBOLS.get(hazard)
    if symbol:
        return symbol
    letters = "".join(ch for ch in (hazard or "").upper() if ch.isascii() and ch.isalpha())
    candidate = letters[:2] or "XX"
    # Issue #2417: auch die Kurzform-Kuerzel des Builders sind belegt (seit
    # AC-27 ist z. B. 'TH' kein Warn-, sondern nur noch ein Wetter-Kuerzel).
    from output.tokens.builder import STD_SYMBOLS

    taken = set(HAZARD_SMS_SYMBOLS.values()) | {s.rstrip(":") for s in STD_SYMBOLS}
    if candidate not in taken:
        return candidate
    candidate = letters[:3]
    while candidate in taken:
        candidate += "X"
    return candidate


# Binaere Gefahren ohne Schweregrad — erscheinen als blankes Kuerzel ohne
# Doppelpunkt/Stufe (`AB`, nicht `AB:H`) und tragen nie eine Stunde.
LEVELLESS_HAZARDS = frozenset({"access_ban"})
