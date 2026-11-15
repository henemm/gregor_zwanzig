"""Ortsvergleich: Aus und Roh/Einfach je Kanal ueber ``display_config.channel_layouts``
(Issue #3039, Vorlauf zu #3031, Teil von #2795 / Epic #2791).

SPEC: docs/specs/modules/feat_3039_vergleich_kanal_layouts.md (AC-1..AC-14).

Einstieg wie im Betrieb (Muster ``test_compare_einstellung_auslieferung_kette.py``):
das Preset liegt als rohes JSON im Nutzerverzeichnis, wird vom ECHTEN Loader
gelesen und ueber ``send_one_compare_preset`` versendet. Messpunkt sind die
Kanal-Ausgaenge (geteilter Aufzeichner ``tests/helpers/transport_mitschrift.py``),
die Vorschau laeuft ueber ``ComparePreviewService.render_all_channels``. Einzige
Naehte: Wetter (``ComparisonEngine.run``, echte Subklasse) und Transport. Kein
``Mock()``/``patch()``.

Erwartungen kommen aus dem rohen Preset (Reihenfolge = Listenindex der
Kanal-Liste) und dem statischen Label-Register des Orakels, NIE aus dem
Resolver selbst. Jeder Versand-Test laeuft mit ZWEI Nutzern.

Tageswerte der Wetter-Naht (``_compare_kette_fixtures._WERTE``):
Innsbruck Boeen 19 km/h, Wolken 35 %; Bozen Boeen 23 km/h, Wolken 48 %.

RED heute: ``channel_layouts`` wird vom Vergleich ignoriert (Resolver liest nur
``channel_active_metrics``), die Vergleichs-Renderer formatieren fest (Roh).
Bestands-Waechter (AC-2/AC-3/AC-7/AC-8 sowie Teile von AC-6) sichern den Ist-
Stand und duerfen gruen sein.
"""
from __future__ import annotations

import copy
import re

import pytest

from tests.helpers.einstellung_auslieferung_orakel import (
    compare_parse_email_plain,
    compare_parse_sms,
    compare_parse_telegram,
    compare_vorbedingung_pruefen,
)
from tests.tdd._compare_kette_fixtures import (
    ORTSNAMEN,
    TARGET_DATE,
    fixture_dict,
    nutzer_anlegen,
    orte_anlegen,
    preset_ablegen,
)
from tests.tdd.test_compare_einstellung_auslieferung_kette import (  # noqa: F401 (Fixture)
    ALLE_MIT_TEXT,
    Lauf,
    _lauf,
    _text,
    mit,
)
from tests.tdd.test_compare_sms_gsm7_charset import assert_gsm7_clean

#: Grundauswahl der Vorlage ``kanal_reihenfolge`` (Katalog-Kennungen, Reihenfolge).
GRUNDAUSWAHL = ["temperature", "wind", "gust", "cloud_total", "sunshine"]

#: Katalog-Kennung -> Vergleichs-Schluessel des Orakels (Grundauswahl hat temperature=max).
KENNUNG_ZU_KEY = {
    "temperature": "temp_max_c",
    "wind": "wind_max_kmh",
    "gust": "gust_max_kmh",
    "cloud_total": "cloud_avg_pct",
    "sunshine": "sunny_hours_h",
    "snow_depth": "snow_depth_cm",
}

_AMPEL_PUNKT = "border-radius:50%"
_WOLKEN_STUFE = r"(?:CLR|FEW|SCT|BKN|OVC)"


# ---------------------------------------------------------------------------
# Aufbau
# ---------------------------------------------------------------------------


def _eintrag(kennung: str, *, an: bool = True, einfach=None) -> dict:
    """Ein Kanal-Eintrag wie die Karte #3031 ihn schreibt; ``einfach=None`` =
    Feld ``use_friendly_format`` fehlt ganz (AC-7)."""
    e = {"metric_id": kennung, "enabled": an}
    if einfach is not None:
        e["use_friendly_format"] = einfach
    return e


