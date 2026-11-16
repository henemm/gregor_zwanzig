"""TDD RED -- #3048 (Altbestand-Trip ohne Metriken) und #3052 (Telegram-Kopf
in Nutzersprache), Epic #3047.

SPEC: docs/specs/modules/fix_3048_altbestand_telegram_kopf.md (AC-1..AC-9)

Echte Kette ohne Mocks: Trip-JSON wird ueber den echten Loader geladen (Datei
im Briefings-Ordner eines frischen Nutzers bzw. Dict-Form), die Mail laeuft
durch ``NotificationService`` bis in den Transport-Aufzeichner, die
Telegram-Bubbles kommen aus dem echten ``render_telegram_bubbles``. Das Soll
steht von Hand als Literal (Standard-Stundenspalten, Katalogtexte), es wird
nicht aus dem Produktcode berechnet.

Ergaenzend (Bestandstests auf Soll umgestellt):
``test_einstellung_gleich_mail_trip.py::test_n1_altbestand_ohne_metrics``,
``test_einstellung_gleich_mail_editor_standard.py::test_python_seite_trip_tabellen_altbestand``,
``tests/golden/telegram_briefing/briefing_normalstil.de.txt``,
``test_issue_1001_telegram_bubbles.py::TestAC6RegressionHeaderPreserved``.

Lauf:
    uv run pytest tests/tdd/test_fix_3048_altbestand_telegram_kopf.py -q
"""
from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from app.loader import get_briefings_dir, get_locations_dir, load_all_locations, load_trip
from tests.helpers.einstellung_gleich_mail_trip import html_tabellen, klartext_tabellen
from tests.helpers.telegram_briefing_fixture import (
    TZ, _display_config, _rows, _segment,
)
from tests.tdd._einstellung_gleich_mail_trip_fixtures import (
    frisches_profil, mail_teile, render_trip_mit_ausblick, trip_json,
)

#: Standard-Stundenspalten (von Hand, = Pruefkatalog
#: ``_REGISTER_STANDARD_STUNDENSPALTEN``); Tagestief/-hoch haben keine
#: Stundenspalte (#1484).
_STANDARD_STUNDENSPALTEN = [
    "temperature", "wind", "gust", "precipitation", "thunder", "freezing_level",
    "visibility",
]
#: Standardsatz des Trips (von Hand, Doku Fall A in ``trip_metric_ids.py``).
_STANDARD_SATZ = _STANDARD_STUNDENSPALTEN + ["temperature_day_low", "temperature_day_high"]


# ---------------------------------------------------------------------------
# Hilfen
# ---------------------------------------------------------------------------


def _altbestand(variante: str, trip_id: str = "altbestand-3048") -> dict:
    """Trip-JSON mit ``display_config`` ohne ``metrics`` (``fehlt``) bzw. mit
    ``metrics: []`` (``leer``)."""
    data = trip_json(["temperature"], trip_id=trip_id)
    if variante == "fehlt":
        del data["display_config"]["metrics"]
    else:
        data["display_config"]["metrics"] = []
    data["display_config"].pop("channel_layouts", None)
    return data


def _trip_aus_datei(data: dict, uid: str):
    """Trip als Datei in den Briefings-Ordner des Nutzers legen und ueber den
    echten Datei-Loader laden (der Weg, den Scheduler und API gehen)."""
    ordner = get_briefings_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / f"{data['id']}.json"
    pfad.write_text(json.dumps(data), encoding="utf-8")
    trip = load_trip(pfad, user_id=uid)
    assert trip is not None, "Trip-Datei liess sich nicht laden"
    return trip


def _aktive_ids(trip) -> list[str]:
    return [m.metric_id for m in trip.display_config.metrics if m.enabled]


def _ueberblick_klartext(text: str) -> list[str]:
    """Zeilen des Metriken-Ueberblicks im Klartext (zwischen Ueberschrift und
    Leerzeile)."""
    from i18n import t

    zeilen = text.splitlines()
    kopf = f"━━ {t('mail.pille.ueberschrift', 'de')} ━━"
    assert kopf in zeilen, "Metriken-Ueberblick fehlt in der Klartext-Mail"
    start = zeilen.index(kopf) + 1
    ende = zeilen.index("", start)
    return zeilen[start:ende]


