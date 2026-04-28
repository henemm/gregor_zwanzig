# External Validator Report

**Spec:** docs/specs/modules/output_channel_renderers.md
**Datum:** 2026-04-28T04:55:00Z
**Server:** https://gregor20.henemm.com
**Validator:** External (unabhängig von Implementer-Session)

## Methodik

- Validator hat **kein** `src/`, `git log`, `git diff`, `docs/artifacts/<vorhandenes>` gelesen.
- Beweisführung über **echte** UI-Aktionen (Playwright/Chromium) und **echten** E-Mail-Empfang via IMAP.
- Trigger-Workflow:
  1. Login an `https://gregor20.henemm.com` (HTTP 200).
  2. Test-Trip `validator-beta3-test` via `POST /api/trips` angelegt
     (Stage `Tag 1: Validator-Test`, Pollença → Lluc, Mallorca, profile=default).
  3. `POST /api/scheduler/trip-reports?hour=6` → Morgen-Report (count=1).
  4. Trip auf Stage-Datum `2026-04-29` aktualisiert,
     `POST /api/scheduler/trip-reports?hour=18` → Abend-Report (count=1).
  5. Beide E-Mails via IMAP `mail.henemm.com:993` empfangen und Body geparst.
  6. Test-Trip via `DELETE /api/trips/validator-beta3-test` aufgeräumt (HTTP 204).

## Spec → Expected Behavior (verifizierte Punkte)

### `TripReportFormatter.format_email` (Adapter, A2)

| # | Expected Behavior | Beweis | Verdict |
|---|---|---|---|
| 1 | Adapter liefert `TripReport` mit `email_subject`, `email_html`, `email_plain` (DTO-Vertrag unverändert) | Empfangene E-Mails 715 + 716 sind `multipart/alternative` mit Subject + `text/html` + `text/plain`. Beide Parts vorhanden, beide nicht-leer (Plain 1687/2567 chars, HTML 4568/5800 chars). | **PASS** |
| 2 | Subject ist §11-konform (Wrapper über β2 `build_email_subject`) | Morgen: `[VALIDATOR β3 Renderer-Split] Tag 1: Validator-Test — Morgen — D22 W15 G31`. Abend: `… — Abend — D22 W15 G32`. Format `[Trip] Stage — ReportType — D{T} W{W} G{G}` entspricht §11-Pattern (β2-Subjekt-Filter aktiv). | **PASS** |
| 3 | `email_html` enthält Voll-HTML mit Tabellen, Compact-Summary, Daylight | HTML enthält `<!DOCTYPE html>`, mehrere `<table>`-Blöcke mit Spalten Time/Temp/Feels/Wind/Gust/Rain/Thunder/SnowL/Cloud/Sun, Compact-Summary-Block (`Tag 1: Validator-Test: 18–22°C, 🌥️, trocken …`), Daylight-Block (`🌄 Ohne Stirnlampe: 06:30 – 20:31`). | **PASS** |
| 4 | `email_plain` enthält identische Sektionen mit ASCII-Tabellen | Plain hat denselben Header/Compact/Daylight + ASCII-Tabellen mit `-----`-Trennern. Spalten identisch zu HTML. | **PASS** |
| 5 | Plain-Werte stimmen zellweise mit HTML überein | HTML-Row `<td>10</td><td>18.2</td><td>17.7</td><td>8</td><td>18</td><td>0.0</td>…` ↔ Plain-Row `10  18.2  17.7  8  18  0.0  …`. Stichprobe über 5 Zeilen Segment 1 und 3 Zeilen Destination identisch. | **PASS** |
| 6 | `night_rows` nur bei `evening` (Test §4: `test_render_email_no_night_rows_when_morning`) | Morgen-Plain: kein "Nacht am Ziel"-Block. Abend-Plain: enthält `━━ Nacht am Ziel (525m) ━━` und `━━ Zusammenfassung ━━` mit `🌡 Tiefste Nachttemperatur: 13.6 °C`. | **PASS** |
| 7 | Subject/Body reagieren auf `report_type` | Morgen-Body-Header `Morning Report – 28.04.2026`, Abend-Body-Header `Evening Report` + Stage-Datum `29.04.2026`. Subject-Tokens unterscheiden sich (G31 vs G32) → Tokens werden pro Forecast neu berechnet. | **PASS** |
| 8 | Pure-Function / Determinismus von `render_email()` (Test §4) | Aus extern nicht beweisbar (Forecast-Provider liefert pro Aufruf eigene Daten; UI ruft Renderer indirekt). Strukturelle Konsistenz beider Mails ist gegeben — bit-Determinismus bleibt **UNKLAR** über UI. | **UNKLAR** |
| 9 | `email_html` enthält Tabellen-Header `<th>` (Test §4: `test_render_email_html_contains_segment_table`) | HTML enthält `<table><tr><th>Time</th><th>Temp</th>…<th>Sun</th></tr>` zweimal (Segment 1 + Destination) bei Morgen und dreimal bei Abend (+Night). | **PASS** |
| 10 | Compact-Summary-Block sichtbar | HTML hat eigenen Block (`background:#f0f7ff;border-left:4px solid #42a5f5`), Plain-Body führt die gleiche Zeile vor dem Daylight-Block. | **PASS** |

