"""TDD RED — Issue #3128: gemeinsamer Berichtsaufbau des Trip-Briefings.

SPEC: docs/specs/modules/trip_briefing_aufbau.md (AC-1 bis AC-8; AC-9 ist Staging)

Versand (``TripReportSchedulerService._briefing_bauen_und_senden``) und
Vorschau (``PreviewService._build_report``) setzen den Bericht heute an zwei
Stellen zusammen. Kuenftig baut ihn EIN Baustein ``services.trip_briefing_aufbau``
(Muster: ``services.compare_briefing_aufbau``, #2983).

Vertrag, den diese Tests an den Baustein stellen (nur soweit die Spec ihn nennt):

* ``trip_segmente_bauen(scheduler, trip, target, persist)`` -> Liste der Segmente
  (``persist=False`` = Vorschau, kein Backfill-Schreiben, #2036)
* ``trip_wetter_laden(...)``, ``trip_anreicherung_bauen(..., trend_parallel=False)``,
  ``trip_briefing_bauen(...)`` -- existieren als Modul-Attribute; ihre
  Detailparameter legt der Developer fest (hier nicht direkt aufgerufen)
* ``trip_report_rendern(..., has_gap, lang, undelivered, vortag, starkregen)``
  -> der gerenderte ``TripReport`` (der EINE Render-Weg ueber
  ``TripReportFormatter``). Versand und Vorschau rufen ihn ZUR LAUFZEIT ueber
  das Modul auf (``aufbau.trip_report_rendern(...)`` bzw. funktionslokaler
  Import), sonst ist AC-4 am Wirkort nicht beobachtbar.

Golden-Tests (AC-1, AC-2, AC-8): die Soll-Werte unter
``tests/golden/trip_briefing_aufbau/`` wurden mit dem Code VOR dem Umbau
erzeugt (``GZ_GOLDEN_ERZEUGEN=3128 uv run pytest <diese Datei>``, einmalig in
Phase 5). Sie sind vor UND nach dem Umbau gruen (Characterization).

KEINE Mocks (kein Mock()/patch()/MagicMock). Naehte:
* Uhr: ``freezegun`` auf ``JETZT`` (Golden byte-stabil, Etappen relativ zum Tag).
* Wetter: der offline ``FixtureProvider`` (``GZ_TEST_FIXTURE_DIR``, conftest),
  ein leeres Fixture-Verzeichnis = echter Totalausfall.
* Transport: ``tests/helpers/transport_mitschrift.py`` (vier Ausgangsklassen).
* Beobachtung: aufzeichnende Huellen um echte Methoden
  (``SegmentWeatherService.fetch_segment_weather``,
  ``segment_weather.fetch_night_weather``, ``TripReportFormatter.format_email``),
  die das Original unveraendert aufrufen. Amtliche Warnungen haben keine
  Fixture-Naht: ``official_alerts.get_official_alerts_with_status`` wird durch
  einen zaehlenden Ersatz ohne Netz ersetzt (nur AC-8).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pytest
from freezegun import freeze_time

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "tests" / "golden" / "trip_briefing_aufbau"
FIXTURES = REPO_ROOT / "fixtures" / "openmeteo"

#: Feste Uhr (Donnerstag, Innsbruck 05:00 MEZ). Die Fixture-Wetterreihe
#: beginnt an 00:00 UTC dieses Tages und deckt drei Tage ab.
JETZT = datetime(2026, 10, 29, 4, 0, tzinfo=timezone.utc)
TAG = JETZT.date()
INNSBRUCK = (47.2692, 11.4041)
STUBAI = (47.1015, 11.2958)

NUTZER_A = "aufbau3128-nutzer-a"
NUTZER_B = "aufbau3128-nutzer-b"
TRIP_A = "aufbau3128-trip-a"
TRIP_B = "aufbau3128-trip-b"
TRIP_A_KURZ = "aufbau3128-trip-a-kurz"
TRIP_A_OHNE_NACHT = "aufbau3128-trip-a-ohne-nacht"
TRIP_A_LUECKE = "aufbau3128-trip-a-luecke"
TRIP_A_GEWITTER = "aufbau3128-trip-a-gewitter"
TRIP_NAME_A = "Hoehenweg Nord"
TRIP_NAME_B = "Westweg Sued"
ETAPPE_A = "Kamm"
ETAPPE_B = "Tobel"

_TRANSPORT_ENV = {
    "GZ_ENV": "development",
    "GZ_SMTP_HOST": "smtp.invalid",
    "GZ_SMTP_USER": "unbrauchbar",
    "GZ_SMTP_PASS": "unbrauchbar",
    "GZ_MAIL_FROM": "gregor@example.invalid",
    "GZ_MAIL_TO": "globaler-rueckfall@example.invalid",
    "GZ_TEST_SMTP_HOST": "smtp.invalid",
    "GZ_TEST_SMTP_USER": "",
    "GZ_TEST_SMTP_PASS": "",
    "GZ_TELEGRAM_BOT_TOKEN": "0000000:unbrauchbar",
    "GZ_TELEGRAM_CHAT_ID": "globaler-rueckfall-chat",
    "GZ_TELEGRAM_TEST_BOT_TOKEN": "",
    "GZ_TELEGRAM_TEST_CHAT_ID": "",
    "GZ_SMS_GATEWAY_URL": "https://gateway.invalid/api/sms",
    "GZ_SEVEN_API_KEY": "unbrauchbar",
    "GZ_SEVEN_SANDBOX_KEY": "",
    "GZ_SMS_TO": "+490000000000",
    # Nutzer-Link im Bericht: fest, damit das Golden nicht an der .env haengt.
    "GZ_PUBLIC_HOST": "https://gregor20.henemm.com",
}


# ---------------------------------------------------------------------------
# Umgebung
# ---------------------------------------------------------------------------


class _Beobachtung:
    """Was die aufzeichnenden Huellen gesehen haben (kein Mock)."""

    def __init__(self) -> None:
        self.wetter_nutzer: list = []
        self.nacht_nutzer: list = []
        self.format_email: list[dict] = []
        self.warnungen = 0

    def leeren(self) -> None:
        self.__init__()


def _nutzer_anlegen(uid: str) -> None:
    """Echtes ``user.json``: Premium, alle vier Kanaele mit belegten Empfaengern."""
    import hashlib

    from app.loader import get_data_dir

    ordner = get_data_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({
        "id": uid, "tier": "premium",
        "mail_to": f"{uid}@example.invalid",
        "telegram_chat_id": f"chat-{uid}",
        "sms_to": "+490000000001",
        "sms_verified_number": "+490000000001",
        "sms_verified_at": "2026-01-01T00:00:00Z",
        # ADR-0116: Rueckadresse je Nutzer eindeutig.
        "premium_sms_reply_to": "+4900" + str(
            int(hashlib.sha256(uid.encode()).hexdigest(), 16) % 10**8).zfill(8),
        "premium_sms_reply_at": (JETZT - timedelta(minutes=5)).isoformat(),
    }))


def _trip_anlegen(uid: str, trip_id: str, name: str, etappe: str, *,
                  telegram_style: str = "rich", display_config=None,
                  official_alerts: bool = False, nur_ein_wegpunkt_am=None,
                  gewitter_metrik: bool = False):
    """Vier Etappen (gestern bis uebermorgen) mit je drei Wegpunkten
    (Innsbruck -> Stubai -> Innsbruck, zwei Segmente) und festen Gehzeiten."""
    from app.loader import save_trip
    from app.models import TripReportConfig
    from app.trip import Stage, TimeWindow, Trip, Waypoint

    etappen = []
    for i in range(4):
        tag = TAG + timedelta(days=i - 1)
        coords = [INNSBRUCK, STUBAI, (INNSBRUCK[0] + 0.02, INNSBRUCK[1] + 0.02)]
        if nur_ein_wegpunkt_am == tag:
            coords = coords[:1]
        wps = [
            Waypoint(id=f"G{i}{j}", name=f"{etappe}-{j}", lat=lat, lon=lon,
                     elevation_m=600 + 300 * j,
                     time_window=TimeWindow(start=time(8 + 3 * j, 0), end=time(8 + 3 * j, 0)))
            for j, (lat, lon) in enumerate(coords)
        ]
        etappen.append(Stage(id=f"T{i}", name=f"{etappe} {i}", date=tag,
                             start_time=time(8, 0), waypoints=wps))
    trip = Trip(
        id=trip_id, name=name, stages=etappen,
        official_alerts_enabled=official_alerts,
        report_config=TripReportConfig(
            trip_id=trip_id, send_email=True, send_sms=True,
            send_premium_sms=True, send_telegram=True,
            telegram_style=telegram_style,
        ),
    )
    if display_config is not None:
        trip.display_config = display_config
    save_trip(trip, user_id=uid)
    if gewitter_metrik:
        # Standard-Anzeige des Loaders plus Gewitter-Metrik (SMS-Token TH,
        # Gewitter-Vorschau, Nacht-Zusatz), Read-Modify-Write.
        geladen = _trip(uid, trip_id)
        for mc in geladen.display_config.metrics:
            if mc.metric_id == "thunder":
                mc.enabled = True
        save_trip(geladen, user_id=uid)
        trip = geladen
    return trip


def _ohne_nacht_display_config(trip_id: str):
    """Anzeige ohne Nacht-Tabelle, ohne Nacht-Temperatur und ohne Gewitter:
    ``night_weather_needed`` ist False (Nachtwetter-Gate der Vorschau, AC-8)."""
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig

    return UnifiedWeatherDisplayConfig(
        trip_id=trip_id, show_night_block=False,
        metrics=[MetricConfig(metric_id=m, enabled=True)
                 for m in ("temperature", "wind", "gust", "precipitation")]
        # ausdruecklich aus: der Loader ergaenzt fehlende Nacht-Kennungen als "an"
        + [MetricConfig(metric_id=m, enabled=False)
           for m in ("temperature_night", "wind_chill_night", "thunder")],
    )


@pytest.fixture
def env(monkeypatch):
    """Feste Uhr, Transport-Mitschrift, zwei Nutzer mit je eigenem Trip,
    aufzeichnende Huellen um Wetterabruf, Nachtwetter und Formatter."""
    from app.config import Settings
    from tests.helpers.transport_mitschrift import aufzeichner_installieren

    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for k, v in _TRANSPORT_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(FIXTURES))

    uhr = freeze_time(JETZT)
    uhr.start()
    try:
        mitschrift = aufzeichner_installieren(monkeypatch)
        beob = _Beobachtung()
        _huellen_installieren(monkeypatch, beob)
        for uid in (NUTZER_A, NUTZER_B):
            _nutzer_anlegen(uid)
        _trip_anlegen(NUTZER_A, TRIP_A, TRIP_NAME_A, ETAPPE_A)
        _trip_anlegen(NUTZER_A, TRIP_A_KURZ, TRIP_NAME_A, ETAPPE_A, telegram_style="kurzform")
        _trip_anlegen(NUTZER_A, TRIP_A_GEWITTER, TRIP_NAME_A, ETAPPE_A, gewitter_metrik=True)
        _trip_anlegen(NUTZER_B, TRIP_B, TRIP_NAME_B, ETAPPE_B)
        from app.loader import get_data_root

        yield {"mitschrift": mitschrift, "beob": beob, "data_root": get_data_root()}
    finally:
        uhr.stop()


def _huellen_installieren(monkeypatch, beob: _Beobachtung) -> None:
    import services.segment_weather as sw_mod
    from output.renderers.trip_report import TripReportFormatter

    orig_fetch = sw_mod.SegmentWeatherService.fetch_segment_weather

    def _fetch(self, segment, *args, **kwargs):
        beob.wetter_nutzer.append(kwargs.get("user_id"))
        return orig_fetch(self, segment, *args, **kwargs)

    monkeypatch.setattr(sw_mod.SegmentWeatherService, "fetch_segment_weather", _fetch)

    orig_nacht = sw_mod.fetch_night_weather

    def _nacht(*args, **kwargs):
        beob.nacht_nutzer.append(kwargs.get("user_id"))
        return orig_nacht(*args, **kwargs)

    monkeypatch.setattr(sw_mod, "fetch_night_weather", _nacht)

    orig_format = TripReportFormatter.format_email

    def _format(self, *args, **kwargs):
        beob.format_email.append(dict(kwargs))
        return orig_format(self, *args, **kwargs)

    monkeypatch.setattr(TripReportFormatter, "format_email", _format)


def _trip(uid: str, trip_id: str):
    from app.loader import load_all_trips

    treffer = [t for t in load_all_trips(uid) if t.id == trip_id]
    assert len(treffer) == 1, f"Vorbedingung: Trip {trip_id!r} fuer {uid!r} nicht ladbar"
    return treffer[0]


TELEGRAM_TRENNER = "\n\n<<<BUBBLE>>>\n\n"


def _versand(env, uid: str, trip_id: str, report_type: str) -> dict:
    """Echter Scheduler-Versand (``_send_trip_report_outcome``, regulaerer Slot)
    bis zu den Transport-Sinks; liefert die zugestellten Inhalte je Kanal."""
    from services.trip_report_scheduler import TripReportSchedulerService

    mit = env["mitschrift"]
    mit.leeren()
    svc = TripReportSchedulerService(user_id=uid)
    ausgang = svc._send_trip_report_outcome(_trip(uid, trip_id), report_type)
    assert ausgang == "sent", f"Vorbedingung: Versand muss gelingen, war {ausgang!r}"
    assert mit.kanaele == ["email", "sms", "premium_sms", "telegram"], (
        f"Vorbedingung: alle vier Kanaele bedient: {mit.kanaele}"
    )
    mail = mit.sendungen("email")
    assert len(mail) == 1, f"genau eine Mail erwartet: {len(mail)}"
    return {
        "subject": mail[0]["subject"],
        "email_html": mail[0]["body"],
        "email_text": mail[0]["plain_text_body"] or "",
        "sms": "\n".join(s["body"] for s in mit.sendungen("sms")),
        "premium_sms": "\n".join(s["body"] for s in mit.sendungen("premium_sms")),
        "telegram": TELEGRAM_TRENNER.join(s["body"] for s in mit.sendungen("telegram")),
    }


def _vorschau_bericht(uid: str, trip_id: str, report_type: str, target=TAG):
    """``PreviewService._build_report`` wie ``render_sms_preview`` es aufruft
    (Fassade, Rueckgabe-Tupel ist Vertrag)."""
    from services.preview_service import PreviewService

    svc = PreviewService()
    trip = svc._load_trip(trip_id, uid)
    return svc._build_report(trip, target, report_type, now_utc=datetime.now(timezone.utc),
                             user_id=uid)


def _vorschau_sms(uid: str, trip_id: str, report_type: str) -> tuple[str, str]:
    from services.preview_service import PreviewService

    return PreviewService().render_sms_preview(
        trip_id, user_id=uid, report_type=report_type, target_date=TAG.isoformat(),
    )


def _tupel_inhalt(tupel) -> dict:
    report, segment_weather, stage_name, trip_tz = tupel
    return {
        "subject": report.email_subject,
        "email_html": report.email_html,
        "email_text": report.email_plain,
        "sms": report.sms_text or "",
        "telegram": TELEGRAM_TRENNER.join(report.telegram_bubbles or []),
        "tupel": json.dumps({
            "stage_name": stage_name, "trip_tz": str(trip_tz),
            "segmente": len(segment_weather),
            "segmente_mit_fehler": sum(1 for s in segment_weather if s.has_error),
        }, ensure_ascii=False, sort_keys=True),
    }


# ---------------------------------------------------------------------------
# Golden-Werte (einmalig mit dem Code VOR dem Umbau erzeugt)
# ---------------------------------------------------------------------------


def _golden_pfad(fall: str, kanal: str) -> Path:
    endung = {"email_html": "html", "tupel": "json"}.get(kanal, "txt")
    return GOLDEN_DIR / f"{fall}.{kanal}.{endung}"


def _golden_pruefen(fall: str, ist: dict, ac: str) -> None:
    if os.environ.get("GZ_GOLDEN_ERZEUGEN") == "3128":  # pragma: no cover - nur Phase 5
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        for kanal, wert in ist.items():
            _golden_pfad(fall, kanal).write_text(wert, encoding="utf-8")
    for kanal, wert in ist.items():
        pfad = _golden_pfad(fall, kanal)
        assert pfad.is_file(), f"{ac}: Golden-Datei fehlt: {pfad}"
        soll = pfad.read_text(encoding="utf-8")
        assert wert.encode("utf-8") == soll.encode("utf-8"), (
            f"{ac}: {fall}/{kanal} weicht vom Stand vor dem Umbau ab ({pfad.name})"
        )


# ---------------------------------------------------------------------------
# AC-1: Versand byte-gleich
# ---------------------------------------------------------------------------


def _gewitter_fixtures(ziel: Path) -> Path:
    """Aufgezeichnete Reihen mit Sturm, Regen und mittlerem Gewitter 10-15 UTC
    sowie starkem Gewitter um 02 UTC jedes Tages (Gewitter-Vorschau, Nacht-
    Zusatz, Warnfarben). Muster ``scheduler_sprache_fixture._sturm_fixture``."""
    ziel.mkdir(parents=True, exist_ok=True)
    for name in ("innsbruck.json", "stubai.json", "zillertal.json"):
        daten = json.loads((FIXTURES / name).read_text())
        for i, p in enumerate(daten["data"]):
            stunde = i % 24
            if 10 <= stunde <= 15:
                p.update(wind10m_kmh=50, gust_kmh=75, precip_1h_mm=1.5 + stunde / 10,
                         thunder_level="MED", cape_jkg=900)
            elif stunde == 2:
                p.update(thunder_level="HIGH", precip_1h_mm=4.0)
            else:
                p["thunder_level"] = "NONE"
        (ziel / name).write_text(json.dumps(daten))
    return ziel


@pytest.mark.parametrize("report_type,trip_id,stil,wetter", [
    ("morning", TRIP_A, "langform", "ruhig"),
    ("evening", TRIP_A, "langform", "ruhig"),
    ("morning", TRIP_A_KURZ, "kurzform", "ruhig"),
    ("evening", TRIP_A_KURZ, "kurzform", "ruhig"),
    ("morning", TRIP_A_GEWITTER, "langform", "gewitter"),
    ("evening", TRIP_A_GEWITTER, "langform", "gewitter"),
])
def test_ac1_versand_bleibt_byte_gleich(env, monkeypatch, tmp_path, report_type, trip_id,
                                        stil, wetter):
    """AC-1: Given ein Trip mit festen Etappen und gleichen (Fixture-)Wetterdaten /
    When der regulaere Versand ueber den echten Scheduler-Pfad laeuft / Then
    sind Mail (Betreff, HTML, Text), SMS (<=160), Premium-SMS und Telegram
    (Lang- bzw. Kurzform) byte-gleich zum vor dem Umbau erfassten Stand.

    Characterization: VOR dem Umbau gruen, nach dem Umbau unveraendert gruen.
    Morgen = Gewitter-Vorschau ueber Einzelabruf (kein Ausblick), Abend =
    Ausblick + Gewitter aus den Ausblick-Zeilen. ``gewitter``: Sturm/Regen/
    Gewitter tagsueber und starkes Nachtgewitter (Nacht-Zusatz, Warnungen)."""
    if wetter == "gewitter":
        from services.weather_cache import reset_shared_weather_cache_for_tests

        monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(_gewitter_fixtures(tmp_path / "fx")))
        reset_shared_weather_cache_for_tests()
    ist = _versand(env, NUTZER_A, trip_id, report_type)
    assert 0 < len(ist["sms"]) <= 160, f"SMS-Laenge {len(ist['sms'])}: {ist['sms']!r}"
    if stil == "kurzform":
        assert ist["telegram"] == ist["sms"], "Vorbedingung: Telegram-Kurzform = SMS-Text"
        # Die Mail haengt nicht am Telegram-Stil; sie ist im Langform-Fall
        # festgehalten (gleiche Etappen/Wetter) -- hier nur die Kurzkanaele.
        ist = {k: ist[k] for k in ("subject", "sms", "premium_sms", "telegram")}
    else:
        assert ist["telegram"] != ist["sms"], "Vorbedingung: Telegram-Langform"
    fall = f"versand_{report_type}_{stil}" + ("_gewitter" if wetter == "gewitter" else "")
    _golden_pruefen(fall, ist, "AC-1")


# ---------------------------------------------------------------------------
# AC-2: Vorschau unveraendert
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("report_type", ["morning", "evening"])
def test_ac2_vorschau_tupel_und_sms_bleiben_gleich(env, report_type):
    """AC-2: Given derselbe Trip / When ``_build_report`` und
    ``render_sms_preview`` laufen / Then sind Rueckgabe-Tupel
    ``(report, segment_weather, stage_name, trip_tz)`` (Berichtsinhalte,
    Etappenname, Zeitzone, Segmentzahl) und SMS-Vorschau byte-gleich zum Stand
    vor dem Umbau. Trend laeuft dabei nebenlaeufig (#1839), ohne Backfill (#2036).

    Characterization: VOR dem Umbau gruen, nach dem Umbau unveraendert gruen."""
    tupel = _vorschau_bericht(NUTZER_A, TRIP_A, report_type)
    ist = _tupel_inhalt(tupel)
    betreff, sms = _vorschau_sms(NUTZER_A, TRIP_A, report_type)
    assert (betreff, sms) == (ist["subject"], ist["sms"]), (
        "AC-2: render_sms_preview liefert nicht den Bericht aus _build_report"
    )
    _golden_pruefen(f"vorschau_{report_type}", ist, "AC-2")


def test_ac2_vorschau_fehlercodes_bleiben(env):
    """AC-2: Given ein Zieltag ohne Etappe bzw. eine Etappe mit nur einem
    Wegpunkt / When ``_build_report`` laeuft / Then wirft die Vorschau wie
    bisher ``LookupError`` mit Code ``vorschau_etappe_fehlt`` bzw.
    ``vorschau_zu_wenige_wegpunkte`` (das Frontend leitet daraus ab)."""
    with pytest.raises(LookupError) as fehlt:
        _vorschau_bericht(NUTZER_A, TRIP_A, "morning", target=TAG + timedelta(days=9))
    assert getattr(fehlt.value, "code", None) == "vorschau_etappe_fehlt", fehlt.value

    _trip_anlegen(NUTZER_A, TRIP_A_LUECKE, TRIP_NAME_A, ETAPPE_A,
                  nur_ein_wegpunkt_am=TAG + timedelta(days=1))
    with pytest.raises(LookupError) as wenige:
        _vorschau_bericht(NUTZER_A, TRIP_A_LUECKE, "morning", target=TAG + timedelta(days=1))
    assert getattr(wenige.value, "code", None) == "vorschau_zu_wenige_wegpunkte", wenige.value


# ---------------------------------------------------------------------------
# AC-3: Mandantentrennung
# ---------------------------------------------------------------------------


def test_ac3_vorschau_und_versand_nur_mit_daten_des_nutzers(env):
    """AC-3: Given zwei Nutzer mit je eigenem Trip / When Vorschau und Versand
    fuer Nutzer A laufen / Then enthalten Berichte nur A-Daten (Trip- und
    Etappennamen), jeder Wetter- und Nachtabruf laeuft mit A als Nutzer (nie
    ``"default"``, nie ``None``), und B's Trip ist fuer A nicht ladbar."""
    beob = env["beob"]
    vorschau = _tupel_inhalt(_vorschau_bericht(NUTZER_A, TRIP_A, "evening"))
    versand = _versand(env, NUTZER_A, TRIP_A, "evening")

    for quelle, payload in (("Vorschau", vorschau), ("Versand", versand)):
        alles = "\n".join(payload.values())
        assert TRIP_NAME_A in alles and ETAPPE_A in alles, f"{quelle}: Daten von A fehlen"
        for fremd in (TRIP_NAME_B, ETAPPE_B, NUTZER_B, TRIP_B):
            assert fremd not in alles, f"AC-3: {quelle} fuer A zeigt {fremd!r} von Nutzer B"
    assert beob.wetter_nutzer, "Vorbedingung: Wetterabruf beobachtet"
    assert set(beob.wetter_nutzer) == {NUTZER_A}, (
        f"AC-3: Wetterabruf lief mit {set(beob.wetter_nutzer)!r}, erwartet nur A"
    )
    assert beob.nacht_nutzer and set(beob.nacht_nutzer) == {NUTZER_A}, (
        f"AC-3: Nachtabruf lief mit {beob.nacht_nutzer!r}, erwartet nur A"
    )
    empfaenger = {e for k in env["mitschrift"].kanaele for e in env["mitschrift"].empfaenger(k)}
    assert not any(NUTZER_B in str(e) for e in empfaenger), f"AC-3: Empfaenger von B: {empfaenger}"

    from services.preview_service import PreviewService

    with pytest.raises(FileNotFoundError):
        PreviewService()._load_trip(TRIP_B, NUTZER_A)

    # Gegenrichtung: derselbe Prozess bedient danach B mit B's Daten und Konto.
    beob.leeren()
    versand_b = _versand(env, NUTZER_B, TRIP_B, "evening")
    assert TRIP_NAME_B in versand_b["subject"] and TRIP_NAME_A not in versand_b["email_html"]
    assert set(beob.wetter_nutzer) == {NUTZER_B}, f"AC-3: B-Versand rief mit {beob.wetter_nutzer!r}"


# ---------------------------------------------------------------------------
# AC-4: genau eine Aufbau-Stelle, beide Seiten nutzen sie
# ---------------------------------------------------------------------------

_MARKE = "<3128>"


def test_ac4_aenderung_am_baustein_wirkt_in_vorschau_und_versand(env, monkeypatch):
    """AC-4: Given eine Test-Ersatzfassung von ``trip_report_rendern`` (ruft die
    echte Funktion und haengt eine Marke an Mail-HTML und SMS) / When Vorschau
    und Versand laufen / Then traegt die Mail beider Seiten und die SMS beider
    Seiten die Marke -- es gibt keine zweite, eigene Kopie des Render-Aufrufs.

    RED: services.trip_briefing_aufbau existiert noch nicht."""
    import services.trip_briefing_aufbau as aufbau

    original = aufbau.trip_report_rendern

    def _markiert(*a, **k):
        report = original(*a, **k)
        report.email_html = (report.email_html or "") + _MARKE
        report.sms_text = (report.sms_text or "") + _MARKE
        return report

    monkeypatch.setattr(aufbau, "trip_report_rendern", _markiert)

    report, *_ = _vorschau_bericht(NUTZER_A, TRIP_A, "morning")
    _betreff, vorschau_sms = _vorschau_sms(NUTZER_A, TRIP_A, "morning")
    versand = _versand(env, NUTZER_A, TRIP_A, "morning")

    assert _MARKE in report.email_html, "AC-4: Vorschau-Mail laeuft nicht durch den Baustein"
    assert vorschau_sms.endswith(_MARKE), "AC-4: Vorschau-SMS laeuft nicht durch den Baustein"
    assert _MARKE in versand["email_html"], "AC-4: Versand-Mail laeuft nicht durch den Baustein"
    assert _MARKE in versand["sms"], "AC-4: Versand-SMS laeuft nicht durch den Baustein"


# ---------------------------------------------------------------------------
# AC-5: kein Zirkelimport, Alt-Namen bleiben
# ---------------------------------------------------------------------------


def test_ac5_baustein_laedt_weder_scheduler_noch_vorschau_und_alte_namen_bleiben():
    """AC-5: Given der Baustein / When er in einem frischen Prozess importiert
    wird / Then sind weder ``trip_report_scheduler`` noch ``preview_service``
    geladen, die fuenf Baustein-Funktionen existieren, und die alten Namen
    (``PreviewService``, ``render_sms_preview``, ``_build_report``,
    ``TripReportSchedulerService._briefing_bauen_und_senden``) bleiben
    importierbar.

    RED: Modul existiert nicht (Import scheitert im Subprozess)."""
    code = (
        "import sys, services.trip_briefing_aufbau as m\n"
        "geladen = sorted(n for n in sys.modules if n.endswith(('trip_report_scheduler',"
        " 'preview_service')))\n"
        "fehlt = [f for f in ('trip_segmente_bauen', 'trip_wetter_laden',"
        " 'trip_anreicherung_bauen', 'trip_report_rendern', 'trip_briefing_bauen')"
        " if not callable(getattr(m, f, None))]\n"
        "print(geladen)\n"
        "print(fehlt)\n"
        "from services.preview_service import PreviewService\n"
        "from services.trip_report_scheduler import TripReportSchedulerService\n"
        "assert callable(PreviewService.render_sms_preview)\n"
        "assert callable(PreviewService._build_report)\n"
        "assert callable(TripReportSchedulerService._briefing_bauen_und_senden)\n"
        "assert callable(TripReportSchedulerService._send_trip_report_outcome)\n"
    )
    env = dict(os.environ, PYTHONPATH=f"{REPO_ROOT / 'src'}{os.pathsep}{REPO_ROOT}")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       cwd=REPO_ROOT, env=env, timeout=120)
    assert r.returncode == 0, f"AC-5: Baustein/Alt-Namen nicht importierbar:\n{r.stderr[-1500:]}"
    geladen, fehlt = r.stdout.strip().splitlines()[-2:]
    assert geladen == "[]", f"AC-5: Baustein zieht Dienste nach: {geladen}"
    assert fehlt == "[]", f"AC-5: Baustein-Funktionen fehlen: {fehlt}"


