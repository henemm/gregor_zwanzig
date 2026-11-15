"""TDD RED (#3031, Inhalt je Kanal A1) -- Wirkung am Renderer, Trip.

SPEC: docs/specs/modules/feat_3031_inhalt_je_kanal_listen.md
      Test Plan 2b (AC-8), 9 (AC-4), 14 (AC-3).

Die Karte „Inhalt je Kanal und Fläche" im Reiter Wetter speichert IMMER den
vollen ``display_config.channel_layouts``-Stand aller Listen-Kanaele in der
schlanken Form des Zeilenmodells:

    {"email"|"telegram"|"sms": [{"metric_id", "enabled", "use_friendly_format"}, ...]}

-- in Listenreihenfolge, OHNE ``order``/``bucket``/``format_mode`` (eine
ausgeschaltete Zeile bleibt mit ``enabled: false`` an ihrer Position; eine
im Reiter Wetter neu eingeschaltete Metrik steht eingeschaltet am Ende jeder
Liste). Premium-SMS hat bis S9 keine eigene Liste (ADR-0049) und folgt der
SMS-Liste.

Diese Datei baut ``display_config`` in GENAU dieser Form und prueft, was der
echte Loader/Kaskade/Formatter je Kanal ausliefert (Naht nur am Transport-
Aufzeichner, ``render_trip_dict``). Die Frontend-Seite derselben Form ist in
``frontend/src/lib/components/shared/wetter-tab/__tests__/
kanal_inhalt_3031_speicherung.test.ts`` festgelegt (dort zusaetzlich die
Kette Speicherer -> Go-Merge -> Python-Kaskade).

Erwartung in der RED-Phase: Der Trip-Renderer liest ``channel_layouts`` schon
heute (Issue #429/#1575/#2422) -- diese Tests sind SCHUTZTESTS und duerfen
gruen sein. Sie halten fest, dass die schlanke Form der neuen Karte (ohne
``order``) die Renderer-Wirkung traegt. Die Vergleichs-Renderer-Wirkung
gehoert zu #3039 und ist hier bewusst NICHT abgedeckt.

Kein ``Mock()``/``patch()``/``MagicMock``.

    uv run pytest tests/tdd/test_kanal_inhalt_3031_renderer_wirkung.py
"""
from __future__ import annotations

import copy

import pytest

import re

from tests.helpers.einstellung_auslieferung_orakel import (
    _TD_RE,
    _text_ohne_tags,
    parse_kanal,
    roh_wert_der_metrik,
)
from tests.tdd._einstellung_auslieferung_fixtures import golden_dict, render_trip_dict

pytestmark = pytest.mark.filterwarnings("ignore")

#: Fixture-Werte (``_voller_datenpunkt``): Boeen 45 km/h, Luftdruck 1013 hPa.
_GUST_ROH = "45"
_PRESS_ROH = "1013"


def _zeile(mid: str, enabled: bool = True, einfach: bool = False) -> dict:
    """Ein Eintrag in der Form der Karte (Zeilenmodell -> channel_layouts)."""
    return {"metric_id": mid, "enabled": enabled, "use_friendly_format": einfach}


#: Wetter-Reiter-Auswahl (globale Liste, das Maximum je Kanal, ADR-0050).
_AUSWAHL = ["wind", "gust", "precipitation", "rain_probability", "thunder", "cloud_total"]


def _trip(channel_layouts: dict, auswahl: list[str] = _AUSWAHL) -> dict:
    """golden_b (alle vier Kanaele an, Telegram rich) mit der globalen Liste
    ``auswahl`` und dem VOLLEN Kanal-Stand der Karte."""
    d = golden_dict("golden_b")
    dc = d["display_config"]
    dc["metrics"] = [
        {"metric_id": mid, "enabled": True, "bucket": "primary", "order": i}
        for i, mid in enumerate(auswahl)
    ]
    dc["channel_layouts"] = copy.deepcopy(channel_layouts)
    return d


def _volle_listen(**ueberschreiben: list[dict]) -> dict:
    """Voller Stand der drei Listen-Kanaele: jede Metrik der Auswahl
    eingeschaltet, Roh; ``ueberschreiben`` ersetzt einzelne Kanaele."""
    basis = {k: [_zeile(m) for m in _AUSWAHL] for k in ("email", "telegram", "sms")}
    basis.update(ueberschreiben)
    return basis


