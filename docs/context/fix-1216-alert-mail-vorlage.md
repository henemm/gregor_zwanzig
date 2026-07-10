# Context: fix-1216-alert-mail-vorlage

## Request Summary
Die amtliche-Warnung-Alarm-Mail (Ist-Betreff „[KHW 403] Amtliche Warnung") soll dem Claude-Design-Handoff „Alert · Amtliche Warnung" folgen — sprechender Betreff, Route-Bündelung, Warnstufen-Leiter/Eskalations-Meter, Segment-Bezug — und das **über alle drei Kanäle** (E-Mail, Telegram, SMS) sowie für **Trip und Ortsvergleich**. Vorgabe des PO: **Code der Vorlage übernehmen, nicht nachbauen.**

## Vorlage (Design-Handoff)
- Herkunft: Claude-Design-Projekt `019dfcf4-1e69-73f2-b094-c19e157014a2`, Datei `Gregor 20 - Alert Amtliche Warnung.html` (GitHub-Zip-Upload war fehlgeschlagen → PO lieferte Design-Link nach).
- Lokal gesichert: `docs/design-requests/issue_1216_alert_mail/` (HTML + tokens.css).
- **Kern-Regeln:**
  - Betreff `[KHW xxx] <Reichweite> · <Stufe> <Typ> (Tag)` — Reichweite = „gesamte Route" oder betroffenes Segment; bei gemischten Stufen führt die höchste.
  - **Route-Bündelung:** 1 Warnung über mehrere Segmente → 1 Zeile + Segment-Liste (nicht pro Segment wiederholt).
  - **Warnstufen-Leiter** GELB→ORANGE→ROT bei einheitlicher Stufe („1/3" = Position); **Eskalations-Meter pro Warnung** (gefüllte Punkte) bei gemischten Stufen.
  - **Sortierung = Stufe** (ROT>ORANGE>GELB, innerhalb: Startzeit). **Kein Δ/Pfeil** — kategorisch.
  - Nicht betroffene Segmente **durchgestrichen** im Body.
  - **Quelle** immer sichtbar (E-Mail/Telegram ausgeschrieben; SMS entfällt aus Platzgründen).
  - **Telegram:** fette erste Zeile. **SMS:** GSM-7-Tokens (`AMT`, `GELB1/3`, `HZ`/`TH`, `ges.Route`/`nur S2-4`), ≤140 Z.

## Related Files
| Datei | Relevanz |
|------|-----------|
| `src/services/notification_service.py:446` `send_official_alert` | **Standalone-Pfad.** Betreff `[{trip.name}] Amtliche Warnung` hartkodiert; E-Mail = Plain-Text (`html=False`), Telegram = derselbe Plain-Text, **SMS fehlt ganz**. Kernstelle des Bugs. |
| `src/services/notification_service.py:537` `_dispatch_alert_message` | Deviation/Onset-Alert; hängt amtliche Notices als Plain-Block an html/plain/telegram an (`official_notices`, SMS bewusst ohne). |
| `src/output/renderers/alert/official_alerts.py` | Gemeinsamer Renderer. `render_official_alert_notice_plain` (Standalone-Plain, dedupe+Segment+Gültigkeit), `render_official_alerts_html/plain` (Briefing/Compare-Block), `dedupe_official_alerts`, `format_segment_reference`. **Kein HTML-Standalone, keine Telegram/SMS-Formate, kein Betreff-Builder.** |
| `src/output/renderers/alert/render.py` | Deviation/Onset-Renderer `render_subject/email/telegram/sms` auf Design-Tokens. **Vorbild/„dieselben Renderer"** — liefert `_datarow_html`, Badge/H1/Footer-Muster, SMS-Längenkürzung, `_ascii`. Nutzt `AlertMessage`. |
| `src/services/official_alerts/models.py` | `OfficialAlert(source, hazard, level 1–4, label, valid_from/to, url, region_label, dedup_id)`. **Kein `segment`-Feld** — Segment-IDs kommen vom Container. |
| `src/services/official_alerts/geosphere_warn.py:41` / `vigilance.py` / `massif_closure.py` | Hazard-Vokabular: `wind_gust, rain, snow, black_ice, thunderstorm, extreme_heat, extreme_cold, access_ban`. **Kein Mapping hazard→SMS-Kürzel (HZ/TH)** vorhanden. |
| `src/services/trip_alert.py:327/340/920/994` | Trigger: `check_official_alert_triggers` liefert `list[tuple[OfficialAlert, list[str]]]` (Alert + Segment-IDs); `_send_official_alert_only` ruft `send_official_alert`. |
| `src/output/renderers/email/plain.py:200`, `html.py`, `compact.py` | **Trip-Briefing-Block** via `collect_trip_alert_entries` + `render_official_alerts_*`. |
| `src/output/renderers/email/compare_html.py:443`, `comparison.py:109` | **Compare-Briefing-Block** (per-Ort-Streifen HTML + Plain-Zeilen). E-Mail-only. |
| `src/services/scheduler_dispatch_service.py:251/290`, `compare_subscription.py:18` | Compare-Report: Betreff `Wetter-Vergleich: {name}`, Versand **nur E-Mail**. |

## Existing Patterns
- **Ein gemeinsamer Renderer** für amtliche Warnungen (ADR-0011, Epic #1073 Punkt 6) — Trip-Briefing + Compare rufen dieselben `render_official_alerts_*`-Funktionen.
- **Design-Token-HTML** (`_datarow_html`, Badge/H1/Footer) im Deviation/Onset-Renderer — das ist das Muster, das die Vorlage für die Standalone-Mail verlangt.
- `dedupe_official_alerts` (dedup_id|region_label|label, hazard; höchste Stufe je Gruppe) + `format_segment_reference` (Range/Aufzählung/Verdichtung, 🏁 Ziel) — **direkt wiederverwendbar** für Bündelung/Segment-Bezug der Vorlage.
- SMS: `_ascii()` + Längen-Budget-Kürzung in `render_sms` — Muster für die neuen SMS-Tokens.

## Dependencies
- Upstream: `OfficialAlert`-Model, `dedupe_official_alerts`, `format_segment_reference`, Design-Tokens (`email/design_tokens.py`), `utils.timezone.local_fmt`.
- Downstream: `EmailOutput/TelegramOutput/SMSOutput.send`, `mail_type`-Header (Validator-Dispatch), `alert_state` (Dedupe über Zyklen).

## Existing Specs
- `docs/specs/modules/issue_1034_official_alerts_foundation.md` (Datentyp), `issue_1087_*` (gemeinsamer Renderer), `#1172/#1200` (Standalone-Dedup + Segment-Bezug), `#1217/#1218` (Dedup-Namespace).

## Risks & Considerations
- **SCOPE-BEFUND (für Analyse-Phase entscheidend):** Der Compare-Pfad hat **keinen eigenständigen amtliche-Warnung-Alert** und gibt amtliche Warnungen **nie über Telegram/SMS** aus — nur als eingebetteten Block in der E-Mail-Vergleichs-Mail. „Vorlage auf Compare-Standalone anwenden" wäre daher ein **neues Feature** (`send_multi_location_official_alert` + Trigger-Verdrahtung + Kanal-Config), nicht Format-Fidelity. → PO-Empfehlung vor Spec: #1216 auf den **Trip-Standalone-Alert (3 Kanäle)** fokussieren + gemeinsamen Renderer, der Briefing-Blöcke (Trip+Compare) mitzieht; Compare-Standalone-Alert als **separates Issue**.
- Die Vorlage zeigt die **Standalone-Alarm-Mail**, nicht den Briefing-Block. Wie weit die Bündelungs-/Leiter-Optik auf den (dichteren, eingebetteten) Briefing-Block übertragbar ist, muss die Analyse klären.
- **Gates:** `alert/*.py` triggert `renderer_mail_gate` → Radar-Validator; Mail-Änderungen brauchen Validator-Lauf gegen echte Staging-Mail. Test-Politik: Kern-Tests deterministisch, Bug-Repro aus Nutzersicht.
- Neues Mapping `hazard → (Anzeige-Name, SMS-Kürzel)` nötig (HZ/TH etc.) — es gibt keins.
- Betreff-Reichweite („gesamte Route" vs. Segment) verlangt Wissen über die Gesamt-Segmentzahl des Trips, nicht nur die betroffenen — muss beschafft werden.
- Kein Regress bei Dedup (#1172/#1200/#1217/#1218) — die Bündelung der Vorlage muss auf `dedupe_official_alerts` aufsetzen, nicht daneben.

## Analysis

### Type
Bug (Format-Fidelity zu einer freigegebenen Design-Vorlage). Kein Dedup-Bug (Mail ist bereits sauber dedupliziert, #1172/#1200/#1217/#1218).

### Kernbefund: Was die Vorlage ist — und wo sie greift
Die Vorlage ist durchgängig eine **eigenständige (standalone) Alarm-Mail** über 3 Kanäle. Sie mappt **1:1 auf den Trip-Standalone-Pfad** (`send_official_alert`, #1088) — genau die Mail aus dem Issue-Screenshot. Sie ist **kein** Briefing-Block-Design (Briefing zeigt die Vorlage nicht).

Ist-Zustand des Ziel-Pfads (Trip-Standalone):
- E-Mail = Plain-Text (`html=False`) — **kein HTML-Renderer** vorhanden
- Telegram = derselbe Plain-Text — **kein eigenes Format**
- SMS = **fehlt komplett** (kein Zweig in `send_official_alert`)
- Betreff = `[{trip.name}] Amtliche Warnung` (nichtssagend)

### Technical Approach (Reuse-first, „Code verwenden")
Ein neuer, gemeinsamer **Official-Alert-Präsentations-Renderer** (erweitert `alert/official_alerts.py`) mit vier reinen Funktionen analog `alert/render.py`:
- `render_official_alert_subject(notices, *, total_segments, trip_short)` → `[KHW] <Reichweite> · <Stufe> <Typ> (Tag)`; höchste Stufe führt; Reichweite = „gesamte Route" wenn betroffene ⊇ alle Segmente, sonst `format_segment_reference`.
- `render_official_alert_html(notices, ...)` → Vorlagen-HTML auf Design-Tokens: Verdict-Badge, **Warnstufen-Leiter** (einheitliche Stufe) bzw. **Eskalations-Meter** (gemischt), Warnungs-Block mit Segment-Chips (betroffen/durchgestrichen), Quelle, Footer. Baut auf `_datarow_html`-Muster + Tokens.
- `render_official_alert_telegram(notices, ...)` → fette 1. Zeile + Warnungszeilen (Muster `_render_telegram_onset`).
- `render_official_alert_sms(notices, ...)` → GSM-7-Tokens ≤140 (`_ascii` + Budget-Kürzung wie `render_sms`).
- Neues Mapping `hazard → (Anzeige, SMS-Kürzel)` (thunderstorm→Gewitter/TH, extreme_heat→Hitze/HZ …).

Wiederverwendet **ohne Neubau:** `dedupe_official_alerts` (Bündelung, bereits im Trigger aktiv), `format_segment_reference` (Segment-Bezug), Design-Tokens, `_ascii`, `local_fmt`. Verdrahtung: `send_official_alert` ruft die neuen Renderer (HTML-Mail statt `html=False`, strukturiertes Telegram, **neuer SMS-Zweig**); `total_segments` aus `trip` beschaffen.

Briefing-Blöcke (Trip `plain/html/compact`, Compare per-Ort-Streifen): erben über den gemeinsamen Renderer die **Regeln** (Sortierung=Stufe, Bündelung, Segment-Bezug, kein Δ) — die die Blöcke via #1172/#1200/#1217 großteils schon erfüllen. Die standalone-exklusive Leiter/Meter-Optik wird im dichten eingebetteten Streifen **nicht** neu erfunden (kein Design dafür).

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| `src/output/renderers/alert/official_alerts.py` | MODIFY | 4 neue Präsentations-Renderer (subject/html/telegram/sms) + hazard-Mapping |
| `src/services/notification_service.py` | MODIFY | `send_official_alert`: HTML-Mail, strukturiertes Telegram, neuer SMS-Zweig |
| `src/services/trip_alert.py` | MODIFY (klein) | `total_segments`/`trip_short` an `send_official_alert` durchreichen |
| `tests/tdd/test_*` (neu, verhaltensbenannt) | CREATE | Betreff/HTML/Telegram/SMS-Fidelity + Bündelung/Stufen-Leiter/Segment |

### Scope Assessment
- Files: ~3 MODIFY + 1–2 CREATE (Tests)
- Est. LoC: +180/-30 (Renderer-lastig; ggf. LoC-Override nötig — vorher PO fragen)
- Risk: **MEDIUM–HIGH** (nutzersichtbarer Alarm-Kanal, `renderer_mail_gate`/Radar-Validator, Mail-Validator-Lauf Pflicht)

### Aufgelöste Scope-Richtung (PO 2026-07-10)
PO-Prinzip: „Ortsvergleiche verhalten sich grundsätzlich wie Trips, gleiche Funktionen nutzen, **nichts neu erfinden** — Ortsvergleiche sind nur abgewandelte Trips." Deckt sich mit Konvergenz-Richtung Epic #1204. Zusatz: wo eine Design-Vorlage fehlt, **melden** — PO lässt sie bei Claude Design erstellen, ich erfinde nichts.

**Architektur-Konsequenz:** Die vier Präsentations-Renderer werden **kontext-agnostisch** gebaut (Input = generische `notices` + Scope-Deskriptor), NICHT trip-spezifisch — damit Trip UND Ortsvergleich exakt dieselben Funktionen aufrufen. Scope-Vokabular kommt vom Aufrufer: Trip liefert Segment-/Routen-Bezug (`format_segment_reference`, „gesamte Route"), Ortsvergleich liefert Orts-Bezug („alle Orte" / „nur Ort B") — reine Text-Adaption, kein neues Layout.

**Ist-Lage Ortsvergleich (bestätigt):** amtliche Warnungen werden pro Ort **gefetcht** (`comparison_engine.py:188`, `LocationResult.official_alerts`), aber es gibt **kein** eigenständiges Auslösen (kein State-Trigger analog `check_official_alert_triggers`), **kein** `send_multi_location_official_alert`, und Vergleichs-Mails gehen nur per E-Mail. Parität = neuer Trigger + Versandweg, der die **gemeinsamen** Renderer nutzt.

**Delivery (Slicing, keine Architektur-Trennung):**
- **Slice 1 (dieser Workflow):** kontext-agnostische Renderer + Trip-Standalone-Alarm über E-Mail/Telegram/SMS (= Screenshot-Fix). Eigenständig deploybar + staging-verifiziert.
- **Slice 2 (Folge, unter #1216):** Ortsvergleich-Standalone-Alarm über dieselben Funktionen (E-Mail/Telegram/SMS) + Trigger/State/Orts-Scope. Kein Neubau der Darstellung.

**Fehlende Design-Vorlage (an PO gemeldet):** Für die amtliche-Warnung-Darstellung **innerhalb** der normalen Tour-Vorschau- bzw. Vergleichs-Mail (die eingebettete Warn-Sektion, kein Standalone-Alarm) existiert **keine** Vorlage. Nicht in Scope; falls Angleich gewünscht → Claude-Design-Anfrage. Wird NICHT erraten.

### Open Questions
- [ ] Betreff-Präfix `[KHW …]`: kommt aus `trip.name`. Für Ortsvergleich gibt es keinen „trip.name" — welcher Kurzname trägt den Präfix? (Slice-2-Detail, in Slice-2-Spec.)
- [ ] `total_segments` für „gesamte Route"-Erkennung: aus `trip` beziehen (Slice 1).
