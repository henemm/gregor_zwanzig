"""Compare-Preview-Service — echte Vorschau fuer den Orts-Vergleich (Issue #1270).

SPEC: docs/specs/modules/compare_channel_preview_dispatch.md (Scheiben S2/S4)

Loest das Preset + die ECHTEN Orte des Nutzers auf, laesst die
``ComparisonEngine`` genau EINMAL JE ORT laufen (seit #1765 B1 gleichzeitig,
ueber ``comparison_parallel.run_comparison_parallel``) und rendert daraus die
fertigen Kanal-Payloads (E-Mail/Telegram/SMS) — kein Versand, keine
Persistenz. Ersetzt fachlich den Validator-Stub
(`validator_render_service.render_compare_email_preview`, hartcodierter Ort
"Vorschau-Ort"), der unveraendert dem externen Validator gehoert (#464).

Eigene Klasse statt Klassen-Paritaet zu `PreviewService` (Trip); die
Einzel-Kanal-Huellen sind mit #1743 (AC-31) entfallen, einziger oeffentlicher
Einstieg ist `render_all_channels` (dokumentierte Ausnahme von der
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
from datetime import date, datetime, timezone

import services.compare_briefing_aufbau as aufbau
# Issue #2983: Re-Export unter dem alten Namen; der Ordnungs-Kern liegt im Baustein.
from services.compare_briefing_aufbau import order_locations_by_ids
from services.fehler_code import fehler_mit_code

logger = logging.getLogger(__name__)


class ComparePreviewService:
    """Rendert Vorschau-Payloads eines Compare-Presets ohne Versand."""

    # ------------------------------------------------------------------
    # Oeffentliche API
    # ------------------------------------------------------------------

    def render_all_channels(
        self,
        preset_id: str,
        *,
        user_id: str,
        target_date: str | date | None = None,
    ) -> dict:
        """Sammel-Einstieg (ADR-0011): duenne Huelle um den gemeinsamen
        Berichtsaufbau des Versands (Issue #2983) -- EIN Wetterlauf je Ort,
        ALLE Kanaele fertig gerendert in EINER Antwort (AC-7). Seit #1743
        Render-Pfad der Paritaetstests; die HTTP-Route ist entfallen.
        """
        from i18n import resolve_user_lang

        preset = self._load_preset(preset_id, user_id=user_id)
        locations = self._resolve_locations(preset, user_id=user_id)
        zieltag = _resolve_target_date(target_date, locations, datetime.now(timezone.utc))
        # Issue #2672: die Vorschau spricht die Sprache des Nutzers wie der Versand.
        bericht = aufbau.compare_briefing_bauen(
            preset, locations, zieltag, user_id, lang=resolve_user_lang(user_id),
        )
        return {
            "subject": bericht["subject"],
            "email_html": bericht["email_html"],
            # Issue #3059: bei Kompakt ist das HTML leer, der Text IST die Mail.
            "email_text": bericht["email_text"],
            "telegram": bericht["telegram"],
            "sms": bericht["sms"],
            "sms_char_count": len(bericht["sms"]),
        }

    # ------------------------------------------------------------------
    # Interna
    # ------------------------------------------------------------------

    def _prepare(self, preset_id: str, *, user_id: str, target_date: str | date | None) -> dict:
        """Preset + Orte laden und den Wetterlauf des Bausteins ausfuehren
        (Test-Einstieg, Issue #2983)."""
        preset = self._load_preset(preset_id, user_id=user_id)
        locations = self._resolve_locations(preset, user_id=user_id)
        zieltag = _resolve_target_date(target_date, locations, datetime.now(timezone.utc))
        return aufbau.compare_wetter_laden(preset, locations, zieltag, user_id)

    def _render_email(self, ctx: dict, *, lang: str = "de") -> tuple[str, str]:
        return aufbau.compare_email_rendern(ctx, lang=lang)

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
        raise fehler_mit_code(LookupError, "vergleich_nicht_gefunden",
                              preset_id=preset_id, user_id=user_id)

    def _resolve_locations(self, preset: dict, *, user_id: str) -> list:
        """Echte Orte des Nutzers in Preset-Reihenfolge (kein Stub-Ort)."""
        from app.loader import load_all_locations

        location_ids = preset.get("location_ids") or []
        if not location_ids:
            raise fehler_mit_code(ValueError, "vergleich_ohne_orte",
                                  preset_id=preset.get("id", ""))
        locations = order_locations_by_ids(
            load_all_locations(user_id=user_id), location_ids
        )
        if not locations:
            raise fehler_mit_code(ValueError, "vergleich_orte_geloescht",
                                  preset_id=preset.get("id", ""), location_ids=location_ids)
        return locations


def _resolve_target_date(
    given: str | date | None, locations: list, now_utc: datetime,
) -> date:
    """ISO-String/`date`/None → `date`. None = Ortstag des ersten aufloesbaren
    Orts (Issue #1727 S5c, ADR-0044/-0051) — analog zum Compare-Versandpfad
    seit S5b (``scheduler_dispatch_service.py``), nicht mehr die zonenlose
    Serveruhr. Der ``given``-Zweig bleibt unveraendert."""
    if given is None or given == "":
        # Issue #2983 (AC-9): dieselbe Ermittlung wie der Versand.
        return aufbau.compare_zieltag_bestimmen(locations, now_utc, context_label="Compare-Vorschau")
    if isinstance(given, date):
        return given
    try:
        return date.fromisoformat(str(given))
    except ValueError as e:
        raise fehler_mit_code(ValueError, "vergleich_datum_ungueltig", datum=given) from e
