"""TDD RED — Issue #1987 Scheibe S1: nur ZUGESTELLTE Kanaele ruecken vor.

SPEC: ``docs/specs/modules/fix_1987_kanal_anker.md`` (AC-1, AC-2, AC-3, AC-5,
AC-6).

Gepruefte Zusicherung in einem Satz: der rollierende Tier-2-Alarm-Anker wird
je Kanal gefuehrt und ausschliesslich fuer die Kanaele fortgeschrieben, die
den Alarm TATSAECHLICH zugestellt bekommen haben
(``NotificationResult.delivered_channels``) — ein gescheiterter (AC-1),
gar nicht zustellender (AC-2) oder von der Kanal-Schwelle vorab entfernter
Kanal (AC-6) behaelt seinen alten Stand. Der unbedingte Tier-1-Write des
Briefings (#1629) bleibt davon unberuehrt (AC-3), Bestandsdaten ohne
Kanal-Suffix bleiben als Rueckfall lesbar (AC-5).

Angenommene API: ``WeatherSnapshotService.save_alarm_anchor()``/
``.load_alarm_anchor()`` bekommen ``channel`` als Pflicht-Parameter, die
kanalscharfe Ablage ist ``{trip_id}_alarm_anchor_{channel}.json``
(Spec, Implementation Details).

Test-Politik (kein Mock-Theater): echte ``WeatherSnapshotService``-Dateien in
der pytest-isolierten ``get_data_dir()``-Basis (#1133); die Zustellbilanz
entsteht am ECHTEN Transportrand — E-Mail ueber die ``mail_sink``-Naht (kein
SMTP, kein Netz), Telegram ueber den echten ``TelegramOutput``-Guard (#1363),
der bei Testlauf-Herkunft VOR jedem Netzaufruf wirft. Geprueft wird der
GELADENE Anker-Inhalt (``aggregated.gust_max_kmh``), nie ein
Dateiinhalt-String. Jede Zusicherung hat einen Fixtur-Schutz, der die
tatsaechliche Zustellbilanz des Laufs aus dem Alarm-Protokoll nachweist —
ohne ihn waeren die Erwartungen auch dann erfuellt, wenn ein Kanal gar nicht
erst betreten worden waere.

Pfadregel #1409: alle Prueflinge werden ueber ``app.loader`` bzw. relativ zur
Testdatei aufgeloest, nie ueber einen festen Hauptrepo-Pfad.
"""
from __future__ import annotations

import dataclasses
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.helpers.alert_log_fixtures import (
    gust_alert_trip,
    read_log,
    settings_email_and_failing_telegram,
    weather,
)

# Unverwechselbare Boeen-Werte je Anker — sie sagen, WELCHER Stand in der
# Datei steht. Zwei im selben Lauf geschriebene Anker unterscheiden sich im
# Zeitstempel nur um Mikrosekunden; der Inhalt ist eindeutig.
EMAIL_ALTSTAND = 22.0
TELEGRAM_ALTSTAND = 33.0
SMS_ALTSTAND = 44.0
PREMIUM_ALTSTAND = 55.0
ALTBESTAND_BOE = 77.0   # Inhalt der kanallosen Altdatei (AC-5)
TIER1_BOE = 11.0

ANKER_BOE = 10.0        # Vergleichsbasis, gegen die gemeldet wird
FRISCH_HOCH_BOE = 150.0  # Δ 140 km/h -> Dringlichkeit HIGH
FRISCH_NIEDRIG_BOE = 35.0  # Δ 25 km/h -> ausloesend, aber nur LOW (AC-6)

ALLE_KANAELE = ("email", "telegram", "sms", "premium_sms")


def _nutzer(prefix: str) -> str:
    return f"tdd-1987-{prefix}-{uuid.uuid4().hex[:6]}"


def _wetter(gust_kmh: float, *, alter: timedelta = timedelta(0)):
    return dataclasses.replace(
        weather(1, gust_max_kmh=gust_kmh),
        fetched_at=datetime.now(timezone.utc) - alter,
    )


def _ortstag(trip) -> date:
    """Der Tag, den der Alarm-Pfad selbst benutzt (``trip_local_today``)."""
    from services.trip_day import trip_local_today

    return trip_local_today(trip, datetime.now(timezone.utc))