def _vorlage(layouts: dict | None, *, ohne_kanal_auswahl: bool = True) -> dict:
    """Vorlage ``kanal_reihenfolge`` (Grundauswahl = GRUNDAUSWAHL). Mit
    ``channel_layouts`` wird ``channel_active_metrics`` entfernt, damit allein
    die neue Stufe die Ausgabe bestimmt."""
    p = fixture_dict("kanal_reihenfolge")
    dc = p["display_config"]
    if ohne_kanal_auswahl:
        dc.pop("channel_active_metrics", None)
    if layouts is not None:
        dc["channel_layouts"] = copy.deepcopy(layouts)
    return p


def _voll(kennungen: list[str], **je_kennung) -> list[dict]:
    """Volle Kanal-Liste (jede Kennung ein Eintrag, Standard an + Roh);
    ``je_kennung`` ueberschreibt einzelne Eintraege (dict mit an/einfach)."""
    return [_eintrag(k, **je_kennung.get(k, {"einfach": False})) for k in kennungen]


def _zwei(mit, vorlage: dict) -> tuple[Lauf, Lauf]:
    a = _lauf(mit, vorlage, "premium")
    b = _lauf(mit, vorlage, "premium")
    assert a.uid != b.uid
    for lauf in (a, b):
        compare_vorbedingung_pruefen(lauf.snap, ALLE_MIT_TEXT)
        assert lauf.snap.empfaenger("email") == [f"{lauf.uid}@example.invalid"]
    return a, b


def _keys(lauf: Lauf, kanal: str) -> dict[str, list[str]]:
    if kanal == "email":
        return compare_parse_email_plain(_text(lauf.snap, "email"), ORTSNAMEN)
    if kanal == "telegram":
        return compare_parse_telegram(_text(lauf.snap, "telegram"), ORTSNAMEN)[0]
    return compare_parse_sms(_text(lauf.snap, kanal), ORTSNAMEN)


def _plain_wert(text: str, ort: str, label: str) -> str | None:
    """Wert der Zeile ``   <label>: <wert>`` im Ortsblock ``ort`` des Klartexts."""
    aktuell = None
    for zeile in text.splitlines():
        if zeile.startswith(("STUNDENVERLAUF", "AUSBLICK")):
            break
        if zeile in ORTSNAMEN:
            aktuell = zeile
            continue
        m = re.match(rf"^   {re.escape(label)}: (.*)$", zeile)
        if aktuell == ort and m:
            return m.group(1)
    return None


def _html_zeile(html: str, label: str) -> str:
    """Die Uebersichtszeile ``<tr>…<td>label</td>…</tr>`` der Mail (erste Fundstelle)."""
    m = re.search(rf"<tr[^>]*>(?:(?!</tr>).)*?>{re.escape(label)}</td>(?:(?!</tr>).)*</tr>", html, re.DOTALL)
    assert m, f"Zeile {label!r} fehlt in der HTML-Mail"
    return m.group(0)


def _telegram_zelle(text: str, ort: str, label: str) -> str | None:
    aktuell = None
    for zeile in text.splitlines():
        if zeile in ORTSNAMEN:
            aktuell = zeile
            continue
        if aktuell == ort and zeile.startswith("   "):
            for zelle in zeile.strip().split(" · "):
                if zelle.startswith(label + " "):
                    return zelle[len(label) + 1:]
    return None


# ---------------------------------------------------------------------------
# AC-1 -- Boeen: Telegram Roh, E-Mail Einfach, im selben Bericht
# ---------------------------------------------------------------------------


