"""TDD RED — Issue #1944, AC-2: der ``alert_log``-Eintrag des Trip-Pfads
traegt die ``capture_id`` des ausloesenden Mitschnitts.

SPEC: docs/specs/modules/feat_1944_warn_mitschnitt_herkunft.md (AC-2)

RED-Grund: ``OfficialAlert`` kennt kein Feld ``capture_id`` -- der
Konstruktoraufruf scheitert mit ``TypeError``. Nach dem additiven Feld muss
zusaetzlich ``_send_official_alert_only`` die Kennung an
``alert_log.append_entry()`` durchreichen.

Mock-frei: echter ``TripAlertService._send_official_alert_only()``-Lauf (DIE
Aufrufstelle des Protokoll-Eintrags, ``trip_alert.py`` ~Z. 1765), echter Trip
auf Platte, Transport ueber die vorhandene ``mail_sink``-Naht. Der
geschriebene ``alert_log.json`` wird per ``json.loads`` geladen und
strukturell verglichen -- kein String-Check.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.helpers.briefing_imminent_fixtures import (
    TRIP_ZONE,
    clean_uid,
    fresh_uid,
    settings_email_only,
    load_trip_obj,
    stunde_versetzt,
    write_trip,
    write_user_tier,
)
from tests.helpers.alert_log_fixtures import read_log


def _slot_fern() -> int:
    """Briefing-Stunde weit weg -- die Vorlauf-Sperre darf nicht greifen."""
    return stunde_versetzt(5, zone=TRIP_ZONE)


def _slot_weiter_weg() -> int:
    return stunde_versetzt(9, zone=TRIP_ZONE)


@pytest.fixture
def nutzer():
    vergeben: list[str] = []

    def _neu(kennung: str) -> str:
        user_id = fresh_uid(kennung)
        clean_uid(user_id)
        write_user_tier(user_id, "premium")
        vergeben.append(user_id)
        return user_id

    yield _neu
    for user_id in vergeben:
        clean_uid(user_id)


def amtliche_warnung(*, capture_id, hazard: str = "wind", level: int = 3):
    from services.official_alerts.models import OfficialAlert

    jetzt = datetime.now(timezone.utc)
    return OfficialAlert(
        source="test-1944", hazard=hazard, level=level, label="Sturmwarnung",
        region_label="Testregion-1944",
        valid_from=jetzt - timedelta(hours=1), valid_to=jetzt + timedelta(hours=12),
        capture_id=capture_id,
    )


def trip_amtlicher_versand(user_id: str, trip_id: str, warnungen: list):
    """Echter ``_send_official_alert_only()``-Lauf mit vorgegebenen Warnungen.

    Returns ``(versendet, mail_sink-Aufrufe)``."""
    from services.trip_alert import TripAlertService

    mails: list = []
    dienst = TripAlertService(
        settings=settings_email_only(), throttle_hours=2, user_id=user_id,
        mail_sink=lambda *a, **kw: mails.append((a, kw)),
    )
    versendet = dienst._send_official_alert_only(
        load_trip_obj(user_id, trip_id), [(w, ["1"]) for w in warnungen],
    )
    return bool(versendet), mails


def test_ac2_alert_log_eintrag_traegt_die_kennung_der_ausloesenden_warnung(nutzer):
    """AC-2: GIVEN eine amtliche Warnung wird im Trip-Pfad tatsaechlich
    verschickt und ihr ``OfficialAlert`` traegt eine ``capture_id``, WHEN
    ``_send_official_alert_only`` den ``alert_log``-Eintrag schreibt, THEN
    enthaelt dieser Eintrag ein ``capture_id``-Feld mit exakt diesem Wert."""
    uid = nutzer("ac2-trip")
    write_trip(uid, "t-1944-ac2", morgen_stunde=_slot_fern(), abend_stunde=_slot_weiter_weg())

    versendet, mails = trip_amtlicher_versand(
        uid, "t-1944-ac2", [amtliche_warnung(capture_id="cap-trip-1944-aaa")],
    )
    assert versendet is True and mails, (
        f"Voraussetzung: die Warnung muss verschickt werden "
        f"(versendet={versendet}, Mails={len(mails)})."
    )

    eintraege = read_log(uid)["entries"]
    assert eintraege, "Kein alert_log-Eintrag geschrieben."
    eintrag = eintraege[-1]
    assert eintrag.get("reason") == "official_alert", (
        f"Falscher Eintragstyp: {eintrag!r}"
    )
    assert eintrag.get("capture_id") == "cap-trip-1944-aaa", (
        f"Der Protokoll-Eintrag muss die Kennung der ausloesenden Warnung "
        f"tragen: {eintrag!r}"
    )
    assert "capture_ids" not in eintrag, (
        f"Bei genau EINER Kennung bleibt das Listenfeld ungesetzt: {eintrag!r}"
    )


def test_ac2_ohne_kennung_bleibt_der_eintrag_wie_bisher(nutzer):
    """Bestandsschutz: traegt die Warnung KEINE Kennung (Mehrdeutigkeit oder
    Fail-open-Fehlschlag), wird weder ``capture_id`` noch ``capture_ids``
    geschrieben -- der Eintrag bleibt im Uebrigen vollstaendig."""
    uid = nutzer("ac2-ohne")
    write_trip(uid, "t-1944-ac2b", morgen_stunde=_slot_fern(), abend_stunde=_slot_weiter_weg())

    versendet, mails = trip_amtlicher_versand(
        uid, "t-1944-ac2b", [amtliche_warnung(capture_id=None)],
    )
    assert versendet is True and mails, "Voraussetzung: die Warnung muss verschickt werden."

    eintrag = read_log(uid)["entries"][-1]
    assert "capture_id" not in eintrag and "capture_ids" not in eintrag, (
        f"Ohne Kennung darf kein Herkunfts-Feld entstehen: {eintrag!r}"
    )
    assert eintrag.get("changes_count") == 1 and eintrag.get("channels_sent") == ["email"], (
        f"Der Eintrag muss ansonsten vollstaendig bleiben: {eintrag!r}"
    )
