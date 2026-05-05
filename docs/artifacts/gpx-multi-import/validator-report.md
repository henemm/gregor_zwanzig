# External Validator Report — Re-Validation

> **Hinweis:** Dieser Report ersetzt den Report vom 2026-05-04 (Verdict: BROKEN).
> Die Implementierung wurde zwischenzeitlich deployed und erneut validiert.

**Spec:** `docs/specs/modules/gpx_multi_import.md` (v1.1)
**Datum:** 2026-05-05T14:38:17Z
**Server:** https://staging.gregor20.henemm.com
**Validator:** Unabhängige Session — kein Zugriff auf src/, git log, docs/artifacts der Implementierer

## Test-Setup (Re-Validation 2026-05-05)

- Auth: gz_session-Cookie fuer User `validator-issue110`
- 3 valide GPX-Files in absichtlich falscher Upload-Reihenfolge:
  - `KHW_11.gpx`, `KHW_00a.gpx`, `KHW_10.gpx` (jeweils 12 Trackpoints — API-Minimum: 10)
- 1 invalide GPX-Datei (`CORRUPT.gpx` mit Klartext) fuer Skip-Test
- Browser: Chromium (Playwright headless)
- Screenshots in `docs/artifacts/gpx-multi-import/v-*.png`

## Checklist

| # | Expected Behavior (aus Spec) | Beweis | Verdict |
|---|------------------------------|--------|---------|
| 1 | Multi-Select-Upload (`max_files=-1`) im New-Trip-Dialog | `<input type="file" multiple accept=".gpx">` vorhanden — Screenshot v-01 | **PASS** |
| 2 | Multi-Select-Upload im Edit-Trip-Dialog | Edit-Trip → Route aufklappen → `multiple=True` — Screenshot v-08 | **PASS** |
| 3 | Nach Datei-Auswahl erscheint **Datumspicker + Commit-Button** | "3 Datei(en) ausgewaehlt", Startdatum-Picker (05/05/2026), "3 Etappen anlegen" sichtbar — Screenshot v-02 | **PASS** |
| 4 | Natural-Sort: KHW_11+KHW_00a+KHW_10 → verarbeitet als 00a→10→11 | API-Responses in Reihenfolge: `KHW Tag 00a, KHW Tag 10, KHW Tag 11` — Log + Screenshot v-03 | **PASS** |
| 5 | Stages in sortierter Reihenfolge angelegt | Step 2 "Etappen": KHW Tag 00a (05/01), KHW Tag 10 (05/02), KHW Tag 11 (05/03) — Screenshot v-03 | **PASS** |
| 6 | Erste Stage = Startdatum, jede weitere +1 Tag | API-Calls: `stage_date=2026-05-01, 2026-05-02, 2026-05-03` | **PASS** |
| 7 | Default-Datum: `date.today()` bei leerem Trip | Default nach Upload ohne Stages: `2026-05-05` (= Testdatum) | **PASS** |
| 8 | Default-Datum: `last_stage_date + 1` falls Stages vorhanden | Nach Stage mit 2026-05-10 → Default = `2026-05-11` — Screenshot v-07 | **PASS** |
| 9 | Default-Datum in Edit-Trip: last_stage_date + 1 | Trip mit Stage 2026-05-04 → Default = `2026-05-05` — Test-Log | **PASS** |
| 10 | Single-File-Upload: Datumspicker erscheint, 1 Stage mit Datum | "1 Etappe anlegen" + Datumspicker vorhanden; API mit date=2026-06-15; "1 Etappe(n) geladen" — Screenshot v-05 | **PASS** |
| 11 | Kein Datum → Fehlermeldung, nichts angelegt | "Bitte Startdatum waehlen." (rot); Buffer bleibt — Screenshot v-04 | **PASS** |
| 12 | Korruptes GPX → Warnung, restliche lückenlos verarbeitet | "CORRUPT.gpx: GPX parse failed: ..."; "2 Etappe(n) geladen"; dates: 2026-05-01 + 2026-05-02 (keine Lücke) — Screenshot v-06 | **PASS** |
| 13 | Buffer nach Commit geleert, Commit-Button verschwindet | "3 Etappe(n) geladen"; Commit-Block weg | **PASS** |
| 14 | "Abbrechen" im Commit-Block löscht Buffer | Buffer weg, kein Commit — Screenshot v-09 | **PASS** |
| 15 | Edit-Trip: natural sort + date propagation | KHW 00a (05-10) → KHW 10 (05-11) → KHW 11 (05-12) — Test-Log | **PASS** |
| 16 | Per-Stage-Waypoint-Import unverändert single-file | SvelteKit-UI hat kein per-Stage GPX-Widget (architekturkonsistent) | **N/A** |
| 17 | Safari Factory Pattern | Chromium-Test bestätigt Commit-Button-Reaktion; Safari extern nicht testbar | **UNKLAR** |