def test_ac1_boeen_telegram_roh_und_mail_einfach_im_selben_bericht(mit):
    layouts = {
        "email": _voll(GRUNDAUSWAHL, gust={"einfach": True}),
        "telegram": _voll(GRUNDAUSWAHL, gust={"einfach": False}),
        "sms": _voll(GRUNDAUSWAHL),
    }
    for lauf in _zwei(mit, _vorlage(layouts)):
        tg = _text(lauf.snap, "telegram")
        assert _telegram_zelle(tg, "Innsbruck", "Böen") == "19 km/h", tg
        assert _telegram_zelle(tg, "Bozen", "Böen") == "23 km/h", tg

        html = lauf.snap.sendungen("email")[-1]["body"]
        zeile = _html_zeile(html, "Böen")
        assert _AMPEL_PUNKT in zeile, f"Mail-HTML Böen muss bei Einfach den Ampelpunkt zeigen:\n{zeile}"
        assert "19 km/h" not in zeile and "23 km/h" not in zeile, (
            f"Mail-HTML Böen darf bei Einfach keine Zahl zeigen:\n{zeile}")

        plain = _text(lauf.snap, "email")
        wert = _plain_wert(plain, "Innsbruck", "Böen")
        assert wert and not re.search(r"\d", wert), (
            f"Mail-Klartext Böen muss bei Einfach ein Wort zeigen, war {wert!r}\n{plain}")


# ---------------------------------------------------------------------------
# AC-2 / AC-3 -- Bestand (Waechter, duerfen heute gruen sein)
# ---------------------------------------------------------------------------


def test_ac2_bestand_nur_channel_active_metrics_bleibt_zeichengleich(mit):
    """Bestandsvergleich ohne ``channel_layouts``: Telegram/SMS/Premium-SMS
    zeichengleich zu einem Lauf derselben Vorlage, die Kanal-Auswahl greift wie
    bisher (Reihenfolge der Kanal-Liste), die Mail zeigt Zahlen (Festzustand)."""
    bestand = fixture_dict("kanal_reihenfolge")
    assert "channel_layouts" not in bestand["display_config"]
    a, b = _zwei(mit, bestand)
    for kanal in ("telegram", "sms", "premium_sms"):
        assert _text(a.snap, kanal) == _text(b.snap, kanal)
    assert _keys(a, "telegram")["Innsbruck"] == [
        "sunny_hours_h", "cloud_avg_pct", "gust_max_kmh", "wind_max_kmh", "temp_max_c"]
    assert _keys(a, "sms")["Innsbruck"] == ["gust_max_kmh", "temp_max_c", "sunny_hours_h"]
    assert _plain_wert(_text(a.snap, "email"), "Innsbruck", "Böen") == "19 km/h"
    assert _AMPEL_PUNKT not in _html_zeile(a.snap.sendungen("email")[-1]["body"], "Böen")


def test_ac3_ohne_beide_schluessel_gilt_die_grundauswahl(mit):
    for lauf in _zwei(mit, _vorlage(None)):
        soll = [KENNUNG_ZU_KEY[k] for k in GRUNDAUSWAHL]
        assert _keys(lauf, "telegram")["Innsbruck"] == soll
        assert _keys(lauf, "sms")["Innsbruck"] == soll
        assert sorted(_keys(lauf, "email")["Innsbruck"]) == sorted(soll)


# ---------------------------------------------------------------------------
# AC-4 -- Aus nur in einem Kanal
# ---------------------------------------------------------------------------


def test_ac4_aus_nur_in_telegram_blendet_nur_dort_aus(mit):
    layouts = {
        "email": _voll(GRUNDAUSWAHL),
        "telegram": _voll(GRUNDAUSWAHL, gust={"an": False, "einfach": False}),
        "sms": _voll(GRUNDAUSWAHL),
    }
    for lauf in _zwei(mit, _vorlage(layouts)):
        for ort in ORTSNAMEN:
            assert "gust_max_kmh" not in _keys(lauf, "telegram")[ort], _text(lauf.snap, "telegram")
            assert "gust_max_kmh" in _keys(lauf, "email")[ort]
            assert "gust_max_kmh" in _keys(lauf, "sms")[ort]
            assert "gust_max_kmh" in _keys(lauf, "premium_sms")[ort]


# ---------------------------------------------------------------------------
# AC-5 -- eigene Reihenfolge je Kanal
# ---------------------------------------------------------------------------


