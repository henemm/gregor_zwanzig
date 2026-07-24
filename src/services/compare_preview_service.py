"""Compare-Preview-Service — echte Vorschau fuer den Orts-Vergleich (Issue #1270).

SPEC: docs/specs/modules/compare_channel_preview_dispatch.md (Scheiben S2/S4)

Loest das Preset + die ECHTEN Orte des Nutzers auf, laesst die
``ComparisonEngine`` genau EINMAL je Aufruf laufen und rendert daraus die
fertigen Kanal-Payloads (E-Mail/Telegram/SMS) — kein Versand, keine
Persistenz. Ersetzt fachlich den Validator-Stub
(`validator_render_service.render_compare_email_preview`, hartcodierter Ort
"Vorschau-Ort"), der unveraendert dem externen Validator gehoert (#464).

Konventions-Paritaet statt Klassen-Paritaet zu `PreviewService` (Trip): gleiche
Methodennamen, eigene Klasse (dokumentierte Ausnahme von der
Trip/Compare-Teilungs-Invariante, s. Spec "Architektur-Entscheidung"). Geteilt
wird die Infrastruktur: `resolve_compare_render_options` (#1209, Metrik-Filter),
`CHANNEL_LIMITS` (#360, Kanal-Budget), Neutralitaets-Vertrag der Renderer (#1110).

Bewusst OHNE `settings`-Konstruktor-Argument (anders als `PreviewService`): die
Render-Pfade des Vergleichs sind rein — kein Transport, kein nutzerspezifisches
Mail-Layout. Ein nur der Paritaet zuliebe mitgefuehrtes, nirgends gelesenes Feld
waere toter Code und taeuschte eine Abhaengigkeit vor, die es nicht gibt. Wird
hier je eine Einstellung gebraucht, kommt das Argument mit seinem ersten echten
Lesezugriff zurueck.

Multi-User (ADR-0003): `user_id` ist Pflicht-Keyword ohne Default — ein
Preset eines fremden Nutzers ist strukturell nicht aufloesbar (LookupError),
weil ausschliesslich im Nutzer-Verzeichnis gesucht wird. NIE `"default"` als
Fallback.
"""
from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)


