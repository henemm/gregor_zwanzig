"""Gemeinsamer Berichtsaufbau des Ortsvergleichs (Issue #2983).

SPEC: docs/specs/modules/compare_briefing_aufbau.md

EINZIGE Stelle, die Profil, Wetterlauf, Render-Optionen, Betreff und die
Kanaltexte (E-Mail, SMS, Telegram) eines Ortsvergleichs zusammensetzt.
Versand (``scheduler_dispatch_service.send_one_compare_preset``) = Baustein +
Nebenwirkungen + Senden; Vorschau (``ComparePreviewService``) = Baustein.

Vier kleine Funktionen statt eines Rundum-Aufrufs, weil der Versand zwischen
Wetterlauf und Rendern Kontingent und ``no_weather`` prueft und SMS/Telegram im
try-Block des Anker-Pfads (#1629) rendert. Ohne Nebenwirkungen: kein Versand,
kein Kontingent, kein Anker, keine Vorfaelle, keine Schreibzugriffe.

Importiert weder ``scheduler_dispatch_service`` noch ``compare_preview_service``
(kein Zirkelimport). Aufrufer loesen die Funktionen zur Laufzeit ueber das Modul
auf, damit eine Aenderung hier in Vorschau UND Versand wirkt.

Multi-User (ADR-0003): ``user_id`` kommt immer vom Aufrufer, nie ``"default"``.
"""
from __future__ import annotations

from datetime import date, datetime

from i18n import Lang, t
from i18n.format import fmt_date_numeric


def order_locations_by_ids(locations: list, location_ids: list[str]) -> list:
    """Filtert ``locations`` reihenfolge-erhaltend nach ``location_ids``.

    Die Listenposition in ``location_ids`` IST die vom Nutzer konfigurierte
    Reihenfolge (Issue #1359 Scheibe 2). Geteilt zwischen Vorschau und Versand.
    """
    by_id = {loc.id: loc for loc in locations}
    return [by_id[loc_id] for loc_id in location_ids if loc_id in by_id]


def build_compare_preset_subject(name: str, target_date: date, *, lang: Lang = "de") -> str:
    """Mail-Betreff eines Ortsvergleichs (pure Funktion).

    Adversary-Fund F001 (#1232 Scheibe 2a): das Datum ist ``target_date``,
    nicht der Sende-Zeitpunkt.
    """
    return t("versand.scheduler.vergleich_betreff", lang, name=name,
             datum=fmt_date_numeric(target_date, lang))


def compare_zieltag_bestimmen(locations: list, jetzt_utc: datetime, *, context_label: str) -> date:
    """Zieltag ohne Vorgabe = Ortstag des ersten aufloesbaren Orts
    (#1727 S5b/S5c, ADR-0044) -- gemeinsam fuer Vorschau und Versand."""
    from utils.timezone import first_resolvable_tz, local_dt

    zone = first_resolvable_tz(locations, context_label=context_label)
    return local_dt(jetzt_utc, zone).date()


def compare_wetter_laden(preset: dict, locations: list, zieltag: date, user_id: str) -> dict:
    """Profil aus der Vorlage, Tagesfenster und Wetterlauf je Ort (gleichzeitig,
    #1765 B1). Ausnahmen des Wetterlaufs fliegen unveraendert weiter."""
    from app.ampel import profile_for_template, template_id_for
    from services.amtliche_warnungen_schalter import amtliche_warnungen_an_preset
    from services.comparison_engine import COMPARE_FORECAST_HOURS
    from services.comparison_parallel import run_comparison_parallel
    from services.report_config_resolver import (
        resolve_compare_render_options, resolve_compare_time_window,
    )

    # Issue #2796 S4a (ADR-0108 P3): Bewertungsprofil aus der aufgeloesten Vorlage.
    profile = profile_for_template(template_id_for(preset))
    # ``call_source`` ausdruecklich: der ThreadPoolExecutor reicht den
    # ContextVar-Kontext nicht an seine Arbeiter weiter.
    result = run_comparison_parallel(
        locations=locations,
        time_window=resolve_compare_time_window(preset),  # #1361/#1372 S1b
        target_date=zieltag,
        forecast_hours=COMPARE_FORECAST_HOURS,  # Issue #1305
        profile=profile,
        official_alerts_enabled=amtliche_warnungen_an_preset(preset),  # #1040, #3047 E4
        call_source="vergleich",
        user_id=user_id,  # Issue #2234: Budget beim ausloesenden Nutzer
    )
    return {
        "preset": preset,
        "result": result,
        "profile": profile,
        "opts": resolve_compare_render_options(preset),  # Issue #1209 (Scheibe B)
        "name": preset.get("name", preset.get("id", "")),
        "target_date": zieltag,
    }


