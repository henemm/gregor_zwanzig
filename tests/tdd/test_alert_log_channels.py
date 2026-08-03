"""TDD RED — Issue #1459: Welche Kanaele bekamen die Meldung, welche nicht?

SPEC: docs/specs/modules/feat_1459_alert_protokoll.md (AC-8..AC-11, AC-15)

Kernaussage der Kriterien: Ein Eintrag haelt getrennt fest, welche Kanaele
zugestellt bekamen (``channels_sent``) und welche nicht — jeder
nicht-zugestellte Kanal MIT Begruendung (``channel_disabled`` = vom Nutzer
abgeschaltet, ``delivery_failed`` = wollte, kam aber nicht an).

Ueber die ZIEL-LISTE entscheidet dabei das heutige Kriterium (Spec v1.4,
D4): ein Eintrag entsteht in ``entries``, sobald mindestens ein Kanal eine
FUNKTIONIERENDE KONFIGURATION hat — ein technischer Zustellfehler auf einem
konfigurierten Kanal unterdrueckt ihn ausdruecklich NICHT (Best-Effort,
Anti-Pattern #656). Nur wenn gar kein Kanal konfigurierbar ist — heute
verschwindet die Meldung dann SPURLOS — landet der Eintrag im zweiten
Top-Level-Schluessel ``not_delivered``. So aendern sich Cockpit-Kachel und
Archiv-Statistik fuer Bestandstouren um keine Zahl (AC-11).

RED-Grund heute: ``_append_alert_log()`` kennt weder Kanal-Listen noch
``not_delivered``; ``services.alert_log.append_entry()`` existiert nicht.

Mock-frei: echte ``TripAlertService``-Laeufe. Der scheiternde Telegram-Versand
entsteht aus dem ECHTEN Transport — der Test-Modus-Token-Waechter (#1363)
wirft ``OutputConfigError`` vor jedem HTTP-Aufruf, es geht also kein Byte
ins Netz. Der scheiternde E-Mail-Versand entsteht aus einer ``mail_sink``,
die wirft (dieselbe DI-Naht wie im Erfolgsfall).
"""
from __future__ import annotations

import json

from app.loader import get_data_dir

from tests.helpers.alert_log_fixtures import (
    fresh_user, gust_alert_trip, read_log, reason_for_channel,
    settings_email_and_failing_telegram, settings_email_only, weather,
)

_EMAIL_ONLY = {"email": True, "telegram": False, "sms": False}
_EMAIL_AND_TELEGRAM = {"email": True, "telegram": True, "sms": False}


def _run(uid: str, trip_id: str, *, settings, channels: dict, mail_sink) -> None:
    """Ein Boeen-Alarm (20 -> 60 km/h) durch den echten Alarm-Lauf."""
    from services.trip_alert import TripAlertService

    trip = gust_alert_trip(trip_id, alert_channels=channels)
    TripAlertService(
        settings=settings, user_id=uid, throttle_hours=0, mail_sink=mail_sink,
    ).check_and_send_alerts(
        trip, [weather(1, gust_max_kmh=20.0)],
        fresh_weather=[weather(1, gust_max_kmh=60.0)],
    )


def _boom(subject, body):  # noqa: ANN001 - DI-Naht mit der Signatur des Erfolgsfalls
    raise RuntimeError("E-Mail-Transport nicht erreichbar (TDD #1459)")


def _settings_email_unconfigured_telegram_available():
    """E-Mail NICHT konfigurierbar, Telegram global vorhanden.

    Fuer AC-10: der Nutzer hat E-Mail fuer Alarme eingeschaltet, es gibt
    dafuer aber keine funktionierende Konfiguration -> ``can_send_email()``
    ist False, der Kanal wird gar nicht erst betreten. Telegram bleibt global
    konfiguriert, damit der Eingangs-Waechter von ``check_and_send_alerts()``
    ("kein einziger Kanal konfiguriert") nicht schon vorher abbricht — auf
    Trip-Ebene ist Telegram fuer Alarme abgeschaltet, es geht also kein Byte
    ins Netz.
    """
    from app.config import Settings

    return Settings(
        smtp_host="", smtp_user="", smtp_pass="", mail_to="",
        telegram_bot_token="tdd-1459-nur-fuer-den-eingangs-waechter",
        telegram_chat_id="4711",
    )


# ───────────────────────────────── AC-8 ────────────────────────────────────

