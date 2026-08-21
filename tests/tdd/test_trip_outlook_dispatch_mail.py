"""TDD RED — #1720 S1: die Auswahl wirkt bis in die zugestellte Mail.

SPEC: docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md
(AC-2, AC-3, AC-4/AC-16 ganze Kette, AC-14, AC-15)

🔴 Warum zusaetzlich zu ``test_trip_outlook_metric_selection.py``: dort baut
der TEST die Ausblick-Zeilen. Ein Auseinanderlaufen von Zeilenbau
(``build_outlook_row``, trip_report_scheduler.py:2161) und Spaltenbau
(``render_outlook_table``, html.py:1357) kann jene Datei nicht sehen. Hier
speist EINE Implementierung beide Stellen: getrieben wird
``_send_trip_report_outcome()``, abgefangen der reale
``EmailOutput(settings).send(...)``-Aufruf des ``NotificationService``,
geprueft der von ``build_mime_message()`` gebaute Nachrichtenkoerper.

Kein Mock-Framework: echte Unterklassen + Attribut-Rebind, in ``finally``
restauriert (Muster ``test_compare_dispatch_mail_marker.py`` und
``test_briefing_anchor_survives_dispatch_failure.py``). Ersetzt werden nur
teure Upstream-Abhaengigkeiten, nie der Pruefgegenstand: ``_fetch_weather``
(feste Auswertungen), ``_enrich_ensemble_for_trip``/``_fetch_night_weather``
(echte Provider-Calls), ``EmailOutput.send`` (SMTP).

Versand-Sicherheit (#1477): ``Settings(...)`` faellt bei fehlenden Feldern
still auf die Prod-``.env`` zurueck -- alle Transport-Felder werden hier
ausdruecklich gesetzt, Telegram/SMS sind leer und werden gegengeprueft.

RED-Erwartung: ``UnifiedWeatherDisplayConfig`` kennt ``outlook_metrics``
nicht -- die Auswahl erreicht den Renderpfad gar nicht.
"""
from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Pfadregel #1409: Pruefling relativ zur eigenen Testdatei aufloesen.
REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

from tests.helpers.trip_outlook_selection import (  # noqa: E402
    OUTLOOK_EYEBROW, html_outlook_body_rows, html_outlook_headers,
    mit_outlook_metrics, plain_outlook_block, tages_summary,
)

LAT, LON = 46.65, 12.85
# #1848 A2: Auswahl-Bausteine sind reine Kennungen (vorher Paare, #1373).
NIEDERSCHLAG = "precipitation"
BOEEN = "gust"
SCHNEEHOEHE = "snow_depth"

_MAIL_FIELDS: dict = {
    "smtp_host": "dummy.invalid", "smtp_port": 587,
    "smtp_user": "dummy-1720", "smtp_pass": "dummy-1720",
    "mail_to": "gregor-test@henemm.com",
    "telegram_bot_token": "", "telegram_chat_id": "",
    "telegram_test_bot_token": "", "telegram_test_chat_id": "",
    "sms_gateway_url": "", "seven_api_key": "", "sms_to": "",
    "_env_file": None,
}


def _settings(user_id: str):
    from app.config import Settings

    settings = Settings(**_MAIL_FIELDS).with_user_profile(user_id)
    assert settings.can_send_email() is True, (
        "Vorbedingung: der E-Mail-Kanal muss sendefaehig konfiguriert sein."
    )
    assert settings.can_send_telegram() is False, (
        "Sicherung (#1477): Telegram darf nicht sendefaehig sein -- sonst "
        "ginge eine echte Nachricht an den Prod-Chat."
    )
    assert settings.can_send_sms() is False, "Sicherung (#1477): kein SMS."
    return settings


