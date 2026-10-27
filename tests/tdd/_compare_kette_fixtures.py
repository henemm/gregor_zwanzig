"""Gemeinsamer Aufbau fuer die Ortsvergleich-Kette (Issue #2422 S5).

Kein Test-Modul (fuehrender Unterstrich). Geteilt von
``test_compare_einstellung_auslieferung_kette.py`` (Briefing, Slots, Tages-
stand) und ``test_compare_alarm_einstellung_auslieferung_kette.py`` (Alarme).

Grundsatz: das Preset liegt als ROHES JSON der Fixture-Datei
(``tests/fixtures/compare_kette/*.json``, Persistenzformat des Editors) im
Nutzerverzeichnis, wird vom ECHTEN ``load_compare_presets`` gelesen und ueber
``send_one_compare_preset`` versendet. Die einzigen Naehte:

* Wetter: ``ComparisonEngine.run`` (echte Subklasse, wie in
  ``test_compare_dispatch_channel_fanout.py``) -- Werte je ORT-KENNUNG, weil
  ``run_comparison_parallel`` je Ort einen Lauf macht (ein Index waere immer 0).
* Transport: der geteilte Aufzeichner (``tests/helpers/transport_mitschrift.py``)
  -- KEINE ``mail_sink``/``sms_sink``/``telegram_sink``, sonst wuerde der
  Aufzeichner umgangen.

Nutzerkennungen tragen bewusst kein "test"/"tdd" (Herkunftssperre #2406).
"""
from __future__ import annotations

import copy
import json
from datetime import date, datetime, timezone
from pathlib import Path

from app.config import Settings
from app.loader import (
    compare_preset_to_dict, get_data_dir, get_data_root, load_compare_presets,
    save_location,
)
from app.models import ForecastDataPoint, ThunderLevel
from app.user import SavedLocation
from tests.tdd._einstellung_auslieferung_fixtures import TRANSPORT_ENV, frisches_profil

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "compare_kette"

#: Orts-Kennung -> (Name, lat, lon). Reihenfolge = Reihenfolge in ``location_ids``.
ORTE = {
    "loc-ibk": ("Innsbruck", 47.27, 11.39),
    "loc-bz": ("Bozen", 46.50, 11.35),
}
ORTSNAMEN = [v[0] for v in ORTE.values()]

TARGET_DATE = date(2026, 7, 8)

#: Tageswerte je Ort-Kennung -- paarweise verschieden je Metrik UND je Ort.
_WERTE = {
    "loc-ibk": dict(temp_max=22.0, temp_min=12.0, wind_max=11.0, gust_max=19.0,
                    cloud_avg=35, sunny_hours=6.0, snow_depth_cm=20.0,
                    snow_new_cm=3.0, precip_1h=1.5, pop=10),
    "loc-bz": dict(temp_max=27.0, temp_min=15.0, wind_max=14.0, gust_max=23.0,
                   cloud_avg=48, sunny_hours=8.0, snow_depth_cm=25.0,
                   snow_new_cm=6.0, precip_1h=2.0, pop=20),
}


