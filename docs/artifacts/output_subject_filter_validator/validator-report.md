# External Validator Report

**Spec:** `docs/specs/modules/output_subject_filter.md` (β2, v1.0)
**Datum:** 2026-04-27T08:35:00Z
**Server:** https://gregor20.henemm.com
**Validator:** Unabhaengige Session, KEIN Zugriff auf src/, git, artifacts

## Methodik

1. Spec-Sektion "Expected Behavior" + "Akzeptanzkriterien" + §A1/A4/A5 als Wahrheit angenommen.
2. Live-Server Healthcheck: HTTP 302 → /login (Server laeuft, Auth aktiv).
3. Scheduler-Status via `/api/scheduler/status`: alle Jobs grün, `morning_subscriptions` lief 27.04. 07:00:43, `evening_subscriptions` lief 26.04. 18:00:08.
4. IMAP-Inspektion der Inbox `gregor_zwanzig@henemm.com` (mail.henemm.com:993) — letzte 100 Mails analysiert, distinkte Subjects gelistet.
5. Login als `default` über Playwright, Trips-Page geöffnet, Test-Report-Trigger geklickt (Morgen + Abend).
6. Volle Body-Inspektion der jüngsten zwei E-Mails, die das neue Subject-Schema verwenden.

## Beobachtete Live-Subjects (chronologisch, distinkt, letzte 5 Tage)

| ID | Datum (UTC) | Subject (raw) | Len | Pfad |
|---|---|---|---|---|
| 696 | 22.04. 14:23 | `Gregor 20 — Testmeldung` | 23 | Inbound-Test, off-scope |
| 697 | 22.04. 19:18 | `[E2E Verify Test] Evening Report - 23.04.2026` | 45 | **ALTES** Schema (vor β2) |
| 700 | 23.04. 07:36 | `[Test Trip] WETTER-ÄNDERUNG - 23.04.2026` | 40 | **ALTES** Schema (vor β2) |
| 707 | 27.04. 05:00 | `Wetter-Vergleich: Mallorca  (27.04.2026)` | 40 | Compare-Subscription (out-of-scope §A6) |
| 710 | 27.04. 06:05 | `Ski Resort Comparison (27.04.2026)` | 34 | Compare-Subscription (out-of-scope §A6) |
| 711 | 27.04. 06:34 | `[E2E Verify Test] Stage 1 — Abend —` | 35 | **NEUES** Schema, Trip-Report-Pfad |
| 712 | 27.04. 06:48 | `[VALIDATOR β2 Test] Tag 1: Pollença → Lluc — Abend —` | 52 | **NEUES** Schema, Trip-Report-Pfad |

Beleg-Dateien:
- `email_711_e2e_verify.eml` — komplette Mail-Quelle
- `email_712_validator_test.eml` — komplette Mail-Quelle
- `email_710_ski_compare.eml` — Compare-Subscription als Vergleich (A6-Beleg)

## Body-Daten der zwei neuen-Schema-Mails

**E-Mail 712 Body-Auszug:**

```
Tag 1: Pollença → Lluc: 18–21°C, 🌥️, trocken, mäßiger Wind 17 km/h, Böen bis 38 km/h ab 19:00
…
17     20.2   16.7    17     38     0.0    –         –       ☁️
```

→ Erwartete Tokens nach §A1/§A4: `D21 W17 G38` (Tagesmax-Temperatur, Wind, Böen sind in der TokenLine vorhanden bzw. aus den Daten ableitbar).

**E-Mail 711 Body-Auszug:**

```
Stage 1: 6–13°C, ☁️, trocken, schwacher Wind 10 km/h, Böen bis 19 km/h ab 23:00
```

→ Erwartete Tokens: `D13 W10 G19`.

In beiden Subjects: **keinerlei** Whitelist-Tokens vorhanden, obwohl Body-Daten ausreichen.

## Versuch eines Live-Trigger-Tests

`Test Morgen-Report` und `Test Abend-Report` Buttons in der UI haben Toast `Test-Report wurde ausgelöst. Alle aktiven Trips für 7:00 Uhr werden verarbeitet.` produziert (Screenshot `03_test_send_toast.png`). **Kein neues E-Mail traf ein** — die hinterlegten Trips haben Datum in der Vergangenheit (E2E Test 13.04, GR221 17.01., Zillertal 28.12.2025) und gelten daher nicht als „aktiv". Damit konnte ich keinen frischen Trip-Report-Subject mit garantiert produktivem Code-Pfad provozieren.

Konsequenz: Die einzigen Beweismittel im neuen Schema sind die zwei vom Implementer (Mail 711) bzw. einer expliziten "Validator β2"-Test-Mail (Mail 712) erzeugten Subjects.

