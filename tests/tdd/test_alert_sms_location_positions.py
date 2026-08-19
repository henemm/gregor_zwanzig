"""TDD RED — Issue #1467 Scheibe S2, Arbeitsgang AG3b (Korrektur-Runde,
PO-Beanstandung 2026-08-04): die Kurznachricht (SMS) eines
Ortsvergleich-Aenderungsalarms enthaelt NUR NOCH DIE WERTE — jeder Ort als
ZAHL (1-basierte Position in der AKTUELLEN Ortsliste des Vergleichs), gar
kein Kopf, kein Ortsname, kein Vergleichsname.

SPEC: docs/specs/modules/rework_1467_s2_aenderungsalarm.md — AC-7, Abschnitt
"AG3 — Darstellung der Kurznachrichten".
Kontext: docs/context/rework-1467-s2-ag3b-ag4.md

WAS DIE AUSGELIEFERTE FASSSUNG (Commit 97ec3deb) FALSCH MACHT — alle drei
Werte hier GEMESSEN (`render_sms()` ueber `to_multi_point_alert_message()`,
kein hergeleiteter Text):

  | Fall       | heute                        | Ziel (PO)         |
  |------------|------------------------------|-------------------|
  | zwei Orte  | 'Graz, Wien: 2:+R45 1:+R30'  | '2:+R45 1:+R30'   |
  | ein Ort    | 'Graz Graz: +R30'            | '+R30'            |

Begruendung des PO (er hatte den Kopf zuvor selbst als "Schluessel zu den
Zahlen" verteidigt und diese Entscheidung ausdruecklich zurueckgenommen):
DIE ZAHL IST DIE ORTSANGABE. Ein Kopf, der die Ortsliste noch einmal
ausschreibt, frisst genau das Laengenbudget, das die Zahlenkodierung
freischaufeln sollte — im Ein-Ort-Fall stand der Name sogar doppelt
('Graz Graz'), weil `to_multi_point_alert_message()`
(`src/output/renderers/alert/project.py:217-220`) denselben
`collective_label` in `trip_short` UND `location_label` schreibt.

Dritte Beanstandung — NACHRUECKEN IST RICHTIG: die ausgelieferte Fassung
sichert zu, dass eine nicht aufloesbare Orts-Kennung ihren Platz behaelt
(`compare_alert.py:190-203` Docstring + ein Test, der genau das festnagelte).
PO: "die nummer soll immer die Reihenfolge darstellen. Wenn ein Ort geloescht
wird, ruecken die anderen nach, das ist kein Fehler sondern fuer den User
nachvollziehbares Verhalten." Die Position ist damit der 1-basierte Index in
der AKTUELLEN (= aufloesbaren) Ortsliste; Luecken werden geschlossen.

WICHTIGE ABGRENZUNG (zwei verschiedene Arten von "Luecke"):
  * Ort STEHT NOCH in der Liste, hat diesmal nur nicht ausgeloest → er zaehlt
    mit, die Zahlen der folgenden Orte bleiben (`test_k3_position_numbers_*`).
  * Ort ist WEG (Kennung nicht mehr aufloesbar) → er zaehlt NICHT mit, die
    folgenden ruecken auf (`test_k4_deleted_location_*`).
Diese beiden Tests widersprechen sich nicht — sie trennen "nicht getroffen"
von "nicht mehr vorhanden".

ROT/GRUEN-Aufteilung dieser Datei:
- `test_k1_*`/`test_k2_*`/`test_k4_*`: ROT. Zielverhalten der Korrektur.
- `test_k3_*`: GRUEN vor UND nach (die Positions-Quelle aendert sich nicht)
  bis auf den weggefallenen Kopf im Goldstring — deshalb heute ROT im
  Goldstring, gruen in allen Einzel-Zusicherungen.
- `test_regression_*` (3 Tests): GRUEN vor UND nach dem Umbau. Sie nageln die
  drei anderen Alarmwege (Trip-Aenderung, Trip-Radar, Ortsvergleich-Radar)
  byte-identisch fest — ohne Orts-Positionszuordnung darf sich dort KEIN
  Zeichen aendern (Vorbild: AC-26 in
  `test_compare_alert_telegram_per_location.py`). Die Vergleichswerte sind
  gemessene Goldstrings, keine Vermutungen. K-3 der Korrektur-Runde ist die
  wichtigste Zusicherung: wird einer dieser drei rot, ist das ein BEFUND —
  kein Anlass, den Goldstring anzupassen.

TESTPOLITIK (CLAUDE.md, Kern-Schicht): kein `Mock()`/`patch()`/`MagicMock`.
Als Naht dient ein echter lokaler HTTP-Stub fuer die seven.io-SMS-API
(Loopback-Socket, 1:1 das Muster aus `test_compare_alert_telegram_per_location.py`
und `test_telegram_kurzstil_trip_alert.py`), eine echte
`LocationWeatherSource`-Implementierung und echte Preset-/Orts-Dateien.

KEIN ECHTER VERSAND (Issue #1477): `Settings(...)` faellt bei NICHT gesetzten
Feldern still auf die Prod-`.env` des Worktrees zurueck (gemessen:
`Settings().telegram_chat_id == '<Prod-Chat>'`, `sms_gateway_url ==
'https://gateway.seven.io/api/sms'`). Deshalb setzt `_settings_sms_only()`
JEDES versandrelevante Feld ausdruecklich: Telegram-Felder auf leere
Zeichenketten (`can_send_telegram() == False`), SMS auf den lokalen Stub,
E-Mail auf leere Felder bzw. ausschliesslich `mail_sink`. Es gibt in dieser
Datei keinen Pfad, auf dem eine Nachricht den Rechner verlassen kann.

Pfadregel #1409: der Prueflings-Datenpfad wird relativ zur Testdatei
aufgeloest, nie ueber einen festen Hauptrepo-Pfad.
"""
from __future__ import annotations

import http.server
import re
import shutil
import socket
import threading
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import Settings
from app.models import (
    ChangeSeverity, GPXPoint, SegmentWeatherData, SegmentWeatherSummary,
    TripSegment, WeatherChange,
)
from app.trip import Stage, Trip, Waypoint
from app.user import SavedLocation
from services.notification_service import NotificationService, RadarAlertRequest
from services.radar_service import NowcastResult

