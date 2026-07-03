# Context: fix-alert-bundle-958ff

Bündel aus 8 Alert-Issues: #958, #959, #933, #921, #980, #981, #982, #986.
Standard Track (Intake-Score 3: Scope High, Blast Medium, Unsicherheit Low).

## Request Summary

Acht zusammenhängende Bugs im Alert-System beheben: semantisch falsches
„über/unter"-Label (#958), tote `freezing_level`-Alert-Metrik + Zwei-Namen-Verwirrung
(#959), ungefilterte Schwellwerte-Liste im Alerts-Tab (#933), veraltete
Profil-Farb-Tests am toten Alt-Pfad (#921) sowie vier Renderer-Abweichungen von der
Design-Vorlage bei gemischten über/unter-Schwelle-Events (#980, #981, #982, #986).

## Related Files

| File | Relevanz |
|------|----------|
| `src/output/renderers/alert/model.py:62-83` | `over_thr()`/`side_label()`/`severity()` — Kern von #958; Fundament für #980/981/982 |
| `src/output/renderers/alert/render.py` | Alle 4 Kanal-Renderer — #980 (Z.281-290 Multi-Zeile), #981 (Z.195-203 Betreff, Z.277 Verdict, Z.342 Telegram), #982 (Z.24-27 `_sorted`), #986 (Z.299-317 Datenblock-Rows) |
| `src/output/renderers/alert/project.py:49-65` | Baut `AlertEvent` aus `WeatherChange` — `threshold` = Δ-Sensitivität (#958-Beleg) |
| `src/services/weather_change_detection.py:41-51,69-99` | `_ALERT_METRIC_TO_SUMMARY_FIELD` / `_ALERT_METRIC_TO_CATALOG_ID` — FREEZING_LEVEL fehlt in beiden (#959 Befund 1) |
| `src/services/alert_preset.py:44-45` | Preset-Zeile für FREEZING_LEVEL existiert (Δ 400/200/100) — erzeugt Regeln, die der Detector still verwirft |
| `src/app/models.py:768-788` | `AlertMetric`-Enum: `SNOW_LINE` + `FREEZING_LEVEL` koexistieren seit #946 |
| `src/app/metric_catalog.py:266-272,390-397` | `snowfall_limit` (eigene Wettergröße!) vs. `freezing_level` (summary_field `freezing_level_m`) |
| `src/formatters/trip_report.py` | `format_email(report_type='alert')` — toter Alt-Pfad, kein Produktiv-Aufrufer (#921) |
| `tests/tdd/test_trip_alert_profile.py:122-166` | Zwei AC-2-Tests fordern Profilfarbe entgegen PO-Entscheidung (#921) |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte:49,95-96` | Filter-Aufruf `activeAlertableMetrics` (#933) |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts:279-323` | `CATALOG_TO_ALERT_METRICS`-Mapping + drei Fallback-Zweige auf ALLE Metriken (Z.311/313/320) — #933-Verdächtige |
| `frontend/src/lib/utils/alertMetricLabels.ts:19,31` | `snow_line`=„Schneefallgrenze" / `freezing_level`=„Nullgradgrenze" (#959 Befund 2) |
| `docs/design-requests/alert-mail-vorschlaege/Gregor 20 - Alert Mail Vorschläge.html:55-58,218-236` | SOLL: `.datarow` flex/space-between (#986); Multi-Mockup mit gedämpfter „Regen% · unter Schwelle"-Zeile (#980) und Betreff, der nur über-Schwelle-Events zählt (#981) |

## Analyse-Kernbefunde

1. **#958 ist das Fundament des Renderer-Teilbündels.** `over_thr()` vergleicht
   `value_to` (Absolutwert, z. B. Nullgradgrenze 3.285 m) mit `e.threshold`
   (Δ-Sensitivitätsschwelle, z. B. 400 m) — semantisch falsch, für Höhen-Metriken
   konstant „unter". #980 (Dämpfung), #981 (Zähler/Top3-Filter), #982 (Sortierung)
   und die Verdict-Farbe (render.py:293-296) bauen ALLE auf `over_thr()` auf —
   deren Fixes sind nur korrekt, wenn `over_thr()` zuerst repariert wird.
   Konsistente Neudefinition: Event ist „über Schwelle" ⇔ `abs(value_to − value_from)
   ≥ threshold` (Δ-Semantik — deckungsgleich mit dem Auslöse-Grund des Alarms;
   unter-Schwelle-Events sind seit #638 bewusst mitgelieferte Kontext-Events).
   Wortlaut-Konsequenzen für Single-Metrik-Verdict/Datenblock (`side_label`) sind
   PO-Entscheidung in der Spec.
2. **#959 braucht eine Produktentscheidung**: (a) `snow_line`+`freezing_level` zu
   EINER Metrik „Nullgradgrenze" konsolidieren (beide beobachten faktisch
   `freezing_level_m`; #961-OR-Policy war erklärte Übergangslösung) oder
   (b) FREEZING_LEVEL voll verdrahten + `snow_line` auf das echte `snowfall_limit_m`
   umziehen. Option (a) ist deutlich kleiner und fachlich sauber
   (Schneefallgrenze ≠ Nullgradgrenze; `snowfall_limit` bleibt als Briefing-Metrik erhalten).
   Migration: Bestandstrips mit `metric_alert_levels.snow_line` müssen weiter wirken.
3. **#933**: Filter existiert seit #961, degradiert aber in drei Zweigen auf „alle 14
   Metriken" (leere/nicht gemappte Auswahl). Verhalten auf Staging verifizieren;
   Fix vermutlich: Fallbacks entfernen bzw. leere Auswahl → leere Tabelle + Hinweis.
4. **#921**: PO-Entscheidung liegt vor (Alarm-Mail bewusst neutral). Rest-Arbeit:
   zwei Tests auf neutrales Soll korrigieren, toten `report_type='alert'`-Zweig
   entfernen. Ursprünglich an #918 gekoppelt — #918 ist zu, Aufräumen blieb liegen.
5. **#986**: Datenblock-Zeilen als Outlook-kompatible 2-Spalten-Tabellen-Rows
   (Pattern: Briefing-Mail-Tabellen, vgl. #902 Outlook-Inline-Borders) statt
   aneinanderklebender Spans. Betrifft Deviation-Single, Deviation-Multi UND
   Onset-Datenblock (render.py:137-152).

## Existing Patterns

- Metrik-Registry als Single Source (`metric_catalog.py`, seit #914/#917) — Kürzel,
  Dezimalstellen, cmp, sms_code kommen ausschließlich von dort.
- Design-Tokens für Mail-HTML: `output/renderers/email/design_tokens.py`.
- Outlook-kompatible 2-Spalten-Rows: bestehende Briefing-Mail-Tabellen (#902).
- Frontend-Filter-Pattern: `activeAlertableMetrics()` + `activeMetrics`-Prop.

## Dependencies

- Upstream: `WeatherChange` (models.py), Katalog, Design-Tokens, `trip_alert.py`
  (reicht seit #638 alle Changes durch — Verhalten NICHT ändern, nur Darstellung).
- Downstream: Alert-Versand E-Mail/Telegram/SMS (Prod-Pfad seit #917), Alert-Vorschau
  (4 Kanäle, #918), Bestandstests `test_issue_917_alert_renderer.py`,
  `test_issue_957_*`, `test_issue_978_*`.

## Existing Specs

- `docs/specs/modules/fix_946_alert_architecture.md` — AC-6/AC-8 (freezing_level) unvollständig erfüllt
- `docs/specs/modules/epic_191_state_migration.md` — AC-Format-Vorbild
- #978-Spec-Nachträge (Sortierung „gedämpft zuletzt", Top3 severity-absteigend)

## Risks & Considerations

- **`over_thr()`-Neudefinition ändert Verdict-Farbe/Sortierung/Zähler bestehender
  Alerts** — Bestandstests aus #957/#978 können brechen; erwartete Brüche in der
  Spec ausweisen.
- **#959 Migration**: Bestands-`metric_alert_levels` mit `snow_line`-Key müssen
  ohne Datenverlust weiterwirken (Read-Modify-Write-Regel, Schema-Backup-Hook).
- SMS-Renderer (`_sms_token`) nutzt `over_thr` NICHT — Betreff/Telegram/E-Mail sind
  die betroffenen Kanäle; SMS nur via Sortierung (#982).
- Validator-Gate: Alert-Mails haben keinen eigenen Mail-Validator (nur compare +
  trip-briefing) — E2E-Nachweis via Vorschau-Endpoint (#918) + echter Staging-Alert
  (Fake-Radar-Seam bzw. Preview-Payload, siehe Memory `reference_onset_preview_verification`).
- `renderer_mail_gate` feuert NICHT (nur `renderers/email/*`, `formatters/*`,
  `outputs/email.py`) — aber #921 fasst `src/formatters/trip_report.py` an →
  Modus-Matrix-Test + Briefing-Validator werden Pflicht vor Commit.