def _anker_pfad(user_id: str, trip_id: str, channel: str) -> Path:
    from app.loader import get_snapshots_dir

    return get_snapshots_dir(user_id) / f"{trip_id}_alarm_anchor_{channel}.json"


def _kanal_anker_boe(user_id: str, trip_id: str, channel: str):
    """Boeenwert im Tier-2-Merker dieses Kanals — ``None``, wenn es ihn nicht gibt."""
    from services.weather_snapshot import WeatherSnapshotService

    geladen = WeatherSnapshotService(user_id=user_id).load_alarm_anchor(
        trip_id, channel=channel,
    )
    return geladen[0].aggregated.gust_max_kmh if geladen else None


def _altstaende_anlegen(user_id: str, trip_id: str, tag: date) -> dict[str, float]:
    """Fuer JEDEN der vier Kanaele einen unterscheidbaren Tier-2-Merker."""
    from services.weather_snapshot import WeatherSnapshotService

    svc = WeatherSnapshotService(user_id=user_id)
    staende = dict(zip(
        ALLE_KANAELE,
        (EMAIL_ALTSTAND, TELEGRAM_ALTSTAND, SMS_ALTSTAND, PREMIUM_ALTSTAND),
    ))
    for channel, boe in staende.items():
        svc.save_alarm_anchor(trip_id, tag, [_wetter(boe)], channel=channel)
    return staende


def _letzter_protokoll_eintrag(user_id: str) -> dict:
    """Die Zustellbilanz des Laufs, wie das Alarm-Protokoll sie festhaelt.

    ``channels_sent`` traegt exakt ``NotificationResult.delivered_channels``
    (``alert_log.py:362``) — der unabhaengige Nachweis, welcher Kanal in
    diesem Lauf wirklich zugestellt hat.
    """
    eintraege = read_log(user_id)["entries"]
    assert eintraege, (
        "Fixtur-Schutz: der Lauf hat keinen Protokoll-Eintrag hinterlassen — "
        "dann ist der Versand gar nicht erst versucht worden und die "
        "Anker-Erwartungen unten waeren trivial wahr."
    )
    return eintraege[-1]


def _alarm_service(user_id: str, mails: list):
    from services.trip_alert import TripAlertService

    settings = settings_email_and_failing_telegram()
    assert settings.can_send_email() is True, (
        "Fixtur-Schutz: ohne sendefaehigen E-Mail-Kanal gaebe es keine "
        "erfolgreiche Zustellung, gegen die sich der Fehlschlag abheben kann."
    )
    assert settings.can_send_telegram() is True, (
        "Fixtur-Schutz: Telegram MUSS betreten werden und dort scheitern — "
        "ein gar nicht erst betretener Kanal wuerde die Zusicherung "
        "trivial erfuellen (kein Varianz-Nachweis)."
    )
    return TripAlertService(
        settings=settings, user_id=user_id,
        mail_sink=lambda subject, body: mails.append(subject),
    )


# ═════════════════════════════════ AC-1 ══════════════════════════════════════