def test_ac8_abgeschaltete_kanaele_stehen_mit_begruendung_im_eintrag():
    """AC-8 GIVEN eine Tour hat nur E-Mail fuer Alarme aktiv (Telegram/SMS aus)
    und der Versand gelingt
    WHEN protokolliert wird
    THEN steht ``email`` in ``channels_sent``; ``telegram`` und ``sms`` stehen
    je mit dem Grund ``channel_disabled`` in ``channels_not_sent``; der
    Eintrag liegt in ``entries``."""
    uid = fresh_user("ac8")
    mails: list = []
    _run(uid, "trip-ac8", settings=settings_email_only(), channels=_EMAIL_ONLY,
         mail_sink=lambda subject, body: mails.append((subject, body)))

    assert mails, "Voraussetzung: die Meldung muss per E-Mail rausgehen."
    log = read_log(uid)
    assert len(log["entries"]) == 1 and not log["not_delivered"], (
        f"Ein Teil-Erfolg gehoert nach 'entries': {log!r}"
    )
    entry = log["entries"][0]
    assert entry.get("channels_sent") == ["email"], (
        f"Erwartet ['email'] als zugestellte Kanaele, erhalten: "
        f"{entry.get('channels_sent')!r}"
    )
    for kanal in ("telegram", "sms"):
        assert reason_for_channel(entry, kanal) == "channel_disabled", (
            f"Kanal {kanal!r} ist abgeschaltet und muss mit dem Grund "
            f"'channel_disabled' festgehalten werden, erhalten: "
            f"{reason_for_channel(entry, kanal)!r}"
        )


# ───────────────────────────────── AC-9 ────────────────────────────────────

def test_ac9_teil_erfolg_haelt_gescheiterten_kanal_getrennt_fest():
    """AC-9 GIVEN E-Mail UND Telegram sind aktiv, die E-Mail kommt an, der
    Telegram-Versand scheitert
    WHEN protokolliert wird
    THEN steht ``email`` in ``channels_sent``, ``telegram`` mit dem Grund
    ``delivery_failed`` in ``channels_not_sent`` — und der Eintrag liegt
    (weil mindestens ein Kanal ankam) in ``entries``: die Eintragszahl
    verhaelt sich wie heute, nur die Detailtiefe waechst."""
    uid = fresh_user("ac9")
    mails: list = []
    _run(uid, "trip-ac9", settings=settings_email_and_failing_telegram(),
         channels=_EMAIL_AND_TELEGRAM,
         mail_sink=lambda subject, body: mails.append((subject, body)))

    assert mails, "Voraussetzung: die E-Mail muss ankommen."
    log = read_log(uid)
    assert len(log["entries"]) == 1 and not log["not_delivered"], (
        f"Bei Teil-Erfolg gehoert der Eintrag nach 'entries': {log!r}"
    )
    entry = log["entries"][0]
    assert entry.get("channels_sent") == ["email"], (
        "Nur die E-Mail kam an — Telegram darf NICHT als zugestellt gelten: "
        f"{entry.get('channels_sent')!r}"
    )
    assert reason_for_channel(entry, "telegram") == "delivery_failed", (
        "Der gescheiterte Telegram-Versand muss als 'delivery_failed' "
        f"erkennbar sein, erhalten: {reason_for_channel(entry, 'telegram')!r}"
    )
    assert reason_for_channel(entry, "sms") == "channel_disabled", (
        "SMS ist abgeschaltet, nicht gescheitert: "
        f"{reason_for_channel(entry, 'sms')!r}"
    )


# ───────────────────────────────── AC-10 ───────────────────────────────────