# ---------------------------------------------------------------------------
# AC-6: Baustein ohne Nebenwirkung
# ---------------------------------------------------------------------------


def _verzeichnis_abbild(root: Path) -> dict:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def _abbild_ohne_abrufbudget(abbild: dict) -> dict:
    """Der Wetterabruf bucht Abrufbudget des Nutzers wie bisher (Spec,
    Side effects) -- das ist kein Schreibzugriff des Bausteins selbst."""
    return {k: v for k, v in abbild.items() if "forecast_budget.json" not in k}


def test_ac6_baustein_und_vorschau_ohne_nebenwirkung(env, monkeypatch):
    """AC-6: Given der Baustein / When er direkt (``trip_segmente_bauen`` mit
    ``persist=False``) und ueber die Vorschau ausgefuehrt wird / Then wird
    nichts versendet, kein Anker/Snapshot/Melde-Gedaechtnis geschrieben, kein
    Vorfall gebucht und keine Datei im Datenverzeichnis angelegt oder
    geaendert (ausser der Abrufbudget-Buchung des Wetterabrufs).

    RED: services.trip_briefing_aufbau existiert noch nicht."""
    import services.alert_briefing_anchor as anker
    import services.notification_service as ns
    import services.trip_report_scheduler as trs
    import services.weather_snapshot as snap
    from services.trip_briefing_aufbau import trip_segmente_bauen
    from services.trip_report_scheduler import TripReportSchedulerService

    def _verboten(name):
        def _wirf(*a, **k):
            raise AssertionError(f"AC-6: Baustein/Vorschau loest {name} aus")
        return _wirf

    monkeypatch.setattr(ns.NotificationService, "send_trip_report", _verboten("Versand"))
    for name in ("write_anchor_and_reset_memory", "record_briefing_dispatch_failure",
                 "record_official_alerts_reported"):
        monkeypatch.setattr(anker, name, _verboten(name))
        if hasattr(trs, name):
            monkeypatch.setattr(trs, name, _verboten(name))
    for name in ("save", "save_dated"):
        monkeypatch.setattr(snap.WeatherSnapshotService, name, _verboten(f"Snapshot.{name}"))

    vorher = _abbild_ohne_abrufbudget(_verzeichnis_abbild(env["data_root"]))
    scheduler = TripReportSchedulerService(user_id=NUTZER_A)
    segmente = trip_segmente_bauen(scheduler, _trip(NUTZER_A, TRIP_A), TAG, persist=False)
    report, segment_weather, _stage, _tz = _vorschau_bericht(NUTZER_A, TRIP_A, "evening")
    nachher = _abbild_ohne_abrufbudget(_verzeichnis_abbild(env["data_root"]))

    assert segmente, "Baustein liefert keine Segmente"
    assert report.sms_text and segment_weather, "Vorschau liefert keinen Bericht"
    assert env["mitschrift"].kanaele == [], f"AC-6: zugestellt: {env['mitschrift']!r}"
    assert sorted(nachher) == sorted(vorher), (
        f"AC-6: Dateien angelegt/geloescht: {sorted(set(nachher) ^ set(vorher))}"
    )
    geaendert = [k for k in vorher if vorher[k] != nachher[k]]
    assert not geaendert, f"AC-6: Dateien geaendert: {geaendert}"