## Findings

### F1 — Notification-Typ: Inline-Text statt Toast (LOW, kein Bug)

- **Severity:** LOW
- **Expected:** Spec referenziert `ui.notify(type="warning")` / `ui.notify(type="negative")` (NiceGUI-API)
- **Actual:** SvelteKit zeigt inline roten Text statt Toasts. Intent erfüllt (Nutzer sieht Fehlermeldung). SvelteKit-Architektur-Note in Spec v1.1 macht diese Anpassung erwartbar.
- **Evidence:** Screenshot v-04 (kein Datum), Screenshot v-06 (korrupte Datei)

### F2 — Korrupte Datei sortiert vor valide Files (LOW, Verhalten korrekt)

- **Severity:** LOW (Verhalten ist spec-konform, aber Seiteneffekt dokumentiert)
- **Expected:** Spec sagt "korrupte Datei → übersprungen, Datum lückenlos für valide Files"
- **Actual:** CORRUPT.gpx (C < K) sortiert alphabetisch vor KHW_*. Erhält stage_date=2026-05-01, schlägt fehl, added-Zähler nicht erhöht. Valide Files: 2026-05-01 + 2026-05-02 → lückenlos. Spec-Intent erfüllt.
- **Evidence:** API-Log Test C: `stage_date=2026-05-01` (CORRUPT→fail), `stage_date=2026-05-01` (KHW_00a→ok), `stage_date=2026-05-02` (KHW_10→ok)

## Verdict: VERIFIED

### Begründung

Alle 15 prüfbaren Acceptance-Criteria sind erfüllt. Die als UNKLAR/N/A markierten Punkte sind:
- Safari Factory Pattern (nicht extern testbar ohne echten Safari-Browser)
- Per-Stage-Waypoint-Import in SvelteKit (existiert nicht in SvelteKit — architekturkonform)

**Kernbeweise:**
1. **Natural-Sort bewiesen:** Upload-Reihenfolge KHW_11, KHW_00a, KHW_10 → API-Responses in Reihenfolge `KHW Tag 00a, KHW Tag 10, KHW Tag 11`. Stage-Ansicht in Step 2 bestätigt: 00a (05-01) → 10 (05-02) → 11 (05-03).
2. **Datumspropagation exakt:** `stage_date=+1 Tag` pro valider Stage, keine Lücken bei korrupten Files.
3. **Default-Datum-Logik korrekt:** `today()` bei leerem Trip; `last_stage_date+1` bei vorhandenen Stages — in New-Trip UND Edit-Trip.
4. **Fehlerfälle robust:** Kein Datum → User-Feedback, Buffer bleibt. Korrupt → Warnung sichtbar, valide Files normal verarbeitet.
5. **Beide Dialog-Ebenen:** New-Trip-Wizard UND Edit-Trip-Seite haben identisches Multi-Upload-Verhalten.

### Screenshots (Beweise)
- `v-01_wizard_initial.png` — Upload-Widget im Wizard
- `v-02_buffer_with_datepicker.png` — Commit-Block nach 3-Datei-Upload
- `v-03_natural_sort_verified.png` — Stage-Reihenfolge in Step 2 (KHW 00a→10→11, Daten 05-01→02→03)
- `v-04_no_date_error.png` — "Bitte Startdatum waehlen." Fehlermeldung
- `v-05_single_file_works.png` — Single-File-Upload Regression-Check
- `v-06_corrupt_gpx_handled.png` — Korruptions-Warnung + "2 Etappe(n) geladen"
- `v-07_default_date_last_plus1.png` — Default-Datum last+1 nach vorhandener Stage
- `v-08_edit_trip_multi_upload.png` — Edit-Trip: Route-Sektion mit Multi-Upload
- `v-09_abbrechen_clears_buffer.png` — Buffer-Clear durch Abbrechen
