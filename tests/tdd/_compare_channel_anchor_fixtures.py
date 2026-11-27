"""Geteilte Bausteine fuer die S2-Tests des kanalscharfen Compare-Alarm-Ankers
(Issue #1987, Scheibe S2).

SPEC: ``docs/specs/modules/fix_1987_s2_compare_kanal_anker.md``.

Mock-frei (CLAUDE.md Test-Politik): echte Preset-, Orts- und Snapshot-Dateien
in der pytest-isolierten ``get_data_dir()``-Basis (#1133), echte
``CompareAlertService``-Laeufe, Transport nur ueber die vorhandenen Naehte:
E-Mail ueber ``mail_sink`` (kein SMTP), Telegram scheitert am ECHTEN
Transport ohne Netz (``settings_email_and_failing_telegram``: Testmodus,
kein zustellbarer Empfaenger -- der Kanal wird betreten und als
``delivery_failed`` gebucht, wie im S1-Pendant). Beobachtet wird die an
``DeviationAlertEngine.evaluate`` uebergebene Vergleichsbasis ueber einen
aufzeichnenden Wrapper, der die echte Methode weiter aufruft (kein
``Mock()``/``patch()``).

Pfadregel #1409: alle Pfade ueber ``app.loader`` -- nie ein Hauptrepo-Pfad.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherSummary,
    ThunderLevel,
)
from app.user import SavedLocation

from tests.helpers.alert_log_fixtures import read_log, reason_for_channel
from tests.helpers.compare_briefings import write_compare_briefings

ALLE_KANAELE = ("email", "telegram", "sms", "premium_sms")

# Orte mit eindeutigen Kennungen; Koordinaten in Mitteleuropa.
ORT_A = ("loc-s2-a", "Alpenort", 47.07, 11.44)
ORT_B = ("loc-s2-b", "Bergort", 47.50, 11.90)

ANKER_MM = 2.0          # Briefing-Stand, gegen den ein Alarm ausloest
FRISCH_HOCH_MM = 30.0   # Δ 28 mm (Schwelle 10 mm) -> ausloesend, HIGH
FRISCH_NIEDRIG_MM = 13.0  # Δ 11 mm -> ausloesend, nur LOW
FRISCH_RUHIG_MM = 2.0   # kein Δ -> kein Alarm (reine Basis-Beobachtung)


def nutzer(prefix: str) -> str:
    """Eindeutige, echte user_id -- nie ``"default"``."""
    return f"tdd-1987s2-{prefix}-{uuid.uuid4().hex[:8]}"


def punkt(
    loc_id: str, precip_mm: float, *, alter: timedelta = timedelta(0),
    target_date: Optional[date] = None, mit_reihe: bool = False,
):
    """Echtes ``PointWeatherData``-DTO mit eindeutigem Niederschlagswert und
    praepariertem ``fetched_at`` (jetzt minus ``alter``)."""
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=loc_id, name=loc_id, lat=47.0, lon=11.0,
        timeseries=_reihe() if mit_reihe else None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_mm),
        fetched_at=datetime.now(timezone.utc) - alter, provider="tdd-1987s2",
        target_date=target_date,
    )


def _reihe() -> NormalizedTimeseries:
    heute = date.today()
    return NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
        data=[
            ForecastDataPoint(
                ts=datetime(heute.year, heute.month, heute.day, h, 0),
                t2m_c=20.0, wind_chill_c=19.0, wind10m_kmh=10.0, gust_kmh=15.0,
                precip_1h_mm=0.0, cloud_total_pct=30, uv_index=4.0,
                thunder_level=ThunderLevel.NONE, pop_pct=10, visibility_m=9000,
            )
            for h in (9, 12, 15)
        ],
    )


class FesteQuelle:
    """Deterministische ``LocationWeatherSource`` (kein Mock): fester
    Frischwert je Ort, zeichnet die Abruf-Argumente (inkl. ``target_date``)
    auf."""

    def __init__(self, werte: dict[str, float]) -> None:
        self._werte = dict(werte)
        self.aufrufe: list[dict] = []

    def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None, **kw):
        self.aufrufe.append({"point_id": point_id, **kw})
        return punkt(point_id, self._werte.get(point_id, 0.0),
                     target_date=kw.get("target_date"))


def preset_dict(preset_id: str, loc_ids: list[str], **extra) -> dict:
    preset = {
        "id": preset_id, "name": preset_id, "user_id": "unused",
        "location_ids": list(loc_ids), "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": [], "letzter_versand": None,
        "top_ort_letzter_versand": None, "created_at": "2026-11-27T00:00:00Z",
    }
    preset.update(extra)
    return preset


def lege_vergleich_an(
    uid: str, preset_id: str, orte=(ORT_A,), **preset_extra,
) -> dict:
    """Orte + Preset als echte Dateien; gibt das Preset-Rohdict zurueck."""
    from app.loader import get_data_dir, save_location

    for loc_id, name, lat, lon in orte:
        save_location(
            SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=800),
            user_id=uid,
        )
    preset = preset_dict(preset_id, [o[0] for o in orte], **preset_extra)
    write_compare_briefings(get_data_dir(uid), [preset])
    return preset


def briefing_anker(uid, preset_id, loc_id, precip_mm, *, alter, target_date=None):
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    CompareWeatherSnapshotService(user_id=uid).save(
        preset_id, loc_id, punkt(loc_id, precip_mm, alter=alter, target_date=target_date),
    )


def kanal_merker(uid, preset_id, loc_id, channel, precip_mm, *, alter, target_date=None):
    """Legt einen Kanal-Merker ueber die NEUE API an (Spec, Datenmodell)."""
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    CompareWeatherSnapshotService(user_id=uid).save_alarm_anchor(
        preset_id, loc_id,
        punkt(loc_id, precip_mm, alter=alter, target_date=target_date),
        channel,
    )


def merker(uid, preset_id, loc_id, channel):
    """Geladener Kanal-Merker (``PointWeatherData``) oder ``None``."""
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    geladen = CompareWeatherSnapshotService(user_id=uid).load_alarm_anchor(
        preset_id, loc_id, channel,
    )
    return geladen[0] if geladen else None


def snapshot_dir(uid: str) -> Path:
    from app.loader import get_data_dir

    return get_data_dir(uid) / "compare_weather_snapshots"


def alarm_dateien(uid: str) -> set[str]:
    d = snapshot_dir(uid)
    if not d.is_dir():
        return set()
    return {p.name for p in d.iterdir() if "__alarm_" in p.name}


def verzeichnis_stand(uid: str) -> dict[str, tuple[int, int]]:
    """Name -> (mtime_ns, size) aller Dateien im Snapshot-Ordner."""
    d = snapshot_dir(uid)
    if not d.is_dir():
        return {}
    return {p.name: (p.stat().st_mtime_ns, p.stat().st_size) for p in d.iterdir()}


def basis_spion(monkeypatch) -> list[list]:
    """Aufzeichnender Wrapper um ``DeviationAlertEngine.evaluate`` (kein
    Mock): merkt sich je Aufruf den uebergebenen ``cached``-Wert und ruft die
    echte Methode weiter auf."""
    from services.deviation_alert_engine import DeviationAlertEngine

    gesehen: list[list] = []
    original = DeviationAlertEngine.evaluate

    def _aufzeichnend(self, cached, fresh, config, alert_state, **kw):
        gesehen.append(list(cached))
        return original(self, cached, fresh, config, alert_state, **kw)

    monkeypatch.setattr(DeviationAlertEngine, "evaluate", _aufzeichnend)
    return gesehen


def basis_mm(gesehen: list[list]) -> Optional[float]:
    """Niederschlag der EINEN gesehenen Basis (Fixtur-Schutz: genau ein Lauf)."""
    assert len(gesehen) == 1, (
        f"Fixtur-Schutz: erwartet genau EINE Auswertung, gesehen {len(gesehen)}."
    )
    return gesehen[0][0].aggregated.precip_sum_mm if gesehen[0] else None


def alarmlauf(uid: str, settings, werte: dict[str, float], mails: list | None = None):
    """Ein echter ``CompareAlertService``-Lauf; gibt ``(sent, quelle)``."""
    from services.compare_alert import CompareAlertService

    mails = mails if mails is not None else []
    quelle = FesteQuelle(werte)
    service = CompareAlertService(
        settings=settings, user_id=uid,
        weather_source=quelle,
        mail_sink=lambda subject, body: mails.append((subject, body)),
    )
    return service.check_all_compare_presets(), quelle


def telegram_gescheitert(eintrag: dict) -> bool:
    """Fixtur-Schutz: Telegram wurde betreten und ist technisch gescheitert."""
    from services import alert_log

    return reason_for_channel(eintrag, "telegram") == alert_log.REASON_DELIVERY_FAILED


def letzter_eintrag(uid: str) -> dict:
    eintraege = read_log(uid)["entries"]
    assert eintraege, (
        "Fixtur-Schutz: der Lauf hat keinen Protokoll-Eintrag hinterlassen -- "
        "dann wurde gar kein Versand versucht und die Erwartungen waeren trivial."
    )
    return eintraege[-1]