def test_ac1_nur_der_zugestellte_kanal_bekommt_einen_frischen_merker():
    """AC-1.

    GIVEN eine Tour mit den Alarmkanaelen E-Mail und Telegram, beide mit einem
          eigenen, unterscheidbaren Tier-2-Merker.
    WHEN  ein Alarm laeuft, den nur E-Mail zustellt (Telegram scheitert am
          echten Transport-Guard).
    THEN  traegt der E-Mail-Merker den neuen Stand, waehrend der
          Telegram-Merker unveraendert auf seinem Altstand stehen bleibt.

    HEUTE ROT: ``save_alarm_anchor()`` kennt keinen ``channel``-Parameter
    (TypeError) — es gibt genau EINEN kanallosen Merker je Tour, der nach
    jedem versendeten Alarm vorrueckt, gleichgueltig wer ihn bekommen hat.

    Mutations-Gegenprobe (Spec Nr. 1): iteriert der Schreibpfad ueber
    ``effective_channels`` statt ``delivered_channels``, bekaeme auch der
    gescheiterte Telegram-Kanal den frischen Stand — dieser Test wird rot.
    """
    user_id, trip_id = _nutzer("ac1"), "trip-1987-ac1"
    trip = gust_alert_trip(trip_id, alert_channels={"email": True, "telegram": True})
    heute = _ortstag(trip)
    staende = _altstaende_anlegen(user_id, trip_id, heute)

    mails: list = []
    ausgeloest = _alarm_service(user_id, mails).check_and_send_alerts(
        trip, [_wetter(ANKER_BOE, alter=timedelta(hours=1))],
        fresh_weather=[_wetter(FRISCH_HOCH_BOE)],
    )

    assert ausgeloest, "Fixtur-Schutz: das Delta 10 -> 150 km/h muss ausloesen."
    assert mails, "Fixtur-Schutz: die E-Mail muss tatsaechlich zugestellt sein."
    bilanz = _letzter_protokoll_eintrag(user_id)["channels_sent"]
    assert bilanz == ["email"], (
        "Fixtur-Schutz: die Zustellbilanz dieses Laufs muss genau 'E-Mail "
        f"zugestellt, Telegram nicht' lauten, erhalten: {bilanz!r}."
    )

    assert _kanal_anker_boe(user_id, trip_id, "email") == pytest.approx(FRISCH_HOCH_BOE), (
        "AC-1: der zugestellte Kanal MUSS auf den neuen Stand vorruecken "
        f"({FRISCH_HOCH_BOE} km/h), erhalten: "
        f"{_kanal_anker_boe(user_id, trip_id, 'email')}."
    )
    assert _kanal_anker_boe(user_id, trip_id, "telegram") == pytest.approx(
        staende["telegram"]
    ), (
        "AC-1: der NICHT zugestellte Kanal muss auf seinem Altstand "
        f"({staende['telegram']} km/h) stehen bleiben — sonst vergleicht der "
        "naechste Lauf gegen einen Stand, den dieser Empfaenger nie bekommen "
        f"hat. Erhalten: {_kanal_anker_boe(user_id, trip_id, 'telegram')}."
    )


# ═════════════════════════════════ AC-2 ══════════════════════════════════════


def test_ac2_ohne_jede_zustellung_rueckt_kein_einziger_kanal_vor():
    """AC-2.

    GIVEN eine Tour, deren einziger Alarmkanal Telegram ist, mit vorbelegten
          Tier-2-Merkern fuer ALLE vier Kanaele.
    WHEN  ein Alarm laeuft, den kein einziger Kanal zustellt (Telegram
          scheitert am echten Transport-Guard).
    THEN  bleibt JEDER der vier Merker unveraendert — es entsteht nirgends
          ein frischer Stand.

    HEUTE ROT: ``save_alarm_anchor()`` kennt keinen ``channel``-Parameter
    (TypeError). Fachlich schreibt der Bestand hier sogar einen frischen
    (kanallosen) Merker, obwohl niemand etwas bekommen hat — genau der Bug
    aus #1987.
    """
    user_id, trip_id = _nutzer("ac2"), "trip-1987-ac2"
    trip = gust_alert_trip(trip_id, alert_channels={"telegram": True})
    heute = _ortstag(trip)
    staende = _altstaende_anlegen(user_id, trip_id, heute)

    mails: list = []
    ausgeloest = _alarm_service(user_id, mails).check_and_send_alerts(
        trip, [_wetter(ANKER_BOE, alter=timedelta(hours=1))],
        fresh_weather=[_wetter(FRISCH_HOCH_BOE)],
    )

    assert ausgeloest, (
        "Fixtur-Schutz: der Lauf muss bis zum Schreibpfad kommen — Telegram "
        "war erreichbar (nur der Transport scheiterte), der Bestand wertet "
        "das als 'gesendet'."
    )
    assert not mails, "Fixtur-Schutz: E-Mail ist hier gar nicht konfiguriert."
    bilanz = _letzter_protokoll_eintrag(user_id)["channels_sent"]
    assert bilanz == [], (
        f"Fixtur-Schutz: kein Kanal darf zugestellt haben, erhalten: {bilanz!r}."
    )

    for channel, alt in staende.items():
        assert _kanal_anker_boe(user_id, trip_id, channel) == pytest.approx(alt), (
            f"AC-2: ohne jede Zustellung darf KEIN Kanal vorruecken — "
            f"{channel!r} steht auf "
            f"{_kanal_anker_boe(user_id, trip_id, channel)} statt {alt} km/h."
        )


# ═════════════════════════════════ AC-6 ══════════════════════════════════════