def _trip(*, outlook_metrics, enabled_ids=None, leere_grundauswahl=False,
          email_layout_ids=None, report_overrides=None,
          trend_reports=("evening",), ohne_nachtblock=False):
    """Tour mit fuenf Etappen ab heute: der Abendbericht zielt auf MORGEN
    (``_get_target_date``), der Ausblick zeigt die drei Etappen danach.

    ``email_layout_ids``: setzt ein E-Mail-eigenes Kanal-Layout
    (``per_channel_layouts["email"]``, Bestandsfeature seit #429) auf genau
    diese Groessen -- die Konfigurationsflaeche, an der AC-17 haengt.
    ``report_overrides``: z.B. ``{"gust": {"evening_enabled": False}}``.
    ``ohne_nachtblock``: haelt den Vorschau-Pfad von einem echten
    Nacht-Wetter-Abruf fern (``night_weather_needed``).
    """
    from app.metric_catalog import build_default_display_config
    from app.models import TripReportConfig
    from app.trip import Stage, Trip, Waypoint

    trip_id = f"trip-1720-{uuid.uuid4().hex[:8]}"
    heute = date.today()
    # #1709: feste Ankunftszeiten statt Naismith-Self-Heal
    # (trip_segments.py:125-127) — die Zeiten selbst tragen keine
    # Pruefaussage dieser Datei, sie muessen nur ueberhaupt gesetzt sein.
    stages = [
        Stage(id=f"S{i}", name=f"Tag {i}", date=heute + timedelta(days=i),
              waypoints=[
                  Waypoint(id=f"W{i}a", name="Start", lat=LAT, lon=LON,
                           elevation_m=1400.0, arrival_calculated="08:00"),
                  Waypoint(id=f"W{i}b", name="Ziel", lat=LAT + 0.05,
                           lon=LON + 0.1, elevation_m=2100.0,
                           arrival_calculated="12:00"),
              ])
        for i in range(5)
    ]
    dc = build_default_display_config()
    dc.trip_id = trip_id
    if enabled_ids is not None:
        for mc in dc.metrics:
            mc.enabled = mc.metric_id in enabled_ids
    for metric_id, felder in (report_overrides or {}).items():
        for mc in dc.metrics:
            if mc.metric_id == metric_id:
                for name, wert in felder.items():
                    setattr(mc, name, wert)
    if ohne_nachtblock:
        dc.show_night_block = False
    if leere_grundauswahl:
        dc.metrics = []
    if email_layout_ids is not None:
        dc.per_channel_layouts = {
            "email": [mc for mc in dc.metrics if mc.metric_id in email_layout_ids],
        }
    if outlook_metrics is not None:
        dc = mit_outlook_metrics(dc, outlook_metrics)

    trip = Trip(id=trip_id, name="Karnischer Höhenweg", stages=stages,
                display_config=dc, official_warnings=None)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=False, send_sms=False,
        show_outlook=True, multi_day_trend_reports=list(trend_reports),
    )
    trip.official_alerts_enabled = False       # kein Netz fuer amtliche Warnungen
    trip.official_alert_triggers_enabled = False
    trip.alert_cooldown_minutes = 0
    return trip


def _fixture_scheduler_klasse():
    from app.models import (
        ForecastMeta, NormalizedTimeseries, Provider, SegmentWeatherData,
    )
    from services.trip_report_scheduler import TripReportSchedulerService

    heute = date.today()
    # RED-Korrektur (#1720 S1, GREEN-Phase): der Abendbericht zielt auf MORGEN
    # (heute+1), der Ausblick zeigt die drei Etappen DANACH -- also heute+2,
    # +3, +4. Der Index wurde gegen ``heute`` gerechnet und rotierte die drei
    # Tage dadurch um zwei Positionen gegen die erwarteten Werte
    # (_TAGE[2],[0],[1] statt [0],[1],[2]). Gemessen am Etappenkalender, nicht
    # geraten. Ankerpunkt ist jetzt der ERSTE Ausblickstag.
    erster_ausblickstag = heute + timedelta(days=2)

    class _FixtureScheduler(TripReportSchedulerService):
        """Echte Unterklasse: Wetter aus der Fixture statt vom Provider. Der
        Tages-Index folgt dem Etappendatum, damit die drei Ausblick-Tage
        unterscheidbare Werte tragen."""

        def _fetch_weather(self, segments, provider=None):
            return [
                SegmentWeatherData(
                    segment=seg,
                    timeseries=NormalizedTimeseries(
                        meta=ForecastMeta(provider=Provider.OPENMETEO,
                                          model="fixture", grid_res_km=1.0),
                        data=[]),
                    aggregated=tages_summary(
                        max((seg.start_time.date() - erster_ausblickstag).days, 0),
                        anteile=len(segments)),
                    fetched_at=seg.start_time, provider="openmeteo",
                )
                for seg in segments
            ]

        def _enrich_ensemble_for_trip(self, trip, weather_data):
            return None  # Bug #288: echter Ensemble-API-Call

        def _fetch_night_weather(self, segment_weather):
            return None  # echter Provider-Call

    return _FixtureScheduler


