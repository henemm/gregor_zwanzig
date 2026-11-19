"""#3154: das erste Speichern der Tabelle "Was steht wo" aendert die Mail nicht.

SPEC: docs/specs/modules/feat_3122_was_steht_wo.md Teil A Nr. 8, AC-11.

Nutzersicht: ein Trip ohne gespeicherte Tabelle; der Nutzer oeffnet die Karte
(GET) und speichert den gezeigten Stand unveraendert (PUT). Danach muessen
3-Tages-Ausblick und Grosswetterlage ("Wetterlage: ...") je Briefing-Typ
genau so in der Mail stehen wie vorher, und die Karte muss den Ausblick so
zeigen, wie die Mail ihn sendet.

* F002: ausfuehrlich + ``show_outlook: false`` -- vorher keine
  Grosswetterlage, nach dem Speichern "Wetterlage: ...".
* F003: Kompakt + ``show_outlook: false`` -- die Kompakt-Mail zeigte den
  Ausblick, die Karte "Ausblick aus"; nach dem Speichern fehlte er.

Kern-Schicht: echte Dateien, echter Python-Router (GET, Begleitfelder des
PUT), echter Versandweg (``NotificationService``, Naht nur am Transport).
Der PUT selbst ist Go (``store.SaveBriefingPlacements``); ``_put_wie_go``
schreibt dieselben zwei Felder, die der Go-Test
``internal/handler/placements_erstanlage_3154_test.go`` am echten Handler
prueft -- verbunden ueber die aufgezeichnete Kern-Antwort
``tests/fixtures/placements_erstanlage_3154/stabilitaet_aus.json``.
Den Ausblick-Tagesdatensatz gibt es nur, wenn der Zeitplaner ihn abruft
(``render_options.show_multi_day_trend``, wie ``trip_briefing_aufbau``).
"""
from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.tdd._einstellung_gleich_mail_trip_fixtures import (
    AUSBLICK_TAGE, BASIS_KATALOG, STAGE_NAME, TRANSPORT_ENV, TZ, ausblick_zeilen,
    frisches_profil, mail_teile, night_weather, segment, trip_json,
)
from tests.helpers.einstellung_gleich_mail_trip import html_ausblick, klartext_ausblick
from tests.helpers.transport_mitschrift import aufzeichner_installieren

KENNUNG = "erstes-speichern"
FEHLT = "fehlt"
REPORT_TYPES = ("morning", "evening")
FIXTURE = Path(__file__).parents[1] / "fixtures" / "placements_erstanlage_3154" / "stabilitaet_aus.json"

#: Format x show_outlook x show_stability x multi_day_trend_reports.
MATRIX = list(itertools.product(
    ("full", "compact"), (True, False, FEHLT), (True, False, FEHLT),
    (FEHLT, ["morning", "evening"], []),
))


def _id(fall) -> str:
    fmt, ausblick, stabil, trend = fall
    return f"{fmt}-outlook_{ausblick}-stab_{stabil}-trend_{trend}"


@pytest.fixture
def client():
    from api.routers import placements

    app = FastAPI()
    app.include_router(placements.router)
    return TestClient(app)


def _datei(uid: str) -> Path:
    from app.loader import get_data_root

    return Path(get_data_root()) / "users" / uid / "briefings" / f"{KENNUNG}.json"


def _anlegen(uid: str, fall) -> dict:
    fmt, ausblick, stabil, trend = fall
    rc: dict = {"email_format": fmt}
    for schluessel, wert in (("show_outlook", ausblick), ("show_stability", stabil),
                             ("multi_day_trend_reports", trend)):
        if wert != FEHLT:
            rc[schluessel] = wert
    daten = trip_json(list(BASIS_KATALOG), report_config=rc, trip_id=KENNUNG)
    daten["kind"] = "route"
    _datei(uid).parent.mkdir(parents=True, exist_ok=True)
    _datei(uid).write_text(json.dumps(daten), encoding="utf-8")
    return daten