from tests.helpers.compare_briefings import write_compare_briefings
import pytest


# Live-Schicht (Test-Politik, CLAUDE.md): braucht echtes Netz/echte Dienste --
# lief im Kern nie gruen (CI-Vermessung 2026-08-04, #1196) und gehoert per
# Marker in den /e2e-verify-Lauf, nicht auf eine Ausnahmeliste.
pytestmark = pytest.mark.live

# Pfadregel #1409: relativ zur Testdatei. `load_compare_presets()` liest
# ComparePresets ueber `data_root="data"` RELATIV zum Arbeitsverzeichnis
# (`src/app/loader.py:318`) und laeuft damit an der data-root-Isolation der
# conftest vorbei — die Preset-Dateien muessen deshalb genau hier liegen und
# werden im `finally` restlos wieder entfernt.
DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"


# ---------------------------------------------------------------------------
# Echte lokale Aufzeichnungs-Senke (kein Mock, kein Netz)
# ---------------------------------------------------------------------------

def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _SMSStub:
    """Lokaler HTTP-Stub fuer die seven.io-API — empfaengt den echten POST von
    `SMSOutput.send()` und zeichnet die Nutzlast auf. 1:1 das Muster aus
    `test_compare_alert_telegram_per_location.py::_SMSStub`."""

    def __init__(self) -> None:
        self.received: list[dict] = []
        received = self.received

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                data = urllib.parse.parse_qs(body.decode())
                received.append({k: v[0] for k, v in data.items()})
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"100")

            def log_message(self, *args):  # noqa: D401 - silence
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def texts(self) -> list[str]:
        return [r.get("text", "") for r in self.received]

    def stop(self) -> None:
        self._server.shutdown()


# ---------------------------------------------------------------------------
# Settings — JEDES versandrelevante Feld ausdruecklich gesetzt (#1477)
# ---------------------------------------------------------------------------

def _settings_sms_only(sms_port: int) -> Settings:
    """`can_send_sms() == True` gegen den LOKALEN Stub; Telegram ausdruecklich
    ausgeschaltet (leere Zeichenketten statt "Feld weglassen" — sonst zieht
    pydantic den Prod-Wert aus der `.env`, #1477); E-Mail-Felder leer, der
    E-Mail-Zweig laeuft ausschliesslich ueber `mail_sink`."""
    return Settings(
        smtp_host="", smtp_user="", smtp_pass="", mail_to="",
        telegram_bot_token="", telegram_chat_id="",
        sms_gateway_url=f"http://127.0.0.1:{sms_port}/api/sms",
        seven_api_key="tdd-stub-key", sms_to="+49000000000", sms_from=None,
    )


def _settings_email_and_sms(sms_port: int) -> Settings:
    """Wie oben, aber zusaetzlich `can_send_email() == True` (Dummy-SMTP; der
    Versand geht ueber `mail_sink`, es wird nie ein SMTP-Socket geoeffnet —
    `notification_service.py:1130-1131`)."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.invalid",
        telegram_bot_token="", telegram_chat_id="",
        sms_gateway_url=f"http://127.0.0.1:{sms_port}/api/sms",
        seven_api_key="tdd-stub-key", sms_to="+49000000000", sms_from=None,
    )


# ---------------------------------------------------------------------------
# Fixture-Daten (echte DTOs)
# ---------------------------------------------------------------------------

def _pwd(point_id: str, name: str, lat: float, lon: float, precip_sum_mm: float):
    """Echtes `PointWeatherData` (kein Mock)."""
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=name, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=datetime.now(timezone.utc), provider="test-scripted",
    )


class _ScriptedWeatherSource:
    """Deterministische `LocationWeatherSource`-Implementierung — ein
    Konfigurations-Seam, kein Mock: liefert echte `PointWeatherData` mit
    vorab festgelegten Werten, ohne Netz."""

    def __init__(self, values: dict[str, float]) -> None:
        self._values = dict(values)

    def fetch(
        self, point_id: str, lat: float, lon: float,
        start_hour: int | None = None, end_hour: int | None = None,
    ):
        return _pwd(point_id, point_id, lat, lon, self._values.get(point_id, 0.0))


def _gpx(lat: float, lon: float) -> GPXPoint:
    return GPXPoint(lat=lat, lon=lon, elevation_m=500.0)


def _change(new_value: float = 30.0) -> WeatherChange:
    """Niederschlags-Aenderung 2 -> `new_value` mm.

    Die verwendeten Zielwerte (30 und 45) sind bewusst so gewaehlt, dass die
    gerenderten Token (`+R30`, `+R45`) WEDER die Ziffer 1 NOCH die Ziffer 2
    NOCH die Ziffer 3 enthalten: jede Ziffer im Text kann damit nur aus der
    Positions-Kodierung stammen und nicht aus einem Messwert.

    Fix-Loop AG3b (Mutation M3): die Zielwerte je Ort sind ausserdem
    UNTERSCHIEDLICH. Solange zwei Orte denselben Messwert haben, sind ihre
    Token austauschbar — ein Test kann dann nur pruefen, DASS die Zahlen 1
    und 2 vorkommen, nicht WELCHER Ort welche Zahl bekommt. Genau diese
    Luecke liess `reversed(location_ids)` in `_location_positions()`
    unbemerkt durch."""
    return WeatherChange(
        metric="precip_sum_mm", old_value=2.0, new_value=new_value,
        delta=new_value - 2.0,
        threshold=5.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id="1",
    )


def _compare_preset(preset_id: str, location_ids: list[str], **extra) -> dict:
    """Compare-Preset-Rohdict. `location_ids` ist die QUELLE DER REIHENFOLGE
    fuer die Ortspositionen (Spec AG3: "1-basierte Position des Ortes in der
    konfigurierten Ortsliste des Vergleichs, identisch zur Spaltenreihenfolge
    der Vergleichs-E-Mail")."""
    preset = {
        "id": preset_id,
        "name": preset_id,
        "user_id": "unused",
        "location_ids": list(location_ids),
        "schedule": "daily",
        "weekday": 4,
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": [],
        "letzter_versand": None,
        "top_ort_letzter_versand": None,
        "created_at": "2026-08-04T00:00:00Z",
    }
    preset.update(extra)
    return preset


def _clean_user(user_id: str) -> None:
    d = DATA_ROOT / user_id
    if d.exists():
        shutil.rmtree(d)


def _trip_segment() -> TripSegment:
    start = datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    return TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=12.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500, distance_from_start_km=18.0),
        start_time=start, end_time=end, duration_hours=4.0, distance_km=6.0,
        ascent_m=500, descent_m=0,
    )


