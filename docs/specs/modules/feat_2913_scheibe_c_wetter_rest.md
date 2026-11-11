---
entity_id: feat_2913_scheibe_c_wetter_rest
type: module
created: 2026-11-11
updated: 2026-11-11
status: draft
version: "1.0"
tags: [design-system, bausteine, wetter-reiter, switch, aufklapper, tagesfenster, adr-0112, epic-2791]
workflow: feature-2913-scheibe-c
issue: 2913
---

# Einstellungen neu, Reiter Wetter, Scheibe (c): „Nicht im Briefing“, Warnungen, Radar, Anpassen (#2913)

## Approval

- [ ] Approved

## Purpose

Der Wetter-Reiter von Trip und Orts-Briefing hat nach den Bausteine-Teilen 1 und 2 (`feat_2913_s3_bausteine`) noch drei Organismen, die nicht dem Mockup Fassung 3 und nicht dem Design-System-Grundsatz (ADR-0112) entsprechen: „Nicht im Briefing“ stapelt Titel und Chips untereinander, die Karte Warnungen/Radar baut ihren Schalter aus einem rohen Knopf mit Eigen-CSS, und „Anpassen“ nutzt einen rohen Knopf als Aufklapper und ein Auswahlfeld statt zweier Uhrzeitfelder. Diese Scheibe baut die vier Abschnitte (Nicht im Briefing, Amtliche Warnungen, Radar-Regen, Anpassen/Tagesfenster) lückenlos nach dem Mockup aus Atomen und Molekülen, ohne das Speichern oder die Fachlogik zu ändern. Trip und Orts-Briefing nutzen denselben Code (ADR-0097).

