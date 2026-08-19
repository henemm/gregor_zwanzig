"""TDD RED — Issue #1944, AC-6: ein Versand aus MEHREREN Mitschnitten
erzeugt ein additives ``capture_ids``-Listenfeld; ``capture_id`` bleibt
UNGESETZT (keine willkuerliche Auswahl einer der Kennungen).

SPEC: docs/specs/modules/feat_1944_warn_mitschnitt_herkunft.md (AC-6)

Genau der Vorfall aus #1929: zwei byte-identische Meldungen, keine Zuordnung
moeglich. Eine der beiden Kennungen zu waehlen wuerde die Frage wieder
verschliessen, die dieses Ticket beantworten soll.

RED-Grund: ``OfficialAlert`` kennt kein ``capture_id``-Feld und
``alert_log.append_entry()`` keinen ``capture_ids``-Parameter.

Mock-frei: echter ``_send_official_alert_only()``-Lauf fuer den Buendel-Fall
(die Aufrufstelle, an der die Entscheidung faellt) plus ein direkter
``append_entry()``-Aufruf fuer den Serialisierungs-Vertrag. Geschriebene
Dateien werden geladen (``json.loads``) und strukturell verglichen.
"""
from __future__ import annotations

import pytest

from services import alert_log

from tests.helpers.alert_log_fixtures import read_log
from tests.helpers.briefing_imminent_fixtures import (
    TRIP_ZONE,
    clean_uid,
    fresh_uid,
    stunde_versetzt,
    write_trip,
    write_user_tier,
)
from tests.unit.test_trip_alert_official_alert_capture_correlation import (
    amtliche_warnung,
    trip_amtlicher_versand,
)


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


def test_ac6_buendel_aus_zwei_mitschnitten_schreibt_capture_ids_liste(nutzer):
    """AC-6: GIVEN ein einzelner Versand buendelt amtliche Warnungen aus zwei
    verschiedenen Mitschnitten, WHEN der ``alert_log``-Eintrag geschrieben
    wird, THEN enthaelt er ``capture_ids`` mit beiden entdoppelten Kennungen
    (sortiert) und KEIN skalares ``capture_id``."""
    uid = nutzer("ac6-buendel")
    write_trip(
        uid, "t-1944-ac6",
        morgen_stunde=stunde_versetzt(5, zone=TRIP_ZONE),
        abend_stunde=stunde_versetzt(9, zone=TRIP_ZONE),
    )

    versendet, mails = trip_amtlicher_versand(uid, "t-1944-ac6", [
        amtliche_warnung(capture_id="cap-zzz-zweite", hazard="wind"),
        amtliche_warnung(capture_id="cap-aaa-erste", hazard="rain"),
    ])
    assert versendet is True and mails, (
        f"Voraussetzung: das Buendel muss verschickt werden "
        f"(versendet={versendet}, Mails={len(mails)})."
    )

    eintrag = read_log(uid)["entries"][-1]
    assert eintrag.get("capture_ids") == ["cap-aaa-erste", "cap-zzz-zweite"], (
        f"Beide Kennungen muessen sortiert und entdoppelt im Listenfeld stehen: "
        f"{eintrag!r}"
    )
    assert "capture_id" not in eintrag, (
        f"Bei mehreren Kennungen darf KEINE willkuerlich als skalares Feld "
        f"gewaehlt werden: {eintrag!r}"
    )
    assert eintrag.get("changes_count") == 2, (
        f"Der Eintrag muss im Uebrigen unveraendert bleiben: {eintrag!r}"
    )


def test_ac6_gleiche_kennung_zweimal_bleibt_ein_skalares_feld(nutzer):
    """Abgrenzung: tragen beide Warnungen DIESELBE Kennung, ist die Herkunft
    eindeutig -- dann bleibt es beim skalaren ``capture_id`` (die Liste waere
    nur Rauschen)."""
    uid = nutzer("ac6-gleich")
    write_trip(
        uid, "t-1944-ac6b",
        morgen_stunde=stunde_versetzt(5, zone=TRIP_ZONE),
        abend_stunde=stunde_versetzt(9, zone=TRIP_ZONE),
    )

    versendet, _mails = trip_amtlicher_versand(uid, "t-1944-ac6b", [
        amtliche_warnung(capture_id="cap-eine-quelle", hazard="wind"),
        amtliche_warnung(capture_id="cap-eine-quelle", hazard="rain"),
    ])
    assert versendet is True, "Voraussetzung: das Buendel muss verschickt werden."

    eintrag = read_log(uid)["entries"][-1]
    assert eintrag.get("capture_id") == "cap-eine-quelle", (
        f"Eine einzige (doppelt vorkommende) Kennung bleibt skalar: {eintrag!r}"
    )
    assert "capture_ids" not in eintrag, (
        f"Kein Listenfeld bei eindeutiger Herkunft: {eintrag!r}"
    )


def test_ac6_append_entry_serialisiert_capture_ids_sortiert_und_entdoppelt():
    """Der additive Parameter selbst (``alert_log.append_entry``): die Liste
    wird sortiert und entdoppelt geschrieben, Alt-Eintraege bleiben
    unberuehrt."""
    uid = fresh_uid("ac6-append")
    clean_uid(uid)
    try:
        alert_log.append_entry(
            uid, entity_id="trip-1944", entity_type="trip", changes_count=2,
            severity="moderate", reason=alert_log.REASON_OFFICIAL_ALERT,
            effective_channels=["email"], sent_channels=["email"],
            capture_ids=["cap-b", "cap-a", "cap-b"],
        )
        eintrag = read_log(uid)["entries"][-1]
        assert eintrag.get("capture_ids") == ["cap-a", "cap-b"], (
            f"capture_ids muss sortiert und entdoppelt sein: {eintrag!r}"
        )
        assert "capture_id" not in eintrag

        # Leere Liste ist wie „keine Kennung": kein Feld (Bestandsverhalten).
        alert_log.append_entry(
            uid, entity_id="trip-1944", entity_type="trip", changes_count=1,
            severity="moderate", reason=alert_log.REASON_OFFICIAL_ALERT,
            effective_channels=["email"], sent_channels=["email"],
            capture_ids=[],
        )
        leer = read_log(uid)["entries"][-1]
        assert "capture_ids" not in leer and "capture_id" not in leer, (
            f"Eine leere Kennungs-Liste darf kein Feld erzeugen: {leer!r}"
        )
    finally:
        clean_uid(uid)
