# Context: Issue #722 — E-Mail-Format Kompakt/Nur-Text

## Request Summary
Format-Schalter `email_format: full | compact` für die E-Mail. **full** = heutige HTML-Mail
mit stündlicher Werte-Tabelle pro Etappe. **compact** = Nur-Text, zeigt **immer fix**
Metriken-Überblick + Ausblick als ausformulierten Text, **nie** Stundentabellen. Im
Kompakt-Modus greift die Baustein-Auswahl NICHT (PO-Entscheidung). Slice 2 von #709, baut
auf #721 (Ausblick) auf.

## Related Files
| File | Relevance |
|------|-----------|
| `src/app/models.py` (`TripReportConfig`, ab Z.680) | Neues Feld `email_format` neben `show_outlook` (#721, Z.733) |
| `src/app/loader.py` (Z.351 deser / Z.1065 ser) | `email_format` lesen/schreiben (Default "full") |
| `src/formatters/trip_report.py` (Z.120–159) | Adapter: leitet Toggles aus `report_config` ab, ruft `render_email()` |
| `src/output/renderers/email/__init__.py` (`render_email`) | Pure Orchestrator → ruft `render_html` + `render_plain` |
| `src/output/renderers/email/plain.py` (`render_plain`) | Basis für Nur-Text-Renderer; Metriken-Überblick (Z.266) + Ausblick (Z.164/237) existieren bereits |
| `src/output/renderers/email/html.py` (`render_html`) | full-Pfad; compact braucht minimale `<pre>`-HTML-Hülle |
| `src/output/renderers/email/helpers.py` | `build_metrics_summary_pills`, `build_confidence_hint` etc. |
| `src/outputs/email.py` (Z.112–141) | Multipart-Versand (HTML-Part + Plain-Part) — beide Parts müssen compact sein |
| `src/services/trip_report_scheduler.py` (Z.499) | Sende-Pfad: `body=email_html`, `plain_text_body=email_plain` |
| `src/services/preview_service.py` (Z.146 `render_email_preview`) | Vorschau gibt `email_html` zurück → muss compact-HTML liefern |
| `frontend/src/lib/types.ts` (`ReportConfig`, Z.174) | Neues optionales Feld `email_format` |
| `frontend/src/lib/components/edit/reportConfigWrite.ts` | UI↔Payload-Mapping |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` (586 Z.) | Format-Schalter UI; Baustein-Gruppe bei compact deaktivieren |
| `internal/model/trip.go` (Z.96) | `ReportConfig map[string]interface{}` — Passthrough, **keine** typisierte Änderung nötig |

## Existing Patterns
- **show_*-Toggle-Pattern (#621/#664/#721):** Feld in `TripReportConfig` → loader deser/ser
  mit Default → `trip_report.py` `_show_x = report_config.x if report_config else <default>`
  → als kwarg an `render_email` → in `render_plain`/`render_html` Block gaten. `email_format`
  ist analog, aber ein **enum-String** (`"full"`/`"compact"`) statt bool.
- **Multipart-Mail (KERNLEHRE #721):** Mail ist multipart/alternative — HTML-Part UND Plain-Part
  müssen beide den compact-Inhalt tragen. NICHT nur HTML anfassen.
- **Metriken-Überblick + Ausblick existieren schon** in `render_plain`: `show_metrics_summary`
  (Z.266 pills via `build_metrics_summary_pills`) + Ausblick-Block (`show_outlook`: Stabilität
  Z.164, Confidence-Hint Z.185, „Nächste Etappen" Trend Z.237). Compact = nur diese Blöcke +
  Header + Footer, alles andere weg.

## Dependencies
- **Upstream:** `report_config` (TripReportConfig) liefert die Konfiguration; `render_email`
  konsumiert die Toggles.
- **Downstream:** Scheduler-Versand, Preview-Service, E-Mail-Spec-Validator.

## Existing Specs
- `docs/specs/modules/output_channel_renderers.md` — render_email/render_plain Vertrag (§A1/A5/A6)
- #721 (E-Mail-Ausblick verschmolzen) — direkter Vorläufer, Ausblick-Block

## Byte-Größen-Recherche (PO-Fokus: minimale KB)
Empirisch gemessen an echten Projekt-Daten:

| Variante | Größe (was der Wanderer lädt) |
|---|---|
| Heutige Mail (multipart HTML+Plain, real `mail_712.eml`) | ~16.600 B |
| Kompakt single `text/plain`, base64 (Python-Default) | 895 B |
| Kompakt single `text/plain`, quoted-printable | 831 B |
| Kompakt **ASCII-schlank, 7bit** (gewählt) | **691 B** |

**Hebel nach Wirkung:**
1. **~95 %: single `text/plain`, kein HTML, kein multipart.** Der HTML-Teil (Stundentabellen)
   macht ~95 % der heutigen 16 KB aus. `email.py` kann text-only via `html=False`, aber der
   Scheduler ruft heute immer `html=True`. **compact muss text-only senden.**
2. **~15–20 %: wenig Nicht-ASCII.** Resend liefert immer als `quoted-printable` aus (in allen
   echten `.eml` bestätigt) → Emoji = 12 B, Box-Zeichen ━ = 9 B. ASCII drückt das weg.
3. **CTE-Wahl (base64/QP/8bit) bewusst NICHT optimieren** — Resend normalisiert ohnehin auf QP;
   8bit erzwingen wäre fragil ohne Gewinn. Python-base64-Falle hier irrelevant.

**PO-Entscheidungen:**
- **Umfang:** strikt nur Kopf + Metriken-Überblick + Ausblick + Footer. Keine Tabellen,
  kein Tageslicht, keine Änderungen, keine Highlights/Tages-Summe. Baustein-Auswahl ignoriert.
- **Optik:** **ASCII-schlank** — reines us-ascii, Umlaute transliteriert (ue/ae/oe), keine
  Emojis, keine Box-Zeichen → echtes **7bit** (kein QP), kleinste & robusteste Mail.

## Design-Konsequenzen
- `TripReportConfig.email_format: str = "full"` (Werte "full"/"compact"); loader deser/ser Default "full".
- Neuer **ASCII-Compact-Renderer** (auf plain.py-Bausteinen): Header + Metriken-Überblick +
  Ausblick + Footer, alles transliteriert/ASCII-only.
- Formatter: bei compact text-only signalisieren (z. B. `email_html=""` / Flag auf `TripReport`).
- Scheduler-Send: compact → `email_output.send(..., html=False)` (single text/plain).
- `email.py` `html=False`-Pfad: bei reinem ASCII `us-ascii`-Charset statt `utf-8` → **7bit**
  statt base64 (sonst base64-Falle auch für ASCII).
- Preview-Service: compact-Vorschau zeigt den Text (für Browser in `<pre>`, nur Preview).
- Frontend: Format-Schalter (Ausführlich/Kompakt) oben in der Report-Config; bei „Kompakt"
  Inhalts-Bausteine-Gruppe ausgrauen.

## Risks & Considerations
- **Multipart-Falle (#721-Lehre):** compact muss in HTML- UND Plain-Part wirken. HTML-Part
  als `<pre>`-umschlossener escapeter compact-Text, sonst kollabieren Zeilenumbrüche.
- **Baustein-Auswahl ignorieren:** Im compact-Modus dürfen `show_highlights`/`daily_summary`/
  `show_stage_stats` etc. NICHT greifen — fix nur Metriken-Überblick + Ausblick.
- **Backward Compatibility:** Alt-Trips ohne `email_format` → Default `"full"` (heutiges
  Verhalten unverändert, byte-identisch).
- **show_outlook (#721) hat noch KEINEN Frontend-Toggle** — der neue Format-Schalter ist die
  erste UI-Berührung dieses Bereichs.
- **Mandantentrennung:** report_config lädt/schreibt schon user-isoliert (loader user_id) —
  keine neue Endpoint-Logik, nur Feld-Durchreichung.
- **E2E:** echter Backend-Mail-E2E gegen Staging (Test-Trip → gregor-test@henemm.com → IMAP)
  + `email_spec_validator.py`. Trip braucht ≥2 Waypoints/Etappe (sonst 422).
