# External Validator Report

**Spec:** `docs/specs/modules/output_subject_filter.md`
**Datum:** 2026-04-27T06:14:00Z
**Server:** https://gregor20.henemm.com
**Validator:** External (independent von Implementierer-Session)

## Methode

1. Spec gelesen — nur Sektion "Expected Behavior" und "Akzeptanzkriterien"
2. Live-Server geprüft (Login via Playwright, IMAP-Inspektion via Stalwart)
3. Inbox `gregor_zwanzig@henemm.com` (709→710 Mails) inspiziert: Subject-Format der zuletzt gesendeten Trip-Reports
4. Versucht, frischen `Test Morgen-Report` über die UI auszulösen (Knopf an `/trips`-Tabelle)

**KEIN** Zugriff auf `src/`, `git log`, `docs/artifacts/<implementer>` oder `.claude/workflow_state.json`.

## Spec-Erwartung (kanonisch)

Aus Spec §A1 / Akzeptanzkriterien:

```
[{Trip}] {Etappen-Name} — {ReportType-DE} — {MainRisk} {D-Token} {W-Token} {G-Token} {TH:-Token}
```

Beispiele aus Spec:
- `[GR221] Tag 3: Valldemossa → Sóller — Morgen — Thunder D24 W15 G30 TH:M`
- `[GR221] Tag 1: Port d'Andratx → Esporles — Update — D26 W08 G15`

ReportType-Mapping: `morning → Morgen`, `evening → Abend`, `update → Update` (Spec §A2).

Risk-Labels deutsch: `Thunder → Gewitter`, `Storm → Sturm`, etc. (Spec §A3).

## Beobachtete Ist-Realität

Inhalt der vier zuletzt gesendeten Trip-Reports (IMAP, full headers via Stalwart `mail.henemm.com:993`, Box `gregor_zwanzig`):

| UID | Datum | Subject | Länge |
|---|---|---|---|
| 674 | Sun, 26 Apr 2026 07:16:19 +0000 | `[E2E Verify Test] Evening Report - 27.04.2026` | 45 |
| 654 | Sat, 25 Apr 2026 19:45:21 +0000 | `[Test Trip] WETTER-ÄNDERUNG - 25.04.2026` | 40 |
| 645 | Thu, 23 Apr 2026 12:39:50 +0000 | `[E2E Verify Test] Evening Report - 24.04.2026` | 45 |
| 626 | Thu, 23 Apr 2026 07:36:34 +0000 | `[Test Trip] WETTER-ÄNDERUNG - 23.04.2026` | 40 |

(Histogramm-Querschnitt: 28 Trip-Report-Subjects der letzten Wochen — alle im selben Alt-Format. Subjects wie `[GR221 Mallorca] WETTER-ÄNDERUNG - 05.04.2026` und `[E2E Story3 Stubai] Morning Report - 14.04.2026` belegen das Muster über mehrere Tage.)

## Checklist (jeder Akzeptanzkriterium-Punkt aus Spec)

