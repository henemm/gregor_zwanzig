# Context: feat-1441-s2-entwarnung

## Request Summary
Scheibe S2 von #1441 (PO-Entscheid 13.10.2026): Sinkt oder endet eine amtliche Warnung (alle Quellen, nicht nur Lawine), geht eine **Entwarnung** über alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) in beiden Flächen (Trip-Alarm, Ortsvergleich-Alarm) — mit der **Dringlichkeit des alten Werts**. Ein Quellenausfall, eine Neuausgabe oder eine Folgeperiode ist nie eine Entwarnung; pro Nutzer kommt die Entwarnung nur einmal.

## Ist-Stand (Kurzfazit)
Beide Flächen erkennen nur **neue/gestiegene** amtliche Warnungen. Das Melde-Gedächtnis wird beim Verschwinden nie gelöscht und bei Absenkung nie gesenkt (Höchstwert bleibt). Die Alarmpfade werten die Abrufbarkeit der Quelle nicht aus. `urgency_from_official_transition` (`src/services/alert_urgency.py:36`) hat keinen produktiven Aufrufer.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_alert.py:3056-3173` | `check_official_alert_triggers` — Trip-Ermittlung (nur neu/eskaliert); Aufruf in `check_all_trips` :1193-1226 via `_send_alert` (:920) bzw. `_send_official_alert_only` (:3192); Dringlichkeit `urgency_from_official_level(a.level)` :944/:3027/:3246/:3296; Ereignis-Identitäts-Gate :3244-3290, `split_by_threshold` :3300, Retry-Backoff :3304 |
| `src/services/alert_briefing_anchor.py:324-354` | `record_official_alerts_reported` — schreibt Gedächtnis nach Versand (nur Überschreiben, nie Löschen); auch vom Briefing-Versand genutzt (#1614) |
| `src/services/compare_official_alert.py:402-469, 505-514` | Ortsvergleich `_detect` (Fenster = jetzt bis Tagesfenster-Ende, Entity `preset_id:loc_id`), `_record_state` (nur neue); Dringlichkeit `highest_urgency(...)` ~:310, Versand `send_multi_location_official_alert` ~:328 |
| `src/output/renderers/alert/official_alerts.py` | `official_alert_state_key` :451 (Schlüssel enthält `valid_from:valid_to`), `_identity_hazard_prefix` :470, `official_alert_revision_verdict` :496-637 (Absenkung still, `max(alt,neu)` :615), DTO `OfficialAlertNotice` :197 (kein Feld für alte Stufe/Entwarnung), Builder `build_official_alert_notices` :2276 / `build_compare_official_alert_notices` :2366, Renderer Betreff :957, HTML :1525/`render_warn_block` :1901, Plain :1611, Telegram :1934, SMS/Premium-SMS :2187 (Token `_sms_hazard_token` :2171) |
| `src/services/alert_state.py:83ff` | `reset()` schont `official_alert:`-Schlüssel; kein Aufräumen abgelaufener Einträge |
| `src/services/official_alerts/base.py:119-300` | `get_official_alerts_with_status` → `(alerts, unavailable)`, `unavailable = covering>0 and failed>=covering` (:202, Ausgleich verdeckt Teilausfall); `get_official_alerts_for_location` verwirft `_unavailable` (:296); Quellen-Zusammenschluss pro Gefahrenart (:209-235); Zeitfenster-Schnitt (:60-88) |
| `src/services/official_alerts/warn_egress.py:77-115` | Fehlschlag-/Nicht-zuständig-Marker pro Quelle (`observe_fetch_failure`, `mark_not_covered`, `mark_fetch_incomplete`) |
| `src/services/official_alerts/models.py:19,60` | `OfficialAlert` (kein Status-Feld), `comparable_level` (native vor level, ADR-0089) |
| `src/services/official_alerts/meteoalarm.py:620-621` | DE `responseType: AllClear` wird verworfen — potenzielles positives Entwarnungssignal |
| `src/services/notification_service.py:1096-1275, 1410ff` | `send_official_alert` (Trip, 4 Kanäle), `send_multi_location_official_alert` (Compare, `_dispatch_compare_official_*` :1523/:1541/:1580/:1610) |
| `src/services/alert_urgency.py:36-43` | Helfer `urgency_from_official_transition` (max(alt,neu) → Dringlichkeit) |

## Existing Patterns
- **Vorbild Wetter-Entwarnung (#1503 AC-6, ADR-0043):** `_ordinal_change_triggers` / `_ordinal_severity` (`src/services/weather_change_detection.py:955-1000`) — Dringlichkeit = max(alt,neu). Darstellung ohne eigene Vorlage: normaler Change mit `direction="decrease"`, „alt → neu" (`src/output/renderers/alert/render.py:1220/1248/1429/1519`). „Nur einmal": Gedächtnis wird nach Versand auf neuen Wert **gesenkt** (`trip_alert.py:978-986`, `deviation_alert_engine.py:234-248`).
- **„Nicht bestimmbar ≠ Entwarnung":** `weather_change_detection.py:324-404`, `radar_service.py:449`, ADR-0082:47.
- **Drei-Zustände-Muster (Warnung / sauber leer / nicht abrufbar):** `avalanche_report.py:13-16`, `meteoalarm_feed.py:17-21` (#1445 S3) — über `warn_egress`-Marker, Rückgabe bleibt `list[OfficialAlert]`.
- **Gedächtnis erst nach Zustellung** (ADR-0086) — gilt auch für Entwarnungen.

## Dependencies
- Upstream: Quellen-Registry `official_alerts/*`, `warn_egress`, `AlertStateService`, `alert_urgency`, Kanal-Schwellen (ADR-0046), Ereignis-Identitäts-Gate, Retry-Backoff.
- Downstream: Trip-Briefing-Versand (schreibt dasselbe Gedächtnis, #1614), Briefing-Reset (#1460 P2), Mail-Validatoren, SMS-Token-Katalog.

## Existing Specs
- `docs/specs/modules/avalanche_report_bulletin.md` — Abschnitt 8 (:166-175), AC-13 (:275-279), Known Limitations :385, Changelog v1.1 :417: S1 begrenzt bewusst, S2 muss nachziehen.
- `docs/specs/modules/feat_1681_meteoalarm_de.md` — AllClear verworfen (:94), AC-5 (:205-209), Known Limitations (:258-260), Out of Scope (:270): aktive Entwarnung als offene Produktfrage → S2 hebt auf.
- `docs/specs/modules/fix_1503_delta_dringlichkeit.md` — Vorbild-Regel, AC-6 (:203-205).
- `docs/specs/modules/feat_1461_s3a_alarm_dringlichkeit.md` — Spec von `alert_urgency.py`.
- `docs/specs/modules/warnmail_official_alert_display.md` — Darstellung Warn-/Alarm-Mail.
- Randrelevant: `compare_official_alert_channels.md`, `sms_official_alert_tokens.md`, `fix_1744_alarm_format_angleichen.md`, `fix_1935_1779_alarm_nachricht_klarheit.md`, `feat_1260_telegram_kurzstil.md`.

## ADRs
- 0043 (Grundsatz Entwarnung, PO 2026-08-03: „eine Entwarnung ist auch wichtig"), 0089 (Lawine zweite Skala, Gedächtnis auf `native_level`, Identität = Mikroregion), 0016 (amtliche Warnungen additiver Typ), 0046 (Kanal-Schwelle), 0086 (Erfolg = Zustellung), 0082:47, 0069:85.
- **Keine ADR regelt die Entwarnung amtlicher Warnungen** → neue ADR oder Ergänzung 0016/0089 nötig.

## Bestehende Tests (bewachen heutiges Verhalten — teils bewusst anzupassen)
- `tests/test_avalanche_report_escalation.py` — AC-13 :151/:159/:178 (Absenkung still, Höchstwert bleibt), Helfer :188-223, AC-12 :46-127.
- `tests/tdd/test_official_alert_revision_dedup.py` — `test_f004` :459 (Höchstwert wird nicht gesenkt), Trip :527, Compare :603/:615.
- `tests/tdd/test_alert_state_briefing_reset.py` — AC-20..23, :853 (kein Gedächtnis bei Fehlversand), :935-1050.
- Weitere: `test_issue_1088_official_alert_triggers.py`, `test_official_alert_dedup_timespan.py`, `test_official_alert_time_window.py`, `test_alarm_amtliche_warnungen_kette.py`, `test_compare_official_alert*.py`, `test_alert_change_urgency_grading.py:303`, `test_avalanche_official_alert_channels.py`, `test_alarm_totalausfall_wird_wiederholt.py`; Fixtures `tests/tdd/_alarm_amtlich_fixtures.py`, `tests/helpers/official_alert_gate_fixtures.py`.

## Risks & Considerations
1. **Ausfallsignal pro Quelle fehlt in den Alarmpfaden** — heute verworfen; Ausgleichsregel verdeckt Teilausfall (MeteoAlarm fällt aus, GeoSphere leer → `unavailable=False`). Schein-Entwarnung = sicherheitskritisch.
2. **Schlüssel enthält Zeitraum** — Neuausgabe/Folgeperiode erzeugt neuen Schlüssel; Abgleich muss über Identitäts-Präfix + Überlappung laufen.
3. **Wechsel der besten Quelle** pro Gefahrenart ändert die Identität — darf keine Entwarnung auslösen.
4. **Scheinbares Verschwinden durch Fenster:** natürlicher Ablauf (`valid_to < now`), vergangenes Trip-Segment, Tagesfenster-Ende im Ortsvergleich. Spec muss festlegen, welche Fälle Entwarnung sind.
5. **„Nur einmal"** braucht Senken oder Tombstone im Gedächtnis — kollidiert bewusst mit `test_f004` und S1-AC-13 (gezielt anpassen, in Spec begründen).
6. **Trip-Gedächtnis ohne Segment-Bezug** — Entwarnung kennt Ort/Etappe nicht ohne Erweiterung.
7. **Gates/Schwelle** hängen an der Stufe der neuen Warnung — für Entwarnung muss die alte Stufe gelten (sonst erreicht HIGH-Entwarnung die Satelliten-SMS nicht).
8. **Darstellung** — `OfficialAlertNotice` hat kein Feld für alte Stufe/Entwarnungsart; alle vier Renderer × zwei Flächen betroffen; Mail-Validatoren + Renderer-Commit-Gate greifen.
9. **Offizielles AllClear (DE)** als positives Signal nutzbar — Produktentscheid, ob zusätzlich zum Verschwinden.

## Analysis

### Type
Feature (Scheibe S2 von #1441, PO-Entscheid 13.10.2026 — nicht erneut zur Frage stellen)

### Befund Ist-Stand (verifiziert, 3 Explore-Agenten + Plan)
- **Ausfallsignal geht in beiden Alarmpfaden verloren:** Trip (`trip_alert.py:3142`) und Ortsvergleich (`compare_official_alert.py:427`) rufen `get_official_alerts_for_location` (base.py:238), das `unavailable` verwirft. Ausgefallene Quelle = „keine Warnung". Gegenbeispiel mit Status: Briefing `trip_report_scheduler.py:1476-1481`.
- **Aggregat-`unavailable` reicht nicht** (base.py:202 `covering>0 and failed>=covering`): Teilausfall wird kompensiert; der Merge pro Gefahrenart (base.py:209-235) behält nur die Quelle mit höchstem `comparable_level` → Absenkung der unterlegenen Quelle unsichtbar, Ausfall der besten Quelle sieht aus wie Verschwinden. Pro Quelle gibt es heute nur Zähler (Name in :162 verfügbar).
- **Gedächtnis:** Datei pro Entity (`trip.id` bzw. `preset_id:loc_id`), Schlüssel `official_alert:{id|region|label}:{hazard}:{valid_from}:{valid_to}` (official_alerts.py:451), Wert `{last_reported_value=Rang, reported_at, valid_from, valid_to}` (:640-651). **Kein** Quellen-, Orts-/Segment- oder `level`-Feld. Nie gesenkt/gelöscht (nur Revision-Merge trip_alert.py:3168 / compare :462 ersetzt mit `max`); `reset()` schont `official_alert:` (alert_state.py:116); kein GC.
- **Drei Schreibpfade** ins selbe Gedächtnis: Trip-Alarm (`trip_alert.py:3175`), Ortsvergleich (`compare_official_alert.py:505-514`), **Briefing** (`alert_briefing_anchor.py:324-354`, #1614).
- **Fenster:** Trip je Segment `[max(jetzt,Start), Ende]`, vergangene Segmente übersprungen (trip_alert.py:3127); Ortsvergleich jetzt..Tagesfenster-Ende (compare :423-433, :471-503).
- **Dringlichkeit/Schwelle:** Trip `urgency_from_official_level(a.level)` + `split_by_threshold` (:3300); Ortsvergleich Max über den ganzen Preset-Stapel (:310) → Schwelle (:314). `urgency_from_official_transition` (alert_urgency.py:36) ohne produktiven Aufrufer.
- **Reiner Entwarnungs-Versand** hat keinen Zweig: `_send_official_alert_only` (trip_alert.py:3192) prüft nur `bool(official)`.
- **Darstellung:** `OfficialAlertNotice` (official_alerts.py:197) ohne Vorgänger-/Übergangsfeld; Builder :2276/:2366 sehen nur aktuelle Warnungen. Wetter-Change-Vorbild „alt ↓ neu" (render.py:1255), Betreff `{von}→{bis}` (:1219).
- **MeteoAlarm AllClear** verworfen (meteoalarm.py:619-622, nur JSON-Feed setzt `response_type`).
- **Validator:** `.claude/hooks/official_alert_mail_validator.py` (Header `X-GZ-Mail-Type: official-alert`, :159) prüft keine Entwarnung.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/base.py` | MODIFY | Pro-Quelle-Ergebnis VOR dem Merge, NACH dem Fensterfilter herauslösen; neue Funktion `get_official_alerts_with_sources(...)` → `{quelle: (ok, alerts)}`; bestehende Signaturen (37 Aufrufer) unverändert |
| `src/services/official_alert_allclear.py` (Name in Spec) | CREATE | Reine Erkennungsfunktion „gesenkt / vorzeitig beendet / nichts" gegen das Gedächtnis; von beiden Flächen genutzt |
| `src/output/renderers/alert/official_alerts.py` | MODIFY | `official_alert_state_entry` um `source`, `scope`, `level` erweitern; Senken/Tombstone-Schreibweg; DTO-Erweiterung bzw. eigene Entwarnungs-Notice; Builder; Renderer Betreff :957, Headline :1114/:1064, HTML :1525/:1901, Plain :1611/:734, Telegram :1934, SMS/Premium-SMS :2171/:2187 |
| `src/services/alert_briefing_anchor.py` | **MODIFY (Pflicht)** | Briefing-Schreibpfad :324 muss `source`/`scope`/`level` mitschreiben — sonst bekommt jede zuerst per Briefing gemeldete Warnung NIE eine Entwarnung (stiller Totalausfall). Pflicht-Prüfpunkt Adversary |
| `src/services/alert_state.py` | MODIFY | GC abgelaufener `official_alert:`-Einträge (`valid_to < jetzt`) |
| `src/services/trip_alert.py` | MODIFY | `check_official_alert_triggers` (Quellenstatus, Entwarnungs-Erkennung, Rückgabe erweitern), `check_all_trips` :1195-1226, `_send_official_alert_only` :3192 (reine Entwarnung), Gate/Schwelle/Retry nach ALTER Stufe, Gedächtnis senken nach Zustellung |
| `src/services/compare_official_alert.py` | MODIFY | `_detect`, `_record_state`, Stapel-Dringlichkeit inkl. alter Stufen (:310) |
| `src/services/notification_service.py` | MODIFY | `send_official_alert` (:1096-1275), `send_multi_location_official_alert` + `_dispatch_compare_official_*` (:1410ff) Entwarnungen durchreichen |
| `src/services/alert_urgency.py` | MODIFY (klein) | `urgency_from_official_transition` produktiv nutzen (alter Stand aus Gedächtnis) |
| `.claude/hooks/official_alert_mail_validator.py` | MODIFY | Entwarnungs-Plausibilität (alte Stufe > neue Stufe bzw. „beendet") |
| `tests/test_avalanche_report_escalation.py` AC-13 :151/:159/:178 | MODIFY (bewusst) | „Absenkung still, Höchstwert bleibt" wird zu Soll „Entwarnung, Gedächtnis gesenkt" |
| `tests/tdd/test_official_alert_revision_dedup.py` test_f004 :459 (+ :527/:603/:615 prüfen) | MODIFY (bewusst) | dto. |
| neue Verhaltens-Testdateien (z. B. `test_official_alert_allclear.py`, `test_official_alert_allclear_channels.py`) | CREATE | Erkennung, Ausfall/Quellenwechsel/Folgeperiode/Fenster, vier Kanäle × zwei Flächen |
| `docs/adr/00xx-entwarnung-amtlicher-warnungen.md` + Index | CREATE | Keine ADR regelt das bisher (0016/0043/0089 berührt) |
| `docs/specs/modules/avalanche_report_bulletin.md` (AC-13), `feat_1681_meteoalarm_de.md` (AC-5, Known Limitations), `sms_official_alert_tokens.md` | MODIFY | Nachziehen |

### Scope Assessment
- Dateien produktiv: ~9, Tests: ~4, Doku: ~4
- Geschätzte LoC produktiv: ~+450 (Plan-Agent, **unbelegt**; der LoC-Zähler zählt nur produktive Spec-Dateien). Tests zusätzlich ~+450.
- **Entscheidung (Tech Lead): EIN Workflow, EINE Spec** mit `loc_limit_override 500`. Begründung: ~450 produktive Zeilen passen unter 500; drei Teil-Workflows würden das Thema über drei Freigaben strecken und zuerst ein Fundament ohne Nutzerwirkung liefern. `/40` deckt ALLE ACs der Spec ab — kein nachträgliches Verengen. Falls `/30` beim Ausformulieren erkennt, dass es klar >500 wird, wird VOR der Freigabe in zwei Specs geschnitten (Trip / Ortsvergleich), beide in #1441.
- Risk Level: **HIGH** — eine Schein-Entwarnung ist sicherheitskritisch (Wanderer läuft in eine fortbestehende Gefahr).

### Technical Approach (Empfehlung: Variante C + D)
1. **Erkennung über Identität statt vollem Schlüssel:** Abgleich über `_identity_hazard_prefix` (official_alerts.py:470) + Gefahrenart; bewertet werden nur gespeicherte Einträge, deren Zeitraum das aktuell abgefragte Fenster **überlappt**. Damit sind Folgeperiode, vergangenes Trip-Segment und Tagesfenster-Ende im Ortsvergleich keine Entwarnung.
   - aktueller Rang < gespeichert → **gesenkt**
   - keine passende Warnung, Quelle in diesem Lauf `ok`, `valid_to` noch in der Zukunft → **vorzeitig beendet**
   - sonst → nichts
2. **Ausfallsicherheit „im Zweifel still":** Entwarnung nur, wenn die im Gedächtnis gespeicherte **meldende Quelle** in diesem Lauf erfolgreich geantwortet hat (keine Exception, kein `fetch_status.failed`, nicht `not_covered`, nicht `mark_fetch_incomplete`). Verglichen wird auf dem Pre-Merge-Satz dieser Quelle → Wechsel der besten Quelle ist keine Entwarnung. Alt-Einträge ohne `source` erzeugen nie eine Entwarnung (einmalige Lücke, bewusst).
3. **„Beendet" braucht Bestätigung in zwei aufeinanderfolgenden Läufen** (Variante D, Tech-Lead-Entscheid): schützt gegen eine einzelne erfolgreich-aber-unvollständige Antwort (Feed-Bug, leere Teilantwort), die keine Ausfallerkennung fängt. Trade-off: Entwarnung kommt ein Prüfintervall später; Feld `absent_since` im Eintrag. „Gesenkt" steht explizit in den Daten → keine Bestätigung nötig.
4. **Planmäßiger Ablauf (`valid_to` erreicht) ist KEINE Entwarnung** — abgeleitet aus dem PO-Kommentar vom 13.10. („ein Quellenausfall ist nie eine Entwarnung (unavailable/404/**abgelaufen**/egress-gesperrt)") und S1 („abgelaufenes Bulletin = sauber leer"): Das Ende stand schon in der Warnung; zudem ist es nicht von Ausfall/Rotation unterscheidbar. Wird in der Spec als AC ausformuliert und mit der Spec freigegeben. Abgelaufene Einträge räumt ein GC weg.
5. **„Nur einmal pro Nutzer":** Nach Zustellung (ADR-0086) `last_reported_value` auf neuen Rang senken bzw. bei „beendet" Tombstone (`ended_at`, Rang 0). Wiederanstieg = normale neue Warnung. Expliziter Schreibweg, getrennt vom Revision-Merge (der `max` behält). Fehlversand schreibt nichts → Wiederholung wie heute.
6. **Dringlichkeit/Schwelle nach ALTER Stufe** (`urgency_from_official_transition`; `level` im Gedächtnis nötig) → Entwarnung von Stufe „hoch" erreicht auch Premium-SMS (gewollt, PO 07.09.). Ortsvergleich: Stapel-Max über Warnungen UND alte Stufen der Entwarnungen.
7. **Darstellung (nur Daten, keine Empfehlung):** eigener Abschnitt „Entwarnung" in Mail (HTML/Plain) und Telegram; Inhalt Gefahr + Region/Ort + „Stufe alt → neu" bzw. „beendet"; Betreff mit „Entwarnung". SMS/Premium-SMS: ASCII/GSM-7-Token im Warn-Block (Form in der Spec gegen `sms_official_alert_tokens.md` festlegen; dort gilt „1 Zeichen, GSM-7-sicher, kein Emoji").
8. **Gemeinsam mit neuen Warnungen im selben Lauf:** EINE Nachricht, Warnungen zuerst, Entwarnungs-Abschnitt danach; Dringlichkeit = Max beider. SMS-Budget: Warnungen haben Vorrang; eine nicht zugestellte Entwarnung schreibt kein Gedächtnis → kommt beim nächsten Lauf (Kürzungsfall als AC).
9. **MeteoAlarm AllClear bleibt verworfen** (S2 wertet es nicht zusätzlich aus) — das Verschwinden bei gesundem Quellenstatus trägt.

### Varianten
| Variante | Idee | Pro | Contra |
|---|---|---|---|
| A | voller Schlüssel, globales `unavailable` | minimaler Eingriff | Folgeperiode = falsche Entwarnung, Teilausfall verdeckt, Quellenwechsel kippt |
| B | Identität + Gefahr, nur Aggregat-Flag | mittlerer Aufwand | Schein-Entwarnung bei Teilausfall |
| **C** | Identität + Gefahr + Pro-Quelle-`ok` vor Merge, `source` im Gedächtnis | Ausfall und Quellenwechsel sauber | Umbau base.py, Gedächtnis-Schema |
| **D** | C + „beendet" erst nach 2 Läufen | schützt vor leerer Teilantwort | 1 Intervall Verzögerung, Feld `absent_since` |

**Gewählt: C für „gesenkt", D für „vorzeitig beendet".**

### Dependencies
- Upstream: Quellen-Registry `official_alerts/*`, `warn_egress`-Marker, `AlertStateService`, `alert_urgency`, Kanal-Schwellen (ADR-0046), Ereignis-Identitäts-Gate, Retry-Backoff.
- Downstream: Briefing-Versand (gleiches Gedächtnis, #1614), Briefing-Reset (#1460 P2), Mail-Validator `official_alert_mail_validator.py`, SMS-Token-Katalog, Renderer-Commit-Gate.
- Reihenfolge: ADR → Spec → RED (alle ACs) → base.py + Erkennung + Gedächtnis → Renderer → Trip-Verdrahtung → Ortsvergleich-Verdrahtung.
- Parallelstand 15.10.: `workflow.py sessions` zeigt nur diese Session; `git log HEAD..origin/main --grep "#1441"` leer.

### Pflicht-Prüfpunkte Adversary
- Briefing-Schreibpfad schreibt die neuen Felder (sonst nie Entwarnung nach Briefing-Erstmeldung).
- Teilausfall (beste Quelle fällt aus, andere leer) → KEINE Entwarnung.
- Folgeperiode / Neuausgabe / vergangenes Segment / Tagesfenster-Ende / planmäßiger Ablauf → KEINE Entwarnung.
- Zwei verschiedene Nutzer: Entwarnung landet nur beim eigenen Nutzer.
- Dringlichkeit = alte Stufe an der Wirkstelle (Kanalauswahl), nicht nur im Helfer.

### PO-Entscheid 15.10.2026 (AskUserQuestion)
**Briefing reicht:** Hat ein zugestelltes Briefing die niedrigere Stufe (bzw. das Fehlen der Warnung) bereits gezeigt, gilt der Nutzer als informiert — **keine** zusätzliche Entwarnung als Alarm.
Folge für den Ansatz:
- Der Briefing-Schreibpfad (`alert_briefing_anchor.py:324`) **senkt** das Gedächtnis auf die im Briefing gezeigte Stufe (statt `max`) bzw. setzt den Tombstone für eine nicht mehr gezeigte Warnung — **nur** nach erfolgreicher Zustellung und **nur**, wenn die meldende Quelle in diesem Briefing-Lauf erfolgreich geantwortet hat (sonst zeigt das Briefing „nicht abrufbar", das ist keine Information über ein Ende).
- Gleiche Ausfall-/Folgeperioden-/Fenster-Regeln wie im Alarmpfad (gemeinsame Erkennungsfunktion nutzen).
- Neue AC: „Briefing zeigte Stufe 2 nach Alarm Stufe 4 → kein Entwarnungs-Alarm"; Gegenprobe „Briefing mit nicht abrufbarer Quelle → Entwarnung bleibt möglich".

### Open Questions
- [x] (PO) Briefing zeigte die niedrigere Lage bereits → keine zusätzliche Entwarnung (15.10.).
- [ ] (Spec) SMS-Token-Form der Entwarnung gegen `sms_official_alert_tokens.md`.