# ---------------------------------------------------------------------------
# AC-7: Reihenfolge des Versands
# ---------------------------------------------------------------------------


def test_ac7_ohne_etappe_no_stage_ohne_wetterabruf_und_versand(env):
    """AC-7: Given ein Zieltag ohne Etappe / When der Versand laeuft / Then
    endet er mit ``no_stage``, ohne Wetterabruf, ohne Rendern, ohne Zustellung."""
    from services.trip_report_scheduler import TripReportSchedulerService

    beob = env["beob"]
    ausgang = TripReportSchedulerService(user_id=NUTZER_A)._send_trip_report_outcome(
        _trip(NUTZER_A, TRIP_A), "morning", target_date=TAG + timedelta(days=9),
    )
    assert ausgang == "no_stage", ausgang
    assert beob.wetter_nutzer == [] and beob.format_email == [], "AC-7: no_stage nach Abruf/Render"
    assert env["mitschrift"].kanaele == [], "AC-7: trotz no_stage zugestellt"


def test_ac7_ohne_wetter_no_weather_ohne_briefing(env, monkeypatch, tmp_path):
    """AC-7: Given alle Wetterabrufe scheitern (leeres Fixture-Verzeichnis) /
    When der regulaere Versand laeuft / Then endet er mit ``no_weather``
    NACH dem Wetterabruf, es wird kein Briefing gerendert und keins
    zugestellt (nur der Ausfall-Hinweis, #1012)."""
    from services.trip_report_scheduler import TripReportSchedulerService
    from services.weather_cache import reset_shared_weather_cache_for_tests

    leer = tmp_path / "fixtures-leer"
    leer.mkdir()
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(leer))
    reset_shared_weather_cache_for_tests()

    beob = env["beob"]
    ausgang = TripReportSchedulerService(user_id=NUTZER_A)._send_trip_report_outcome(
        _trip(NUTZER_A, TRIP_A), "morning",
    )
    assert ausgang == "no_weather", ausgang
    assert beob.wetter_nutzer, "Vorbedingung: der Wetterabruf hat stattgefunden"
    assert beob.format_email == [], "AC-7: trotz no_weather ein Briefing gerendert"
    briefing_betreff = "Etappe 2: " + ETAPPE_A + " 1"
    for s in env["mitschrift"].sendungen("email"):
        assert briefing_betreff not in (s["subject"] or ""), (
            f"AC-7: trotz no_weather ein Briefing zugestellt: {s['subject']!r}"
        )