def test_ac10_kein_konfigurierbarer_kanal_landet_in_not_delivered():
    """AC-10 (Spec v1.4) GIVEN eine Tour hat E-Mail fuer Alarme eingeschaltet,
    fuer E-Mail gibt es aber KEINE funktionierende Konfiguration — kein
    einziger Kanal ist also konfigurierbar, obwohl der Nutzer einen wollte
    WHEN protokolliert wird
    THEN landet GENAU EIN Eintrag in ``not_delivered`` (NICHT in ``entries``)
    mit leerem ``channels_sent``.

    Das ist der Fall, in dem die Meldung heute SPURLOS verschwindet: der
    Bestand schreibt hier gar keinen Eintrag. ``entries`` waechst dadurch
    nicht — die Zahl in Cockpit-Kachel und Archiv-Statistik bleibt fuer
    Bestandstouren unveraendert (AC-11)."""
    uid = fresh_user("ac10")
    settings = _settings_email_unconfigured_telegram_available()
    assert settings.can_send_email() is False, (
        "Voraussetzung: E-Mail darf NICHT konfigurierbar sein."
    )
    _run(uid, "trip-ac10", settings=settings, channels=_EMAIL_ONLY,
         mail_sink=None)

    log = read_log(uid)
    assert log["entries"] == [], (
        "Heute entstuende hier GAR KEIN Eintrag — `entries` darf also nicht "
        f"wachsen: {log['entries']!r}"
    )
    assert len(log["not_delivered"]) == 1, (
        "Die spurlos verschwundene Meldung muss festgehalten werden "
        f"(Sicherheitsleine, #638): {log['not_delivered']!r}"
    )
    entry = log["not_delivered"][0]
    assert entry.get("channels_sent") == [], (
        f"Kein Kanal kam an: {entry.get('channels_sent')!r}"
    )
    assert entry.get("entity_id") == "trip-ac10", (
        "Die Nicht-Zustellung muss der Tour zuordenbar bleiben: "
        f"{entry.get('entity_id')!r}"
    )


# ───────────────────────────────── AC-15 ───────────────────────────────────

def test_ac15_konfiguriert_aber_nichts_zugestellt_bleibt_in_entries():
    """AC-15 (Spec v1.4) GIVEN E-Mail UND Telegram sind konfiguriert und
    aktiv, aber KEIN EINZIGER Versandweg stellt tatsaechlich zu
    WHEN protokolliert wird
    THEN liegt der Eintrag in ``entries`` — die Zahl verhaelt sich exakt wie
    heute (Best-Effort, Anti-Pattern #656) — und traegt leeres
    ``channels_sent`` sowie beide Kanaele mit ``delivery_failed``.

    Damit ist "ausgeloest, aber niemand hat es bekommen" im Protokoll
    erkennbar, ohne die im Cockpit gezeigte Zahl anzufassen."""
    uid = fresh_user("ac15")
    _run(uid, "trip-ac15", settings=settings_email_and_failing_telegram(),
         channels=_EMAIL_AND_TELEGRAM, mail_sink=_boom)

    log = read_log(uid)
    assert len(log["entries"]) == 1 and not log["not_delivered"], (
        "Beide Kanaele WAREN konfiguriert — heute entstuende hier ein "
        f"`entries`-Eintrag, das muss so bleiben: {log!r}"
    )
    entry = log["entries"][0]
    assert entry.get("channels_sent") == [], (
        "Kein Kanal hat tatsaechlich zugestellt — das muss an der leeren "
        f"Liste erkennbar sein: {entry.get('channels_sent')!r}"
    )
    for kanal in ("email", "telegram"):
        assert reason_for_channel(entry, kanal) == "delivery_failed", (
            f"Kanal {kanal!r} war aktiv und ist gescheitert — erwartet "
            f"'delivery_failed', erhalten: {reason_for_channel(entry, kanal)!r}"
        )
    assert entry.get("entity_id") == "trip-ac15", (
        f"Der Eintrag muss der Tour zuordenbar bleiben: {entry.get('entity_id')!r}"
    )


# ───────────────────────────────── AC-11 ───────────────────────────────────