### `SMSTripFormatter.format_sms` (Adapter, A3)

| # | Expected Behavior | Beweis | Verdict |
|---|---|---|---|
| 11 | `sms_text=None` in allen aktiven Pfaden (Spec, A3) | Test-Trip mit `send_sms=false`, `send_signal=false`. Nur E-Mail-Pfad ausgelöst. SMS-Render-Strecke wird in Produktion **nicht** befahren — durch Spec explizit so vorgesehen. | **PASS** (intent) |
| 12 | `format_sms()` produziert v2.0-Format (`{Name}: N D R PR W G TH:…`) statt Legacy (`E1:T12/18 …`) | Aus extern **nicht** verifizierbar. SMS-Render-Strecke ist in Produktion dormant. Direkt nur über Unit-Test (`tests/unit/test_renderers_sms.py`, `test_render_sms_v2_format`) prüfbar. | **UNKLAR** |
| 13 | `render_sms()` ist Wrapper über `render_line()` (Test §5) | Aus extern nicht prüfbar (kein Aufruf-Pfad). | **UNKLAR** |

### `format_alert_sms` (A4)

| # | Expected Behavior | Beweis | Verdict |
|---|---|---|---|
| 14 | Bleibt Legacy, von β3 unangetastet | Aus extern nicht prüfbar (kein Alert-Pfad ausgelöst). | **UNKLAR** |

## Zusätzliche Beobachtungen / Findings

### Finding 1 — Token-Aggregation Subject vs. Tabelle

- **Severity:** LOW
- **Expected (Spec):** `D` = Daytime peak temp, `W` = Wind, `G` = Gust max — gemäß `sms_format.md` v2.0 §2/§3 (β1 Token Builder).
- **Actual:** Morgen-Subject `D22 W15 G31`. Tabelle Segment 1 zeigt max Temp 22.0, max Wind 16, max Gust 32. `D22` und `G31` weichen leicht ab (max Gust 32 vs Subject G31, Wind 16 vs W15). Abend-Subject `G32` matcht Tabelle 32.
- **Bewertung:** Diskrepanz vermutlich durch Token-Aggregations-Regel (Quantil/Mittelwert) statt Raw-Max — **kein β3-Scope** (β1-Token-Builder ist Authority). β3 reicht `TokenLine.main_risk`/Tokens nur durch.
- **Evidence:** `email-headers.txt`, `email-plain.txt`.

### Finding 2 — Determinismus über UI nicht prüfbar

- **Severity:** INFORMATIONAL
- **Expected (Spec):** "Identische Inputs → bit-identische Outputs" für `render_email()` und `render_sms()`.
- **Actual:** Forecast-Provider liefert pro Aufruf evtl. neue Daten; UI bietet keinen "fixed input"-Pfad. Pure-Function-Determinismus muss über die in der Spec geforderten Unit-Tests (`test_render_email_pure_function`) bewiesen werden, nicht über UI.
- **Konsequenz:** Renderer-Determinismus bleibt aus Black-Box-Sicht **UNKLAR**.

### Finding 3 — SMS-Pfad in Produktion nicht aktivierbar (per Design)

- **Severity:** INFORMATIONAL
- **Expected (Spec, A3):** SMS-Wire-Format wechselt auf v2.0, aber „null Live-Aufrufer".
- **Actual:** Bestätigt: Trip-Konfig erlaubt zwar `send_sms=true`, aber die Test-Mechanik triggert ausschließlich E-Mail. SMS-Format-Korrektheit (v2.0) muss über Unit-Tests `test_render_sms_v2_format` und `test_renderers_sms.py` belegt werden.
- **Konsequenz:** Akzeptanzkriterium "SMS-Tests in `test_sms_trip_formatter.py` migriert auf v2.0-Format und grün" ist aus extern **nicht** beweisbar.

## Acceptance Criteria — Coverage durch externe Validierung