def _zugestellte_teile(trip, *, report_type: str = "evening") -> tuple[str, str]:
    """Treibt den echten Versandpfad, faengt die realen ``send()``-Argumente
    ab und baut daraus mit dem ECHTEN ``build_mime_message()`` die Nachricht.
    Liefert (HTML-Teil, Klartext-Teil) -- das, was beim Empfaenger ankommt."""
    import services.notification_service as ns_mod
    from output.channels.email import build_mime_message

    user_id = f"tdd-1720-{uuid.uuid4().hex[:8]}"
    aufzeichnung: list[dict] = []
    original = ns_mod.EmailOutput

    class _RecordingEmailOutput(original):  # echte Subklasse, kein Mock
        def send(self, subject, body, **kwargs):
            aufzeichnung.append({"subject": subject, "body": body, **kwargs})
            return None

    ns_mod.EmailOutput = _RecordingEmailOutput
    try:
        scheduler = _fixture_scheduler_klasse()(settings=_settings(user_id),
                                                user_id=user_id)
        ergebnis = scheduler._send_trip_report_outcome(trip, report_type,
                                                       on_demand=True)
    finally:
        ns_mod.EmailOutput = original

    assert ergebnis == "sent", (
        f"Der Versandlauf endete mit {ergebnis!r} statt 'sent' -- ohne "
        "erfolgten Versand prueft dieser Test nichts."
    )
    assert aufzeichnung, "Es wurde keine E-Mail versendet."
    kwargs = aufzeichnung[0]
    msg = build_mime_message(
        subject=kwargs["subject"], body=kwargs["body"],
        from_addr="gregor_zwanzig@henemm.com",
        to_header="gregor-test@henemm.com", reply_to=None,
        html=kwargs.get("html", True),
        plain_text_body=kwargs.get("plain_text_body"),
        mail_type=kwargs.get("mail_type"), mail_format=kwargs.get("mail_format"),
    )
    assert msg["X-GZ-Mail-Type"] == "trip-briefing", (
        f"Unerwarteter Mail-Typ: {msg['X-GZ-Mail-Type']!r}"
    )
    teile = {t.get_content_type(): t.get_payload(decode=True).decode("utf-8")
             for t in msg.walk() if not t.is_multipart()}
    assert "text/html" in teile and "text/plain" in teile, (
        f"Die Nachricht traegt nicht beide Teile: {sorted(teile)!r}"
    )
    return teile["text/html"], teile["text/plain"]


# ═══════════════════ AC-2 / AC-3 — die zugestellte Mail ══════════════════════

def test_ac2_zugestellte_html_mail_zeigt_genau_die_gewaehlten_spalten():
    """AC-2: Given der Nutzer hat nur "Niederschlag" und "Böen" gewaehlt /
    When die naechste Trip-Mail ueber den echten Versandpfad verschickt wird /
    Then zeigt der HTML-Ausblick ausschliesslich diese Spalten in
    Auswahlreihenfolge mit deutschen Katalog-Bezeichnungen.
    """
    html, _ = _zugestellte_teile(_trip(outlook_metrics=[NIEDERSCHLAG, BOEEN]))

    assert OUTLOOK_EYEBROW in html, (
        "Die zugestellte Mail enthaelt gar keinen Ausblick-Block (AC-2)."
    )
    assert html_outlook_headers(html) == ["Tag", "Niederschlag", "Böen"], (
        f"Kopfzeile {html_outlook_headers(html)!r} -- die sieben festen "
        "Spalten (N/D/R/PR/Wind/Böen/Gew) waeren der unveraenderte Zustand."
    )