def compare_email_rendern(kontext: dict, *, lang: Lang = "de", undelivered=None) -> tuple[str, str]:
    """E-Mail (HTML, Text). ``undelivered`` liest nur der Versand (Vorschau: None)."""
    from output.renderers.comparison import render_compare_email

    opts = kontext["opts"]
    return render_compare_email(
        kontext["result"],
        undelivered=undelivered,
        profile=kontext["profile"],
        # Issue #1703 S8: kanal-eigene Uebersichts-Auswahl.
        enabled_metrics=opts.enabled_metrics_by_channel["email"],
        hourly_metrics=opts.hourly_metrics,
        hourly_metric_formats=opts.hourly_metric_formats,  # Issue #3097
        hourly_enabled=opts.hourly_enabled,
        preset_name=kontext["name"],
        preset=kontext["preset"],  # Issue #1969 (AC-26): Fuss "Naechster Versand"
        corridors=opts.corridors,
        outlook_enabled=opts.outlook_enabled,
        outlook_metrics=opts.outlook_metrics,
        outlook_metric_formats=opts.outlook_metric_formats,  # Issue #2049
        unresolved_count=opts.unresolved_by_channel.get("email", 0),  # Issue #1405 S3
        metric_formats=opts.metric_formats("email"),  # Issue #3039
        lang=lang,
        show_fallback_notice=True,  # Issue #1563
    )


def compare_kanaltexte_rendern(kontext: dict, *, lang: Lang = "de") -> tuple[str, str]:
    """(SMS-Text, Telegram-Text). Telegram-Stil "kurzform" = derselbe Text wie
    die SMS (Issue #2422 S5, AC-28), sonst der Telegram-Renderer."""
    from output.renderers.comparison import render_compare_sms, render_compare_telegram
    from services.compare_alert_channels import effective_compare_telegram_style

    opts, result, preset = kontext["opts"], kontext["result"], kontext["preset"]
    sms = render_compare_sms(
        result, enabled_metrics=opts.enabled_metrics_by_channel["sms"],
        unresolved_count=opts.unresolved_by_channel.get("sms", 0),
        metric_formats=opts.metric_formats("sms"),
    )
    if effective_compare_telegram_style(preset) == "kurzform":
        return sms, sms
    telegram = render_compare_telegram(
        result,
        enabled_metrics=opts.enabled_metrics_by_channel["telegram"],
        preset_name=kontext["name"],
        unresolved_count=opts.unresolved_by_channel.get("telegram", 0),
        metric_formats=opts.metric_formats("telegram"),
        lang=lang,
        show_fallback_notice=True,
        # Issue #3047 B-K7 (AC-24): 3-Tages-Ausblick je Ort wie in der Mail.
        outlook_enabled=opts.outlook_enabled,
        outlook_metrics=opts.outlook_metrics,
        outlook_metric_formats=opts.outlook_metric_formats,
        preset=preset,
    )
    return sms, telegram


def compare_briefing_bauen(preset: dict, locations: list, zieltag: date, user_id: str, *,
                           lang: Lang = "de", undelivered=None) -> dict:
    """Gesamtaufruf (Vorschau): Wetterlauf, E-Mail, SMS/Telegram, Betreff."""
    kontext = compare_wetter_laden(preset, locations, zieltag, user_id)
    email_html, email_text = compare_email_rendern(kontext, lang=lang, undelivered=undelivered)
    sms, telegram = compare_kanaltexte_rendern(kontext, lang=lang)
    return {
        "subject": build_compare_preset_subject(kontext["name"], zieltag, lang=lang),
        "email_html": email_html,
        "email_text": email_text,
        "telegram": telegram,
        "sms": sms,
    }
