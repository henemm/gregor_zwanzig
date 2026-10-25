"""TDD RED — Bug #2615: Wetterbefehle bei pausierten Ortsvergleichen.

SPEC: docs/specs/modules/fix_2615_befehle_pausierte_vergleiche.md
AC-1 .. AC-9 (Pausierte bei heute/morgen/report ausblenden, Rückfrage-Namen
paarweise eindeutig, gekürzter Name im Antwort-Parser auflösbar).

Kern-Schicht: echte Dateien unter der per conftest umgeleiteten Datenwurzel,
echte Reader (`InboundTelegramReader`, `InboundSmsReader`), echter
`TripCommandProcessor`. Gepatcht wird nur der Transport. Die Helfer stammen
aus dem Bestand (`test_eingangsauswahl_trip_und_vergleich.py`).
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.loader import get_briefings_dir  # noqa: E402
from tests.tdd.test_eingangsauswahl_trip_und_vergleich import (  # noqa: E402
    _nutzer_mit_tier,
    _preset,
    _preset_dict,
    _read,
    _trip,
    _trip_obj,
    _via_premium_sms,
    _via_telegram,
)

_ZIELLOSE_KANAELE = {"telegram": _via_telegram, "premium_sms": _via_premium_sms}


@pytest.fixture
def user_ids():
    import shutil

    created: list[str] = []

    def _new() -> str:
        uid = f"tdd-2615-{uuid.uuid4().hex[:8]}"
        created.append(uid)
        return uid

    yield _new
    for uid in created:
        shutil.rmtree(get_briefings_dir(uid).parent, ignore_errors=True)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _eins_aktiv_fuenf_pausiert() -> list[dict]:
    aktiv = _preset_dict("Aktiv-Runde")
    pausiert = [
        _preset_dict(f"Pausiert-{i}", paused_at="2026-10-01T08:00:00Z") for i in range(5)
    ]
    return [aktiv, *pausiert]


# ---------------------------------------------------------------------------
# AC-1: Ein aktiver + fünf pausierte, kein Trip -> heute/morgen/report eindeutig
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("schluessel", ["heute", "morgen", "report"])
@pytest.mark.parametrize("kanal", ["telegram", "premium_sms"])
def test_ac1_aktiver_vergleich_wird_trotz_pausierter_eindeutig(schluessel, kanal):
    from services.trip_selection import resolve_command_target

    presets = _eins_aktiv_fuenf_pausiert()
    erg = resolve_command_target(schluessel, [], presets, _now(), channel=kanal)
    assert erg.kind == "vergleich", f"Rückfrage statt Ziel: {erg.text!r}"
    assert erg.target["name"] == "Aktiv-Runde"
    assert erg.text is None


@pytest.mark.parametrize("befehl", ["heute", "morgen", "report"])
@pytest.mark.parametrize("kanal", ["telegram", "premium_sms"])
def test_ac1_befehl_ueber_echten_eingang_fragt_nicht_nach(monkeypatch, user_ids, befehl, kanal):
    uid = user_ids()
    _nutzer_mit_tier(uid)
    _preset(uid, "Aktiv-Runde")
    for i in range(5):
        _preset(uid, f"Pausiert-{i}", paused_at="2026-10-01T08:00:00Z", schedule="manual")

    sent, calls = _ZIELLOSE_KANAELE[kanal](monkeypatch, uid, befehl)

    assert len(calls) == 1, f"process() muss laufen, Antworten: {sent!r}"
    assert not any("Mehrdeutig" in s or "Ambiguous" in s for s in sent), sent


# ---------------------------------------------------------------------------
# AC-2: pause/weiter bleiben mehrdeutig, Rückfrage nennt alle sechs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("schluessel", ["pause", "weiter"])
def test_ac2_pause_weiter_nennen_alle_sechs_vergleiche(schluessel):
    from services.trip_selection import resolve_command_target

    presets = _eins_aktiv_fuenf_pausiert()
    erg = resolve_command_target(schluessel, [], presets, _now(), channel="telegram")
    assert erg.kind is None and erg.text
    for p in presets:
        assert p["name"] in erg.text, (p["name"], erg.text)


# ---------------------------------------------------------------------------
# AC-3: Trip + nur pausierte -> Trip; Trip + aktiv -> Rückfrage
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("schluessel", ["heute", "morgen", "report"])
def test_ac3_trip_plus_nur_pausierte_ist_eindeutig_trip(schluessel):
    from services.trip_selection import resolve_command_target

    trip = _trip_obj("Korsika", 0)
    presets = [_preset_dict(f"P{i}", paused_at="2026-10-01T08:00:00Z") for i in range(3)]
    erg = resolve_command_target(schluessel, [trip], presets, _now(), channel="telegram")
    assert erg.kind == "route" and erg.target is trip, erg.text


@pytest.mark.parametrize("schluessel", ["heute", "morgen", "report"])
def test_ac3_trip_plus_aktiver_vergleich_fragt_weiter_nach(schluessel):
    from services.trip_selection import resolve_command_target

    trip = _trip_obj("Korsika", 0)
    presets = [_preset_dict("Aktiv"), _preset_dict("P1", paused_at="2026-10-01T08:00:00Z")]
    erg = resolve_command_target(schluessel, [trip], presets, _now(), channel="telegram")
    assert erg.kind is None and erg.text
    assert "Korsika" in erg.text and "Aktiv" in erg.text
    assert "P1" not in erg.text, "Pausierte erscheinen nicht in der Liste"


# ---------------------------------------------------------------------------
# AC-4: Nur pausierte -> bisheriges Verhalten
# ---------------------------------------------------------------------------

def test_ac4_ein_pausierter_vergleich_bleibt_eindeutig():
    from services.trip_selection import resolve_command_target

    p = _preset_dict("Nur-Pause", paused_at="2026-10-01T08:00:00Z")
    erg = resolve_command_target("heute", [], [p], _now(), channel="telegram")
    assert erg.kind == "vergleich" and erg.target is p


def test_ac4_mehrere_pausierte_fragen_mit_allen_namen_nach():
    from services.trip_selection import resolve_command_target

    presets = [_preset_dict(f"Pause-{i}", schedule="manual") for i in range(3)]
    erg = resolve_command_target("heute", [], presets, _now(), channel="telegram")
    assert erg.kind is None and erg.text
    for p in presets:
        assert p["name"] in erg.text


# ---------------------------------------------------------------------------
# AC-5: Pausen-Definition = is_silenced; archiviert bleibt unsichtbar
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pausiert", [
    {"paused_at": "2026-10-01T08:00:00Z"},
    {"schedule": "manual"},
])
def test_ac5_beide_pausen_varianten_werden_bei_heute_ausgeblendet(pausiert):
    from services.trip_selection import resolve_command_target

    presets = [
        _preset_dict("Aktiv"),
        _preset_dict("Pause", **pausiert),
        _preset_dict("Archiv", archived_at="2026-09-01T08:00:00Z"),
    ]
    erg = resolve_command_target("heute", [], presets, _now(), channel="telegram")
    assert erg.kind == "vergleich" and erg.target["name"] == "Aktiv", erg.text


def test_ac5_archivierter_ist_nie_adressierbar():
    from services.trip_selection import resolve_command_target

    presets = [_preset_dict("Archiv", archived_at="2026-09-01T08:00:00Z")]
    erg = resolve_command_target("heute", [], presets, _now(), channel="telegram")
    assert erg.kind is None and "Archiv" not in (erg.text or "")


# ---------------------------------------------------------------------------
# AC-6: Direktaufruf ohne neuen Parameter bleibt unverändert
# ---------------------------------------------------------------------------

def test_ac6_resolve_active_target_ohne_parameter_zaehlt_pausierte_mit():
    from services.trip_selection import resolve_active_target

    presets = _eins_aktiv_fuenf_pausiert()
    erg = resolve_active_target([], presets, _now(), channel="telegram")
    assert erg.kind is None and erg.text
    for p in presets:
        assert p["name"] in erg.text


# ---------------------------------------------------------------------------
# AC-7: Premium-SMS-Rückfrage mit paarweise eindeutigen, gekürzten Namen
# ---------------------------------------------------------------------------

def _angezeigte_namen(text: str) -> list[str]:
    import re

    rumpf = text.split(": ", 1)[1].rsplit(". ", 1)[0]
    return [m.group(1).strip() for m in re.finditer(r"(?:^|, )(.+?) \((?:comparison|route)\)", rumpf)]


def test_ac7_gekuerzte_namen_sind_paarweise_verschieden_und_passen_in_160():
    from services.trip_selection import _rueckfrage_text

    kandidaten = [
        ("vergleich", "Alpenrunde Nord"),
        ("vergleich", "Alpenrunde Süd"),
        ("vergleich", "Brenner"),
        ("vergleich", "Chiemsee"),
    ]
    text = _rueckfrage_text(kandidaten, "premium_sms")
    namen = _angezeigte_namen(text)
    assert len(namen) == 4, text
    assert len({n.lower() for n in namen}) == 4, f"nicht unterscheidbar: {text!r}"
    assert all(len(n) >= 4 for n in namen), text
    assert len(text) <= 160, (len(text), text)


def test_ac7_gleiche_vier_zeichen_anfaenge_mit_umlauten():
    from services.trip_selection import _rueckfrage_text

    kandidaten = [
        ("vergleich", "Zillertal Nord"),
        ("vergleich", "Zillertal Süd"),
        ("vergleich", "Zillergrund"),
    ]
    text = _rueckfrage_text(kandidaten, "premium_sms")
    namen = _angezeigte_namen(text)
    assert len(namen) == 3, text
    assert len({n.lower() for n in namen}) == 3, f"nicht unterscheidbar: {text!r}"
    assert len(text) <= 160, text


def test_ac7_telegram_bleibt_bei_vollen_namen():
    from services.trip_selection import _rueckfrage_text

    text = _rueckfrage_text(
        [("vergleich", "Zillertal Nord"), ("vergleich", "Zillertal Süd")], "telegram",
    )
    assert "Zillertal Nord" in text and "Zillertal Süd" in text


# ---------------------------------------------------------------------------
# AC-8: Antwort-Parser löst eindeutiges Präfix (>= 4 Zeichen) auf
# ---------------------------------------------------------------------------

def test_ac8_match_leading_name_eindeutiges_praefix_trifft():
    from services.trip_command_processor import match_leading_name

    presets = [_preset_dict("München Nord"), _preset_dict("Hamburg Hafen")]
    treffer = match_leading_name("Muen pause", [], presets)
    assert treffer is not None, "gekürzter Rückfrage-Name wird nicht gefunden"
    prefix, rest, kind, ziel = treffer
    assert (prefix, rest, kind) == ("Muen", "pause", "vergleich")
    assert ziel["name"] == "München Nord"


def test_ac8_match_leading_name_mehrdeutiges_praefix_waehlt_keinen():
    from services.trip_command_processor import match_leading_name

    presets = [_preset_dict("München Nord"), _preset_dict("München Süd")]
    treffer = match_leading_name("Muen pause", [], presets)
    assert treffer is not None
    assert treffer[2] is None and treffer[3] is None


def test_ac8_match_leading_name_praefix_unter_vier_zeichen_loest_nichts_auf():
    from services.trip_command_processor import match_leading_name

    presets = [_preset_dict("München Nord")]
    assert match_leading_name("Mue pause", [], presets) is None


def test_ac8_match_leading_name_exakt_schlaegt_praefix():
    from services.trip_command_processor import match_leading_name

    presets = [_preset_dict("Muen"), _preset_dict("München Nord")]
    treffer = match_leading_name("Muen pause", [], presets)
    assert treffer is not None and treffer[3]["name"] == "Muen"


def test_ac8_praefix_braucht_gueltigen_befehl_im_rest():
    from services.trip_command_processor import match_leading_name

    presets = [_preset_dict("München Nord")]
    assert match_leading_name("Muen blabla", [], presets) is None


def test_ac8_find_compare_preset_praefix(user_ids):
    from services.trip_command_processor import TripCommandProcessor

    uid = user_ids()
    p = _preset(uid, "München Nord")
    _preset(uid, "Hamburg Hafen")
    proc = TripCommandProcessor()
    assert (proc._find_compare_preset("Muen", uid) or {}).get("id") == p["id"]
    assert proc._find_compare_preset("Mue", uid) is None


def test_ac8_find_compare_preset_mehrdeutiges_praefix_ist_none(user_ids):
    from services.trip_command_processor import TripCommandProcessor

    uid = user_ids()
    _preset(uid, "München Nord")
    _preset(uid, "München Süd")
    assert TripCommandProcessor()._find_compare_preset("Muen", uid) is None


def test_ac8_roundtrip_rueckfrage_dann_gekuerzte_antwort_pausiert_richtigen(
    monkeypatch, user_ids,
):
    """Bug aus Nutzersicht: Premium-SMS-Rückfrage kürzt auf 4 Zeichen, die
    Antwort mit genau diesem Namen muss den richtigen Vergleich pausieren."""
    uid = user_ids()
    _nutzer_mit_tier(uid)
    _trip(uid, "Korsika", start_offset_days=-1)
    ziel = _preset(uid, "Hamburg Hafenrunde Nordseekueste")
    andere = _preset(uid, "München Nord Isarauen Wanderung")
    for i in range(3):
        _preset(uid, f"Zusatzvergleich Nummer {i} lang", paused_at="2026-10-01T08:00:00Z",
                schedule="manual")

    sent1, calls1 = _via_premium_sms(monkeypatch, uid, "pause")
    assert calls1 == [] and len(sent1) == 1
    text = sent1[0]
    namen = _angezeigte_namen(text)
    kurz = next(n for n in namen if n.lower().startswith("hamb"))
    assert len(kurz) < len("Hamburg Hafenrunde Nordseekueste"), (
        f"Testvoraussetzung: Name muss gekürzt sein: {text!r}"
    )

    _via_premium_sms(monkeypatch, uid, f"{kurz} pause")

    assert _read(uid, ziel["id"])["schedule"] == "manual", f"Antwort auf {text!r} löste nichts auf"
    assert _read(uid, andere["id"])["schedule"] != "manual"


# ---------------------------------------------------------------------------
# AC-9: Zwei Nutzer, getrennte Preset-Listen
# ---------------------------------------------------------------------------

def test_ac9_pausen_eines_nutzers_beeinflussen_den_anderen_nicht(monkeypatch, user_ids):
    ua, ub = user_ids(), user_ids()
    _nutzer_mit_tier(ua)
    _nutzer_mit_tier(ub)
    for i in range(3):
        _preset(ua, f"A-Pause-{i}", paused_at="2026-10-01T08:00:00Z", schedule="manual")
    _preset(ub, "B-Aktiv")
    for i in range(2):
        _preset(ub, f"B-Pause-{i}", paused_at="2026-10-01T08:00:00Z", schedule="manual")

    sent_a, calls_a = _via_premium_sms(monkeypatch, ua, "heute")
    sent_b, calls_b = _via_premium_sms(monkeypatch, ub, "heute")

    assert calls_a == [] and sent_a and "Ambiguous" in sent_a[0], sent_a
    assert all("B-" not in s for s in sent_a)
    assert len(calls_b) == 1, f"B muss eindeutig auf B-Aktiv zeigen: {sent_b!r}"
    assert not any("Ambiguous" in s for s in sent_b)