class ComparePreviewService:
    """Rendert Vorschau-Payloads eines Compare-Presets ohne Versand."""

    # ------------------------------------------------------------------
    # Oeffentliche API (Methodennamen-Paritaet zu PreviewService)
    # ------------------------------------------------------------------

    def render_all_channels(
        self,
        preset_id: str,
        *,
        user_id: str,
        target_date: str | date | None = None,
    ) -> dict:
        """Sammel-Einstieg (ADR-0011): EIN Engine-Lauf, ALLE Kanaele fertig
        gerendert in EINER Antwort — der Kanalwechsel im Vorschau-Tab braucht
        damit keinen weiteren Request (AC-7).
        """
        from output.renderers.comparison import render_compare_sms, render_compare_telegram
        from services.scheduler_dispatch_service import build_compare_preset_subject

        ctx = self._prepare(preset_id, user_id=user_id, target_date=target_date)
        html_body, _text_body = self._render_email(ctx)
        telegram = render_compare_telegram(
            ctx["result"],
            enabled_metrics=ctx["opts"].enabled_metrics,
            preset_name=ctx["name"],
        )
        sms = render_compare_sms(ctx["result"], enabled_metrics=ctx["opts"].enabled_metrics)
        return {
            "subject": build_compare_preset_subject(ctx["name"], ctx["target_date"]),
            "email_html": html_body,
            "telegram": telegram,
            "sms": sms,
            "sms_char_count": len(sms),
        }

    def render_email_preview(
        self,
        preset_id: str,
        *,
        user_id: str,
        target_date: str | date | None = None,
    ) -> str:
        """E-Mail-Vorschau (HTML) aus den echten Preset-Orten (AC-1)."""
        ctx = self._prepare(preset_id, user_id=user_id, target_date=target_date)
        html_body, _text_body = self._render_email(ctx)
        return html_body

    def render_telegram_preview(
        self,
        preset_id: str,
        *,
        user_id: str,
        target_date: str | date | None = None,
    ) -> str:
        """Telegram-Vorschau (fertiger Nachrichtentext, AC-2)."""
        from output.renderers.comparison import render_compare_telegram

        ctx = self._prepare(preset_id, user_id=user_id, target_date=target_date)
        return render_compare_telegram(
            ctx["result"],
            enabled_metrics=ctx["opts"].enabled_metrics,
            preset_name=ctx["name"],
        )

    def render_sms_preview(
        self,
        preset_id: str,
        *,
        user_id: str,
        target_date: str | date | None = None,
    ) -> str:
        """SMS-Vorschau (fertige, budgetierte Zeile, AC-2)."""
        from output.renderers.comparison import render_compare_sms

        ctx = self._prepare(preset_id, user_id=user_id, target_date=target_date)
        return render_compare_sms(ctx["result"], enabled_metrics=ctx["opts"].enabled_metrics)

    # ------------------------------------------------------------------
    # Interna
    # ------------------------------------------------------------------

    def _prepare(
        self,
        preset_id: str,
        *,
        user_id: str,
        target_date: str | date | None,
    ) -> dict:
        """Preset + echte Orte laden und die ComparisonEngine EINMAL laufen
        lassen. Alle Kanal-Renderer eines Aufrufs sitzen auf demselben
        ``ComparisonResult`` (AC-7).
        """
        from app.loader import _parse_activity_profile
        from services.comparison_engine import COMPARE_FORECAST_HOURS, ComparisonEngine
        from services.report_config_resolver import resolve_compare_render_options

        preset = self._load_preset(preset_id, user_id=user_id)
        locations = self._resolve_locations(preset, user_id=user_id)
        resolved_date = _resolve_target_date(target_date)
        profile = _parse_activity_profile(str(preset.get("profil", "")).lower())

        # Issue #1268 (AC-11): Zeitfenster und Horizont sind keine Editor-Felder
        # mehr. Die Vorschau MUSS mit denselben festen Werten rechnen wie der
        # echte Versand (scheduler_dispatch_service.py:319-326) — sonst zeigt sie
        # etwas anderes, als der Nutzer bekommt. Die deprecateten Preset-Felder
        # hour_from/hour_to/forecast_hours werden bewusst NICHT gelesen: bei neu
        # angelegten Presets stehen dort die Go-Zero-Values (0), das ergaebe das
        # leere Fenster (0, 0) und eine leer laufende Vorschau.
        # Issue #1305 (ex #1268 AC-11): Vorschau MUSS denselben Horizont anfordern
        # wie der echte Versand (scheduler_dispatch_service.py). Der geteilte Bezug
        # auf COMPARE_FORECAST_HOURS ersetzt den bisherigen Kommentar-Appell durch
        # Struktur — Divergenz ist strukturell ausgeschlossen (#1297).
        result = ComparisonEngine.run(
            locations=locations,
            time_window=(0, 23),  # Issue #1268: ganzer Tag, kein Editor-Feld mehr
            target_date=resolved_date,
            forecast_hours=COMPARE_FORECAST_HOURS,
            profile=profile,
            official_alerts_enabled=preset.get("official_alerts_enabled", True),
        )
        return {
            "preset": preset,
            "result": result,
            "profile": profile,
            "opts": resolve_compare_render_options(preset),
            "name": preset.get("name", preset_id),
            "target_date": resolved_date,
        }

    def _render_email(self, ctx: dict) -> tuple[str, str]:
        from output.renderers.comparison import render_compare_email

        opts = ctx["opts"]
        preset = ctx["preset"]
        return render_compare_email(
            ctx["result"],
            profile=ctx["profile"],
            top_n_details=opts.top_n_details,
            enabled_metrics=opts.enabled_metrics,
            hourly_metrics=opts.hourly_metrics,
            hourly_enabled=opts.hourly_enabled,
            preset_name=ctx["name"],
            preset_schedule=preset.get("schedule"),
            preset_weekday=preset.get("weekday"),
            corridors=opts.corridors,
            outlook_enabled=opts.outlook_enabled,
        )

    def _load_preset(self, preset_id: str, *, user_id: str) -> dict:
        """Laedt das Preset AUSSCHLIESSLICH aus dem Verzeichnis dieses Nutzers.

        Raises:
            ValueError: wenn keine `user_id` uebergeben wurde (kein
                `"default"`-Fallback, ADR-0003).
            LookupError: wenn der Nutzer kein Preset mit dieser ID hat — auch
                dann, wenn es einem anderen Nutzer gehoert (AC-6). Die
                Fehlermeldung traegt keinerlei fremde Inhalte.
        """
        from app.loader import compare_preset_to_dict, get_data_root, load_compare_presets

        if not user_id:
            raise ValueError("user_id ist Pflicht — kein 'default'-Fallback (ADR-0003)")
        presets = load_compare_presets(user_id=user_id, data_root=get_data_root())
        for preset in presets:
            if preset.id == preset_id:
                return compare_preset_to_dict(preset)
        raise LookupError(
            f"Orts-Vergleich '{preset_id}' nicht gefunden für Nutzer '{user_id}'"
        )

    def _resolve_locations(self, preset: dict, *, user_id: str) -> list:
        """Echte Orte des Nutzers in Preset-Reihenfolge (kein Stub-Ort)."""
        from app.loader import load_all_locations

        location_ids = preset.get("location_ids") or []
        if not location_ids:
            raise ValueError(
                f"Orts-Vergleich '{preset.get('id', '')}' hat keine Orte konfiguriert — "
                "es gibt nichts zu vergleichen."
            )
        locations = order_locations_by_ids(
            load_all_locations(user_id=user_id), location_ids
        )
        if not locations:
            raise ValueError(
                f"Orts-Vergleich '{preset.get('id', '')}': Orte {location_ids} "
                "nicht aufloesbar"
            )
        return locations


def order_locations_by_ids(locations: list, location_ids: list[str]) -> list:
    """Filtert ``locations`` reihenfolge-erhaltend nach ``location_ids``.

    Ordnungs-Kern (dict-by-id aufbauen, dann über ``location_ids`` iterieren) —
    die Listenposition in ``location_ids`` IST die vom Nutzer konfigurierte
    Reihenfolge (Issue #1359 Scheibe 2). Geteilt zwischen
    ``ComparePreviewService._resolve_locations()`` und dem Versandpfad
    (``scheduler_dispatch_service.send_one_compare_preset``), damit beide Wege
    die gespeicherte Orts-Reihenfolge bewahren statt über eine andere Sammlung
    (z. B. den Orte-Cache) zu iterieren.
    """
    by_id = {loc.id: loc for loc in locations}
    return [by_id[loc_id] for loc_id in location_ids if loc_id in by_id]


def _resolve_target_date(given: str | date | None) -> date:
    """ISO-String/`date`/None → `date`. None = heute (analog Einzelversand)."""
    if given is None or given == "":
        return date.today()
    if isinstance(given, date):
        return given
    try:
        return date.fromisoformat(str(given))
    except ValueError as e:
        raise ValueError(f"Ungültiges Datum '{given}' (erwartet ISO JJJJ-MM-TT)") from e