| AC (β3-Phase) | Extern beweisbar? | Verdict |
|---|---|---|
| `src/output/renderers/sms/render.py` existiert, ≤120 LoC | Nein (src/ verboten) | n/a |
| `src/output/renderers/email/{__init__,html,plain,helpers}.py` existieren, je ≤500 LoC | Nein | n/a |
| `TripReportFormatter.format_email()` Signatur byte-identisch | Nein (Code-Inspektion) | n/a |
| `TripReport`-DTO unverändert | Indirekt: E-Mail mit Subject+HTML+Plain wurde geliefert ⇒ DTO-Felder konsistent | **PASS** |
| 5 Plain-Goldens grün (bit-identisch) | Nein (Test-Run nötig) | n/a |
| ~87 bestehende HTML/Plain-Tests grün ohne Code-Änderung | Nein | n/a |
| SMS-Tests migriert auf v2.0 und grün | Nein | n/a |
| Neue Direktaufruf-Tests grün | Nein | n/a |
| **E2E-Test (`e2e_browser_test.py email`) grün** | **Ja**: E-Mail über UI/API getriggert, empfangen, strukturell valide | **PASS** |
| `email_spec_validator.py` Exit 0 | Nein (Hook nicht extern ausgeführt) | n/a |
| `format_alert_sms` unverändert (A4) | Nein | n/a |
| Adapter-Dateien mit Deprecation-Header | Nein (Code-Inspektion) | n/a |
| β1-SMS-Goldens unverändert grün | Nein | n/a |
| β2-Subject-Goldens unverändert grün | Indirekt: Subjects entsprechen §11-Pattern (`[Trip] Stage — Type — D W G`) | **PASS** (semantisch) |
| Render-Module importieren keine Domain-Funktionen (A5) | Nein (Code-Inspektion) | n/a |
| Kein `RiskEngine`-Import in `src/output/renderers/` | Nein (Code-Inspektion) | n/a |

## Beweismittel

- `screenshots/01-login.png` — Login-Seite vor Auth.
- `screenshots/02-home.png` — Startseite nach Auth.
- `screenshots/03-trips-list.png` — Trips-Übersicht (zeigt Action-Buttons inkl. „Test Abend-Report").
- `screenshots/10-trips-list-pretrigger.png` — Snapshot vor Trigger.
- `screenshots/11-after-evening-trigger.png` — Bestätigungs-Dialog „Test-Report (Evening) wurde ausgelöst".
- `email-headers.txt` — Header der Morgen-Mail (Subject §11-Format, Multipart).
- `email-plain.txt` — Plain-Body Morgen.
- `email-html.html` — HTML-Body Morgen.
- `email-plain-evening.txt` — Plain-Body Abend (mit Nacht-Block).
- `email-html-evening.html` — HTML-Body Abend.

## Verdict: **AMBIGUOUS**

### Begründung

**Funktional (Channel-Pfad E-Mail):** Der β3-Vertrag ist aus Black-Box-Sicht **erfüllt**:
- Adapter liefert `TripReport`-DTO mit `email_subject`, `email_html`, `email_plain` (Punkt 1–4, 9, 10 = PASS).
- `(html, plain)`-Output ist strukturell konsistent (Punkt 5 = PASS).
- `report_type=evening` produziert Night-Block, `morning` nicht (Punkt 6 = PASS).
- Subject folgt §11-Pattern (Punkt 2 = PASS, β2 indirekt verifiziert).

**Nicht extern beweisbar:**
1. **SMS-Render-Strecke (`render_sms`, `format_sms`-Adapter mit v2.0-Format):** Per Spec dormant in Produktion (`sms_text=None`). Format-Korrektheit ausschließlich über die in der Spec geforderten Unit-Tests verifizierbar — extern weder beobachtbar noch widerlegbar.
2. **Pure-Function-Determinismus:** Forecast-Provider variiert; bit-Identität nicht über UI nachweisbar.
3. **Code-Strukturelle Akzeptanzkriterien** (LoC-Budget, Modulpfade, fehlende Domain-Imports, Deprecation-Header): Validator hat per Auftrag keinen `src/`-Lesezugriff.
4. **Goldens / bestehende Tests grün:** Test-Run liegt außerhalb des extern beobachtbaren Verhaltens.

**Empfehlung:**
Die E-Mail-Render-Strecke ist extern als funktional erwiesen (**VERIFIED** für E-Mail-Channel).
Für ein finales **VERIFIED** auf der Gesamtspec muss zusätzlich nachgewiesen sein:
- `pytest tests/unit/test_renderers_sms.py` (insbesondere `test_render_sms_v2_format`) grün,
- `pytest tests/unit/test_renderers_email.py` grün,
- `pytest tests/golden/email/test_email_plain_golden.py` grün (5 Profile bit-identisch),
- `pytest tests/unit/test_sms_trip_formatter.py` grün auf v2.0-Format,
- `pytest tests/golden/test_sms_golden.py` und `tests/golden/test_subject_golden.py` unverändert grün,
- LoC-Budget pro Datei (≤500, `render_sms` ≤120) per `wc -l`-Check belegt.

Diese Punkte sind dem Implementer-Workflow / Adversary-Verification-Schritt vorbehalten. Aus rein externer Black-Box-Perspektive: **AMBIGUOUS** — kein Bruch festgestellt, aber wesentliche AC nicht extern abdeckbar.