def test_ac11_fehlgeschlagener_versand_veraendert_die_angezeigte_zahl_nicht():
    """AC-11 GIVEN eine Tour hat bereits zwei erfolgreiche Eintraege in
    ``entries``
    WHEN zusaetzlich ein komplett fehlgeschlagener Versand derselben Tour
    protokolliert wird
    THEN bleibt die Zahl der ``entries``-Eintraege dieser Tour bei zwei — das
    ist bit-genau das, was die Archiv-Statistik (``AlertCountByEntity``) und die
    Cockpit-Kachel lesen."""
    from services import alert_log

    uid = fresh_user("ac11")
    user_dir = get_data_dir(uid)
    user_dir.mkdir(parents=True, exist_ok=True)
    bestand = {"entries": [
        {"trip_id": "X", "sent_at": "2026-08-01T10:00:00+00:00",
         "changes_count": 1, "severity": "MODERATE"},
        {"trip_id": "X", "sent_at": "2026-08-01T12:00:00+00:00",
         "changes_count": 2, "severity": "HIGH"},
    ]}
    (user_dir / "alert_log.json").write_text(json.dumps(bestand))

    def _zaehle_x() -> int:
        # Bestand traegt die Kennung noch als `trip_id` (#1467 S1: keine
        # Datei-Migration), neue Eintraege als `entity_id` — beide zaehlen.
        return sum(
            1 for e in read_log(uid)["entries"]
            if (e.get("entity_id") or e.get("trip_id")) == "X"
        )

    vorher = _zaehle_x()
    alert_log.append_entry(
        uid, entity_id="X", entity_type="trip", changes_count=1, severity="MODERATE",
        metrics=[("gust", "max")], reason="forecast_change",
        effective_channels={"email"}, sent_channels=[],
    )
    nachher = _zaehle_x()

    assert vorher == 2, f"Voraussetzung: zwei Bestands-Eintraege, erhalten {vorher}."
    assert nachher == 2, (
        f"Die fuer die Tour 'X' gezaehlten Eintraege sind von {vorher} auf "
        f"{nachher} gestiegen — Cockpit-Kachel und Archiv-Statistik wuerden "
        "sich fuer eine Bestandstour aendern (D4-Kernforderung)."
    )
    assert len(read_log(uid)["not_delivered"]) == 1, (
        "Der fehlgeschlagene Versand muss stattdessen in 'not_delivered' stehen."
    )


# ───────────────────────────────── AC-16 ───────────────────────────────────

_ALLE_KANAELE_AUS = {"email": False, "telegram": False, "sms": False}


def test_ac16_abgeschaltete_alarme_erzeugen_gar_keinen_eintrag():
    """AC-16 (Spec v1.5, aus Adversary-Finding F001) GIVEN eine Tour hat
    KEINEN Kanal fuer Alarme eingeschaltet, es liegt aber ein ausloesender
    Befund vor
    WHEN der Protokoll-Aufruf erfolgt
    THEN entsteht WEDER in ``entries`` NOCH in ``not_delivered`` ein Eintrag —
    die Protokoll-Datei wird gar nicht erst angelegt.

    Das ist keine Nicht-Zustellungs-Luecke, sondern die ausdrueckliche
    Einstellung des Nutzers; ein Eintrag dafuer waere Log-Rauschen ohne
    Erkenntniswert (Spec, Known Limitations).

    Damit dieser Waechter nicht die Falle aus #1435 E3a wiederholt — ein Test,
    der auch dann gruen bliebe, wenn er gar nichts prueft — laeuft ZUERST
    dieselbe Ausloese-Lage mit eingeschaltetem Kanal: sie MUSS einen Eintrag
    erzeugen. Erst dadurch ist belegt, dass die Lage die Schreibfunktion
    ueberhaupt erreicht und der zweite Teil eine echte Aussage trifft.
    """
    # Kontrolle: dieselbe Ausloese-Lage MIT Kanal schreibt nachweislich.
    uid_kontrolle = fresh_user("ac16-kontrolle")
    mails: list = []
    _run(uid_kontrolle, "trip-ac16-kontrolle", settings=settings_email_only(),
         channels=_EMAIL_ONLY,
         mail_sink=lambda subject, body: mails.append((subject, body)))
    kontrolle = read_log(uid_kontrolle)
    assert len(kontrolle["entries"]) == 1, (
        "Kontrolle fehlgeschlagen: die Ausloese-Lage erreicht die "
        "Schreibfunktion gar nicht — der eigentliche Nachweis unten waere "
        f"dann wertlos. {kontrolle!r}"
    )

    # Der eigentliche Nachweis: derselbe Lauf, alle Alarm-Kanaele aus.
    uid = fresh_user("ac16")
    _run(uid, "trip-ac16", settings=settings_email_only(),
         channels=_ALLE_KANAELE_AUS, mail_sink=_boom)

    log = read_log(uid)
    assert log["entries"] == [] and log["not_delivered"] == [], (
        "Der Nutzer hat Alarme fuer diese Tour komplett abgeschaltet — dafuer "
        f"darf KEIN Protokoll-Eintrag entstehen: {log!r}"
    )
    assert not (get_data_dir(uid) / "alert_log.json").exists(), (
        "Ohne eingeschalteten Kanal darf die Protokoll-Datei nicht einmal "
        "angelegt werden."
    )
