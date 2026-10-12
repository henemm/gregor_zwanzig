"""TDD RED/GREEN — Issue #1427 S1: neue Gefahrenart "flood" (Hochwasser/
Erdrutsch) braucht ein eigenes SMS-Kuerzel im SSOT-Katalog.

SPEC: docs/specs/modules/feat_1427_dpc_warn_fallback.md, Abschnitt "Scheiben"
S1-Zeile, Test Plan.

Kein Mock: `HAZARD_SMS_SYMBOLS`/`sms_symbol_for()` sind der echte SSOT-Katalog
aus `src/output/tokens/hazard_symbols.py` (Issue #1318), unveraendert
importiert.
"""
from __future__ import annotations


def test_flood_hat_eigenes_katalog_kuerzel_kein_fallback():
    """S1: GIVEN der SSOT-Katalog HAZARD_SMS_SYMBOLS, WHEN nach dem
    SMS-Kuerzel fuer 'flood' gefragt wird, THEN liefert sms_symbol_for('flood')
    ein Kuerzel AUS DEM KATALOG -- nicht den abgeleiteten 2-Buchstaben-Notbehelf.
    RED heute: 'flood' fehlt im Katalog, sms_symbol_for() faellt auf den
    Notbehelf ('FL') zurueck."""
    from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS, sms_symbol_for

    assert "flood" in HAZARD_SMS_SYMBOLS, (
        "Katalog muss einen eigenen Eintrag fuer 'flood' tragen (Issue #1427 S1), "
        f"vorhandene Eintraege: {sorted(HAZARD_SMS_SYMBOLS)}"
    )

    symbol = sms_symbol_for("flood")
    assert symbol == HAZARD_SMS_SYMBOLS["flood"], (
        f"sms_symbol_for('flood') muss das Katalog-Kuerzel liefern, nicht den "
        f"abgeleiteten Notbehelf, erhalten {symbol!r}"
    )


def test_flood_kuerzel_kollidiert_mit_keinem_anderen_katalog_kuerzel():
    """S1: GIVEN das neue Katalog-Kuerzel fuer 'flood', WHEN es mit allen
    anderen Kuerzeln des Katalogs verglichen wird, THEN ist es eindeutig --
    kein anderer hazard traegt dasselbe Kuerzel (Praezedenz #1239: eine
    Warnung, die wie eine andere Gefahr aussieht, ist eine Fehlinformation
    in einer Sicherheitsmeldung). RED heute: der Eintrag fehlt noch, die
    Kollisionspruefung kann also gar nicht positiv ausfallen."""
    from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS

    assert "flood" in HAZARD_SMS_SYMBOLS, (
        "Katalog muss 'flood' enthalten, bevor eine Kollisionspruefung "
        "sinnvoll ist (RED heute: Eintrag fehlt)"
    )
    flood_symbol = HAZARD_SMS_SYMBOLS["flood"]
    others = {h: s for h, s in HAZARD_SMS_SYMBOLS.items() if h != "flood"}
    colliding = [h for h, s in others.items() if s == flood_symbol]
    assert colliding == [], (
        f"Kuerzel {flood_symbol!r} fuer 'flood' kollidiert mit {colliding} -- "
        f"jede Gefahr muss ein eindeutiges Kuerzel tragen"
    )


# ---------------------------------------------------------------------------
# #1430 -- Gefahrenart "avalanche" (MeteoAlarm Typ 9), Kuerzel AW
# ---------------------------------------------------------------------------
def test_1430_lawine_hat_kuerzel_aw_und_nie_av():
    from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS, sms_symbol_for

    assert HAZARD_SMS_SYMBOLS.get("avalanche") == "AW"
    # AV ist die Lawinen-STUFE (Wintersport-Token) -- Fallback darf nie dorthin fuehren.
    assert sms_symbol_for("avalanche") == "AW"
    assert sms_symbol_for("avalanche") != "AV"


def test_1430_aw_kollidiert_mit_keinem_wetter_oder_warn_kuerzel():
    from app.metric_catalog import _METRICS
    from output.tokens.builder import STD_SYMBOLS
    from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS

    assert HAZARD_SMS_SYMBOLS.get("avalanche") == "AW", "Katalogeintrag fehlt"
    wetter = {s.rstrip(":") for s in STD_SYMBOLS}
    wetter |= {m.sms_symbol.rstrip(":") for m in _METRICS if getattr(m, "sms_symbol", None)}
    assert "AW" not in wetter
    assert list(HAZARD_SMS_SYMBOLS.values()).count("AW") == 1


def test_1430_lawine_sortiert_unmittelbar_nach_schnee():
    from output.tokens.hazard_symbols import HAZARD_ORDER

    assert HAZARD_ORDER["avalanche"] == HAZARD_ORDER["snow"] + 1


def test_1430_codes_und_kuerzel_nennen_aw_getrennt_von_av():
    from output.tokens.hazard_symbols import HAZARD_BEDEUTUNG_DE, HAZARD_BEDEUTUNG_EN
    from services.trip_command_processor import codes_text

    assert HAZARD_BEDEUTUNG_DE.get("avalanche") == "Lawine"
    assert HAZARD_BEDEUTUNG_EN.get("avalanche") == "avalanche"
    de = codes_text(False)
    en = codes_text(True)
    assert "AW Lawine" in de, f"KUERZEL muss 'AW Lawine' nennen: {de!r}"
    assert "AW avalanche" in en, f"CODES muss 'AW avalanche' nennen: {en!r}"
    assert "AV" in de, "Lawinenstufe AV muss weiter getrennt stehen"