def test_ac3_zugestellter_klartext_zeigt_dieselben_spalten_wie_das_html():
    """AC-3: Given dieselbe zugestellte Nachricht / When der Klartext-Teil
    betrachtet wird / Then zeigt er dieselben Groessen in derselben
    Reihenfolge wie der HTML-Teil.

    Mutation 2 am Wirkort: ``metrics=`` nur an ``render_outlook_table``
    (html.py:1357) und nicht an ``render_outlook_plain`` (plain.py:338) faellt
    NUR hier auf -- beide Aufrufstellen sind unabhaengig.
    """
    html, plain = _zugestellte_teile(_trip(outlook_metrics=[NIEDERSCHLAG, BOEEN]))

    block = plain_outlook_block(plain)
    assert block is not None, (
        "Der Klartext-Teil der zugestellten Mail hat keinen Ausblick (AC-3)."
    )
    kopf = html_outlook_headers(html)[1:]
    assert kopf == ["Niederschlag", "Böen"], f"Vorbedingung (AC-2): {kopf!r}"
    zeile = block.splitlines()[1]
    positionen = [zeile.find(label) for label in kopf]
    assert all(p >= 0 for p in positionen), (
        f"Der Klartext nennt die gewaehlten Groessen nicht -- er steht "
        f"vermutlich noch auf den festen Tokens. Zeile: {zeile!r} (AC-3)"
    )
    assert positionen == sorted(positionen), (
        f"Klartext-Reihenfolge weicht vom HTML ab: {zeile!r} (AC-3)"
    )


def test_ac2_zellwerte_der_zugestellten_mail_gehoeren_zu_ihren_spalten():
    """AC-2 (Zuordnung ueber die ganze Kette): jede Zelle traegt den Wert
    IHRER Spalte.

    Der eigentliche Grund fuer den Ketten-Test: arbeiteten Zeilenbau
    (Scheduler) und Spaltenbau (Renderer) mit verschiedenen Listen, stuenden
    die richtigen Ueberschriften ueber den falschen Zahlen.
    """
    html, _ = _zugestellte_teile(_trip(outlook_metrics=[NIEDERSCHLAG, BOEEN]))
    zeilen = html_outlook_body_rows(html)

    assert len(zeilen) == 3, f"Erwartet drei Ausblick-Zeilen: {zeilen!r}"
    assert [z[1] for z in zeilen] == ["2.5 mm", "0.0 mm", "7.1 mm"], (
        f"Niederschlag-Spalte: {[z[1] for z in zeilen]!r} (AC-2)"
    )
    assert [z[2] for z in zeilen] == ["44 km/h", "52 km/h", "33 km/h"], (
        f"Böen-Spalte: {[z[2] for z in zeilen]!r} -- Abweichung deutet auf "
        "einen Spaltenversatz zwischen Zeilenbau und Spaltenbau hin (AC-2)."
    )


# ═══════ AC-14 / AC-15 / AC-16 — Schnitt gegen die Grundauswahl, Kette ═══════

def test_ac14_manipulierte_auswahl_erreicht_die_zugestellte_mail_nicht():
    """AC-14 (ganze Kette): Given "Schneehoehe" ist in der Grundauswahl nicht
    aktiv, landet aber ueber einen manipulierten Speicher-Aufruf in der
    Vorschau-Auswahl / When die Mail zugestellt wird / Then erscheint sie
    weder im HTML- noch im Klartext-Teil.

    Mutation 8: ein Schnitt, der nur im Frontend sitzt, zeigt dem Nutzer das
    richtige Verhalten -- die zugestellte Mail haelt es nicht ein. Eine
    Pruefung, die nur den Editor betrachtet, waere eine Attrappe, die ein
    direkter PUT umgeht (ADR-0053, "die ganze Kette").
    """
    trip = _trip(outlook_metrics=[NIEDERSCHLAG, SCHNEEHOEHE],
                 enabled_ids={"precipitation"})
    html, plain = _zugestellte_teile(trip)

    assert html_outlook_headers(html) == ["Tag", "Niederschlag"], (
        f"Kopfzeile {html_outlook_headers(html)!r}: die zugestellte Mail zeigt "
        "eine Groesse ausserhalb der Grundauswahl (AC-14)."
    )
    block = plain_outlook_block(plain)
    assert block is not None and "Schneehöhe" not in block, (
        f"Der Klartext-Teil zeigt die verbotene Groesse:\n{block}\n(AC-14)"
    )
    assert [z[1] for z in html_outlook_body_rows(html)] == [
        "2.5 mm", "0.0 mm", "7.1 mm",
    ], (
        "Nach dem Schnitt stehen falsche Werte unter 'Niederschlag' -- "
        "Zeilenbau und Spaltenbau sind auseinandergelaufen (AC-14)."
    )