def test_ac6_schwellengefilterter_kanal_bekommt_keinen_frischen_merker():
    """AC-6.

    GIVEN eine Tour mit den Alarmkanaelen E-Mail und Telegram, bei der
          Telegram erst ab Dringlichkeit MODERATE gemeldet wird, und beide
          Kanaele haben einen eigenen Tier-2-Merker.
    WHEN  ein Alarm der Dringlichkeit LOW laeuft — ``split_by_threshold()``
          entfernt Telegram VOR dem Versand, er landet also weder in
          ``sent_channels`` noch in ``failed_channels``.
    THEN  bekommt Telegram KEINEN frischen Merker (er hat nichts empfangen),
          waehrend der E-Mail-Merker vorrueckt.

    HEUTE ROT: ``save_alarm_anchor()`` kennt keinen ``channel``-Parameter
    (TypeError).

    Mutations-Gegenprobe (Spec Nr. 1): iteriert der Schreibpfad ueber
    ``effective_channels`` (rohes Opt-in, enthaelt Telegram) statt ueber
    ``delivered_channels``, wird dieser Test rot — genau der Fehler, der die
    Zusicherung still bricht.
    """
    user_id, trip_id = _nutzer("ac6"), "trip-1987-ac6"
    trip = gust_alert_trip(trip_id, alert_channels={"email": True, "telegram": True})
    trip.alert_channel_thresholds = {"telegram": "MODERATE"}
    heute = _ortstag(trip)
    staende = _altstaende_anlegen(user_id, trip_id, heute)

    mails: list = []
    svc = _alarm_service(user_id, mails)
    ausgeloest = svc.check_and_send_alerts(
        trip, [_wetter(ANKER_BOE, alter=timedelta(hours=1))],
        fresh_weather=[_wetter(FRISCH_NIEDRIG_BOE)],
    )

    assert ausgeloest, "Fixtur-Schutz: das Delta 10 -> 35 km/h muss ausloesen."
    assert svc._last_below_threshold_channels == {"telegram"}, (
        "Fixtur-Schutz: genau Telegram muss an der Kanal-Schwelle "
        "haengenbleiben, erhalten: "
        f"{svc._last_below_threshold_channels!r} — sonst misst dieser Test "
        "den Schwellenfall gar nicht."
    )
    bilanz = _letzter_protokoll_eintrag(user_id)["channels_sent"]
    assert bilanz == ["email"], (
        f"Fixtur-Schutz: nur E-Mail darf zugestellt haben, erhalten: {bilanz!r}."
    )

    assert _kanal_anker_boe(user_id, trip_id, "email") == pytest.approx(
        FRISCH_NIEDRIG_BOE
    ), (
        "AC-6: der zugestellte Kanal muss vorruecken, erhalten: "
        f"{_kanal_anker_boe(user_id, trip_id, 'email')}."
    )
    assert _kanal_anker_boe(user_id, trip_id, "telegram") == pytest.approx(
        staende["telegram"]
    ), (
        "AC-6: ein unterhalb der Dringlichkeitsschwelle entfernter Kanal hat "
        "nichts empfangen und darf deshalb keinen frischen Merker bekommen — "
        f"erhalten: {_kanal_anker_boe(user_id, trip_id, 'telegram')} statt "
        f"{staende['telegram']} km/h."
    )


# ═════════════════════════════════ AC-5 ══════════════════════════════════════


