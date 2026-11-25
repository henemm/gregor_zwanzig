---
entity_id: rework_3366_waisen_waechter_layout_tab
type: refactor
created: 2026-11-25
updated: 2026-11-25
status: draft
workflow: rework-3366-waisen-loeschen
version: "1.0"
tags: [frontend, waisen, ratsche, loeschen, "#3366", "#3020"]
---

# Rework #3366: Waisen-Wächter und Scheibe S2 (layout-tab, Barrels löschen)

## Approval

- [ ] Approved

## Purpose

Verwaiste Alt-Editor-Bausteine (Frontend-Dateien ohne Produktionsaufrufer) kehren nicht wieder: ein dauerhafter Waisen-Wächter unter `node --test` hält die Menge als Ratsche (darf nur kleiner werden). Als erste Löschscheibe (S2) gehen die 6 Dateien unter `layout-tab/` und 9 Barrel-Dateien (`lib/index.ts` bleibt als SvelteKit-Konvention) samt der Tests, Prüfstände, Ratschen und Katalogschlüssel, die nur sie betreffen. Für Nutzer ändert sich nichts Sichtbares.

## Source

- **File:** `frontend/src/lib/__tests__/waisen_waechter.test.ts` (neu), `frontend/src/lib/components/shared/layout-tab/` (Löschung)
- **Identifier:** Test `Waisen-Wächter` (Liste `BEKANNTE_WAISEN`, Konstante `OBERGRENZE_WAISEN`); gelöscht: `LTCapNote.svelte`, `LTChannelPicker.svelte`, `LTCutLine.svelte`, `LayoutTab.svelte`, `channelLayoutsDirty.ts`, `ltIdealRange.ts`

Schicht: ausschließlich Frontend (`frontend/src/...`) plus Testdaten und Ratschenzahlen. Kein Go-, kein Python-Produktionscode, keine Hook-Änderung (`.claude/hooks` bleibt unberührt). Trip/Vergleich-Teilung: es entsteht kein neuer Baustein; Mandantentrennung: keine Nutzerdaten betroffen; Kanäle: kein Briefing- oder Alarm-Inhalt betroffen.

## Estimated Scope