def test_ac15_globale_abwahl_entfernt_die_spalte_im_naechsten_lauf():
    """AC-15: Given eine Groesse erscheint heute in der Vorschau / When der
    Nutzer sie in der Grundauswahl abwaehlt / Then verschwindet sie ohne
    weiteres Zutun auch aus der Vorschau der naechsten Mail, waehrend die
    uebrigen Spalten bleiben (ADR-0050 Regel 3).

    Zwei Laeufe DESSELBEN Trips; dazwischen wird ausschliesslich die
    Grundauswahl geaendert, ``outlook_metrics`` bleibt unangetastet.
    """
    trip = _trip(outlook_metrics=[NIEDERSCHLAG, BOEEN],
                 enabled_ids={"precipitation", "gust"})
    html_vorher, _ = _zugestellte_teile(trip)
    assert html_outlook_headers(html_vorher) == ["Tag", "Niederschlag", "Böen"], (
        f"Vorbedingung von AC-15: {html_outlook_headers(html_vorher)!r}"
    )

    for mc in trip.display_config.metrics:
        if mc.metric_id == "gust":
            mc.enabled = False

    html_nachher, plain_nachher = _zugestellte_teile(trip)
    assert html_outlook_headers(html_nachher) == ["Tag", "Niederschlag"], (
        "Nach der globalen Abwahl von 'Böen' zeigt die Vorschau die Spalte "
        f"weiterhin: {html_outlook_headers(html_nachher)!r} (AC-15)."
    )
    block = plain_outlook_block(plain_nachher)
    assert block is not None and "Böen" not in block, (
        f"Der Klartext zeigt die abgewaehlte Groesse weiter:\n{block}\n(AC-15)"
    )


def test_ac16_leere_grundauswahl_schneidet_auch_die_zugestellte_mail_nicht():
    """AC-16 (ganze Kette): ohne jede Grundauswahl (``metrics == []``)
    erscheinen alle gewaehlten Spalten -- "kein Maximum definiert", nicht
    "nichts erlaubt" (Regel D4, models.py:913-914).
    """
    trip = _trip(outlook_metrics=[NIEDERSCHLAG, BOEEN, SCHNEEHOEHE],
                 leere_grundauswahl=True)
    html, _ = _zugestellte_teile(trip)

    assert html_outlook_headers(html) == [
        "Tag", "Niederschlag", "Böen", "Schneehöhe",
    ], (
        f"Kopfzeile {html_outlook_headers(html)!r}: bei leerer Grundauswahl "
        "wurde geschnitten -- Totalausfall fuer jeden Altbestand (AC-16)."
    )


def test_ac4_leere_auswahl_laesst_den_block_auch_in_der_zugestellten_mail_entfallen():
    """AC-4 (ganze Kette): bei bewusst geleerter Auswahl enthaelt weder der
    HTML- noch der Klartext-Teil einen Ausblick-Block."""
    html, plain = _zugestellte_teile(_trip(outlook_metrics=[]))

    assert OUTLOOK_EYEBROW not in html, (
        "Die zugestellte Mail zeigt weiterhin die Ausblick-Ueberschrift (AC-4)."
    )
    assert plain_outlook_block(plain) is None, (
        "Der Klartext-Teil zeigt weiterhin einen Ausblick-Block (AC-4)."
    )


# ═════ AC-17 — der Ausblick kennt keine Kanal-Ebene (Adversary F001) ════════