# ---------------------------------------------------------------------------
# AC-1 / AC-2 -- Loader ergaenzt den Standardsatz (zwei Nutzer, Datei-Pfad)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variante", ["fehlt", "leer"])
def test_loader_ergaenzt_standardsatz_fuer_zwei_nutzer(variante):
    """AC-1/AC-2: Trip-Datei ohne bzw. mit leerer ``metrics``-Liste -- der
    Loader liefert fuer beide Nutzer den Standardsatz, eingeschaltet."""
    uid_a, uid_b = frisches_profil(), frisches_profil()
    assert uid_a != uid_b and "default" not in (uid_a, uid_b)
    for uid in (uid_a, uid_b):
        trip = _trip_aus_datei(_altbestand(variante), uid)
        assert _aktive_ids(trip) == _STANDARD_SATZ, (
            f"{variante}/{uid}: Loader liefert {_aktive_ids(trip)}, Soll {_STANDARD_SATZ}")
        # Eintraege muessen ins Layout passen (bucket/order wie auto_distribute),
        # nicht alle auf secondary/0 fallen.
        primaer = [m.metric_id for m in trip.display_config.metrics if m.bucket == "primary"]
        assert primaer, f"{variante}/{uid}: kein Standard-Eintrag im Primaerbereich"


@pytest.mark.parametrize("variante", ["fehlt", "leer"])
def test_loader_standardsatz_traegt_register_reihenfolge_in_order(variante):
    """AC-1/AC-2 (Gegenprobe F002): die ergaenzten Eintraege tragen die
    Register-Reihenfolge als aufsteigende ``order`` (0, 1, 2, ...) im
    Primaerbereich -- so, wie die Editor-Vorbelegung eines neuen Trips sie
    speichert. Sortiert ein Leser (Editor, Kanal-Layout) nach ``order``, muss
    genau der Standardsatz in Register-Folge herauskommen; fallen alle auf
    ``order=0``, ist die Folge nicht mehr festgelegt."""
    uid = frisches_profil()
    trip = _trip_aus_datei(_altbestand(variante), uid)
    standard = [m for m in trip.display_config.metrics if m.metric_id in _STANDARD_SATZ]
    assert [(m.metric_id, m.bucket, m.order) for m in standard] == [
        (mid, "primary", i) for i, mid in enumerate(_STANDARD_SATZ)
    ], f"{variante}: Eintraege {[(m.metric_id, m.bucket, m.order) for m in standard]}"
    nach_order = sorted(standard, key=lambda m: m.order, reverse=True)
    assert [m.metric_id for m in nach_order] == list(reversed(_STANDARD_SATZ)), (
        f"{variante}: Sortierung nach order ergibt nicht die Register-Folge")


@pytest.mark.parametrize("variante", ["fehlt", "leer"])
@pytest.mark.parametrize("fmt", ["html", "klartext"])
def test_mail_tabellen_zeigen_standardspalten(monkeypatch, variante, fmt):
    """AC-1/AC-2: Etappen- und Nachttabelle derselben Mail zeigen die
    Standard-Wertspalten (heute: keine Wertspalte)."""
    mitschrift, _trip, _uid = render_trip_mit_ausblick(monkeypatch, _altbestand(variante))
    html, text = mail_teile(mitschrift)
    tabellen = html_tabellen(html) if fmt == "html" else klartext_tabellen(text)
    for art in ("etappe", "nacht"):
        assert tabellen[art], f"{variante}/{fmt}: {art}-Tabelle fehlt"
        for tab in tabellen[art]:
            assert tab.spalten == _STANDARD_STUNDENSPALTEN, (
                f"{variante}/{fmt}/{art}: Spalten {tab.spalten}, "
                f"Soll {_STANDARD_STUNDENSPALTEN}")


@pytest.mark.parametrize("variante", ["fehlt", "leer"])
def test_ueberblick_und_tabellen_aus_derselben_liste(monkeypatch, variante):
    """AC-1/AC-2: der Metriken-Ueberblick zeigt den Standardsatz (eine Zeile je
    Stundenspalte; Tagestief/-hoch stehen in der Temperatur-Zeile), und die
    Tabellen tragen dieselben Stundenspalten -- beide aus der geladenen Liste,
    nicht der Ueberblick aus einem Rueckfall."""
    mitschrift, trip, _uid = render_trip_mit_ausblick(monkeypatch, _altbestand(variante))
    _html, text = mail_teile(mitschrift)
    ueberblick = _ueberblick_klartext(text)
    assert len(ueberblick) == len(_STANDARD_STUNDENSPALTEN), ueberblick
    assert _aktive_ids(trip) == _STANDARD_SATZ, (
        f"{variante}: Ueberblick kommt aus dem Rueckfall, geladene Liste ist "
        f"{_aktive_ids(trip)}")
    spalten = klartext_tabellen(text)["etappe"][0].spalten
    assert spalten == [m for m in _aktive_ids(trip) if m in _STANDARD_STUNDENSPALTEN]