Grundlage: Analyse `docs/context/feature-2913-scheibe-c.md` (maßgeblich), Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` (`viewWetter()` ab Z.440, Zeilen 517–536, CSS Z.81–84, 135–145, 164–167, 196), Vorgänger-Spec `feat_2913_s3_bausteine.md` (K-6, K-7, Known Limitations verschieben `AnpassenKarte` und `WarnungenRadarKarte` in diese Scheibe), fachliche Quelle `feat_2794_s3a_teil3_wetter.md` (AC-20 Warn-Lese-Regel, AC-21 Radar nur im Vergleich bis S8 #2800).

## Source

- **Frontend (produktive Oberfläche):** `frontend/src/lib/components/{atoms,molecules,organisms}/`, `frontend/src/lib/components/organisms/wetter-tab/`, `frontend/src/lib/components/shared/WetterTab.svelte`, Wächter `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts`, i18n `frontend/src/lib/i18n/messages/{de,en}/wetter.json`.
- **Identifier:** Atom `Switch` (erweitert), neues Molekül `Aufklapper`, Molekül `UhrzeitFeld` (Stundenraster-Modus), Organismen `NichtImBriefing`, `WarnungenRadarKarte`, `AnpassenKarte`, Logik `dayWindowClamp.ts` (unverändert genutzt).
- **Nicht berührt:** Go-API, Python-Core, Logik-Module unter `shared/wetter-tab/*.ts` (`ampelSchreiben.ts`, `amtlicheWarnungen.ts`, `wetterZustand.ts` u. a.), Renderer, Alarm-Engine.

> **Schicht-Hinweis:** Reine Frontend-Arbeit (SvelteKit, `frontend/src/...`). Keine Backend-Änderung.
>
> **Trip/Ortsvergleich-Teilung (PFLICHT, #1170, ADR-0097):** Alle Bausteine liegen im Design-System und werden über `WetterTabInhalt` mit `context="route"|"vergleich"` von beiden Kontexten gemeinsam genutzt. Es entsteht keine Compare-eigene Komponente. Die Radar-Zeile erscheint nur im Kontext `vergleich` (bestehende Konstante `MIT_RADAR`, bis #2800).
>
> **Mandantentrennung:** Warnungen, Radar und Tagesfenster werden gespeichert (datenbewegend). Der Speicherweg bleibt unverändert (echte `user_id` aus dem Auth-Kontext, Read-Modify-Write, #102). Der Staging-Nachweis läuft mit zwei verschiedenen Nutzern (AC-11).
>
> **Kanäle:** Keine Änderung an Briefing- oder Alarm-Inhalt; E-Mail, Telegram, SMS und Premium-SMS sind nicht berührt. Das Schalten von Warnungen und Radar wirkt unverändert über die bestehenden Felder auf alle vier Kanäle (ADR-0095).

## Estimated Scope

- **LoC:** ca. +350/−180 (Produktivcode ca. +200/−120)
- **Files:** ca. 14 (ca. 5 Produktivdateien, Rest Tests, E2E, i18n)
- **Effort:** medium, Risiko MEDIUM (datenbewegend, drei bestehende E2E-Abläufe ziehen auf die neue Bedienung um)

## Scope

### In Scope

1. **Atom `Switch`:** optionale Props für die Testid (Default `switch`) und für eine Tapfläche von mindestens 44 px bei sichtbarer Größe 36×20 (unsichtbare Trefferfläche). Bestehende Nutzer bleiben unverändert.
2. **Neues Molekül `Aufklapper`** (Mockup `details.adv`, CSS Z.164–167): `details`/`summary`, Titel plus „＋“ (zu) bzw. „－“ (auf), `aria-expanded` gespiegelt, Testids durchgereicht, Inhalt als Snippet. Wird in Scheiben (d)/(e) wiederverwendet.
3. **Molekül `UhrzeitFeld`:** optionaler Stundenraster-Modus (Minute fest `00`, nicht editierbar, Wert `HH:00`); ohne den Modus unverändert (einziger bisheriger Nutzer `edit/StageTimeField.svelte`).
4. **`NichtImBriefing`:** eine waagrechte Zeile aus gedämpftem Label und Chips (Mockup `.more`, Z.135/136), umbrechend.
5. **`WarnungenRadarKarte`:** Zeilen aus `Einstellungszeile`, Schalter aus dem `Switch`-Atom; rohes `<button role="switch">` und `.wt-switch/.wt-track/.wt-knopf`-CSS entfallen.
6. **`AnpassenKarte`:** `Aufklapper` mit Inhalt `Einstellungszeile` „Tagesfenster“, Hinweis „Welche Stunden bewertet werden“ (neuer i18n-Schlüssel), zwei `UhrzeitFeld` im Stundenraster (Aria-Label von/bis), Clamp über `versand-tab/dayWindowClamp.ts`, Über-Mitternacht-Hinweis. `DayWindowCard` wird nicht mehr importiert.
7. **i18n DE und EN:** `wetter.anpassen.hinweis` und der Über-Mitternacht-Hinweis im `wetter`-Namensraum (heute nur `wertebereiche.tagesfenster.ueber_mitternacht`).
8. **E2E-Umzug:** die drei bestehenden Abläufe mit Select-Bedienung des Tagesfensters (`speicherung-ueberlebt-neuladen`, `daywindow-shared-both-contexts`, `daywindow-schedule-control`) und die Helfer-Map `s3a2794-teil3.helpers.ts` (`tagVon`/`tagBis`) bedienen künftig die Uhrzeitfelder.

### Out of Scope

- Radar-Zeile beim Trip (Fachlogik gehört zu #2800, S8).
- Nachbau der Mockup-Attrappe `c.off` („würde mit den Grenzen der Vorlage hinzugefügt“).
- Abschnitt „Inhalt je Kanal und Fläche“ (Mockup Z.523–532): Scheibe (d), S3b #2795.
- Löschen von `DayWindowCard` und Rückbau des nicht mehr gerenderten `WeatherMetricsTab` (eigenes Nebenbefund-Issue).
- Keine Änderung an Speicherpfad, Alarm-Engine, Renderer, Go/Python. Keine Aufstockung von `BESTAND`/`AUSNAHMEN`, kein `audit:exempt`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/adr/0112-oberflaechen-nur-aus-design-system-bausteinen.md` | ADR | Oberflächen nur aus Bausteinen, rohe Controls und Eigen-CSS verboten |
| `docs/adr/0097-trip-ortsvergleich-code-teilung.md`, `docs/adr/0035-ein-tagesfenster-fuer-trip-und-ortsvergleich.md`, ADR-0095, ADR-0104 | ADR | Trip/Orte teilen Code, Kanalparität, Zweisprachigkeit |
| `docs/specs/modules/feat_2913_s3_bausteine.md` | Spec | Vorgänger (Atome, Einstellungszeile, ChipLeiste, Wächter) |
| `docs/specs/modules/feat_2794_s3a_teil3_wetter.md` | Spec | Verhalten: AC-20 Warn-Lese-Regel, AC-21 Radar nur Vergleich |
| `atoms/Switch.svelte`, `atoms/Btn`, `atoms/Input` | Atome | Schalter, Chips |
| `molecules/{Einstellungszeile,ChipLeiste,UhrzeitFeld}.svelte` | Moleküle | Zeilen, Chip-Leiste, Uhrzeitfeld |
| `shared/wetter-tab/{wetterZustand,ampelSchreiben,amtlicheWarnungen}.ts` | Code | Zustand und Speichern, unverändert |
| `shared/versand-tab/dayWindowClamp.ts` | Code | Ende ≠ Start (ADR-0035, PO-Entscheidung #1361/#1372) |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts`, `bausteine_waechter*.test.ts` | Test/Regeln | Regel a/b, Ratschen |
| Switch-Nutzer: `AlertChannelPicker`, `ChannelRow`, `BriefingScheduleRow`, `WeatherV2Kanaele`, `KontoSheet`, Design-System-Seite | Code | müssen unverändert funktionieren |
| Backend-Felder `official_alerts_enabled`, `official_warnings`, `radar_alert_enabled`, `day_window_*_hour` (Go `internal/model/trip.go`, `compare_preset.go`; Python `src/app/trip.py`, `models.py`) | Datenmodell | unverändert |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; setzt ADR-0112 und ADR-0097 um.
- **Rationale:** Die Scheibe führt bestehende Entscheidungen aus (Bausteine aus dem Design-System, Trip/Orte teilen Code). Abgrenzungen (Radar beim Trip, `c.off`, `DayWindowCard`) folgen aus früheren Spec-Entscheidungen und sind unter Known Limitations dokumentiert.

## Affected Files

(Pfade ohne Präfix liegen unter `frontend/src/lib/components/`.)

| File | Change Type | Description |
|------|-------------|-------------|
| `atoms/Switch.svelte` | MODIFY | optionale Props Testid (Default `switch`) und Tapfläche ≥ 44 px, rückwärtskompatibel |
| `molecules/Aufklapper.svelte` | CREATE | `details`/`summary`, ＋/－, `aria-expanded`, Testids, Snippet-Inhalt |
| `molecules/UhrzeitFeld.svelte` | MODIFY | optionaler Stundenraster-Modus (Minute fest 00) |
| `molecules/index.ts` | MODIFY | Export `Aufklapper` |
| `organisms/wetter-tab/WarnungenRadarKarte.svelte` | MODIFY | `Einstellungszeile` + `Switch`, Eigen-CSS und rohes Control entfernt |
| `organisms/wetter-tab/AnpassenKarte.svelte` | MODIFY | `Aufklapper` + `Einstellungszeile` + zwei `UhrzeitFeld`, Clamp, Hinweis |
| `organisms/wetter-tab/NichtImBriefing.svelte` | MODIFY | eine waagrechte Zeile (Label + Chips) |
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json` | MODIFY | `wetter.anpassen.hinweis`, Über-Mitternacht-Hinweis |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` | MODIFY (nur falls nötig) | neues Molekül regelkonform; keine BESTAND-Senkung, keine Aufstockung |
| `organisms/__tests__/wetter_tab_{bausteine,anker_tap,barrel,i18n,ort}.test.ts`, `molecules/__tests__/*`, `atoms/__tests__/*` | CREATE/MODIFY | siehe Test Plan |
| `frontend/e2e/{speicherung-ueberlebt-neuladen,daywindow-shared-both-contexts,daywindow-schedule-control}.spec.ts`, `frontend/e2e/s3a2794-teil3.helpers.ts` | MODIFY | Tagesfenster-Bedienung von Select auf Uhrzeitfeld |
| `frontend/e2e/s3a2794-teil3-*.spec.ts` | MODIFY/CREATE | Nachweis der vier Abschnitte DE/EN, Trip und Orts-Briefing |
| `docs/design-system/COMPONENTS.md`, `docs/design-system/TOKENS.md` | MODIFY | Aufklapper, Switch-Props, Stundenraster |
| `frontend/src/routes/_design-system/+page.svelte`, `showcase.test.ts` | MODIFY | Aufklapper und Switch in der Showcase (Moleküle/Atome) |

## Implementation Details

1. **Atom/Molekül zuerst** (Muster aus Teil 2: optionale, rückwärtskompatible Props). `Switch` md ist bereits 36×20 (Mockup); ergänzt werden Testid-Durchreichung und Tapfläche ≥ 44 px (Token `--g-tap-min`). `Aufklapper` ist neu; `UhrzeitFeld` bekommt den Stundenraster-Modus.
2. **Organismen umbauen:** `WarnungenRadarKarte`, `AnpassenKarte`, `NichtImBriefing` bestehen nur noch aus Atomen und Molekülen, kein rohes `<button>`/`<input>`/`<select>`, kein Eigen-CSS wie `.wt-switch`. Die Prüf-Anker (`wetter-warnungen-schalter`, `wetter-radar-schalter`, `wetter-anpassen-karte`, `wetter-anpassen-aufklappen`, `wetter-nicht-im-briefing(-plus-<id>)`, `wetter-hinzugefuegt-meldung`) bleiben erhalten (K-7 des Vorgängers).
3. **Fachlogik unverändert:** `wetterZustand.ts`/`ampelSchreiben.ts` speichern wie bisher; Tagesfenster bleibt in ganzen Stunden (`day_window_*_hour`), Über-Mitternacht erlaubt, Ende ≠ Start per `clampDayWindowEndHour`.
4. **Warnungen:** ODER-Lese-Regel und Doppelschreiben (`official_alerts_enabled` und `official_warnings`) aus `amtlicheWarnungen.ts` bleiben.
5. **Reihenfolge:** Switch und Aufklapper und UhrzeitFeld (rot, dann grün) → Organismen → i18n → E2E-Umzug → Showcase/Doku → Wächter, `npm run check` → Staging.

## Expected Behavior

- **Input:** Wetter-Reiter in Trip oder Orts-Briefing (Hub und Anlege-Kette), DE oder EN.
- **Output:** Unter den Metriken steht „Nicht im Briefing“ als eine Zeile mit Chips; darunter Karte mit Warnungen-Schalter (und im Orts-Briefing Radar-Schalter); ganz unten ein Aufklapper „Anpassen“, der das Tagesfenster mit zwei Uhrzeitfeldern zeigt.
- **Side effects:** Keine neuen Datenfelder; Speichern wie bisher.

## Test Plan

Unit mit `node --test` (`npm test -- <datei>` im Ordner `frontend/`), Verhalten per Server-Render (`svelte/server`); keine Mocks, die nur die eigene Annahme spiegeln; Quellregeln nur mit `# doc-compliance-test`.

### Automated Tests (TDD RED)

- [ ] `atoms/__tests__/switch_testid_tap.test.ts`: GIVEN `Switch` ohne Testid-Prop WHEN gerendert THEN `data-testid="switch"`; mit Prop THEN der übergebene Wert; Rolle `switch`, `aria-checked`, Tapfläche ≥ 44 px (Token) bei sichtbarer Größe 36×20.
- [ ] `molecules/__tests__/aufklapper.test.ts`: GIVEN `Aufklapper` zu/auf WHEN gerendert THEN `details`/`summary`, „＋“ bzw. „－“, `aria-expanded` passend, Testids vorhanden, Inhalt im Snippet.
- [ ] `molecules/__tests__/uhrzeitfeld_stundenraster.test.ts`: GIVEN Stundenraster-Modus WHEN Wert `06:00` gerendert THEN Minute fest `00` und nicht editierbar; ohne Modus unverändert (Regressionsschutz `StageTimeField`).
- [ ] `organisms/__tests__/wetter_tab_bausteine.test.ts` (erweitert): die drei Organismen enthalten kein rohes `<button>`, `<input>`, `<select>` und kein `.wt-switch/.wt-track/.wt-knopf`; `NichtImBriefing` rendert Label und Chips in einer Zeile; Radar nur bei `context="vergleich"`.
- [ ] `organisms/__tests__/wetter_tab_anker_tap.test.ts` (erweitert): Anker und `data-size="tap"` der Chips bleiben.
- [ ] `organisms/__tests__/wetter_tab_i18n.test.ts` (erweitert): neuer Schlüssel in DE und EN vorhanden, beide Sprachen gleiche Schlüsselmenge, Elementliste (`docs/context/einstellungen_neu/elementliste.json`) für die vier Abschnitte lückenlos.
- [ ] `organisms/__tests__/wetter_tab_ort.test.ts` / `wetter_tab_barrel.test.ts`: Trip und Vergleich nutzen denselben Pfad; `Aufklapper` im Barrel.
- [ ] Wächter `bausteine_waechter.test.ts` und `bausteine_waechter_wirkort.test.ts` bleiben grün, kein neuer Eintrag in `BESTAND`/`AUSNAHMEN`.

### Staging (Playwright, `frontend/playwright.2794-s3a3.staging.config.ts`, seriell, Setup `fix-1895-modus-rueckbau.staging.setup.ts`)

- [ ] Vier Abschnitte in Trip und Orts-Briefing, DE und EN; Elementliste-Abgleich; Chip-Klick, Schalter, Aufklapper, Tagesfenster setzen/speichern/neu laden; zwei Nutzer.
- [ ] Umgezogene Tagesfenster-Abläufe (drei Spezifikationen aus Scope 8) grün.
- [ ] Unabhängige Bildprüfung `mockup-bildpruefer` (ADR-0112), höchstens zwei Runden.

## Definition of Done

Fertig ist Scheibe (c), wenn die vier Abschnitte „Nicht im Briefing“, Amtliche Warnungen, Radar-Regen (nur Orts-Briefing) und Anpassen/Tagesfenster im Wetter-Reiter von Trip und Orts-Briefing ausschließlich aus Design-System-Bausteinen bestehen (Wächter grün, keine rohen Controls, kein Eigen-CSS), auf Staging in DE und EN der Elementliste des Mockups lückenlos entsprechen, Warnungen, Radar und Tagesfenster für zwei verschiedene Nutzer nach Neuladen erhalten bleiben, die drei umgezogenen Tagesfenster-E2E grün sind und der `mockup-bildpruefer` nach höchstens zwei Runden keine offene Abweichung meldet (AC-1 bis AC-11). Das Nebenbefund-Issue für den Rückbau von `WeatherMetricsTab`/`DayWindowCard` ist angelegt.

## Acceptance Criteria

- **AC-1:** Given der Wetter-Reiter eines Trips oder Orts-Briefings mit mindestens einer nicht gewählten Metrik / When die Seite geöffnet wird / Then steht „Nicht im Briefing“ als eine waagrechte Zeile aus gedämpftem Label und daneben umbrechenden Chips „+ <Metrik>“, ein Klick auf einen Chip fügt die Metrik zum Briefing hinzu und zeigt die Meldung `wetter-hinzugefuegt-meldung`, und die Anker `wetter-nicht-im-briefing` und `wetter-nicht-im-briefing-plus-<id>` sind unverändert vorhanden.
  - Test: Staging-E2E klickt einen Chip und sieht die Metrik in der Liste; Unit-Render prüft Label und Chips in einer Zeile und die Anker.

- **AC-2:** Given der Wetter-Reiter eines Trips und eines Orts-Briefings / When der Warnungen-Schalter `wetter-warnungen-schalter` gesetzt und gespeichert wird / Then ist er ein Schalter-Atom mit `role="switch"` und `aria-checked`, sichtbar 36×20 Pixel mit einer Tapfläche von mindestens 44 Pixeln, und nach Neuladen bleibt der Zustand erhalten; gespeichert wird unverändert über die ODER-Lese-Regel und das Doppelschreiben (`official_alerts_enabled` und `official_warnings`) mit Read-Modify-Write ohne Verlust anderer Felder (#102).
  - Test: Staging-E2E schaltet, speichert, lädt neu und prüft Zustand und unveränderte Nachbarfelder; Unit-Render prüft Rolle, ARIA und Tapfläche.

- **AC-3:** Given der Wetter-Reiter eines Orts-Briefings / When die Karte Warnungen/Radar angezeigt wird / Then gibt es eine zweite Zeile „Radar-Regen“ mit dem Schalter `wetter-radar-schalter` (Schalter-Atom, speichert `radar_alert_enabled` wie bisher); Given der Wetter-Reiter eines Trips / When dieselbe Karte angezeigt wird / Then gibt es keine Radar-Zeile und keinen Radar-Schalter, bis #2800 geliefert ist.
  - Test: Unit-Render mit `context="vergleich"` und `context="route"`; Staging-E2E schaltet Radar im Orts-Briefing und prüft Persistenz sowie Abwesenheit beim Trip.

- **AC-4:** Given der Wetter-Reiter / When die Karte „Anpassen“ am Seitenende angezeigt wird / Then ist sie ein Aufklapper (`details`/`summary`, Zeichen „＋“ zugeklappt und „－“ aufgeklappt, `aria-expanded` entsprechend) mit den Ankern `wetter-anpassen-karte` und `wetter-anpassen-aufklappen`, ein Klick klappt den Inhalt auf und wieder zu, und zugeklappt ist der Inhalt nicht sichtbar.
  - Test: Staging-E2E klappt auf und zu und prüft Zeichen, `aria-expanded` und Sichtbarkeit; Unit-Render des Aufklappers.

- **AC-5:** Given die aufgeklappte Karte „Anpassen“ / When das Tagesfenster angezeigt wird / Then zeigt sie die Zeile „Tagesfenster“ mit dem Hinweis „Welche Stunden bewertet werden“ (neuer Katalogtext in DE und EN) und zwei Uhrzeitfeldern „von“ und „bis“ im Stundenraster (Minute fest `00`, nicht editierbar); eine Eingabe wird als ganze Stunde gespeichert (`day_window_*_hour`), ein Fenster über Mitternacht (Ende vor Start) ist erlaubt und zeigt den Über-Mitternacht-Hinweis, und ein Ende gleich Start wird per `dayWindowClamp` verhindert.
  - Test: Staging-E2E setzt 06:00–20:00 und 22:00–06:00, versucht Ende gleich Start, speichert, lädt neu und prüft Werte, Hinweis und Wegfall der Minuten-Eingabe; Unit-Render des Stundenraster-Modus.

- **AC-6:** Given die drei Organismen `NichtImBriefing`, `WarnungenRadarKarte`, `AnpassenKarte` nach dieser Scheibe / When ihre Quellen und der Bausteine-Wächter geprüft werden / Then enthalten sie kein rohes `<button>`, `<input>` oder `<select>` und kein Eigen-CSS wie `.wt-switch`, `.wt-track`, `.wt-knopf`, der Wächter (Regel a und b, Wirkort) ist grün, und das neue Molekül `Aufklapper` ist regelkonform ohne neuen Eintrag in `BESTAND` oder `AUSNAHMEN` und ohne `audit:exempt`.
  - Test: Unit-Tests der Quellregel (`# doc-compliance-test`) plus Wächter-Läufe.

- **AC-7:** Given die bestehenden Nutzer des Switch-Atoms (`AlertChannelPicker`, `ChannelRow`, `BriefingScheduleRow`, `WeatherV2Kanaele`, `KontoSheet`, Design-System-Seite) / When sie nach der Erweiterung gerendert werden / Then rendern sie unverändert mit dem Standard-`data-testid="switch"`, und nur die Wetter-Karte setzt eigene Testids.
  - Test: Unit-Render des Atoms ohne und mit Testid; bestehende Tests der Nutzer bleiben grün.

- **AC-8:** Given Sprache DE oder EN / When die vier Abschnitte angezeigt werden / Then erscheinen alle Texte (Label „Nicht im Briefing“, Warnungen, Radar, „Anpassen“, „Tagesfenster“, Hinweis, Über-Mitternacht-Hinweis, Zeichen und Aria-Labels) vollständig in der gewählten Sprache aus dem Katalog, ohne hartcodierte Nutzertexte und ohne Texte der anderen Sprache.
  - Test: Staging-E2E in DE und EN prüft sichtbare Texte; Unit-Test vergleicht die Schlüsselmengen beider Kataloge.

- **AC-9:** Given Trip und Orts-Briefing / When ihre Wetter-Reiter verglichen werden / Then nutzen beide dieselben Atome, Moleküle und Organismen über `WetterTabInhalt` mit `context="route"|"vergleich"`, es gibt keine Compare-eigene Komponente, und beide Kontexte zeigen „Nicht im Briefing“, Warnungen und „Anpassen“ identisch (Radar nur im Vergleich, siehe AC-3).
  - Test: Unit-Test `wetter_tab_ort.test.ts` (gleicher Importpfad) und Staging-E2E in beiden Kontexten.

- **AC-10:** Given die drei bestehenden E2E-Abläufe `speicherung-ueberlebt-neuladen`, `daywindow-shared-both-contexts`, `daywindow-schedule-control` und die Helfer-Map `tagVon`/`tagBis` / When sie nach dem Umbau laufen / Then bedienen sie das Tagesfenster über die zwei Uhrzeitfelder statt über Auswahlfelder, ohne dass Zusicherungen entfernt oder abgeschwächt wurden, und sind grün.
  - Test: Lauf der drei Spezifikationen gegen Staging.

- **AC-11:** Given Staging mit dieser Scheibe / When zwei verschiedene Nutzer je Warnungen-Schalter, Radar-Schalter (Orts-Briefing) und Tagesfenster ändern, speichern und neu laden / Then sieht jeder Nutzer nur seine eigenen Werte, und die Elementliste der vier Abschnitte ist gegen das Mockup lückenlos abgeglichen (DE und EN), und der unabhängige `mockup-bildpruefer` hat nach höchstens zwei Runden keine offenen Abweichungen.
  - Test: Staging-Playwright mit zwei Nutzern (Config `playwright.2794-s3a3.staging.config.ts`), Elementlisten-Abgleich, Bildprüfung.

## Known Limitations

- **Radar beim Trip** bleibt aus, bis #2800 (S8) liefert (Datenfeld am Trip, Etappen-Orte zur Uhrzeit, Nowcast-Begrenzung, Kanal-Zustellung, Mail-Validator). Ein Schalter ohne Wirkung wäre irreführend (Spec `feat_2794_s3a_teil3_wetter.md` AC-21). Der Mockup-Text „deine Etappe“ gehört zu #2800.
- **`c.off` des Mockups** (Metriken außerhalb der Vorlage mit Meldung „würde mit den Grenzen der Vorlage hinzugefügt“) wird nicht als Attrappe nachgebaut: die App zeigt bereits alle nicht gewählten Katalog-Metriken als Chips, und Vorlagen-Grenzen für Fremd-Metriken gibt es nicht (sie bekommen offene Grenzen, `alarm_ab: never`).
- **`DayWindowCard`** bleibt bestehen, solange der nicht mehr gerenderte `WeatherMetricsTab` existiert (einziger weiterer Importeur); die BESTAND-Ratsche wird nicht gesenkt. Rückbau über ein Nebenbefund-Issue.
- **„Inhalt je Kanal und Fläche“** (Mockup Z.523–532) gehört zu Scheibe (d) (S3b #2795), nicht zu dieser Scheibe.
- Das Tagesfenster kennt nur ganze Stunden (Datenmodell); das Stundenraster verhindert Datenverlust durch Rundung.

## Changelog

- 2026-11-11: Initiale Spec (draft) für Workflow `feature-2913-scheibe-c`, Issue #2913.
- 2026-11-11: Zusätzliche Hilfsmodule (Implementierung): `frontend/src/lib/components/organisms/wetter-tab/tagesfensterEingabe.ts` (Tagesfenster-Eingabelogik aus `AnpassenKarte` ausgelagert, testbar) und `warnungenRadarZeilen.ts` (Zeilenaufbau Warnungen/Radar aus `WarnungenRadarKarte` ausgelagert). Validierung: Golden-Dateien (`tests/golden/**`) um den Svelte-Scoping-Hash `svelte-i4qg81` des Atoms `Switch` nachgezogen (`<style>`-Block für die Tapfläche), sonst byte-gleich.
