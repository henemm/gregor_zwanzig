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


# ---------------------------------------------------------------------------
# #1441 -- Gefahrenart "avalanche_bulletin" (amtlicher Lagebericht, EAWS 1-5), Kuerzel AV
# Ausdrueckliche Freigabe: `AV` darf NUR `avalanche_bulletin` tragen; alles andere bleibt verboten.
# ---------------------------------------------------------------------------
def test_1441_av_gehoert_ausschliesslich_dem_lagebericht():
    from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS, sms_symbol_for

    assert HAZARD_SMS_SYMBOLS.get("avalanche_bulletin") == "AV"
    assert sms_symbol_for("avalanche_bulletin") == "AV"
    assert [h for h, s in HAZARD_SMS_SYMBOLS.items() if s == "AV"] == ["avalanche_bulletin"]
    # die MeteoAlarm-Warnung bleibt AW -- zwei Aussagen, zwei Kuerzel
    assert HAZARD_SMS_SYMBOLS.get("avalanche") == "AW"


def test_1441_av_bleibt_fuer_jede_andere_gefahr_verboten_auch_im_notbehelf():
    from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS, sms_symbol_for

    fremde = [h for h in HAZARD_SMS_SYMBOLS if h != "avalanche_bulletin"] + [
        "avalanche_level", "av_unbekannt", "aval_zzz", "avalanche_zusatz",
    ]
    for hazard in fremde:
        assert sms_symbol_for(hazard) != "AV", f"{hazard!r} darf nie das Lagebericht-Kuerzel AV tragen"


def test_1441_lagebericht_sortiert_unmittelbar_hinter_der_meteoalarm_lawine():
    from output.tokens.hazard_symbols import HAZARD_ORDER

    assert HAZARD_ORDER["avalanche_bulletin"] == HAZARD_ORDER["avalanche"] + 1


def test_1441_bedeutung_de_en_und_codes_text_nennen_av_genau_einmal():
    import re

    from output.tokens.hazard_symbols import HAZARD_BEDEUTUNG_DE, HAZARD_BEDEUTUNG_EN
    from services.trip_command_processor import codes_text

    assert HAZARD_BEDEUTUNG_DE.get("avalanche_bulletin") == "Lawinenstufe"
    assert HAZARD_BEDEUTUNG_EN.get("avalanche_bulletin") == "avalanche level"
    for text, bedeutung in ((codes_text(False), "Lawinenstufe"), (codes_text(True), "avalanche level")):
        assert f"AV {bedeutung}" in text
        assert len(re.findall(r"(?<![A-Z])AV (?=[A-Za-z])", text)) == 1, \
            f"ein Kuerzel = eine Bedeutung, ueberall -- AV doppelt gelistet: {text!r}"
