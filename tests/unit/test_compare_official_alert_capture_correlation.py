"""TDD RED — Issue #1944, AC-3: der ``alert_log``-Eintrag des
Ortsvergleich-Pfads traegt dieselbe Herkunfts-Kennung wie der Trip-Pfad
(Paritaetsnachweis zu AC-2).

SPEC: docs/specs/modules/feat_1944_warn_mitschnitt_herkunft.md (AC-3)

RED-Grund: ``OfficialAlert`` kennt kein Feld ``capture_id``; der
Versandpunkt ``compare_official_alert.py`` (~Z. 201-214) reicht nichts
durch.

Mock-frei: echter ``CompareOfficialAlertService.check_all_compare_presets()``-
Lauf mit einer echten Quelle (strukturelles Subtyping ueber die echte
Registry, Muster ``tests/tdd/test_compare_official_alert.py``), echte
Presets/Orte auf Platte, Versand ueber die ``mail_sink``-Naht. Beide
Protokoll-Dateien werden geladen und ihr FELDSCHEMA verglichen -- nicht nur
je fuer sich auf „Feld vorhanden" geprueft.
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.loader import get_data_dir, save_location
from app.user import SavedLocation

from tests.helpers.alert_log_fixtures import read_log
from tests.helpers.compare_briefings import write_compare_briefings

LAT, LON = 46.62, 13.68


def _users_root() -> Path:
    from app.loader import get_data_root

    return get_data_root() / "users"


def _uid(prefix: str) -> str:
    return f"tdd-1944-{prefix}-{uuid.uuid4().hex[:6]}"


def _clean(user_id: str) -> None:
    d = _users_root() / user_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _settings() -> Settings:
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com", telegram_bot_token="", telegram_chat_id="",
    )


def _write_user_tier(user_id: str, tier: str = "premium") -> None:
    p = get_data_dir(user_id) / "user.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"tier": tier}), encoding="utf-8")


def _preset(preset_id: str, location_ids: list[str]) -> dict:
    return {
        "id": preset_id, "name": preset_id, "user_id": "default",
        "location_ids": location_ids, "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["e@x.invalid"], "created_at": "2026-07-11T00:00:00Z",
    }


class _KennungsQuelle:
    """Echte Warnquelle (kein Mock): liefert Warnungen mit vorgegebener
    Herkunfts-Kennung fuer genau einen Punkt."""

    def __init__(self, lat: float, lon: float, alerts: list) -> None:
        self._lat, self._lon, self._alerts = lat, lon, alerts

    @property
    def name(self) -> str:
        return "test-1944-compare-source"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float, **kwargs):
        return list(self._alerts)


def _warnung(*, capture_id, hazard: str = "extreme_heat", level: int = 3):
    from services.official_alerts.models import OfficialAlert

    jetzt = datetime.now(timezone.utc)
    return OfficialAlert(
        source="test-1944", hazard=hazard, level=level, label="Hitze",
        region_label="Testregion-1944",
        valid_from=jetzt - timedelta(hours=1), valid_to=jetzt + timedelta(hours=12),
        capture_id=capture_id,
    )


def _compare_versand(user_id: str, alerts: list) -> tuple[int, list]:
    """Echter Ortsvergleich-Lauf mit ausschliesslich der Test-Quelle."""
    import services.official_alerts.base as oa_base
    from services.compare_official_alert import CompareOfficialAlertService

    mails: list = []
    sicherung = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        oa_base._REGISTERED_SOURCES.append(_KennungsQuelle(LAT, LON, alerts))
        dienst = CompareOfficialAlertService(
            settings=_settings(), user_id=user_id,
            mail_sink=lambda *a, **kw: mails.append((a, kw)),
        )
        gesendet = dienst.check_all_compare_presets()
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(sicherung)
    return gesendet, mails


@pytest.fixture
def vergleichs_nutzer():
    vergeben: list[str] = []

    def _neu(kennung: str) -> str:
        user_id = _uid(kennung)
        _clean(user_id)
        _write_user_tier(user_id)
        save_location(
            SavedLocation(id="loc-a", name="Hermagor", lat=LAT, lon=LON, elevation_m=1000),
            user_id=user_id,
        )
        write_compare_briefings(_users_root() / user_id, [_preset("p-1944", ["loc-a"])])
        vergeben.append(user_id)
        return user_id

    yield _neu
    for user_id in vergeben:
        _clean(user_id)


def test_ac3_ortsvergleich_eintrag_traegt_die_kennung(vergleichs_nutzer):
    """AC-3: GIVEN eine amtliche Warnung wird im Ortsvergleich-Pfad
    verschickt und ihr ``OfficialAlert`` traegt eine ``capture_id``, WHEN der
    ``alert_log``-Eintrag geschrieben wird, THEN enthaelt er dasselbe
    ``capture_id``-Feld wie im Trip-Pfad."""
    uid = vergleichs_nutzer("ac3")
    gesendet, mails = _compare_versand(uid, [_warnung(capture_id="cap-cmp-1944-aaa")])
    assert gesendet == 1 and mails, (
        f"Voraussetzung: genau ein Vergleichs-Alarm muss rausgehen "
        f"(gesendet={gesendet}, Mails={len(mails)})."
    )

    eintrag = read_log(uid)["entries"][-1]
    assert eintrag.get("entity_type") == "compare", f"Falscher Eintragstyp: {eintrag!r}"
    assert eintrag.get("capture_id") == "cap-cmp-1944-aaa", (
        f"Der Vergleichs-Eintrag muss die Kennung der ausloesenden Warnung "
        f"tragen: {eintrag!r}"
    )


def test_ac3_paritaet_gleiches_feldschema_wie_der_trip_pfad(vergleichs_nutzer, tmp_path):
    """AC-3 (Paritaet): der Ortsvergleich-Eintrag und der Trip-Eintrag tragen
    die Herkunft im GLEICHEN Feld -- Vergleich der Schluesselmengen, nicht
    zweimal dieselbe Einzel-Zusicherung."""
    from tests.helpers.briefing_imminent_fixtures import (
        TRIP_ZONE, clean_uid, fresh_uid, stunde_versetzt, write_trip, write_user_tier,
    )
    from tests.unit.test_trip_alert_official_alert_capture_correlation import (
        amtliche_warnung, trip_amtlicher_versand,
    )

    cmp_uid = vergleichs_nutzer("ac3-par")
    gesendet, _ = _compare_versand(cmp_uid, [_warnung(capture_id="cap-paritaet")])
    assert gesendet == 1, "Voraussetzung: Vergleichs-Alarm muss rausgehen."
    cmp_eintrag = read_log(cmp_uid)["entries"][-1]

    trip_uid = fresh_uid("ac3-par-trip")
    clean_uid(trip_uid)
    write_user_tier(trip_uid, "premium")
    try:
        write_trip(
            trip_uid, "t-1944-ac3",
            morgen_stunde=stunde_versetzt(5, zone=TRIP_ZONE),
            abend_stunde=stunde_versetzt(9, zone=TRIP_ZONE),
        )
        versendet, _mails = trip_amtlicher_versand(
            trip_uid, "t-1944-ac3", [amtliche_warnung(capture_id="cap-paritaet")],
        )
        assert versendet is True, "Voraussetzung: Trip-Alarm muss rausgehen."
        trip_eintrag = read_log(trip_uid)["entries"][-1]
    finally:
        clean_uid(trip_uid)

    herkunft_cmp = {k: v for k, v in cmp_eintrag.items() if k.startswith("capture_id")}
    herkunft_trip = {k: v for k, v in trip_eintrag.items() if k.startswith("capture_id")}
    assert herkunft_cmp == herkunft_trip == {"capture_id": "cap-paritaet"}, (
        f"Beide Flaechen muessen die Herkunft im gleichen Feld tragen: "
        f"Vergleich={herkunft_cmp!r}, Trip={herkunft_trip!r}"
    )


def test_ac3_buendel_mehrerer_orte_schreibt_capture_ids(vergleichs_nutzer):
    """AC-6 im Vergleichs-Pfad (Paritaet zum Trip): zwei Warnungen aus zwei
    Mitschnitten -> ``capture_ids``-Liste, kein skalares ``capture_id``."""
    uid = vergleichs_nutzer("ac3-buendel")
    gesendet, _ = _compare_versand(uid, [
        _warnung(capture_id="cap-zzz", hazard="extreme_heat"),
        _warnung(capture_id="cap-aaa", hazard="wind"),
    ])
    assert gesendet == 1, "Voraussetzung: das Buendel muss als EIN Alarm rausgehen."

    eintrag = read_log(uid)["entries"][-1]
    assert eintrag.get("capture_ids") == ["cap-aaa", "cap-zzz"], (
        f"Beide Kennungen sortiert im Listenfeld erwartet: {eintrag!r}"
    )
    assert "capture_id" not in eintrag, (
        f"Keine willkuerliche Auswahl einer Kennung: {eintrag!r}"
    )
