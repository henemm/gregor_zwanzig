# Context: Issue #428 — Trip-Wizard auf 5-stufige Spec aktualisieren

## Request Summary

Der bestehende 4-stufige Trip-Wizard (`/trips/new`) wird auf **5 Schritte** umgebaut: ein
neuer Schritt **„Layout"** schiebt sich zwischen Wetter und Reports und nutzt denselben
Component wie der Output-Editor im Trip-Detail (`WeatherMetricsTab.svelte`-Pendant).
Weitere strukturelle Änderungen: Step 3 verliert die HEUTE/MORGEN/ÜBERMORGEN-Horizon-Pills
zugunsten eines Format-Dropdowns pro Metrik; Step 5 (Reports) zeigt nur noch 3 Cards
(Abend mit „3–7-Tage-Ausblick"-Toggle, Morgen, Warnungen) statt 4; AUTARK-Pill entfällt;
Abschluss-Button heißt „Tour speichern".

## Related Files

| Datei | Relevanz |
|------|-----------|
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | Stepper-Container, Header-Eyebrow „SCHRITT N VON 4", Footer-Hints, Step-Switch — 4→5 erweitern |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | Klasse mit `currentStep: 1\|2\|3\|4`, `canAdvanceStepN`-Gettern, `nextStep/prevStep`, `toTripPayload()` — Typen auf `1..5` erweitern, neuer State für Layout-Konfiguration |
| `frontend/src/lib/components/trip-wizard/Stepper.svelte` | Pure 4-Step-Stepper (Mobile-Compact + Desktop-Full) — auf 5 Schritte; Mobile-Variante laut Soll als 5-Segment-Progressbar (statt aktueller „N / 5 · Label") |
| `frontend/src/lib/components/trip-wizard/stepperState.ts` | `stepperStateOf(i, current)` — bleibt logisch, akzeptiert größere `current`-Werte |
| `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` | „Route"-Step — bleibt inhaltlich gleich (Name, Region, GPX, Startdatum) |
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | „Etappen"-Step — bleibt inhaltlich gleich (Header, DnD-Liste, Vorschläge-Pill, TemplatePicker) |
| `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte` | „Wetter"-Step — **wird ersetzt:** Horizon-Pills raus, Format-Dropdown rein, Metriken in 5 Kategorien-Gruppen mit Sticky-Headers, scrollbarer Container, Fade-Indikator |
| `frontend/src/lib/components/trip-wizard/steps/Step4Reports.svelte` | Aktueller „Reports"-Step (Position 4) — **wird zu Step 5** und reduziert sich auf 3 Cards: AUTARK-Pill raus, Mehrtages-Trend-Card raus, dafür Toggle in Abend-Card |
| **NEU:** `frontend/src/lib/components/trip-wizard/steps/Step4Layout.svelte` | Neuer Step 4 „Layout": 4 Channel-Tabs, Drag-sortierbare Spalten-/Detail-Liste, Live-Preview pro Kanal |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Bestehender Output-Editor im Trip-Detail — Issue C2 verlangt **geteilten Component** mit Step 4 Layout; Extraktion eines trip-agnostischen `OutputLayoutEditor` notwendig |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | Reine Helpers (`autoAssign`, `move`, `reorder`, `buildWeatherConfigMetrics`, `CATEGORY_LABELS`, `INDICATOR_MAP`) — wiederverwendbar ohne Änderung |
| `frontend/src/lib/components/trip-detail/BucketSection.svelte` | Drag-Sort + ▲▼-Buttons je Bucket — wiederverwendbar in Step 4 |
| `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte` | 4-Kanal-Live-Preview (Desktop 4er-Grid, Mobile Dropdown + 1 Card) — wiederverwendbar |
| `frontend/src/lib/components/trip-detail/ChannelPreviewCard.svelte` | Einzelne Vorschau-Karte pro Kanal |
| `frontend/src/lib/components/trip-detail/AboutOutputLayout.svelte` | Erklärungs-Modal — optional in Step 4 verlinken |
| `frontend/src/lib/components/trip-wizard/+page.server.ts` (bzw. `/routes/trips/new/`) | Profil-Loader bleibt unverändert |
| `frontend/src/lib/components/ui/horizon-chip/` | HorizonChip-Atom — Step 3 entfernt seine Nutzung; das Atom bleibt für Trip-Detail/Wetter-Editor erhalten |
| `frontend/e2e/trip-wizard-step1.spec.ts` … `step4.spec.ts` | E2E-Tests — Step-Anzahl auf 5 anpassen, Step-3-Horizon-Asserts entfernen, Step-4 wird Layout, Step-5 ersetzt Reports |
| `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` | Unit-Tests für `canAdvanceStep*` und `nextStep/prevStep` — auf 5 Schritte erweitern |
| `internal/model/trip.go` | `DisplayConfig map[string]interface{}` — additiv, kein Backend-Schema-Umbau nötig |
| `docs/specs/modules/issue_300_wizard_redesign.md` | Vorgänger-Spec (4-Step-Redesign) — bleibt erhalten, neue Spec referenziert sie als Vorgeschichte |
| `docs/specs/modules/epic_136_trip_wizard.md` | Master-Spec Wizard — Step-Anzahl + Stepper-Doku müssen aktualisiert werden |
| `docs/specs/modules/issue_412_422_wizard_step4.md` | „DEINE KANÄLE"-Karte in Step 4 — wandert mit dem Report-Inhalt nach Step 5 |
| `.github/issue-assets/soll-flow1{B..F}-{wizard,mobile}-*.png` | SOLL-Screens (10 Stück) — Desktop + Mobile pro Schritt, schon im Repo |

## Existing Patterns

- **Factory-Pattern für State:** `WizardState` wird pro Page-Mount neu instanziiert (siehe Kommentar in `+page.svelte` — Safari-Reaktivitätsrisiko vermieden). Neuer Layout-State folgt demselben Muster.
- **Getter statt `$derived` für Step-Validation:** Damit Plain-Node-Tests bei State-Mutation aktuell bleiben (Spec-Begründung in `wizardState.svelte.ts`).
- **Bucket-/Order-Persistenz:** `display_config.metrics` ist heute ein flacher Array mit `bucket: 'primary'|'secondary'|'off'` + `order: number`. Pro-Kanal-Override gibt es noch **nicht** — das wäre eine echte Datenmodell-Erweiterung.
- **Benannte Handler-Factories (Safari/Factory-Pattern):** `makeToggleEnabled(metric)`, `makeChannelHandler(key)` — wird auch in Step 4 Layout konsequent angewendet.
- **Sticky Footer mit `safe-area-inset-bottom`:** TripWizardShell hat schon `position: sticky; bottom: 0` + iOS-Safe-Area. Step 4 mobil braucht denselben Pattern.
- **`lang="de"` auf `<input type="time">`:** Erzwingt 24h-Anzeige in Safari (Memory-Eintrag: en-US-Locale-Artefakt). Beide Time-Felder in Step 5 bekommen das wieder.
- **Daten-Slots (`[data-slot]`, `[data-tone]`, `[data-outlined]`):** Atomic-Bibliothek (Epic #368). Neue Buttons/Pills/Cards in Step 4/5 folgen diesem Muster.
- **Trip-Terminologie-Guard:** Tests (`contrast-audit.test.ts` & Co.) verhindern, dass irgendwo „Tour"/„Touren" für `trip`-Objekte verwendet wird. Der **Abschluss-Button** ist jedoch ein UI-Copy-Element („Tour speichern") — bestätigte PO-Entscheidung im Issue.

## Dependencies

- **Upstream:**
  - `WeatherMetricsTab.svelte` + `metricsEditor.ts` (für Step 4 Layout)
  - `Stepper.svelte` (Step-Anzahl)
  - `GET /api/metrics` (Katalog, schon in Step 3 in Verwendung)
  - `POST /api/trips` (Save-Endpoint, unverändert)
  - Profil-Loader (`+page.server.ts` für „DEINE KANÄLE"-Karte)
- **Downstream:**
  - Trip-Detail-Page nutzt heute `WeatherMetricsTab` direkt — bei Extraktion eines geteilten `OutputLayoutEditor` bleibt das Tab ein dünner Wrapper, der den Editor mit `bind:` an Trip-Felder hängt
  - E2E-Tests für Wizard und Trip-Detail
  - `frontend/src/lib/types.ts` — `WeatherConfigMetric` (bleibt unverändert, bucket/order ist schon drin)

## Existing Specs

| Spec | Zweck |
|------|------|
| `docs/specs/modules/epic_136_trip_wizard.md` | Master-Spec des Wizards (4-Step-Struktur, WizardState-Felder, Routing). Wird aktualisiert. |
| `docs/specs/modules/issue_300_wizard_redesign.md` | Vorgänger-Spec für aktuelle 4-Step-Variante (Route/Etappen/Wetter/Reports). Historisch — wird durch #428-Spec ergänzt. |
| `docs/specs/modules/issue_412_422_wizard_step4.md` | „DEINE KANÄLE"-Karte oben in Step 4 (aktuell). Inhaltlich wandert die Karte nach Step 5 oder verschwindet, weil Kanal-Auswahl pro Card erfolgt — Spec-Update fällig. |
| `docs/specs/modules/issue_364_metrics_editor_buckets.md` | Bucket-/Order-Modell für `display_config.metrics`. Step 4 Layout baut darauf auf. |
| `docs/specs/modules/issue_365_channel_preview_mobile.md` | ChannelPreviewBlock Mobile-Verhalten (Dropdown statt 4er-Grid). Wiederverwendet in Step 4. |

## PO-Entscheidungen (2026-05-28)

1. **Terminologie:** „Trip" durchgehend im UI — Eyebrow „SCHRITT N VON 5 · NEUER TRIP", Abschluss-Button **„Trip speichern"**. Die Issue-Vorgabe „NEUE TOUR" / „Tour speichern" ist damit überschrieben — Memory-Regel zur Trip-Terminologie gilt auch für UI-Copy.
2. **Layout pro Kanal:** Datenmodell wird erweitert. Statt einer globalen `display_config.metrics`-Liste werden vier eigene Spalten-/Detail-/Off-Listen pro Kanal persistiert (Email / Telegram / Signal / SMS). Reihenfolge, Bucket-Zuordnung und damit auch die Detail-Zeile sind pro Kanal frei. SMS bleibt der Sonderfall mit Priorisierungs-Listen-Mode (keine Tabelle, ≤140 Zeichen).
3. **„DEINE KANÄLE"-Karte fliegt raus.** Die Kanal-Auswahl sitzt direkt als Chip-Reihe in jeder Report-Card (Abend, Morgen, Warnungen) — wie in den SOLL-Screens.

## Risks & Considerations

1. **Constraint C2 — geteilter Component:** `WeatherMetricsTab.svelte` ist heute trip-gebunden (lädt Catalog/Presets, hat Save-Button, schreibt PUT auf `/api/trips/{id}/weather-config`). Für die Wizard-Wiederverwendung muss der **reine Editor** extrahiert werden — ohne Save-Knopf, ohne API-Calls, mit gebundenem Bucket/Friendly/Horizons-State. Risiko: Refactor zieht Anpassungen am Trip-Detail mit sich (~150–200 LoC). Alternative wäre eine Wizard-eigene Variante, die aber gegen C2 verstößt.
2. **Datenmodell „Layout pro Kanal":** Der Issue-Body verweist auf `body-14-output-layout-system.md` für ein `trip.output_layout`-Feld pro Kanal — diese Datei existiert nicht im Repo. Heute ist `display_config.metrics` eine **globale** Spalten-Reihenfolge. Issue C3 sagt „Abend & Morgen teilen sich eine Layout-Konfiguration pro Kanal" — das passt zur globalen Konfiguration. Aber **vier Kanäle mit eigener Spalten-Reihenfolge** ist heute nicht abgebildet. Klärungsbedarf: Soll diese Iteration nur die UI bauen und alle Kanäle teilen die gleiche Bucket-/Order-Liste (wie heute), oder wird das Datenmodell erweitert?
3. **Step-3-Format-Dropdown:** Der heutige Wizard zeigt einen schlichten Text „Roh" oder „Indikator". Soll verlangt ein **Dropdown mit 4 Optionen (Roh/Skala/Vereinfacht/Symbol)**. Im Backend gibt es aktuell nur `use_friendly_format: boolean` (zwei Zustände). Out-of-Scope laut Issue Punkt 1 — also UI mit 4 Optionen rendern, hinter den Kulissen mappt sie auf den Bool, bis das Backend nachzieht.
4. **Mobile-Stepper:** Aktuell zeigt der Compact-Stepper „N / M · Label". Soll verlangt einen **5-Segment-Fortschrittsbalken** + den Klar-Text „SCHRITT N VON 5 · NEUE TOUR" oben. Layout-Umbau im Stepper-Atom.
5. **Eyebrow „NEUER TRIP" vs. „NEUE TOUR":** Aktuell `SCHRITT N VON 4 · NEUER TRIP`. Issue verwendet konsequent „NEUE TOUR" und Abschluss-Button „Tour speichern". Memory dokumentiert eine Terminologie-Regel „Trip nicht Tour" — **Konflikt!** Der Issue ist nach der Regel datiert (28.05.) und expliziter PO-Override; der Hinweis im Memory bezieht sich auf interne `trip.*`-Modellfelder, nicht UI-Copy. Vor Spec-Schreiben kurz beim User absichern.
6. **„DEINE KANÄLE"-Karte (Issue #412/#422):** Sie zeigt Kontaktdaten + Switches und sitzt heute über dem 2×2-Grid in Step 4. Im neuen Step 5 (Reports) sind Kanäle laut Soll **pro Card** als Chip-Reihe abgebildet, dazu maskierte Kontaktdaten — ist die Channel-Karte damit obsolet, oder bleibt sie als Übersicht erhalten? Tendenz: integrierte Chip-Reihe pro Card reicht; Channel-Karte fliegt raus.
7. **LoC-Budget:** Step 4 Layout ist ein neuer Step (~250–400 LoC), Step 3 wird umgebaut (~150 LoC), Step 5 vereinfacht sich leicht (~−50 LoC), Stepper-Mobile-Variante neu (~50 LoC), WizardState-Erweiterungen (~30 LoC), Spec-/Test-Anpassungen. Override auf 750–900 LoC erforderlich (kommt mit Begründung in den Workflow-State).
8. **Migration bestehender Trips:** Trips, die mit dem alten 4-Step-Wizard angelegt wurden, haben `display_config.metrics` ohne explizite Bucket-Reihenfolge. Step 4 Layout liest das bestehende Schema (autoAssign-Fallback in `metricsEditor.ts`) — keine Daten-Migration nötig.
9. **Out-of-Scope-Pflichten:** Echtes Drag-and-Drop in Step 4 (Library-Wahl), finale Format-Optionen pro Metrik, Per-Report-Overrides, Routing für „Inhalt im Output-Editor anpassen →" — laut Issue bewusst nicht in Scope. Das hält den Umfang beherrschbar.
10. **Adversary-Verifikation:** Visueller Vergleich gegen 10 SOLL-Screens nötig (5 Desktop, 5 Mobile). Fresh-Eyes-Inspector hilft, Drift früh zu sehen.

## Verteilung der SOLL-Screens (alle im Repo)

| Schritt | Desktop | Mobile |
|---------|---------|--------|
| 1 Route   | `soll-flow1B-wizard-step1-route.png`    | `soll-flow1B-mobile-step1-route.png` |
| 2 Etappen | `soll-flow1C-wizard-step2-etappen.png`  | `soll-flow1C-mobile-step2-etappen.png` |
| 3 Wetter  | `soll-flow1D-wizard-step3-wetter.png`   | `soll-flow1D-mobile-step3-wetter.png` |
| 4 Layout  | `soll-flow1E-wizard-step4-layout.png`   | `soll-flow1E-mobile-step4-layout.png` |
| 5 Reports | `soll-flow1F-wizard-step5-reports.png`  | `soll-flow1F-mobile-step5-reports.png` |