def _mail_html_zelle(mit, col_label: str) -> str:
    """Rohes ``<td>``-HTML der Spalte ``col_label`` in der ersten Datenzeile
    der ersten Stunden-Tabelle (Ampelpunkt = gestylter CSS-Punkt ohne Text,
    #1222 -- deshalb das HTML, nicht der Text)."""
    html = mit.sendungen("email")[0]["body"]
    tabellen = [m.start() for m in re.finditer(r"<table", html)]
    ausschnitt = html[tabellen[1]:tabellen[2] if len(tabellen) > 2 else tabellen[1] + 20000]
    kopf = re.search(r"<thead>(.*?)</thead>", ausschnitt, re.DOTALL)
    labels = [_text_ohne_tags(t) for t in re.findall(r"<th[^>]*>(.*?)</th>", kopf.group(1), re.DOTALL)]
    zeile = re.search(r"<tr[^>]*>(.*?)</tr>", ausschnitt[kopf.end():], re.DOTALL)
    zellen = _TD_RE.findall(zeile.group(1))
    assert col_label in labels, f"Spalte {col_label!r} fehlt in der Mail: {labels}"
    return zellen[labels.index(col_label)]


def _hat_ampelpunkt(zelle: str) -> bool:
    """CSS-Ampelpunkt (#1222) oder -- Regress -- ein Kreis-Emoji."""
    return "border-radius:50%" in zelle or any(e in zelle for e in ("🟢", "🟡", "🟠", "🔴"))


def _erscheint(mit, kanal: str, mid: str) -> bool:
    ids, _ = parse_kanal(mit, kanal)
    return mid in ids


# ═══════════════════════════ Test 9 (AC-4) ═══════════════════════════════════


def test_9_boeen_telegram_roh_mail_einfach(monkeypatch):
    """Test 9 / AC-4 (Trip): Given Boeen in Telegram „Roh", in E-Mail
    „Einfach" (je ``use_friendly_format`` am Kanal-Eintrag der Karte), When
    der Bericht gerendert wird, Then zeigt Telegram die Zahl und die Mail den
    Ampelpunkt -- jeder Kanal behaelt seine eigene Darstellung."""
    listen = _volle_listen(
        email=[_zeile(m, einfach=(m == "gust")) for m in _AUSWAHL],
        telegram=[_zeile(m, einfach=False) for m in _AUSWAHL],
    )
    mit, _ = render_trip_dict(monkeypatch, _trip(listen), name="3031-t9")

    tg = roh_wert_der_metrik(mit, "telegram_rich", "gust")
    assert tg == _GUST_ROH, f"Telegram Roh muss die Zahl zeigen: {tg!r}"

    zelle = _mail_html_zelle(mit, "Gust")
    assert _hat_ampelpunkt(zelle), f"Mail Einfach muss den Ampelpunkt zeigen: {zelle!r}"
    assert _GUST_ROH not in _text_ohne_tags(zelle), f"Mail Einfach zeigt die Zahl: {zelle!r}"


def test_9_gegenrichtung_telegram_einfach_mail_roh(monkeypatch):
    """Gegenrichtung zu Test 9: E-Mail Roh, Telegram Einfach -- die Mail zeigt
    die Zahl (kein Uebersprechen der Telegram-Wahl in die Mail)."""
    listen = _volle_listen(
        email=[_zeile(m, einfach=False) for m in _AUSWAHL],
        telegram=[_zeile(m, einfach=(m == "gust")) for m in _AUSWAHL],
    )
    mit, _ = render_trip_dict(monkeypatch, _trip(listen), name="3031-t9b")
    zelle = _mail_html_zelle(mit, "Gust")
    assert _GUST_ROH in _text_ohne_tags(zelle) and not _hat_ampelpunkt(zelle), f"Mail Roh muss die Zahl zeigen: {zelle!r}"


# ═══════════════════════════ Test 14 (AC-3) ══════════════════════════════════


def test_14_boeen_in_sms_aus_in_mail_und_telegram_an(monkeypatch):
    """Test 14 / AC-3 (Trip): Given Boeen in der SMS-Liste ausgeschaltet
    (Zeile bleibt an ihrer Position, ``enabled: false``), in E-Mail und
    Telegram eingeschaltet, When gerendert, Then fehlt Boeen in SMS und
    Premium-SMS (folgt der SMS-Liste), steht aber in Mail und Telegram."""
    sms = [_zeile(m, enabled=(m != "gust")) for m in _AUSWAHL]
    assert sms[1]["metric_id"] == "gust" and sms[1]["enabled"] is False, "Testaufbau: Aus-Zeile an Position 2"
    mit, _ = render_trip_dict(monkeypatch, _trip(_volle_listen(sms=sms)), name="3031-t14")

    assert not _erscheint(mit, "sms", "gust"), "Boeen steht trotz Aus-Schalter in der SMS"
    assert not _erscheint(mit, "premium_sms", "gust"), "Premium-SMS folgt nicht der SMS-Liste"
    assert _erscheint(mit, "email_html", "gust"), "Boeen fehlt in der Mail (anderer Kanal betroffen)"
    assert _erscheint(mit, "email_plain", "gust"), "Boeen fehlt in der Klartext-Mail"
    assert _erscheint(mit, "telegram_rich", "gust"), "Boeen fehlt in Telegram (anderer Kanal betroffen)"
    # Uebrige SMS-Metriken bleiben (die Aus-Zeile verschiebt nichts):
    for mid in ("wind", "precipitation"):
        assert _erscheint(mit, "sms", mid), f"{mid} fehlt in der SMS"


