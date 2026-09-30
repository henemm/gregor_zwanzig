---
entity_id: feat_2277_s2c_compare_from_vorlage
type: feature
created: 2026-09-30
updated: 2026-09-30
status: draft
version: "1.0"
tags: [compare-new, vorlage, from-param, hydration, multi-user]
---

# `/compare/new?from=<id>` — Ortsvergleich als Vorlage (Issue #2277 Scheibe S2c)

## Approval

- [ ] Approved

## Purpose

Scheibe **S2c** von #2277 (Anlege-Strecke-Konvergenz, Epic #2345) belegt die Anlege-Seite
`/compare/new` mit den Werten eines bestehenden Ortsvergleichs vor, wenn die URL
`?from=<id>` trägt. Der Nutzer bekommt eine Kopie zum Anpassen und speichert sie als
**neuen** Vergleich; das Original bleibt unverändert. Es werden nur Konfigurationswerte
übernommen, keine Identität und keine Lauf-Historie.

## Source

- **Frontend:**
  `frontend/src/routes/compare/new/+page.server.ts` (MODIFY),
  `frontend/src/routes/compare/new/+page.svelte` (MODIFY),
  `frontend/src/lib/components/compare-new/compareNewVorlage.ts` (CREATE),
  `frontend/src/lib/components/compare-new/__tests__/compareNewVorlage.test.ts` (CREATE, `node --test`),
  `frontend/e2e/compare-new-vorlage.spec.ts` (CREATE, Staging, Zwei-Nutzer)
- **Identifier:** `load` in `+page.server.ts` (neu: `vorlage`), `vorlageInZustand(preset, locations, state)`
  in `compareNewVorlage.ts`

> **Schicht-Hinweis:** ausschließlich **Frontend**. Kein Go-API-, kein Python-Core-Code,
> kein Schema-Eingriff. Die Nutzertrennung liefert die bestehende Go-API (`WithUser`)
> über `GET /api/compare/presets/{id}`.

## Entscheidungen

1. **Scope = nur Ortsvergleich** (Ticket-AC-4, Compare-Teil). *Abweichung vom Ticket-Zielbild
   „`?from=` gilt für beide kinds":* Der Trip-Pfad `/trips/new?from=` ist tot —
   `templateTrip` wird serverseitig geladen, aber in `trips/new/+page.svelte` nirgends
   konsumiert. Ihn zu beleben wäre ein Umbau von `TripNewEditor` (1.170 Z.) und ist eine
   eigene Scheibe. Vermerk als Checkbox-Eintrag im Sammel-Issue #1199 (siehe „Nicht im Umfang").
2. **Kein Einstiegs-Button in S2c.** *Abweichung/Hinweis:* Ein Button „Als Vorlage verwenden"
   gehört zum Aktionsmodell #2278 (Liste/Detail/Mobil, P3). Bis dahin ist `?from=` nur per URL
   erreichbar; diese Scheibe liefert die Fähigkeit, nicht den Einstieg.
3. **Name der Kopie:** `<Name> (Kopie)` — verhindert versehentliche Namensdoppelung.
4. **Nicht kopiert:** `id`, ETag, `letzter_versand`/Lauf-Historie, Aktiv-Status. `isEditMode`
   bleibt `false` (Anlege-Modus).
5. **Gelöschte Orte** der Vorlage werden herausgefiltert; bleiben weniger als 2 Orte, bleibt der
   Orte-Reiter durch die bestehende Lock-Engine (`compareNewLogic`) gesperrt.
6. **Fremde oder unbekannte ID** ⇒ leere Anlage, kein Fehler, keine Fremddaten.
7. **Sentinel-Semantik bleibt erhalten:** `null` bleibt `null`, `[]` bleibt `[]`; fehlendes
   `end_date` ⇒ `null`.
8. **Vorbelegung einmalig beim Seitenaufbau**, nicht reaktiv — spätere Eingaben werden nie
   überschrieben.

## Nicht im Umfang

- Ticket-AC-3 (Reiter-Reihenfolge, Lesart offen) und Ticket-AC-5 (Rückbau) — bleiben bei #2277.
- `/trips/new?from=` (toter Pfad, `templateTrip` unkonsumiert) — als Checkbox in #1199 vermerken lassen.
- Einstiegs-Button/-Menüpunkt „Als Vorlage verwenden" — #2278.
- Änderungen an den Hub-Hydrierern selbst (`hydrate*FromPreset`) — werden nur aufgerufen.
- Go-API, Python-Core, Datenmodell.

## Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/routes/compare/new/+page.server.ts` | MODIFY | `url` lesen; bei gesetztem `from` `GET /api/compare/presets/{id}` mit Session-Cookie (wie `routes/compare/[id]/+page.server.ts`); nicht-OK, Netzfehler oder ungültiges Format ⇒ `vorlage: null`, kein Fehler. Rückgabe um `vorlage` erweitert. |
| `frontend/src/routes/compare/new/+page.svelte` | MODIFY | Nach `new CompareWizardState()` und vor dem Rendern: bei `data.vorlage` einmalig `vorlageInZustand(...)` aufrufen (kein `$effect`). |
| `frontend/src/lib/components/compare-new/compareNewVorlage.ts` | CREATE | Reine Funktion: komponiert `hydrateHubFieldsFromPreset` (`compare/compareHubHydration.ts`), `hydrateAlarmFieldsFromPreset` (ebd.), `hydrateVersandFieldsFromPreset` (`shared/versandVergleichSpeicherung.ts`), `hydrateWeatherMetricsFromPreset`, `hydrateChannelActiveMetricsFromPreset`, `hydrateDayWindowFromPreset`, `hydrateLayoutFieldsFromPreset` (`shared/weather-metrics-tab/weatherMetricsCompareSave.ts`) und ergänzt die Felder ohne gemeinsamen Hydrierer (Name-Suffix, Region, `pickedIds` aus `location_ids` gefiltert auf vorhandene Orte, Zeitplan/Wochentag, Stundenverlauf/Ausblick-Schalter und -Metriken/-Formate, Kurzform). Überträgt **nicht** `isEditMode`. |
| `frontend/src/lib/components/compare-new/__tests__/compareNewVorlage.test.ts` | CREATE | Node-Test je Feld mit Mutations-Gegenprobe; Sentinel `null` vs. `[]`; keine Mocks der Prüflinge. |
| `frontend/e2e/compare-new-vorlage.spec.ts` | CREATE | Staging: Zwei-Nutzer-Test, Desktop + 390 px, Speichern erzeugt neuen Vergleich. |

## Estimated Scope

- **LoC (produktiv):** ca. +80 / −5; gesamt inkl. Tests ca. +150. Unter dem 250-LoC-Limit.
- **Files:** 3 produktiv, 2 Test.
- **Effort:** medium.
- **Risk Level: MEDIUM** — kein Schema-/Backend-Eingriff, aber Cross-User-Leck-Risiko und stille
  Default-Lücken bei Teil-Hydration.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/compare/presets/{id}` (Go-API) | endpoint | Liefert die Vorlage, nutzergetrennt (`WithUser`); fremde ID ⇒ 404. |
| `GET /api/locations` | endpoint | Bestehender Load; Referenzmenge für die Filterung gelöschter Orte. |
| `compareHubHydration.ts`, `versandVergleichSpeicherung.ts`, `weatherMetricsCompareSave.ts` | modules | Vorhandene Preset→Zustand-Hydrierer, unverändert wiederverwendet. |
| `CompareWizardState` (`compare/compareWizardState.svelte.ts`) | class | Ziel der Vorbelegung. |
| `compareNewLogic.ts` (Lock-Engine) | logic | Sperrt Orte-Reiter bei <2 Orten bzw. leerem Namen; unverändert. |
| `buildNewComparePresetPayload` / `saveNewPreset` | function | Create-POST aus dem Zustand; enthält `id`/ETag/`letzter_versand` strukturell nicht. |
| `feat_1301_f2a_compare_new_trip_pattern.md` | spec | Anlege-Editor Compare. |

## Implementation Details

1. `+page.server.ts`: `const from = url.searchParams.get('from')`; nur bei nicht leerem `from` ein
   Preset laden (`encodeURIComponent`). Bei `!res.ok` oder Ausnahme ⇒ `vorlage = null`. Die Seite
   darf nie an einer fehlenden Vorlage scheitern.
2. `compareNewVorlage.ts`: `vorlageInZustand(preset, locations, state)`:
   - Hub-Hydrierer aufrufen (Korridore, Profil, Idealwerte, aktive Metriken, Alarmstufen, Alarm-Felder,
     Versand, Wetter-Metriken je Kanal, Tagesfenster, Layout) und Ergebnisse auf `state` übertragen —
     das Feld `isEditMode` wird dabei **ausgelassen**.
   - `state.name = \`${preset.name} (Kopie)\``.
   - `state.pickedIds = preset.location_ids.filter(id => locations.some(l => l.id === id))`.
   - `endDate`: fehlend ⇒ `null`; `hourlyMetricKeys`, `outlookMetricKeys`, `outlookMetricFormats`:
     `null` bleibt `null`, `[]` bleibt `[]`.