- **LoC:** Löschung ca. -405 (layout-tab) und -22 (9 Barrels) Produktionszeilen plus mitgehende Tests/Goldens/Schlüssel (nach dem Löschen messen, nicht schätzen); neu ca. +200 (Wächter samt Selbstnachweis)
- **Files:** ca. 1 neu, 15 Produktionsdateien gelöscht (6 layout-tab + 9 Barrels), dazu die mitgezogenen Testdateien, Goldens und Schlüsseldateien (genaue Zahl wird nach dem Löschen gemessen)
- **Effort:** medium

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/__tests__/waisen_waechter.test.ts` | CREATE | Wächter: transitive Erreichbarkeit ab `routes/`, Ratsche `BEKANNTE_WAISEN` mit `OBERGRENZE_WAISEN`, Selbstnachweis |
| `frontend/src/lib/components/shared/layout-tab/{LTCapNote,LTChannelPicker,LTCutLine,LayoutTab}.svelte` | DELETE | Waisen ohne Aufrufer |
| `frontend/src/lib/components/shared/layout-tab/{channelLayoutsDirty,ltIdealRange}.ts` | DELETE | Waisen ohne Aufrufer (`ltChannels.ts` lebt und bleibt) |
| `frontend/src/lib/components/email-preview/index.ts`, `components/ui/{dot,elev-sparkline,eyebrow,input,pill,segmented,topo,wicon}/index.ts` | DELETE | 9 Barrels ohne Aufrufer |
| `frontend/src/lib/index.ts` | KEEP | SvelteKit-Konventionsdatei; bleibt erhalten und steht im Wächter als begründete Ausnahme (`AUSNAHMEN`, mit Grund), nicht in `BEKANNTE_WAISEN` |
| `layout-tab/ltIdealRange.test.ts`, `layout-tab/__tests__/{channelLayoutsDirty,channelLimitModel,channelHintTextNoJudgement,layout_korridor_sprache}.test.ts`, `__tests__/LayoutTabPruefstand.svelte` | DELETE | Tests, die nur die gelöschten Dateien prüfen (je Datei nach dem Löschen per Testlauf bestätigt) |
| `layout-tab/__tests__/{f8Pruefstand.ts,f8KatalogAnker.ts}` | MODIFY | Layout-Reiter-Teil entfernen; GPX-Teil (`gpxRendern`, `f8VarianteHook.mjs`) bleibt wegen `gpx_upload_sprache` |
| `tests/golden/f8_layout_korridor/{layout_tab_route,layout_tab_vergleich,bausteine,funktionen}.{de,en}.*` | DELETE/MODIFY | Goldens des Layout-Reiters (Repo-Wurzel); `gpx_*` bleiben |
| `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts` | MODIFY | Lösch-Nachweis für die gelöschten Dateien (`GELOESCHT`) |
| `frontend/src/lib/__tests__/{bausteine_waechter_regeln.ts,ink4_waechter.test.ts}` | MODIFY | BESTAND-Einträge, `BESTAND_OBERGRENZE` und ink4-Einträge der gelöschten Dateien senken |
| `frontend/src/lib/i18n/__tests__/{keine_hartkodierten_nutzertexte,reaktivitaet_waechter}.test.ts` | MODIFY | Dateilisten kürzen, Zählung F8 neu messen |
| `frontend/src/lib/i18n/messages/{de,en}/layout.json` | MODIFY | Schlüssel ohne Verwender entfernen (`layout.kappung.schnittlinie_*`, `layout.tab.eyebrow`; Liste durch `katalog_schluessel_haben_verwender.test.ts` gemessen) |
| `frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts` und weitere Schlüssel-Verbraucher | MODIFY | Anker der entfernten Schlüssel nachziehen |
| `tests/fixtures/einstellung_gleich_mail/fallliste_editor.json` | MODIFY | Hinweistexte um Zeile 722 und 1886 ("Waise #3366", "Alt-LTCutLine") nach dem Löschen anpassen; Status bleibt ehrlich, keine Statusänderung |
| `frontend/e2e/layout-tab-route.spec.ts`, `layout-tab-vergleich.spec.ts` | DELETE (nur bedingt) | Gehören zu #3374; hier nur angefasst, wenn sie eine gelöschte Datei importieren und dadurch Build oder CI brechen; nicht auf der CI-Positivliste |

`tests/unit/ein_katalog_ausnahmen.json` und `HOECHSTSTAND` (`tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py`): Für S2 gibt es 0 Treffer, es wird nichts geändert.

Nicht angefasst: `components/molecules/EinstellTabelle.svelte` und ihr Test, `.claude/hooks`, jeder Produktionscode außerhalb der Löschmenge, die Scheiben S1 (#3383), S3 (#3385), S4 (#3384) sowie #3374 (Browser-Specs).

### Estimated Changes

- Files: ca. 1 neu, Rest Löschung/Pflege (nach Messung)
- LoC: +200 / -(ca. 427 Produktion + mitgehende Tests)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/rework-3366-waisen-loeschen.md` | doc | Analyse: 56 Waisen, Methode, Artefaktliste |
| `frontend/src/lib/i18n/__tests__/katalog_schluessel_haben_verwender.test.ts` | test | Fundmechanismus für Katalogschlüssel ohne Verwender |
| `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts` | test | Muster und Liste `GELOESCHT`/`ERHALTEN` |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` | test | Muster Literal-Obergrenze (`BESTAND_OBERGRENZE`) |
| `tests/test_altpfad_import_sperre.py` | test | Muster Ratsche mit Selbstnachweis |
| `node --test`, `svelte-check`, Vite-Build | tooling | Nachweis keine sichtbare Änderung |

## Implementation Details

**Wächter (`waisen_waechter.test.ts`).** Wurzeln: alle Nicht-Test-Dateien unter `frontend/src/routes/` sowie `frontend/src/*.ts` (hooks, service-worker). Kanten: `import … from`, `export … from`, dynamisches `import('…')`, `import.meta.glob`, `new URL(…, import.meta.url)`. Auflösung: Alias `$lib`, relative Pfade, `.js` nach `.ts`, `index.ts` (Barrels), `.svelte`. Dateien unter `__tests__/`, `*.test.ts`, `*.spec.ts` sind weder Wurzel noch Aufrufer. Die Menge aller Nicht-Test-Dateien unter `frontend/src/lib` minus Erreichbare ergibt die Waisen; `AUSNAHMEN` (`lib/index.ts`) wird herausgerechnet. Die Logik entspricht dem Analyseskript des Kontexts (Ausgangslage dort: 56 Waisen).

**Ratsche `BEKANNTE_WAISEN`.** Startliste: heutige Waisen ohne die in #3366 gelöschten (also ohne die 6 layout-tab-Dateien und die 9 gelöschten Barrels; `lib/index.ts` steht in `AUSNAHMEN`). Die Ratsche ist eindeutig: Im Test steht eine feste Konstante `OBERGRENZE_WAISEN` (Literal, Muster wie `BESTAND_OBERGRENZE` in `bausteine_waechter_regeln.ts`); zugesichert wird `BEKANNTE_WAISEN.length <= OBERGRENZE_WAISEN`, und jeder gelistete Eintrag muss tatsächlich eine Waise sein. Ein neuer Eintrag ist nur möglich, wenn jemand die Konstante sichtbar erhöht; jede Folge-Scheibe (S1, S3, S4) senkt die Konstante und streicht ihre Einträge im selben Commit wie die Löschung. Eine nicht gelistete Waise macht den Test rot; ein gelisteter Eintrag, der erreichbar geworden ist oder nicht mehr existiert, macht ihn rot mit der Meldung "aus der Liste streichen".

**Selbstnachweis.** Die Kernfunktion arbeitet auf einem übergebenen Wurzelverzeichnis; der Test legt in einem temporären Baum eine erfundene Waise (und eine über Barrel erreichbare, eine nur von einem Test importierte Datei) an und erwartet: erfundene Waise erkannt, Barrel-Durchgriff erreichbar, Test-Aufrufer zählt nicht.

**Löschung S2.** Dateien löschen, dann betroffene Testdateien benannt laufen lassen; jede neu rote Datei ist ein Umbaufall (nie `uv run pytest` ohne Dateinamen). Zahlen (`BESTAND_OBERGRENZE`, `reaktivitaet_waechter`-Zählung, Katalogschlüssel) werden nach dem Löschen gemessen und im selben Commit gesenkt; `HOECHSTSTAND`/ein_katalog bleiben unverändert (0 Treffer). Goldens des Layout-Reiters werden entfernt; GPX-Goldens bleiben unverändert.

**Lösch-Nachweis.** Die gelöschten Dateien kommen in `GELOESCHT` des Tests `trip_pfad_altfeld_loeschnachweis_3297.test.ts` (mit dem dort vorhandenen Regex-Scan auf Importe der Basisnamen). `outlookFriendlyCapability.ts` steht dort in `ERHALTEN`, ist aber eine Waise und gehört nicht zu S2: sie bleibt in `BEKANNTE_WAISEN` (Löschung in S1, #3383, mit Wechsel von `ERHALTEN` nach `GELOESCHT`); der Eintrag in `ERHALTEN` bleibt bis dahin unverändert, der Wächter verbucht sie als bekannte Waise.

## Expected Behavior

- **Input:** Quelltext von `frontend/src`.
- **Output:** Wächter grün, solange die Waisenmenge (ohne `AUSNAHMEN`) exakt `BEKANNTE_WAISEN` entspricht und deren Länge die Konstante `OBERGRENZE_WAISEN` nicht übersteigt; Löschung ohne Funktionsänderung.
- **Side effects:** Keine sichtbare Änderung für Nutzer; Ratschenzahlen und Katalog schrumpfen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Wächter rot vor der Löschung: Test `waisen_waechter.test.ts` mit Startliste ohne die 15 S2-Dateien meldet diese als neue, nicht gelistete Waisen (RED), nach der Löschung grün.
- [ ] Selbstnachweis: erfundene Waise in temporärem Baum wird erkannt; Barrel-Durchgriff und Test-nicht-Aufrufer-Regel prüfbar.
- [ ] Ratsche in beide Richtungen: nicht gelistete Waise rot; gelisteter, wieder erreichbarer oder nicht mehr vorhandener Eintrag rot mit "aus der Liste streichen"; `BEKANNTE_WAISEN.length <= OBERGRENZE_WAISEN` zugesichert.
- [ ] Lösch-Nachweis: `existsSync` der 6 + 9 gelöschten Pfade ist `false`, kein Importtreffer im Produktionscode.
- [ ] Betroffene Testdateien benannt laufen lassen: `katalog_schluessel_haben_verwender`, `paritaet_de_en`, `deutsch_unveraendert`, `bausteine_waechter`, `ink4_waechter`, `reaktivitaet_waechter`, `keine_hartkodierten_nutzertexte`, `gpx_upload_sprache`.
- [ ] Python (benannt): `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py` und `tests/unit/test_2243_playwright_loeschscheibe.py` grün, außerdem der Verweiswächter für `tests/fixtures/einstellung_gleich_mail/`.
- [ ] Gesamt: Frontend-Suite (`node --test`), Vite-Build und `svelte-check` grün.

## Acceptance Criteria

- **AC-1:** Given der Quelltext unter `frontend/src` im Zustand nach der Löschung / When der Waisen-Wächter die Erreichbarkeit ab `routes/` und `src/*.ts` (Alias `$lib`, `.svelte`/`.ts`/`.js`, Barrels, dynamische Importe, Tests nicht als Aufrufer) berechnet / Then ist die Menge der Waisen, nachdem `AUSNAHMEN` (`lib/index.ts`) herausgerechnet wurde, genau `BEKANNTE_WAISEN`, es gilt `BEKANNTE_WAISEN.length <= OBERGRENZE_WAISEN` (feste Literal-Konstante) und der Test ist grün.
  - Test: `waisen_waechter.test.ts` läuft gegen den echten Baum. Es ist ein Architektur-Wächter: er prüft den echten Importgraphen, der den Build bestimmt, und keine Dateiinhalte als Verhaltensnachweis (wie `altfeld_namen_sperre.test.ts` und `bausteine_waechter_regeln.ts`); Nutzerverhalten belegt AC-7.

- **AC-2:** Given eine neue Datei unter `frontend/src/lib`, die niemand aus `routes/` erreicht und nicht in `BEKANNTE_WAISEN` steht / When der Wächter läuft / Then wird der Test rot und nennt den Dateipfad der neuen Waise; ein neuer Eintrag in die Liste allein genügt nicht, solange `OBERGRENZE_WAISEN` nicht sichtbar erhöht wird.
  - Test: Selbstnachweis mit erfundener Waise in einem temporären Baum; der Wächter-Kern meldet genau diese Datei. Architektur-Wächter über den echten Importgraphen, kein Dateiinhalt-Check als Verhaltensnachweis; Nutzerverhalten belegt AC-7.

- **AC-3:** Given ein Eintrag in `BEKANNTE_WAISEN`, der wieder von einer Route erreichbar ist oder dessen Datei nicht mehr existiert / When der Wächter läuft / Then wird der Test rot mit der Meldung "aus der Liste streichen".
  - Test: Fixture mit wieder erreichbarem und mit nicht vorhandenem gelistetem Eintrag; beide Fälle liefern diese Meldung.

- **AC-4:** Given eine Datei, die nur von einem Test oder nur über einen Barrel von einer Route erreicht wird / When der Wächter rechnet / Then gilt sie im ersten Fall als Waise (Tests zählen nicht als Aufrufer) und im zweiten als erreichbar (Barrel wird durchlaufen).
  - Test: Fixture-Baum mit beiden Fällen, Ergebnis wird je Datei geprüft.

- **AC-5:** Given S2 ist umgesetzt / When das Dateisystem geprüft wird / Then existieren die 6 Dateien `LTCapNote`, `LTChannelPicker`, `LTCutLine`, `LayoutTab`, `channelLayoutsDirty`, `ltIdealRange` unter `layout-tab/` und die 9 gelöschten Barrel-Dateien nicht mehr, `ltChannels.ts` und `lib/index.ts` bestehen weiter, und kein Produktionscode importiert die gelöschten Basisnamen.
  - Test: `trip_pfad_altfeld_loeschnachweis_3297.test.ts` (`GELOESCHT` per `existsSync === false` plus Importscan, `ERHALTEN` als Regressionsschutz). Architektur-Wächter über den echten Importgraphen, kein Dateiinhalt-Check als Verhaltensnachweis; Nutzerverhalten belegt AC-7.

- **AC-6:** Given die Löschung der layout-tab-Dateien / When die Zahlenratschen (`BESTAND_OBERGRENZE`, Zählung in `reaktivitaet_waechter`, Katalogschlüssel de/en) geprüft werden / Then stimmen alle Zahlen mit der Messung nach dem Löschen überein, sind nur gesunken, de und en führen dieselbe Schlüsselmenge ohne Schlüssel ohne Verwender, und `HOECHSTSTAND`/ein_katalog bleiben unverändert, weil es für S2 keine Treffer gibt.
  - Test: `bausteine_waechter`, `ink4_waechter`, `reaktivitaet_waechter`, `katalog_schluessel_haben_verwender`, `paritaet_de_en`, `test_ein_katalog_eine_verarbeitung_ratsche.py` grün.

- **AC-7:** Given die Seiten und Ansichten, die den Layout-Reiter nicht verwenden (insbesondere Trip- und Vergleichs-Editor, GPX-Import) / When die gesamte Frontend-Suite, der Produktions-Build und `svelte-check` laufen / Then sind alle grün, die GPX-Texte und -Goldens sind unverändert, und für Nutzer gibt es keine sichtbare Änderung.
  - Test: Frontend-Suite per `node --test`, `npm run build`, `svelte-check`; `gpx_upload_sprache` unverändert grün.

- **AC-8:** Given `outlookFriendlyCapability.ts` ist eine Waise, wird in S2 aber nicht gelöscht / When der Wächter läuft / Then steht sie in `BEKANNTE_WAISEN` (nicht als erreichbar gewertet) und der Eintrag in `ERHALTEN` des Lösch-Nachweises bleibt bestehen, bis sie in S1 gelöscht wird.
  - Test: Wächter grün mit dieser Datei in der Liste; `ERHALTEN`-Regressionsschutz weiter grün.

## Definition of Done

- [ ] Spec freigegeben (`approved`/`freigabe`)
- [ ] RED-Nachweis: Wächter rot vor der Löschung, grün danach
- [ ] 6 layout-tab-Dateien und 9 Barrels gelöscht, mitgezogene Tests, Prüfstände, Goldens, Schlüssel, Ratschen im selben Commit gepflegt
- [ ] Zahlen nach dem Löschen gemessen und eingetragen
- [ ] Frontend-Suite, Build, `svelte-check` und die benannten Python-Ratschentests grün
- [ ] Adversary und Mutations-Gegenprobe am Wächter (Verfälschung der Erreichbarkeit wird gefangen)
- [ ] CI (6 Checks) grün, Deploy ohne sichtbare Änderung

## Known Limitations

- `frontend/src/lib/index.ts` (SvelteKit-Konvention, 1 Zeile) wird nicht gelöscht (Entscheidung Tech Lead): Sie gehört zum Gerüst des Frameworks. Der Wächter führt sie in einer eigenen, begründeten Liste `AUSNAHMEN`; diese Liste ist getrennt von der Ratsche und darf nur Konventionsdateien mit Begründung enthalten. Gelöscht werden die übrigen 9 Barrels, jeweils erst nach Messung, dass sie keinen Produktionsaufrufer haben.
- `outlookFriendlyCapability.ts` bleibt in dieser Scheibe Waise (BEKANNTE_WAISEN, im Löschnachweis 3297 weiter in ERHALTEN) und wird mit #3383 gelöscht (Entscheidung Tech Lead).
- Die Einstufung "Test prüft nur die Waise" beruht auf Import-/Titelanalyse; sie wird je Datei per benanntem Testlauf nach dem Löschen bestätigt, Mischfälle werden umgebaut statt gelöscht.
- Der Wächter ist ein statischer Importgraph: Verwendung über Zeichenketten oder externe Registries würde er nicht sehen (laut Analyse gibt es keine).
- Tote Exporte in lebenden Dateien (`versandVergleichSpeicherung.ts`, `weatherMetricsCompareSave.ts`, `metricsEditor.ts`, `ltChannels.ts`) erfasst der Wächter nicht (Dateiebene).

## Out of Scope

- Scheibe S1 (#3383, weather-metrics-tab, trip-detail, u. a. Löschung von `outlookFriendlyCapability.ts`), S3 (#3385, versand-tab) und S4 (#3384, compare/edit/mobile/utils).
- #3374 (Browser-Specs, Playwright), insbesondere `layout-tab-route.spec.ts` und `layout-tab-vergleich.spec.ts`, außer sie importieren eine gelöschte Datei und brechen Build oder CI.
- `EinstellTabelle.svelte` und ihr Test; `.claude/hooks`; Produktionscode außerhalb der Löschmenge; `ui/*`-Barrels, soweit nach Messung doch erreichbar.
- Tote Exporte in lebenden Dateien (eigenes Nachlauf-Issue).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Aufräumarbeit nach bestehender Entscheidung (Löschung von Alt-Editor-Bausteinen, #3297/#3122) plus Ratsche nach vorhandenem Muster; keine neue Entscheidungsfläche.

## Changelog

- 2026-11-25: Initial spec created
- 2026-11-25: Korrigiert nach Validierung (15 Dateien, OBERGRENZE_WAISEN, Goldens-Pfad, Architektur-Wächter-Hinweis, fallliste_editor, #3374-Abgrenzung, ein_katalog 0 Treffer)