def _kontingent_erschoepfen(uid: str, anderer: str) -> None:
    """Echter Zaehlerstand (Muster ``test_abruf_kontingent_manuell._erschoepfe``):
    das Handversand-Kontingent von ``uid`` ist fuer heute aufgebraucht."""
    from app.loader import get_data_dir, get_data_root
    from services.forecast_budget import PROVIDER

    grenze = 1500  # GRENZE_JE_NUTZER (ADR-0117 Nachtrag)
    heute = datetime.now(timezone.utc).date().isoformat()
    glob = get_data_root() / "diagnostics" / "forecast_budget.json"
    glob.parent.mkdir(parents=True, exist_ok=True)
    glob.write_text(json.dumps({
        "date": heute, "calls": {PROVIDER: grenze}, "manual_calls": {PROVIDER: grenze},
        "cache_hits": 0, "cache_misses": 0, "active_users": [uid, anderer],
    }))
    eigen = get_data_dir(uid) / "diagnostics" / "forecast_budget.json"
    eigen.parent.mkdir(parents=True, exist_ok=True)
    eigen.write_text(json.dumps({
        "date": heute, "calls": {PROVIDER: grenze}, "manual": {PROVIDER: grenze},
    }))


def test_ac7_kontingent_erschoepft_nach_abruf_vor_jedem_rendern(env, monkeypatch):
    """AC-7: Given ein Handversand, dessen Kontingent beim Wetterabruf
    erschoepft ist (#2961) / When der Versand laeuft / Then bricht er NACH dem
    Wetterabruf und VOR jedem Rendern ab (``kontingent_erschoepft``; der
    Baustein-Render ``trip_report_rendern`` und der Formatter werden nie
    aufgerufen, nichts wird zugestellt).

    RED: services.trip_briefing_aufbau existiert noch nicht."""
    import services.trip_briefing_aufbau as aufbau
    from services import forecast_budget as fb
    from services.trip_report_scheduler import TripReportSchedulerService

    gerendert: list[str] = []
    original = aufbau.trip_report_rendern
    monkeypatch.setattr(
        aufbau, "trip_report_rendern",
        lambda *a, **k: (gerendert.append("trip_report_rendern"), original(*a, **k))[1],
    )

    beob = env["beob"]
    _kontingent_erschoepfen(NUTZER_A, NUTZER_B)

    with fb.manueller_abruf(NUTZER_A, 5):
        ausgang = TripReportSchedulerService(user_id=NUTZER_A)._send_trip_report_outcome(
            _trip(NUTZER_A, TRIP_A), "morning", angefordert=True,
        )
    assert ausgang == "kontingent_erschoepft", ausgang
    assert beob.wetter_nutzer, "Vorbedingung: der Wetterabruf hat stattgefunden"
    assert gerendert == [], f"AC-7: trotz erschoepftem Kontingent gerendert: {gerendert}"
    assert beob.format_email == [], "AC-7: Formatter trotz erschoepftem Kontingent gerufen"
    assert env["mitschrift"].kanaele == [], "AC-7: trotz erschoepftem Kontingent zugestellt"


