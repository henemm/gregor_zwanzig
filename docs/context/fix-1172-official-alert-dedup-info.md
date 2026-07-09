# Context: fix-1172-official-alert-dedup-info

## Request Summary
Amtliche Warn-Mail (`[KHW 403] Amtliche Warnung`) wiederholt 12× dieselbe Zeile
„Amtliche Warnung: Hitze" und ist inhaltlich karg. Fix: (1) Warnungen nach `(region_label,
hazard)` entdoppeln, (2) je Warnung Schwere-Stufe + Region + Gültigkeitszeitraum ausgeben.
**PO-Format-Entscheidung:** Dedup + Kerninfos (kein Quell-Link).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_alert.py:920` (`check_official_alert_triggers`) | **Kernursache:** sammelt Warnungen pro Etappen-Koordinate ohne Kollabierung nach `(region_label, hazard)`. N Etappen in einer Warnregion → N identische Notices. |
| `src/output/renderers/alert/official_alerts.py:68` (`render_official_alerts_plain`) | Gibt nur `Amtliche Warnung: {label}` aus, verwirft `level`/`region_label`/`valid_from`/`valid_to`. Anzureichern. |
| `src/output/renderers/alert/official_alerts.py:24` (`render_official_alerts_html`) | HTML-Variante analog anreichern (Konsistenz). |
| `src/services/notification_service.py:393` (`send_official_alert`) | Baut `entries = [(a.region_label, [a]) for a in notices]` 1:1 — profitiert von Dedup an der Quelle. |
| `src/services/notification_service.py:487` (`_send_alert` official-block) | Zweiter un-deduplizierter Einsprung — dito. |
| `src/services/official_alerts/models.py:15` (`OfficialAlert`) | Feldquelle: `source, hazard, level(1-4), label, valid_from, valid_to, url, region_label`. |
| `src/output/renderers/alert/official_alerts.py:79` (`collect_trip_alert_entries`) | Vorbild-Dedup (Briefing-Pfad) — gruppiert nach `region_label or label`. |

## Existing Patterns
- **Dedup-Vorbild:** `collect_trip_alert_entries` kollabiert per `region_label or label` → EIN Paar je Warnung. Gleiche Idee für den Alert-Pfad, Schlüssel `(region_label, hazard)`, höchstes `level` behalten.
- **Level-Farbmapping** (bereits in `render_official_alerts_html`): 1–2 grün, 3 orange, 4+ rot. Wortstufen für Plain: 1 grün/unkritisch, 2 gelb, 3 orange, 4 rot (Vigilance-Skala, siehe models.py-Docstring).
- **Renderer ist geteilt (ADR-0011/#1087):** Compare UND Trip nutzen `official_alerts.py`. Anreicherung muss beide Aufrufer verträglich lassen (Compare-Badges + Trip-Alerts + Briefings).

## Dependencies
- **Upstream:** `get_official_alerts_for_location()`, `AlertStateService`.
- **Downstream:** `send_official_alert`/`_send_alert` (Email+Telegram), Compare-Mail-Warnzeile, Trip-Briefing-Warnblock (`plain.py:202`, `html.py`, `compact.py`). Änderung am gemeinsamen Renderer betrifft ALLE → sorgfältig, Regressionsschutz nötig.

## Risks & Considerations
- **Geteilter Renderer:** Anreicherung von `render_official_alerts_plain`/`_html` darf Compare- und Briefing-Ausgabe nicht kaputt machen. Entweder additive Anreicherung mit Regressionstests, ODER neue alert-spezifische Formatfunktion, damit Compare/Briefing-Byte-Gleichheit (AC-2 #1087) gewahrt bleibt. **Design-Entscheidung für die Spec.**
- **Compare-Mail-Validator (#1150!):** Ändert sich der Compare-Warn-Renderpfad, greift `email_spec_validator.py` (X-GZ-Mail-Type: compare). Möglichst NICHT den Compare-Pfad anfassen.
- **Dedup-Ort:** An der Quelle (`check_official_alert_triggers`) dedupt beide Notification-Einsprünge auf einmal — bevorzugt gegenüber Dedup in jedem Renderer-Aufrufer.
- **Gültigkeitszeitraum-Zeitzone:** `valid_from/to` lokal zur Warnregion formatieren (vgl. `utils.timezone`).
- **Nachweis:** echter Alert-Versand (Test-Trip mehrere Etappen/eine Warnregion) an gregor-test@henemm.com, IMAP-Verifikation: genau eine Zeile je Warnung + Kerninfos.
