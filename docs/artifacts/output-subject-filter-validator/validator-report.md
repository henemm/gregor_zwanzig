# External Validator Report

**Spec:** `docs/specs/modules/output_subject_filter.md`
**Datum:** 2026-04-27T13:30+02:00
**Server:** https://gregor20.henemm.com
**Validator-Methode:** IMAP-Pull realer App-Outputs (`mail.henemm.com:993`, Postfach `gregor_zwanzig`)

## Methodik

Der Validator hat keinen Zugriff auf `src/`, Git oder Workflow-State. Geprüft wird ausschließlich:

1. Reale Subject-Zeilen im Postfach `gregor_zwanzig@henemm.com` der laufenden App (IMAP)
2. Web-UI-Zustand (SvelteKit) auf https://gregor20.henemm.com
3. Spec `output_subject_filter.md` als einzige Soll-Quelle

**Wichtige Limitation:** Es war kein User-getriggerter Trip-Report-Versand möglich (keine UI-Send-Buttons im SvelteKit-Frontend; Scheduler `trip_reports_hourly` läuft stündlich, sendet aber nur für heutige Etappen — alle vorhandenen Trips haben Etappen in der Vergangenheit). Der Validator stützt sich daher auf die letzten produzierten Mails der laufenden App (Mails 701-713 vom 27.04.2026).

## Beobachtete Mails (27.04.2026)

| Mail-ID | Zeit (UTC) | Subject | Klassifikation |
|---|---|---|---|
| 701 | 05:00 | `Wetter-Vergleich: Mallorca  (27.04.2026)` | Subscription-Compare (out-of-scope §A6) |
| 702-708 | 05:53-05:55 | `Gregor 20 — Testmeldung` (×4) | Channel-Test (kein Trip-Report) |
| 703,705,707,709 | 05:54-05:56 | `Wetter-Vergleich: Mallorca  (27.04.2026)` (×4) | Subscription-Compare (out-of-scope §A6) |
| 710 | 06:05 | `Ski Resort Comparison (27.04.2026)` | Subscription-Compare (out-of-scope §A6) |
| 711 | 06:34 | `[E2E Verify Test] Stage 1 — Abend —` | Trip-Report (älterer Stand) |
| 712 | 06:48 | `[VALIDATOR β2 Test] Tag 1: Pollença → Lluc — Abend —` | Trip-Report (älterer Stand) |
| **713** | **11:18** | **`[POSTFIX Validator Test] Tag 1: Pollença → Lluc — Abend — D21 W13 G27`** | **Trip-Report (aktueller Stand)** |

Mail 713 ist der **letzte** produzierte Trip-Report (vor 5 Stunden zur Validierungszeit) und damit der maßgebliche Beleg für das aktuell deployte Verhalten. Die "POSTFIX"-Markierung im Trip-Namen lässt auf einen Hot-Fix nach Mails 711/712 schließen.

## Checklist gegen "Expected Behavior" (Spec Z. 226-231)

| # | Expected Behavior | Beweis | Verdict |
|---|---|---|---|
| 1 | Output ist `str` ≤ 78 Zeichen | Mail 713: 69 Zeichen (`imap_mail_713.txt`) | **PASS** |
| 2 | §11-konformes Subject-Format | Mail 713 matched Schema `[{Trip}] {Stage} — {ReportType-DE} — {Tokens}` | **PASS** |
| 3 | Pure function, keine Side-Effects | Nicht ohne `src/`-Zugriff verifizierbar | **UNKLAR** |
| 4 | Determinismus (gleiche TokenLine → gleiches Subject) | Nicht ohne wiederholten Trigger verifizierbar | **UNKLAR** |

## Checklist gegen Akzeptanzkriterien (Spec Z. 233-246)

| # | Kriterium | Beweis | Verdict |
|---|---|---|---|
| A1 | `src/output/subject.py` existiert ≤200 LoC | `src/`-Zugriff verboten | **UNKLAR** |
| A2 | TokenLine um `main_risk`/`trip_name` erweitert | indirekt: Mail 713 nutzt `trip_name` (Präfix) → erweitert ✓ | **PASS (indirekt)** |
| A3 | `build_token_line` füllt `main_risk` | Mail 713 ohne MainRisk → entweder None (legitim) oder ungefüllt; nicht unterscheidbar | **UNKLAR** |
| A4 | 9 Unit-Tests grün | `src/`/Tests-Ausführung nicht im Validator-Scope | **UNKLAR** |
| A5 | 5 Golden-Tests grün | Wie A4 | **UNKLAR** |
| A6 | Migrierte Tests grün | Wie A4 | **UNKLAR** |
| A7 | `compare_subscription` UNVERÄNDERT | Mails 701, 710 zeigen weiterhin altes Format `Wetter-Vergleich: Mallorca …` und `Ski Resort Comparison …` ✓ | **PASS** |
| A8 | E2E-Test: Subject im Postfach §11-Schema | Mail 713 §11-konform | **PASS** |
| A9 | `email_spec_validator.py` Exit 0 | Nicht ausgeführt — validiert HTML-Body, nicht Subject | **N/A** |
| A10 | Whitelist strikt: nur D, W, G, TH:, HR: | Mail 713: nur `D21 W13 G27` — keine `N/R/PR/TH+/Z:/M:/SN` | **PASS** |
| A11 | Truncation §A5: Etappen-Name niemals gekürzt | Mail 713 (69 Zeichen) braucht keine Truncation; `Tag 1: Pollença → Lluc` voll | **PASS (trivial)** |
| A12 | HR:/TH:-Fusion ohne Space (FR-only) | Kein FR-Trip in beobachteten Mails | **UNKLAR** |