def test_ac5_kanallose_altdatei_dient_jedem_kanal_als_rueckfall():
    """AC-5.

    GIVEN eine Tour besitzt ausschliesslich die kanallose Altdatei
          ``{trip_id}_alarm_anchor.json`` (Bestand vor dieser Scheibe) und
          KEINE kanalspezifische Datei.
    WHEN  der erste Lesevorgang fuer beliebige Kanaele laeuft (hier
          ``premium_sms`` und ``email``).
    THEN  liefern beide den Inhalt der Altdatei als Vergleichsbasis — kein
          Datenverlust, kein Migrationsskript noetig.

    HEUTE ROT: ``load_alarm_anchor()`` kennt keinen ``channel``-Parameter
    (TypeError).

    Die Altdatei entsteht ueber den echten Serialisierer (``save()`` schreibt
    dasselbe Schema) und wird anschliessend unter den kanallosen Namen
    kopiert — reines Setup der Ausgangslage, keine Zusicherung ueber
    Dateiinhalte. Der undatierte Anker wird danach mit einem ANDEREN Wert
    ueberschrieben: liest die Kette versehentlich die falsche Datei, faellt
    das sofort auf.
    """
    from app.loader import get_snapshots_dir
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = _nutzer("ac5"), "trip-1987-ac5"
    trip = gust_alert_trip(trip_id, alert_channels={"email": True})
    heute = _ortstag(trip)
    svc = WeatherSnapshotService(user_id=user_id)

    svc.save(trip_id, [_wetter(ALTBESTAND_BOE)], heute)
    quelle = get_snapshots_dir(user_id) / f"{trip_id}.json"
    (get_snapshots_dir(user_id) / f"{trip_id}_alarm_anchor.json").write_text(
        quelle.read_text()
    )
    svc.save(trip_id, [_wetter(TIER1_BOE)], heute)

    for channel in ("premium_sms", "email"):
        assert not _anker_pfad(user_id, trip_id, channel).exists(), (
            f"Fixtur-Schutz: fuer {channel!r} darf es KEINE kanalspezifische "
            "Datei geben, sonst prueft dieser Test den Rueckfall nicht."
        )
        geladen = svc.load_alarm_anchor(trip_id, channel=channel)
        assert geladen, (
            f"AC-5: die kanallose Altdatei muss fuer {channel!r} weiterhin als "
            "Vergleichsbasis dienen — sonst verlieren alle Bestandstouren beim "
            "Deploy ihren rollierenden Anker."
        )
        assert geladen[0].aggregated.gust_max_kmh == pytest.approx(ALTBESTAND_BOE), (
            f"AC-5: {channel!r} muss den Inhalt der Altdatei "
            f"({ALTBESTAND_BOE} km/h) sehen, erhalten: "
            f"{geladen[0].aggregated.gust_max_kmh} km/h."
        )


# ═════════════════ AC-3 (Regressionsschutz #1629, Gegenprobe) ════════════════
#
# AC-3 nennt ZWEI gleichwertige #1629-Szenarien, und der Scheduler bedient sie
# an ZWEI verschiedenen Stellen. Beide muessen bewacht sein: eine Kopplung des
# Tier-1-Writes an eine Zustellbedingung waere an jeder von ihnen einzeln
# moeglich, und je Naht faellt nur der Test, der genau sie durchlaeuft
# (Adversary-Befund F001).
#
# Die Briefing-Laeufe werden nicht nachgebaut, sondern ueber die erprobten,
# mockfreien Helfer des #1629-Tests gefahren (echte Kanal-Guards, echter
# Scheduler mit Fixture-Wetterquelle) — ein zweiter Nachbau wuerde nur eine
# zweite Fehlerquelle schaffen.


def _briefing_lauf_mit_ausnahme(user_id: str):
    """Naht 1 (`trip_report_scheduler.py:1543`): der Versandaufruf WIRFT.

    Der Fehler entsteht am echten Konfigurations-Guard des echten
    E-Mail-Kanals — dieselbe Ausnahmeklasse, aus demselben Modul, wie im
    Produktivfall vom 08.08.2026.
    """
    from tests.tdd.test_briefing_anchor_survives_dispatch_failure import (
        _run_failing_briefing,
        _trip as _briefing_trip,
    )

    trip = _briefing_trip(f"trip-1987-ac3a-{uuid.uuid4().hex[:6]}", with_levels=True)
    _run_failing_briefing(user_id, trip, gust=25.0)
    return trip


def _briefing_lauf_ohne_zustellung(user_id: str):
    """Naht 2 (`trip_report_scheduler.py:1651`): KEIN Kanal erreichbar, aber
    auch KEINE Ausnahme — der regulaere Pfad laeuft bis zum Ende durch und
    endet mit ``result.sent == False``.

    Aufbau: E-Mail ist fuer die Tour aus, Telegram an und garantiert
    scheiternd (echter ``TelegramOutput``-Guard #1363, wirft VOR jedem
    Netzaufruf). Telegram ist fail-soft, die Ausnahme kommt also nie beim
    Scheduler an — genau der Unterschied zu Naht 1.
    """
    from tests.tdd.test_briefing_anchor_survives_dispatch_failure import (
        _fixture_scheduler,
        _trip as _briefing_trip,
    )

    trip = _briefing_trip(
        f"trip-1987-ac3b-{uuid.uuid4().hex[:6]}", with_levels=True,
        send_email=False, send_telegram=True,
    )
    ergebnis = _fixture_scheduler(25.0)(
        settings=settings_email_and_failing_telegram(), user_id=user_id,
    )._send_trip_report_outcome(trip, "morning", on_demand=False)
    assert ergebnis == "channels_unreachable", (
        "Fixtur-Schutz: dieser Lauf muss OHNE Ausnahme enden und ehrlich als "
        f"nicht zugestellt gelten, erhalten: {ergebnis!r} — sonst prueft er "
        "dieselbe Naht wie die Ausnahme-Variante und der zweite Fall bleibt "
        "unbewacht."
    )
    return trip


