---
entity_id: issue_130_93_107_ui_polish
type: bugfix
created: 2026-05-19
updated: 2026-05-19
status: draft
version: "1.0"
tags: [bugfix, ui-polish, alert-mail, umlaute, dead-code, issue-130, issue-93, issue-107]
---

<!-- Issues #130, #93, #107 — UI-Polish: Etappenname in Alert-Mail, Deutsche Umlaute im Frontend, TripForm.svelte löschen -->

# Issues #130 / #93 / #107 — UI-Polish: Alert-Mail Etappenname, Umlaute, Toter Code

## Approval

- [ ] Approved

## Zweck

Drei unabhängige UI-Polishes werden gemeinsam umgesetzt, weil sie alle ausschließlich kosmetische oder offensichtliche Korrekturen darstellen und keinen Systemzustand teilen. Issue #130 behebt einen fehlenden `stage_name`-Parameter-Weiterleitungsfehler in `trip_alert.py`, sodass Alert-Mails den Etappennamen statt eines Rohdatums im Betreff zeigen. Issue #93 ersetzt 21 ASCII-Ersetzungen (ae/oe/ue/ss) in 8 Svelte-Komponenten durch korrekte deutsche Umlaute, um die Benutzeroberfläche sprachlich korrekt darzustellen. Issue #107 entfernt die tote Datei `TripForm.svelte`, die seit ihrer Einführung nirgendwo importiert wird und die Codebasis unnötig aufbläht.

## Quelle / Source

**Fix 1 — Issue #130:**
- `src/services/trip_alert.py` — Methode `_send_alert()`: `stage_name` aus Trip ermitteln und an `format_email()` übergeben

**Fix 2 — Issue #93:**
- `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte`
- `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte`
- `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte`
- `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte`
- `frontend/src/lib/components/trip-wizard/steps/WaypointRow.svelte`
- `frontend/src/lib/components/edit/EditRouteSection.svelte`
- `frontend/src/lib/components/trip-detail/FullProfile.svelte`
- `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte`

**Fix 3 — Issue #107:**
- `frontend/src/lib/components/TripForm.svelte` — Datei löschen via `git rm`

**Neue Test-Datei:**
- `tests/integration/test_trip_alert_stage_name.py`

> **Schicht-Hinweis:** Fix 1 liegt ausschließlich im Python-Backend (`src/services/`). Fix 2 und Fix 3 liegen ausschließlich im SvelteKit-Frontend-Layer (`frontend/src/lib/components/`). Es gibt keine Überschneidung zwischen den Schichten.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/trip_alert.py` | Python-Modul | Enthält `_send_alert()` — hier fehlt die `stage_name`-Übergabe an den Formatter |
| `src/formatters/trip_report.py` | Python-Modul | `format_email()` akzeptiert bereits `stage_name: Optional[str] = None` — kein Änderungsbedarf |
| `Trip.get_stage_for_date()` | Python-Methode | Liefert die passende Stage zum Alert-Datum — bereits vorhanden |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | Svelte-Komponente | 4 Umlaut-Korrekturen: Wizard-Schrittnamen + Zurück-Button |
| `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` | Svelte-Komponente | 1 Umlaut-Korrektur: Label "Aktivität" |
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | Svelte-Komponente | 5 Umlaut-Korrekturen: Validierungsmeldung + aria-labels |
| `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` | Svelte-Komponente | 2 Umlaut-Korrekturen: Eyebrow-Label + hint-Text |
| `frontend/src/lib/components/trip-wizard/steps/WaypointRow.svelte` | Svelte-Komponente | 3 Umlaut-Korrekturen: aria-labels für Status und Aktion |
| `frontend/src/lib/components/edit/EditRouteSection.svelte` | Svelte-Komponente | 3 Umlaut-Korrekturen: Validierungsmeldung + aria-labels |
| `frontend/src/lib/components/trip-detail/FullProfile.svelte` | Svelte-Komponente | 1 Umlaut-Korrektur: aria-label "auswählen" |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte` | Svelte-Komponente | 2 Umlaut-Korrekturen: aria-labels "bestätigen" + "löschen" |
| `frontend/src/lib/components/TripForm.svelte` | Svelte-Komponente | Toter Code — wird nirgendwo importiert, wird gelöscht |