def _roh(uid: str) -> dict:
    return json.loads(_datei(uid).read_text(encoding="utf-8"))


def _mail(monkeypatch, uid: str, report_type: str) -> dict:
    """Mail ueber den echten Versandweg, Trip von der Platte des Nutzers."""
    from app.loader import get_data_root, load_trip
    from app.models import StabilityResult
    from services.notification_service import NotificationService, TripReportRequest
    from services.report_config_resolver import resolve_report_render_options

    for k, v in TRANSPORT_ENV.items():
        monkeypatch.setenv(k, v)
    mitschrift = aufzeichner_installieren(monkeypatch)
    trip = load_trip(KENNUNG, data_dir=get_data_root(), user_id=uid)
    rc = trip.report_config
    abruf = resolve_report_render_options(rc, trip.display_config, report_type)
    request = TripReportRequest(
        trip=trip, report_type=report_type, segment_weather=[segment()], trip_tz=TZ,
        night_weather=night_weather(), stage_name=STAGE_NAME, stage_stats=None,
        multi_day_trend=(ausblick_zeilen(trip, report_type)
                         if abruf.show_multi_day_trend else None),
        stability_result=StabilityResult(label="STABIL", confidence_pct=82),
        report_config=rc, display_config=trip.display_config,
        send_email=True, send_sms=False, send_telegram=False, send_premium_sms=False,
    )
    assert NotificationService(user_id=uid).send_trip_report(request).sent
    html, text = mail_teile(mitschrift)
    teile = {"text": text} if html is None else {"html": html, "text": text}
    return {teil: {
        "ausblick": (html_ausblick(inhalt) if teil == "html"
                     else klartext_ausblick(inhalt, AUSBLICK_TAGE)) is not None,
        "wetterlage": "Wetterlage:" in inhalt,
    } for teil, inhalt in teile.items()}


def _get(client, uid: str) -> dict:
    antwort = client.get(f"/api/briefings/{KENNUNG}/placements",
                         params={"kind": "route", "user_id": uid})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _erstanlage(client, uid: str, kennung: str = KENNUNG):
    return client.get(f"/api/briefings/{kennung}/placements/erstanlage",
                      params={"kind": "route", "user_id": uid})


def _put_wie_go(client, uid: str, placements: dict) -> None:
    """Was der Go-PUT schreibt: ``display_config.placements`` und, wenn der
    Kern es meldet, ``report_config.show_stability = false``."""
    begleit = _erstanlage(client, uid)
    assert begleit.status_code == 200, begleit.text
    daten = _roh(uid)
    daten["display_config"]["placements"] = copy.deepcopy(placements)
    if begleit.json()["show_stability_off"] is True:
        daten["report_config"]["show_stability"] = False
    _datei(uid).write_text(json.dumps(daten), encoding="utf-8")


