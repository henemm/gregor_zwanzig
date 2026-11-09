---
entity_id: feat_2794_s3a_teil2_leiste
type: module
created: 2026-11-09
updated: 2026-11-09
status: draft
version: "1.0"
tags: [hub, reiter, wetter, zustellung, leiste, umleitung, anlege-kette, epic-2791]
---

# Einstellungen neu S3a, Teil-PR 2: Leiste und Umleitung (#2794)

## Approval

- [ ] Approved

## Purpose

Teil-PR 2 der freigegebenen Gesamt-Spec `feat_2794_s3a_reiter_wetter.md`. Der Hub von Trip und Orts-Briefing bekommt die vier Reiter Übersicht · Etappen (Trip) bzw. Orte · Wetter · Zustellung unter den neuen Kennungen `wetter` und `zustellung`. Alte Adressen werden umgeleitet, die Anlege-Ketten folgen, die Reiterleiste entspricht dem Atomic-Design-Soll, und die Seitenüberschrift am Desktop wird als Regressionswächter abgesichert.

Der Reiter `zustellung` ist ein Übergangsreiter: Er nimmt die heutigen Versand- und Alarm-Bausteine sowie die Zustellungs-Blöcke aus der Metrik-Oberfläche unverändert auf, damit kein Bedienelement verschwindet. Der Reiter `wetter` zeigt bis Teil-PR 3 die bisherige Metrik-Oberfläche (ohne Zustellungs-Blöcke) und darunter die nur lesende Wertebereiche-Ansicht. Es entstehen keine neuen Speicherwege.

Grundlagen: Gesamt-Spec (§1 Reiter-Definition, §2 Reiterleiste, §3 Übergangsreiter Zustellung mit 16-Punkte-Inventar, Lieferplan), Analyse `docs/context/feature-2794-s3a-teil2-leiste.md`, ADR-0109 und ADR-0106.

## Source

- **Frontend (produktive Oberfläche):** `frontend/src/lib/components/shared/subscriptionTabs.ts` (`REITER_DEFINITION`, `LEGACY`, `LEGACY_ANKER`, `resolveTab`, `versandSprungStart`, `bereinigteTabAdresse`), `trip-detail/TripTabs.svelte`, `compare/CompareTabs.svelte`, `mobile/MTabBar.svelte`, `frontend/src/app.css`, `shared/WeatherMetricsTab.svelte`, `shared/weather-metrics-tab/weatherMetricsTabSections.ts`, `shared/WetterMetrikenVersandPanel.svelte`, `trip-new/*`, `compare-new/*`; neu: `shared/zustellung-tab/ZustellungTab.svelte`.
- **Go-API und Python-Core:** nicht betroffen (keine neuen Datenwege).

> **Schicht-Hinweis:** Alle Änderungen liegen im SvelteKit-Frontend (`frontend/src/...`). Go-API und Python-Core bleiben unverändert.
>
> **Trip/Ortsvergleich-Teilung:** erfüllt. `ZustellungTab` liegt unter `shared/zustellung-tab/` mit `context="route"|"vergleich"`; es entsteht kein einseitiger Baustein. Compare-eigen bleibt nur der Orte-Tab wie bisher.
>
> **Mandantentrennung:** keine neuen Datenwege, `user_id` kommt wie bisher aus dem Auth-Kontext. Die Speicherweg-Tests zu AC-8 laufen trotzdem mit zwei verschiedenen Konten (Gesamt-Spec, Test Plan „Zwei-Konten-Lauf“).
>
> **Kanäle:** Briefing- und Alarm-Inhalt bleiben unverändert (E-Mail · Telegram · SMS · Premium-SMS gleich wie vorher). Kein Mail-Validator-Lauf nötig, das Renderer-Gate wird nicht berührt.

## Estimated Scope