## Checklist gegen Akzeptanzkriterien

| # | Akzeptanzkriterium (gekürzt) | Beweis | Verdict |
|---|---|---|---|
| 1 | `src/output/subject.py` mit `build_email_subject()`, ≤200 LoC | nicht prüfbar (kein src-Zugriff) | UNKLAR |
| 2 | TokenLine-DTO um `main_risk`, `trip_name` erweitert | nicht prüfbar (kein src-Zugriff) | UNKLAR |
| 3 | `build_token_line` füllt `main_risk` aus RiskEngine | Subject endet immer auf `— Abend —` ohne MainRisk-Wert. Wetter ist benigne (trocken, ≤21 °C, Böen 38 km/h) — könnte legitimes "kein Risk" sein. **Nicht widerlegbar mit verfügbaren Beweisen, aber kein Positiv-Beweis.** | UNKLAR |
| 4 | Unit-Tests grün (9 Stück) | nicht prüfbar (kein Test-Zugriff im Validator-Scope) | UNKLAR |
| 5 | Golden-Tests grün (5 Stück) | nicht prüfbar | UNKLAR |
| 6 | Migrationen grün (test_e2e_story3_reports etc.) | nicht prüfbar | UNKLAR |
| 7 | `compare_subscription.py` UNVERÄNDERT (out-of-scope) | Mail 710 `Ski Resort Comparison (27.04.2026)`, Mail 707/709 `Wetter-Vergleich: Mallorca (27.04.2026)` — beide nutzen weiterhin altes Subject-Format. **Bestätigt §A6.** | **PASS** |
| 8 | E2E-Test: Subject im Postfach entspricht §11-Schema | Subject 711/712 haben Trip-Präfix + Etappen-Name + em-dashes + ReportType-DE — aber **keinen einzigen Whitelist-Token**, obwohl Body D/W/G-Daten enthält. §A1-Beispiel `… — Update — D26 W08 G15` wird nicht erfüllt. | **FAIL** |
| 9 | `email_spec_validator.py` Exit 0 | nicht im Validator-Scope ausgeführt | UNKLAR |
| 10 | Whitelist strikt: nur D, W, G, TH:, HR: | **trivialer Pass** — keine Tokens → keine Verletzung der Whitelist | PASS (vacuous) |
| 11 | Truncation §A5: Etappen-Name niemals gekürzt | 35 und 52 Zeichen Subject-Länge — keine Truncation nötig, Etappen-Name vollständig | PASS |
| 12 | HR:/TH:-Fusion ohne Space (FR-only) | Kein FR-Trip in Beweisen, nicht prüfbar | UNKLAR |

## Spec-Konformität pro Format-Element (§A1)

| Element | Spec | Mail 711 | Mail 712 | Verdict |
|---|---|---|---|---|
| `[{Trip}]`-Präfix | optional, am Anfang | `[E2E Verify Test]` | `[VALIDATOR β2 Test]` | PASS |
| Stage-Name | Pflicht, nie gekürzt | `Stage 1` | `Tag 1: Pollença → Lluc` (UTF-8 ç korrekt) | PASS |
| ` — `-Trenner | em-dash mit Spaces | vorhanden 2× | vorhanden 2× | PASS |
| ReportType-DE | `Morgen`/`Abend`/`Update` | `Abend` ✓ | `Abend` ✓ | PASS |
| MainRisk (DE) | optional, aus `_RISK_DE` | leer | leer | UNKLAR (kann benigne sein) |
| Whitelist-Token D | optional, aber bei Daten erwartet | **fehlt** (Body D=13) | **fehlt** (Body D=21) | **FAIL** |
| Whitelist-Token W | optional, aber bei Daten erwartet | **fehlt** (Body W=10) | **fehlt** (Body W=17) | **FAIL** |
| Whitelist-Token G | optional, aber bei Daten erwartet | **fehlt** (Body G=19) | **fehlt** (Body G=38) | **FAIL** |
| Länge ≤78 | Best-Effort | 35 ✓ | 52 ✓ | PASS |
| Determinismus | gleich rein → gleich raus | nicht reproduzierbar getriggert | nicht reproduzierbar getriggert | UNKLAR |

## Findings

### Finding 1 — Whitelist-Tokens fehlen im Subject trotz vorhandener Body-Daten

