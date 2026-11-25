# Context: feat-3059-orte-kompakt-zusatzbloecke

## Request Summary
Issue #3059 (Teil von #3047, Phase 4): E-Mail-Format Ausführlich/Kompakt (W15, `email_format`) und die gemeinsamen Zusatzblöcke auch für Orte. ADR-0124 Nr. 6/7 und Spec `feat_3122_was_steht_wo.md` (:329) verweisen ausdrücklich hierher. Konzept `einstellungen_neu.md` W15: „Gilt künftig auch für Orte, wenn der Renderer es kann.“

## Vorbedingungen und Randentscheidungen
- Phase 3 (#3058): 3a–3f geschlossen, 3g (#3102, Migration/Aufräumen) offen. Die Kanäle lesen aus dem Resolver; 3g ist kein Blocker für einen neuen Ausgabeweg.
- #722 + PO-Entscheidung 2026-11-24 in #3160: Kompakt ist fest. Die Kompakt-Mail ignoriert Block-Schalter (außer dem 3-Tages-Ausblick, feat_3122 Nr. 6); im Editor werden die Schalter bei Kompakt gesperrt. Gilt sinngemäß für Orte.
- Ein angefangener, verworfener #3160-Fix lag auf dem alten Arbeitszweig dieses Worktrees; der Workflow arbeitet auf einem frischen Zweig ab origin/main.

## Related Files
| File | Relevance |
|------|-----------|
| src/app/models.py:1065-1076, :812 | Trip: show_stage_stats, email_format, show_yesterday_comparison, show_night_block |
| src/app/models.py:1202-1287 | ComparePreset (Python) |
| internal/model/compare_preset.go:14-165 | ComparePreset (Go, typisiert; unbekannte Top-Level-Felder fallen weg, display_config ist Map) |
| src/services/compare_alert_channels.py:69-78 | Präzedenz: Orte-`telegram_style` liegt in `display_config` |
| src/services/report_config_resolver.py:110-147, :186-296 | ReportRenderOptions / CompareRenderOptions |
| src/output/renderers/email/__init__.py:117-137 | render_email: compact → render_compact, ("", text) |
| src/output/renderers/email/compact.py:126-338 | render_compact (ASCII, fold_ascii), Trip-segmentförmig |
| src/services/notification_service.py:2485-2505 | Trip-Versand: html=False, mail_format="compact" |
| src/services/notification_service.py:1591-1670 | send_compare_report: immer HTML+Text |
| src/output/channels/email.py:307-390 | build_mime_message, Header X-GZ-Format |
| src/services/scheduler_dispatch_service.py:759, :944, :992 | send_one_compare_preset |
| src/services/compare_briefing_aufbau.py:97-178 | compare_email_rendern, Telegram/SMS, Vorschau |
| src/output/renderers/comparison.py:187, :535-627, :822, :1208 | Orte-Renderer: Text, Mail, Telegram, SMS |
| src/services/placements_view_service.py:421-430, :712-716 | Block-Liste der Karte (Trip vs. Orte) |
| frontend/.../organisms/wetter-tab/WasStehtWoKarte.svelte:48-58, :223, :262-313 | KONTEXT-Gating tripBloecke, E-Mail-Format nur Trip |
| frontend/.../shared/wetter-tab/wasStehtWoSpeicherung.ts:184-243 | felderNutzlast je Kontext |
| frontend/src/lib/i18n/messages/{de,en}/wetter.json:185-212 | Texte (Trip-formuliert) |
| .claude/hooks/email_spec_validator.py:1740-1764 | Orte-Validator: nur HTML, kein Kompakt-Zweig |
| .claude/hooks/briefing_mail_validator.py:624-704, :1297-1375 | Trip-Kompakt-Validierung (Vorlage) |
| .claude/hooks/_soll_aus_konfiguration.py:683-706, :955-1000 | Soll aus Konfiguration: Trip hat email_format, Orte nicht |
| tests/fixtures/einstellung_gleich_mail/fallliste_orte.json | 338 Fälle, nur html/klartext |
| tests/tdd/test_einstellung_gleich_mail_fallliste.py:46, :59-66 | ABDECKUNG_SOLL orte_* nur html/klartext |
| tests/tdd/test_einstellung_gleich_mail_orte*.py | Konsumenten der Orte-Fälle |

## Existing Patterns
- Trip-Kompakt: Renderer liefert leeres HTML → Versand als einzelner text/plain-Teil, us-ascii, Header `X-GZ-Format: compact`; Validator prüft Format gegen `email_format`.
- Orte-Kanaleinstellungen ohne Go-Strukturänderung über `display_config.<feld>` (telegram_style).
- Karte „Was steht wo“: ein geteilter Baustein, Kontext-Map entscheidet, welche Schalter erscheinen (Teilungs-Gate #1170: kein eigener Orte-Baustein).
- Prüfkatalog: Fallliste je Kontext, Format-Dimension `kompakt` existiert schon für Trip.

## Dependencies
- Upstream: Resolver (ADR-0121), Placements (ADR-0124), ComparisonEngine-Daten (`hourly_data`, `outlook_hourly_data`), ascii_fold.
- Downstream: Versand (Scheduler, Vorschau, Testversand), Mail-Validatoren, Prüfkatalog, Editor-Karte, api_contract.md, renderer_email_spec.md.

## Existing Specs
- docs/specs/modules/feat_3122_was_steht_wo.md (Nr. 6, AC-29/30, :329 Verweis)
- docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md
- fix_1703_s4_kompaktform_matrix.md, feat_1720_s2_ausblick_kompakt_telegram.md, fix_1671_kompaktmail_ausblick_tagesfenster.md
- ADR-0121, ADR-0124, ADR-0104 (DE/EN)

## Datenlage der Zusatzblöcke bei Orten
- Etappen-Kennzahlen: Etappen-Begriff, bei Orten sinnlos.
- Vortag-Vergleich: Orte haben nur einen undatierten Δ-Anker je Preset/Ort (`compare_weather_snapshot.py`, Alarmzweck). Bräuchte datierte Snapshots + Adapter von LocationResult-Aggregaten auf DayComparisonService (segment-basiert). Neuer Datenpfad.
- Nacht-Stundentabelle: Trip holt Nachtreihe ab Ankunft bis 06:00. Orte haben keine Ankunft; Engine holt 96 h, verwirft aber Nachtstunden. Machbar, aber fachlich neu (Zeitfenster Tagesende → nächster Morgen).

## Risks & Considerations
- Produktfrage: Welche Zusatzblöcke Orte überhaupt bekommen sollen (fachlich nur Vortag und Nacht denkbar, beide mit neuem Datenpfad) – PO-Entscheidung in der Spec.
- Kompakt-Inhalt für Orte ist neu zu definieren (Übersicht je Ort als Text, Ausblick ja nach feat_3122 Nr. 6, Stundenverlauf? nach #722 ignoriert).
- Validator email_spec_validator.py lehnt heute jede Nicht-HTML-Orte-Mail ab → Kompakt-Zweig nötig, sonst Staging-Gate rot.
- Mehrsprachigkeit DE/EN, ASCII-Faltung, < 2 KB-Regel aus renderer_email_spec.md:279 bei vielen Orten kritisch.
- Zwei-Nutzer-Test, Read-Modify-Write für display_config.
- Paralleler Workflow #3333 (Orte anlegen / Zustellung) in anderer Sitzung – Berührung in Editor-Dateien möglich.

## Analysis

### Type
Feature

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/report_config_resolver.py:172, :258 | MODIFY | `CompareRenderOptions.email_format` ("full" Vorgabe), gelesen aus `display_config.email_format` |
| src/output/renderers/comparison.py (oder email/compact_compare.py) | MODIFY/CREATE | `render_compare_compact`: ASCII-Klartext, je Ort eine Zeile (Name + E-Mail-Metriken, Warnmarker), Ausblick je Ort nur wenn aktiv, kein Stundenverlauf, DE/EN, Kürzung vom Listenende mit „+N Orte" |
| src/services/compare_briefing_aufbau.py:97 | MODIFY | Abzweig VOR dem HTML-Aufbau: compact → ("", text). Einziger gemeinsamer Punkt für Versand + Vorschau |
| src/services/notification_service.py:1591-1670 | MODIFY | `send_compare_report`: leeres HTML → `html=False, mail_format="compact"` (Header X-GZ-Format), mail_sink-Zweig mit abdecken |
| src/services/scheduler_dispatch_service.py:944, :1000 | MODIFY/prüfen | Δ-Anker-Reset (#1629) auch im Kompaktpfad nur nach Erfolg |
| src/services/compare_preview_service.py:85-94, placements_view_service.py:712-716, :742 | MODIFY | Vorschau zeigt Kompakttext; Block-Liste Orte um `email_format` |
| src/output/channels/email.py:307, :669 | prüfen | `mail_format`/`html` existieren bereits |
| internal/model/compare_preset.go, handler/compare_preset.go:318 | prüfen | display_config ist Map, feldweiser Merge → kein Go-Change |
| frontend/.../WasStehtWoKarte.svelte:49-52, :223, :289-302 | MODIFY | Format-Schalter auch im Kontext "vergleich" (neues KONTEXT-Flag statt `tripBloecke`), bei Kompakt Stundenverlauf-Schalter gesperrt, Ausblick bleibt wirksam |
| frontend/.../wasStehtWoSpeicherung.ts:231-238 | MODIFY | Vergleich-Nutzlast schreibt `email_format` (Read-Modify-Write, `telegram_style` bleibt) |
| frontend/src/lib/i18n/messages/{de,en}/wetter.json:185-212 | MODIFY | Texte nicht mehr Trip-formuliert |
| .claude/hooks/email_spec_validator.py:513, :1741 | MODIFY | Kompakt-Zweig (single text/plain, ASCII, X-GZ-Format), Vorlage briefing_mail_validator.py:1297 |
| .claude/hooks/_soll_aus_konfiguration.py:955 | MODIFY | `orte_soll` kennt `email_format` |
| tests/fixtures/einstellung_gleich_mail/fallliste_orte.json, tests/tdd/test_einstellung_gleich_mail_fallliste.py:59-66 | MODIFY | Format-Dimension `kompakt` für Orte (Teilmenge) |
| tests/tdd/test_orte_kompakt_mail.py | CREATE | Renderer, Versand-Header, Resolver, Zwei-Nutzer, Δ-Anker |
| docs/adr/0124-*.md Nr. 6/7, feat_3122:97/:329, feat_3155 AC-2/AC-10, renderer_email_spec.md:272-279, api_contract.md | MODIFY | Widersprüche „Orte kennt keine Kompakt-Mail" nachziehen (Nachtrag, kein stilles Rückgängigmachen) |

### Scope Assessment
- Files: ~18
- Estimated LoC: ~+700/-30 inkl. Tests und Doku (Code ~450)
- Risk Level: MEDIUM (Versandpfad Orte + Validator-Gate; Bestand bleibt durch Vorgabe "full" unverändert)

### Technical Approach
Empfehlung (Plan-Bewertung): #3059 auf „E-Mail-Format Kompakt für Orte" begrenzen.
- Eigener Orte-Kompakt-Renderer; kein Aufsatz auf `render_comparison_text` (Tabellen, Umlaute, weit > 2 KB) und keine SMS-Wiederverwendung (ohne Ortsnamen kaum lesbar). Wiederverwendbar aus Trip-compact.py nur `_ascii`/`_severity_prefix` + `fold_ascii`.
- Signal „Kompakt" = leeres HTML wie beim Trip (kein eigenes Flag), Abzweig in `compare_email_rendern` → Versand und Vorschau gleich.
- Metrik-Auswahl der E-Mail-Spalte bleibt bei Kompakt wirksam (Zeile braucht sie); ignoriert werden nur Block-Schalter (Stundenverlauf), Ausblick steuert `outlook_reports` (#722, feat_3122 Nr. 6, PO #3160).
- `email_format` (Mail) und `telegram_style=kurzform` (Telegram) sind unabhängige Schalter.
- Größe: feste Obergrenze für Orte (Vorschlag 2 KB), Kürzung vom Listenende mit „+N Orte nicht gezeigt".
- Reihenfolge: Resolver → Renderer + Versand + Validator + Soll-Hook in einem Zug → Prüfkatalog → Editor (Editor nie vor Backend ausliefern).
- Zusatzblöcke (Vortag, Nacht) bei Orten = neue Fachlichkeit mit neuem Datenpfad (datierte Snapshots bzw. Nachtfenster ohne Ankunft); Etappen-Kennzahlen sinnlos. Nicht in #3059; bei Bedarf eigene Sub-Issues unter #3047.

### Dependencies
- Upstream: Resolver (ADR-0121), Placements/Tabelle (ADR-0124, feat_3122), `fold_ascii`, `EmailOutput.send(mail_format=…)`.
- Downstream: Scheduler-Versand, Vorschau (compare_preview_service, placements_view), Testversand (über send_compare_preset), Validator/Staging-Gate, Prüfkatalog.
- Parallel: #3333 (Orte anlegen) berührt dieselben Editor-Dateien → früh rebasen. #3102 kein Blocker.

### PO-Entscheidungen (2026-11-24, AskUserQuestion, Kommentar in #3059)
- Zusatzblöcke für Orte: nur „Vergleich mit gestern“, aber ins Backlog → eigenes Issue #3342 (Sub-Issue #3047, nach-go-live). Etappen-Kennzahlen und Nacht-Stundentabelle für Orte nicht vorgesehen. #3059 baut nur Kompakt.
- Inhalt Orte-Kompakt-Mail: eine Zeile je Ort (Name + E-Mail-Metriken), Ausblick je Ort wenn aktiv, kein Stundenverlauf, Kürzung vom Listenende mit „+N Orte nicht gezeigt“. SMS-Text als Mail verworfen.

### Open Questions (Tech-Lead-Vorgaben für die Spec, kein PO-Halt)
- Obergrenze 2 KB wie Trip-Kompakt (renderer_email_spec.md:279).
- Standard für Bestand und Neuanlage: Ausführlich (fehlendes Feld = "full").