- **LoC:** Produktion ca. +900 / −400
- **Files:** ca. 20 Produktiv-Dateien; Tests: ca. 140 Dateien Umzug (überwiegend Kennungs-Ersetzung), ca. 6 neue Kern-Testdateien
- **Effort:** high (Risiko MEDIUM-HIGH: Datenverlust bei Doppel-Instanz, Flush-Listen, Vergleichs-Hydration, Anlege-Ketten)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/subscriptionTabs.ts` | MODIFY | `wetter`/`zustellung` in `REITER_DEFINITION`, Anlege-Köpfe, `ANLEGE_SCHWANZ_HINWEIS`, `LEGACY`, `LEGACY_ANKER`, `versandSprungStart`, `bereinigteTabAdresse` |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts` | MODIFY | zweiter Parameter `bereich`; neue Abschnittsnamen `layout_kanal`, `nachtblock` |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Prop `bereich`, Gates auf neue Abschnittsnamen; Speicherwege und Owner unverändert |
| `frontend/src/lib/components/shared/WetterMetrikenVersandPanel.svelte` | MODIFY | `bereich` durchreichen, Versand-Abschnitt nur bei `zustellung` |
| `frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte` | CREATE | Übergangsreiter mit `context` |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | MODIFY | Reiter `wetter`/`zustellung`, Flush-Liste, Badge Wertebereiche entfällt |
| `frontend/src/lib/components/trip-detail/AlarmeScheduleTab.svelte` | MODIFY | Hülle wird in `ZustellungTab` verwendet (Löschen erst Teil-PR 4) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Reiter `wetter`/`zustellung`, Lazy-Hydration, Panel-Gate, `hubActivationCard` in Zustellung |
| `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | MODIFY | `SELBST_SPEICHERNDE_VERGLEICH_REITER` auf neue Kennungen |
| `frontend/src/lib/components/mobile/MTabBar.svelte`, `frontend/src/app.css` | MODIFY | aktiv 600, Badge Mono 10 px, Segmented-Markup und Box entfernen (nach PR #2871) |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte`, `trip-new/tripNewLogic.ts` | MODIFY | Kette route·etappen·wegpunkte·wetter·zustellung |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Kette vergleich·orte·wetter·zustellung |
| `frontend/src/lib/components/shared/anlegeLockEngine.ts`, `shared/infoboxKeys.ts` | MODIFY | `letzterId='zustellung'`, Infobox-Schlüssel |
| `hub-uebersicht/hubUebersichtModell.ts`, `trip-detail/HubOverview.svelte`, `edit/WeatherSummaryCard.svelte`, `alerts-tab/AlertPreviewCard.svelte`, `routes/+page.svelte`, `routes/trips/+page.svelte`, `routes/compare/+page.svelte`, `routes/compare/[id]/+page.svelte` | MODIFY | Sprungziele auf neue Kennungen (nur Kennung) |
| `frontend/src/lib/i18n/messages/de/aktionen.json`, `.../en/aktionen.json` | MODIFY | neue Schlüssel `aktionen.reiter.wetter`, `aktionen.reiter.zustellung` |
| Bestehende Kern-Tests (ca. 27 Dateien), E2E-Specs (ca. 82), Goldens f9/f10/f3/f7, `tests/unit/test_e2e_compare_paritaet_waechter.py` | MODIFY/DELETE | Kennungen umstellen; Tests ausschließlich entfallener Reiter löschen |
| Neue Kern-Testdateien (ca. 6) | CREATE | siehe Test Plan |