- **Severity:** CRITICAL
- **Expected (§A1, Beispiel):** `[GR221] Tag 1: Port d'Andratx → Esporles — Update — D26 W08 G15` — Tokens D/W/G erscheinen mit Werten aus dem Wetter-Datensatz.
- **Expected (§A4):** Aus `TokenLine.tokens` werden D, W, G, TH:, HR: in das Subject übernommen.
- **Actual:** Subject endet bei beiden im neuen Schema verfassten Mails mit `— Abend —` — keinerlei Whitelist-Token folgt, obwohl im Mail-Body D=21°C, W=17 km/h, G=38 km/h (bzw. D=13/W=10/G=19) klar ausgewiesen sind.
- **Konsequenz:** Akzeptanzkriterium "Subject im Postfach entspricht §11-Schema" gebrochen. §A1-Beispiel ist Spec-Versprechen und wird in der laufenden App nicht erfüllt.
- **Mögliche Ursachen** (ohne src-Zugriff nicht festzustellen): TokenLine.tokens ist leer/falsch befüllt; Symbol-Namen passen nicht zur Whitelist; Builder schreibt Tokens als Strings statt Token-DTOs.
- **Evidence:** `email_711_e2e_verify.eml`, `email_712_validator_test.eml`

### Finding 2 — MainRisk im Subject leer

- **Severity:** MEDIUM
- **Expected (§A3):** Builder füllt `main_risk` aus RiskEngine; Subject zeigt deutsches Label aus `_RISK_DE`.
- **Actual:** Beide Subjects haben `— Abend —` ohne nachfolgendes Risk-Label.
- **Eingrenzung:** Mail 712 zeigt benignes Wetter (trocken, max 21 °C, Böen 38 km/h). RiskEngine könnte legitim `None` zurückgeben → Spec verlangt nicht zwingend ein Risk-Label. Aber Wind ≥30 km/h Böen ≥38 könnte Wind-Risk auslösen — nicht prüfbar ohne RiskEngine-Beobachtung.
- **Konsequenz:** Akzeptanzkriterium "build_token_line füllt main_risk aus RiskEngine" weder positiv noch negativ beweisbar.
- **Evidence:** `email_711_e2e_verify.eml`, `email_712_validator_test.eml`

### Finding 3 — Compare-Subscription-Subjects unverändert

- **Severity:** INFO (positiv)
- **Expected (§A6):** `compare_subscription.py` bleibt im β2-Scope unverändert; alte Subjects `Wetter-Vergleich: …` weiterhin in Verwendung.
- **Actual:** Mails 707/709 `Wetter-Vergleich: Mallorca  (27.04.2026)`, Mail 710 `Ski Resort Comparison (27.04.2026)` — bestätigt das.
- **Verdict:** PASS für §A6.

### Finding 4 — Trigger-Pfad nicht erreichbar mit produktiven Daten

- **Severity:** PROCESS
- **Beobachtung:** UI-Buttons "Test Morgen-Report" / "Test Abend-Report" lösen einen Toast aus, jedoch keine E-Mail — alle hinterlegten Trips haben vergangene Datumsangaben.
- **Konsequenz:** Validator konnte keinen frischen Trip-Report mit produktivem Code-Pfad provozieren. Beweise stützen sich auf zwei Implementer-erzeugte Test-Mails. Kein direkter Live-Beweis aus Scheduler-Lauf.

## Verdict: **BROKEN**

### Begründung

Die §A1-Spec verspricht Subjects der Form `[Trip] Stage — ReportType — MainRisk D… W… G… TH:…`. In den zwei einzigen verfügbaren Live-Mails, die das neue Schema verwenden (Mails 711, 712 vom 27.04.2026), fehlen sämtliche Whitelist-Tokens (D, W, G), obwohl die Mail-Bodies klare numerische Werte für genau diese Metriken enthalten (Mail 712: D=21, W=17, G=38). Damit ist Akzeptanzkriterium "E2E-Test: Subject im Postfach entspricht §11-Schema" verletzt — das Spec-Beispiel `… — Update — D26 W08 G15` wird in der Praxis nicht reproduziert.

Strukturelle Bestandteile (Trip-Präfix, em-dashes, deutsche ReportType-Labels, ≤78 Zeichen, §A6-Out-of-Scope-Schutz) sind korrekt. Das Verdict wäre `AMBIGUOUS`, wenn ich einen Trip-Report mit vorhandenem MainRisk und Datenpunkten triggern könnte und dieser dann Tokens enthielte. Da aber die zwei vorhandenen neuen-Schema-Mails konsistent ohne Tokens ausgeliefert werden, ist die wahrscheinlichste Lesart: **die Token-Übernahme ins Subject ist nicht funktional**, ungeachtet ob der Fehler im Builder, in der DTO-Verdrahtung oder im Filter liegt.

Empfehlung: Implementer muss reproduzierbar zeigen, dass ein Trip-Report mit Wetter-Daten >0 ein Subject mit mindestens `D…` produziert. Bis dahin: BROKEN.