def fixture_dict(name: str) -> dict:
    """Rohes ``json.load`` der Fixture-Datei -- frische Kopie je Aufruf."""
    return copy.deepcopy(json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Nutzer, Orte, Preset-Datei
# ---------------------------------------------------------------------------


def nutzer_anlegen(tier: str = "premium") -> str:
    """Frisches Nutzerprofil (eigene Kennung, eigene Empfaenger) mit Tarif."""
    return frisches_profil(tier=tier)


def orte_anlegen(uid: str) -> None:
    for lid, (name, lat, lon) in ORTE.items():
        save_location(SavedLocation(id=lid, name=name, lat=lat, lon=lon, elevation_m=1000), user_id=uid)


def preset_ablegen(uid: str, preset: dict) -> Path:
    """Preset-Datei UNVERAENDERT ins Nutzerverzeichnis (``briefings/<id>.json``,
    ``kind="vergleich"`` steht schon im Fixture). Kein ``write_compare_briefings``:
    der Helfer wuerde ``morning_time`` einfuegen und den Altbestand-Fall (AC-12)
    verfaelschen."""
    ordner = get_data_dir(uid) / "briefings"
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / f"{preset['id']}.json"
    pfad.write_text(json.dumps(preset, ensure_ascii=False, indent=2), encoding="utf-8")
    return pfad


def preset_laden(uid: str, preset_id: str) -> dict:
    """Den ECHTEN Loader benutzen; ein nicht gefundenes Preset ist ein Fehler
    (Vorbedingung), nie ein stiller Leerlauf."""
    treffer = [p for p in load_compare_presets(uid) if p.id == preset_id]
    assert len(treffer) == 1, f"Vorbedingung verletzt: Preset {preset_id!r} nicht ladbar fuer {uid!r}"
    return compare_preset_to_dict(treffer[0])


def alle_orte(uid: str) -> list[SavedLocation]:
    from app.loader import load_all_locations

    orte = load_all_locations(user_id=uid)
    assert {o.id for o in orte} >= set(ORTE), f"Vorbedingung verletzt: Orte fehlen fuer {uid!r}"
    return orte


# ---------------------------------------------------------------------------
# Settings / Transport
# ---------------------------------------------------------------------------


def transport_einrichten(monkeypatch) -> None:
    """Jedes Transportfeld ausdruecklich unbrauchbar belegt (#1477)."""
    for name, wert in TRANSPORT_ENV.items():
        monkeypatch.setenv(name, wert)


def settings_fuer(uid: str, *, telegram: bool = True, sms: bool = True) -> Settings:
    """Settings des Nutzers (Empfaenger aus SEINEM Profil). ``telegram``/``sms``
    False = global nicht sendefaehig (Felder geleert)."""
    s = Settings().with_user_profile(uid)
    update: dict = {}
    if not telegram:
        update.update({"telegram_bot_token": None, "telegram_chat_id": None})
    if not sms:
        update.update({"sms_to": None})
    return s.model_copy(update=update) if update else s


def sms_tageslimit_erschoepfen(uid: str) -> None:
    """Tageszaehler des Nutzers auf 'weit ueber Limit' -- genau die Datei, die
    ``sms_daily_limit`` liest (``sms_daily_count.json``, UTC-Tag)."""
    heute = datetime.now(timezone.utc).date().isoformat()
    (get_data_dir(uid) / "sms_daily_count.json").write_text(
        json.dumps({"date": heute, "sms": 999, "premium_sms": 999})
    )


# ---------------------------------------------------------------------------
# Wetter-Naht
# ---------------------------------------------------------------------------


def _dp(hour: int, werte: dict) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour, 0),
        t2m_c=22.0, wind_chill_c=21.0, wind10m_kmh=11.0, gust_kmh=19.0,
        precip_1h_mm=werte["precip_1h"], cloud_total_pct=35, uv_index=5.0,
        thunder_level=ThunderLevel.NONE, pop_pct=werte["pop"], visibility_m=9000,
    )


def engine_naht(monkeypatch) -> None:
    """``ComparisonEngine.run`` liefert je Ort-Kennung feste Tageswerte (echte
    Subklasse). Der Δ-Anker-Schreiber holt echtes Nowcast-Wetter (Netz) und ist
    nicht Pruefgegenstand -- neutralisiert wie im Vorbild."""
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod
    from app.user import ComparisonResult, LocationResult

    original = ce_mod.ComparisonEngine

    class RecordingEngine(original):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            locations = kwargs.get("locations")
            if locations is None and args:
                locations = args[0]
            ergebnisse = []
            for i, loc in enumerate(list(locations or [])):
                w = _WERTE[loc.id]
                ergebnisse.append(LocationResult(
                    location=loc, score=90 - 7 * i,
                    temp_max=w["temp_max"], temp_min=w["temp_min"],
                    wind_max=w["wind_max"], gust_max=w["gust_max"],
                    cloud_avg=w["cloud_avg"], sunny_hours=w["sunny_hours"],
                    snow_depth_cm=w["snow_depth_cm"], snow_new_cm=w["snow_new_cm"],
                    official_alerts=[],
                    hourly_data=[_dp(9, w), _dp(12, w), _dp(15, w)],
                ))
            return ComparisonResult(
                locations=ergebnisse,
                time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", TARGET_DATE),
                created_at=datetime(2026, 7, 8, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", RecordingEngine)
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)


# ---------------------------------------------------------------------------
# Versand
# ---------------------------------------------------------------------------


def briefing_senden(
    uid: str, preset_id: str, settings: Settings, *,
    target_date: date = TARGET_DATE, tage_ab_ortstag: int = 0, **sinks,
):
    """Preset ueber den echten Loader lesen und ueber ``send_one_compare_preset``
    versenden -- OHNE Sinks (der Aufzeichner am Ausgang sieht die Sendung)."""
    from services.scheduler_dispatch_service import send_one_compare_preset

    preset = preset_laden(uid, preset_id)
    return send_one_compare_preset(
        preset, settings, uid, str(get_data_root()),
        all_locations_cache=alle_orte(uid),
        target_date=target_date, tage_ab_ortstag=tage_ab_ortstag, **sinks,
    )