| # | Akzeptanzkriterium | Beweis | Verdict |
|---|---|---|---|
| 1 | E2E-Test: Subject im Postfach entspricht §11-Schema | Live-Mailbox: alle 4 jüngsten Trip-Reports verwenden Alt-Schema (`Morning Report`/`Evening Report`/`WETTER-ÄNDERUNG`) — KEIN §11-konformes Subject vorhanden | **FAIL** |
| 2 | ReportType-Mapping `morning → Morgen`, `evening → Abend`, `update → Update` | Mailbox enthält ausschließlich `Morning Report`, `Evening Report`, `WETTER-ÄNDERUNG`. Wörter `Morgen`/`Abend`/`Update` kommen in keinem Trip-Report-Subject vor (Grep über alle 709 Subjects). | **FAIL** |
| 3 | MainRisk im Subject (deutsche Labels: `Gewitter`, `Sturm`, `Hitze`, …) | Keine deutschen Risk-Labels in irgendeinem Subject in der Mailbox. | **FAIL** |
| 4 | Whitelist-Wetter-Tokens (D, W, G, TH:, HR:) im Subject | Kein einziges D/W/G/TH:/HR:-Token in irgendeinem der 709 Subjects. | **FAIL** |
| 5 | Best-Effort ≤ 78 Zeichen | N/A — Format insgesamt nicht implementiert. (Bestehende Subjects sind 40–45 Zeichen.) | **N/A (Format fehlt)** |
| 6 | HR:/TH:-Vigilance-Fusion ohne Space (FR-only) | Kein HR:/TH:-Token im Subject vorhanden — nicht prüfbar. | **N/A (Format fehlt)** |
| 7 | Truncation §A5: Etappen-Name niemals gekürzt | Etappen-Name ist im aktuellen Subject **nicht enthalten** — nur `[Trip] {ReportType} - DD.MM.YYYY`. Etappe selbst fehlt komplett. | **FAIL** |
| 8 | `compare_subscription.py` UNVERÄNDERT (out-of-scope) | Subscription-Subjects in Mailbox lauten weiterhin `Wetter-Vergleich: Mallorca (DD.MM.YYYY)` — wie vor β2. | **PASS (out-of-scope)** |
| 9 | Determinismus / Side-effect-frei | Nicht prüfbar ohne Implementation; Subjects sind ohnehin nicht im Soll-Format. | **N/A** |

## Findings

### F1 (CRITICAL): Subject-Filter ist in Produktion NICHT deployed

- **Severity:** CRITICAL
- **Expected:** `[Trip] {Etappe} — {Morgen/Abend/Update} — {Risk-DE} {D...W...G...}` (Spec §A1)
- **Actual:** `[Trip] {Morning Report|Evening Report|WETTER-ÄNDERUNG} - DD.MM.YYYY` (Alt-Format aus `_generate_subject()`, das Spec §A1 explizit ersetzen will)
- **Evidence:** IMAP UID 674 (`Sun, 26 Apr 2026 07:16:19 +0000` — gestern, nach Spec-Erstelldatum 2026-04-26 — Subject `[E2E Verify Test] Evening Report - 27.04.2026`). Weitere drei jüngste Trip-Reports identisches Alt-Schema. Histogramm über 709 Mails: kein einziges §11-konformes Subject vorhanden.
- **Implication:** Die in Spec §11 / §A1-A5 definierte zentrale Funktion `build_email_subject()` ist entweder (a) noch nicht implementiert oder (b) nicht in den Aufrufpfad `trip_report._generate_subject()` migriert (Spec "Migration" listet diese Migration explizit als β2-Pflicht auf).

### F2 (HIGH): ReportType-Übersetzung fehlt komplett

- **Severity:** HIGH
- **Expected:** `Morgen` / `Abend` / `Update` (Spec §A2)
- **Actual:** `Morning Report` / `Evening Report` / `WETTER-ÄNDERUNG`
- **Evidence:** UIDs 674, 654, 645, 626 — siehe Tabelle oben.

### F3 (HIGH): Etappen-Name fehlt im Subject

- **Severity:** HIGH
- **Expected:** Etappen-Name ist Hauptdiskriminator (Spec §A1 / §A5: "Etappen-Name niemals gekürzt")
- **Actual:** Subject enthält nur Trip-Präfix + ReportType + Datum. Beispiel: `[GR221 Mallorca] WETTER-ÄNDERUNG - 05.04.2026` — Etappe `Tag 1: von Valldemossa nach Deià` (aus Trip-JSON sichtbar in UI) erscheint nirgends.
- **Evidence:** Alle 28 Trip-Report-Subjects in der Mailbox.

### F4 (HIGH): Wetter-Tokens und MainRisk fehlen

- **Severity:** HIGH
- **Expected:** D/W/G + optional TH:/HR: + MainRisk-Label (Spec §A1, §A3, §A4)
- **Actual:** Subject enthält keine Wetter-Information.
- **Evidence:** Grep über 709 Subjects findet keine D-/W-/G-/TH:-/HR:-Tokens und keine deutschen Risk-Labels.