def test_ac5_jeder_kanal_folgt_seiner_eigenen_reihenfolge(mit):
    reihen = {
        "email": ["sunshine", "gust", "temperature", "cloud_total", "wind"],
        "telegram": ["cloud_total", "wind", "sunshine", "temperature", "gust"],
        "sms": ["gust", "sunshine", "temperature", "wind", "cloud_total"],
    }
    layouts = {k: _voll(v) for k, v in reihen.items()}
    for lauf in _zwei(mit, _vorlage(layouts)):
        for kanal, reihe in reihen.items():
            soll = [KENNUNG_ZU_KEY[k] for k in reihe]
            for ort in ORTSNAMEN:
                assert _keys(lauf, kanal)[ort] == soll, (
                    f"{kanal}/{ort}: erwartet {soll}, gesendet {_keys(lauf, kanal)[ort]}\n"
                    f"{_text(lauf.snap, kanal)}")
        assert _keys(lauf, "premium_sms") == _keys(lauf, "sms")


# ---------------------------------------------------------------------------
# AC-6 -- Teilmengen-Regel (ADR-0050), leer bleibt leer
# ---------------------------------------------------------------------------


def test_ac6_eintrag_ausserhalb_der_grundauswahl_erscheint_nicht(mit):
    """Schneehoehe steht nur in der Telegram-Liste, nicht in der Grundauswahl:
    sie erscheint nicht; die Liste bestimmt dennoch die Reihenfolge (Boeen vor
    Temperatur), fehlende Grundauswahl-Groessen folgen am Ende (AC-14)."""
    layouts = {"telegram": [
        _eintrag("snow_depth", einfach=False),
        _eintrag("gust", einfach=False),
        _eintrag("temperature", einfach=False),
    ]}
    for lauf in _zwei(mit, _vorlage(layouts)):
        for ort in ORTSNAMEN:
            ist = _keys(lauf, "telegram")[ort]
            assert "snow_depth_cm" not in ist, _text(lauf.snap, "telegram")
            assert ist == ["gust_max_kmh", "temp_max_c", "wind_max_kmh", "cloud_avg_pct",
                           "sunny_hours_h"], _text(lauf.snap, "telegram")


def test_ac6_leere_grundauswahl_laesst_jeden_kanal_leer(mit):
    vorlage = _vorlage({k: _voll(GRUNDAUSWAHL) for k in ("email", "telegram", "sms")})
    vorlage["display_config"]["active_metrics"] = []
    for lauf in _zwei(mit, vorlage):
        for kanal in ("email", "telegram", "sms"):
            assert not any(_keys(lauf, kanal).values()), (
                f"{kanal}: leere Grundauswahl darf keine Zelle zeigen\n{_text(lauf.snap, kanal)}")


def test_ac6_alle_eintraege_aus_laesst_den_kanal_leer_ohne_rueckfall(mit):
    layouts = {
        "email": _voll(GRUNDAUSWAHL),
        "telegram": _voll(GRUNDAUSWAHL),
        "sms": [_eintrag(k, an=False, einfach=False) for k in GRUNDAUSWAHL],
    }
    for lauf in _zwei(mit, _vorlage(layouts)):
        for ort in ORTSNAMEN:
            assert _keys(lauf, "sms").get(ort) == [], _text(lauf.snap, "sms")
            assert _keys(lauf, "premium_sms").get(ort) == [], _text(lauf.snap, "premium_sms")
            assert _keys(lauf, "telegram")[ort], "Telegram muss seine Liste zeigen"
            assert _keys(lauf, "email")[ort], "E-Mail muss ihre Liste zeigen"


# ---------------------------------------------------------------------------
# AC-7 / AC-8 -- Standard Roh, Einfach ohne zweite Darstellung = Roh
# ---------------------------------------------------------------------------


def test_ac7_eintrag_ohne_einfach_angabe_zeigt_die_zahl(mit):
    layouts = {k: [_eintrag(m) for m in GRUNDAUSWAHL] for k in ("email", "telegram", "sms")}
    assert all("use_friendly_format" not in e for e in layouts["email"])
    for lauf in _zwei(mit, _vorlage(layouts)):
        assert _plain_wert(_text(lauf.snap, "email"), "Innsbruck", "Böen") == "19 km/h"
        assert _plain_wert(_text(lauf.snap, "email"), "Innsbruck", "Bewölkung") == "35%"
        html_zeile = _html_zeile(lauf.snap.sendungen("email")[-1]["body"], "Böen")
        assert "19 km/h" in html_zeile and _AMPEL_PUNKT not in html_zeile
        assert _telegram_zelle(_text(lauf.snap, "telegram"), "Innsbruck", "Böen") == "19 km/h"
        assert re.search(r"\bCT 35\b", _text(lauf.snap, "sms")), _text(lauf.snap, "sms")