## Detail-Analyse Mail 713

**Subject:** `[POSTFIX Validator Test] Tag 1: Pollença → Lluc — Abend — D21 W13 G27` (69 Zeichen)

Zerlegung gegen Schema §A1 `[{Trip}] {Etappen-Name} — {ReportType-DE} — {MainRisk} {D-Token} {W-Token} {G-Token} {TH:-Token}`:

| Element | Erwartung | Beobachtet | Verdict |
|---|---|---|---|
| Trip-Präfix | `[{trip_name}]` | `[POSTFIX Validator Test]` | ✓ |
| Etappen-Name | unverstümmelt | `Tag 1: Pollença → Lluc` | ✓ |
| em-dash Separator | ` — ` | ` — ` | ✓ |
| ReportType-DE | `Morgen`/`Abend`/`Update` | `Abend` (statt englisch "Evening") | ✓ |
| em-dash Separator | ` — ` | ` — ` | ✓ |
| MainRisk (DE) | optional, deutsch | (fehlt — entspricht Spec-Beispiel #3 für `main_risk=None`) | ✓ (Annahme None) |
| D-Token | optional | `D21` | ✓ |
| W-Token | optional | `W13` | ✓ |
| G-Token | optional | `G27` | ✓ |
| TH:/HR: | optional, FR-only | nicht vorhanden (kein FR-Vigilance-Bereich) | ✓ |
| Reihenfolge D→W→G→TH:/HR: | strikt | D, W, G in korrekter Reihenfolge | ✓ |
| Länge ≤ 78 | Best-Effort | 69 Zeichen | ✓ |

**Plausibilitäts-Check Body vs. Subject (Mail 713):**
- Body: "18–21°C, ☁️, trocken, schwacher Wind 13 km/h, Böen bis 32 km/h ab 16:00"
- Subject `D21`: matched Body-Max 21°C ✓
- Subject `W13`: matched Body "Wind 13 km/h" ✓
- Subject `G27`: Body sagt "Böen bis 32 km/h" — **leichte Diskrepanz** (G27 vs 32 km/h). Nicht im Subject-Filter-Scope (TokenLine-Input-Frage), aber dokumentiert.

## Findings

### F-1 — §11-Schema im aktuellen Output erfüllt

- **Severity:** INFO
- **Expected:** §11-Schema mit Trip-Präfix, Etappen-Name, ReportType-DE, optionalem MainRisk, Whitelist-Tokens, ≤ 78 Zeichen
- **Actual:** Mail 713 erfüllt Schema vollständig (mit `main_risk=None`-Variante, vgl. Spec-Beispiel #3)
- **Evidence:** `imap_mail_713.txt`

### F-2 — Subscription-Subjects unverändert (out-of-scope §A6)

- **Severity:** INFO
- **Expected:** Subscriptions weiterhin im alten Format `Wetter-Vergleich: {name} ({datum})`
- **Actual:** Mails 701, 703, 705, 707, 709 zeigen `Wetter-Vergleich: Mallorca (27.04.2026)`; Mail 710 zeigt `Ski Resort Comparison (27.04.2026)` — keine Migration auf §11
- **Evidence:** `imap_mail_701.txt`, `imap_mail_710.txt`

### F-3 — Historische Trip-Reports zeigen Edge-Case-Schwäche (mutmasslich gefixt)

- **Severity:** MEDIUM (historisch); Aktualität unklar
- **Expected:** Subject darf nicht auf bare em-dash enden, wenn weder MainRisk noch Tokens vorhanden sind
- **Actual:** Mails 711, 712 enden auf `… — Abend —` (trailing em-dash, weder MainRisk noch Tokens). Mail 713 (5 Stunden später, Trip-Name "POSTFIX") zeigt korrektes Verhalten — der Bug wurde offenbar noch am 27.04.2026 gefixt.
- **Risiko:** Da kein frischer Trigger mit `main_risk=None` UND `tokens=()` möglich war, kann nicht bewiesen werden, dass der "no-tokens, no-risk"-Edge-Case in der aktuell deployten Version sauber ist. Mails 711/712 belegen aber, dass dieser Pfad in der App vorkommen kann.
- **Evidence:** `imap_mail_711.txt`, `imap_mail_712.txt` (gegen `imap_mail_713.txt`)

### F-4 — Plausibilitäts-Diskrepanz Subject-Tokens vs Body (außerhalb Subject-Filter-Scope)

- **Severity:** LOW
- **Expected:** `G`-Token im Subject = Tagesmaximum Böen (Konvention TokenLine.builder)
- **Actual:** Mail 713: Subject `G27`, Body "Böen bis 32 km/h ab 16:00" — Diskrepanz 5 km/h
- **Hinweis:** Das ist ein TokenLine-Builder-Issue (Out-of-Scope für `output_subject_filter`), kein Subject-Filter-Bug. Der Filter reicht durch was er bekommt.
- **Evidence:** `imap_mail_713.txt`

### F-5 — UNKLAR: Determinismus, Pure-Function, Implementierungs-Details

- **Severity:** INFO
- **Begründung:** Validator-Isolation (kein `src/`-Zugriff, kein git, kein Test-Run) verhindert direkte Verifikation von Pure-Function-Charakter, Determinismus, LoC-Limit, Test-Suite-Status. Die Spec-Anforderungen mit Code-Inspection-Charakter sind aus dem Black-Box-Output nicht ableitbar.

## Verdict: AMBIGUOUS

### Begründung

**Was bewiesen ist (PASS):**
- Mail 713 erfüllt §11-Subject-Schema vollständig — Trip-Präfix, Etappen-Name, deutsches ReportType-Label `Abend`, korrekt eingehaltene Whitelist (nur `D`, `W`, `G`), D→W→G-Reihenfolge, Länge 69 Zeichen unter 78.
- Subscription-Subjects sind unverändert (§A6 out-of-scope respektiert).
- Trip-Präfix und Etappen-Name werden gefüllt → TokenLine-Erweiterung um `trip_name` ist erfolgt.

**Was nicht bewiesen ist (UNKLAR):**
- **Edge-Case "keine Tokens, kein MainRisk":** Mails 711/712 zeigten am Vormittag des 27.04.2026 ein gebrochenes Subject (`… — Abend —` mit trailing em-dash). Mail 713 (POSTFIX) ist korrekt, hatte aber Tokens. Es konnte kein Beweis erzeugt werden, dass die aktuelle Implementierung den No-Tokens-Pfad sauber rendert (z.B. `[Trip] Stage — Abend` ohne dangling separator).
- **HR:/TH:-Vigilance-Fusion (FR-only):** kein FR-Trip in den beobachteten Mails → nicht testbar im aktuellen Postfach.
- **MainRisk-Übersetzung Englisch→Deutsch:** kein Risk-Label in Mail 713 → `_RISK_DE`-Mapping nicht beobachtbar.
- **Truncation auf 78 Zeichen:** kein langes Subject in den beobachteten Mails → Truncation-Algorithmus §A5 nicht stress-getestet.
- **Spec-Implementation-Details (LoC, Pure-Function, Determinismus, Tests):** Validator-Isolation verhindert Code-/Test-Inspektion.

**Warum AMBIGUOUS, nicht VERIFIED:**
Der einzige aktuelle Beweis (Mail 713) deckt nur den glücklichen Pfad ab (alle Felder belegt, kurzes Subject). Mehrere durch die Spec definierte Pfade (No-Tokens-Edge-Case, Vigilance-Fusion, Truncation, Risk-Übersetzung) bleiben unbelegt. Die historischen Mails 711/712 zeigen **eindeutig**, dass der Code zwischen Mails 712 und 713 kurzfristig gefixt wurde — dies erhöht das Risiko, dass weitere Pfade ebenfalls noch unentdeckte Bugs haben.

**Empfehlung an User/Implementierer (kein Validator-Auftrag):**
- Frischer E2E-Test mit drei Profilen: (a) Trip ohne Risk und ohne Wetter-Tokens, (b) FR-Trip mit HR:/TH:-Vigilance, (c) extrem langer Etappen-Name (> 78 Zeichen) zur Truncation-Verifikation. Dann ist VERIFIED erreichbar.

## Evidence-Dateien

- `imap_mail_701.txt` — Subscription-Compare (out-of-scope §A6)
- `imap_mail_710.txt` — Subscription-Compare (out-of-scope §A6)
- `imap_mail_711.txt` — Trip-Report (älterer Stand, gebrochen)
- `imap_mail_712.txt` — Trip-Report (älterer Stand, gebrochen)
- `imap_mail_713.txt` — **Trip-Report (aktueller Stand, §11-konform)**
- `01_login.png`, `02_trip_detail.png`, `03_account.png`, `04_home.png` — UI-Screenshots (zeigen, dass kein Trip-Report-Trigger in der UI verfügbar ist)
