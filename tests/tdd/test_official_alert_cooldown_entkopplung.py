"""TDD RED — Der amtliche Trip-Alarm liest die Sperrzeit des Aenderungsalarms
nicht mehr (Issue #1467 S4a, AC-4 bis AC-6, AC-10, AC-11, AC-15).

SPEC:    docs/specs/modules/rework_1467_s4a_amtlich.md
KONTEXT: docs/context/rework-1467-s4a-amtlich.md

Kernfall (E1): ``trip_alert.py:1494`` liest heute den ``ThrottleStore``-Scope
``"trip"`` — denselben Topf, den der Aenderungsalarm bei ``:358`` befuellt. Ein
Aenderungsalarm um 16:00 verschluckt damit eine amtliche GELB→ORANGE-
Verschaerfung um 16:15, bis zu zwei Stunden lang (Default-Cooldown 120 min).
Genau diese Wirkung schliesst das Issue fuer den Ortsvergleich aus.

Lesen und Schreiben werden getrennt entschieden und hier getrennt bewacht: das
**Lesen** faellt weg (AC-4), das **Schreiben** bleibt (AC-5). Ohne AC-5 koennte
ein Umbau „aus Symmetriegruenden" auch das Schreiben entfernen; die Menge der
Aenderungsalarme stiege still.

Mock-frei: echte Trips auf Platte, echter ``ThrottleStore``, echte Warnquelle in
der Registry (kein Netz), Versand ueber die ``mail_sink``-DI-Naht. #1409.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tests.helpers.briefing_imminent_fixtures import (  # noqa: E402
    TRIP_ZONE, clean_uid, fresh_uid, protokoll_eintraege, ruhezeit_woanders,
    stunde_versetzt, trip_change_alert_run, write_trip, write_user_tier,
)
from tests.helpers.nowcast_gate_fixtures import (  # noqa: E402
    read_daily_counter, read_throttle_state, record_throttle,
    settings_no_channel_reachable, suppression_reasons,
)
from tests.helpers.official_alert_gate_fixtures import (  # noqa: E402
    StufenWarnquelle, gelb_ins_melde_gedaechtnis, schnappschuss_speichern,
    trip_amtlicher_lauf,
)

TRIP, SCOPE_TRIP = "trip-1467s4a", "trip"

#: Produktiv-Default des Aenderungsalarm-Cooldowns (``throttle_hours=2``).
#: Ausdruecklich gesetzt, damit die Sperre real ausgewertet wird statt in einen
#: 0-Kurzschluss zu laufen.
COOLDOWN_MINUTEN = 120

#: Abstand Aenderungsalarm (T) -> amtliche Eskalation (T+15): deutlich INNERHALB
#: des Cooldowns, sonst bewiese der Test nur, dass eine abgelaufene Sperre nicht
#: sperrt.
ESKALATION_NACH_MINUTEN = 15


@pytest.fixture
def nutzer():
    vergeben: list[str] = []

    def _neu(kennung: str, tier: str = "premium") -> str:
        user_id = fresh_uid(f"s4a-{kennung}")
        clean_uid(user_id)
        write_user_tier(user_id, tier)
        vergeben.append(user_id)
        return user_id

    yield _neu
    for user_id in vergeben:
        clean_uid(user_id)


def _trip_schreiben(user_id: str, **kwargs) -> None:
    """Trip mit Briefing-Zeiten weit ausserhalb des 60-Minuten-Vorlaufs (#1594)
    — sonst misst der Test die Briefing-Sperre statt der Sperrzeit."""
    kwargs.setdefault("morgen_stunde", stunde_versetzt(5, zone=TRIP_ZONE))
    kwargs.setdefault("abend_stunde", stunde_versetzt(9, zone=TRIP_ZONE))
    kwargs.setdefault("quiet", ruhezeit_woanders(zone=TRIP_ZONE))
    kwargs.setdefault("cooldown_minutes", COOLDOWN_MINUTEN)
    write_trip(user_id, TRIP, **kwargs)
    schnappschuss_speichern(user_id, TRIP)


def _aenderungsalarm_zugestellt_um(user_id: str, vor_minuten: int) -> datetime:
    """Genau die Spur eines zugestellten Aenderungsalarms — ueber den ECHTEN
    ``ThrottleStore`` (``trip_alert.py:358`` schreibt Scope ``"trip"``)."""
    moment = datetime.now(timezone.utc) - timedelta(minutes=vor_minuten)
    record_throttle(user_id, SCOPE_TRIP, TRIP, moment)
    return moment


def _sperrzeit_eintrag(user_id: str):
    """Issue #2065: der Eintrag traegt seit dieser Aenderung die zuletzt
    gemeldete Menge mit (`{"at": iso, "precip_mm": float|null}`). Gelesen
    wird deshalb ueber die oeffentliche Store-Schnittstelle, die BEIDE
    Formate kennt — die Zusicherung dieses Tests ist "es steht ein neuerer
    Zeitpunkt drin", nicht "die Datei sieht so und so aus"."""
    from services.throttle_store import ThrottleStore

    return ThrottleStore(user_id).last_sent(SCOPE_TRIP, TRIP)


# ═══════════ AC-4 (Kernfall): Eskalation kommt trotz Sperrzeit an ═══════════


def test_ac4_amtliche_eskalation_kommt_trotz_juengerem_aenderungsalarm_an(nutzer):
    """AC-4: Um T wurde ein Aenderungsalarm zugestellt (Topf ``"trip"``
    befuellt). Um T+15 verschaerft sich dieselbe amtliche Warnung von GELB (2)
    auf ORANGE (3) — die Eskalation MUSS zugestellt werden.

    Der Aufbau faehrt die echte Eskalationslogik: Runde 1 schreibt GELB ins
    Melde-Gedaechtnis, Runde 2 liefert dieselbe Warnung eine Stufe hoeher;
    ``official_alert_revision_verdict()`` entscheidet selbst, dass es eine
    Eskalation ist. Eine handgesetzte Zustandsdatei uebersprange diese
    Entscheidung und messe am Pruefling vorbei.

    Mutations-Gegenprobe (Pflicht): das Lesen von Scope ``"trip"`` im amtlichen
    Pfad wieder einbauen MUSS diesen Test rot machen.

    ROT HEUTE: ``trip_alert.py:1494`` liest denselben Topf und bricht ab.
    """
    uid = nutzer("ac4")
    _trip_schreiben(uid)
    quelle = StufenWarnquelle()

    erkannt = gelb_ins_melde_gedaechtnis(uid, TRIP, quelle)
    assert erkannt == 1, (
        f"Aufbau-Nachweis: GELB muss zuerst erkannt und ins Melde-Gedaechtnis "
        f"geschrieben werden, erkannt: {erkannt}")

    _aenderungsalarm_zugestellt_um(uid, ESKALATION_NACH_MINUTEN)
    assert _sperrzeit_eintrag(uid) is not None, (
        f"Aufbau-Nachweis: Topf 'trip' muss befuellt sein: {read_throttle_state(uid)!r}")

    quelle.level = 3
    gesendet, mails = trip_amtlicher_lauf(uid, quelle=quelle)

    assert gesendet >= 1, (
        f"Die amtliche GELB→ORANGE-Eskalation {ESKALATION_NACH_MINUTEN} Minuten "
        f"nach einem Aenderungsalarm MUSS zugestellt werden — der amtliche Pfad "
        f"darf dessen Sperrzeit-Topf nicht mehr lesen. Zugestellt: {gesendet}, "
        f"Mails: {len(mails)}")
    assert len(mails) >= 1, f"Zustellung auf mindestens einem Kanal: {mails!r}"


def test_ac4_gegenprobe_ohne_sperrzeit_bleibt_die_zustellung_unveraendert(nutzer):
    """AC-4 (Gegenprobe): Derselbe Ablauf OHNE vorbelegte Sperrzeit stellt
    ebenfalls zu. Trennt „Sperrzeit wirkt nicht" von „Aufbau kaputt" — ohne diese
    Haelfte waere der Test oben auch dann rot, wenn Schnappschuss, Warnquelle
    oder Eskalation gar nicht traegen.
    """
    uid = nutzer("ac4-frei")
    _trip_schreiben(uid)
    quelle = StufenWarnquelle()

    assert gelb_ins_melde_gedaechtnis(uid, TRIP, quelle) == 1
    assert _sperrzeit_eintrag(uid) is None, (
        f"Aufbau-Nachweis: hier darf KEINE Sperrzeit stehen: "
        f"{read_throttle_state(uid)!r}")

    quelle.level = 3
    gesendet, mails = trip_amtlicher_lauf(uid, quelle=quelle)
    assert gesendet >= 1 and len(mails) >= 1, (
        f"Ohne Sperrzeit muss unveraendert zugestellt werden: gesendet={gesendet}, "
        f"Mails={len(mails)}")


# ══════ AC-5: das SCHREIBEN bleibt — die harmlose Richtung bleibt zu ═══════


def test_ac5_amtlicher_alarm_schreibt_weiterhin_in_den_trip_sperrzeit_topf(nutzer):
    """AC-5: Nach der zugestellten Eskalation steht ein NEUER Eintrag im Topf
    ``"trip"`` — ``trip_alert.py:1539`` bleibt bestehen.

    Gemessen am Zeitstempel, nicht an blosser Anwesenheit: der Topf war vor dem
    Lauf bereits befuellt (Aenderungsalarm zu T). „Neuer Eintrag" heisst also
    „juenger als der vorbelegte" — ein Test auf „Schluessel vorhanden" waere
    schon vor dem Lauf gruen und bewachte nichts.

    ROT HEUTE: der Lauf stellt gar nicht zu (AC-4), es gibt keinen neuen Eintrag.
    """
    uid = nutzer("ac5")
    _trip_schreiben(uid)
    quelle = StufenWarnquelle()
    assert gelb_ins_melde_gedaechtnis(uid, TRIP, quelle) == 1

    vorher_moment = _aenderungsalarm_zugestellt_um(uid, ESKALATION_NACH_MINUTEN)
    vorher = _sperrzeit_eintrag(uid)

    quelle.level = 3
    gesendet, mails = trip_amtlicher_lauf(uid, quelle=quelle)
    nachher = _sperrzeit_eintrag(uid)

    assert (gesendet, len(mails)) >= (1, 1), (
        f"Voraussetzung: die Eskalation muss zugestellt werden — sonst kann "
        f"nichts gebucht worden sein: gesendet={gesendet}, Mails={len(mails)}")
    assert nachher is not None, (
        f"Der amtliche Pfad MUSS weiter in den Topf 'trip' schreiben: "
        f"{read_throttle_state(uid)!r}")
    assert nachher != vorher, (
        f"Der Eintrag muss NEU sein, nicht der vorbelegte: vorher={vorher!r}, "
        f"nachher={nachher!r}")
    assert nachher > vorher_moment, (
        f"Der neue Eintrag muss nach {vorher_moment} liegen, steht auf {nachher!r}")


def test_ac5_nachfolgender_aenderungsalarm_bleibt_wie_bisher_gesperrt(nutzer):
    """AC-5 (zweite Haelfte, Regressionswaechter): Weil das Schreiben bleibt,
    bleibt die harmlose Richtung zu — ein Aenderungsalarm NACH dem amtlichen
    Alarm ist innerhalb des Cooldowns weiterhin gesperrt.

    Gemessen an der Wetterabruf-Naht (``_fetch_fresh_weather``): 0 Abrufe heisst
    „vor dem Abruf gesperrt". Der Kontroll-Nutzer beweist, dass der Zaehler
    hochgehen kann — ohne ihn misst „0" moeglicherweise eine tote Naht.
    """
    uid = nutzer("ac5-folge")
    _trip_schreiben(uid)
    quelle = StufenWarnquelle()
    assert gelb_ins_melde_gedaechtnis(uid, TRIP, quelle) == 1

    quelle.level = 3
    gesendet, mails = trip_amtlicher_lauf(uid, quelle=quelle)
    assert (gesendet, len(mails)) >= (1, 1), (
        f"Voraussetzung: die amtliche Warnung muss zugestellt werden: "
        f"gesendet={gesendet}, Mails={len(mails)}")

    abrufe_gesperrt = trip_change_alert_run(uid, TRIP)

    kontrolle = nutzer("ac5-kontrolle")
    _trip_schreiben(kontrolle)
    abrufe_frei = trip_change_alert_run(kontrolle, TRIP)

    assert abrufe_frei >= 1, (
        f"Kontroll-Lauf: ohne Sperrzeit MUSS der Aenderungsalarm bis zum "
        f"Wetterabruf kommen ({abrufe_frei} Abrufe)")
    assert abrufe_gesperrt == 0, (
        f"Der amtliche Alarm muss den nachfolgenden Aenderungsalarm wie bisher "
        f"sperren, es waren {abrufe_gesperrt} Wetterabrufe")


# ══ AC-6: der Aenderungsalarm-Pfad selbst bleibt vollstaendig unangetastet ══


def test_ac6_aenderungsalarm_drosselung_unveraendert(nutzer):
    """AC-6 (Regressionswaechter): Der Aenderungsalarm-Pfad
    (``trip_alert.py:246``) drosselt unveraendert — frische Sperrzeit sperrt,
    keine und abgelaufene lassen durch. Wuerde jemand
    ``_is_throttled_with_cooldown`` „aufraeumend" mit entfernen, verloere der
    Aenderungsalarm still seine Drosselung.
    """
    gesperrt = nutzer("ac6-gesperrt")
    _trip_schreiben(gesperrt)
    _aenderungsalarm_zugestellt_um(gesperrt, ESKALATION_NACH_MINUTEN)

    frei = nutzer("ac6-frei")
    _trip_schreiben(frei)

    abgelaufen = nutzer("ac6-abgelaufen")
    _trip_schreiben(abgelaufen)
    _aenderungsalarm_zugestellt_um(abgelaufen, COOLDOWN_MINUTEN + 30)

    assert trip_change_alert_run(gesperrt, TRIP) == 0, (
        "Frische Sperrzeit muss den Aenderungsalarm vor dem Wetterabruf stoppen")
    assert trip_change_alert_run(frei, TRIP) >= 1, (
        "Ohne Sperrzeit muss der Aenderungsalarm unveraendert durchlaufen")
    assert trip_change_alert_run(abgelaufen, TRIP) >= 1, (
        f"Eine {COOLDOWN_MINUTEN + 30} Minuten alte Sperrzeit ist abgelaufen")


# ══════ AC-10: ein pausierter Trip alarmiert weiterhin (Absicht #995) ══════


def test_ac10_pausierter_trip_alarmiert_amtlich_weiter(nutzer):
    """AC-10 (Regressionswaechter): Ein Trip mit gesetztem ``paused_at`` bekommt
    seine amtliche Warnung trotzdem.

    Trips kennen den Stilllegungs-Riegel des Ortsvergleichs nicht — Absicht seit
    #995 (``trip_report_scheduler.py:882-888``: die Pause gilt NUR fuer den
    Briefing-Versand, nicht fuer den Alarm-Dispatch). Wuerde jemand
    ``is_silenced`` beim Vereinheitlichen in den Baustein ziehen, verstummte der
    Alarm dieser Trips still (Risiko R-C).
    """
    uid = nutzer("ac10")
    _trip_schreiben(uid, paused_at="2026-08-01T00:00:00Z")
    quelle = StufenWarnquelle()
    assert gelb_ins_melde_gedaechtnis(uid, TRIP, quelle) == 1

    quelle.level = 3
    gesendet, mails = trip_amtlicher_lauf(uid, quelle=quelle)
    assert gesendet >= 1 and len(mails) >= 1, (
        f"Ein pausierter Trip pausiert nur den Briefing-Versand, nicht den Alarm "
        f"(#995): gesendet={gesendet}, Mails={len(mails)}")


# ═══ AC-11: der amtliche Pfad protokolliert seinen Unterdrueckungsgrund ═══
#
# ABGELOEST durch #2050 S3b (Szenario 10, AC-5). Bis dahin sicherte dieser Test
# das GEGENTEIL zu: der amtliche Pfad durfte KEINEN Grund protokollieren
# (Geltungsbereich strikt Nowcast-only, Luecke E3 ausdruecklich offen). Genau
# diese Beschraenkung faellt — jede Unterdrueckung bekommt einen benannten
# Grund. Der Test bleibt deshalb an DERSELBEN Flaeche stehen und prueft sie in
# der NEUEN Richtung, statt ersatzlos zu verschwinden: sonst liesse sich die
# Abloesung spaeter nicht mehr von einem stillen "Schutz entfernt"
# unterscheiden.
#
# SPEC: docs/specs/modules/feat_2050_s3b_budget_und_unterdrueckungsgrund.md


def test_ac11_unterdrueckter_amtlicher_alarm_protokolliert_seinen_grund(nutzer):
    """AC-11, abgeloest durch #2050 S3b (vormals E3-Regressionswaechter).

    Scheitert der amtliche Trip-Alarm an der Ruhezeit, entsteht seither SEHR
    WOHL ein Protokolleintrag — mit dem Grund ``quiet_hours`` und dem
    Ausloeser ``official_alert``. Neues Verhalten brauchte es dafuer nicht:
    ``check_official_alert_gate`` liefert den passenden ``GateResult.reason``
    seit #1467 S4a mit, der Aufrufer verwarf ihn nur.

    Der Ausloeser wird MITGEPRUEFT: Sperrgrund und Ausloeser duerfen nicht
    verschmelzen, sonst laese das Briefing spaeter „Ruhezeit" als Meldungsart.
    """
    from services.alert_log import REASON_OFFICIAL_ALERT, REASON_QUIET_HOURS

    uid = nutzer("ac11")
    jetzt = datetime.now(timezone.utc).astimezone(TRIP_ZONE)
    ruhezeit_jetzt = ((jetzt - timedelta(minutes=30)).strftime("%H:%M"),
                      (jetzt + timedelta(minutes=30)).strftime("%H:%M"))
    _trip_schreiben(uid, quiet=ruhezeit_jetzt)
    quelle = StufenWarnquelle()
    assert gelb_ins_melde_gedaechtnis(uid, TRIP, quelle) == 1

    protokoll_vorher = protokoll_eintraege(uid)
    quelle.level = 3
    gesendet, mails = trip_amtlicher_lauf(uid, quelle=quelle)
    neue = protokoll_eintraege(uid)[len(protokoll_vorher):]

    assert (gesendet, mails) == (0, []), (
        f"Voraussetzung: die Ruhezeit muss unterdruecken: gesendet={gesendet}, "
        f"Mails={mails!r}")
    amtliche = [e for e in neue if e.get("reason") == REASON_OFFICIAL_ALERT]
    assert len(amtliche) == 1, (
        f"Der amtliche Pfad muss GENAU EINEN Unterdrueckungs-Eintrag mit dem "
        f"Ausloeser {REASON_OFFICIAL_ALERT!r} hinterlassen, gefunden "
        f"{len(amtliche)}: {neue!r}")
    assert suppression_reasons(amtliche[0]) == {REASON_QUIET_HOURS}, (
        f"Der amtliche Pfad muss seine Ruhezeit-Unterdrueckung seit #2050 S3b "
        f"mit dem Grund {REASON_QUIET_HOURS!r} protokollieren (vormals: gar "
        f"nicht): {amtliche[0]!r}")


# ═══ AC-15: gebucht wird ausschliesslich nach erfolgreicher Zustellung ═════


def test_ac15_gescheiterte_zustellung_bucht_weder_zaehler_noch_sperrzeit(nutzer):
    """AC-15 (Regressionswaechter): Ist kein Kanal erreichbar, bleiben
    Tageszaehler UND Sperrzeit-Eintrag exakt unveraendert; der Kontroll-Nutzer
    belegt, dass beide Buchungen ueberhaupt stattfinden (die erste Haelfte allein
    waere auch von einer Fassung erfuellt, die NIE bucht).

    Zielt auf Risiko R-A: der Umbau verschiebt die Reihenfolge der Stufen;
    wandert dabei ``increment()`` vor den Versand, zaehlen gescheiterte Versuche
    als verbraucht und der Nutzer verliert Kontingent, ohne je eine Warnung
    gesehen zu haben.
    """
    stumm = nutzer("ac15-stumm", tier="free")
    _trip_schreiben(stumm)
    quelle_stumm = StufenWarnquelle()
    assert gelb_ins_melde_gedaechtnis(stumm, TRIP, quelle_stumm) == 1
    zaehler_vorher = read_daily_counter(stumm, zone=TRIP_ZONE)
    sperrzeit_vorher = read_throttle_state(stumm)

    quelle_stumm.level = 3
    gesendet, mails = trip_amtlicher_lauf(
        stumm, quelle=quelle_stumm, settings=settings_no_channel_reachable())

    assert (gesendet, mails) == (0, []), (
        f"Ohne erreichbaren Kanal darf nichts als versendet gelten: "
        f"gesendet={gesendet}, Mails={mails!r}")
    assert read_daily_counter(stumm, zone=TRIP_ZONE) == zaehler_vorher, (
        f"Tageszaehler trotz gescheiterter Zustellung erhoeht: {zaehler_vorher} "
        f"-> {read_daily_counter(stumm, zone=TRIP_ZONE)}")
    assert read_throttle_state(stumm) == sperrzeit_vorher, (
        f"Sperrzeit trotz gescheiterter Zustellung gebucht: {sperrzeit_vorher!r} "
        f"-> {read_throttle_state(stumm)!r}")

    ok = nutzer("ac15-ok", tier="free")
    _trip_schreiben(ok)
    quelle_ok = StufenWarnquelle()
    assert gelb_ins_melde_gedaechtnis(ok, TRIP, quelle_ok) == 1
    quelle_ok.level = 3
    gesendet_ok, mails_ok = trip_amtlicher_lauf(ok, quelle=quelle_ok)

    assert (gesendet_ok, len(mails_ok)) >= (1, 1), (
        f"Kontroll-Lauf: mit erreichbarem Kanal muss zugestellt werden: "
        f"gesendet={gesendet_ok}, Mails={len(mails_ok)}")
    assert read_daily_counter(ok, zone=TRIP_ZONE) == 1, (
        f"Nach erfolgreicher Zustellung muss der Tageszaehler auf 1 stehen, "
        f"steht auf {read_daily_counter(ok, zone=TRIP_ZONE)}")
    assert (read_throttle_state(ok).get(SCOPE_TRIP) or {}).get(TRIP), (
        f"Nach erfolgreicher Zustellung muss die Sperrzeit gebucht sein: "
        f"{read_throttle_state(ok)!r}")