def _segment_weather_data() -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_trip_segment(), timeseries=None, aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _trip() -> Trip:
    stage = Stage(
        id="S1", name="Etappe 1", date=datetime(2026, 5, 1).date(),
        waypoints=[
            Waypoint(id="W1", name="Start", lat=47.0, lon=11.0, elevation_m=1000),
            Waypoint(id="W2", name="Ziel", lat=47.1, lon=11.1, elevation_m=1500),
        ],
    )
    return Trip(id="trip-ag3b", name="ProbeTrip", stages=[stage])


# ═══════════════════════════ K-1 / K-2 (RED) ═════════════════════════════════

def test_k1_bundled_two_location_sms_carries_only_the_values_no_head():
    """K-1 (ROT) GIVEN ein Ortsvergleich mit ZWEI Orten — "Graz" auf
    Position 1 und "Wien" auf Position 2 der konfigurierten Ortsliste
    (`preset["location_ids"] == ["loc-graz", "loc-wien"]`) — mit je EINER
    Metrik-Aenderung (Niederschlag 2 -> 30 mm) und eingeschaltetem SMS-Versand
    (`send_sms: true`, SMS-faehiges Konto, Nutzer mit SMS-Tarif).

    WHEN `CompareAlertService.check_all_compare_presets()` laeuft.

    THEN kommt an der SMS-Senke GENAU EINE Kurznachricht an, und in ihr gilt:
      (a) die beiden Ereignisse sind unterscheidbar und tragen ihre
          Ortsposition als ZAHL (1 und 2),
      (b) im gesamten Text steht KEIN Ortsname und KEIN Vergleichsname —
          gar kein Kopf, nur die Werte,
      (c) die Gesamtlaenge bleibt <= 140 Zeichen.

    ROT-Grund, an Commit 97ec3deb ueber genau diesen Weg GEMESSEN: der Text
    lautet heute `'Graz, Wien: 2:+R45 1:+R30'`. Die Zahlen stimmen bereits
    (AG3b), der Kopf `'Graz, Wien: '` ist die Beanstandung: er schreibt die
    Ortsliste noch einmal aus, obwohl die Zahl bereits DIE Ortsangabe ist —
    und frisst dabei genau das Laengenbudget, das die Zahlenkodierung
    freischaufeln sollte. 12 von 25 Zeichen dieser Nachricht sind Kopf.

    Die Reihenfolge-Quelle ist ausdruecklich `preset["location_ids"]` und
    nicht etwa die Trefferreihenfolge: beide Orte loesen hier gleichzeitig
    aus, ihre Positionen ergeben sich allein aus der Konfiguration.

    FIX-LOOP AG3b (Mutation M3): dieser Test hatte beiden Orten denselben
    Messwert (+28 mm ⇒ zweimal `+R30`) gegeben und nur geprueft, DASS die
    Ziffern 1 und 2 irgendwo im Text stehen. Damit war die eigentliche
    Zusicherung — "die Zahl 2 meint den ZWEITEN Ort meiner Liste" —
    unbewacht: `reversed(location_ids)` in `_location_positions()` blieb
    gruen. Jetzt tragen die Orte UNTERSCHIEDLICHE Messwerte (Graz +R30,
    Wien +R45), und geprueft wird die konkrete PAARUNG.

    Wien hat bewusst den GROESSEREN Messwert: `_sorted()`
    (`render.py:25-32`) ordnet die Token nach severity absteigend, Wien
    steht also VORNE — waehrend es die Positionszahl 2 traegt. Die Zahlen
    laufen im Text damit ABSTEIGEND (`2:… 1:…`). Das schliesst eine ganze
    Mutations-Familie aus: die Zahl kann weder aus der Token-Reihenfolge
    noch aus einem simplen Mitzaehler beim Rendern stammen, sie ist an den
    ORT gebunden.
    """
    from app.loader import get_data_dir, save_location
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    uid = f"tdd-ag3b-pos-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-ag3b-pos-{uuid.uuid4().hex[:6]}"
    sms_stub = _SMSStub()
    _clean_user(uid)
    try:
        # Tarif-Gate: `sms_allowed()` liest `user.json` aus dem (isolierten)
        # get_data_dir()-Baum, nicht aus dem relativen Preset-Pfad.
        import json

        user_dir = get_data_dir(uid)
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "user.json").write_text(json.dumps({"id": uid, "tier": "standard"}))

        save_location(
            SavedLocation(id="loc-graz", name="Graz", lat=47.07, lon=15.44, elevation_m=353),
            user_id=uid,
        )
        save_location(
            SavedLocation(id="loc-wien", name="Wien", lat=48.21, lon=16.37, elevation_m=171),
            user_id=uid,
        )
        write_compare_briefings(DATA_ROOT / uid, [
            _compare_preset(preset_id, ["loc-graz", "loc-wien"], send_sms=True)
        ])
        snapshots = CompareWeatherSnapshotService(user_id=uid)
        snapshots.save(preset_id, "loc-graz", _pwd("loc-graz", "Graz", 47.07, 15.44, 2.0))
        snapshots.save(preset_id, "loc-wien", _pwd("loc-wien", "Wien", 48.21, 16.37, 2.0))

        mails: list[tuple[str, str]] = []
        service = CompareAlertService(
            settings=_settings_email_and_sms(sms_stub.port), user_id=uid,
            weather_source=_ScriptedWeatherSource({"loc-graz": 30.0, "loc-wien": 45.0}),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        service.check_all_compare_presets()

        texts = sms_stub.texts()
        assert len(texts) == 1, (
            "K-1: erwartet GENAU EINE gebuendelte Kurznachricht an der "
            f"SMS-Senke, erhalten: {len(texts)} -- {texts!r}"
        )
        text = texts[0]

        # Setup-Kontrolle: beide Messwert-Token stehen ueberhaupt drin, und
        # sie sind UNTERSCHEIDBAR (verschiedene Messwerte je Ort).
        assert "+R30" in text and "+R45" in text, (
            "Setup-Kontrolle: erwartet je Ort ein eigenes Niederschlags-Token "
            f"('+R30' fuer Graz, '+R45' fuer Wien) im Text {text!r}"
        )

        # (c) Laengenbudget.
        assert len(text) <= 140, (
            f"K-1c: die Kurznachricht muss <=140 Zeichen bleiben, gemessen "
            f"{len(text)}: {text!r}"
        )

        # (a) DIE PAARUNG, nicht bloss das Vorkommen der Ziffern. Graz steht
        # auf Position 1 der konfigurierten Ortsliste, Wien auf Position 2 --
        # also MUSS `+R30` (Graz) die 1 tragen und `+R45` (Wien) die 2.
        # Gegen `reversed(location_ids)` in `_location_positions()` ist genau
        # das die wirksame Zusicherung.
        assert "1:+R30" in text, (
            "K-1a: Graz steht auf Position 1 von preset['location_ids'] "
            "(['loc-graz', 'loc-wien']) und traegt den Messwert +R30 -- "
            f"erwartet daher das Token '1:+R30' im Text {text!r}. Steht dort "
            "'2:+R30', stammt die Positionszahl nicht aus der konfigurierten "
            "Ortsliste."
        )
        assert "2:+R45" in text, (
            "K-1a: Wien steht auf Position 2 von preset['location_ids'] "
            "und traegt den Messwert +R45 -- erwartet daher das Token "
            f"'2:+R45' im Text {text!r}."
        )

        # (b) GAR KEIN Kopf mehr -- kein Ortsname, kein Vergleichsname.
        # PO-Entscheidung 2026-08-04: die ZAHL ist die Ortsangabe.
        assert "Graz" not in text, (
            "K-1b: der Ortsname 'Graz' darf in der Kurznachricht gar nicht "
            "mehr vorkommen -- die Positionszahl 1 IST seine Ortsangabe. "
            f"Gemessen: {text!r}"
        )
        assert "Wien" not in text, (
            f"K-1b: der Ortsname 'Wien' darf nicht mehr vorkommen: {text!r}"
        )
        # Der Vergleich heisst hier wie seine Kennung (`_compare_preset()`
        # setzt `name = preset_id`) -- also faellt auch ein Kopf auf, der
        # statt der Ortsliste den Vergleichsnamen zeigen wuerde.
        assert preset_id not in text, (
            "K-1b: auch der Name des Vergleichs gehoert nicht in die "
            f"Kurznachricht: {text!r}"
        )

        # Gemessener Goldstring des vollstaendigen Textes. Die Zahlen laufen
        # ABSTEIGEND (2 vor 1), weil Wien den groesseren Messwert hat und
        # dadurch vorne einsortiert wird -- die Positionszahl folgt also dem
        # ORT, nicht der Token-Reihenfolge.
        assert text == "2:+R45 1:+R30", (
            "K-1: vollstaendiger Goldstring der Kurznachricht -- nur die "
            "Werte mit ihrer Ortsnummer, kein Kopf. Heute steht hier "
            f"'Graz, Wien: 2:+R45 1:+R30'. Gemessen: {text!r}"
        )
    finally:
        sms_stub.stop()
        _clean_user(uid)


def test_k1_multi_location_sms_has_no_head_at_all():
    """K-1 isoliert auf der Renderer-Ebene (ROT) — schnelle, netzfreie
    Gegenprobe zur Dienst-Ebene.

    GIVEN eine gebuendelte `AlertMessage` fuer zwei Orte, gebaut ueber genau
    den produktiven Weg `to_multi_point_alert_message()`, und die
    Positions-Zuordnung, die der Ortsvergleich-Aenderungspfad immer mitgibt.
    WHEN sie ueber `render_sms()` gerendert wird.
    THEN besteht der Text ausschliesslich aus den Werte-Token mit ihrer
    Ortsnummer — kein Ortsname, kein Doppelpunkt-Kopf davor.

    ROT-Grund (gemessen): `render_sms()` (`render.py:650-651`) baut im
    Mehr-Orte-Fall `head = f"{_ascii(msg.location_label or msg.trip_short)[:24]}: "`,
    Ergebnis heute `'Graz, Wien: 2:+R45 1:+R30'`.
    """
    from output.renderers.alert.project import to_multi_point_alert_message
    from output.renderers.alert.render import render_sms

    groups = [
        ("Graz", [_change(30.0)], _gpx(47.07, 15.44)),
        ("Wien", [_change(45.0)], _gpx(48.21, 16.37)),
    ]
    msg = to_multi_point_alert_message(
        groups, tz=ZoneInfo("Europe/Vienna"), stand_at="04.08. 08:00",
    )
    text = render_sms(msg, location_positions={"Graz": 1, "Wien": 2})

    assert "Graz" not in text and "Wien" not in text, (
        "K-1: in der Kurznachricht steht kein Ortsname mehr -- die Zahl IST "
        f"die Ortsangabe. Gemessen: {text!r}"
    )
    assert text == "2:+R45 1:+R30", (
        f"K-1: Goldstring der gerenderten Kurznachricht, gemessen {text!r}"
    )


def test_k2_single_location_sms_carries_no_location_name():
    """K-2 (ROT) GIVEN einen Ortsvergleich mit GENAU EINEM Ort ("Graz"), der
    eine Niederschlags-Aenderung 2 -> 30 mm hat, mit eingeschaltetem
    SMS-Versand.

    WHEN `CompareAlertService.check_all_compare_presets()` laeuft.

    THEN kommt an der SMS-Senke genau eine Kurznachricht an, die NUR den Wert
    traegt: `'+R30'`. Kein Ortsname, kein Kopf.

    ROT-Grund (gemessen an Commit 97ec3deb): der Text lautet heute
    `'Graz Graz: +R30'` -- der Ortsname steht sogar ZWEIMAL, weil
    `to_multi_point_alert_message()` (`project.py:217-220`) denselben
    `collective_label` in `trip_short` UND `location_label` schreibt und
    `render_sms()` (`render.py:652-653`) im Ein-Ort-Fall daraus
    `head = f"{trip} {location_label}: "` baut. Von 15 Zeichen der Nachricht
    sind 11 Kopf -- fuer eine Information, die der Empfaenger bereits kennt
    (er hat genau einen Ort im Vergleich).

    Der Ein-Ort-Fall laeuft ueber einen ANDEREN Kopf-Zweig als der
    Mehr-Orte-Fall (`multi_location` ist hier False, weil
    `to_multi_point_alert_message()` das per-Event-`location_label` bei genau
    einer Gruppe bewusst auf None laesst, `project.py:215`). Ein Fix, der nur
    den Mehr-Orte-Zweig anfasst, laesst diesen hier stehen -- deshalb ein
    eigener Test statt einer Variante des K-1-Tests.
    """
    from app.loader import get_data_dir, save_location
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    uid = f"tdd-k2-single-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-k2-single-{uuid.uuid4().hex[:6]}"
    sms_stub = _SMSStub()
    _clean_user(uid)
    try:
        import json

        user_dir = get_data_dir(uid)
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "user.json").write_text(json.dumps({"id": uid, "tier": "standard"}))

        save_location(
            SavedLocation(id="loc-graz", name="Graz", lat=47.07, lon=15.44, elevation_m=353),
            user_id=uid,
        )
        write_compare_briefings(DATA_ROOT / uid, [
            _compare_preset(preset_id, ["loc-graz"], send_sms=True)
        ])
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, "loc-graz", _pwd("loc-graz", "Graz", 47.07, 15.44, 2.0)
        )

        mails: list[tuple[str, str]] = []
        service = CompareAlertService(
            settings=_settings_email_and_sms(sms_stub.port), user_id=uid,
            weather_source=_ScriptedWeatherSource({"loc-graz": 30.0}),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        service.check_all_compare_presets()

        texts = sms_stub.texts()
        assert len(texts) == 1, (
            f"K-2: erwartet GENAU EINE Kurznachricht, erhalten {len(texts)}: "
            f"{texts!r}"
        )
        text = texts[0]
        assert "Graz" not in text, (
            "K-2: der Ortsname darf auch im Ein-Ort-Fall nicht mehr in der "
            f"Kurznachricht stehen, gemessen: {text!r}"
        )
        assert text == "+R30", (
            "K-2: Goldstring der Ein-Ort-Kurznachricht -- nur der Wert. Heute "
            f"steht hier 'Graz Graz: +R30'. Gemessen: {text!r}"
        )
    finally:
        sms_stub.stop()
        _clean_user(uid)


def test_k3_position_numbers_come_from_configured_list_not_from_hit_order():
    """K-3 (Fix-Loop, Mutation M3) — die Positionszahl stammt aus
    `preset["location_ids"]` und NICHT aus der Trefferreihenfolge, nicht aus
    der alphabetischen Ordnung und nicht aus einem Mitzaehler beim Rendern.

    ABGRENZUNG ZU K-4: hier ist Zell NOCH VORHANDEN, er hat diesmal nur nicht
    ausgeloest. Ein vorhandener Ort zaehlt IMMER mit — sonst zeigte dieselbe
    Zahl von Lauf zu Lauf auf einen anderen Ort. Erst ein GELOESCHTER Ort
    laesst die folgenden aufruecken (`test_k4_deleted_location_*`).

    GIVEN ein Ortsvergleich mit DREI konfigurierten Orten in der Reihenfolge
      1. "Bruck"  (Niederschlag 2 -> 30 mm  ⇒ loest aus, Token `+R30`)
      2. "Zell"   (Niederschlag 2 -> 2 mm   ⇒ loest NICHT aus)
      3. "Melk"   (Niederschlag 2 -> 45 mm  ⇒ loest aus, Token `+R45`)

    Die Fixture ist so gebaut, dass sich die vier denkbaren Reihenfolge-
    Quellen ALLE unterscheiden — nur so ist bewiesen, welche davon wirkt:

      | Quelle                          | Bruck | Melk |
      |---------------------------------|-------|------|
      | konfigurierte Liste (SOLL)      |   1   |  3   |
      | Trefferreihenfolge              |   1   |  2   |
      | alphabetisch (Bruck<Melk<Zell)  |   1   |  2   |
      | `reversed(location_ids)`        |   3   |  1   |
      | 0-basiert statt 1-basiert       |   0   |  2   |

    Der Ort auf Position 2 loest bewusst NICHT aus: dadurch KLAFFT eine
    Luecke in den vergebenen Zahlen (1 und 3, keine 2). Genau diese Luecke
    ist der Beweis, dass durchgezaehlt wird, was KONFIGURIERT ist, und nicht,
    was diesmal getroffen hat. Fuer den Empfaenger ist das die eigentliche
    Zusicherung: die Zahl bedeutet dauerhaft denselben Ort, auch wenn von
    Lauf zu Lauf andere Orte ausloesen.

    Melk hat zusaetzlich den GROESSEREN Messwert und steht durch die
    severity-Sortierung (`render.py:25-32`) VORNE — die Zahlen laufen im Text
    also `3:… 1:…`, absteigend und mit Luecke. Eine Positionszahl, die aus
    der Token-Reihenfolge stammt, kann dieses Muster nicht erzeugen.

    WHEN `CompareAlertService.check_all_compare_presets()` laeuft.
    THEN traegt `+R30` die 1, `+R45` die 3 — und es gibt keine 2.
    """
    from app.loader import get_data_dir, save_location
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    uid = f"tdd-ag3b-order-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-ag3b-order-{uuid.uuid4().hex[:6]}"
    sms_stub = _SMSStub()
    _clean_user(uid)
    try:
        import json

        user_dir = get_data_dir(uid)
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "user.json").write_text(json.dumps({"id": uid, "tier": "standard"}))

        # Die Orte werden ABSICHTLICH in einer anderen Reihenfolge angelegt,
        # als sie im Preset stehen: die Anlege-/Ladereihenfolge darf die
        # Positionszahlen nicht beeinflussen.
        save_location(
            SavedLocation(id="loc-melk", name="Melk", lat=48.23, lon=15.33, elevation_m=213),
            user_id=uid,
        )
        save_location(
            SavedLocation(id="loc-bruck", name="Bruck", lat=47.41, lon=15.27, elevation_m=482),
            user_id=uid,
        )
        save_location(
            SavedLocation(id="loc-zell", name="Zell", lat=47.32, lon=12.79, elevation_m=754),
            user_id=uid,
        )
        write_compare_briefings(DATA_ROOT / uid, [
            _compare_preset(
                preset_id, ["loc-bruck", "loc-zell", "loc-melk"], send_sms=True,
            )
        ])
        snapshots = CompareWeatherSnapshotService(user_id=uid)
        snapshots.save(preset_id, "loc-bruck", _pwd("loc-bruck", "Bruck", 47.41, 15.27, 2.0))
        snapshots.save(preset_id, "loc-zell", _pwd("loc-zell", "Zell", 47.32, 12.79, 2.0))
        snapshots.save(preset_id, "loc-melk", _pwd("loc-melk", "Melk", 48.23, 15.33, 2.0))

        mails: list[tuple[str, str]] = []
        service = CompareAlertService(
            settings=_settings_email_and_sms(sms_stub.port), user_id=uid,
            weather_source=_ScriptedWeatherSource({
                "loc-bruck": 30.0,   # Position 1 -> loest aus
                "loc-zell": 2.0,     # Position 2 -> unveraendert, loest NICHT aus
                "loc-melk": 45.0,    # Position 3 -> loest aus
            }),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        service.check_all_compare_presets()

        texts = sms_stub.texts()
        assert len(texts) == 1, (
            "erwartet GENAU EINE gebuendelte Kurznachricht an der SMS-Senke, "
            f"erhalten: {len(texts)} -- {texts!r}"
        )
        text = texts[0]

        # Setup-Kontrolle: genau die beiden ausloesenden Orte sind drin.
        assert "+R30" in text and "+R45" in text, (
            "Setup-Kontrolle: Bruck (+R30) und Melk (+R45) muessen beide "
            f"ausgeloest haben: {text!r}"
        )
        assert "Zell" not in text, (
            "Setup-Kontrolle: Zell hat sich nicht geaendert und darf im "
            f"Alarm gar nicht vorkommen: {text!r}"
        )

        # DIE ZUSICHERUNG: Zahl gehoert zum ORT, aus der konfigurierten Liste.
        assert "1:+R30" in text, (
            "Bruck steht auf Position 1 der konfigurierten Ortsliste "
            "(['loc-bruck', 'loc-zell', 'loc-melk']) und traegt +R30 -- "
            f"erwartet '1:+R30' in {text!r}"
        )
        assert "3:+R45" in text, (
            "Melk steht auf Position 3 der konfigurierten Ortsliste und "
            f"traegt +R45 -- erwartet '3:+R45' in {text!r}. Steht dort "
            "'2:+R45', stammt die Zahl aus der Trefferreihenfolge (Melk ist "
            "der zweite TREFFER) statt aus der Ortsliste -- dann bedeutet "
            "dieselbe Zahl von Lauf zu Lauf einen anderen Ort."
        )
        # Die Luecke: Position 2 hat nicht ausgeloest, also darf keine 2 als
        # Positionszahl auftauchen. (Die Messwerte 30/45 enthalten keine 2.)
        assert "2:" not in text, (
            "Position 2 (Zell) hat nicht ausgeloest -- es darf keine "
            f"Positionszahl 2 vergeben werden: {text!r}"
        )
        assert "0:" not in text, (
            "Die Positionen sind 1-basiert -- eine 0 darf nie auftauchen: "
            f"{text!r}"
        )

        assert len(text) <= 140, (
            f"K-3: <=140 Zeichen, gemessen {len(text)}: {text!r}"
        )

        # Gemessener Goldstring: Zahlen ABSTEIGEND (3 vor 1) UND mit Luecke
        # (keine 2, weil Zell nicht ausgeloest hat). Weder die
        # Trefferreihenfolge noch die Token-Reihenfolge noch die
        # alphabetische Ordnung koennen dieses Muster erzeugen. Der Kopf
        # 'Bruck, Melk: ' faellt mit K-1 weg (heute steht er noch da).
        assert text == "3:+R45 1:+R30", (
            "Vollstaendiger Goldstring der Kurznachricht (ohne Kopf, K-1), "
            f"gemessen {text!r}"
        )
    finally:
        sms_stub.stop()
        _clean_user(uid)


def test_k4_deleted_location_lets_the_following_positions_move_up():
    """K-4 (ROT) — faellt ein Ort weg, RUECKEN DIE FOLGENDEN AUF. Keine
    Luecken, keine Platzhalter.

    PO-Entscheidung 2026-08-04, woertlich: "die nummer soll immer die
    Reihenfolge darstellen. Wenn ein Ort geloescht wird, ruecken die anderen
    nach, das ist kein Fehler sondern fuer den User nachvollziehbares
    Verhalten." Die Zahl ist also der 1-basierte Index in der Liste, die der
    Nutzer HEUTE vor sich sieht — nicht in einer historischen Fassung, von
    der er nichts mehr weiss.

    GIVEN ein Preset mit drei Kennungen
      1. "loc-bruck"     -> Ort "Bruck", loest aus (+R30)
      2. "loc-geloescht" -> KEIN gespeicherter Ort (Nutzer hat ihn geloescht)
      3. "loc-melk"      -> Ort "Melk", loest aus (+R45)

    WHEN der Ortsvergleich laeuft.
    THEN traegt Melk die 2 — die Zahl 3 wird gar nicht mehr vergeben, weil
    der Vergleich nur noch ZWEI Orte hat.

    ROT-Grund (gemessen an Commit 97ec3deb): `_location_positions()`
    (`compare_alert.py:190-207`) zaehlt mit `enumerate(location_ids)` ueber
    die ROHE Kennungsliste und laesst unaufloesbare Kennungen ihren Platz
    behalten — Melk bekommt heute die 3, und im Text klafft eine Luecke, die
    auf einen Ort zeigt, den es nicht mehr gibt. Der Docstring an dieser
    Stelle sichert das sogar ausdruecklich zu; die Zusicherung ist mit dieser
    Korrektur hinfaellig und muss ins Gegenteil.

    ABGRENZUNG ZU K-3: dort steht Zell NOCH in der Ortsliste und hat nur
    diesmal nicht ausgeloest — der behaelt seinen Platz, und Melk bleibt 3.
    Hier ist der mittlere Ort WEG. "nicht getroffen" und "nicht mehr
    vorhanden" sind zwei verschiedene Dinge.
    """
    from app.loader import get_data_dir, save_location
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    uid = f"tdd-k4-gap-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-k4-gap-{uuid.uuid4().hex[:6]}"
    sms_stub = _SMSStub()
    _clean_user(uid)
    try:
        import json

        user_dir = get_data_dir(uid)
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "user.json").write_text(json.dumps({"id": uid, "tier": "standard"}))

        save_location(
            SavedLocation(id="loc-bruck", name="Bruck", lat=47.41, lon=15.27, elevation_m=482),
            user_id=uid,
        )
        save_location(
            SavedLocation(id="loc-melk", name="Melk", lat=48.23, lon=15.33, elevation_m=213),
            user_id=uid,
        )
        # "loc-geloescht" wird BEWUSST NICHT angelegt.
        write_compare_briefings(DATA_ROOT / uid, [
            _compare_preset(
                preset_id, ["loc-bruck", "loc-geloescht", "loc-melk"], send_sms=True,
            )
        ])
        snapshots = CompareWeatherSnapshotService(user_id=uid)
        snapshots.save(preset_id, "loc-bruck", _pwd("loc-bruck", "Bruck", 47.41, 15.27, 2.0))
        snapshots.save(preset_id, "loc-melk", _pwd("loc-melk", "Melk", 48.23, 15.33, 2.0))

        mails: list[tuple[str, str]] = []
        service = CompareAlertService(
            settings=_settings_email_and_sms(sms_stub.port), user_id=uid,
            weather_source=_ScriptedWeatherSource({
                "loc-bruck": 30.0, "loc-melk": 45.0,
            }),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        service.check_all_compare_presets()

        texts = sms_stub.texts()
        assert len(texts) == 1, (
            f"erwartet GENAU EINE Kurznachricht, erhalten {len(texts)}: {texts!r}"
        )
        text = texts[0]

        assert "2:+R45" in text, (
            "K-4: der Vergleich hat nach der Loeschung nur noch zwei Orte -- "
            "Melk ist der zweite davon und traegt +R45. Erwartet '2:+R45' in "
            f"{text!r}. Steht dort '3:+R45', zaehlt die geloeschte Kennung "
            "noch mit und der Empfaenger sucht in seiner Ortsliste nach einer "
            "3, die es nicht gibt."
        )
        assert "3:" not in text, (
            "K-4: keine Luecke, kein Platzhalter -- die Zahl 3 darf gar nicht "
            f"mehr vergeben werden, gemessen: {text!r}"
        )
        assert "1:+R30" in text, (
            f"K-4: Bruck bleibt auf Position 1: {text!r}"
        )
        # Goldstring: identisch zu einem Vergleich, der von Anfang an nur
        # Bruck und Melk enthalten haette -- genau das ist die Zusicherung.
        assert text == "2:+R45 1:+R30", (
            "K-4: Goldstring nach dem Aufruecken. Heute steht hier "
            f"'Bruck, Melk: 3:+R45 1:+R30'. Gemessen: {text!r}"
        )
    finally:
        sms_stub.stop()
        _clean_user(uid)


def test_k3_sms_token_binds_position_to_location_name_not_to_token_order():
    """K-3 (Fix-Loop) auf der Renderer-Ebene: `render_sms()` bindet die
    Positionszahl an den ORTSNAMEN des Ereignisses (`location_label`), nicht
    an die Reihenfolge, in der die Token im Text stehen.

    Schnelle, netzfreie Gegenprobe zur Dienst-Ebene: die Gruppen werden in
    der Reihenfolge (Melk, Bruck) uebergeben, die Positions-Zuordnung sagt
    aber Bruck=1, Melk=3. Wuerde `_sms_token()` (`render.py:585-601`) statt
    des Namens einen Laufindex verwenden, kaeme `1:` an Melk und `2:` an
    Bruck heraus.

    Zusaetzlich abgedeckt: ein Ort, der ausloest, aber in der Zuordnung FEHLT
    (er stand nicht in `preset["location_ids"]`, oder seine Kennung war nicht
    aufloesbar). Er bekommt KEINE erfundene Zahl, sondern bleibt unnummeriert
    -- eine falsche Zahl waere schlimmer als gar keine, weil sie auf einen
    anderen Ort zeigt.
    """
    from output.renderers.alert.project import to_multi_point_alert_message
    from output.renderers.alert.render import render_sms

    groups = [
        ("Melk", [_change(45.0)], _gpx(48.23, 15.33)),
        ("Bruck", [_change(30.0)], _gpx(47.41, 15.27)),
    ]
    msg = to_multi_point_alert_message(
        groups, tz=ZoneInfo("Europe/Vienna"), stand_at="04.08. 08:00",
    )

    text = render_sms(msg, location_positions={"Bruck": 1, "Melk": 3})
    assert "3:+R45" in text, (
        "Melk traegt Position 3 der konfigurierten Ortsliste und den Messwert "
        f"+R45 -- erwartet '3:+R45' in {text!r}. Steht dort '1:+R45', ist die "
        "Zahl an die Token-Reihenfolge gebunden statt an den Ortsnamen."
    )
    assert "1:+R30" in text, (
        f"Bruck traegt Position 1 und +R30 -- erwartet '1:+R30' in {text!r}"
    )
    assert "2:" not in text, (
        f"Position 2 ist nicht vergeben -- keine 2 im Text: {text!r}"
    )
    assert text == "3:+R45 1:+R30", (
        "K-1 auf der Renderer-Ebene: der Text besteht ausschliesslich aus den "
        f"Werte-Token mit ihrer Ortsnummer, gemessen {text!r}"
    )

    # Ort ohne Eintrag in der Zuordnung: unnummeriert, aber nicht falsch
    # nummeriert.
    partial = render_sms(msg, location_positions={"Bruck": 1})
    assert "1:+R30" in partial, (
        f"Bruck bleibt korrekt nummeriert: {partial!r}"
    )
    assert "+R45" in partial and "3:+R45" not in partial, (
        "Melk fehlt in der Zuordnung -- sein Token muss OHNE Positionszahl "
        f"stehen, nicht mit einer erfundenen: {partial!r}"
    )
    # Genau EIN Token traegt eine Positionszahl (das von Bruck).
    nummerierte = re.findall(r"(?:^| )(\d+):", partial)
    assert nummerierte == ["1"], (
        "ausser dem korrekt nummerierten Bruck-Token darf kein weiteres "
        f"Token eine Positionszahl tragen, gefunden: {nummerierte!r} in "
        f"{partial!r}"
    )


# ═════════════════ Regressions-Zusicherung (GRUEN vor UND nach) ══════════════
# Die drei anderen Alarmwege duerfen sich durch AG3b um KEIN Zeichen aendern:
# ohne Orts-Positionszuordnung bleibt der SMS-Text byte-identisch. Vorbild:
# AC-26 in `test_compare_alert_telegram_per_location.py`. Die Vergleichswerte
# sind an HEAD 6b6ad80d GEMESSEN (lokaler seven.io-Stub), nicht geschaetzt.

def test_regression_trip_deviation_alert_sms_text_unchanged():
    """Trip-Aenderungsalarm (`send_deviation_alert`) — SMS byte-identisch."""
    stub = _SMSStub()
    try:
        svc = NotificationService(
            settings=_settings_sms_only(stub.port), user_id="tdd-ag3b-reg-trip",
        )
        svc.send_deviation_alert(
            trip=_trip(), weather=[_segment_weather_data()], changes=[_change()],
            effective_channels={"sms"},
        )
        # Issue #1935/#1779 (E3/E4): Kopf spricht seither die Segment-Sprache
        # statt einer km-Spanne (kein Trip-Name mehr), Token traegt Von- UND
        # Bis-Wert (`_trip_segment().segment_id=1` -> "Segment 1").
        # Issue #1948 S3: das Vorzeichen-Praefix ist im Trip-Δ-Pfad entfallen
        # und `>` durch `->` ersetzt -- der Compare-Pfad (unten) behaelt beides,
        # deshalb aendert sich hier genau ein Goldstring und keiner der anderen.
        assert stub.texts() == ["Segment 1: R2->30"], (
            "Regression: der SMS-Text des Trip-Aenderungsalarms muss ohne "
            "Orts-Positionszuordnung unveraendert bleiben, gemessen: "
            f"{stub.texts()!r}"
        )
    finally:
        stub.stop()


def test_regression_trip_radar_alert_sms_text_unchanged():
    """Trip-Radar-Alarm (`send_radar_alert`) — SMS byte-identisch."""
    stub = _SMSStub()
    try:
        svc = NotificationService(
            settings=_settings_sms_only(stub.port), user_id="tdd-ag3b-reg-radar",
        )
        req = RadarAlertRequest(
            onset_minutes=12, onset_time="14:35", km_from=5.0, km_to=18.0,
            is_convective=False, intensity_label="leichter Regen",
            source_label="Radar (DWD)", tz=ZoneInfo("Europe/Zurich"),
        )
        svc.send_radar_alert(
            trip=_trip(), request=req, source="Radar (DWD)",
            cooldown_display="2 Stunden", effective_channels={"sms"},
        )
        # Issue #1935/#1779 (E4): Trip-Radar/Onset-Kopf verliert den Trip-Namen,
        # km-Spanne bleibt (kein Segment-Bezug im Radar-Request dieser Fixture).
        assert stub.texts() == ["km5-18: R!12"], (
            "Regression: der SMS-Text des Trip-Radar-Alarms muss unveraendert "
            f"bleiben, gemessen: {stub.texts()!r}"
        )
    finally:
        stub.stop()


def test_regression_compare_radar_alert_sms_text_unchanged():
    """Ortsvergleich-Radar-Alarm (`send_multi_location_radar_alert`) — SMS
    byte-identisch, obwohl MEHRERE Orte beteiligt sind. Die Positions-
    Kodierung aus AG3b gilt ausdruecklich nur fuer den Aenderungs-Pfad
    (Spec "Known Limitations": Radar-Onset bleibt S3-Scope)."""
    stub = _SMSStub()
    try:
        svc = NotificationService(
            settings=_settings_sms_only(stub.port), user_id="tdd-ag3b-reg-cmp-radar",
        )
        loc_a = SavedLocation(id="loc-a", name="Zermatt", lat=46.02, lon=7.75, elevation_m=1600)
        loc_b = SavedLocation(id="loc-b", name="Chamonix", lat=45.92, lon=6.87, elevation_m=1000)
        nc_a = NowcastResult(
            onset_minutes=8, intensity_label="leichter Regen", source="radar",
            is_convective=False,
        )
        nc_b = NowcastResult(
            onset_minutes=15, intensity_label="maessiger Regen", source="radar",
            is_convective=False,
        )
        svc.send_multi_location_radar_alert(
            [("Zermatt", loc_a, nc_a), ("Chamonix", loc_b, nc_b)], {"sms"},
        )
        assert stub.texts() == ["Zermatt, Chamoni km0-0: R!8"], (
            "Regression: der SMS-Text des Ortsvergleich-Radar-Alarms muss "
            f"unveraendert bleiben, gemessen: {stub.texts()!r}"
        )
    finally:
        stub.stop()