@pytest.mark.parametrize(
    "briefing_lauf, naht",
    [
        (_briefing_lauf_mit_ausnahme, "Ausnahme aus dem Versandaufruf (:1543)"),
        (_briefing_lauf_ohne_zustellung, "kein Kanal erreichbar, ohne Ausnahme (:1651)"),
    ],
    ids=["naht_ausnahme", "naht_unerreichbar"],
)
def test_ac3_briefing_ohne_jede_zustellung_schreibt_tier1_aber_keinen_kanal_merker(
    briefing_lauf, naht,
):
    """AC-3.

    GIVEN ein Briefing-Lauf, bei dem auf keinem Kanal etwas zugestellt wird —
          einmal, weil der Versandaufruf mit einer Ausnahme abbricht, einmal,
          weil der regulaere Pfad mit ``result.sent == False`` endet. Die Spec
          nennt beide Faelle ausdruecklich gleichwertig.
    WHEN  der Briefing-Lauf abgeschlossen ist.
    THEN  ist der Tier-1-Briefing-Anker TROTZDEM geschrieben und ein
          anschliessender Abweichungs-Alarm-Check findet eine gueltige
          Vergleichsbasis (nicht ``None``) — gleichzeitig ist fuer KEINEN der
          vier Kanaele ein Tier-2-Merker entstanden: die Zustellungsbindung
          dieser Scheibe gilt fuer Tier 2, der unbedingte Tier-1-Write
          bleibt unveraendert bestehen (E1).

    Der Tier-1-Teil dieser Zusicherung ist Bestandsverhalten und MUSS es
    bleiben.

    Mutations-Gegenprobe (Spec Nr. 2): koppelt eine Verfaelschung den
    Tier-1-Write an eine Zustellbedingung, kehrt die #1629-Regression zurueck
    (Vergleichsbasis ``None``, Abweichungs-Wache strukturell blind) und
    dieser Test wird rot. Beide Parameter sind noetig: die Mutation ist an
    jeder der beiden Nahtstellen EINZELN moeglich, und je Naht faellt nur der
    Fall, der genau sie durchlaeuft (Adversary-Befund F001).
    """
    from app.loader import get_data_dir
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService
    from tests.helpers.alert_log_fixtures import settings_email_only

    user_id = _nutzer("ac3")
    # Im Betrieb existiert die Nutzerablage laengst (der Nutzer hat Touren).
    # Hier legt sie sonst erst der Anker-Write selbst an — und dann scheitert
    # bei einer Mutation, die genau ihn ausschaltet, der nachfolgende
    # Nachliefer-Vermerk mit einem FileNotFoundError. Der Test waere zwar rot,
    # aber am falschen Grund: er wuerde die Reihenfolge zweier Schreibvorgaenge
    # messen statt der Vergleichsbasis. Deshalb Vorbedingung statt Zufall.
    get_data_dir(user_id).mkdir(parents=True, exist_ok=True)
    trip = briefing_lauf(user_id)

    basis = TripAlertService(
        settings=settings_email_only(), user_id=user_id,
    )._get_cached_weather(trip, tagesgleicher_anker_noetig=True)
    assert basis, (
        f"AC-3 ({naht}): nach einem Briefing ohne jede Zustellung muss der "
        "Tier-1-Briefing-Anker trotzdem geschrieben sein und eine gueltige "
        "Vergleichsbasis liefern — sonst ist die Abweichungs-Wache den "
        "ganzen Tag blind (#1629)."
    )

    svc = WeatherSnapshotService(user_id=user_id)
    for channel in ALLE_KANAELE:
        assert svc.load_alarm_anchor(trip.id, channel=channel) is None, (
            f"AC-3 ({naht}): ein Briefing ohne jede Zustellung darf fuer "
            f"{channel!r} KEINEN rollierenden Tier-2-Merker anlegen — dieser "
            "Empfaenger hat nichts bekommen. Nur Tier 1 bleibt unbedingt (E1)."
        )