3. `+page.svelte`: Aufruf einmalig im Script-Block nach der Zustandserzeugung; kein reaktiver Effekt.
4. Keine Änderung an `saveNewPreset`: der Payload entsteht aus dem Zustand, dadurch gelangen
   Identitätsfelder nie in den POST.

## Expected Behavior

- **Input:** Nutzer öffnet `/compare/new?from=<id-eines-eigenen-Vergleichs>`.
- **Output:** Der Editor steht im Anlege-Modus, alle Konfigurationsfelder der Vorlage sind belegt,
  der Name lautet `<Name> (Kopie)`. Speichern legt einen neuen Vergleich mit neuer ID an.
- **Side effects:** Ein zusätzlicher lesender Aufruf im Server-Load, nur wenn `from` gesetzt ist.
  Ohne `from` unverändertes Verhalten. Das Original wird nie geschrieben.

## Acceptance Criteria

- **AC-1:** Given ein bestehender Ortsvergleich mit gesetzten Werten für Region, Aktivitätsprofil,
  Orte, Korridore, Wetter-Metriken, Versand-Kanäle, Alarm-Einstellungen, Zeitplan, Tagesfenster,
  Stundenverlauf/Ausblick und Kurzform / When der Nutzer `/compare/new?from=<id>` öffnet / Then
  zeigt der Editor jedes dieser Felder mit dem Wert der Vorlage vorbelegt, nicht mit dem Standardwert.
  - Test: Kern — `compareNewVorlage.test.ts`, ein Testfall je Feld auf dem echten Zustand
    (`CompareWizardState`); Staging-E2E zeigt die Werte in den Reitern.
  - Mutations-Gegenprobe: pro Feld die Zuweisung in `vorlageInZustand` auslassen ⇒ der jeweilige
    Feld-Test wird rot; wird kein Test rot, ist das ein Finding.

- **AC-2:** Given ein Ortsvergleich namens „Korsika Nord" / When `/compare/new?from=<id>` geöffnet wird
  / Then lautet das Namensfeld „Korsika Nord (Kopie)".
  - Test: Kern — `compareNewVorlage.test.ts`; Staging-E2E liest das Namensfeld.
  - Mutations-Gegenprobe: Suffix entfernen ⇒ rot.

- **AC-3:** Given ein bestehender Vergleich mit ID, ETag, `letzter_versand` und Aktiv-Status / When die
  Anlege-Seite per `?from=` vorbelegt ist und der Nutzer speichert / Then enthält der Create-Request
  keine `id`, keinen ETag-/`If-Match`-Bezug, keinen `letzter_versand` und keinen übernommenen
  Aktiv-Status, und der Editor bleibt im Anlege-Modus (`isEditMode` ist `false`).
  - Test: Kern — `compareNewVorlage.test.ts` prüft `isEditMode === false` und den Payload aus
    `buildNewComparePresetPayload`; Staging-E2E beobachtet den POST-Request.
  - Mutations-Gegenprobe: `isEditMode` aus dem Hub-Ergebnis mitübertragen ⇒ rot.

- **AC-4:** Given die Vorlage verweist auf drei Orte, von denen einer inzwischen gelöscht ist / When
  `/compare/new?from=<id>` geöffnet wird / Then sind nur die zwei noch vorhandenen Orte gewählt und der
  gelöschte Ort erscheint nicht.
  - Test: Kern — `compareNewVorlage.test.ts` mit Ortsliste ohne den gelöschten Ort.
  - Mutations-Gegenprobe: Filter entfernen ⇒ `pickedIds` enthält die gelöschte ID ⇒ rot.

- **AC-5:** Given die Vorlage hat nach dem Filtern weniger als zwei vorhandene Orte / When die
  Anlege-Seite geöffnet wird / Then bleibt der Orte-Reiter gesperrt, und die Seite zeigt keinen Fehler.
  - Test: Kern — `compareNewVorlage.test.ts` zusammen mit `unlockedTabs()` aus `compareNewLogic.ts`.
  - Mutations-Gegenprobe: Mindestzahl in der Vorbelegung umgehen (z. B. Platzhalter-ID einfügen) ⇒ rot.