(Alle Pfade ohne Präfix liegen unter `frontend/src/lib/components/` bzw. `frontend/src/`.)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| PR #2871 (#2845 Leiste) | Vorarbeit | ändert MTabBar, CompareTabs, f10-Goldens; muss vor der Implementierung gemergt sein |
| PR #2872 (S2b `AlarmeTab`) | Vorarbeit | ändert `AlarmeTab.svelte`, `alerts-tab/*`; muss vor der Implementierung gemergt sein, dann auf `origin/main` rebasen |
| Teil-PR 1 (#2870) | Vorarbeit | live (Backend Vorlagen, Katalog, Zähler) |
| `saveController`, Vergleichs-Speicherer (`versandVergleichSpeicherung`, `alarmeVergleichSpeicherung`, `wertebereicheVergleichSpeicherung`) | Code | Speicherwege bleiben bitgleich |
| i18n-Katalog (ADR-0104) | Code | neue Reiter-Labels DE/EN |
| Teil-PR 3, Teil-PR 4, S3b #2795 | Folgearbeit | Teil-PR 3 ersetzt den Inhalt hinter `wetter`, Teil-PR 4 löscht Altkomponenten und zieht Übersicht/Hilfe nach, S3b baut Zustellung um |

## Implementation Details

**Lieferung:** ein PR, drei lauffähige Commits: (1) Leiste nach Soll und AC-36-Regressionswächter; (2) Kennungen, `LEGACY`, Ketten, Flush-Listen, Hydration; (3) `bereich`-Filter.

### 1. Reiter-Definition und Umleitung (`subscriptionTabs.ts`)

- `REITER_DEFINITION` bekommt `wetter` und `zustellung` für Hub und Anlege-Köpfe; `ANLEGE_SCHWANZ_HINWEIS` wird auf die neuen Kennungen umgestellt.
- `LEGACY`: `wetter-metriken`, `wertebereiche`, `layout` → `wetter`; `alarme`, `versand`, `briefings` → `zustellung`; die übrigen Alt-Kennungen (`overview`, `stages`, `weather`, `alerts`, `preview`, `vorschau`, `idealwerte`) zeigen weiter auf das passende neue Ziel.
- `LEGACY_ANKER`: `versand`/`briefings` → `zustellung` mit Anker `versand`. `versandSprungStart` und `bereinigteTabAdresse` folgen; die Adresse wird bereinigt (`replaceState`, kein Rest der Alt-Kennung). Der Anker `#versand` gewinnt gegen die Reiterkennung.

### 2. `bereich`-Darstellungsfilter

`weatherMetricsTabSections(context, bereich)` mit `bereich ∈ {wetter, zustellung, alles}`; neue Abschnittsnamen `layout_kanal` und `nachtblock`.

- **wetter:** Grundauswahl, Tagesfenster, SMS-Schwellen, amtliche Warnungen (Bericht).
- **zustellung:** Layout je Kanal (Reihenfolge), Stundenverlauf, Ausblick, Mail-Inhalt (`report_config`), Nacht-Block.
- wetter ∪ zustellung = alles, beide disjunkt.

Der Filter ist rein darstellend: Speicherwege, Owner, Payloads und Hydration bleiben bitgleich (`sections` ist in `WeatherMetricsTab` rein abgeleitet, kein Effekt hängt daran). Zwei gleichzeitig gemountete WMT-Instanzen sind verboten (gegenseitiges Überschreiben mit veraltetem Stand).

### 3. Neue Shared-Komponente `ZustellungTab`

`shared/zustellung-tab/ZustellungTab.svelte` mit `context="route"|"vergleich"` enthält:

- `WeatherMetricsTab` mit `bereich=zustellung` (über das Panel);
- Versand-Abschnitt `<section id="versand">` (Trip-Hub `BriefingScheduleTab`, Vergleich und Anlegen `VersandTab`; Aktivieren im Vergleich über das bisherige Snippet `hubActivationCard`);
- `AlarmeTab` unverändert und vollständig, inklusive Alarm für amtliche Warnungen, Radar (Orte) und der nur lesenden Alarmstufen-Tabelle.

Diese drei Alarm-Teile wandern erst in Teil-PR 3 nach Wetter; in Teil-PR 2 bleiben sie in Zustellung, damit nichts verschwindet und PR #2872 nicht kollidiert.

### 4. Reiter `wetter` im Hub

Panel mit `WeatherMetricsTab` (`bereich=wetter`) und darunter die bestehende nur lesende Wertebereiche-Ansicht (`CorridorEditor` bzw. `CorridorEditorMobile`), bis Teil-PR 3 sie ersetzt. Der Hub mountet je Reiter per if-Kette (Trip) bzw. nach dem bisherigen Hydrations-Gate (Vergleich); nie zwei WMT-Instanzen zugleich.

### 5. Anlege-Ketten

- **Trip:** route · etappen · wegpunkte · wetter · zustellung (`TabId`, `TAIL`, `PROGRESS_STEPS`). EINE dauerhafte WMT-Instanz (Muster #932, `style:display`), deren `bereich` dem aktiven Schritt folgt. Der `CorridorEditor` (createMode) hängt im Schritt `wetter` unter der Metrik-Auswahl und bleibt dauerhaft gemountet, damit die Vorbelegung (`handleVorbelegungFertig`, `corridors` im Payload) wie bisher läuft; „Mit Standardwerten speichern“ wartet weiter auf `wertebereicheVorbelegt`.
- **Vergleich:** vergleich · orte · wetter · zustellung als if-Kette mit Wizard-State wie heute.
- `anlegeLockEngine.ts`: `letzterId='zustellung'`; `infoboxKeys.ts` auf neue Kennungen.

### 6. Flush, Hydration, Badges

- Trip `TripTabs.svelte`: Flush-Liste (`saveController.flush()` beim Reiterwechsel) enthält `wetter` und `zustellung` statt der alten Kennungen.
- Vergleich: `SELBST_SPEICHERNDE_VERGLEICH_REITER` und die Lazy-Hydration in `CompareTabs.svelte` hängen an `wetter`/`zustellung`.
- Speicher-Owner-Strings `'wetter-metriken'`, `'wetter-metriken-report-config'`, `'versand'`, `'alarme'`, `'wertebereiche'` werden **nicht** umbenannt (Speicherweg wie vorher, AC-8).
- Badge Wertebereiche entfällt; Etappen/Orte-Badge bleibt.

### 7. Reiterleiste nach Soll (§2 Gesamt-Spec)

Nach Merge von PR #2871 verbleibend: aktiver Reiter 600, Badge Mono 10 px neutral; `data-slot="segmented"`/`segmented-badge` in `MTabBar.svelte` und die Segmented-Box `app.css:502–528` entfallen. Mobil bleibt die Pill-Form.

### 8. Sprungziele und i18n

- Nur Kennungen nachziehen: `hubUebersichtModell.ts`, `HubOverview.svelte:152`, `WeatherSummaryCard.svelte:29`, `AlertPreviewCard.svelte:71`, `routes/+page.svelte`, `routes/trips/+page.svelte`, `routes/compare/+page.svelte`, `routes/compare/[id]/+page.svelte:370` (`?tab=wetter-metriken#versand` → `zustellung#versand`). Inhalte U3/U4/K17/X1 bleiben Teil-PR 4.
- Neue Katalog-Schlüssel `aktionen.reiter.wetter` (DE „Wetter“, EN „Weather“) und `aktionen.reiter.zustellung` (DE „Zustellung“, EN „Delivery“). Bestehende `aktionen.weather`/`aktionen.alarms` bleiben fürs Aktionsmenü. Protokoll-Token bleiben unübersetzt (ADR-0104).

### 9. Testumzug

Kennungen umstellen; Tests, die ausschließlich entfallene Reiter prüfen, werden gelöscht statt umgebogen. Redirect-Tests (`hub-reiter-alt-kennungen-umleitung.spec.ts`, `issue_1273_s3_redirect_links.test.ts`) behalten die Alt-Kennungen als Eingabe. Tests, die `'wertebereiche'` nur als Speicher-Owner nutzen, bleiben unberührt. Golden-Prüfstände f9/f10/f3/f7 werden nachgezogen.

## Expected Behavior

- **Input:** Aufruf von Hub oder Anlege-Kette, auch über alte Adressen (`?tab=…`, `#versand`); Bedienung der Reiter Wetter und Zustellung.
- **Output:** vier Reiter nach Soll; Zustellung zeigt alle 16 Inventar-Elemente; Wetter zeigt die bisherige Metrik-Oberfläche (ohne Zustellungs-Blöcke) plus nur lesende Wertebereiche; Anlege-Ketten mit den neuen Schritten.
- **Side effects:** keine. Gespeicherte Daten und Speicherwege bleiben gleich; Adresszeile wird bei Alt-Kennungen bereinigt.

## Acceptance Criteria

ACs AC-1 bis AC-8 und AC-36 sind wörtlich aus der freigegebenen Gesamt-Spec übernommen; einzige Abweichung ist die Klammer in AC-36 (siehe Changelog). AC-2.T1 bis AC-2.T4 sind technische Absicherungen ohne neue fachliche Anforderung.

- **AC-1:** Given ein Trip / When der Nutzer den Hub öffnet / Then stehen genau die Reiter Übersicht · Etappen · Wetter · Zustellung in der Leiste (kein Reiter Wertebereiche, Alarme oder Wetter-Metriken), auf Deutsch und auf Englisch
  - Test: Playwright auf Staging, Reiter-Liste je Sprache; `node --test` auf `REITER_DEFINITION` (Trip) ohne Mocks.

- **AC-2:** Given ein Orts-Briefing / When der Nutzer den Hub öffnet / Then stehen genau die Reiter Übersicht · Orte · Wetter · Zustellung in der Leiste, der Badge am Reiter Orte zeigt die Zahl der Orte
  - Test: Playwright auf Staging mit einem Orts-Vergleich mit drei Orten; `node --test` auf die Definition (Vergleich).

- **AC-3:** Given der Hub eines Trips oder Orts-Briefings am Desktop / When der Nutzer die Leiste ansieht / Then hat sie genau eine Grundlinie, der aktive Reiter ist 600 stark mit 2px-Unterstrich in der Akzentfarbe, und Badges sind kleine neutrale Mono-Marken (keine orangen Kreise, keine Segmented-Box)
  - Test: Playwright mit gemessenen Stilen (Unterstrich-Höhe, Badge-Hintergrund, kein `data-slot="segmented"` an der Leiste) plus Fresh-Eyes-Abgleich gegen `current/soll/*.png`.

- **AC-36:** Given der Hub eines Trips und eines Orts-Briefings am Desktop (Breite ≥ 1024 px) / When der Nutzer den Seitenkopf ansieht / Then hat die Seitenüberschrift (h1) eine berechnete Schriftgröße zwischen 30 und 38 px (Soll Atomic Design; Regressionswächter: am Desktop heute bereits 38 px gemessen), in beiden Kontexten aus demselben Kopf-Baustein; mobil bleibt die Überschrift im Soll der mobilen Kopfzeile
  - Test: Playwright auf Staging misst `getComputedStyle(h1).fontSize` je Kontext am Desktop und im Mobil-Viewport; Fresh-Eyes-Abgleich gegen `current/soll/*.png`.

- **AC-4:** Given ein Mobilgerät (schmale Breite) / When der Nutzer einen Hub öffnet / Then zeigt die Leiste weiter die Pill-Form mit denselben vier Reitern und alle vier sind erreichbar
  - Test: Playwright im Mobil-Viewport, vier Reiter antippbar; Pill-Stil unverändert (bestehender MTabBar-Test bleibt grün).

- **AC-5:** Given Lesezeichen mit den alten Adressen / When `?tab=wetter-metriken`, `?tab=wertebereiche` oder `?tab=layout` geöffnet wird / Then landet der Nutzer im Reiter Wetter, und bei `?tab=alarme` oder `?tab=versand` (auch `#versand`) im Reiter Zustellung, jeweils für Trip und Orts-Briefing, und die Adresszeile zeigt danach die neue Kennung
  - Test: Playwright-Tabelle aller fünf alten Kennungen je Trip und Vergleich; `node --test` auf `resolveTab`/`bereinigteTabAdresse`.

- **AC-6:** Given der Nutzer legt einen Trip über `/trips/new` bzw. ein Orts-Briefing über `/compare/new` an / When er durch die Schritte geht / Then lauten die Schritte beim Trip Route · Etappen · Wegpunkte · Wetter · Zustellung und bei Orten Vergleich · Orte · Wetter · Zustellung, kein Schritt führt auf einen entfallenen Reiter, und der angelegte Trip bzw. Vergleich ist danach vollständig gespeichert
  - Test: Playwright auf Staging, beide Anlege-Ketten bis zum Speichern; Datei-/API-Zustand des neuen Abos.

- **AC-7:** Given ein Trip mit gesetzten Alarm- und Versand-Einstellungen vor dem Umbau / When der Nutzer den Reiter Zustellung öffnet / Then ist jedes der 16 Bedienelemente aus dem Inventar (Alarm-Kanäle und Dringlichkeit je Kanal, Kanal je Wettergröße, Telegram-Kurzstil, Cooldown, Stille Stunden, Briefing-Kanäle, Morgen/Abend mit Uhrzeit, Mehrtages-Trend, Laufzeit, Aktivieren, Mail-Inhalt, Layout je Kanal, 3-Tages-Ausblick, Nacht-Block, Stundenverlauf, Beispiel-Warnung) vorhanden, zeigt seinen gespeicherten Wert, und das Gleiche gilt im Orts-Briefing für die dort vorhandenen Elemente
  - Test: Playwright auf Staging, Bedienelement-Liste je Kontext gegen das Inventar (festgeschrieben als Testdaten, abgeleitet aus dem Stand vor dem Umbau).

- **AC-8:** Given der Reiter Zustellung / When der Nutzer einen Wert ändert (z. B. Cooldown, Stille Stunden, Briefing-Uhrzeit, Alarm-Kanal) und speichert / Then bleibt der Wert nach Neuladen erhalten, wirkt über denselben Speicherweg wie vor dem Umbau, und alle anderen gespeicherten Felder des Abos (Ampel, Etappen, Orte) bleiben unverändert
  - Test: Playwright auf Staging mit Datei-/API-Vergleich vorher/nachher je Feld, Trip und Vergleich.

### Technische Absicherung (keine neue fachliche Anforderung)

- **AC-2.T1:** Given die Speicher-Owner `'wetter-metriken'`, `'wetter-metriken-report-config'`, `'versand'`, `'alarme'` und `'wertebereiche'` / When der Nutzer im Reiter Zustellung oder Wetter einen Wert ändert und speichert / Then erzeugt das Speichern denselben Request (gleiche Adresse, gleicher Besitzer, gleiche Felder) wie vor dem Umbau, und die fünf Owner-Strings kommen unverändert im Code vor
  - Test: `node --test` ohne Mocks: Wächter auf die fünf Owner-Strings an ihren Speicher-Aufrufen; Playwright auf Staging vergleicht den Request je Feld vorher/nachher in zwei Konten.

- **AC-2.T2:** Given Hub und Anlege-Kette von Trip und Orts-Briefing / When der Nutzer durch die Reiter bzw. Schritte wechselt / Then ist zu jedem Zeitpunkt höchstens eine `WeatherMetricsTab`-Instanz gemountet, sodass keine zwei Instanzen einander mit veraltetem Stand überschreiben
  - Test: `node --test` (AST-Wächter über alle WMT-Einbettungen, inklusive des bestehenden Wertprops-Wächters) plus Playwright, das nach jedem Reiter- bzw. Schrittwechsel die Zahl der WMT-Wurzelknoten im DOM zählt.

- **AC-2.T3:** Given ungespeicherte Änderungen in Wetter oder Zustellung / When der Nutzer den Reiter wechselt / Then werden die Änderungen gesichert (Trip: Flush-Liste in `TripTabs.svelte`, Vergleich: `SELBST_SPEICHERNDE_VERGLEICH_REITER`), und die Lazy-Hydration des Vergleichs greift unter `wetter` und `zustellung`, sodass nach dem Wechsel und Neuladen nichts verloren ist
  - Test: `node --test` auf beide Listen und die Hydrations-Bedingungen; Playwright auf Staging: Wert ändern, Reiter wechseln, Neuladen, Wert vergleichen, je Trip und Vergleich.

- **AC-2.T4:** Given das Anlegen eines Trips ohne eigenen Wertebereiche-Schritt / When der Nutzer „Speichern“ oder „Mit Standardwerten speichern“ wählt / Then enthält das neue Abo weiterhin die Wertebereiche-Vorbelegung (`corridors`), und „Mit Standardwerten speichern“ wartet weiter, bis `wertebereicheVorbelegt` gesetzt ist
  - Test: Playwright auf Staging: Trip über `/trips/new` anlegen, gespeicherte Abo-Datei auf `corridors` prüfen; `node --test` auf die Wartebedingung in `tripNewLogic.ts`.

## Test Plan

### Automated Tests (TDD RED)

- [ ] **Kern-Schicht Frontend (`node --test`, kein Vitest):** `REITER_DEFINITION` (Trip, Vergleich, Hub und Anlege-Kette); `resolveTab` und `bereinigteTabAdresse` für alle Alt-Kennungen inklusive `#versand`; `weatherMetricsTabSections` je `bereich` (disjunkt, Vereinigung = alles); Flush-Listen und `SELBST_SPEICHERNDE_VERGLEICH_REITER` enthalten `wetter` und `zustellung`; Wächter „Speicher-Owner-Strings unverändert“ (AC-2.T1); Wächter „höchstens eine WMT-Instanz“ (AC-2.T2); Anlege-Ketten und Wartebedingung `wertebereicheVorbelegt` (AC-2.T4); Katalog-Parität der neuen Schlüssel DE/EN.
- [ ] **Golden-Prüfstände:** f9, f10, f3, f7 auf die neuen Kennungen nachziehen (SSR-Render ohne Mocks).
- [ ] **RED zuerst aus Nutzersicht:** AC-1 bis AC-8 und AC-36 werden vor der Umsetzung rot nachgewiesen (AC-36 ist als Regressionswächter schon grün und wird als solcher registriert); Artefakte im Workflow.
- [ ] **Mutations-Gegenprobe (Adversary), jede Verfälschung muss einen Test rot machen:** Umleitung `alarme` → `wetter` statt `zustellung`; fehlende Kennung in der Flush-Liste; umbenannter Owner-String; zweite WMT-Instanz; Anker `#versand` landet in `wetter`; Corridor-Vorbelegung fehlt im Anlege-Payload.

### Live-E2E (nur `/e2e-verify` gegen Staging)

- [ ] Playwright Desktop und Mobil, beide Kontexte (Trip und Orts-Briefing), Deutsch und Englisch, für AC-1 bis AC-8 und AC-36, mit Datei- bzw. API-Zustand vorher/nachher.
- [ ] Zwei-Konten-Lauf für den Speicherweg von AC-8 und AC-2.T1.
- [ ] Fresh-Eyes-Abgleich der Screenshots gegen `current/soll/*.png` (AC-3, AC-36).

## Definition of Done

- [ ] AC-1 bis AC-8, AC-36 und AC-2.T1 bis AC-2.T4 grün in ihrer Schicht; Kern-Schicht zu 100 % grün, alle 6 CI-Checks grün.
- [ ] PR #2871 und PR #2872 vor der Umsetzung gemergt, Arbeitsstand danach auf `origin/main` rebased.
- [ ] Kein Bedienelement aus dem 16-Punkte-Inventar verschwunden (AC-7 grün, beide Kontexte).
- [ ] Adversary-Verdict VERIFIED inklusive Mutations-Gegenprobe (alle sechs Mutationen aus dem Test Plan rot).
- [ ] `/e2e-verify` auf Staging grün, Prod-Deploy mit Selftest Exit 0.
- [ ] Gesamt-Spec `feat_2794_s3a_reiter_wetter.md` (Lieferplan Teil-PR 2) und betroffene Specs mit Status-Hinweis nachgezogen; Issue #2794 bleibt offen bis Teil-PR 4.

## Known Limitations

- **Zustellung ist ein Übergangsreiter:** Er zeigt bis S3b die heutigen Bausteine in der heutigen Reihenfolge, noch nicht die Kanal-Tabelle.
- **Alarm-Teile bleiben bis Teil-PR 3 in Zustellung:** Alarm für amtliche Warnungen, Radar (Orte) und die nur lesende Alarmstufen-Tabelle wandern erst mit Teil-PR 3 nach Wetter.
- **Wetter zeigt bis Teil-PR 3 die alte Metrik-Oberfläche** (ohne Zustellungs-Blöcke) plus die nur lesende Wertebereiche-Ansicht.
- **Übersicht und Listen-Texte erst Teil-PR 4:** Inhalte U3/U4/K17/X1 werden nicht in diesem PR angefasst, es ändern sich nur Sprung-Kennungen.
- **Reihenfolge der PRs:** Die Implementierung beginnt erst, wenn PR #2871 und PR #2872 gemergt sind; danach Rebase auf `origin/main`.
- **Kein Mail-Validator-Lauf nötig:** Mail-Inhalt und Renderer ändern sich nicht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (ADR-0109 und ADR-0106 tragen die Entscheidung; ADR-0097 Punkt 1 wird durch ADR-0109 präzisiert).
- **Rationale:** Die Reiterstruktur ist entschieden. Dieser Teil-PR setzt sie ohne neue Speicherwege um; `bereich` ist ein reiner Darstellungsfilter innerhalb der bestehenden Komponente.

## Changelog

- 2026-11-09: v1.0 Entwurf (Phase 3). Grundlage: Gesamt-Spec `feat_2794_s3a_reiter_wetter.md` und Analyse `docs/context/feature-2794-s3a-teil2-leiste.md`. AC-1 bis AC-8 und AC-36 wörtlich übernommen; technische Zusatz-ACs AC-2.T1 bis AC-2.T4 ergänzt.
- 2026-11-09: AC-36-Prämissenkorrektur. Die Klammer „heute 20 px“ wurde durch „Regressionswächter: am Desktop heute bereits 38 px gemessen“ ersetzt. Begründung (Analyse-Befund 1, Staging-Messung 2026-11-09): Trip- und Vergleichs-Hub haben am Desktop bereits eine h1 von 38 px; die 20 px stammen von den Anlege-Seiten (`/trips/new`, `/compare/new`) bzw. von der mobilen Kopfzeile. Die Akzeptanz (30 bis 38 px am Desktop, beide Kontexte aus demselben Kopf-Baustein, mobil unverändert) bleibt gleich; AC-36 wird als Regressionswächter umgesetzt.