## Implementation Details

### Fix 1 — Issue #130: Etappenname in Alert-Mail (`src/services/trip_alert.py`)

In der Methode `_send_alert()` drei Zeilen vor dem `format_email()`-Aufruf einfügen:

```python
alert_date = weather[0].segment.start_time.date()
matched_stage = trip.get_stage_for_date(alert_date)
stage_name = matched_stage.name if matched_stage else None
```

Anschließend `format_email()` um den Parameter `stage_name=stage_name` ergänzen:

```python
report = self._formatter.format_email(
    ...,
    stage_name=stage_name,  # NEU: Etappenname für Betreff-Generierung
)
```

`format_email()` in `trip_report.py` nimmt `stage_name` bereits als `Optional[str]` entgegen und nutzt ihn für den E-Mail-Betreff. Kein Änderungsbedarf dort.

### Fix 2 — Issue #93: Deutsche Umlaute (alle 8 Svelte-Dateien)

Exakte String-Ersetzungen (Ist → Soll):

**TripWizardShell.svelte:**
- Zeile 32: `'Aktivitaet, Name, Zeitraum'` → `'Aktivität, Name, Zeitraum'`
- Zeile 34: `'KI-Vorschlaege bestaetigen'` → `'KI-Vorschläge bestätigen'`
- Zeile 35: `'Kanaele und Alerts'` → `'Kanäle und Alerts'`
- Zeile 117: Button-Text `Zurueck` → `Zurück`

**Step1Profile.svelte:**
- Zeile 43: `Aktivitaet` → `Aktivität`

**Step2Stages.svelte:**
- Zeile 88: `'Bitte Startdatum waehlen.'` → `'Bitte Startdatum wählen.'`
- Zeile 211: aria-label `klicken zum Auswaehlen` → `Auswählen`
- Zeile 224: `oder klicken zum Auswaehlen` → `Auswählen`
- Zeile 242: `ausgewaehlt` → `ausgewählt`
- Zeile 309: aria-label `einfuegen` → `einfügen`

**Step4Briefings.svelte:**
- Zeile 57: `>Kanaele</Eyebrow>` → `>Kanäle</Eyebrow>`
- Zeile 83: hint `"demnaechst verfuegbar"` → `"demnächst verfügbar"`

**WaypointRow.svelte:**
- Zeile 54: aria-label `'Vorschlag (unbestaetigt)'` → `'Vorschlag (unbestätigt)'`
- Zeile 54: aria-label `'Bestaetigt'` → `'Bestätigt'`
- Zeile 87: aria-label `"Vorschlag bestaetigen"` → `"Vorschlag bestätigen"`

**EditRouteSection.svelte:**
- Zeile 59: `'Bitte Startdatum waehlen.\n'` → `'Bitte Startdatum wählen.'`
- Zeile 166: `oder klicken zum Auswaehlen` → `Auswählen`
- Zeile 180: `ausgewaehlt` → `ausgewählt`

**FullProfile.svelte:**
- Zeile 168: aria-label `auswaehlen` → `auswählen`

**WaypointCard.svelte:**
- Zeile 74: aria-label `"Wegpunkt bestaetigen"` → `"Wegpunkt bestätigen"`
- Zeile 113: aria-label `"Wegpunkt loeschen"` → `"Wegpunkt löschen"`

**Nicht ändern:** Code-Kommentare (z.B. `// …zurueck…`) — nicht user-visible.
**Kein Test-Anpassungsbedarf:** Alle E2E-Tests selektieren per `data-testid`, nicht per Labeltext.

### Fix 3 — Issue #107: TripForm.svelte löschen

```bash
git rm frontend/src/lib/components/TripForm.svelte
```

Vor dem Löschen Grep-Verifikation, dass kein Import existiert:

```bash
grep -r "TripForm" frontend/src/
```