def test_ac17_eigenes_email_kanal_layout_schneidet_die_vorschau_nicht():
    """AC-17: Given ein Trip mit einem E-Mail-eigenen Kanal-Layout
    (``per_channel_layouts["email"]``), das "Böen" NICHT enthaelt, waehrend
    "Böen" in der Grundauswahl aktiv UND in der Vorschau gewaehlt ist / When
    die Mail ueber den echten Versandpfad zugestellt wird / Then erscheint
    "Böen" als Spalte im Ausblick.

    Adversary-Finding F001 (HIGH): der Ausblick hat bewusst KEINE Kanal-Ebene
    (Spec "Out of Scope"). Wird der Schnitt gegen
    ``get_metrics_for_channel("email", ...)`` statt gegen die kanal-neutrale
    Grundauswahl gefahren, faellt eine global aktive, ausdruecklich gewaehlte
    Groesse still aus der Vorschau -- fuer jeden Trip mit eigenem
    E-Mail-Layout (Bestandsfeature seit #429).

    Die Stundentabelle derselben Mail behaelt ihr enges Kanal-Layout: der
    Ausblick folgt der Grundauswahl, die Kanal-Ebene bleibt fuer alles andere
    unangetastet.
    """
    trip = _trip(outlook_metrics=[NIEDERSCHLAG, BOEEN],
                 enabled_ids={"precipitation", "gust"},
                 email_layout_ids={"precipitation"})
    assert {mc.metric_id
            for mc in trip.display_config.get_metrics_for_channel("email", "evening")
            } == {"precipitation"}, (
        "Vorbedingung: das E-Mail-Kanal-Layout muss enger sein als die "
        "Grundauswahl, sonst prueft dieser Test die Kanal-Kopplung gar nicht."
    )

    html, plain = _zugestellte_teile(trip)

    assert html_outlook_headers(html) == ["Tag", "Niederschlag", "Böen"], (
        f"Kopfzeile {html_outlook_headers(html)!r}: 'Böen' ist global aktiv "
        "und ausdruecklich gewaehlt, faellt aber wegen des E-Mail-eigenen "
        "Kanal-Layouts aus der Vorschau -- der Ausblick hat keine "
        "Kanal-Ebene (AC-17)."
    )
    block = plain_outlook_block(plain)
    assert block is not None and "Böen" in block, (
        f"Der Klartext-Teil zeigt die Groesse nicht:\n{block}\n(AC-17)"
    )


def test_ac17_ueberschrift_und_zahl_bleiben_bei_engem_kanal_layout_gepaart():
    """AC-17 (Zuordnung): Given dasselbe Kanal-Layout schliesst diesmal die
    ERSTE gewaehlte Groesse aus / When die Mail zugestellt wird / Then traegt
    jede Spalte den Wert IHRER Groesse -- kein Spaltenversatz.

    Genau die Fehlerklasse, die der urspruengliche Schnitt gegen
    ``get_metrics_for_channel()`` vermeiden wollte: laufen Zeilenbau
    (Scheduler, ungekollabiertes ``display_config``) und Spaltenbau
    (Renderer, kanal-kollabiertes ``dc``) auseinander, stuenden die richtigen
    Ueberschriften ueber den falschen Zahlen. Weil das Layout hier die erste
    Spalte betrifft, verschiebt sich die Zuordnung um eine Position statt nur
    abgeschnitten zu werden -- ein Test, der nur die Kopfzeile prueft, saehe
    das nicht.
    """
    trip = _trip(outlook_metrics=[NIEDERSCHLAG, BOEEN],
                 enabled_ids={"precipitation", "gust"},
                 email_layout_ids={"gust"})
    html, _ = _zugestellte_teile(trip)

    assert html_outlook_headers(html) == ["Tag", "Niederschlag", "Böen"], (
        f"Kopfzeile {html_outlook_headers(html)!r} (AC-17)."
    )
    zeilen = html_outlook_body_rows(html)
    assert len(zeilen) == 3, f"Erwartet drei Ausblick-Zeilen: {zeilen!r}"
    assert [z[1] for z in zeilen] == ["2.5 mm", "0.0 mm", "7.1 mm"], (
        f"Unter 'Niederschlag' stehen {[z[1] for z in zeilen]!r} -- Zeilenbau "
        "und Spaltenbau haben verschiedene Auswahl-Listen benutzt (AC-17)."
    )
    assert [z[2] for z in zeilen] == ["44 km/h", "52 km/h", "33 km/h"], (
        f"Unter 'Böen' stehen {[z[2] for z in zeilen]!r} -- die Zellen sind "
        "um eine Position gegen die Ueberschriften verschoben (AC-17)."
    )


