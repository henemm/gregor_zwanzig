# Context: rework-2276-s6d-corridor-wertprops

Issue #2276 (Epic #2345), Scheibe **S6d** — Wertebereiche/Corridor.
Stand der Erhebung: 2026-09-21, Basis-Commit `c737159e` (S6c-Merge).

## Request Summary

Die beiden geteilten Bausteine `CorridorEditor.svelte` und `CorridorEditorMobile.svelte`
lesen ihren Vergleichs-Zustand heute aus dem Svelte-Context `compare-wizard-state` und
schreiben vier Felder direkt dorthin zurück. S6d stellt sie — wie S6b (Stundenverlauf) und
S6c (Alarme) — auf **Wertprops + Rückrufe** um. Desktop und Mobil sind 1:1-Duplikate und
werden gemeinsam umgebaut (unteilbar, so im S6-Schnitt vom 20.09. festgelegt).

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` (539 Z.) | Hauptbaustein Desktop. `getContext` :57, Props-Block endet :54 |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte` (525 Z.) | 1:1-Duplikat, um ca. 13 Zeilen versetzt. `getContext` :70 |
| `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | **Dritte Produktivdatei**, kein Nebenschauplatz — braucht einen Adapter (s. Risiko R2) |
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts` (818 Z.) | Bereits context-frei: nimmt `context` als expliziten Parameter, kein `getContext`. **Kein Umbau nötig** |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Hub-Mounts :1024/:1027 · `setContext('compare-wizard-state')` :328 (dieselbe Datei) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | Anlege-Mounts :389/:485 — heute **nur** `context="vergleich"`, alles Übrige aus dem Context |
| `frontend/src/routes/compare/new/+page.svelte` | `setContext('compare-wizard-state')` :20 — eine Ebene **über** `CompareNewEditor` |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Trip-Mounts :227/:229 — schon Wertprops, dienen als Vorbild |
| `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | Die Ratsche. 53 Einträge, davon **30** im Corridor-Umfeld |

## Die drei Mountpunkte

Wie beim Alarme-Reiter sind es **drei**, je einmal Desktop und Mobil:

| Fläche | Mount | Props heute |
|---|---|---|
| **A Trip** | `TripTabs.svelte:227` (Mobil), `:229` (Desktop) | `trip`, `onTripUpdate`, `saveController`. Die Desktop-Zeile setzt kein `context` und fällt auf den Default `'route'` (`CorridorEditor.svelte:53`) zurück — unschädlich, aber inkonsistent zur Mobil-Zeile daneben |
| **B Vergleich-Hub** | `CompareTabs.svelte:1024` (Mobil), `:1027` (Desktop) | `context="vergleich"`, `preset`, `saveController`, `enqueueHubWrite`, `onCompareUpdate` |
| **C Vergleich-Anlegen** | `CompareNewEditor.svelte:485` (Mobil), `:389` (Desktop) | **nur** `context="vergleich"`. Persistenz läuft dort nicht über den Baustein, sondern über den Wizard-Submit |

Fläche A hat keinen `compare-wizard-state`-Context — dort ist `ws` stets `undefined`.

## Ratschen-Bilanz: 30 Einträge, erwartete Zielzahl 53 → 45

Von den 53 eingefrorenen `Datei:Zeile`-Fundstellen liegen **30** im Corridor-Umfeld:
14 in `CorridorEditor.svelte`, 14 in `CorridorEditorMobile.svelte` (paarweise identisch),
plus `corridorEditorState.ts:297` und `wertebereicheVergleichSpeicherung.ts:200`.

> Eine Suche allein nach „Corridor" findet nur 28 — die beiden letztgenannten Dateinamen
> enthalten das Wort nicht in dieser Schreibweise. Beim Zählen die ganze Liste lesen.

**Entwurf der Schicksals-Tabelle** (Desktop/Mobil-Paare; die Analyse-Phase schärft und
begründet jede Zeile einzeln — diese Fassung ist Erhebung, nicht Beschluss):

| Desktop:Mobil | Bedingung | Einschätzung | Grund |
|---|---|---|---|
| `:57`/`:70` | `context === 'vergleich' ? getContext(...) : undefined` | **FÄLLT** | Der Context-Zugriff selbst |
| `:79`/`:91` | `originalLevels` aus `ws` **oder** `trip` | **FÄLLT** | Dasselbe Feld, nur zwei Speicherorte |
| `:89`/`:96` | `originalActiveMetricKeys` nur für Vergleich | **FÄLLT** | Reines Wizard-Feld; als Prop für beide Flächen versorgbar |
| `:240`/`:207` | Dispatch `syncToWizard()` vs. `saveController.schedule()` | **BLEIBT** (in der Analyse entschieden, s. Analysis/E4) | Der `schedule`-Fall ist zwar reine Weiterleitung, aber der **Ungültig-Fall** trägt einen dokumentierten fachlichen Unterschied: Route setzt `setDirty()`, Vergleich tut bewusst nichts (F001/F005-Adversary-Fix aus S3) |
| `:95`/`:98` | `isFreshCompareCreate` (Profil-Prefill beim Anlegen) | BLEIBT | Compare-only-Produktverhalten, Trip hat kein Pendant |
| `:138`/`:126` | Effect-Guard Compare-Metrikkatalog | BLEIBT | Eigener Katalog `/api/compare/metrics` |
| `:170`/`:151` | Effect-Guard Route-Metrikkatalog | BLEIBT | Spiegelbild |
| `:268`/`:234` | `addCompareRow` vs. `addRow` | BLEIBT | Zwei Metrik-Domänen mit eigenen Defaults |
| `:302`/`:297` | Blockierender Fehlerbanner (Vergleich) | BLEIBT | Echter UX-Unterschied zu Route |
| `:315`/`:310` | Ladezustand Compare-Katalog | BLEIBT | |
| `:318`/`:313` | Ladezustand Route-Katalog | BLEIBT | |
| `:324`/`:318` | Überschrift/Erklärtext | BLEIBT | Inhaltlich verschiedene Texte |
| `:345`/`:330` | Non-blocking Fallback (Route) | BLEIBT | |
| `:474`/`:451` | Neutralitäts-Hinweis „kein Score · kein Rang" | BLEIBT | AC-13, Compare-Eigenschaft |
| `corridorEditorState.ts:297` | `supportsMark` | BLEIBT | Fachlich (Tages-Summen ohne Marken-Schalter nur im Trip) |
| `wertebereicheVergleichSpeicherung.ts:200` | `context === 'vergleich' && !!p.ws && …` | **ändert sich** | Enthält den `ws`-Test. Ob der Eintrag fällt oder nur seinen Wortlaut ändert, entscheidet der Adapter-Zuschnitt |

**Erwartung nach der Analyse: 3 Paare fallen = 6 Einträge ⇒ 53 → 47.**
`wertebereicheVergleichSpeicherung.ts:200` bleibt (die Umbenennung `ws` → `zustand` ist
zeilenneutral, der Zweig `context === 'vergleich'` selbst bleibt stehen).
`:240`/`:207` bleibt ebenfalls — Begründung in Analysis/E4.
Diese Zahl gehört **vor der RED-Phase** in die Spec — bei S6c war die Vorausberechnung
67→53 spec-getrieben, nicht aus dem Muster ableitbar.

> Die Ist-Liste wurde mit dem Zählbefehl der Ratsche gegengeprüft: 53 Treffer, deckungsgleich
> mit dem eingefrorenen Soll, Ratsche aktuell grün.

**Wichtig für die Erwartungshaltung:** Der Ertrag ist kleiner als bei S6c (dort fielen 14).
Der eigentliche Zweck von S6d ist nicht die Ratschenzahl, sondern dass `getContext` aus
`shared/` verschwindet — das ist die Voraussetzung für S6f (Bridge-Rückbau, AC-4).

## Context-Zugriffe, die verschwinden müssen

`CorridorEditor.svelte` (Mobil-Pendants in Klammern):

- **Lesen:** `:80 ws?.metricAlertLevels` (`:92`) · `:89 ws?.activeMetricKeys` (`:96`) ·
  `:95 ws?.isEditMode`, `ws?.corridors` (`:98`) · `:97 buildComparePool(ws?.corridors)` (`:100`) ·
  `:98 ws?.activityProfile` (`:101`) · `:217 if (!ws) return` (`:192`) ·
  `:219-221 ws.idealRanges / ws.activeMetricKeys / ws.metricAlertLevels` (`:194-196`)
- **Schreiben:** `:223-226` — vier direkte Zuweisungen `ws.corridors =`, `ws.idealRanges =`,
  `ws.activeMetricKeys =`, `ws.metricAlertLevels =` in `syncToWizard()` (`:198-201`).
  Diese vier werden zu Rückrufen.
- **Durchreichen:** `:63` und `:66` geben `ws` an `wertebereicheVergleichSpeicherung.ts`
  weiter (`:76`/`:79`)

Es gibt in diesen beiden Dateien **keine** `onCompareCommit`/`onHourlyCommit`/`onOutlookCommit`-
Rückrufe wie bei `AlarmeTab`/`WeatherMetricsTab` — nur `onTripUpdate`, `onCompareUpdate` und
`enqueueHubWrite`.

## Bestehendes Muster aus S6b und S6c

| | S6b (Stundenverlauf) | S6c (Alarme) |
|---|---|---|
| Umgebauter Baustein | `CompareHourlyLayoutControls.svelte` | `AlarmeTab.svelte` |
| Betroffene Mounts | 1 | **3** |
| Prop-Übersetzung | Inline-Adapter direkt im Mount | eigenes Modul `compare/alarmePropsAus.ts` (133 Z.), aufgerufen als `{...alarmePropsAus(wiz)}` **direkt im Markup-Ausdruck** — nicht in einer Skript-Variable vorberechnet, sonst würden `$state`-Lesezugriffe außerhalb des reaktiven Renderns registriert |
| Speicherungs-Modul | — | `alarmZustandsBruecke(werte, setzen)` als Proxy-Adapter neu eingeführt |
| Ratschen-Pflege | 1 Eintrag gestrichen, **Zeilenzahl-Vertrag eingehalten** (Umbau netto zeilenneutral, deshalb Inline- statt benannte Funktionen) | Vertrag für `AlarmeTab.svelte` **ausgesetzt**: 14 gestrichen, 4 Überlebende auf neue Zeilen nachgeführt **plus** `BLEIBT_MIT_INHALT`-Wächter eingeführt |
| CI-Runden | 1 | 3 (alle Befunde in der E2E-Spec selbst) |

**Regel aus S6c:** Das Props-Bündel-Modul liegt in `compare/`, **nicht** in `shared/` —
sonst importierte der geteilte Bereich die Compare-Klebeschicht.

### Die Ratsche hat zwei Wächter

1. **Mengenvergleich** Soll (Literal-Liste) gegen Ist (Zählbefehl), in **beiden** Richtungen —
   ein Leeren der Ist-Liste macht ebenso rot wie ein Zusatz.
2. **`BLEIBT_MIT_INHALT`** (seit S6c): prüft je Überlebendem per `readFileSync`, dass an der
   eingetragenen Zeile **wörtlich** die eingefrorene Bedingung steht **und** im 8-Zeilen-Fenster
   darunter ein benannter Folge-Baustein auftaucht. Ohne diesen Wächter wäre der billigste Weg
   zu Grün, einfach die Nummern einzutragen, die der Zählbefehl gerade ausgibt — dann bewachte
   die Ratsche nur noch sich selbst.

## Dependencies

- **Upstream:** `corridorEditorState.ts` (context-frei, unverändert) · `api.ts` (ETag/If-Match
  generisch seit #1395 S6) · `saveController` · `compareMetricCatalogLoader.ts`
- **Downstream:** `CompareTabs.svelte:91` importiert `sichereSelbstSpeichererVorReiterwechsel`
  aus dem Speicherungsmodul · zahlreiche SSR-Tests unter `compare/__tests__/` und
  `shared/corridor-editor/__tests__/`

## Bestehende E2E-Abdeckung

| Spec | Fläche | Darstellung |
|---|---|---|
| `speicherung-ueberlebt-neuladen.spec.ts` | A + B | **Desktop und Mobil** (Viewport 390×844 ab :351) — einzige Spec, die den echten Band-Drag des mobilen Bausteins prüft |
| `compare-wertebereiche-speichert-selbst.spec.ts` | B | nur Desktop |
| `compare-editor-slice3.spec.ts`, `compare-editor-slice4.spec.ts` | C | nur Desktop |
| `compare-hub-inline-edit.spec.ts`, `compare-editor-autosave.spec.ts` | B | nur Desktop |
| `fix-1350t3-compare-threshold-source.staging.spec.ts` | B/C | nur Desktop |

## Risks & Considerations

- **R1 — Fläche C ist E2E-seitig unbewacht, wird aber im Kern bewacht (korrigiert nach der
  Analyse).** Auf `/compare/new` prüft **keine** Spec den mobilen Corridor inhaltlich —
  `issue-682-compare-editor-mobile.spec.ts` und `compare-editor-fidelity-s8d.spec.ts` fahren
  dort zwar im Mobil-Viewport, berühren aber **null** `corridor-*`-Testids. **Das ist bei S6c
  ein dokumentiert akzeptierter Zustand**, kein Versehen: die Anlege-Seite hat keinen eigenen
  Speicherweg (gespeichert wird erst beim Wizard-Submit), Persistenz ist dort browserseitig
  nicht beobachtbar, eine E2E-Spec hätte nichts zu behaupten. Stattdessen trägt ein
  **Kern-AST-Wächter** die Verdrahtungs-Zusicherung (`compare_alarme_wertprops.test.ts`,
  AC-3/AC-4). Eine zweite E2E-Spec dafür wäre laut S6c-Spec „gegen die Scheiben-Disziplin".
  ⇒ Für S6d ist das Gegenmittel ein **analoger Kern-Wächter**, keine neue Mobil-E2E-Spec auf
  Fläche C. Der Code bestätigt die Voraussetzung: `CorridorEditor.svelte:244` trägt den
  Kommentar „Anlege-Seite: kein Speicherweg hier, Speichern über `wiz.saveNewPreset()`".
- **R2 — `wertebereicheVergleichSpeicherung.ts` braucht einen Adapter.**
  `rollbackCorridorSnapshot` schreibt `target[field] = before[field]` direkt auf `ws`, und
  `erstelleWertebereicheVergleichSpeicherung` hält `ws` in einer Closure und liest es bei jedem
  `aenderungMelden()` neu. Das Modul braucht eine **lebendige, mutierbare Objektreferenz** —
  reine Wertprops genügen ihm nicht. S6c stand vor derselben Wand und löste sie mit
  `alarmZustandsBruecke(werte, setzen)`. Ohne Adapter ist der Umbau nicht durchführbar.
- **R3 — Zeilenzahl-Vertrag ist hier nicht haltbar.** Der Props-Block endet bei `:53-55`, alle
  14 Einträge liegen darunter. Jede neue Prop-Zeile verschiebt sie — in **beiden** Dateien.
  Der Vertrag muss also für beide Corridor-Dateien ausgesetzt werden, wie S6c es für
  `AlarmeTab.svelte` tat. Folge: **20 überlebende Einträge** (10 Paare) müssen nachgeführt und
  per `BLEIBT_MIT_INHALT` inhaltlich gefesselt werden — bei S6c waren es 4. Die Spec muss
  festlegen, wie sich RED und GREEN das teilen; S6c schrieb RED mit der Streichliste und führte
  die Überlebenden-Nummern erst in GREEN nach. Wer in RED 20 Nummern schreibt, schreibt sie
  konstruktionsbedingt falsch.
- **R4 — Fläche C braucht eine Designentscheidung.** Nach dem Umbau muss jemand die Props
  liefern. Entweder ruft `CompareNewEditor` selbst `getContext` auf (zulässig — die Datei liegt
  in `compare-new/`, nicht in `shared/`) oder die Route reicht sie durch. Die Spec muss sich
  festlegen.
- **R5 — Timing-Unterschied in `maybeSchedule`.** Der Zweig `:240`/`:207` trennt nicht nur
  Speicherorte, sondern auch Zeitverhalten: Trip feuert ein Debounce-PUT, der Vergleich meldet
  an die gebündelte Hub-Orchestrierung. Ein Rückruf kann das abbilden, aber nicht ungeprüft —
  hier hängt der Datenerhalt dran.
- **R6 — Die SSR-Harness beweist die Verdrahtung nicht.** Sie läuft mit `generate: 'server'`
  ohne DOM; reaktive Effekte laufen dort prinzipiell nie. Für jeden `$effect`-Wirkort gehört
  eine E2E-Spec dazu (Lehre aus S5).
- **R7 — Schreibschlange nicht anfassen.** `hubPutQueue` ist Schutzmechanismus, keine Altlast:
  Zwei PUTs ohne Schlange bauen beide aus demselben stalen `currentPreset`, der zweite bekommt
  **200 OK mit veraltetem Körper** statt 412 — stiller Datenverlust. Fällt frühestens in S6f
  und dort nicht ersatzlos.
- **R8 — Read-Modify-Write bleibt Pflicht** (BUG-DATALOSS-GR221). Der Voll-Spread-Payload darf
  nicht durch einen Minimal-Body ersetzt werden, solange der Go-Handler in das volle Modell
  dekodiert.

---

## Analysis

### Type

**Feature** (Rework/Refactoring, verhaltensneutral). Kein Bug — es wird kein Fehlverhalten
behoben, sondern eine Zustandsquelle ersetzt.

### Affected Files (with changes)

| Datei | Change | Beschreibung |
|---|---|---|
| `shared/corridor-editor/CorridorEditor.svelte` | MODIFY | `getContext` entfällt; Props-Block bekommt die Wertprops + Rückrufe; `syncToWizard()` schreibt nicht mehr auf `ws`, sondern ruft die Rückrufe; `corridorZustandsBruecke(...)` ersetzt die `ws`-Übergabe an den Speicherweg |
| `shared/corridor-editor/CorridorEditorMobile.svelte` | MODIFY | Identisch, 1:1-Duplikat |
| `shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | MODIFY | Neue `corridorZustandsBruecke(werte, setzen)` **unterhalb Zeile 200** (Auflage A2); Optionsfeld `ws` → `zustand` (Auflage A3). Queue, Diff-Gate, Read-Modify-Write und Rollback bleiben mechanisch unverändert |
| `compare/corridorPropsAus.ts` | **CREATE** | Übersetzung Wizard-Zustand → Prop-Bündel für alle drei Vergleichs-Mounts. Liegt in `compare/`, nicht `shared/` (Auflage A1) |
| `compare/CompareTabs.svelte` | MODIFY | Hub-Mounts `:1024`/`:1027` bekommen `{...corridorPropsAus(wizardState)}` |
| `compare-new/CompareNewEditor.svelte` | MODIFY | Anlege-Mounts `:389`/`:485` bekommen dasselbe Bündel; nutzt das dort schon vorhandene `wiz` aus `:65` |
| `shared/corridor-editor/__tests__/compare_corridor_wertprops.test.ts` | **CREATE** | SSR-Wächter: AST-Scan auf `ws`-Identifier in beiden Corridor-Dateien + Verdrahtungs-Prüfung aller drei Mounts (Muster `compare_alarme_wertprops.test.ts`) |
| `shared/corridor-editor/__tests__/` (AC-12-Test) | **CREATE** | Sichert die Verzweigung `:240`/`:207` ab, die heute nur durch einen Kommentar belegt ist (s. E4) |
| `shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY | 6 Einträge streichen, 24 Überlebende nachführen, `BLEIBT_MIT_INHALT` erweitern |
| `frontend/e2e/compare-wertebereiche-wertprops.spec.ts` | **CREATE** | Wirkort-Nachweis im Browser am Hub, Desktop **und** Mobil |
| `.github/ci_e2e_specs.txt` | MODIFY | Neue E2E-Spec in die Ampel aufnehmen |

Unverändert bleiben: `corridorEditorState.ts` (schon context-frei, nimmt `context` als
Parameter) und `hubPutQueue` (R7).

### Scope Assessment

- Dateien: **11** (3 CREATE Produktiv/Test + 1 CREATE E2E, 6 MODIFY, 1 Ampel-Eintrag)
- Geschätzte LoC: **+550 / −180** — der Großteil sind die 24 Ratschen-Nachführungen mit
  Inhalts-Fesselung und die neuen Tests. **Das 800er-Limit ist damit knapp**; vor `/40` neu
  bewerten und ggf. anheben.
- Risiko: **MITTEL-HOCH**. Drei Mounts, zwei 1:1-Duplikate, ein Modul mit Datenverlust-Relevanz.
  Dämpfend: das Muster ist in S6b und S6c zweimal gefahren, und `corridorEditorState.ts`
  bleibt unberührt.

### Technical Approach

Das S6c-Muster wird eins zu eins übertragen, mit vier bindenden Auflagen:

**A1 — Prop-Bündel in `compare/corridorPropsAus.ts`.** Bei drei Mounts wären Inline-Adapter
dreifache Gelegenheit zur Drift — genau das Anti-Pattern, das #2276 abbaut. Der Aufruf steht
`{...corridorPropsAus(wiz)}` **im Markup-Ausdruck jedes Mounts**, niemals in einer
Skript-Variablen: ein dort eingefrorenes Objekt bestünde SSR-Prüfstand und AST-Wächter
anstandslos und fiele erst im Browser auf, weil die `$state`-Lesezugriffe außerhalb des
reaktiven Renderns registriert würden.

**A2 — `corridorZustandsBruecke` unterhalb Zeile 200.** Der Speicherweg braucht eine lebendige,
mutierbare Objektreferenz (`rollbackCorridorSnapshot` schreibt direkt, `erstelle…` liest bei
jedem `aenderungMelden()` neu). Die Brücke ist ein `Proxy` über einem leeren Objekt: `get` liest
bei jedem Zugriff frisch aus `werte()`, `set` reicht an `setzen` weiter, ohne lokal zu speichern.
Bei Corridor sind es **vier** Felder (`corridors`, `idealRanges`, `activeMetricKeys`,
`metricAlertLevels`) — alle unter identischem Namen, die Namensumleitung `PROP_JE_FELD` aus S6c
entfällt. **Platzierung ist Pflicht, keine Vorliebe:** S6c legte seine Brücke bei `:162-195` ab;
dieselbe Position würde hier den eingefrorenen Eintrag `:200` nach unten schieben und die
Ratsche rot machen, ohne dass inhaltlich etwas falsch wäre.

**A3 — Optionsfeld `ws` → `zustand`.** Der AST-Wächter zählt jeden `Identifier` mit dem
gesuchten Namen, **auch als Objektschlüssel** — in S6c erzwang das die Umbenennung der ganzen
Options-Schnittstelle. Die Umbenennung ist zeilenneutral, `:200` übersteht sie.

**A4 — Fläche C ruft `getContext` selbst.** `CompareNewEditor.svelte:65` hat die Referenz
bereits (`const wiz = getContext(...)`) und versorgt damit schon die Alarme-Mounts. Zulässig,
weil die Datei in `compare-new/` liegt, nicht in `shared/`. **Keine offene Designfrage mehr.**

### Entscheidungen

**E1 — Zielzahl der Ratsche: 53 → 47.** Es fallen drei Desktop/Mobil-Paare: `:57`/`:70`
(der `getContext`-Aufruf), `:79`/`:91` (`originalLevels` aus zwei Speicherorten), `:89`/`:96`
(`originalActiveMetricKeys`). Ist-Liste mit dem Zählbefehl gegengeprüft.

**E2 — Der Zeilenzahl-Vertrag wird für beide Corridor-Dateien ausgesetzt.** Der Props-Block
endet bei `:53-55`, alle 14 Einträge je Datei liegen darunter. Jede neue Prop-Zeile verschiebt
sie. S6c setzte den Vertrag aus demselben Grund für `AlarmeTab.svelte` aus. Folge: **24
überlebende Einträge** (12 Paare) müssen nachgeführt und per `BLEIBT_MIT_INHALT` inhaltlich
gefesselt werden — bei S6c waren es 4.

**E3 — RED schreibt die Streichliste, GREEN führt die Nummern nach.** So hielt es S6c. Wer in
RED 24 Zeilennummern schreibt, schreibt sie konstruktionsbedingt falsch, weil die Verschiebung
erst durch die Implementierung entsteht. Beim Fesseln jedes Paares den Folge-Anker in **beiden**
Dateien einzeln prüfen — die Mobil-Testids tragen meist ein `-mobile-`-Infix, aber
`corridor-editor-pool-item-` ausgerechnet nicht.

**E4 — `:240`/`:207` bleibt stehen.** Die Verzweigung ist nur zur Hälfte Herkunft. Im
`schedule`-Fall ist sie reine Weiterleitung (Route ruft `saveController.schedule()`, Vergleich
delegiert an das Modul — beide mit demselben 700-ms-Takt, der fachliche Unterschied „Diff-Gate"
sitzt seit S3 vollständig **im Modul**). Im **Ungültig-Fall** trägt sie aber einen dokumentierten
fachlichen Unterschied: Route setzt aktiv `setDirty()`, damit der Indikator nicht fälschlich
„Gespeichert ✓" neben einem sichtbaren Fehlerbanner zeigt; Vergleich tut bewusst **nichts**,
damit der externe Speichern-Button im Hub keinen ungültigen Zwischenstand persistiert
(F001/F005, Adversary HIGH aus S3). Eine Verzweigung, die einen dokumentierten Fix kodiert, ist
keine Herkunfts-Weiche.
Der naheliegende Umbau (zwei Rückrufe `onAenderung`/`onUngueltig`, vom Elternteil verschieden
verdrahtet) wird **verworfen**: er wäre eine verhaltenstragende Änderung in einer Scheibe, die
verhaltensneutral sein soll, auf einem Pfad, den **kein** Test abdeckt — SSR kann es nicht
(`$effect` läuft dort nie), und keine E2E-Spec stellt im Vergleichs-Editor gezielt eine
beidseitig offene Grenze her. Ein Ratschen-Paar ist diesen Einsatz nicht wert.

**E5 — Die Lücke am Ungültig-Fall wird stattdessen geschlossen.** Genau weil dieser
Verhaltensunterschied heute nur durch einen Code-Kommentar belegt ist und an der Stelle sitzt,
die beim Umbau am ehesten bricht, gehört ein Test dafür in die RED-Phase: beidseitig offene
Grenze herstellen, dann Route → `dirty`, Vergleich → nichts. Damit wird das Überleben der
Verzweigung beweisbar statt behauptet.

### Dependencies

Reihenfolge innerhalb der Scheibe: `corridorPropsAus.ts` und die Brücke zuerst (sonst
kompiliert der Baustein-Umbau nicht), dann die beiden `.svelte`-Dateien, dann die beiden
Elternteile, zuletzt die Ratschen-Nachführung (braucht die endgültigen Zeilennummern).

Die Scheibe bleibt **unteilbar**: Desktop und Mobil sind bestätigte 1:1-Duplikate, und die
Brücke von den `.svelte`-Änderungen zu trennen hinterließe einen nicht kompilierenden
Zwischenstand.

### Regressionsnetz

| Test | Sichert |
|---|---|
| `frontend/e2e/speicherung-ueberlebt-neuladen.spec.ts:200` | Trip Desktop: Wertebereich-Zahl ändern, sofort neu laden, Wert ist da |
| dieselbe Datei `:423` | Trip **Mobil**: Obergrenze per Stepper ändern, sofort neu laden |
| `frontend/e2e/compare-wertebereiche-speichert-selbst.spec.ts` (6 Fälle) | Hub-Wirkort: zwei Metriken schnell hintereinander, Regler-Drag, Reiterwechsel bei offener Änderung, Konflikt, Pausieren-Reihenfolge, Neuladen |
| `frontend/e2e/issue-953-alerts-autosave-tabswitch.spec.ts` | Trip-Autosave beim Reiterwechsel |
| 11 SSR-Modultests unter `corridor-editor/__tests__/` | Diff-Gate, EIN-PUT-Garantie, Konflikt, Flush, gemeinsamer Speicherplatz mit Alarme, Nutzlast-Vollständigkeit |

Produktiv importiert außer den beiden Corridor-Dateien nur `CompareTabs.svelte:91` das
Speicherungsmodul (`sichereSelbstSpeichererVorReiterwechsel`) — die Änderungsfläche ist eng.

### Open Questions

Keine offenen Fragen an den PO. Die vier Entscheidungen, die in die Analyse gingen, sind
oben mit Begründung geschlossen (E1 Zielzahl, E4 Timing-Weiche, A4 Fläche C, R1 E2E-Schnitt).
