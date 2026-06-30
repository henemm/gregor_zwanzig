# Context: feat-918-alert-preview-4ch

## Request Summary
Issue #918 (Slice 3 von 3 zu #914): Der Alert-Vorschau-Endpunkt soll alle vier
Kanäle liefern (`subject`, `email_html`, `telegram`, `sms`) — gerendert durch die
Slice-2-Renderer (#917). Das Frontend zeigt die fertigen Texte; hartcodierte
TS-Render-Logik (`SMS_TOK`/`smsRender`) entfällt. ADR-0011: Vorschau zieht fertige
Texte vom Backend, KEIN zweiter Renderer in TypeScript.

## Related Files
| File | Relevance |
|------|-----------|
| `api/routers/validator.py:258` | `alert_preview`-Endpunkt; nutzt **heute noch** alten `TripReportFormatter.format_email(report_type="alert")` und gibt `{html, plain}` zurück → Kern-Umstellung |
| `src/output/renderers/alert/render.py` | Slice-2-Renderer: `render_subject`, `render_email`→`(html, plain)`, `render_telegram`, `render_sms(msg, limit=140)` |
| `src/output/renderers/alert/project.py` | `to_alert_message(changes, segments, trip_name, *, tz, stand_at)` → `AlertMessage` |
| `src/output/renderers/alert/model.py` | `AlertMessage`/`AlertEvent`, reine Helfer |
| `api/routers/validator.py:225` | `_stub_segment` baut `SegmentWeatherData` aus `SegmentTimePayload` (GPXPoint ohne `distance_from_start_km` → Projektion `_segment_km` prüfen!) |
| `internal/handler/proxy.go:304` | `AlertPreviewProxyHandler` proxyt POST → Python; injiziert `user_id` (Anti-Spoofing) — vermutlich unverändert |
| `frontend/.../alerts-tab/AlertPreviewCard.svelte` | Konsumiert heute `{html, plain}`, zeigt nur Email-iframe → auf 4 Kanäle erweitern |
| `frontend/.../trip-detail/ChannelFidelitySMS.svelte` | Hartcodiertes `SMS_TOK`/`smsRender` — **ABER: Briefing-SMS-Fidelity** (Prefix `KHW03:`, „gesendet 06:00"), nicht Alert! Siehe Risiko 1 |

## Existing Patterns
- 4 reine Renderer aus #917, generisch über die Metrik-Registry. `render_email`
  liefert `(html, plain)`, die übrigen einen String.
- Projektion `to_alert_message` mappt `WeatherChange` → `AlertMessage` mit
  Disambiguierung über `direction`, kein stiller Fallback.
- Endpunkt ist mandantengetrennt: `user_id: str = Query(...)`, vom Go-Proxy
  injiziert. Kein `"default"`-Fallback.
- Compare-Preview-Endpunkt (`/api/_validator/compare-email-preview`) als Muster
  für Renderer-gespeiste Vorschau.

## Dependencies
- Upstream: `alert/render.py` + `alert/project.py` (Slice 2), Metric-Katalog.
- Downstream: Go-Proxy `AlertPreviewProxyHandler`, Svelte `AlertPreviewCard`,
  `alertPreviewHelpers.buildAlertPreviewPayload`.

## Existing Specs / ADR
- `docs/adr/0011-*` (Vorschau zieht fertige Texte vom Backend) — bindend.
- `docs/specs/modules/alert_render_foundation.md` (#914/#917).

## Risks & Considerations
1. **ChannelFidelitySMS.svelte ist Briefing-, nicht Alert-Fidelity.** Prefix
   `KHW03:`, Semantik „gesendet 06:00", Ziel-Risiko-Tail — das ist die
   tägliche **Briefing**-SMS, nicht der Alert. Das Issue nennt sie aber explizit
   zum Entfernen von `SMS_TOK`. Backend-Feed für Briefing-SMS ist ein **anderer**
   Pfad und nicht Teil des Alert-Renderers. → In Analyse/Spec klären: Scope auf
   Alert-Vorschau (`AlertPreviewCard`) begrenzen, oder Briefing-Fidelity-Umbau
   separat? Empfehlung vorab: sauberer Alert-Scope; Briefing-Fidelity ggf.
   Folge-Issue.
2. **Response-Shape-Bruch:** `{html, plain}` → `{subject, email_html, telegram,
   sms}`. Frontend + ggf. Tests (`test_issue_221_validator_endpoints.py`) müssen
   mitziehen. Rückwärtskompatibilität: `html`/`plain` weiter mitliefern?
3. **`_stub_segment` GPXPoint ohne `distance_from_start_km`:** Projektion
   `_segment_km` liest dieses Feld → Default/0.0 sicherstellen, sonst km-Span 0.
4. **Mail-Validator-Pfad:** Alert ist kein Compare und kein Trip-Briefing — der
   Renderer-Commit-Gate (#811) prüft Briefing-Mail; Alert hat eigene Modus-
   Matrix. Klären welcher Nachweis greift.
5. **stand_at/tz:** Renderer braucht `stand_at` (HH:MM) + tz; Endpunkt muss das
   aus Trip-tz/now ableiten.

## Analysis

### Type
Feature (Slice 3 von 3 zu #914).

### Scope-Entscheidung (PO 2026-06-30)
**Nur Alert-Vorschau.** `ChannelFidelitySMS.svelte` (Briefing-SMS-Fidelity,
trip-detail) bleibt unberührt → Folge-Issue **#923** für deren Backend-Feed.
`AlertPreviewCard.svelte` (alerts-tab) ist der einzige Frontend-Liefergegenstand.

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| `api/routers/validator.py` | MODIFY | `alert_preview`: alten `TripReportFormatter`-Pfad durch Slice-2-Renderer ersetzen; Response `{subject, email_html, email_plain, telegram, sms}` |
| `frontend/.../alerts-tab/AlertPreviewCard.svelte` | MODIFY | 4-Kanal-Anzeige statt nur Email-iframe; Typ `{subject, email_html, telegram, sms}` |
| `tests/integration/test_issue_221_validator_endpoints.py` | MODIFY | AC-4 auf kanonisches Renderer-Format anpassen; AC-5/AC-6 unverändert |
| `internal/handler/proxy.go` | KEEP | Proxy reicht JSON transparent durch — keine Änderung |

### Technical Approach
1. **Endpunkt:** `to_alert_message(changes, segments, trip_name, tz=UTC,
   stand_at=now-HH:MM)` → `AlertMessage`. Dann `render_subject`, `render_email`
   (→ html, plain), `render_telegram`, `render_sms`. Response um die 4 Kanäle +
   `email_plain` erweitern. `user_id`-Mandantentrennung bleibt (kein default).
2. **GPXPoint:** `distance_from_start_km` defaultet 0.0 → km-Span im Stub 0–0.
   Akzeptierte Synthetik-Limitation der Vorschau (Format-Treue, nicht Geografie).
3. **occurred_at:** Body liefert keins → `AlertEvent.occurred_at=None` → SMS-Token
   ohne `@HH`. Korrekt.
4. **Frontend:** `AlertPreviewCard` zeigt: Betreff-Zeile, Email als iframe
   (`email_html`), Telegram als Textblock, SMS als Mono-Block mit Zeichen-Zähler.

### Scope Assessment
- Files: 3 MODIFY (1 Backend, 1 Frontend, 1 Test). LoC: ~+90/-40. Risk: LOW–MEDIUM.
- Blast Radius: Tooling-/Preview-Endpunkt + isolierte Frontend-Karte. Kein Versand,
  kein Scheduler, keine Persistenz, keine Auth.

### Open Questions
- [x] ChannelFidelitySMS-Scope → nur Alert-Vorschau, #923 abgespalten.
- [x] Response-Shape → additiv `{subject, email_html, email_plain, telegram, sms}`.

## Next Step
`/30-write-spec` — Spec mit AC-N.