def test_14_reihenfolge_der_sms_ist_die_listenreihenfolge_ohne_order(monkeypatch):
    """Die schlanke Form traegt KEIN ``order``: die Reihenfolge der Liste ist
    die Reihenfolge im Bericht (stabile Sortierung). Umgedrehte SMS-Liste ⇒
    umgedrehte Token-Folge."""
    umgedreht = [_zeile(m) for m in reversed(_AUSWAHL)]
    mit, _ = render_trip_dict(monkeypatch, _trip(_volle_listen(sms=umgedreht)), name="3031-t14b")
    ids, _ = parse_kanal(mit, "sms")
    erwartet = [m for m in reversed(_AUSWAHL) if m in ids]
    assert ids == erwartet, f"SMS-Reihenfolge folgt nicht der Liste: {ids} statt {erwartet}"
    assert len(ids) >= 3 and "gust" in ids, f"Vakuum-Schutz (eingeschaltete Boeen muessen erkannt werden): {ids}"


# ═══════════════════════════ Test 2b (AC-8) ══════════════════════════════════


def test_2b_neue_metrik_luftdruck_erscheint_in_allen_kanaelen(monkeypatch):
    """Test 2b / AC-8 (Trip): Given „Luftdruck" im Reiter Wetter neu
    eingeschaltet und von der Karte beim Speichern eingeschaltet ans Ende
    jeder Kanalliste gesetzt, When gerendert, Then erscheint Luftdruck in
    Mail, Telegram und SMS."""
    auswahl = ["wind", "gust", "precipitation", "pressure"]
    listen = {k: [_zeile(m) for m in auswahl] for k in ("email", "telegram", "sms")}
    mit, _ = render_trip_dict(monkeypatch, _trip(listen, auswahl), name="3031-t2b")
    for kanal in ("email_html", "email_plain", "telegram_rich", "sms"):
        assert _erscheint(mit, kanal, "pressure"), f"Luftdruck fehlt in {kanal}"
    assert (roh_wert_der_metrik(mit, "email_html", "pressure") or "").startswith(_PRESS_ROH)


def test_2b_abgewaehlte_metrik_fehlt_in_allen_kanaelen(monkeypatch):
    """Test 2b / AC-8, Abwahl: Luftdruck im Reiter Wetter abgewaehlt ⇒ die
    Karte schreibt ihn in keine Liste mehr ⇒ er erscheint in keinem Kanal."""
    auswahl = ["wind", "gust", "precipitation"]
    listen = {k: [_zeile(m) for m in auswahl] for k in ("email", "telegram", "sms")}
    mit, _ = render_trip_dict(monkeypatch, _trip(listen, auswahl), name="3031-t2b-ab")
    for kanal in ("email_html", "email_plain", "telegram_rich", "sms", "premium_sms"):
        assert not _erscheint(mit, kanal, "pressure"), f"abgewaehlter Luftdruck steht in {kanal}"


def test_2b_teilmengenregel_alter_kanaleintrag_holt_abgewaehlte_metrik_nicht_zurueck(monkeypatch):
    """Teilmengen-Regel (ADR-0050 R3) als Schutz: steht in einer Kanalliste
    noch ein eingeschalteter Luftdruck, den der Reiter Wetter abgewaehlt hat
    (etwa ein Altbestand), erscheint er trotzdem in keinem Kanal."""
    auswahl = ["wind", "gust", "precipitation"]
    listen = {k: [_zeile(m) for m in auswahl + ["pressure"]] for k in ("email", "telegram", "sms")}
    mit, _ = render_trip_dict(monkeypatch, _trip(listen, auswahl), name="3031-t2b-r3")
    for kanal in ("email_html", "telegram_rich", "sms"):
        assert not _erscheint(mit, kanal, "pressure"), f"Kanalliste holt abgewaehlten Luftdruck in {kanal} zurueck"
