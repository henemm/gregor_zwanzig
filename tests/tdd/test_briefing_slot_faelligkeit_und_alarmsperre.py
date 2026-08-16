"""TDD RED — #1897: Faelligkeitsliste und Alarm-Vorlauf-Sperre bei offenem
Briefing-Vermerk.

SPEC: docs/specs/modules/fix_1897_verwaister_briefing_slot.md (AC-2, AC-6,
AC-9). AC-1/AC-3/AC-4/AC-5/AC-7/AC-8 stehen in
``test_briefing_slot_verwaister_claim.py``, dort auch die vollstaendige Liste
der neuen Schnittstellen-Namen.

Die beiden Wirkorte stellen VERSCHIEDENE Fragen (Spec, „Implementation
Details"):

* ``_collect_due_trips()`` — „wird jetzt ein Versand stattfinden?" Ein
  LEBENDIGER Vermerk (juenger als ``CLAIM_TTL``) haelt den Trip aus der Liste,
  ein VERWAISTER bringt ihn zurueck. Praedikat:
  ``BriefingSlotStore.is_recorded_or_claimed(..., moment=...)``.
* ``trip_briefing_due_at()`` / ``check_briefing_imminent()`` — „steht fuer
  diesen Slot noch ein Briefing aus?" Solange ``outcome`` nicht gesetzt ist,
  kam nichts raus: die Alarm-Sperre aus #1594 muss halten, UNABHAENGIG vom
  Alter des Vermerks. Praedikat: ``is_recorded()``, ab jetzt „abgeschlossen".

Nachbar zu R6 in ``test_trip_alert_briefing_imminent.py`` — dieselben
mock-freien Bausteine (``tests/helpers/briefing_imminent_fixtures.py``),
dieselbe Messnaht: gezaehlte Wetterabrufe, 0 = vor dem Abruf gesperrt.

Die Uhr wird eingefroren, weil ``check_and_send_alerts()`` seinen Zeitpunkt
konstruktionsbedingt selbst holt (Begruendung wie im Kopf von AC-5/R6 der
Nachbardatei); alle geprueften Entscheidungen bekommen ihren Zeitpunkt
trotzdem als PARAMETER. Ortszone des Trips ist ``Atlantic/Reykjavik``
(ganzjaehrig UTC+0), Ortsstunde = UTC-Stunde.

Pfadregel #1409: alles relativ zu DIESER Datei bzw. ueber ``app.loader``.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import get_data_dir  # noqa: E402
from services import briefing_slots  # noqa: E402
from services.briefing_slots import BriefingSlotStore  # noqa: E402

from tests.helpers.briefing_imminent_fixtures import (  # noqa: E402
    TRIP_ZONE,
    fresh_uid,
    load_trip_obj,
    ortstag,
    trip_change_alert_run,
    write_trip,
    write_user_tier,
)

TRIP = "t-1897"
SLOT_STUNDE = 7
ABEND_STUNDE = 18
TAG_DER_MESSUNG = datetime(2026, 3, 15, tzinfo=timezone.utc)


def _ttl() -> int:
    """``CLAIM_TTL`` zur LAUFZEIT — nie als getippte Zahl im Test."""
    return briefing_slots.CLAIM_TTL


def _slot(minuten: int = 0) -> datetime:
    return TAG_DER_MESSUNG.replace(hour=SLOT_STUNDE) + timedelta(minutes=minuten)


def _nutzer(kennung: str) -> str:
    """Eigene, sprechende Kennung je Fall (Mandantentrennung, nie ``default``).
    Aufraeumen ist nicht noetig: ``_isolate_data_root`` gibt jedem Test einen
    frischen Daten-Baum."""
    user_id = fresh_uid(kennung)
    write_user_tier(user_id)
    return user_id


def _offener_vermerk(user_id: str, local_day: date, recorded_at: datetime) -> None:
    """Der Zustand, den ein HART BEENDETER Versandprozess hinterlaesst: ein
    Eintrag im Bestandsschema mit ``outcome: null``.

    Bewusst roh geschrieben statt ueber ``reserve(..., moment=...)`` — so misst
    der Test das gemeldete FEHLVERHALTEN und nicht bloss eine fehlende
    Signatur.
    """
    pfad = get_data_dir(user_id) / "briefing_slots.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"entries": [{
        "trip_id": TRIP, "slot": "morning", "local_day": local_day.isoformat(),
        "recorded_at": recorded_at.isoformat(), "outcome": None,
    }]}, indent=2), encoding="utf-8")


def _scheduler(user_id: str):
    """Echter ``TripReportSchedulerService``, bei dem nur die zwei Naehte zum
    Netz ersetzt sind — Versand und Wetterabruf. Beide durch echte
    Implementierungen mit echten DTOs, kein Mock."""
    from app.models import SegmentWeatherData, SegmentWeatherSummary
    from services.trip_report_scheduler import TripReportSchedulerService

    class _OhneNetz(TripReportSchedulerService):
        versandversuche: list = []

        def _send_trip_report_outcome(self, trip, report_type, **kwargs):
            type(self).versandversuche.append((trip.id, report_type))
            return "sent"

        def _fetch_weather(self, segments, provider=None):
            # Alle Abschnitte weiterhin ohne Daten -> der #1012-Marker wird
            # hochgezaehlt statt weggeraeumt (`_bump_pending_marker_attempts`).
            return [
                SegmentWeatherData(
                    segment=s, timeseries=None, aggregated=SegmentWeatherSummary(),
                    fetched_at=datetime.now(timezone.utc), provider="test",
                    has_error=True,
                )
                for s in segments
            ]

    _OhneNetz.versandversuche = []
    return _OhneNetz(user_id=user_id)


def _marker(user_id: str) -> dict | None:
    from services.trip_report_scheduler import _load_pending_entries

    pfad = get_data_dir(user_id) / "pending_briefings.json"
    for eintrag in _load_pending_entries(pfad).get("entries", []):
        if eintrag.get("trip_id") == TRIP:
            return eintrag
    return None


def _faellige_ids(scheduler, now_utc: datetime) -> set:
    return {trip.id for trip, _, _ in scheduler._collect_due_trips(now_utc)}


def _steht_aus(user_id: str, trip, moment: datetime) -> bool:
    """``trip_briefing_due_at()`` DIREKT — ohne die Abtastung darueber.

    🔴 ``check_briefing_imminent()`` tastet dieses Praedikat ueber ein Fenster
    von ``BRIEFING_VORLAUF_MINUTEN`` ab und meldet „gesperrt", sobald IRGENDEIN
    Abtastpunkt ``True`` liefert. Ein Vermerk altert waehrend dieses Fensters
    mit — eine altersabhaengige Antwort kann also weiter hinten zufaellig
    richtig herauskommen, obwohl vorne die falsche Frage gestellt wurde. Deshalb
    wird das Praedikat zusaetzlich an EINEM Zeitpunkt direkt befragt (Adversary
    F004).
    """
    from services.trip_report_scheduler import trip_briefing_due_at

    return trip_briefing_due_at(trip, moment, user_id=user_id)


def _sperre_greift(user_id: str, trip, now_utc: datetime) -> bool:
    """``check_briefing_imminent()`` (#1594) mit dem ECHTEN Trip-Praedikat —
    genau so verdrahtet wie im Produktivpfad (``trip_alert.py``)."""
    from services.alert_gate import check_briefing_imminent

    return check_briefing_imminent(
        user_id=user_id, entity_id=trip.id, entity_type="trip",
        now=now_utc, zone=TRIP_ZONE,
        briefing_due_at=lambda moment: _steht_aus(user_id, trip, moment),
    )


# ---------------------------------------------------------------------------
# AC-2 — offener Vermerk haelt die Alarm-Vorlauf-Sperre
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "vermerk, erwartet_gesperrt",
    [("offen_jung", True), ("offen_verwaist", True), ("abgeschlossen", False)],
)
def test_ac2_offener_vermerk_haelt_die_alarm_sperre(
    vermerk, erwartet_gesperrt, monkeypatch,
):
    """AC-2.

    GIVEN fuer einen Trip steht ein Briefing im Faelligkeitsfenster an und es
    liegt ein Vermerk ohne Ausgang vor, weil der Versand laeuft oder
    abgebrochen ist
    WHEN im selben Zeitraum ein Aenderungs-Alarm ausgewertet wird
    THEN wird der Alarm nicht als eigenstaendige Nachricht verschickt, weil das
    Briefing noch aussteht.

    Beide Alter werden geprueft: ``outcome: null`` heisst „es kam nichts raus",
    unabhaengig davon, ob der Versand noch laeuft oder abgebrochen ist. Der
    dritte Fall ist die Gegenprobe — mit gesetztem Ausgang ist das Briefing
    zugestellt, der Alarm muss regulaer rausgehen. Ohne ihn bewiese „0 Abrufe"
    nur, dass irgendetwas den Lauf stoppt.

    Kein Briefing-Anker: ein hart beendeter Prozess setzt ihn nie
    (``_anchor_and_reset`` laeuft erst NACH dem Versandaufruf) — genau deshalb
    haengt die Sperre hier allein am Vermerk.

    🔴 ``CLAIM_TTL`` wird fuer diesen Fall hochgesetzt (Adversary F004): der
    „junge" Vermerk muss ueber das GESAMTE Abtastfenster von
    ``check_briefing_imminent()`` jung bleiben. Sonst altert er waehrend der
    Abtastung ueber die Frist hinaus, und ein Praedikat, das faelschlich aufs
    ALTER statt auf den AUSGANG sieht, kippt weiter hinten zufaellig auf das
    erwartete Ergebnis zurueck — die Zusicherung waere blind. Die Frist wirkt
    hier ausserdem nirgends sonst: der Alarm-Lauf fragt allein ``is_recorded``.

    RED-Charakter: Fehlernachweis — heute zaehlt der offene Vermerk als
    erledigt, der Trip gilt als nicht mehr faellig, die Sperre faellt und der
    Alarm geht raus, obwohl nie ein Briefing kam.
    """
    from freezegun import freeze_time

    monkeypatch.setattr(briefing_slots, "CLAIM_TTL", 2 * 60 * 60)
    jetzt = _slot(5)
    with freeze_time(jetzt):
        uid = _nutzer(f"1897-ac2-{vermerk}")
        write_trip(uid, TRIP, morgen_stunde=SLOT_STUNDE, abend_stunde=ABEND_STUNDE)
        tag = ortstag(TRIP_ZONE)
        if vermerk == "abgeschlossen":
            BriefingSlotStore(uid).record_outcome(TRIP, "morning", tag, "sent")
        else:
            alter = 60 if vermerk == "offen_jung" else _ttl() * 2
            _offener_vermerk(uid, tag, jetzt - timedelta(seconds=alter))
        abrufe = trip_change_alert_run(uid, TRIP)

    if erwartet_gesperrt:
        assert abrufe == 0, (
            f"Vermerk '{vermerk}': ohne gesetzten Ausgang hat der Nutzer kein "
            f"Briefing bekommen — der Aenderungsalarm muss schweigen und darf "
            f"kein Wetter abrufen, es waren {abrufe} Abrufe."
        )
    else:
        assert abrufe >= 1, (
            f"Vermerk '{vermerk}': das Briefing ist zugestellt, der Alarm muss "
            f"regulaer pruefen — es waren {abrufe} Abrufe. Ohne diese "
            f"Gegenprobe misst der Test die Sperre gar nicht."
        )


@pytest.mark.parametrize(
    "vermerk, steht_aus",
    [("offen_jung", True), ("offen_verwaist", True), ("abgeschlossen", False)],
)
def test_ac2_faelligkeits_praedikat_fragt_nach_dem_ausgang_nicht_nach_dem_alter(
    vermerk, steht_aus,
):
    """AC-2, an seinem WIRKORT statt an der Abtastung darueber.

    GIVEN ein Vermerk ohne Ausgang liegt vor — einmal jung (Versand laeuft),
    einmal verwaist (Prozess hart beendet)
    WHEN ``trip_briefing_due_at()`` an EINEM Zeitpunkt befragt wird
    THEN meldet es in BEIDEN Faellen „steht noch aus", und nur der
    abgeschlossene Vermerk beendet die Faelligkeit.

    Die Spec teilt die beiden Praedikate nach der FRAGE auf: hier „steht noch
    ein Briefing aus?" (allein der Ausgang), in ``_collect_due_trips()`` „wird
    jetzt ein Versand stattfinden?" (Ausgang UND Alter). Vertauscht man die
    beiden an ihren Wirkorten, ist genau das kaputt — und ueber
    ``check_briefing_imminent()`` allein bleibt es unsichtbar, weil dessen
    Abtastfenster den Kipppunkt der Alters-Antwort ueberdeckt (Adversary F004).

    Der dritte Fall ist die Gegenprobe: ohne ihn waere „True" auch von einem
    Praedikat erfuellt, das immer True liefert.
    """
    from freezegun import freeze_time

    jetzt = _slot(5)
    with freeze_time(jetzt):
        uid = _nutzer(f"1897-ac2-direkt-{vermerk}")
        write_trip(uid, TRIP, morgen_stunde=SLOT_STUNDE, abend_stunde=ABEND_STUNDE)
        tag = ortstag(TRIP_ZONE)
        if vermerk == "abgeschlossen":
            BriefingSlotStore(uid).record_outcome(TRIP, "morning", tag, "sent")
        else:
            alter = 60 if vermerk == "offen_jung" else _ttl() * 2
            _offener_vermerk(uid, tag, jetzt - timedelta(seconds=alter))
        ergebnis = _steht_aus(uid, load_trip_obj(uid, TRIP), jetzt)

    assert ergebnis is steht_aus, (
        f"Vermerk '{vermerk}': die Faelligkeit dieses Slots haengt allein am "
        f"AUSGANG des Vermerks, nicht an seinem Alter — erwartet "
        f"{steht_aus}, gemeldet {ergebnis}."
    )


# ---------------------------------------------------------------------------
# AC-6 — lebendiger Vermerk: Trip nicht faellig, Nachliefer-Marker ueberlebt
# ---------------------------------------------------------------------------

def test_ac6_lebendiger_vermerk_haelt_den_trip_aus_der_faelligkeitsliste():
    """AC-6.

    GIVEN ein Vermerk ohne Ausgang ist juenger als ``CLAIM_TTL``
    WHEN die Faelligkeitsliste zusammengestellt wird
    THEN steht der Trip nicht darin, sodass ein offener Nachliefer-Marker aus
    #1012 nicht verfaellt.

    Zwei Zusicherungen, weil eine allein nichts beweist:
    * Der Trip fehlt in ``_collect_due_trips()`` — sonst raeumte
      ``_process_pending_markers`` den Marker ersatzlos weg (`:658-668`).
    * Der VERWAISTE Vermerk bringt denselben Trip zurueck in die Liste. Ohne
      diese Gegenprobe waere die erste Haelfte auch von einer Regel erfuellt,
      die JEDEN offenen Vermerk blockieren laesst — also vom heutigen Fehler.

    RED-Charakter: die Gegenprobe ist Fehlernachweis (heute blockiert der
    verwaiste Vermerk die Faelligkeit dauerhaft); die erste Haelfte ist
    Mutations-Waechter fuer die neu eingezogene Alters-Dimension.
    """
    from freezegun import freeze_time

    jetzt = _slot(30)
    with freeze_time(jetzt):
        uid = _nutzer("1897-ac6-lebendig")
        write_trip(uid, TRIP, morgen_stunde=SLOT_STUNDE, abend_stunde=ABEND_STUNDE)
        tag = ortstag(TRIP_ZONE)
        _offener_vermerk(uid, tag, jetzt - timedelta(seconds=60))

        scheduler = _scheduler(uid)
        trip = load_trip_obj(uid, TRIP)
        segmente = scheduler._convert_trip_to_segments(trip, tag)
        assert segmente, "Testaufbau prueft nichts: der Trip braucht Abschnitte"
        scheduler._write_pending_marker(
            trip, "morning", tag, [str(s.segment_id) for s in segmente],
        )

        assert BriefingSlotStore(uid).is_recorded_or_claimed(
            TRIP, "morning", tag, moment=jetzt,
        ) is True, (
            "Ein Vermerk ohne Ausgang, der juenger als CLAIM_TTL ist, gehoert "
            "zu einem laufenden Versand — die Faelligkeitsliste muss ihn "
            "beruecksichtigen."
        )
        faellig = _faellige_ids(scheduler, jetzt)
        assert TRIP not in faellig, (
            f"Waehrend ein Versand laeuft, darf der Trip nicht in der "
            f"Faelligkeitsliste stehen, gefunden: {faellig}"
        )

        scheduler._process_pending_markers(jetzt, faellig)
        marker = _marker(uid)
        assert marker is not None and marker.get("attempts") == 1, (
            "Der offene Nachliefer-Marker aus #1012 muss den Lauf ueberleben "
            f"(Versuchszaehler +1), gefunden: {marker!r}. Steht der Trip "
            "faelschlich in der Faelligkeitsliste, verfaellt er ersatzlos."
        )

        anderer = _nutzer("1897-ac6-verwaist")
        write_trip(anderer, TRIP, morgen_stunde=SLOT_STUNDE, abend_stunde=ABEND_STUNDE)
        _offener_vermerk(anderer, tag, jetzt - timedelta(seconds=_ttl() * 2))
        assert TRIP in _faellige_ids(_scheduler(anderer), jetzt), (
            "Gegenprobe: ein verwaister Vermerk muss den Trip ZURUECK in die "
            "Faelligkeitsliste bringen — sonst bleibt das Briefing aus."
        )


# ---------------------------------------------------------------------------
# AC-9 — jenseits des Nachhol-Fensters endet beides: Nachholung und Sperre
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "minuten_nach_slot, im_fenster", [(150, True), (210, False)],
)
def test_ac9_nachhol_fenster_begrenzt_nachholung_und_sperre(
    minuten_nach_slot, im_fenster,
):
    """AC-9.

    GIVEN der Abbruch geschah so spaet, dass beim naechsten stuendlichen Lauf
    das dreistuendige Nachhol-Fenster bereits vorbei ist
    WHEN dieser Lauf laeuft
    THEN wird das Briefing nicht mehr nachgeholt und die Alarm-Sperre gilt fuer
    diesen Slot nicht mehr.

    Beide Wirkorte in einem Fall, weil sie zusammen die Grenze bilden: der
    Scheduler holt nicht mehr nach UND der Alarm darf wieder eigenstaendig
    raus — schwiege er weiter, waere die Meldung verschluckt statt ersetzt
    (Fehlerklasse #1555/#1584).

    Der Lauf 150 Minuten nach dem Slot (Ortsstunde 9, ``7 <= 9 < 10``) ist die
    Gegenprobe: dort MUESSEN Nachholung und Sperre noch greifen. Ohne sie
    bewiese der 210-Minuten-Fall nur, dass irgendetwas gar nicht laeuft.

    RED-Charakter: die Gegenprobe ist Fehlernachweis (heute laesst der offene
    Vermerk den Slot als erledigt gelten, also weder Nachholung noch Sperre);
    der Fall ausserhalb des Fensters ist Mutations-Waechter — rot, sobald die
    Uebernahme eines verwaisten Vermerks das Fenster ``NACHHOL_FENSTER_STUNDEN``
    umgeht und ein Briefing Stunden zu spaet nachschiebt.
    """
    from freezegun import freeze_time

    jetzt = _slot(minuten_nach_slot)
    with freeze_time(jetzt):
        uid = _nutzer(f"1897-ac9-{minuten_nach_slot}")
        write_trip(uid, TRIP, morgen_stunde=SLOT_STUNDE, abend_stunde=ABEND_STUNDE)
        _offener_vermerk(uid, ortstag(TRIP_ZONE), _slot(120))

        trip = load_trip_obj(uid, TRIP)
        faellig = _faellige_ids(_scheduler(uid), jetzt)
        gesperrt = _sperre_greift(uid, trip, jetzt)

    if im_fenster:
        assert TRIP in faellig, (
            "Ortsstunde 9 liegt im Nachhol-Fenster — der verwaiste Slot muss "
            f"nachgeholt werden, gefunden: {faellig}"
        )
        assert gesperrt is True, (
            "Solange das Briefing noch nachgeholt wird, haelt die Alarm-Sperre."
        )
    else:
        assert TRIP not in faellig, (
            "Ortsstunde 10 liegt DREI Stunden hinter dem 07:00-Slot und damit "
            f"ausserhalb des Nachhol-Fensters, gefunden: {faellig}"
        )
        assert gesperrt is False, (
            "Ausserhalb des Nachhol-Fensters kommt kein Briefing mehr — der "
            "Alarm muss wieder eigenstaendig rausgehen, sonst schweigt er ohne "
            "Ersatz."
        )