def test_fehlt_und_leer_liefern_identische_mail(monkeypatch):
    """AC-2: ``metrics: []`` ergibt dieselben Tabellen wie das fehlende Feld."""
    ergebnisse = []
    for variante in ("fehlt", "leer"):
        mitschrift, _t, _u = render_trip_mit_ausblick(monkeypatch, _altbestand(variante))
        html, text = mail_teile(mitschrift)
        ergebnisse.append((
            [t.spalten for t in html_tabellen(html)["etappe"]],
            [t.spalten for t in klartext_tabellen(text)["etappe"]],
        ))
    assert ergebnisse[0] == ergebnisse[1]
    assert ergebnisse[0][0] and ergebnisse[0][0][0] == _STANDARD_STUNDENSPALTEN


# ---------------------------------------------------------------------------
# AC-3 -- bewusst leer (alle Eintraege aus) bleibt leer (#1394)
# ---------------------------------------------------------------------------


def test_bewusst_leer_bleibt_leer(monkeypatch):
    """AC-3 (Schutz #1394): Eintraege vorhanden, alle ausgeschaltet -- kein
    Standardsatz, keine Wertspalten."""
    data = trip_json(["temperature", "wind"], trip_id="bewusst-leer-3048")
    for eintrag in data["display_config"]["metrics"]:
        eintrag["enabled"] = False
    data["display_config"].pop("channel_layouts", None)
    uid = frisches_profil()
    trip = _trip_aus_datei(copy.deepcopy(data), uid)
    assert _aktive_ids(trip) == [], f"bewusst leer: Loader ergaenzt {_aktive_ids(trip)}"
    mitschrift, _t, _u = render_trip_mit_ausblick(monkeypatch, data)
    html, text = mail_teile(mitschrift)
    for tab in html_tabellen(html)["etappe"] + klartext_tabellen(text)["etappe"]:
        assert not set(tab.spalten) & set(_STANDARD_STUNDENSPALTEN), tab.spalten


# ---------------------------------------------------------------------------
# AC-4 -- Orte unveraendert
# ---------------------------------------------------------------------------


def test_orte_ladepfad_ergaenzt_keinen_standardsatz():
    """AC-4: ein Ort mit ``display_config`` ohne ``metrics`` wird wie bisher
    ohne Metriken geladen (zwei Nutzer)."""
    for uid in (frisches_profil(), frisches_profil()):
        ordner = get_locations_dir(uid)
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / "ort-3048.json").write_text(json.dumps({
            "id": "ort-3048", "name": "Ort 3048", "lat": 47.27, "lon": 11.40,
            "elevation_m": 600, "display_config": {"show_night_block": True},
        }), encoding="utf-8")
        orte = load_all_locations(uid)
        assert [o.id for o in orte] == ["ort-3048"]
        assert orte[0].display_config is not None
        assert [m.metric_id for m in orte[0].display_config.metrics] == [], (
            f"{uid}: Orte-Ladepfad ergaenzt Metriken")


@pytest.mark.parametrize("variante", ["fehlt", "leer"])
def test_kanal_auflösung_trip_altbestand_liefert_standardsatz(variante):
    """#3048: die geteilte Kanal-Aufloesung (``resolve_channel_lists`` mit
    Flaeche ``trip``, genutzt von ``report_config_resolver``) liest die rohe
    Trip-``display_config`` selbst ein und muss fuer Altbestand denselben
    Standardsatz liefern wie der Trip-Loader -- nicht leer."""
    from services.channel_list_resolver import resolve_channel_lists

    dc = _altbestand(variante)["display_config"]
    sicht = resolve_channel_lists(copy.deepcopy(dc), "trip", "evening")
    for kanal in ("email", "telegram"):
        ids = [z.metric_id for z in getattr(sicht, kanal)]
        assert ids == _STANDARD_SATZ, (
            f"{variante}/{kanal}: Kanal-Aufloesung liefert fuer Trip-Altbestand {ids}")


def test_trip_ohne_display_config_bleibt_beim_profil_standard():
    """Gegenprobe: Trip ganz ohne ``display_config`` (Zweig #111) bleibt
    unveraendert beim Profil-Standard und ist nicht leer."""
    data = trip_json(["temperature"], trip_id="ohne-dc-3048")
    del data["display_config"]
    trip = load_trip(data, user_id=frisches_profil())
    assert _aktive_ids(trip), "Profil-Standard-Zweig liefert keine Metriken"


# ---------------------------------------------------------------------------
# AC-6 .. AC-9 -- Telegram-Kopf in Nutzersprache
# ---------------------------------------------------------------------------


