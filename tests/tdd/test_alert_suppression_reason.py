"""TDD RED — jede Unterdrueckung bekommt einen BENANNTEN Grund
(Issue #2050 Scheibe S3b, Szenario 10 / Anforderung D-2, AC-1 bis AC-10).

SPEC:    docs/specs/modules/feat_2050_s3b_budget_und_unterdrueckungsgrund.md
KONTEXT: docs/context/feat-2050-s3b-budget-und-unterdrueckungsgrund.md

Heute protokollieren nur die beiden Nowcast-/Radar-Pfade ihre Unterdrueckung
(#1467 S3). Aenderungsalarm und amtliche Warnung schweigen — offene Luecken
**O3**/**E3**. Diese Scheibe schaltet neun bislang stille Gate-Stellen scharf
und laesst VIER bewusst still (Briefing-Vorlauf, Bestandsschutz
#1233/ADR-0009, AC-10).

RED-Stand heute (gemessen):

* AC-1 … AC-9 sind ROT — an keiner der neun Stellen entsteht ein
  ``not_delivered``-Eintrag; AC-4 zusaetzlich, weil
  ``alert_log.REASON_DOUBLE_ALERT_GUARD`` noch gar nicht existiert.
* AC-10 ist ein BEWAHRUNGS-Kriterium und heute wie nachher GRUEN: der
  Briefing-Vorlauf darf gerade KEINEN Eintrag erzeugen. Ein gruener Test ist
  hier kein Versehen, sondern der Zweck — er faengt die naheliegendste
  Fehl-Umsetzung ("Protokoll gleich in den geteilten Baustein haengen"), die
  alle vier Vorlauf-Stellen mitnehmen wuerde. Der Trip-Aenderungsfall
  (``test_ac10_briefing_vorlauf_am_trip_aenderungsalarm_bleibt_still``) haelt
  seine Positivkontrolle zusaetzlich am neuen Verhalten fest und ist deshalb
  in dieser Haelfte heute ROT.

Mock-frei: echte Trips/Presets/Orte auf Platte, echte Dienste, echte
Zustandsdateien. Der Vorzustand entsteht IMMER ueber den produktiven
Schreibweg — Sperrzeit ueber ``ThrottleStore.record``, Tageszaehler ueber
``alert_daily_limit.increment`` (Anzahl der Schritte aus ``is_allowed()``
abgeleitet, nicht als Zahl hingeschrieben), Ruhezeit ueber die Trip-/Preset-
Felder. Gelesen wird ueber die produktive Leseseite
``alert_log.read_undelivered()``, nicht ueber rohe Dateiinhalte.

Jeder Test faehrt zusaetzlich einen KONTROLL-Lauf ohne die jeweilige Sperre
und behauptet dessen tatsaechlichen Versand. Ohne diese Haelfte waere jede
Zusicherung auch dann erfuellt, wenn der Pfad aus einem GANZ ANDEREN Grund
gar nicht erst losliefe.

Pfadregel #1409: alles ueber ``app.loader`` bzw. relativ zu dieser Datei.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import save_location  # noqa: E402
from services.trip_day import anchor_tz  # noqa: E402
from utils.timezone import first_resolvable_tz  # noqa: E402

from tests.helpers.alert_log_fixtures import gust_alert_trip, weather  # noqa: E402
from tests.helpers.briefing_imminent_fixtures import (  # noqa: E402
    LOCATION_ZONE as VORLAUF_ORTSZONE,
)
from tests.helpers.briefing_imminent_fixtures import (  # noqa: E402
    TRIP_ZONE as VORLAUF_TRIP_ZONE,
)
from tests.helpers.briefing_imminent_fixtures import (  # noqa: E402
    FakeOfficialAlertSource,
    alarmfaehige_lage,
    compare_change_alert_run,
    compare_official_alert_run,
    compare_official_versand_lauf,
    compare_preset,
    load_trip_obj,
    nur_diese_warnquelle,
    ruhezeit_woanders,
    stunde_versetzt,
    trip_change_alert_lauf,
    trip_official_alert_run,
    write_location,
    write_trip,
)
from tests.helpers.briefing_imminent_fixtures import (  # noqa: E402
    clean_uid as vorlauf_clean_uid,
)
from tests.helpers.briefing_imminent_fixtures import (  # noqa: E402
    fresh_uid as vorlauf_fresh_uid,
)
from tests.helpers.briefing_imminent_fixtures import (  # noqa: E402
    write_presets as vorlauf_write_presets,
)
from tests.helpers.briefing_imminent_fixtures import (  # noqa: E402
    write_user_tier as vorlauf_write_user_tier,
)
from tests.helpers.nowcast_gate_fixtures import (  # noqa: E402
    CountingFrameSource, clean_uid, fresh_uid, location, make_trip,
    quiet_window_elsewhere, quiet_window_now, radar_preset, record_throttle,
    reset_radar_cache, save_trip, settings_email_only, trip_alert_service,
    write_presets, write_user_tier,
)

# Sperrzeit-Toepfe, wie die Pruefstellen sie fuehren:
#   Trip-Aenderungsalarm  -> `ThrottleStore.is_throttled("trip", trip.id, ...)`
#                            (`trip_alert.py:1081`)
#   Vergleichs-Aenderung  -> `("compare_preset", preset_id)`
#                            (`compare_alert.py:151`)
# Beide Namen sind feste Kennungen, keine abgeleiteten Werte. Wuerde einer
# davon in der Produktivseite wechseln, faellt das hier LAUT auf: der
# gesperrte Lauf wuerde dann versenden und die Vorbedingungs-Zusicherung
# ("die Sperre muss greifen") scheitert, bevor irgendetwas Gruenes entsteht.
_SCOPE_TRIP_AENDERUNG = "trip"
_SCOPE_COMPARE_AENDERUNG = "compare_preset"

# Reissleine der Budget-Schleife: das grosszuegigste endliche Tagesbudget ist
# heute 4 (`user_tier.daily_alert_limit`). Ein Wert weit darueber faengt nur
# die Endlosschleife ab, falls der Nutzer versehentlich Premium ist.
_MAX_BUDGET_SCHRITTE = 25


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


# ────────────────────────── Leseseite (produktiv) ───────────────────────────


def _vorfaelle(uid: str, entity_id: str, entity_type: str, seit: datetime) -> list:
    """Alle Nicht-Zustellungen dieser Kennung ueber die PRODUKTIVE Leseseite —
    dieselbe Funktion, aus der auch das Briefing seinen Hinweis speist."""
    from services.alert_log import read_undelivered

    return read_undelivered(
        uid, entity_id=entity_id, entity_type=entity_type, since=seit,
    )


def _genau_ein_grund(
    uid: str, entity_id: str, entity_type: str, seit: datetime,
    *, gate_reason: str, ausloeser: str,
):
    """GENAU EIN Vorfall mit GENAU DIESEM Grund und GENAU DIESEM Ausloeser.

    Bewusst Gleichheit statt Enthaltensein: ``gate_reason in v.reasons``
    waere auch dann erfuellt, wenn der Eintrag zusaetzlich einen zweiten,
    falschen Grund traegt — und ``is not None`` waere selbst mit einem
    beliebigen anderen Wert gruen. Geprueft wird der WERT, nicht die Form.
    """
    vorfaelle = _vorfaelle(uid, entity_id, entity_type, seit)
    assert len(vorfaelle) == 1, (
        f"Erwartet GENAU EINEN Unterdrueckungs-Vorfall fuer "
        f"{entity_type}/{entity_id}, gefunden {len(vorfaelle)}: {vorfaelle!r}"
    )
    vorfall = vorfaelle[0]
    assert set(vorfall.reasons) == {gate_reason}, (
        f"Der Vorfall muss GENAU den Grund {gate_reason!r} tragen, "
        f"gefunden {sorted(vorfall.reasons)!r}"
    )
    assert vorfall.trigger == ausloeser, (
        f"Der Ausloeser der Meldung muss {ausloeser!r} bleiben (er darf nicht "
        f"mit dem Sperrgrund verschmelzen), gefunden {vorfall.trigger!r}"
    )
    assert vorfall.channels, (
        f"Ein Vorfall ohne betroffenen Kanal ist im Briefing unsichtbar: "
        f"{vorfall!r}"
    )
    return vorfall


def _kein_vorfall(uid: str, entity_id: str, entity_type: str, seit: datetime) -> None:
    vorfaelle = _vorfaelle(uid, entity_id, entity_type, seit)
    assert vorfaelle == [], (
        f"Fuer {entity_type}/{entity_id} darf KEIN Unterdrueckungs-Vorfall "
        f"entstanden sein, gefunden: {vorfaelle!r}"
    )


# ─────────────────────── Vorzustand ueber Produktivwege ─────────────────────


def _budget_ausschoepfen(uid: str, zone, *, reason: str | None) -> int:
    """Tageszaehler ueber ``alert_daily_limit.increment()`` bis ans Limit
    fuellen und die Anzahl der Schritte zurueckgeben.

    Die Zahl steht bewusst NICHT im Test: sie haengt am Nutzerlevel UND an
    der NowCast-Reserve (#1555, ``forecast_change`` prueft gegen ein
    reduziertes Limit). Ein Literal waere ein abgeleiteter Wert im Testaufbau
    — die Bildungsstelle bliebe unbewacht, und eine Aenderung der Reserve
    machte den Test still gruen aus dem falschen Grund.
    """
    from services import alert_daily_limit

    now = _jetzt()
    schritte = 0
    while alert_daily_limit.is_allowed(uid, now, zone, reason=reason):
        alert_daily_limit.increment(uid, now, zone)
        schritte += 1
        assert schritte <= _MAX_BUDGET_SCHRITTE, (
            f"Das Tagesbudget von {uid!r} in {zone} liess sich nicht "
            f"erschoepfen — hat der Nutzer ueberhaupt ein endliches Limit?"
        )
    assert schritte >= 1, (
        f"Vorbedingung: {uid!r} muss in {zone} ueberhaupt Budget gehabt "
        f"haben, sonst misst der Test nicht das Tageslimit"
    )
    return schritte


def _budget_knapp_unter_limit(uid: str, zone, schritte: int, *, reason: str | None) -> None:
    """Kontroll-Nutzer auf EINEN Alarm unter dem Limit setzen — die Anzahl
    kommt aus dem Ausschoepfen des gesperrten Nutzers, nicht aus einer Zahl."""
    from services import alert_daily_limit

    now = _jetzt()
    for _ in range(schritte - 1):
        alert_daily_limit.increment(uid, now, zone)
    assert alert_daily_limit.is_allowed(uid, now, zone, reason=reason), (
        f"Vorbedingung: der Kontroll-Nutzer {uid!r} muss noch Budget haben"
    )


# ───────────────────── Trip-Aenderungsalarm (AC-1 … AC-3) ───────────────────


def _aenderungs_trip(trip_id: str):
    """Tour mit scharfer Boeen-Regel — der Aufbau, den auch #1467 S3 fuer den
    Aenderungspfad benutzt."""
    return gust_alert_trip(trip_id)


def _aenderungslauf(uid: str, trip, mails: list) -> bool:
    return trip_alert_service(
        uid, settings_email_only(), CountingFrameSource(),
        lambda subject, body: mails.append((subject, body)),
    ).check_and_send_alerts(
        trip,
        [weather(1, gust_max_kmh=20.0)],
        fresh_weather=[weather(1, gust_max_kmh=60.0)],
    )


def test_ac1_ruhezeit_am_trip_aenderungsalarm_wird_protokolliert():
    """AC-1: Eine durch die RUHEZEIT unterdrueckte Vorhersage-Aenderung
    hinterlaesst einen ``not_delivered``-Eintrag mit
    ``gate_reason == quiet_hours`` und ``reason == forecast_change``.

    ROT heute: ``trip_alert.py:342-345`` bricht mit einem Debug-Log ab und
    schreibt nichts."""
    from services.alert_log import REASON_FORECAST_CHANGE, REASON_QUIET_HOURS

    kontrolle, gesperrt = fresh_uid("s3b-ac1-ok"), fresh_uid("s3b-ac1-quiet")
    clean_uid(kontrolle)
    clean_uid(gesperrt)
    seit = _jetzt() - timedelta(minutes=1)
    try:
        write_user_tier(kontrolle, "premium")
        write_user_tier(gesperrt, "premium")

        offen = _aenderungs_trip("trip-2050s3b-ac1-ok")
        offen.alert_quiet_from, offen.alert_quiet_to = quiet_window_elsewhere(
            zone=anchor_tz(offen, _jetzt())
        )
        mails_ok: list = []
        assert _aenderungslauf(kontrolle, offen, mails_ok) is True, (
            "Positivkontrolle: ohne Ruhezeit MUSS der Aenderungsalarm rausgehen"
        )
        assert len(mails_ok) == 1, (
            f"Positivkontrolle: genau EINE Mail erwartet, erhalten {len(mails_ok)}"
        )
        _kein_vorfall(kontrolle, offen.id, "trip", seit)

        still = _aenderungs_trip("trip-2050s3b-ac1-quiet")
        still.alert_quiet_from, still.alert_quiet_to = quiet_window_now(
            zone=anchor_tz(still, _jetzt())
        )
        mails_still: list = []
        assert _aenderungslauf(gesperrt, still, mails_still) is False, (
            "Vorbedingung: die Ruhezeit muss den Aenderungsalarm unterdruecken"
        )
        assert mails_still == [], "Waehrend der Ruhezeit darf nichts rausgehen"
        _genau_ein_grund(
            gesperrt, still.id, "trip", seit,
            gate_reason=REASON_QUIET_HOURS, ausloeser=REASON_FORECAST_CHANGE,
        )
    finally:
        clean_uid(kontrolle)
        clean_uid(gesperrt)


def test_ac2_sperrzeit_am_trip_aenderungsalarm_wird_protokolliert():
    """AC-2: Eine durch die SPERRZEIT unterdrueckte Vorhersage-Aenderung
    hinterlaesst einen Eintrag mit ``gate_reason == cooldown``.

    Der Vorzustand entsteht ueber den echten ``ThrottleStore.record()``, nicht
    per Handschrift in die Datei — so misst der Test das Format, das der
    Pruefling selbst schreibt.

    ROT heute: ``trip_alert.py:358-360``."""
    from services.alert_log import REASON_COOLDOWN, REASON_FORECAST_CHANGE

    kontrolle, gesperrt = fresh_uid("s3b-ac2-ok"), fresh_uid("s3b-ac2-cd")
    clean_uid(kontrolle)
    clean_uid(gesperrt)
    seit = _jetzt() - timedelta(minutes=1)
    try:
        write_user_tier(kontrolle, "premium")
        write_user_tier(gesperrt, "premium")

        # `gust_alert_trip()` setzt `alert_cooldown_minutes = 0` — das heisst
        # "kein Limit" (#181) und liesse die Sperrzeit-Stufe gar nicht wirken.
        offen = _aenderungs_trip("trip-2050s3b-ac2-ok")
        offen.alert_cooldown_minutes = 120
        offen.alert_quiet_from, offen.alert_quiet_to = quiet_window_elsewhere(
            zone=anchor_tz(offen, _jetzt())
        )
        mails_ok: list = []
        assert _aenderungslauf(kontrolle, offen, mails_ok) is True, (
            "Positivkontrolle: ohne laufende Sperrzeit MUSS der Alarm rausgehen"
        )
        assert len(mails_ok) == 1
        _kein_vorfall(kontrolle, offen.id, "trip", seit)

        still = _aenderungs_trip("trip-2050s3b-ac2-cd")
        still.alert_cooldown_minutes = 120
        still.alert_quiet_from, still.alert_quiet_to = quiet_window_elsewhere(
            zone=anchor_tz(still, _jetzt())
        )
        record_throttle(
            gesperrt, _SCOPE_TRIP_AENDERUNG, still.id,
            _jetzt() - timedelta(minutes=5),
        )
        mails_still: list = []
        assert _aenderungslauf(gesperrt, still, mails_still) is False, (
            "Vorbedingung: die laufende Sperrzeit muss den Alarm unterdruecken"
        )
        assert mails_still == []
        _genau_ein_grund(
            gesperrt, still.id, "trip", seit,
            gate_reason=REASON_COOLDOWN, ausloeser=REASON_FORECAST_CHANGE,
        )
    finally:
        clean_uid(kontrolle)
        clean_uid(gesperrt)


def test_ac3_tageslimit_am_trip_aenderungsalarm_wird_protokolliert():
    """AC-3: Eine durch die TAGES-OBERGRENZE unterdrueckte Vorhersage-
    Aenderung hinterlaesst einen Eintrag mit ``gate_reason == daily_limit``.

    Der Zaehler wird ueber ``alert_daily_limit.increment()`` in der Zone
    gefuellt, die der Pruefling selbst benutzt (``anchor_tz``) — eine andere
    Zone fuellte einen ANDEREN Zaehler (#1726) und der Test waere gruen, ohne
    das Tageslimit je erreicht zu haben.

    ROT heute: ``trip_alert.py:365-370``."""
    from services.alert_log import REASON_DAILY_LIMIT, REASON_FORECAST_CHANGE

    kontrolle, gesperrt = fresh_uid("s3b-ac3-ok"), fresh_uid("s3b-ac3-dl")
    clean_uid(kontrolle)
    clean_uid(gesperrt)
    seit = _jetzt() - timedelta(minutes=1)
    try:
        write_user_tier(kontrolle, "free")
        write_user_tier(gesperrt, "free")

        still = _aenderungs_trip("trip-2050s3b-ac3-dl")
        still.alert_quiet_from, still.alert_quiet_to = quiet_window_elsewhere(
            zone=anchor_tz(still, _jetzt())
        )
        schritte = _budget_ausschoepfen(
            gesperrt, anchor_tz(still, _jetzt()), reason="forecast_change",
        )

        offen = _aenderungs_trip("trip-2050s3b-ac3-ok")
        offen.alert_quiet_from, offen.alert_quiet_to = quiet_window_elsewhere(
            zone=anchor_tz(offen, _jetzt())
        )
        _budget_knapp_unter_limit(
            kontrolle, anchor_tz(offen, _jetzt()), schritte,
            reason="forecast_change",
        )
        mails_ok: list = []
        assert _aenderungslauf(kontrolle, offen, mails_ok) is True, (
            "Positivkontrolle: einen Alarm unter dem Limit MUSS der "
            "Aenderungsalarm rausgehen"
        )
        assert len(mails_ok) == 1
        _kein_vorfall(kontrolle, offen.id, "trip", seit)

        mails_still: list = []
        assert _aenderungslauf(gesperrt, still, mails_still) is False, (
            "Vorbedingung: das erreichte Tageslimit muss den Alarm unterdruecken"
        )
        assert mails_still == []
        _genau_ein_grund(
            gesperrt, still.id, "trip", seit,
            gate_reason=REASON_DAILY_LIMIT, ausloeser=REASON_FORECAST_CHANGE,
        )
    finally:
        clean_uid(kontrolle)
        clean_uid(gesperrt)


# ─────────────────── Doppel-Alarm-Guard, Trip-Radar (AC-4) ──────────────────


def _radarlauf(uid: str, mails: list) -> int:
    return trip_alert_service(
        uid, settings_email_only(), CountingFrameSource(onset_minutes=8),
        lambda subject, body: mails.append((subject, body)),
    ).check_radar_alerts()


def _aktives_segment_id(uid: str, trip_id: str):
    """Kennung des Segments, das ``check_radar_alerts()`` fuer diesen Trip
    waehlt — ueber DENSELBEN Aufloeser, nicht als Literal.

    Als ``"1"`` hingeschrieben bliebe die Bildungsstelle unbewacht: ein
    veraenderter Segment-Zuschnitt liesse den Guard-Eintrag ins Leere zeigen,
    der Guard griffe nicht — und der Test waere gruen, weil "kein Eintrag"
    auch dann herauskaeme.
    """
    from services.trip_alert import TripAlertService
    from services.trip_day import trip_local_today

    trip = load_trip_obj(uid, trip_id)
    jetzt = _jetzt()
    dienst = TripAlertService(
        settings=settings_email_only(), throttle_hours=2, user_id=uid,
    )
    aufgeloest = dienst._resolve_alert_segment(
        trip, jetzt, trip_local_today(trip, jetzt),
    )
    assert aufgeloest is not None, (
        f"Vorbedingung: {trip_id!r} muss ein aktives Segment haben"
    )
    return aufgeloest[0].segment_id


def _doppel_alarm_gedaechtnis_setzen(uid: str, trip_id: str) -> None:
    """Melde-Gedaechtnis so hinterlassen, wie ein soeben zugestellter
    Aenderungsalarm es hinterlaesst (``trip_alert.py:511-517``) — ueber den
    produktiven Speicher ``AlertStateService.save()``."""
    from services.alert_state import AlertStateService

    AlertStateService(uid).save(trip_id, {
        f"precip:{_aktives_segment_id(uid, trip_id)}": {
            "last_reported_value": 1.0,
            "reported_at": _jetzt().isoformat(),
        },
    })


def test_ac4_doppel_alarm_guard_wird_protokolliert_und_deutsch_beschriftet():
    """AC-4: Haelt der Doppel-Alarm-Guard (#818) eine juengere Meldung
    desselben Segments zurueck, entsteht ein Eintrag mit
    ``gate_reason == alert_log.REASON_DOUBLE_ALERT_GUARD`` — und die
    gerenderte Briefing-Mail zeigt dafuer eine DEUTSCHE Beschriftung im
    Block "ZURUECKGEHALTEN", keinen rohen Code.

    ROT heute doppelt: ``trip_alert.py:1632-1649`` bricht still ab, und
    ``alert_log.REASON_DOUBLE_ALERT_GUARD`` existiert gar nicht
    (``AttributeError``)."""
    from services import alert_log
    from output.renderers.email.undelivered_hint import (
        HEADING_FAILED, HEADING_WITHHELD, render_undelivered_plain,
    )

    assert alert_log.REASON_DOUBLE_ALERT_GUARD == "double_alert_guard", (
        "Der Doppel-Alarm-Guard braucht einen EIGENEN Grund: er ist kein "
        "Cooldown auf ThrottleStore-Ebene, sondern ein kanaluebergreifender "
        "Wiederholungsschutz auf AlertStateService-Ebene"
    )

    kontrolle, gesperrt = fresh_uid("s3b-ac4-ok"), fresh_uid("s3b-ac4-guard")
    clean_uid(kontrolle)
    clean_uid(gesperrt)
    seit = _jetzt() - timedelta(minutes=1)
    try:
        for uid, trip_id in (
            (kontrolle, "trip-2050s3b-ac4-ok"), (gesperrt, "trip-2050s3b-ac4-guard"),
        ):
            write_user_tier(uid, "premium")
            trip = make_trip(trip_id)
            trip.alert_quiet_from, trip.alert_quiet_to = quiet_window_elsewhere(
                zone=anchor_tz(trip, _jetzt())
            )
            save_trip(trip, uid)

        mails_ok: list = []
        reset_radar_cache()
        assert _radarlauf(kontrolle, mails_ok) == 1, (
            "Positivkontrolle: ohne Guard-Eintrag MUSS der Radar-Alarm rausgehen"
        )
        assert len(mails_ok) == 1
        _kein_vorfall(kontrolle, "trip-2050s3b-ac4-ok", "trip", seit)

        _doppel_alarm_gedaechtnis_setzen(gesperrt, "trip-2050s3b-ac4-guard")
        mails_still: list = []
        reset_radar_cache()
        assert _radarlauf(gesperrt, mails_still) == 0, (
            "Vorbedingung: der Doppel-Alarm-Guard muss den Radar-Alarm halten"
        )
        assert mails_still == []
        vorfall = _genau_ein_grund(
            gesperrt, "trip-2050s3b-ac4-guard", "trip", seit,
            gate_reason=alert_log.REASON_DOUBLE_ALERT_GUARD,
            ausloeser=alert_log.REASON_NOWCAST,
        )

        text = render_undelivered_plain([vorfall], tz=anchor_tz(
            load_trip_obj(gesperrt, "trip-2050s3b-ac4-guard"), _jetzt(),
        ))
        assert alert_log.REASON_DOUBLE_ALERT_GUARD not in text, (
            "Im Briefing darf der rohe Code nicht erscheinen — der Grund "
            f"braucht eine deutsche Beschriftung:\n{text}"
        )
        assert HEADING_WITHHELD in text, (
            "Ein zurueckgehaltener Alarm gehoert in den Block "
            f"{HEADING_WITHHELD!r} (Nutzer-Absicht), nicht in den "
            f"Fehler-Block:\n{text}"
        )
        assert HEADING_FAILED not in text, (
            "Der Doppel-Alarm-Guard ist KEIN Zustellfehler — ein unbekannter "
            "Grund faellt in `_REASON_BLOCK` still auf 'failed' zurueck:\n"
            f"{text}"
        )
    finally:
        clean_uid(kontrolle)
        clean_uid(gesperrt)


# ──────────────────── Amtliche Warnung, Trip (AC-5) ─────────────────────────


def _fern() -> int:
    """Briefing-Stunde weit weg vom Vorlauf-Fenster (Trip-Ortszone)."""
    return stunde_versetzt(5, zone=VORLAUF_TRIP_ZONE)


def _fern_abend() -> int:
    return stunde_versetzt(9, zone=VORLAUF_TRIP_ZONE)


def _amtlicher_trip(uid: str, trip_id: str, *, quiet) -> None:
    write_trip(
        uid, trip_id, morgen_stunde=_fern(), abend_stunde=_fern_abend(),
        quiet=quiet, cooldown_minutes=0,
    )


def test_ac5_amtlicher_trip_alarm_protokolliert_ruhezeit():
    """AC-5 (Fall 1): ``check_official_alert_gate`` liefert
    ``GateResult(False, REASON_QUIET_HOURS)`` — der Aufrufer muss den Grund
    weiterreichen statt ihn zu verwerfen.

    ROT heute: ``trip_alert.py:2193-2198`` verwirft das ``GateResult``
    komplett (Luecke E3)."""
    from services.alert_log import REASON_OFFICIAL_ALERT, REASON_QUIET_HOURS

    kontrolle = vorlauf_fresh_uid("s3b-ac5q-ok")
    gesperrt = vorlauf_fresh_uid("s3b-ac5q-quiet")
    vorlauf_clean_uid(kontrolle)
    vorlauf_clean_uid(gesperrt)
    seit = _jetzt() - timedelta(minutes=1)
    try:
        vorlauf_write_user_tier(kontrolle, "premium")
        vorlauf_write_user_tier(gesperrt, "premium")
        _amtlicher_trip(kontrolle, "trip-2050s3b-ac5q-ok",
                        quiet=ruhezeit_woanders(zone=VORLAUF_TRIP_ZONE))
        _amtlicher_trip(gesperrt, "trip-2050s3b-ac5q-quiet",
                        quiet=quiet_window_now(zone=VORLAUF_TRIP_ZONE))

        versendet, mails = trip_official_alert_run(kontrolle, "trip-2050s3b-ac5q-ok")
        assert versendet is True, (
            "Positivkontrolle: ohne Ruhezeit MUSS die amtliche Warnung rausgehen"
        )
        assert mails, "Positivkontrolle: es wurde keine Mail erzeugt"
        _kein_vorfall(kontrolle, "trip-2050s3b-ac5q-ok", "trip", seit)

        versendet, mails = trip_official_alert_run(gesperrt, "trip-2050s3b-ac5q-quiet")
        assert versendet is False, (
            "Vorbedingung: die Ruhezeit muss die amtliche Warnung unterdruecken"
        )
        assert mails == []
        _genau_ein_grund(
            gesperrt, "trip-2050s3b-ac5q-quiet", "trip", seit,
            gate_reason=REASON_QUIET_HOURS, ausloeser=REASON_OFFICIAL_ALERT,
        )
    finally:
        vorlauf_clean_uid(kontrolle)
        vorlauf_clean_uid(gesperrt)


def test_ac5_amtlicher_trip_alarm_protokolliert_tageslimit():
    """AC-5 (Fall 2): derselbe Pfad, diesmal mit
    ``GateResult(False, REASON_DAILY_LIMIT)``.

    BEIDE Faelle brauchen einen eigenen Nachweis: eine Umsetzung, die nur den
    Ruhezeit-Zweig protokolliert, waere sonst gruen.

    ROT heute: ``trip_alert.py:2193-2198``."""
    from services.alert_log import REASON_DAILY_LIMIT, REASON_OFFICIAL_ALERT

    kontrolle = vorlauf_fresh_uid("s3b-ac5d-ok")
    gesperrt = vorlauf_fresh_uid("s3b-ac5d-limit")
    vorlauf_clean_uid(kontrolle)
    vorlauf_clean_uid(gesperrt)
    seit = _jetzt() - timedelta(minutes=1)
    try:
        vorlauf_write_user_tier(kontrolle, "free")
        vorlauf_write_user_tier(gesperrt, "free")
        _amtlicher_trip(kontrolle, "trip-2050s3b-ac5d-ok",
                        quiet=ruhezeit_woanders(zone=VORLAUF_TRIP_ZONE))
        _amtlicher_trip(gesperrt, "trip-2050s3b-ac5d-limit",
                        quiet=ruhezeit_woanders(zone=VORLAUF_TRIP_ZONE))

        # `check_official_alert_gate` prueft OHNE `reason` — also gegen das
        # volle Budget, nicht gegen die um die NowCast-Reserve reduzierte
        # Schranke des Aenderungspfads.
        zone_gesperrt = anchor_tz(
            load_trip_obj(gesperrt, "trip-2050s3b-ac5d-limit"), _jetzt(),
        )
        schritte = _budget_ausschoepfen(gesperrt, zone_gesperrt, reason=None)
        zone_kontrolle = anchor_tz(
            load_trip_obj(kontrolle, "trip-2050s3b-ac5d-ok"), _jetzt(),
        )
        _budget_knapp_unter_limit(kontrolle, zone_kontrolle, schritte, reason=None)

        versendet, mails = trip_official_alert_run(kontrolle, "trip-2050s3b-ac5d-ok")
        assert versendet is True, (
            "Positivkontrolle: einen Alarm unter dem Limit MUSS die amtliche "
            "Warnung rausgehen"
        )
        assert mails, "Positivkontrolle: es wurde keine Mail erzeugt"
        _kein_vorfall(kontrolle, "trip-2050s3b-ac5d-ok", "trip", seit)

        versendet, mails = trip_official_alert_run(gesperrt, "trip-2050s3b-ac5d-limit")
        assert versendet is False, (
            "Vorbedingung: das erreichte Tageslimit muss die amtliche Warnung "
            "unterdruecken"
        )
        assert mails == []
        _genau_ein_grund(
            gesperrt, "trip-2050s3b-ac5d-limit", "trip", seit,
            gate_reason=REASON_DAILY_LIMIT, ausloeser=REASON_OFFICIAL_ALERT,
        )
    finally:
        vorlauf_clean_uid(kontrolle)
        vorlauf_clean_uid(gesperrt)


# ─────────────── Ortsvergleich-Aenderungsalarm (AC-6 … AC-8) ────────────────

_COMPARE_ORT = "loc-2050s3b"


def _punkt(point_id: str, lat: float, lon: float, precip_sum_mm: float):
    """Echtes ``PointWeatherData``-DTO (kein Mock)."""
    from app.models import SegmentWeatherSummary
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=point_id, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=_jetzt(), provider="tdd-2050s3b",
    )


class _SkriptQuelle:
    """Echte ``LocationWeatherSource``-Implementierung ohne Netz — Muster aus
    ``test_compare_alert_quiet_hours_precedes_fetch.py``."""

    def __init__(self, precip_sum_mm: float) -> None:
        self._wert = precip_sum_mm

    def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None,
              elevation_m=None):
        return _punkt(point_id, lat, lon, self._wert)


def _compare_zone(ort):
    """Zone, in der ``compare_alert.py`` Ruhezeit UND Tageszaehler fuehrt —
    ueber denselben Aufloeser wie ``_build_eval_config`` (#1726)."""
    return first_resolvable_tz([ort], context_label="tdd-2050s3b")


def _compare_aufbau(uid: str, preset_id: str, *, ruhezeit_aktiv: bool):
    """Vergleich mit EINEM Ort, frischem Δ-Anker und scharfem Alarm.

    Das Ruhezeit-Fenster entsteht in DERSELBEN Zone, in der der Pruefling es
    auswertet (``first_resolvable_tz`` ueber die Orte des Presets) — eine
    andere Zone verschoebe das Fenster um Stunden und der Test maesse etwas
    anderes als die Ruhezeit.
    """
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    ort = location(_COMPARE_ORT, "Vergleichsdorf")
    save_location(ort, user_id=uid)
    zone = _compare_zone(ort)
    quiet_from, quiet_to = (
        quiet_window_now(zone=zone) if ruhezeit_aktiv
        else quiet_window_elsewhere(zone=zone)
    )
    write_presets(uid, [radar_preset(
        preset_id, [_COMPARE_ORT], user_id=uid, cooldown_minutes=120,
        quiet_from=quiet_from, quiet_to=quiet_to,
    )])
    CompareWeatherSnapshotService(user_id=uid).save(
        preset_id, _COMPARE_ORT, _punkt(_COMPARE_ORT, ort.lat, ort.lon, 2.0),
    )
    return zone


def _compare_lauf(uid: str, mails: list) -> int:
    from services.compare_alert import CompareAlertService

    return CompareAlertService(
        settings=settings_email_only(), user_id=uid,
        weather_source=_SkriptQuelle(30.0),  # Δ = 28 mm, weit ueber jeder Stufe
        mail_sink=lambda subject, body: mails.append((subject, body)),
    ).check_all_compare_presets()


def test_ac6_sperrzeit_am_vergleichs_aenderungsalarm_wird_protokolliert():
    """AC-6: Sperrzeit im Ortsvergleich — Eintrag mit
    ``entity_type == "compare"`` und ``gate_reason == cooldown``.

    ROT heute: ``compare_alert.py:151-153``."""
    from services.alert_log import REASON_COOLDOWN, REASON_FORECAST_CHANGE

    kontrolle, gesperrt = fresh_uid("s3b-ac6-ok"), fresh_uid("s3b-ac6-cd")
    p_ok, p_cd = "cp-2050s3b-ac6-ok", "cp-2050s3b-ac6-cd"
    clean_uid(kontrolle)
    clean_uid(gesperrt)
    seit = _jetzt() - timedelta(minutes=1)
    try:
        write_user_tier(kontrolle, "premium")
        write_user_tier(gesperrt, "premium")
        _compare_aufbau(kontrolle, p_ok, ruhezeit_aktiv=False)
        _compare_aufbau(gesperrt, p_cd, ruhezeit_aktiv=False)

        mails_ok: list = []
        assert _compare_lauf(kontrolle, mails_ok) == 1, (
            "Positivkontrolle: ohne Sperrzeit MUSS der Vergleichsalarm rausgehen"
        )
        assert len(mails_ok) == 1
        _kein_vorfall(kontrolle, p_ok, "compare", seit)

        record_throttle(
            gesperrt, _SCOPE_COMPARE_AENDERUNG, p_cd,
            _jetzt() - timedelta(minutes=5),
        )
        mails_still: list = []
        assert _compare_lauf(gesperrt, mails_still) == 0, (
            "Vorbedingung: die Sperrzeit muss den Vergleichsalarm unterdruecken"
        )
        assert mails_still == []
        _genau_ein_grund(
            gesperrt, p_cd, "compare", seit,
            gate_reason=REASON_COOLDOWN, ausloeser=REASON_FORECAST_CHANGE,
        )
    finally:
        clean_uid(kontrolle)
        clean_uid(gesperrt)


def test_ac7_tageslimit_am_vergleichs_aenderungsalarm_wird_protokolliert():
    """AC-7: Tages-Obergrenze im Ortsvergleich — Eintrag mit
    ``gate_reason == daily_limit``.

    ROT heute: ``compare_alert.py:164-168``."""
    from services.alert_log import REASON_DAILY_LIMIT, REASON_FORECAST_CHANGE

    kontrolle, gesperrt = fresh_uid("s3b-ac7-ok"), fresh_uid("s3b-ac7-dl")
    p_ok, p_dl = "cp-2050s3b-ac7-ok", "cp-2050s3b-ac7-dl"
    clean_uid(kontrolle)
    clean_uid(gesperrt)
    seit = _jetzt() - timedelta(minutes=1)
    try:
        write_user_tier(kontrolle, "free")
        write_user_tier(gesperrt, "free")
        zone = _compare_aufbau(gesperrt, p_dl, ruhezeit_aktiv=False)
        _compare_aufbau(kontrolle, p_ok, ruhezeit_aktiv=False)

        schritte = _budget_ausschoepfen(gesperrt, zone, reason="forecast_change")
        _budget_knapp_unter_limit(kontrolle, zone, schritte, reason="forecast_change")

        mails_ok: list = []
        assert _compare_lauf(kontrolle, mails_ok) == 1, (
            "Positivkontrolle: einen Alarm unter dem Limit MUSS der "
            "Vergleichsalarm rausgehen"
        )
        assert len(mails_ok) == 1
        _kein_vorfall(kontrolle, p_ok, "compare", seit)

        mails_still: list = []
        assert _compare_lauf(gesperrt, mails_still) == 0, (
            "Vorbedingung: das erreichte Tageslimit muss den Vergleichsalarm "
            "unterdruecken"
        )
        assert mails_still == []
        _genau_ein_grund(
            gesperrt, p_dl, "compare", seit,
            gate_reason=REASON_DAILY_LIMIT, ausloeser=REASON_FORECAST_CHANGE,
        )
    finally:
        clean_uid(kontrolle)
        clean_uid(gesperrt)


def test_ac8_ruhezeit_am_vergleichs_aenderungsalarm_wird_protokolliert():
    """AC-8: Ruhezeit im Ortsvergleich — Eintrag mit
    ``gate_reason == quiet_hours``.

    ROT heute: ``compare_alert.py:189-195``."""
    from services.alert_log import REASON_FORECAST_CHANGE, REASON_QUIET_HOURS

    kontrolle, gesperrt = fresh_uid("s3b-ac8-ok"), fresh_uid("s3b-ac8-quiet")
    p_ok, p_quiet = "cp-2050s3b-ac8-ok", "cp-2050s3b-ac8-quiet"
    clean_uid(kontrolle)
    clean_uid(gesperrt)
    seit = _jetzt() - timedelta(minutes=1)
    try:
        write_user_tier(kontrolle, "premium")
        write_user_tier(gesperrt, "premium")
        _compare_aufbau(kontrolle, p_ok, ruhezeit_aktiv=False)
        _compare_aufbau(gesperrt, p_quiet, ruhezeit_aktiv=True)

        mails_ok: list = []
        assert _compare_lauf(kontrolle, mails_ok) == 1, (
            "Positivkontrolle: ausserhalb der Ruhezeit MUSS der "
            "Vergleichsalarm rausgehen"
        )
        assert len(mails_ok) == 1
        _kein_vorfall(kontrolle, p_ok, "compare", seit)

        mails_still: list = []
        assert _compare_lauf(gesperrt, mails_still) == 0, (
            "Vorbedingung: die Ruhezeit muss den Vergleichsalarm unterdruecken"
        )
        assert mails_still == []
        _genau_ein_grund(
            gesperrt, p_quiet, "compare", seit,
            gate_reason=REASON_QUIET_HOURS, ausloeser=REASON_FORECAST_CHANGE,
        )
    finally:
        clean_uid(kontrolle)
        clean_uid(gesperrt)


# ──────────────── Amtliche Warnung, Ortsvergleich (AC-9) ────────────────────


def _amtliche_vergleichs_zone(uid: str):
    """Zone, in der ``compare_official_alert.py`` Ruhezeit UND Tageszaehler
    fuehrt — derselbe Aufloeser (``first_resolvable_tz`` ueber die Orte des
    Presets), erst NACH dem Anlegen des Orts auswertbar."""
    from app.loader import load_all_locations

    orte = load_all_locations(user_id=uid)
    assert orte, f"Vorbedingung: {uid!r} braucht mindestens einen Ort"
    return first_resolvable_tz(orte, context_label="tdd-2050s3b-amtlich")


def _amtlicher_vergleich(uid: str, preset_id: str, *, ruhezeit_aktiv: bool):
    """Ort ZUERST, dann die Zone daraus ableiten, dann das Preset schreiben.

    Umgekehrt liefe ``first_resolvable_tz`` ueber eine LEERE Ortsliste und
    fiele auf UTC zurueck — das Ruhezeit-Fenster laege dann um den
    Zonenversatz daneben und der Test maesse nicht die Ruhezeit.
    """
    write_location(uid)
    zone = _amtliche_vergleichs_zone(uid)
    quiet = (
        quiet_window_now(zone=zone) if ruhezeit_aktiv
        else quiet_window_elsewhere(zone=zone)
    )
    vorlauf_write_presets(uid, [compare_preset(
        preset_id,
        morgen_stunde=stunde_versetzt(5, zone=VORLAUF_ORTSZONE),
        abend_stunde=stunde_versetzt(9, zone=VORLAUF_ORTSZONE),
        quiet=quiet, cooldown_minutes=0,
    )])
    return zone


def test_ac9_amtlicher_vergleichs_alarm_protokolliert_ruhezeit():
    """AC-9 (Fall 1): Ruhezeit im amtlichen Ortsvergleich-Pfad.

    ROT heute: ``compare_official_alert.py:149-157`` verwirft das
    ``GateResult`` (Luecke E3, spiegelbildlich zum Trip)."""
    from services.alert_log import REASON_OFFICIAL_ALERT, REASON_QUIET_HOURS

    kontrolle = vorlauf_fresh_uid("s3b-ac9q-ok")
    gesperrt = vorlauf_fresh_uid("s3b-ac9q-quiet")
    p_ok, p_quiet = "cp-2050s3b-ac9q-ok", "cp-2050s3b-ac9q-quiet"
    vorlauf_clean_uid(kontrolle)
    vorlauf_clean_uid(gesperrt)
    seit = _jetzt() - timedelta(minutes=1)
    try:
        vorlauf_write_user_tier(kontrolle, "premium")
        vorlauf_write_user_tier(gesperrt, "premium")
        _amtlicher_vergleich(kontrolle, p_ok, ruhezeit_aktiv=False)
        _amtlicher_vergleich(gesperrt, p_quiet, ruhezeit_aktiv=True)

        sent, mails = compare_official_versand_lauf(kontrolle)
        assert sent == 1, (
            f"Positivkontrolle: ohne Ruhezeit MUSS die amtliche Warnung "
            f"rausgehen, erhalten {sent}"
        )
        assert len(mails) == 1
        _kein_vorfall(kontrolle, p_ok, "compare", seit)

        sent, mails = compare_official_versand_lauf(gesperrt)
        assert sent == 0, (
            "Vorbedingung: die Ruhezeit muss die amtliche Warnung unterdruecken"
        )
        assert mails == []
        _genau_ein_grund(
            gesperrt, p_quiet, "compare", seit,
            gate_reason=REASON_QUIET_HOURS, ausloeser=REASON_OFFICIAL_ALERT,
        )
    finally:
        vorlauf_clean_uid(kontrolle)
        vorlauf_clean_uid(gesperrt)


def test_ac9_amtlicher_vergleichs_alarm_protokolliert_tageslimit():
    """AC-9 (Fall 2): Tages-Obergrenze im amtlichen Ortsvergleich-Pfad.

    ROT heute: ``compare_official_alert.py:149-157``."""
    from services.alert_log import REASON_DAILY_LIMIT, REASON_OFFICIAL_ALERT

    kontrolle = vorlauf_fresh_uid("s3b-ac9d-ok")
    gesperrt = vorlauf_fresh_uid("s3b-ac9d-limit")
    p_ok, p_dl = "cp-2050s3b-ac9d-ok", "cp-2050s3b-ac9d-limit"
    vorlauf_clean_uid(kontrolle)
    vorlauf_clean_uid(gesperrt)
    seit = _jetzt() - timedelta(minutes=1)
    try:
        vorlauf_write_user_tier(kontrolle, "free")
        vorlauf_write_user_tier(gesperrt, "free")
        zone_ok = _amtlicher_vergleich(kontrolle, p_ok, ruhezeit_aktiv=False)
        zone_dl = _amtlicher_vergleich(gesperrt, p_dl, ruhezeit_aktiv=False)

        # `check_official_alert_gate` prueft gegen das VOLLE Budget (kein
        # `reason`), anders als der Aenderungspfad (#1555-Reserve).
        schritte = _budget_ausschoepfen(gesperrt, zone_dl, reason=None)
        _budget_knapp_unter_limit(kontrolle, zone_ok, schritte, reason=None)

        sent, mails = compare_official_versand_lauf(kontrolle)
        assert sent == 1, (
            f"Positivkontrolle: einen Alarm unter dem Limit MUSS die amtliche "
            f"Warnung rausgehen, erhalten {sent}"
        )
        assert len(mails) == 1
        _kein_vorfall(kontrolle, p_ok, "compare", seit)

        sent, mails = compare_official_versand_lauf(gesperrt)
        assert sent == 0, (
            "Vorbedingung: das erreichte Tageslimit muss die amtliche Warnung "
            "unterdruecken"
        )
        assert mails == []
        _genau_ein_grund(
            gesperrt, p_dl, "compare", seit,
            gate_reason=REASON_DAILY_LIMIT, ausloeser=REASON_OFFICIAL_ALERT,
        )
    finally:
        vorlauf_clean_uid(kontrolle)
        vorlauf_clean_uid(gesperrt)


# ══════════ Der Briefing-Vorlauf bleibt BEWUSST still (AC-10) ═══════════════
#
# Bestandsschutz #1233/ADR-0009: die Meldung wird ERSETZT, nicht verschluckt —
# sie kommt Minuten spaeter vollstaendig im Briefing an. Ein Protokoll-Eintrag
# behauptete hier faelschlich "hat dich nicht erreicht".
#
# Diese vier Tests sind heute und nachher GRUEN. Sie fangen die naheliegendste
# Fehl-Umsetzung: den Protokoll-Aufruf in den geteilten Vorlauf-Baustein
# statt an die neun benannten Stellen zu haengen.


def _nah() -> int:
    """Briefing-Stunde im Vorlauf-Fenster (Trip-Ortszone)."""
    return stunde_versetzt(1, zone=VORLAUF_TRIP_ZONE)


def test_ac10_briefing_vorlauf_am_trip_aenderungsalarm_bleibt_still():
    """AC-10 (Trip-Aenderungsalarm): Vorlauf-Sperre ⇒ KEIN Eintrag — obwohl
    im selben Aufbau eine laufende Sperrzeit wartet, die nach dieser Scheibe
    sehr wohl protokolliert.

    Genau das ist die Positivkontrolle: derselbe Trip mit FERNEM Briefing
    faellt eine Stufe weiter in die Sperrzeit und bekommt dort seinen
    Eintrag. Die zweite Haelfte ist heute ROT (AC-2 ist noch nicht umgesetzt),
    die erste gruen — zusammen bewachen sie die Grenze zwischen den neun
    scharfen und den vier stillen Stellen.

    MESSGROESSE DES KONTROLL-TRIPS ABGELOEST durch Issue #2050 S3c
    (2026-08-23), SPEC
    ``docs/specs/modules/feat_2050_s3c_abweichung_ueberholt_sperrzeit.md``:
    Beide Trips wurden bis dahin an der Wetterabruf-Naht gemessen (0 Abrufe =
    gesperrt). Fuer den VORLAUF gilt das unveraendert — die Stufe sitzt weiter
    VOR dem Abruf. Fuer die SPERRZEIT des Kontroll-Trips nicht mehr: sie
    entscheidet seit S3c erst danach, weil die Schwere der Lage vorher nicht
    existiert. Beide Trips bekommen deshalb dieselbe alarmfaehige Lage; der
    Kontroll-Trip wird an seiner ausbleibenden ZUSTELLUNG und am
    protokollierten Grund gemessen. Das zieht die Grenze schaerfer als zuvor:
    der Vorlauf-Trip bleibt bei identischer Lage vor dem Abruf stehen."""
    from services.alert_log import REASON_COOLDOWN, REASON_FORECAST_CHANGE

    still = vorlauf_fresh_uid("s3b-ac10t-nah")
    laut = vorlauf_fresh_uid("s3b-ac10t-fern")
    vorlauf_clean_uid(still)
    vorlauf_clean_uid(laut)
    seit = _jetzt() - timedelta(minutes=1)
    try:
        for uid, trip_id, stunde in (
            (still, "trip-2050s3b-ac10t-nah", _nah()),
            (laut, "trip-2050s3b-ac10t-fern", _fern()),
        ):
            vorlauf_write_user_tier(uid, "premium")
            write_trip(uid, trip_id, morgen_stunde=stunde,
                       abend_stunde=_fern_abend(), cooldown_minutes=120)
            record_throttle(uid, _SCOPE_TRIP_AENDERUNG, trip_id,
                            _jetzt() - timedelta(minutes=5))

        cached, fresh = alarmfaehige_lage()

        abrufe, zugestellt = trip_change_alert_lauf(
            still, "trip-2050s3b-ac10t-nah", cached=cached, fresh=fresh)
        assert (abrufe, zugestellt) == (0, []), (
            f"Vorbedingung: die Vorlauf-Sperre muss VOR dem Wetterabruf "
            f"greifen — Abrufe={abrufe}, zugestellt={zugestellt!r}"
        )
        _kein_vorfall(still, "trip-2050s3b-ac10t-nah", "trip", seit)

        _, zugestellt_laut = trip_change_alert_lauf(
            laut, "trip-2050s3b-ac10t-fern", cached=cached, fresh=fresh)
        assert zugestellt_laut == [], (
            f"Vorbedingung: der Kontroll-Trip muss an der SPERRZEIT haengen "
            f"bleiben, nicht am Vorlauf — zugestellt: {zugestellt_laut!r}"
        )
        _genau_ein_grund(
            laut, "trip-2050s3b-ac10t-fern", "trip", seit,
            gate_reason=REASON_COOLDOWN, ausloeser=REASON_FORECAST_CHANGE,
        )
    finally:
        vorlauf_clean_uid(still)
        vorlauf_clean_uid(laut)


def test_ac10_briefing_vorlauf_an_der_amtlichen_trip_warnung_bleibt_still():
    """AC-10 (amtliche Trip-Warnung, ``trip_alert.py:2202-2205``): KEIN
    Eintrag; derselbe Trip mit fernem Briefing stellt tatsaechlich zu."""
    still = vorlauf_fresh_uid("s3b-ac10ta-nah")
    laut = vorlauf_fresh_uid("s3b-ac10ta-fern")
    vorlauf_clean_uid(still)
    vorlauf_clean_uid(laut)
    seit = _jetzt() - timedelta(minutes=1)
    try:
        for uid, trip_id, stunde in (
            (still, "trip-2050s3b-ac10ta-nah", _nah()),
            (laut, "trip-2050s3b-ac10ta-fern", _fern()),
        ):
            vorlauf_write_user_tier(uid, "premium")
            write_trip(uid, trip_id, morgen_stunde=stunde,
                       abend_stunde=_fern_abend(), cooldown_minutes=0)

        versendet, mails = trip_official_alert_run(still, "trip-2050s3b-ac10ta-nah")
        assert versendet is False and mails == [], (
            "Vorbedingung: die Vorlauf-Sperre muss die amtliche Warnung halten"
        )
        _kein_vorfall(still, "trip-2050s3b-ac10ta-nah", "trip", seit)

        versendet, mails = trip_official_alert_run(laut, "trip-2050s3b-ac10ta-fern")
        assert versendet is True and mails, (
            "Positivkontrolle: mit fernem Briefing MUSS die amtliche Warnung "
            "rausgehen — sonst unterscheidet die Bedingung gar nichts"
        )
    finally:
        vorlauf_clean_uid(still)
        vorlauf_clean_uid(laut)


def test_ac10_briefing_vorlauf_am_vergleichs_aenderungsalarm_bleibt_still():
    """AC-10 (Ortsvergleich-Aenderungsalarm, ``compare_alert.py:204-212``):
    KEIN Eintrag; mit fernem Briefing laeuft die Erkennung an."""
    still = vorlauf_fresh_uid("s3b-ac10c-nah")
    laut = vorlauf_fresh_uid("s3b-ac10c-fern")
    p_still, p_laut = "cp-2050s3b-ac10c-nah", "cp-2050s3b-ac10c-fern"
    vorlauf_clean_uid(still)
    vorlauf_clean_uid(laut)
    seit = _jetzt() - timedelta(minutes=1)
    try:
        for uid, preset_id, stunde in (
            (still, p_still, stunde_versetzt(1, zone=VORLAUF_ORTSZONE)),
            (laut, p_laut, stunde_versetzt(5, zone=VORLAUF_ORTSZONE)),
        ):
            vorlauf_write_user_tier(uid, "premium")
            write_location(uid)
            vorlauf_write_presets(uid, [compare_preset(
                preset_id, morgen_stunde=stunde,
                abend_stunde=stunde_versetzt(9, zone=VORLAUF_ORTSZONE),
                cooldown_minutes=0,
            )])

        assert compare_change_alert_run(still) == 0, (
            "Vorbedingung: die Vorlauf-Sperre muss VOR der Erkennung greifen"
        )
        _kein_vorfall(still, p_still, "compare", seit)

        assert compare_change_alert_run(laut) >= 1, (
            "Positivkontrolle: mit fernem Briefing MUSS die Erkennung laufen"
        )
    finally:
        vorlauf_clean_uid(still)
        vorlauf_clean_uid(laut)


def test_ac10_briefing_vorlauf_an_der_amtlichen_vergleichswarnung_bleibt_still():
    """AC-10 (amtlicher Ortsvergleich, ``compare_official_alert.py:165-176``):
    KEIN Eintrag; mit fernem Briefing laeuft der Warnungs-Abruf an."""
    still = vorlauf_fresh_uid("s3b-ac10ca-nah")
    laut = vorlauf_fresh_uid("s3b-ac10ca-fern")
    p_still, p_laut = "cp-2050s3b-ac10ca-nah", "cp-2050s3b-ac10ca-fern"
    vorlauf_clean_uid(still)
    vorlauf_clean_uid(laut)
    seit = _jetzt() - timedelta(minutes=1)
    try:
        for uid, preset_id, stunde in (
            (still, p_still, stunde_versetzt(1, zone=VORLAUF_ORTSZONE)),
            (laut, p_laut, stunde_versetzt(5, zone=VORLAUF_ORTSZONE)),
        ):
            vorlauf_write_user_tier(uid, "premium")
            write_location(uid)
            vorlauf_write_presets(uid, [compare_preset(
                preset_id, morgen_stunde=stunde,
                abend_stunde=stunde_versetzt(9, zone=VORLAUF_ORTSZONE),
                cooldown_minutes=0,
            )])

        with nur_diese_warnquelle(FakeOfficialAlertSource()):
            assert compare_official_alert_run(still) == 0, (
                "Vorbedingung: die Vorlauf-Sperre muss VOR dem Warnungs-Abruf "
                "greifen"
            )
            _kein_vorfall(still, p_still, "compare", seit)

            assert compare_official_alert_run(laut) >= 1, (
                "Positivkontrolle: mit fernem Briefing MUSS der Abruf laufen"
            )
    finally:
        vorlauf_clean_uid(still)
        vorlauf_clean_uid(laut)