# ---------------------------------------------------------------------------
# AC-8: bekannte Vorschau-Abweichungen bleiben bis #3144 unveraendert
# ---------------------------------------------------------------------------


def test_ac8_vorschau_ohne_nachtgate_ohne_warnungen_has_gap_false(env, monkeypatch):
    """AC-8: Given ein Trip mit eingeschalteten amtlichen Warnungen, aber ohne
    Nacht-Bedarf (``night_weather_needed`` False) / When die SMS-Vorschau
    laeuft / Then ist die SMS byte-gleich zum Stand vor dem Umbau, die
    Vorschau ruft weder Nachtwetter noch amtliche Warnungen ab und rendert mit
    ``has_gap`` False -- der Versand desselben Trips dagegen holt beides
    (Gegenprobe: der Unterschied ist heutiger Stand, Angleichung in #3144)."""
    import services.official_alerts as oa
    from services.segment_weather import night_weather_needed

    beob = env["beob"]

    def _warnungen(*a, **k):
        beob.warnungen += 1
        return [], False

    monkeypatch.setattr(oa, "get_official_alerts_with_status", _warnungen)
    _trip_anlegen(NUTZER_A, TRIP_A_OHNE_NACHT, TRIP_NAME_A, ETAPPE_A, official_alerts=True,
                  display_config=_ohne_nacht_display_config(TRIP_A_OHNE_NACHT))
    trip = _trip(NUTZER_A, TRIP_A_OHNE_NACHT)
    assert night_weather_needed(trip.display_config) is False, "Vorbedingung: Gate aus"

    betreff, sms = _vorschau_sms(NUTZER_A, TRIP_A_OHNE_NACHT, "morning")
    assert beob.nacht_nutzer == [], "AC-8: Vorschau holt trotz Gate Nachtwetter"
    assert beob.warnungen == 0, "AC-8: Vorschau fragt amtliche Warnungen ab"
    assert beob.format_email and all(not k.get("has_gap") for k in beob.format_email), (
        f"AC-8: Vorschau rendert mit has_gap: {[k.get('has_gap') for k in beob.format_email]}"
    )
    _golden_pruefen("vorschau_ohne_nacht_morning", {"subject": betreff, "sms": sms}, "AC-8")

    beob.leeren()
    _versand(env, NUTZER_A, TRIP_A_OHNE_NACHT, "morning")
    assert beob.nacht_nutzer == [NUTZER_A], "Gegenprobe: Versand holt Nachtwetter immer"
    assert beob.warnungen > 0, "Gegenprobe: Versand fragt amtliche Warnungen ab"