def test_ac8_einfach_bei_metrik_ohne_zweite_darstellung_wie_roh(mit):
    """Temperatur kennt nur ``raw``: ``use_friendly_format=true`` wird ignoriert,
    die Ausgabe gleicht dem Roh-Lauf in jedem Kanal."""
    roh = {k: _voll(GRUNDAUSWAHL) for k in ("email", "telegram", "sms")}
    einfach = {k: _voll(GRUNDAUSWAHL, temperature={"einfach": True}) for k in ("email", "telegram", "sms")}
    a_roh, _ = _zwei(mit, _vorlage(roh))
    a_einf, _ = _zwei(mit, _vorlage(einfach))
    for kanal in ("telegram", "sms", "premium_sms"):
        assert _text(a_roh.snap, kanal) == _text(a_einf.snap, kanal), kanal
    for ort in ORTSNAMEN:
        assert _plain_wert(_text(a_einf.snap, "email"), ort, "Temperatur") == _plain_wert(
            _text(a_roh.snap, "email"), ort, "Temperatur")


# ---------------------------------------------------------------------------
# AC-9 / AC-10 -- SMS: Einfach nur fuer Wolken, GSM-7, <=160; Premium-SMS = SMS
# ---------------------------------------------------------------------------


def test_ac9_sms_einfach_nur_fuer_wolken_gsm7_und_hoechstens_160(mit):
    layouts = {"sms": _voll(
        ["cloud_total", "gust", "temperature"],
        cloud_total={"einfach": True}, gust={"einfach": True},
    )}
    for lauf in _zwei(mit, _vorlage(layouts)):
        sms = _text(lauf.snap, "sms")
        assert re.search(rf"Innsbruck CT {_WOLKEN_STUFE}\b", sms), (
            f"SMS: Wolken muessen bei Einfach als Stufe erscheinen\n{sms}")
        assert re.search(r"\bG 19\b", sms) and re.search(r"\bG 23\b", sms), (
            f"SMS: Boeen bleiben trotz Einfach eine Zahl\n{sms}")
        assert len(sms) <= 160, f"SMS zu lang ({len(sms)}): {sms}"
        assert_gsm7_clean(sms, "Vergleichs-SMS mit channel_layouts")


def test_ac10_premium_sms_text_gleich_sms_text_mit_kanal_einstellungen(mit):
    layouts = {"sms": _voll(
        ["sunshine", "cloud_total", "gust"], cloud_total={"einfach": True},
    )}
    for lauf in _zwei(mit, _vorlage(layouts)):
        sms = _text(lauf.snap, "sms")
        assert _text(lauf.snap, "premium_sms") == sms
        assert re.search(rf"CT {_WOLKEN_STUFE}\b", sms), (
            f"Vorbedingung: SMS muss die Kanal-Einstellung tragen\n{sms}")
        assert sms.index("SU ") < sms.index("CT ") < sms.index("G "), sms


# ---------------------------------------------------------------------------
# AC-12 -- zwei Nutzer, verschiedene Einstellungen, keine Vermischung
# ---------------------------------------------------------------------------


def test_ac12_zwei_nutzer_bekommen_je_ihre_eigenen_kanal_einstellungen(mit):
    a_layouts = {"telegram": _voll(GRUNDAUSWAHL, gust={"an": False, "einfach": False})}
    b_layouts = {"telegram": _voll(GRUNDAUSWAHL, wind={"an": False, "einfach": False})}
    a = _lauf(mit, _vorlage(a_layouts), "premium")
    b = _lauf(mit, _vorlage(b_layouts), "premium")
    assert a.uid != b.uid
    for lauf in (a, b):
        compare_vorbedingung_pruefen(lauf.snap, ALLE_MIT_TEXT)
        assert lauf.snap.empfaenger("telegram") == [f"chat-{lauf.uid}"]
    for ort in ORTSNAMEN:
        assert _keys(a, "telegram")[ort] == ["temp_max_c", "wind_max_kmh", "cloud_avg_pct", "sunny_hours_h"]
        assert _keys(b, "telegram")[ort] == ["temp_max_c", "gust_max_kmh", "cloud_avg_pct", "sunny_hours_h"]


