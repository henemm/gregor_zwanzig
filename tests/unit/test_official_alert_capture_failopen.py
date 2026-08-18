"""TDD RED — Issue #1944, AC-7: ein Fehler im Herkunfts-Pfad verhindert den
Alarmversand NICHT.

SPEC: docs/specs/modules/feat_1944_warn_mitschnitt_herkunft.md (AC-7)

Zwei Fehlerquellen, beide am WIRKORT injiziert:

1. **Am Versandpunkt** -- eine Kennung, die beim Anfassen wirft
   (``__hash__``/``__bool__``/``__str__``). Der Versandpunkt sammelt die
   distinct Kennungen; genau dort muss der Fail-open-Mantel sitzen.
2. **An der Anreicherungs-Naht** -- ``warn_egress.observe_capture_id()``
   wirft beim Betreten. ``get_official_alerts_with_status`` muss die Warnung
   trotzdem liefern.

RED-Grund: ``OfficialAlert`` kennt kein ``capture_id``-Feld;
``warn_egress.observe_capture_id`` existiert nicht.

Mock-frei: die Fehlerquellen sind echte Python-Objekte/-Funktionen mit echter
Nebenwirkung (Exception), kein ``Mock()``/``patch()``. Der Versand laeuft
ueber die echten Dienste und die ``mail_sink``-Naht.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.helpers.alert_log_fixtures import read_log
from tests.helpers.briefing_imminent_fixtures import (
    TRIP_ZONE, clean_uid, fresh_uid, stunde_versetzt, write_trip, write_user_tier,
)
from tests.unit.test_trip_alert_official_alert_capture_correlation import (
    amtliche_warnung, trip_amtlicher_versand,
)


class _ExplodierendeKennung:
    """Echte Fehlerquelle: jede Verarbeitung dieser „Kennung" wirft.

    Zaehlt ihre Beruehrungen mit -- ohne mindestens eine Beruehrung bewacht
    der Test nichts (dann liefe der Herkunfts-Pfad an der injizierten Stelle
    gar nicht vorbei)."""

    def __init__(self) -> None:
        self.beruehrungen = 0

    def _knall(self):
        self.beruehrungen += 1
        raise RuntimeError("Herkunfts-Pfad: absichtlicher Fehler in der Kennung")

    def __hash__(self):
        self._knall()

    def __bool__(self):
        self._knall()

    def __str__(self):
        self._knall()

    def __eq__(self, other):
        self._knall()

    def __lt__(self, other):
        self._knall()


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


def test_ac7_positivkontrolle_die_fehlerquelle_schlaegt_wirklich_an():
    """Gegenprobe der Messmethode: das injizierte Objekt wirft nachweislich,
    sobald der Herkunfts-Pfad es anfasst (eigenes Objekt, damit der Zaehler
    des Fail-open-Tests unberuehrt bleibt)."""
    kennung = _ExplodierendeKennung()
    with pytest.raises(RuntimeError):
        {kennung}
    assert kennung.beruehrungen >= 1


def test_ac7_fehler_am_versandpunkt_verhindert_den_versand_nicht(nutzer):
    """AC-7: GIVEN die Herkunfts-Ermittlung am Versandpunkt wirft, WHEN der
    amtliche Trip-Alarm laeuft, THEN wird trotzdem verschickt und der
    ``alert_log``-Eintrag ist -- ohne Herkunfts-Feld -- vollstaendig."""
    uid = nutzer("ac7-versand")
    write_trip(
        uid, "t-1944-ac7",
        morgen_stunde=stunde_versetzt(5, zone=TRIP_ZONE),
        abend_stunde=stunde_versetzt(9, zone=TRIP_ZONE),
    )
    kennung = _ExplodierendeKennung()

    versendet, mails = trip_amtlicher_versand(
        uid, "t-1944-ac7", [amtliche_warnung(capture_id=kennung)],
    )

    assert versendet is True and len(mails) == 1, (
        f"Ein Fehler in der Beweisaufnahme darf den Alarm NIE ausfallen "
        f"lassen: versendet={versendet}, Mails={len(mails)}"
    )
    assert kennung.beruehrungen >= 1, (
        "Die injizierte Fehlerquelle wurde nie beruehrt — der Test bewacht "
        "dann nichts (der Versandpunkt fasst die Kennung gar nicht an)."
    )
    eintrag = read_log(uid)["entries"][-1]
    assert "capture_id" not in eintrag and "capture_ids" not in eintrag, (
        f"Nach einem Fehlschlag der Beweisaufnahme bleibt das Herkunfts-Feld "
        f"aus -- keine halbe Angabe: {eintrag!r}"
    )
    assert eintrag.get("reason") == "official_alert" and eintrag.get("changes_count") == 1, (
        f"Der Eintrag muss ansonsten vollstaendig sein: {eintrag!r}"
    )
    assert eintrag.get("channels_sent") == ["email"], (
        f"Der Kanal-Nachweis muss unveraendert bleiben: {eintrag!r}"
    )


def test_ac7_fehler_an_der_anreicherungs_naht_liefert_die_warnung_trotzdem(monkeypatch):
    """AC-7 (zweite Fehlerquelle): wirft der Rueckkanal selbst, liefert
    ``get_official_alerts_with_status`` die Warnung unveraendert -- ohne
    Kennung, aber ohne Ausfall."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import warn_egress
    from services.official_alerts.models import OfficialAlert

    aufrufe = {"n": 0}

    def _werfender_rueckkanal():
        aufrufe["n"] += 1
        raise RuntimeError("Rueckkanal: absichtlicher Fehler")

    # Reihenfolge ist wesentlich: erst pruefen, DANN ersetzen -- ein
    # ``setattr`` mit ``raising=False`` haette die Existenzpruefung trivial
    # wahr gemacht.
    assert hasattr(warn_egress, "observe_capture_id"), (
        "warn_egress.observe_capture_id() fehlt — der Rueckkanal aus AC-1 ist "
        "die Voraussetzung dieser Zusicherung."
    )
    monkeypatch.setattr(warn_egress, "observe_capture_id", _werfender_rueckkanal)

    jetzt = datetime.now(timezone.utc)
    warnung = OfficialAlert(
        source="test-1944", hazard="wind", level=3, label="Sturmwarnung",
        region_label="Testregion-1944",
        valid_from=jetzt - timedelta(hours=1), valid_to=jetzt + timedelta(hours=12),
    )

    class _EinfacheQuelle:
        @property
        def name(self) -> str:
            return "test-1944-failopen"

        def covers(self, lat: float, lon: float) -> bool:
            return True

        def fetch(self, lat: float, lon: float):
            return [warnung]

    sicherung = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        oa_base._REGISTERED_SOURCES.append(_EinfacheQuelle())
        alerts, unavailable = oa_base.get_official_alerts_with_status(46.62, 13.68)
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(sicherung)

    assert aufrufe["n"] >= 1, (
        "Die Naht hat den Rueckkanal nie geoeffnet — der Test bewacht dann nichts."
    )
    assert unavailable is False and len(alerts) == 1, (
        f"Ein Fehler im Herkunfts-Pfad darf die Quelle NICHT als ausgefallen "
        f"markieren: alerts={alerts!r}, unavailable={unavailable}"
    )
    assert alerts[0].capture_id is None, (
        f"Ohne verwertbare Herkunft bleibt die Kennung leer: {alerts[0]!r}"
    )