### F5 (INFO): Approval-Status der Spec ist offen

- **Severity:** INFO
- **Beobachtung:** `docs/specs/modules/output_subject_filter.md` Frontmatter `status: draft`, Approval-Checkbox unangehakt. Das erklärt, warum keine Implementation vorliegt — entspricht aber nicht dem Validator-Auftrag (User hat zur Validierung aufgefordert). Verdict basiert ausschließlich auf Ist-vs-Soll.

## Aktiv versuchte Widerlegung

1. **Test Morgen-Report über UI ausgelöst** (Trip-Tabelle `/trips`, Knopf `[title="Test Morgen-Report"]` an Reihe `GR221 Mallorca`). Toast: "Test-Report — Morgen Test-Report (Morning) wurde ausgelöst. Alle aktiven Trips für 7:00 Uhr werden verarbeitet." Inbox-Polling über 4 Minuten: keine neue Trip-Report-Mail eingelaufen (vermutlich keine "aktiven" Trips → alle Trip-Daten in der Vergangenheit, GR221 morning_time=06:00, Steffi=07:00 aber Datum 2025-12-28). Damit nicht beweisbar, ob ein hypothetisches Live-Subject das neue oder alte Format hätte. Bezugsmenge: die zuletzt **tatsächlich** gesendeten Trip-Reports (UID 674 ff.) — alle Alt-Format.
2. **E2E-Hook `email --send-from-ui`** ausgelöst — Resultat: `Ski Resort Comparison (27.04.2026)` (out-of-scope per A6, kein Trip-Report).

## Verdict: **BROKEN**

### Begründung

Spec definiert ein neues Subject-Format mit Etappen-Name, deutschen ReportType-Labels (`Morgen`/`Abend`/`Update`), deutschem MainRisk-Label und Wetter-Tokens (D/W/G/TH:/HR:). Auf der laufenden Produktion (`https://gregor20.henemm.com`) zeigt jedes der vier zuletzt versendeten Trip-Report-Subjects (jüngstes: gestern 26.04.2026 07:16 UTC, also nach Spec-Erstelldatum) das in der Spec explizit als "alt" und "trivial" beschriebene Format `[Trip] {Morning Report|Evening Report|WETTER-ÄNDERUNG} - DD.MM.YYYY`. Vier von sieben prüfbaren Akzeptanzkriterien sind FAIL, drei nicht prüfbar weil das Format insgesamt fehlt. Damit ist das in der Spec dokumentierte Verhalten in der laufenden App **nicht** beobachtbar — Verdict: **BROKEN**.

Die einzige PASS-Beobachtung ist negativ definiert (A6: `compare_subscription.py` ist unverändert) und beweist nur, dass der out-of-scope Pfad nicht versehentlich angefasst wurde — sie kann den Verdict nicht retten.

## Beweis-Artefakte

- `screenshots/04_post_login.png` — Startseite nach Login (zeigt Trip-Karten)
- `screenshots/05_gr221_trip.png` — `/trips`-Tabelle (zeigt Aktion-Icons inkl. "Test Morgen-Report")
- `screenshots/09_trips_page.png` — `/trips` mit allen vier Trips
- `screenshots/10_after_morgen.png` — Toast-Bestätigung nach `Test Morgen-Report`-Klick
- IMAP-Histogramm aller 709 Mails (siehe Beobachtungsabschnitt)

## Empfehlung an Implementierer-Session

Nicht mein Auftrag — aber für Vollständigkeit: vor erneutem Validierungs-Run muss
1. die Spec approved sein (`Approval: [x]`)
2. `src/output/subject.py::build_email_subject()` existieren
3. `src/formatters/trip_report.py::_generate_subject()` auf die neue Funktion migriert sein
4. Production deployed und systemd-restartet sein
5. Mindestens ein neuer Trip-Report im Postfach §11-konform erscheinen