Kein Treffer erwartet. Datei enthält Lat/Lon/Höhe-Felder ohne Labels — nie produktiv eingesetzt, nie importiert.

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `src/services/trip_alert.py` | +4 | ja |
| `tests/integration/test_trip_alert_stage_name.py` | ~40 | ja |
| 8 × Svelte-Komponenten | +0 / -0 (nur Zeichenwechsel in bestehenden Zeilen) | nein (Frontend-Asset) |
| `frontend/src/lib/components/TripForm.svelte` | Datei gelöscht | nein (Frontend-Asset) |
| **Gesamt (zählend)** | **~44** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input (Fix 1):** `_send_alert()` empfängt `trip` (mit Stages) und `weather` (Segment mit `start_time`)
- **Output (Fix 1):** `format_email()` erhält `stage_name` mit dem Namen der Stage, deren Datum mit dem Alert-Datum übereinstimmt; ist keine Stage zum Datum vorhanden, wird `None` übergeben und `format_email()` fällt auf das bisherige Datumsformat zurück
- **Input (Fix 2):** Kein Laufzeit-Input — reine String-Ersetzungen in Svelte-Templates
- **Output (Fix 2):** 21 UI-Strings zeigen korrekte deutsche Umlaute
- **Input (Fix 3):** Kein Laufzeit-Input — Datei-Löschung
- **Output (Fix 3):** `TripForm.svelte` existiert nicht mehr im Repository
- **Side effects:** Keine Laufzeit-Seiteneffekte. E2E-Tests sind nicht betroffen (selektieren per `data-testid`).

## Acceptance Criteria

- **AC-1:** Given ein Trip mit einer Stage, deren Datum mit dem Alert-Datum übereinstimmt / When `_send_alert()` ausgeführt wird / Then enthält der E-Mail-Betreff den Namen dieser Stage statt eines Rohdatums (>=30 Zeichen: Stage-Name wird als Betreff-Bestandteil übergeben, nicht das ISO-Datum)
  - Test: `tests/integration/test_trip_alert_stage_name.py::test_ac1_subject_contains_stage_name`

- **AC-2:** Given ein Trip ohne Stage zum Alert-Datum / When `_send_alert()` ausgeführt wird / Then enthält der E-Mail-Betreff das Datumsformat als Fallback und wirft keinen Fehler (>=30 Zeichen: Fallback-Pfad funktioniert fehlerfrei wenn keine Stage matched)
  - Test: `tests/integration/test_trip_alert_stage_name.py::test_ac2_fallback_to_date_when_no_stage`

- **AC-3:** Given die 8 geänderten Svelte-Quelldateien / When nach den 21 korrigierten Strings gesucht wird / Then sind alle korrekten Umlaut-Varianten vorhanden und keine ASCII-Ersetzung (ae/oe/ue) mehr in user-sichtbaren Strings (>=30 Zeichen: kein ae/oe/ue in UI-Labels, Buttons, aria-labels)
  - Test: `tests/integration/test_trip_alert_stage_name.py::test_ac3_no_ascii_umlauts_in_svelte_files`

- **AC-4:** Given das Repository nach Durchführung des Fix 3 / When nach `TripForm.svelte` gesucht wird / Then existiert die Datei nicht mehr und kein Import referenziert sie (>=30 Zeichen: TripForm.svelte ist vollständig aus dem Repository entfernt und nicht referenziert)
  - Test: `tests/integration/test_trip_alert_stage_name.py::test_ac4_tripform_deleted`

## Known Limitations

- **Kein Browser-Rendering-Test für Umlaute:** Die Svelte-Komponenten werden nicht im Browser gerendert und geprüft. Die Datei-Inhalt-Prüfung (AC-3) ist hinreichend, da die Strings direkt als Template-Literals eingebettet sind.
- **`get_stage_for_date()` muss vorhanden sein:** Fix 1 setzt voraus, dass `Trip.get_stage_for_date(date)` bereits implementiert ist. Vor der Implementierung verifizieren.

## Out of Scope

- Umlaut-Korrekturen in Code-Kommentaren
- Anpassungen an E2E-Tests (selektieren per `data-testid`, nicht per Label)
- Änderungen an anderen Svelte-Komponenten außer den 8 aufgeführten
- Entfernung anderer toter Dateien außer `TripForm.svelte`

## Changelog

- 2026-05-19: Initial spec erstellt. Fasst drei unabhängige UI-Polishes zusammen: #130 (stage_name in Alert-Mail), #93 (21 Umlaut-Korrekturen in 8 Svelte-Dateien), #107 (TripForm.svelte als toten Code löschen).
