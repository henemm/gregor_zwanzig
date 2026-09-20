---
entity_id: rework_2276_s6a_totcode_und_ratsche
type: refactor
created: 2026-09-20
updated: 2026-09-20
status: draft
version: "1.0"
tags: [compare, trips, persistenz, totcode, ratsche]
---

# Totcode-Rückbau und HERKUNFT-Zweig-Ratsche (Issue #2276, Scheibe S6a, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Letzte Etappe von #2276 (Epic #2345, Etappe P1) ist S6 — die Auflösung der
verbliebenen Klebeschicht zwischen Ortsvergleich-Hub und den sechs geteilten
Reiter-Bausteinen unter `frontend/src/lib/components/shared/`. S6 ist zu
groß für eine Scheibe und wird analog S1–S5 in Unter-Scheiben S6a–S6f
zerlegt (Analyse `docs/context/rework-2276-s6-rueckbau.md`, Abschnitt
„Antwort auf F6"). **Diese Spec beschreibt ausschließlich S6a.**

S6a legt das Messfundament, auf dem die Zusicherung von Issue-AC-2 in den
folgenden Scheiben ruht: Sie entfernt nachweislich unerreichten Code
(Totcode, Befund 5 der Analyse) und friert die heutige Zahl der
`context ===`/`context !==`-Verzweigungen unter `shared/` als benannte
`Datei:Zeile`-Liste in einem Wächter-Test ein. Erst mit dieser Ratsche lässt
sich in S6b–S6f nachweisen, dass eine Verzweigung wirklich **entfernt**
statt nur verschoben wurde. S6a rührt keinen Speicherweg, keinen `$effect`
und keine Prop-Verdrahtung an — sie ist reiner Rückbau plus Messwerkzeug,
verhaltensneutral in jeder Hinsicht.

## Source

- **File (Frontend):**
  `frontend/src/lib/components/compare/compareWizardState.svelte.ts`,
  `frontend/src/lib/components/compare/__tests__/wizard_state_no_legacy_save.test.ts`,
  `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`,
  `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts`,
  `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts`,
  `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts`,
  `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts`
- **Identifier:** `CompareWizardState.saveComparePreset()` (entfällt),
  `export type SaveStatus` in `compareWizardState.svelte.ts` (entfällt),
  `includeHourly`/`subscriptionId`/`subscriptionEnabled`/`existingDisplayConfig`
  (entfallen), neue Ratsche `context_herkunft_zweige_eingefroren.test.ts`

Betroffene Schicht: ausschließlich **Frontend**
(`frontend/src/lib/components/`). Kein Go-API- und kein Python-Core-Code in
dieser Scheibe.

## Nicht in dieser Scheibe

S6 zerfällt in sechs Unter-Scheiben (Analyse, Abschnitt „Antwort auf F6").
Diese Spec deckt **ausschließlich S6a**. Die folgenden Scheiben sind
Ausblick ohne eigene ACs an dieser Stelle — kein Vorgriff:

| Scheibe | Inhalt | Status |
|---|---|---|
| **S6b** | Wetter-Metriken + Layout, einschließlich `CompareHourlyLayoutControls` | offen, eigene Spec folgt |
| **S6c** | Alarme | offen, eigene Spec folgt |
| **S6d** | Wertebereiche: `CorridorEditor` + `CorridorEditorMobile` gemeinsam (Doppel-Mount, paarweise identisch) | offen, eigene Spec folgt |
| **S6e** | Versand | offen, eigene Spec folgt |
| **S6f** | `compareWizardState`/Bridge aus dem Hub entfernen, AC-2/AC-4-Bilanz, Schlangen-Entscheid dokumentieren | offen, eigene Spec folgt |

Insbesondere **kein Vorgriff auf #2277** (Anlege-Editor, Etappe P2) — S6a
ändert an `/compare/new` nichts. Der Eigentums-Umbau (Wertprop-Umstellung,
Weg (c) aus der Analyse) ist **nicht** Teil von S6a.

## Abweichung vom Ticket-AC-2

Die Ticket-Fassung von AC-2 lautet sinngemäß: „Nach dem Umbau verbleiben in
`shared/` nur noch fachliche Verzweigungen." Das ist **nicht erfüllbar**.

Der eingefrorene Zählbefehl (Abschnitt „Eingefrorener Zählbefehl" unten)
liefert beim Stand `73f504c9` **69 produktive Verzweigungsstellen**. Davon
sind nach Befund 1 der Analyse **11 Stellen reine
Beschriftungs-/Sichtbarkeitsunterschiede ohne eigenen Datenweg**
(Kategorie DARSTELLUNG — z. B. eine kontextabhängige Überschrift oder
DOM-Id) und fallen bei diesem Umbau **nicht** weg, weil sie nichts mit dem
Speicherweg zu tun haben, den S6 auflöst. Die Ticket-Fassung würde also
strukturell nie erreichbar sein — die Scheibe bliebe an ihrer eigenen
Zusicherung blockiert (Analyse, Risiko 4).

**Freizugebende Neufassung (PO-Freigabe erforderlich):**

> **AC-2 (neu, gilt für S6, nicht nur S6a):** Nach Abschluss von S6 enthält
> `frontend/src/lib/components/shared/` **keine HERKUNFT-Verzweigung**
> mehr — keine Stelle, die allein danach unterscheidet, woher ein Wert
> gelesen oder wohin er geschrieben wird (`wiz`/`ws` vs. `trip`-Prop,
> Vergleichs-Speicherweg vs. `saveController.schedule`). Verbleibende
> Verzweigungen sind ausschließlich FACHLICH (echter Sachunterschied) oder
> DARSTELLEND (nur Beschriftung/Sichtbarkeit, kein Datenweg-Unterschied)
> und einzeln mit Grund gelistet. Der Nachweis ist mechanisch reproduzierbar
> über den eingefrorenen Zählbefehl.

Diese Neufassung wird **in S6a nur begründet und dokumentiert**, nicht
erfüllt — S6a entfernt keine HERKUNFT-Verzweigung, sie schafft nur das
Messwerkzeug (die Ratsche), mit dem S6b–S6f ihren jeweiligen Fortschritt
gegen genau diese Liste nachweisen. **AC-4** bleibt unverändert wie im
Ticket formuliert (kein produktiver Importeur von `compareHubWizardBridge.ts`
mehr) und wird ebenfalls erst in S6f erreicht.

## Eingefrorener Zählbefehl

Grundlage von AC-2 (Bezugsgröße ist die `Datei:Zeile`-Liste im Anhang, nicht
die Zahl allein):

```
cd frontend/src/lib/components/shared && \
  grep -rn 'context ===\|context !==' . --include='*.svelte' --include='*.ts' \
  | grep -v __tests__ | grep -vE ':\s*(\*|//|/\*)'
```

**Erneut ausgeführt am 2026-09-20 beim Stand `73f504c9`** (Verifikation
dieser Spec, unabhängig von der Phase-1/Phase-2-Messung): **69 produktive
Fundstellen**, deckungsgleich mit der Analyse. Die vollständige Liste steht
im Anhang.

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | MODIFY | Totcode entfernen: `saveComparePreset()` (Z. 194–235, verifiziert — null Aufrufer außerhalb der Klasse), `export type SaveStatus` (Z. 12, null externe Importeure; kollidiert namentlich mit der unabhängigen Store-Klasse `SaveStatus` aus `$lib/stores/saveStatusStore.svelte.ts`, die von ~15 anderen Dateien importiert wird — verifiziert), `subscriptionId`/`subscriptionEnabled` (Z. 20–21), `existingDisplayConfig` (Z. 23), `includeHourly` (Z. 111) — alle vier nur deklariert, verifiziert null Referenzen außerhalb ihrer eigenen Deklarationszeile im gesamten `frontend/src` |
| `frontend/src/lib/components/compare/__tests__/wizard_state_no_legacy_save.test.ts` | MODIFY | Nur der **dritte** Test (`behaelt saveNewPreset() und saveComparePreset()`, Z. 47–56) wird angepasst: die Assertion auf `saveComparePreset` entfällt, `saveNewPreset` bleibt gefordert. Test 1 (Z. 27–34, `save()`) und Test 2 (Z. 36–43, `toggleEnabled()`) bleiben **unangetastet** — sie bewachen weiterhin #1250 |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Tote Bedingung Z. 577 ersatzlos vereinfachen: `if ((context === 'vergleich' || context === 'route') && !compareCatalogLoaded)` — `context` ist ein `'route' \| 'vergleich'`-Union, die Disjunktion ist für beide Werte wahr, verifiziert. Wird zu `if (!compareCatalogLoaded)` |
| `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts` | MODIFY | Kommentar-Nennung von `buildHubPutPayload` (Z. 72) ohne Aufruf bereinigen |
| `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts` | MODIFY | Kommentar-Nennung von `buildHubPutPayload` (Z. 118) ohne Aufruf bereinigen |
| `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | MODIFY | Kommentar-Nennung von `buildHubPutPayload` (Z. 58) ohne Aufruf bereinigen |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | MODIFY | Vier Kommentar-Nennungen von `buildHubPutPayload` (Z. 12, 134, 228, 344) ohne Aufruf bereinigen |
| `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | CREATE | Neue Ratsche: hält die 69 `Datei:Zeile`-Fundstellen des Anhangs als **eingefrorenes** Array (kein Verzeichnis-Scan zur Laufzeit), vergleicht sie mit dem tatsächlichen Ergebnis des eingefrorenen Zählbefehls (via `node:child_process`, `execSync`, gleicher Befehl wie oben, `cwd` relativ zur Testdatei aufgelöst) — Soll-Ist-Abgleich als Mengenvergleich, nicht nur Zählung |

**Korrektur gegenüber der Analyse:** Befund 5 nennt „9 Kommentar-Nennungen
von `buildHubPutPayload` in den vier `shared/*Speicherung`-Modulen". Erneute
Zählung beim Stand `73f504c9` (`grep -rn 'buildHubPutPayload' . --include='*.ts'
--include='*.svelte' | grep -v __tests__` in `shared/`, auf die vier
Module `alarmeVergleichSpeicherung.ts`, `versandVergleichSpeicherung.ts`,
`corridor-editor/wertebereicheVergleichSpeicherung.ts`,
`weather-metrics-tab/weatherMetricsCompareSave.ts` beschränkt) ergibt
**7 Kommentar-Nennungen**, nicht 9. Die Affected-Files-Tabelle oben listet
die tatsächlichen 7 Fundstellen; die Differenz ist ein Zähl-Drift der
Analyse-Phase, keine Verhaltensänderung — betrifft ausschließlich
Kommentartext, keine Testabdeckung.

Die sechs dateiinternen Signaturtypen `HubWizardFields`, `HubEdit`,
`PutQueue` (alle drei in `compare/compareHubWizardBridge.ts`),
`CompareEditorEdits`, `NewComparePresetFields` (beide in
`compare/compareEditorSave.ts`), `RehydratedActiveMetrics` (in
`compare/compareEditorLoad.ts`) bleiben **ausdrücklich stehen** — sie sind
zwar exportiert, aber ohne externe Importeure (verifiziert einzeln, mit
Ausnahme von `CompareEditorEdits`, das zusätzlich von zwei Testdateien
importiert wird); sie tragen weiterhin die Funktionssignaturen ihrer
jeweiligen Datei und werden von dieser Scheibe nicht angefasst.

## Estimated Scope

- **LoC:** ~+70/−120 (Totcode-Rückbau überwiegt zahlenmäßig; die neue
  Ratsche fügt eine mittelgroße, aber überwiegend deklarative Testdatei
  hinzu). Das Limit 250 wird voraussichtlich **nicht** überschritten.
  Falls doch: vor der Override-Ankündigung `workflow.py status` fragen,
  nicht aus der Ausschlussliste ableiten.
- **Files:** ~8 (1 Modul mit Totcode-Rückbau, 1 bestehender Legacy-Test
  angepasst, 1 Komponente mit toter Bedingung, 4 Kommentar-Bereinigungen,
  1 neue Ratsche).
- **Effort:** low.
- **Risk Level:** NIEDRIG — kein `$effect`-Wirkort berührt, keine
  Prop-Verdrahtung geändert, kein Speicher-/Datenweg angefasst. Reiner
  Rückbau von nachweislich unerreichtem Code plus ein Messwerkzeug.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompareWizardState` (`compare/compareWizardState.svelte.ts`) | class | Trägt den zu entfernenden Totcode; `saveNewPreset()` (Anlege-Pfad) bleibt unverändert bestehen |
| `wizard_state_no_legacy_save.test.ts` (Issue #1250 Scheibe 0) | test | Bestehender Wächter, dessen dritter Test präzisiert wird — Test 1+2 sind die eigentliche #1250-Zusicherung und bleiben unberührt |
| Eingefrorener Zählbefehl (`grep -rn 'context ===\|context !=='...`) | script | Bezugsgröße für AC-2 in allen S6-Unterscheiben; S6a erzeugt daraus erstmals eine benannte Liste statt einer bloßen Zahl |
| `*_laedt_keine_compare_klebeschicht.test.ts` (4 bestehende AST-Wächter) | test | Bewachen bereits AC-4 (Ladegraph); S6a führt kein Pendant für AC-2 auf Basis dieser Mechanik ein, weil AC-2 eine Grep-Ratsche braucht (Zeilen zählen), keinen Ladegraphen |

## Implementation Details

### Design-Entscheidungen

1. **Totcode-Rückbau genau im Umfang von Befund 5** — jeder Posten mit
   belegtem „null Aufrufer" (siehe Affected Files, jede Fundstelle einzeln
   gegen den echten Code verifiziert, Stand `73f504c9`). Die sechs
   dateiinternen Signaturtypen (`HubWizardFields`, `HubEdit`, `PutQueue`,
   `CompareEditorEdits`, `NewComparePresetFields`,
   `RehydratedActiveMetrics`) bleiben ausdrücklich stehen — sie tragen die
   Funktionssignaturen ihrer jeweiligen Datei und sind nicht Teil dieser
   Scheibe.
2. **Der Legacy-Save-Wächter wird nicht umgedreht, sondern präzisiert.**
   Sein Schutzziel liegt in Test 1 und 2 (`save()`/`toggleEnabled()` dürfen
   nicht zurückkehren — sie schrieben in den mit #1250 abgeschafften Store
   `/api/subscriptions`); der dritte Test ist laut eigenem Kommentar
   („Gegenprobe... darf durch Scheibe 0 NICHT rot werden") eine Gegenprobe,
   keine Kernaussage. Die Zusicherung von #1250 bleibt vollständig
   erhalten: Test 1+2 unangetastet, im dritten Test entfällt allein die
   Assertion auf `saveComparePreset`, `saveNewPreset` bleibt gefordert
   (Anlege-Pfad, `POST /api/compare/presets`).
3. **Die Ratsche hält die Liste, nicht nur die Zahl** — 69
   `Datei:Zeile`-Einträge (Anhang), im Wächter als eingefrorenes Array
   hinterlegt, **nicht** zur Laufzeit aus dem Verzeichnis berechnet. Würde
   der Wächter die Liste selbst aus dem Verzeichnis herleiten, würde ein
   versehentliches Leeren der Ist-Liste den Test vakuum-grün machen, statt
   ihn scheitern zu lassen (bekanntes Muster, s. Memory
   `ratsche_leeren_macht_den_abhaengigen_test_vakuum_gruen`). Deshalb
   vergleicht der Test die eingefrorene Soll-Liste gegen das tatsächliche
   Ergebnis des Zählbefehls zur Testlaufzeit — beide Richtungen: kein
   Soll-Eintrag darf fehlen, kein Ist-Eintrag darf zusätzlich auftauchen.
4. **Totcode-Rückbau und Ratsche in getrennten Commits** — damit ein
   Bisect zwischen „Code entfernt" und „Messwerkzeug eingeführt"
   unterscheiden kann, und damit ein Revert der Ratsche (falls sie sich als
   fehlerhaft erweist) den Totcode-Rückbau nicht mitreißt.
5. **Kein Eintrag in `.github/ci_e2e_specs.txt` nötig** — S6a rührt keinen
   `$effect`-Wirkort und keine Prop-Verdrahtung an; die SSR-Harness-Lücke
   (`generate: 'server'`, kein DOM, sieht `$effect`-Wirkorte nie) betrifft
   diese Scheibe nicht, weil sie keine reaktive Logik ändert.

## Expected Behavior

- **Input:** Kein Nutzer-sichtbares Verhalten ändert sich — S6a ist reiner
  Code-Rückbau plus ein neuer, ausschließlich intern wirkender Test.
- **Output:** `frontend`-Build und Typecheck bleiben grün; die vier
  produktiven `shared/*Speicherung`-Module referenzieren `buildHubPutPayload`
  nicht mehr in Kommentaren; `WeatherMetricsTab.svelte:577` (neue Zeilennummer
  nach dem Rückbau kann abweichen) enthält keine tautologische Bedingung mehr;
  `CompareWizardState` besitzt keine `saveComparePreset()`-Methode und kein
  `SaveStatus`-Typalias mehr.
- **Side effects:** keine — der Anlege-Pfad (`saveNewPreset()`, `POST
  /api/compare/presets`) und der Hub-Edit-Pfad über `buildComparePresetSavePayload`
  sind von dieser Scheibe unberührt, weil `saveComparePreset()` bereits vor
  dieser Scheibe null Aufrufer hatte.

## Acceptance Criteria

- **AC-1 (Totcode ist entfernt, Signaturtypen bleiben stehen):** Given der
  in Befund 5 belegte Totcode (`CompareWizardState.saveComparePreset()`,
  `export type SaveStatus` in `compareWizardState.svelte.ts`,
  `subscriptionId`/`subscriptionEnabled`/`existingDisplayConfig`/
  `includeHourly`, die tote Bedingung `WeatherMetricsTab.svelte:577`, die
  sieben Kommentar-Nennungen von `buildHubPutPayload`) / When der Rückbau
  abgeschlossen ist / Then sind alle genannten Posten aus dem Quellcode
  entfernt, die sechs dateiinternen Signaturtypen (`HubWizardFields`,
  `HubEdit`, `PutQueue`, `CompareEditorEdits`, `NewComparePresetFields`,
  `RehydratedActiveMetrics`) sind unverändert vorhanden, und `frontend`-Build
  sowie Typecheck laufen fehlerfrei durch.
  - Nachweisschicht: Kern (Build/Typecheck-Lauf; bestehende Testsuite bleibt
    grün, da der entfernte Code laut Befund 5 ohnehin unerreicht war).
  - Mutations-Gegenprobe: einen der sechs stehenbleibenden Signaturtypen
    (z. B. `HubEdit`) versehentlich mitlöschen ⇒ Typecheck schlägt fehl
    (Referenzen in `compareHubWizardBridge.ts` selbst brechen), Build rot.

- **AC-2 (Ratsche hält 69 benannte Fundstellen):** Given die neue
  Testdatei
  `shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` mit der im
  Anhang gelisteten, eingefrorenen 69-Zeilen-Liste / When der Test gegen den
  aktuellen Stand von `frontend/src/lib/components/shared/` läuft / Then ist
  der Test grün, weil die eingefrorene Liste exakt mit dem Ergebnis des
  eingefrorenen Zählbefehls übereinstimmt (Mengengleichheit, keine bloße
  Zählung).
  - Nachweisschicht: Kern (`node --test` auf die neue Datei).
  - Mutations-Gegenprobe: einen echten `context ===`-Zweig in `shared/`
    einfügen, ohne die eingefrorene Liste nachzuführen ⇒ Test rot (Ist-Menge
    enthält einen Eintrag, der nicht in der Soll-Liste steht).

- **AC-3 (Rückdreh-Gegenprobe der Ratsche):** Given die eingefrorene
  69-Zeilen-Liste in der Ratsche /
  When eine einzelne Zeile daraus künstlich aus der eingefrorenen Liste
  entfernt wird (Testdatei selbst, nicht der Quellcode) / Then wird **genau
  dieser** Wächter (`context_herkunft_zweige_eingefroren.test.ts`) rot — kein
  anderer, zufällig überlappender Test.
  - Nachweisschicht: Kern (Mutations-Lauf ist selbst Teil des
    Adversary-Nachweises dieser AC, nicht nur eine Beschreibung).
  - Mutations-Gegenprobe: ist mit der AC identisch — das Entfernen einer
    Zeile aus der eingefrorenen Soll-Liste **ist** die geforderte Mutation;
    bleibt der Test dabei grün, ist die Ratsche vakuum-artig (berechnet ihre
    Soll-Menge zur Laufzeit statt sie einzufrieren) und die AC gilt als
    nicht erfüllt.

- **AC-4 (#1250-Zusicherung bleibt vollständig erhalten):** Given
  `wizard_state_no_legacy_save.test.ts` mit drei Tests (Test 1: `save()`
  entfernt, Test 2: `toggleEnabled()` entfernt, Test 3: Gegenprobe) / When
  der dritte Test auf die Entfernung von `saveComparePreset` angepasst wird
  / Then bleiben Test 1 und Test 2 unverändert grün (sie prüfen weiterhin,
  dass `save`/`toggleEnabled` nicht auf dem Prototyp erscheinen), und Test 3
  fordert weiterhin `saveNewPreset` (Anlege-Pfad bleibt aktiv), aber nicht
  mehr `saveComparePreset`.
  - Nachweisschicht: Kern (`node --test` auf die angepasste Testdatei).
  - Mutations-Gegenprobe: `save()` versehentlich wieder in
    `CompareWizardState` einführen ⇒ Test 1 wird rot (unverändert bewacht,
    zeigt, dass die Präzisierung des dritten Tests die Schutzwirkung von
    Test 1+2 nicht geschwächt hat).

## Known Limitations

- **Vakuum-grüne Ratsche ist die Hauptgefahr dieser Scheibe.** Die
  eingefrorene Liste muss beim Schreiben der Testdatei wortgetreu aus dem
  Anhang übernommen werden, nicht aus einem Verzeichnis-Scan zur
  Testlaufzeit — sonst verliert die Ratsche ihre Schutzwirkung genau in dem
  Moment, in dem S6b–S6f beginnen, Zeilen aus der Liste zu entfernen.
- **`e2e_scope` fällt im Worktree bei jedem Commit still auf `docs-only`
  zurück** (wiederholt in S5 beobachtet) — nach **jedem** Commit dieser
  Scheibe gegenlesen, obwohl S6a keine E2E-Spec braucht: ein falsch
  gesetztes Scope-Feld wirkt sich sonst unbemerkt auf den nächsten
  `/70-deploy`-Lauf aus.
- **Testkopplung bleibt unangetastet.** ~48 Dateien importieren aus
  `compareHubWizardBridge.ts`, ~30 nutzen `createPutQueue` — beides gehört
  zu S6f, nicht zu S6a. Diese Scheibe ändert an der Bridge selbst nichts.
- **Die Kategorisierung HERKUNFT/FACHLICH/DARSTELLUNG im Anhang ist
  unvollständig, absichtlich.** Befund 1 der Analyse nennt eine
  Aggregatzahl (45/12/11/1) und benennt einzeln nur die 12 fachlichen
  Zweige plus die eine tote Bedingung. Für die verbleibenden 56 Zeilen ist
  im Anhang nur dort eine Kategorie eingetragen, wo der Code beim
  Nachlesen eindeutig der Definition folgt (z. B. ein Lesezugriff, der
  ausschließlich zwischen `wiz`/`ws` und einer lokalen Variable
  unterscheidet ⇒ HERKUNFT); der Rest ist als „unklar" markiert und bleibt
  eine Aufgabe der jeweiligen S6b–S6f-Spec, die die betroffene Zeile
  tatsächlich anfasst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Diese Scheibe trifft keine neue Architekturentscheidung —
  sie setzt die in Phase 2 der Analyse (`docs/context/rework-2276-s6-rueckbau.md`)
  bereits getroffenen Entscheidungen F2/F3/F5/F6 um, soweit sie auf S6a
  entfallen (Totcode-Rückbau, Messfundament für AC-2). Die Neufassung von
  AC-2 ist keine Architekturentscheidung, sondern eine Präzisierung der
  Ticket-Zusicherung, die als eigener Abschnitt „Abweichung vom
  Ticket-AC-2" zur PO-Freigabe steht.

## Anhang: Eingefrorene HERKUNFT-Zweig-Liste (69 Fundstellen, Stand `73f504c9`, verifiziert 2026-09-20)

Ergebnis des eingefrorenen Zählbefehls (Abschnitt oben), Kategorie nach
Befund 1 der Analyse, soweit dort einzeln benannt oder beim Nachlesen des
Codes eindeutig ableitbar; „—" markiert eine noch nicht zugeordnete Zeile
(s. Known Limitations).

| # | Datei:Zeile | Kategorie |
|---|---|---|
| 1 | `AlarmeTab.svelte:171` | HERKUNFT |
| 2 | `AlarmeTab.svelte:174` | HERKUNFT |
| 3 | `AlarmeTab.svelte:186` | HERKUNFT |
| 4 | `AlarmeTab.svelte:199` | FACHLICH — nicht-alarmfähige Größen, route strukturell leer (#1435 AC-7) |
| 5 | `AlarmeTab.svelte:216` | HERKUNFT |
| 6 | `AlarmeTab.svelte:221` | HERKUNFT |
| 7 | `AlarmeTab.svelte:243` | HERKUNFT |
| 8 | `AlarmeTab.svelte:253` | HERKUNFT |
| 9 | `AlarmeTab.svelte:280` | HERKUNFT |
| 10 | `AlarmeTab.svelte:285` | HERKUNFT |
| 11 | `AlarmeTab.svelte:345` | HERKUNFT |
| 12 | `AlarmeTab.svelte:367` | HERKUNFT |
| 13 | `AlarmeTab.svelte:379` | HERKUNFT |
| 14 | `AlarmeTab.svelte:424` | — |
| 15 | `AlarmeTab.svelte:443` | — |
| 16 | `AlarmeTab.svelte:459` | HERKUNFT |
| 17 | `AlarmeTab.svelte:467` | HERKUNFT |
| 18 | `AlarmeTab.svelte:482` | FACHLICH — Beispielwarnung mit Ort- statt Etappen-Subjekt |
| 19 | `VersandTab.svelte:284` | HERKUNFT |
| 20 | `VersandTab.svelte:294` | FACHLICH — Markup-Baum route (S5-Spec, Implementation Details Punkt 4) |
| 21 | `VersandTab.svelte:330` | FACHLICH — Markup-Baum vergleich (S5-Spec, Implementation Details Punkt 4) |
| 22 | `versandVergleichSpeicherung.ts:221` | HERKUNFT |
| 23 | `WeatherMetricsTab.svelte:545` | HERKUNFT |
| 24 | `WeatherMetricsTab.svelte:560` | HERKUNFT |
| 25 | `WeatherMetricsTab.svelte:577` | TOTE BEDINGUNG — für beide Werte des Union-Typs wahr, entfällt in S6a (AC-1) |
| 26 | `WeatherMetricsTab.svelte:589` | HERKUNFT |
| 27 | `WeatherMetricsTab.svelte:602` | HERKUNFT |
| 28 | `WeatherMetricsTab.svelte:1273` | HERKUNFT |
| 29 | `WeatherMetricsTab.svelte:1323` | FACHLICH — Metrik-Markup-Baum |
| 30 | `corridor-editor/wertebereicheVergleichSpeicherung.ts:200` | HERKUNFT |
| 31 | `corridor-editor/CorridorEditor.svelte:57` | HERKUNFT |
| 32 | `corridor-editor/CorridorEditor.svelte:79` | HERKUNFT |
| 33 | `corridor-editor/CorridorEditor.svelte:89` | HERKUNFT |
| 34 | `corridor-editor/CorridorEditor.svelte:95` | — |
| 35 | `corridor-editor/CorridorEditor.svelte:138` | HERKUNFT |
| 36 | `corridor-editor/CorridorEditor.svelte:170` | HERKUNFT |
| 37 | `corridor-editor/CorridorEditor.svelte:240` | HERKUNFT |
| 38 | `corridor-editor/CorridorEditor.svelte:268` | FACHLICH — persistierter Startwert neuer Zeilen |
| 39 | `corridor-editor/CorridorEditor.svelte:302` | — |
| 40 | `corridor-editor/CorridorEditor.svelte:315` | — |
| 41 | `corridor-editor/CorridorEditor.svelte:318` | — |
| 42 | `corridor-editor/CorridorEditor.svelte:324` | — |
| 43 | `corridor-editor/CorridorEditor.svelte:345` | — |
| 44 | `corridor-editor/CorridorEditor.svelte:474` | — |
| 45 | `corridor-editor/CorridorEditorMobile.svelte:70` | HERKUNFT |
| 46 | `corridor-editor/CorridorEditorMobile.svelte:91` | HERKUNFT |
| 47 | `corridor-editor/CorridorEditorMobile.svelte:96` | HERKUNFT |
| 48 | `corridor-editor/CorridorEditorMobile.svelte:98` | — |
| 49 | `corridor-editor/CorridorEditorMobile.svelte:126` | HERKUNFT |
| 50 | `corridor-editor/CorridorEditorMobile.svelte:151` | HERKUNFT |
| 51 | `corridor-editor/CorridorEditorMobile.svelte:207` | HERKUNFT |
| 52 | `corridor-editor/CorridorEditorMobile.svelte:234` | FACHLICH — persistierter Startwert neuer Zeilen |
| 53 | `corridor-editor/CorridorEditorMobile.svelte:297` | — |
| 54 | `corridor-editor/CorridorEditorMobile.svelte:310` | — |
| 55 | `corridor-editor/CorridorEditorMobile.svelte:313` | — |
| 56 | `corridor-editor/CorridorEditorMobile.svelte:318` | — |
| 57 | `corridor-editor/CorridorEditorMobile.svelte:330` | — |
| 58 | `corridor-editor/CorridorEditorMobile.svelte:451` | — |
| 59 | `corridor-editor/corridorEditorState.ts:297` | FACHLICH — Markieren-Schalter bei Tages-Summen nur im Trip gesperrt |
| 60 | `alarme-tab/alarmeTabSections.ts:27` | FACHLICH — Radar-Abschnitt nur im Vergleich |
| 61 | `alarme-tab/alarmeTabSections.ts:38` | DARSTELLUNG — nur Überschrifttext |
| 62 | `alarme-tab/alarmeTabSections.ts:42` | DARSTELLUNG — nur DOM-/Tab-Id |
| 63 | `versand-tab/vtBriefingChannelsText.ts:21` | — |
| 64 | `versand-tab/vtBriefingChannelsText.ts:26` | — |
| 65 | `versand-tab/VTSchedulePlan.svelte:55` | FACHLICH — Mehrtages-Trend-Karte |
| 66 | `versand-tab/VTSchedulePlan.svelte:83` | — |
| 67 | `weather-metrics-tab/weatherMetricsCompareSave.ts:534` | HERKUNFT |
| 68 | `weather-metrics-tab/weatherMetricsTabSections.ts:72` | FACHLICH — SMS-Schwellen/Report-Config nur im Trip |
| 69 | `weather-metrics-tab/weatherMetricsTabSections.ts:73` | FACHLICH — Stundenverlauf nur im Vergleich |

**Summe:** 35 HERKUNFT (verifiziert) + 12 FACHLICH (verifiziert, deckt sich
mit Befund 1) + 2 DARSTELLUNG (verifiziert) + 1 TOTE BEDINGUNG + 19 unklar
= 69. Die Aggregatzahl aus Befund 1 (45 HERKUNFT / 11 DARSTELLUNG) ist
höher bzw. niedriger als die hier verifizierten Teilmengen — die restlichen
19 „unklar"-Zeilen verteilen sich vermutlich auf beide Kategorien; eine
abschließende Zuordnung ist nicht Gegenstand von S6a und wird durch die
jeweilige S6b–S6f-Spec nachgeliefert, wenn die Zeile tatsächlich angefasst
wird.

## Changelog

- 2026-09-20: Initial spec created