@pytest.mark.parametrize("fall", MATRIX, ids=[_id(f) for f in MATRIX])
def test_erstes_speichern_erhaelt_ausblick_und_wetterlage(monkeypatch, client, fall):
    uid = frisches_profil()
    _anlegen(uid, fall)
    vorher = {rt: _mail(monkeypatch, uid, rt) for rt in REPORT_TYPES}
    karte = _get(client, uid)
    assert karte["stored"] is False

    # (2) Die Karte zeigt den Ausblick so, wie die Mail ihn sendet.
    for rt in REPORT_TYPES:
        gesendet = {t["ausblick"] for t in vorher[rt].values()}
        assert len(gesendet) == 1, f"{rt}: HTML und Text uneinig: {vorher[rt]}"
        zeigt = rt in karte["outlook_reports"]
        assert karte["blocks"]["outlook"][rt] is zeigt
        assert zeigt is gesendet.pop(), f"{rt}: Karte {karte['outlook_reports']}, Mail {vorher[rt]}"

    roh_vorher = _roh(uid)
    _put_wie_go(client, uid, karte["placements"])

    # (1) Ausblick und Grosswetterlage je Briefing-Typ wie vorher.
    for rt in REPORT_TYPES:
        assert _mail(monkeypatch, uid, rt) == vorher[rt], f"{rt}: Mail nach dem ersten Speichern"
    # (3) Ausser placements und ggf. show_stability ist nichts veraendert.
    roh_nachher = _roh(uid)
    for roh in (roh_vorher, roh_nachher):
        roh["display_config"].pop("placements", None)
    rc_vorher, rc_nachher = roh_vorher["report_config"], roh_nachher["report_config"]
    if rc_nachher.get("show_stability") != rc_vorher.get("show_stability"):
        assert rc_nachher["show_stability"] is False and fall[:2] == ("full", False), (
            "show_stability darf sich nur bei ausfuehrlich + show_outlook false aendern")
        rc_nachher.pop("show_stability")
        rc_vorher.pop("show_stability", None)
    assert roh_nachher == roh_vorher
    # Mit Tabelle meldet der Kern nichts mehr (nur das ERSTE Speichern).
    assert _erstanlage(client, uid).json() == {"show_stability_off": False}


def test_f002_ausfuehrlich_ohne_ausblick_bleibt_ohne_wetterlage(monkeypatch, client):
    """F002 benannt, plus (4): ein zweites Speichern fasst ``show_stability``
    nicht mehr an, auch wenn der Nutzer es inzwischen eingeschaltet hat."""
    uid = frisches_profil()
    _anlegen(uid, ("full", False, FEHLT, FEHLT))
    assert _mail(monkeypatch, uid, "evening") == {
        "html": {"ausblick": False, "wetterlage": False},
        "text": {"ausblick": False, "wetterlage": False}}
    assert _erstanlage(client, uid).json() == json.loads(FIXTURE.read_text())
    _put_wie_go(client, uid, _get(client, uid)["placements"])
    assert _roh(uid)["report_config"]["show_stability"] is False
    assert _mail(monkeypatch, uid, "evening")["html"]["wetterlage"] is False

    daten = _roh(uid)
    daten["report_config"]["show_stability"] = True
    _datei(uid).write_text(json.dumps(daten), encoding="utf-8")
    _put_wie_go(client, uid, _get(client, uid)["placements"])
    assert _roh(uid)["report_config"]["show_stability"] is True


def test_f003_kompakt_ohne_ausblick_schalter_zeigt_und_behaelt_ausblick(monkeypatch, client):
    uid = frisches_profil()
    _anlegen(uid, ("compact", False, FEHLT, FEHLT))
    assert _mail(monkeypatch, uid, "evening")["text"]["ausblick"] is True
    karte = _get(client, uid)
    assert karte["outlook_reports"] == ["evening"]
    assert karte["blocks"]["outlook"] == {"morning": False, "evening": True}
    _put_wie_go(client, uid, karte["placements"])
    assert _mail(monkeypatch, uid, "evening")["text"]["ausblick"] is True
    assert "show_stability" not in _roh(uid)["report_config"]


def test_begleitfelder_je_nutzer_und_nie_fremd(client):
    """Zwei Nutzer mit derselben Kennung: jeder bekommt die Aussage zu SEINEM
    Abo; ein fremdes oder unbekanntes Abo ist 404, ``kind`` ist Pflicht."""
    a, b = frisches_profil(), frisches_profil()
    _anlegen(a, ("full", False, FEHLT, FEHLT))
    _anlegen(b, ("compact", False, FEHLT, FEHLT))
    assert _erstanlage(client, a).json() == {"show_stability_off": True}
    assert _erstanlage(client, b).json() == {"show_stability_off": False}
    assert _erstanlage(client, a, "gibt-es-nicht").status_code == 404
    ohne = client.get(f"/api/briefings/{KENNUNG}/placements/erstanlage",
                      params={"user_id": a})
    assert ohne.status_code == 400