- **AC-6:** Given zwei verschiedene Nutzer A und B, und A besitzt einen Vergleich / When B
  `/compare/new?from=<A-ID>` öffnet, ebenso bei einer unbekannten ID / Then sieht B eine leere Anlage
  (kein Name, keine Orte, keine Werte von A), ohne Fehlerseite.
  - Test: Live-E2E Staging — `compare-new-vorlage.spec.ts` mit zwei Sitzungen; Kern —
    Server-Load-Verhalten bei nicht-OK-Antwort ⇒ `vorlage: null`.
  - Mutations-Gegenprobe: Server-Load bei nicht-OK trotzdem eine Ersatzvorlage liefern lassen
    (bzw. Cookie weglassen/vertauschen) ⇒ rot.

- **AC-7:** Given die Anlege-Seite ist per `?from=<id>` vorbelegt / When der Nutzer einen Wert ändert und
  speichert / Then entsteht ein neuer Vergleich mit neuer ID in der Liste, und der Original-Vergleich
  ist unverändert (Name, Orte, Werte, ETag).
  - Test: Live-E2E Staging — `compare-new-vorlage.spec.ts`: Original vorher/nachher lesen und
    vergleichen, Anzahl der Vergleiche +1.
  - Mutations-Gegenprobe: Speichern per PUT auf die Vorlagen-ID statt POST ⇒ Original verändert ⇒ rot.

- **AC-8:** Given `/compare/new` ohne `from` (oder mit leerem `from`) / When die Seite geöffnet wird /
  Then ist die Anlage leer wie bisher (Standardwerte, kein Namenssuffix, kein zusätzlicher
  Vorlagen-Request).
  - Test: Kern — `compareNewVorlage.test.ts` (kein Aufruf ohne Vorlage ⇒ Zustand gleich frischem
    `CompareWizardState`); Staging-E2E prüft die leere Anlage.
  - Mutations-Gegenprobe: Vorbelegung unbedingt ausführen ⇒ Zustand weicht vom Standard ab ⇒ rot.

- **AC-9:** Given eine Vorlage mit `hourly_metric_keys: []` (bewusst leer) und eine mit fehlendem Feld
  (nie eingestellt), sowie eine ohne `end_date` / When sie vorbelegt werden / Then bleibt `[]` bei
  `[]` und fehlend bei `null`, und `endDate` ist `null`.
  - Test: Kern — `compareNewVorlage.test.ts` mit `toBeUndefined()`/strikten Vergleichen, nicht
    `toBeFalsy()`.
  - Mutations-Gegenprobe: `?? []` bzw. `|| null` an der Übertragung einsetzen ⇒ Sentinel kippt ⇒ rot.

- **AC-10:** Given die Anlege-Seite ist per `?from=<id>` vorbelegt / When der Nutzer den Namen ändert
  und danach weitere Eingaben macht / Then werden diese Eingaben nicht durch die Vorlage
  zurückgesetzt (einmalige Vorbelegung).
  - Test: Live-E2E Staging — `compare-new-vorlage.spec.ts`: Name ändern, Reiter wechseln,
    Name bleibt.
  - Mutations-Gegenprobe: Vorbelegung als reaktiven `$effect` einbauen ⇒ Eingabe wird überschrieben
    ⇒ rot.

- **AC-11:** Given ein Smartphone-Viewport von 390 px Breite / When `/compare/new?from=<id>` geöffnet wird
  / Then ist die Vorbelegung (Name mit Suffix, gewählte Orte) sichtbar, es gibt keinen horizontalen
  Seitenüberlauf, und Speichern ist erreichbar.
  - Test: Live-E2E Staging — `compare-new-vorlage.spec.ts`, Projekt/Viewport 390 px und Desktop.
  - Mutations-Gegenprobe: entfällt (Sichtprüfung); Ersatz: derselbe Test bei Desktop UND 390 px muss
    beide grün sein.

## Known Limitations

- Ohne Einstiegs-Button ist `?from=` nur per URL erreichbar (Entscheidung 2, bis #2278).
- `/trips/new?from=` bleibt tot (Entscheidung 1); Erfassung in #1199.
- `/compare/new` mobil wurde bisher nie im Browser gemessen; der 390-px-Nachweis dieser Scheibe ist
  der erste.
- Hub-Hydrierer sind für den Bearbeiten-Weg geschrieben; die Komposition stützt sich darauf, dass
  ihre Rückgaben Felder ohne Seiteneffekt sind. Lücken fängt AC-1 je Feld.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Wiederverwendung der vorhandenen Hydrierer und des geteilten Anlege-Musters
  (Trip/Ortsvergleich-Code-Teilung); keine Änderung an Kanälen, Provider, Datenmodell, Auth.

## Changelog

- 2026-09-30: Initial spec created (Scheibe S2c von #2277, Epic #2345).