# ---------------------------------------------------------------------------
# AC-13 -- Vorschau = Versand
# ---------------------------------------------------------------------------


def test_ac13_vorschau_und_versand_zeigen_dieselben_zeilen_und_formate(mit):
    from services.compare_preview_service import ComparePreviewService

    layouts = {
        "email": _voll(["gust", "temperature", "cloud_total"], gust={"einfach": True}),
        "telegram": _voll(["cloud_total", "gust", "temperature"]),
        "sms": _voll(["cloud_total", "gust"], cloud_total={"einfach": True}),
    }
    for lauf in _zwei(mit, _vorlage(layouts)):
        vorschau = ComparePreviewService().render_all_channels(
            lauf.roh["id"], user_id=lauf.uid, target_date=TARGET_DATE,
        )
        assert vorschau["sms"] == _text(lauf.snap, "sms")
        assert vorschau["telegram"] == _text(lauf.snap, "telegram")
        versand_html = lauf.snap.sendungen("email")[-1]["body"]
        assert _html_zeile(vorschau["email_html"], "Böen") == _html_zeile(versand_html, "Böen")
        # Inhalt, nicht nur Gleichheit: die Kanal-Einstellung hat gewirkt.
        # Spec-Regel 7 (AC-14): Grundauswahl-Werte ohne Kanal-Eintrag (Wind,
        # Sonne) sind neu und folgen eingeschaltet am Ende, in der Reihenfolge
        # der Grundauswahl.
        assert _keys(lauf, "telegram")["Innsbruck"] == [
            "cloud_avg_pct", "gust_max_kmh", "temp_max_c", "wind_max_kmh", "sunny_hours_h"]
        assert _AMPEL_PUNKT in _html_zeile(versand_html, "Böen")


# ---------------------------------------------------------------------------
# AC-14 -- neue Grundauswahl-Groesse ohne Kanal-Eintrag erscheint am Ende
# ---------------------------------------------------------------------------


def test_ac14_neue_metrik_ohne_kanaleintrag_erscheint_eingeschaltet_am_ende(mit):
    """Kanal-Listen kennen nur Wind und Temperatur (gespeichert, bevor Boeen,
    Wolken, Sonne in die Grundauswahl kamen): diese folgen eingeschaltet am Ende,
    in der Reihenfolge der Grundauswahl."""
    layouts = {k: _voll(["wind", "temperature"]) for k in ("email", "telegram", "sms")}
    soll = ["wind_max_kmh", "temp_max_c", "gust_max_kmh", "cloud_avg_pct", "sunny_hours_h"]
    for lauf in _zwei(mit, _vorlage(layouts)):
        for kanal in ("telegram", "sms", "email"):
            for ort in ORTSNAMEN:
                assert _keys(lauf, kanal)[ort] == soll, (
                    f"{kanal}/{ort}: erwartet {soll}, gesendet {_keys(lauf, kanal)[ort]}\n"
                    f"{_text(lauf.snap, kanal)}")


@pytest.mark.parametrize("kanal", ["email", "telegram", "sms"])
def test_ac14_aus_ist_ein_ausdruecklicher_eintrag_und_kein_neuer_wert(mit, kanal):
    """Abgrenzung AC-6/AC-14: eine als ``aus`` gespeicherte Groesse kommt NICHT
    als „neu“ am Ende zurueck."""
    layouts = {kanal: _voll(GRUNDAUSWAHL, sunshine={"an": False, "einfach": False})}
    for lauf in _zwei(mit, _vorlage(layouts)):
        for ort in ORTSNAMEN:
            assert "sunny_hours_h" not in _keys(lauf, kanal)[ort], _text(lauf.snap, kanal)