def _kopf(report_type: str, **kw) -> str:
    """Kopf-Bubble eines Briefings am 15.07.2026 (echter Renderer)."""
    from output.renderers.narrow import render_telegram_bubbles

    seg = _segment(1, (0.0, 8.0), (7, 12), [])
    start = datetime(2026, 7, 15, 7, 0, tzinfo=TZ)
    seg = replace(seg, segment=replace(seg.segment, start_time=start,
                                       end_time=start + timedelta(hours=5)))
    bubbles = render_telegram_bubbles(
        segments=[seg], seg_tables=[_rows(range(7, 13))], dc=_display_config(),
        report_type=report_type, tz=TZ, trip_name="Kopf 3052", **kw,
    )
    return bubbles[0].text


def _kopfzeile(kopf: str) -> str:
    zeilen = kopf.splitlines()
    assert zeilen[0] == "Kopf 3052", zeilen
    return zeilen[1]


@pytest.mark.parametrize("report_type, soll", [
    ("evening", "Abend 15.07.2026"),
    ("morning", "Morgen 15.07.2026"),
    ("alert", "Alarm 15.07.2026"),
])
def test_telegram_kopf_deutsch(report_type, soll):
    """AC-6: deutsche Nutzer sehen die Briefing-Art auf Deutsch."""
    assert _kopfzeile(_kopf(report_type, lang="de")) == soll


def test_telegram_kopf_ohne_lang_ist_deutsch():
    """AC-6: Bestandsaufrufer ohne ``lang`` (Default de) bekommen Deutsch."""
    assert _kopfzeile(_kopf("evening")) == "Abend 15.07.2026"


@pytest.mark.parametrize("report_type, soll", [
    ("evening", "Evening 15.07.2026"),
    ("morning", "Morning 15.07.2026"),
])
def test_telegram_kopf_englisch(report_type, soll):
    """AC-7: englische Nutzer sehen weiter ``Evening``/``Morning``."""
    assert _kopfzeile(_kopf(report_type, lang="en")) == soll


@pytest.mark.parametrize("language, soll", [
    ("en", "Evening 20.07.2026"),
    ("de", "Abend 20.07.2026"),
])
def test_telegram_kopf_im_versand_folgt_nutzersprache(monkeypatch, language, soll):
    """AC-6/AC-7 dort, wo der Nutzer es erreicht (Gegenprobe F001): Profil mit
    ``language`` -> ``NotificationService.send_trip_report`` ->
    ``TripReportFormatter`` -> ``render_telegram_bubbles`` -> Telegram-
    Transport. Die erste zugestellte Bubble traegt die Briefing-Art in der
    Nutzersprache (Etappendatum der Fixture: 20.07.2026)."""
    data = trip_json(["temperature"], trip_id=f"kopf-versand-{language}",
                     report_config={"send_telegram": True})
    mitschrift, _trip, uid = render_trip_mit_ausblick(
        monkeypatch, data, language=language)
    sendungen = mitschrift.sendungen("telegram")
    assert sendungen, f"{language}: keine Telegram-Sendung: {mitschrift!r}"
    assert {s["empfaenger"] for s in sendungen} == {f"chat-{uid}"}
    zeilen = sendungen[0]["body"].splitlines()
    assert zeilen[0] == "Pruefkatalog 3047", zeilen
    assert zeilen[1] == soll, f"{language}: Telegram-Kopf {zeilen[1]!r}, Soll {soll!r}"


@pytest.mark.parametrize("lang", ["de", "en"])
def test_telegram_kopf_unbekannter_typ_faellt_auf_title_zurueck(lang):
    """AC-8: unbekannter Typ -> ``.title()``-Form, Datum bleibt, kein Fehler."""
    assert _kopfzeile(_kopf("sonder", lang=lang)) == "Sonder 15.07.2026"


@pytest.mark.parametrize("lang, soll", [("de", "Abend"), ("en", "Evening")])
def test_mail_und_telegram_nennen_dieselbe_briefing_art(lang, soll):
    """AC-9: Mail-Kopf und Telegram-Kopf desselben Briefings tragen dieselbe
    Briefing-Art (eine Quelle). Mail-Seite: der Kopftext ``mail.kopf.briefing``
    mit dem Katalogtext; Telegram-Seite: Kopfzeile des Renderers."""
    from i18n import t

    from output.renderers.briefing_typ import briefing_typ

    assert briefing_typ("evening", lang) == soll
    mail_kopf = t("mail.kopf.briefing", lang, typ=briefing_typ("evening", lang))
    assert soll in mail_kopf
    assert _kopfzeile(_kopf("evening", lang=lang)) == f"{soll} 15.07.2026"


def test_mail_html_nutzt_die_geteilte_quelle():
    """AC-9: die Mail zieht die Briefing-Art aus demselben neutralen Modul
    wie Telegram -- kein zweiter Helfer im Mail-Paket."""
    from output.renderers import briefing_typ as modul
    from output.renderers.email import html

    assert html._briefing_typ is modul.briefing_typ