def test_ac17_vorschau_zeigt_denselben_ausblick_wie_die_zugestellte_mail():
    """AC-17 (Vorschau-Paritaet): Given ein Trip mit engem E-Mail-Kanal-Layout
    UND einem Abend-Override, das "Böen" nur im Morgenbericht zeigt / When
    die Morgen-Vorschau ueber ``PreviewService._build_report()`` erzeugt wird
    / Then zeigt sie Kopfzeile UND Zellen des Ausblicks genau wie die
    zugestellte Morgen-Mail.

    Der Vorschau-Pfad baut seine Ausblick-ZEILEN mit einem EIGENEN
    ``_build_stage_trend()``-Aufruf (preview_service.py), die SPALTEN dagegen
    ueber dieselbe eine Aufloesung in ``format_email()``. Fehlt dort der
    ``report_type``, baut die Vorschau die Zellen nach dem Abend-Default und
    die Ueberschriften nach dem echten Typ -- der Abend-Override laesst die
    Böen-Zelle dann auf "–" laufen, waehrend die Ueberschrift steht.

    Getrieben wird die echte Vorschau-Pipeline; ersetzt ist nur die
    Scheduler-KLASSE durch die Fixture-Unterklasse dieses Moduls (echte
    Unterklasse, Attribut-Rebind, in ``finally`` restauriert) -- sonst holte
    die Vorschau Wetter vom echten Provider.
    """
    import services.trip_report_scheduler as sched_mod
    from services.preview_service import PreviewService

    trip = _trip(outlook_metrics=[NIEDERSCHLAG, BOEEN],
                 enabled_ids={"precipitation", "gust"},
                 email_layout_ids={"gust"},
                 report_overrides={"gust": {"evening_enabled": False}},
                 trend_reports=("morning", "evening"), ohne_nachtblock=True)
    html_versand, _ = _zugestellte_teile(trip, report_type="morning")
    assert html_outlook_headers(html_versand) == ["Tag", "Niederschlag", "Böen"], (
        f"Vorbedingung: {html_outlook_headers(html_versand)!r} (AC-17)."
    )

    settings = _settings(f"tdd-1720-{uuid.uuid4().hex[:8]}")
    original = sched_mod.TripReportSchedulerService
    sched_mod.TripReportSchedulerService = _fixture_scheduler_klasse()
    try:
        report, *_ = PreviewService(settings=settings)._build_report(
            trip, date.today(), "morning", now_utc=datetime.now(timezone.utc),
        )
    finally:
        sched_mod.TripReportSchedulerService = original

    assert html_outlook_headers(report.email_html) == html_outlook_headers(html_versand), (
        f"Vorschau {html_outlook_headers(report.email_html)!r} vs. Versand "
        f"{html_outlook_headers(html_versand)!r} (AC-17)."
    )
    assert html_outlook_body_rows(report.email_html) == html_outlook_body_rows(html_versand), (
        "Die Vorschau zeigt andere Ausblick-Zellen als die zugestellte Mail "
        f"-- Vorschau: {html_outlook_body_rows(report.email_html)!r}, "
        f"Versand: {html_outlook_body_rows(html_versand)!r} (AC-17)."
    )


def test_bestandstrip_behaelt_die_sieben_festen_spalten_in_der_zugestellten_mail():
    """AC-1 (ganze Kette, Bestandsschutz): ohne gesetzte Vorschau-Auswahl
    stehen weiterhin die sieben festen Spalten samt ACC in der Tabelle.

    Mutation 1 am Wirkort (``resolve_outlook_metrics(...) or []``): der
    Ausblick verschwaende fuer 100 % der heutigen Trips. Dieser Test ist der
    einzige hier, der schon vor der Lieferung gruen ist -- und muss es
    BLEIBEN.
    """
    html, plain = _zugestellte_teile(_trip(outlook_metrics=None))

    assert html_outlook_headers(html) == [
        "Tag", "N", "D", "R", "PR", "Wind", "Böen", "Gew", "ACC",
    ], (
        f"Kopfzeile {html_outlook_headers(html)!r}: ein Trip ohne Auswahl "
        "zeigt nicht mehr die sieben festen Spalten (AC-1)."
    )
    assert plain_outlook_block(plain) is not None, (
        "Der Klartext-Ausblick eines Bestandstrips fehlt vollstaendig (AC-1)."
    )
