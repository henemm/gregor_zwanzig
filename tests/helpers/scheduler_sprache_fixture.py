"""Deterministische Scheduler-Fixture fuer P9b (Issue #2672, Epic #2644).

Eigene Nutzertexte der Orchestrierung -- Nachlieferungs-Praefixe,
Teilausfall-Hinweis, Ausfall-Meldung, Ortsvergleich-Briefing und -Betreff,
Gewitter-Vorschau, Service-Fehler-Mail -- erzeugt durch den ECHTEN Weg
(``TripReportSchedulerService``, ``send_one_compare_preset``). Ersetzt werden
nur die Raender: Wetter ueber den offline ``FixtureProvider``
(``GZ_TEST_FIXTURE_DIR``, leeres Verzeichnis = echter Ausfall), die
Vergleichs-Engine als echte Subklasse (Haus-Muster
``test_compare_channel_metrics_reach_the_renderer.py``), das Drahtende ueber
``KanalRig``. Kein ``Mock()``/``patch()``.

Die Sprache kommt aus ``user.json`` (``language``) -- wie im Betrieb. Reine
Funktionen bekommen ``lang`` nur bei ``en`` (``de`` = Bestandsaufruf), damit
die deutsche Golden-Datei mit dem Code VOR der Umstellung entstehen konnte.
Feste Zeit 2026-10-29T04:00Z (Donnerstag), ``freeze_time`` im Aufrufer.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, time, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO / "tests" / "golden" / "scheduler_texte"
FIXTURES = REPO / "fixtures" / "openmeteo"
JETZT = datetime(2026, 10, 29, 4, 0, tzinfo=timezone.utc)
TAG = JETZT.date()
INNSBRUCK = (47.2692, 11.4041)
STUBAI = (47.1015, 11.2958)


def _kw(lang: str | None) -> dict:
    return {} if lang is None else {"lang": lang}


def golden_pfad(lang: str) -> Path:
    return GOLDEN_DIR / f"texte.{lang}.txt"


# ----------------------------------------------------------------- Nutzer


def nutzer_anlegen(user_id: str, lang: str | None) -> None:
    """``user.json`` mit allen vier Kanaelen (Read-Modify-Write), Sprache
    nur wenn ``lang`` gesetzt ist (``None`` = Bestandsnutzer ohne Feld)."""
    from app.loader import get_data_dir
    from tests.helpers.kanal_fake_transporte import premium_profil_schreiben

    shutil.rmtree(get_data_dir(user_id), ignore_errors=True)
    premium_profil_schreiben(user_id, reply_at=JETZT)
    pfad = get_data_dir(user_id) / "user.json"
    profil = json.loads(pfad.read_text())
    if lang is not None:
        profil["language"] = lang
    pfad.write_text(json.dumps(profil))


def wetter(monkeypatch, tmp_path: Path, art: str) -> None:
    """``voll`` (alle Fixture-Orte), ``teil`` (nur Innsbruck), ``aus`` (nichts)."""
    if art == "voll":
        monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(FIXTURES))
        return
    ziel = tmp_path / f"fx-{art}"
    ziel.mkdir(exist_ok=True)
    if art == "teil":
        shutil.copy(FIXTURES / "innsbruck.json", ziel / "innsbruck.json")
    if art == "sturm":
        _sturm_fixture(ziel / "innsbruck.json")
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(ziel))
    from services.weather_cache import reset_shared_weather_cache_for_tests

    reset_shared_weather_cache_for_tests()


def _sturm_fixture(ziel: Path) -> None:
    """Aufgezeichnete Innsbruck-Reihe mit Sturm, Regen und mittlerem Gewitter
    von 10 bis 15 Uhr UTC jedes Tages (Trend-Notiz und Gewitter-Vorschau)."""
    daten = json.loads((FIXTURES / "innsbruck.json").read_text())
    for i, p in enumerate(daten["data"]):
        p.update(wind10m_kmh=50, gust_kmh=75, precip_1h_mm=1.0)
        p["thunder_level"] = "MED" if 10 <= i % 24 <= 15 else "NONE"
    ziel.write_text(json.dumps(daten))


def trip_mehrtaegig(user_id: str, tage: int = 3):
    """Trip mit je einer Etappe ab ``TAG`` (fuer Ausblick und Gewitter-Vorschau)."""
    from datetime import timedelta

    from app.loader import save_trip
    from app.trip import Stage, TimeWindow, Trip, Waypoint

    etappen = []
    for i in range(tage):
        wps = [Waypoint(id=f"G{j}", name=f"W{j}", lat=INNSBRUCK[0], lon=INNSBRUCK[1],
                        elevation_m=600 + 50 * j,
                        time_window=TimeWindow(start=time(9 + 3 * j, 0), end=time(9 + 3 * j, 0)))
               for j in range(2)]
        etappen.append(Stage(id=f"T{i}", name=f"Etappe {i}", date=TAG + timedelta(days=i),
                             start_time=time(9, 0), waypoints=wps))
    trip = Trip(id=f"trip-lang-{user_id}", name="GR20", stages=etappen,
                official_alerts_enabled=False)
    save_trip(trip, user_id=user_id)
    return trip


def trip_anlegen(user_id: str, coords: list[tuple[float, float]], *, sms: bool = True):
    """Eine Etappe am festen Tag; je Koordinate ein Wegpunkt (= ein Segment)."""
    from app.loader import save_trip
    from app.models import TripReportConfig
    from app.trip import Stage, TimeWindow, Trip, Waypoint

    stunden = [7, 9, 11, 13][: len(coords)]
    wps = [
        Waypoint(id=f"G{i + 1}", name=f"WP{i + 1}", lat=lat, lon=lon, elevation_m=600 + 50 * i,
                 time_window=TimeWindow(start=time(h, 0), end=time(h, 0)))
        for i, ((lat, lon), h) in enumerate(zip(coords, stunden))
    ]
    trip = Trip(
        id=f"trip-{user_id}", name="GR20",
        stages=[Stage(id="T1", name="Etappe 3", date=TAG, start_time=time(stunden[0], 0),
                      waypoints=wps)],
        official_alerts_enabled=False,
        report_config=TripReportConfig(
            trip_id=f"trip-{user_id}", send_email=True, send_telegram=True, send_sms=sms,
            multi_day_trend_reports=[],
        ),
    )
    save_trip(trip, user_id=user_id)
    return trip


def scheduler(rig, user_id: str):
    from services.trip_report_scheduler import TripReportSchedulerService

    return TripReportSchedulerService(rig.settings(), user_id=user_id)


# ------------------------------------------------------------ Mitschrift


def _erster_absatz(text: str) -> str:
    return text.split("\n\n", 1)[0]


def mails(rig) -> list[dict]:
    from tests.helpers.versand_fixture import mime

    return [mime(m["roh"]) for m in rig.angenommen["email"]]


def kanaele(rig) -> dict:
    """Erste Nachricht je Kanal: Mail (Betreff, Kopf, Klartext), Telegram, SMS."""
    m = mails(rig)
    return {
        "mail": m[0] if m else None,
        "telegram": [x["text"] for x in rig.angenommen["telegram"]],
        "sms": [x["text"] for x in rig.angenommen["sms"]],
    }


# ------------------------------------------------------------ Trip-Faelle


def nachlieferung(rig, monkeypatch, tmp_path, user_id: str, fall: str) -> dict:
    """Ein Nachliefer-Vermerk und danach die Nachlieferung.

    ``komplett``: Totalausfall um 6 Uhr, dann voll erholt.
    ``vollstaendig``: Segment 1 fehlte, jetzt alle Daten.
    ``unvollstaendig``: Segment 1 fehlte, jetzt fehlt das Ziel-Segment.
    ``versandfehler``: Zustellung um 6 Uhr scheiterte.
    """
    coords = {"unvollstaendig": [INNSBRUCK, INNSBRUCK, STUBAI]}.get(fall, [INNSBRUCK, INNSBRUCK])
    trip = trip_anlegen(user_id, coords)
    svc = scheduler(rig, user_id)
    segmente = svc._convert_trip_to_segments(trip, TAG)
    alle = [str(s.segment_id) for s in segmente]
    fehlend = {"komplett": alle, "vollstaendig": alle[:1], "unvollstaendig": alle[:1],
               "versandfehler": []}[fall]
    svc._write_pending_marker(
        trip, "morning", TAG, failed_segment_ids=fehlend,
        reason="dispatch_error" if fall == "versandfehler" else None,
    )
    _vermerk_stunde(user_id, 6)
    wetter(monkeypatch, tmp_path, "teil" if fall == "unvollstaendig" else "voll")
    rig.zaehler_leeren()
    ergebnis = svc._process_pending_markers(JETZT, set())
    return {"ergebnis": ergebnis, **kanaele(rig)}


def _vermerk_stunde(user_id: str, stunde: int) -> None:
    """Die Slot-Stunde des Vermerks fest auf ``stunde`` (der Schreiber nimmt
    die Wanduhr). Read-Modify-Write auf die echte Vermerkdatei."""
    from app.loader import get_data_dir

    pfad = get_data_dir(user_id) / "pending_briefings.json"
    daten = json.loads(pfad.read_text())
    for e in daten.get("entries", []):
        e["slot_hour"] = stunde
    pfad.write_text(json.dumps(daten))


def ausfall(rig, monkeypatch, tmp_path, user_id: str) -> dict:
    """Totalausfall aller Provider beim regulaeren Briefing."""
    trip = trip_anlegen(user_id, [INNSBRUCK, INNSBRUCK])
    wetter(monkeypatch, tmp_path, "aus")
    rig.zaehler_leeren()
    ausgang = scheduler(rig, user_id)._send_trip_report_outcome(trip, "morning")
    return {"ausgang": ausgang, **kanaele(rig)}


def teilausfall(rig, monkeypatch, tmp_path, user_id: str) -> dict:
    trip = trip_anlegen(user_id, [INNSBRUCK, INNSBRUCK, STUBAI])
    wetter(monkeypatch, tmp_path, "teil")
    rig.zaehler_leeren()
    ausgang = scheduler(rig, user_id)._send_trip_report_outcome(trip, "morning")
    return {"ausgang": ausgang, **kanaele(rig)}


def servicefehler(rig, monkeypatch, tmp_path, user_id: str) -> dict:
    """SMS-only-Trip mit Teilausfall: Service-Fehler-Mail an den Nutzer."""
    from app.loader import save_trip
    from app.models import TripReportConfig

    trip = trip_anlegen(user_id, [INNSBRUCK, INNSBRUCK, STUBAI])
    trip.report_config = TripReportConfig(trip_id=trip.id, send_email=False, send_sms=True,
                                          multi_day_trend_reports=[])
    save_trip(trip, user_id=user_id)
    wetter(monkeypatch, tmp_path, "teil")
    rig.zaehler_leeren()
    scheduler(rig, user_id)._send_trip_report_outcome(trip, "morning")
    roh = [m["roh"] for m in rig.angenommen["email"]]
    return {"mails": mails(rig), "roh": roh}


# --------------------------------------------------------- Gewitter/Trend


def gewitter_zeilen(rig, user_id: str, kw: dict) -> list[tuple[str, str]]:
    """Gewitter-Vorschau aus der Trend-Zeile (Tag, Herkunft, Hagel, Nacht)
    und Trend-Notiz -- Methoden des Dienstobjekts dieses Nutzers."""
    from app.day_window import format_night_addendum
    from app.models import ThunderLevel
    from services import trip_report_scheduler as trs

    svc = scheduler(rig, user_id)
    zeile = {
        "thunder": "HIGH",
        "hourly_thunder": tuple(_hv(h, ThunderLevel.MED if h < 15 else ThunderLevel.NONE)
                                for h in range(10, 17)),
        "hourly_thunder_signals": tuple((h, ThunderLevel.MED, ("cape", "blitzdichte"))
                                        for h in range(10, 15)),
        "hourly_hail": (12,),
    }
    nacht = ((2, ThunderLevel.HIGH, True),)
    out = [("gewitter.tag", svc._thunder_entry_from_trend_row(zeile, TAG, night_hourly=nacht))]
    leicht = {"thunder": "LOW", "hourly_thunder": (_hv(11, ThunderLevel.LOW),),
              "hourly_thunder_signals": ((11, ThunderLevel.LOW, ("cape",)),)}
    out.append(("gewitter.leicht", svc._thunder_entry_from_trend_row(leicht, TAG)))
    out.append(("gewitter.kein", svc._thunder_entry_from_trend_row({"thunder": "NONE"}, TAG)))
    texte = [(k, f"{v['date']}: {v['text']}") for k, v in out]
    texte.append(("nacht.leicht", format_night_addendum(ThunderLevel.LOW, 3, **kw)))
    texte.append(("nacht.mittel", format_night_addendum(ThunderLevel.MED, 1, True, **kw)))
    for name, args in (("hoch", ("HIGH", 9.0, 50)), ("leicht", ("LOW", 1.0, 10)),
                       ("ruhig", ("NONE", 0.0, 10))):
        texte.append((f"trend_notiz.{name}", str(trs._trend_note(*args, **kw))))
    return texte


def gewitter_abruf(rig, user_id: str) -> dict:
    """Gewitter-Vorschau ueber den ABRUF-Weg (``_build_thunder_forecast``):
    Folgetag mit mittlerem Gewitter 10-14 UTC (Herkunft Blitzdichte, Hagel um
    12) und starkem Nachtgewitter um 02 UTC mit Hagel."""
    from datetime import timedelta

    from app.models import (
        ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider, SegmentWeatherData,
        ThunderLevel,
    )
    from services.trip_segments import convert_trip_to_segments
    from utils.timezone import tz_for_coords

    morgen = datetime(2026, 10, 30, 0, 0, tzinfo=timezone.utc)
    punkte = [ForecastDataPoint(ts=morgen + timedelta(hours=2), thunder_level=ThunderLevel.HIGH,
                                hail_flag=True)]
    punkte += [ForecastDataPoint(ts=morgen + timedelta(hours=h), thunder_level=ThunderLevel.MED,
                                 thunder_level_signals=["blitzdichte"], hail_flag=(h == 12))
               for h in range(10, 15)]
    trip = trip_anlegen(user_id, [INNSBRUCK, INNSBRUCK])
    seg = convert_trip_to_segments(trip, TAG)[0]
    sw = SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=punkte),
        aggregated=None, fetched_at=JETZT, provider="openmeteo")
    return scheduler(rig, user_id)._build_thunder_forecast(
        [sw], TAG, tz_for_coords(*INNSBRUCK))


def _hv(stunde: int, stufe):
    from app.thunder_scale import thunder_label_value
    from output.tokens.dto import HourlyValue

    return HourlyValue(stunde, float(thunder_label_value(stufe)))


# ----------------------------------------------------------- Ortsvergleich


VERGLEICH_ORTE = (("loc-ibk", "Innsbruck", 47.27, 11.39), ("loc-stb", "Stubai", 47.10, 11.30),
                  ("loc-zil", "Zillertal", 47.22, 11.88))


def vergleich_engine(monkeypatch) -> None:
    """Echte Subklasse der Vergleichs-Engine mit festem Wetter je Ort;
    der Delta-Anker (Netz) ist kein Pruefgegenstand."""
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod
    from app.models import ForecastDataPoint, ThunderLevel
    from app.user import ComparisonResult, LocationResult

    def _dp(h: int) -> ForecastDataPoint:
        return ForecastDataPoint(
            ts=datetime(2026, 10, 29, h, 0, tzinfo=timezone.utc), t2m_c=9.0 + h % 5,
            wind_chill_c=7.0, wind10m_kmh=12.0, gust_kmh=25.0, precip_1h_mm=0.2,
            cloud_total_pct=40, uv_index=2.0, thunder_level=ThunderLevel.NONE, pop_pct=20,
            visibility_m=9000,
        )

    class FesteEngine(ce_mod.ComparisonEngine):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            orte = kwargs.get("locations") or (args[0] if args else [])
            return ComparisonResult(
                locations=[
                    LocationResult(location=loc, score=90 - 5 * i, temp_max=14.0 - i,
                                   temp_min=4.0, wind_max=12.0, gust_max=25.0, cloud_avg=40,
                                   sunny_hours=4, official_alerts=[],
                                   hourly_data=[_dp(8), _dp(11), _dp(14)])
                    for i, loc in enumerate(orte)
                ],
                time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", TAG),
                created_at=datetime(2026, 10, 29, 4, 0, tzinfo=timezone.utc),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", FesteEngine)
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)


def vergleich_preset(user_id: str, *, telegram_stil: str | None = None) -> dict:
    preset = {
        "id": f"cp-{user_id}", "name": "Tirol", "user_id": user_id, "kind": "vergleich",
        "location_ids": [o[0] for o in VERGLEICH_ORTE], "schedule": "daily",
        "profil": "ALLGEMEIN", "created_at": "2026-10-01T00:00:00Z",
        "send_telegram": True, "send_sms": True, "hourly_enabled": False,
        "outlook_enabled": False,
    }
    if telegram_stil:
        preset["display_config"] = {"telegram_style": telegram_stil}
    return preset


def _vergleich_orte() -> list:
    from app.user import SavedLocation

    return [SavedLocation(id=i, name=n, lat=la, lon=lo, elevation_m=600)
            for i, n, la, lo in VERGLEICH_ORTE]


def vergleich_senden(rig, user_id: str, *, catchup: bool = False, **preset_kw) -> dict:
    """Handversand (``send_one_compare_preset``) bzw. mit ``catchup`` der
    echte Nachholweg: Vermerk um 6 Uhr, dann ``process_compare_pending_markers``."""
    from services import scheduler_dispatch_service as sds

    preset = vergleich_preset(user_id, **preset_kw)
    rig.zaehler_leeren()
    if catchup:
        sds._mark_compare_undelivered(user_id, preset["id"], "morning", TAG, 6)
        sds.process_compare_pending_markers(
            [preset], user_id, "", rig.settings(), JETZT, _vergleich_orte(), [],
        )
    else:
        sds.send_one_compare_preset(
            preset, rig.settings(), user_id, "", all_locations_cache=_vergleich_orte(),
            target_date=TAG, tage_ab_ortstag=0, on_demand=True,
        )
    return kanaele(rig)


# ---------------------------------------------------------------- Alarm

ALARM_JETZT = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)  # Reykjavik = UTC


class _KonvektiveFrames:
    """Echter ``frame_source`` (kein Mock): konvektiver Nowcast in 20 Minuten."""

    def __call__(self, lat: float, lon: float) -> list:
        from datetime import timedelta

        from providers.brightsky import RadarFrame

        ts = datetime.now(timezone.utc) + timedelta(minutes=20)
        return [RadarFrame(timestamp=ts, precip_mm_h=9.0, is_convective=True),
                RadarFrame(timestamp=ts + timedelta(minutes=10), precip_mm_h=12.0,
                           is_convective=True)]


def radar_alarm(user_id: str, lang: str | None, *, cooldown: int = 120,
                angekuendigt: bool = False) -> list[tuple[str, str]]:
    """Trip-Radar-Alarm (Cooldown 120 Min) als Nachtrag zu einer amtlichen
    Warnung von 11:35 -- ``TripAlertService`` dieses Nutzers, Mail ueber die
    ``mail_sink``-Naht. Aufrufer friert die Uhr auf ``ALARM_JETZT`` ein.

    ``angekuendigt``: das letzte Briefing nannte Regen zum Beginn (Unterklasse
    am Lesezugriff auf den Briefing-Stand, die Entscheidung bleibt echt)."""
    from datetime import timedelta

    from services.alert_gate import record_event_identity
    from services.trip_alert import TripAlertService
    from tests.helpers import nowcast_gate_fixtures as ng

    ng.clean_uid(user_id)
    ng.write_user_tier(user_id, "premium")
    if lang is not None:
        _sprache_setzen(user_id, lang)
    trip_id = f"trip-alarm-{user_id}"
    record_event_identity(
        user_id=user_id, entity_id=trip_id, hazard_class="wet", segment_ids=["1"],
        severity="MODERATE", window_start=ALARM_JETZT - timedelta(minutes=30),
        window_end=ALARM_JETZT + timedelta(hours=3), now=ALARM_JETZT - timedelta(minutes=25),
    )
    von, bis = ng.quiet_window_elsewhere(zone=ng.TRIP_ZONE)
    ng.save_trip(ng.make_trip(trip_id, cooldown_minutes=cooldown, quiet_from=von, quiet_to=bis,
                              stage_date=ALARM_JETZT.date()), user_id)
    post: list[tuple[str, str]] = []

    class _Angekuendigt(TripAlertService):
        def _briefing_precip_for_onset(self, *args, **kwargs):
            return 2.0

    klasse = _Angekuendigt if angekuendigt else TripAlertService
    svc = klasse(
        settings=ng.settings_email_only(), throttle_hours=0, user_id=user_id,
        radar_service=ng.radar_service(_KonvektiveFrames()),
        mail_sink=lambda subject, body: post.append((subject, body)),
    )
    gesendet = svc.check_radar_alerts()
    paare = [("alarm.gesendet", str(gesendet))]
    for i, (betreff, rumpf) in enumerate(post):
        paare += [(f"alarm.{i}.betreff", betreff), (f"alarm.{i}.rumpf", rumpf)]
    return paare


def _sprache_setzen(user_id: str, lang: str) -> None:
    from app.loader import get_data_dir

    pfad = get_data_dir(user_id) / "user.json"
    profil = json.loads(pfad.read_text())
    profil["language"] = lang
    pfad.write_text(json.dumps(profil))


def vergleich_vorschau(user_id: str) -> dict:
    """Vorschau aller Kanaele (``ComparePreviewService``) mit Preset und Orten
    aus der Ablage dieses Nutzers."""
    from app.loader import get_data_dir, save_location
    from services.compare_preview_service import ComparePreviewService
    from tests.helpers.compare_briefings import write_compare_briefings

    for ort in _vergleich_orte():
        save_location(ort, user_id=user_id)
    preset = vergleich_preset(user_id)
    write_compare_briefings(get_data_dir(user_id), [preset])
    return ComparePreviewService().render_all_channels(preset["id"], user_id=user_id,
                                                       target_date=TAG)


# -------------------------------------------------------------- Sammlung


def _mail_paare(name: str, k: dict, *, absatz: bool) -> list[tuple[str, str]]:
    m = k["mail"]
    if m is None:
        return [(f"{name}.mail", "-")]
    plain = _erster_absatz(m["plain"]) if absatz else m["plain"]
    paare = [(f"{name}.betreff", m["betreff"]), (f"{name}.header", str(m["lang"])),
             (f"{name}.mail", plain)]
    for i, tg in enumerate(k["telegram"][:1]):
        paare.append((f"{name}.telegram", _erster_absatz(tg) if absatz else tg))
    for sms in k["sms"][:1]:
        paare.append((f"{name}.sms", sms))
    return paare


def alle_texte(rig, monkeypatch, tmp_path, lang: str) -> str:
    """Alle Faelle fuer ``golden-<lang>``; jede Gruppe mit frischem Nutzer."""
    from freezegun import freeze_time

    rein = None if lang == "de" else lang
    paare: list[tuple[str, str]] = list(reine_texte(rein))
    with freeze_time(JETZT):
        for fall in ("komplett", "vollstaendig", "unvollstaendig", "versandfehler"):
            uid = f"golden-{lang}-nl-{fall}"
            nutzer_anlegen(uid, lang)
            k = nachlieferung(rig, monkeypatch, tmp_path, uid, fall)
            paare += [(f"nachlieferung.{fall}.ergebnis", str(k["ergebnis"]))]
            paare += _mail_paare(f"nachlieferung.{fall}", k, absatz=True)
        uid = f"golden-{lang}-ausfall"
        nutzer_anlegen(uid, lang)
        k = ausfall(rig, monkeypatch, tmp_path, uid)
        paare += [("ausfall.ausgang", k["ausgang"])] + _mail_paare("ausfall", k, absatz=False)
        uid = f"golden-{lang}-teil"
        nutzer_anlegen(uid, lang)
        k = teilausfall(rig, monkeypatch, tmp_path, uid)
        paare += [("teilausfall.ausgang", k["ausgang"])]
        paare += _mail_paare("teilausfall", k, absatz=True)
        uid = f"golden-{lang}-service"
        nutzer_anlegen(uid, lang)
        s = servicefehler(rig, monkeypatch, tmp_path, uid)
        for m in s["mails"]:
            paare += [("servicefehler.betreff", m["betreff"]),
                      ("servicefehler.header", str(m["lang"]))]
        uid = f"golden-{lang}-gewitter"
        nutzer_anlegen(uid, lang)
        paare += gewitter_zeilen(rig, uid, _kw(rein))
        abruf = gewitter_abruf(rig, uid)
        paare += [(f"gewitter_abruf.{k}", f"{v['date']}: {v['text']}")
                  for k, v in sorted(abruf.items()) if k.startswith("+")]
        vergleich_engine(monkeypatch)
        uid = f"golden-{lang}-vergleich"
        nutzer_anlegen(uid, lang)
        paare += _mail_paare("vergleich", vergleich_senden(rig, uid), absatz=False)
        paare += _mail_paare("vergleich_nachgeholt", vergleich_senden(rig, uid, catchup=True),
                             absatz=True)
        paare += _mail_paare("vergleich_kurzform",
                             vergleich_senden(rig, uid, telegram_stil="kurzform"), absatz=True)
        vorschau = vergleich_vorschau(uid)
        paare += [(f"vorschau.{k}", vorschau[k]) for k in ("subject", "telegram", "sms")]
    with freeze_time(ALARM_JETZT):
        paare += radar_alarm(f"golden-{lang}-alarm", lang)
    return "".join(f"----- {k} -----\n{v}\n" for k, v in paare)


def reine_texte(lang: str | None) -> list[tuple[str, str]]:
    """Reine Bausteine ohne Dienstobjekt (Bestandsaufruf bei ``de``)."""
    from services import pending_briefings as pb
    from services.notification_service import build_service_error_email_html
    from services.scheduler_dispatch_service import build_compare_preset_subject

    return [
        ("vergleich.betreff", build_compare_preset_subject("Tirol", TAG, **_kw(lang))),
        ("versandfehler.07", pb.dispatch_error_hint(7, **_kw(lang))),
        ("versandfehler.unlesbar", pb.dispatch_error_hint("x", **_kw(lang))),
        ("servicefehler.rumpf", build_service_error_email_html(
            "GR20", "morning", "  - Segment 2: HTTP 503", **_kw(lang))),
    ]
