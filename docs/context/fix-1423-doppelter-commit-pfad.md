# Kontext: #1423 — Ausblick-Kaestchen bleiben still angehakt

## Analysis

### Type
Bug-Analyse (Mechanismus-Beweis, KEIN Fix) — Auftrag: Vermutung aus #1423
(doppelter Commit-Pfad ueber zwei verschachtelte Wrapper) bestaetigen oder
widerlegen.

### Symptom (aus Issue #1423)
Im Reiter "Wetter-Metriken" eines Orts-Vergleichs bleiben nach schnellem
Abwaehlen mehrerer 3-Tages-Ausblick-Kaestchen 1-2 davon serverseitig aktiv
(20-30 % Fehlschlagrate ueber ~15 Laeufe, auch mit explizitem Warten auf jede
PUT-Antwort). Nachweis-Test: `frontend/e2e/compare-outlook-metric-selection.staging.spec.ts:515`
(`test.fixme`).

### Ergebnis vorweg
**Die Vermutung aus #1423 traegt NICHT.** Der doppelte Commit-Pfad
(`.hub-layout-hourly-wrap` / `.hub-wetter-metriken-wrap`,
`CompareTabs.svelte:1350-1361`) existiert und feuert nachweislich mehrfach je
Klick — er verursacht aber **keinen** Datenverlust: die serialisierte,
diff-geschuetzte `hubPutQueue` faengt ihn zuverlaessig ab. Die tatsaechliche
Ursache liegt im **Test/Reproduktions-Script selbst**: ein Rennen zwischen
Katalog-Ladezeit und der Existenzpruefung der Checkbox im DOM
(`compare-outlook-metric-selection.staging.spec.ts:578`,
`if (await box.count() === 0) continue;`), begünstigt durch einen bewussten
Render-Gate in `WeatherMetricsTab.svelte:1026`
(`{#if sections.includes('ausblick') && wiz && compareCatalogLoaded}`).

### Messbeweis 1: Doppel-/Dreifach-Feuerung ist real, aber folgenlos

Ad-hoc-Netzwerkmitschnitt (Playwright, `page.on('request'/'response')`) auf
Staging (`86ff7f1c`+), mit vorher **sicher abgewarteter** Katalog-Hydration
(`outlook.getByTestId('compare-layout-outlook-option-temperature-min').waitFor({state:'attached'})`),
danach alle 7 Ausblick-Kaestchen **ohne jede Wartezeit** abgewaehlt
(Haertungsstufe "a" aus dem Issue, alle Klicks < 300 ms):

```
Alle Klicks ausgeloest nach 239ms
PUT #1 body.outlook: [max, precipitation, rain_probability, wind, gust, thunder]   -> 200
PUT #2 body.outlook: [precipitation, rain_probability, wind, gust, thunder]         -> 200
PUT #3 body.outlook: [rain_probability, wind, gust, thunder]                        -> 200
PUT #4 body.outlook: [wind, gust, thunder]                                          -> 200
PUT #5 body.outlook: [gust, thunder]                                               -> 200
PUT #6 body.outlook: [thunder]                                                     -> 200
PUT #7 body.outlook: []                                                            -> 200
Server-Endstand: []   RESULT=PASS
```

**Exakt 7 PUTs fuer 7 Klicks**, jeder korrekt auf dem Vorgaenger aufbauend —
nicht die 14-21 PUTs, die die "jeder Klick loest 2-3 Commit-Pfade aus"-Theorie
erwarten liesse. 9 von 9 Wiederholungen dieses Szenarios (5x mit sequentiellem
Warten je Klick, 4x im echten Rapid-Fire ohne Wartezeit) liefen **fehlerfrei**
durch. Die Diff-Guards (`flushPendingLayoutSave`/`flushPendingWeatherMetricsSave`
in `compareHubWizardBridge.ts:669-691` bzw. dort im Wetter-Metriken-Analogon)
vergleichen `current` vs. `before` erst **zur Ausfuehrungszeit** innerhalb der
`hubPutQueue`-Closure (`CompareTabs.svelte:812-840`) — dadurch sieht ein
redundanter zweiter/dritter Aufruf desselben oder des falschen Handlers exakt
den bereits persistierten Stand und liefert `null` (kein PUT). Der
Code-Kommentar `CompareTabs.svelte:1344-1349` ("ein Klick erzeugt genau EINEN
PUT") **haelt in der Praxis** — anders als das Issue behauptet.

### Messbeweis 2: Der reale Ausfall entsteht VOR dem ersten Klick

Ohne den expliziten Hydration-Wait (also exakt der Ablauf, den der stillgelegte
Test selbst fahrt: Tab wechseln, `networkidle` abwarten, dann sofort
`box.count()` fuer `compare-layout-outlook-option-temperature-min` prüfen)
zeigte sich in 4 von 5 Läufen ein fehlendes `temperature-min` (in 1 Lauf
zusätzlich `temperature-max`) — **niemals** ein anderes der sieben Kästchen.
Klick-Log eines Fehlschlags:

```
click-start "temperature-max" ...   (kein Eintrag fuer "temperature-min"!)
click-start "precipitation" ...
click-start "rain_probability" ...
...
=> 6 Klicks, 6 PUTs statt 7 — temperature-min wurde NIE angeklickt.
```

`box.count() === 0` fuehrt bei fehlendem Element zu `continue` (Test-Zeile 578)
— das Kaestchen wird als "gibt es nicht in dieser Zeilenform" interpretiert und
für immer uebersprungen, nicht etwa angeklickt und dann ueberschrieben.

**Der offizielle, unveraenderte Playwright-Test bestaetigt dasselbe Muster**
(5 Wiederholungen ueber den echten Testrunner, `retries:1`): 4 von 5
Erstversuchen scheiterten mit exakt `temperature-min` weiterhin angehakt
(Server-Snapshot im `error-context.md`: `checkbox "Minimum" [checked]` direkt
unter der Temperatur-Zeile, alle anderen sechs Groessen bereits abgewaehlt).
Das deckt sich 1:1 mit dem eigenen Testkommentar (Zeile 557-559): "*bleibt
IMMER dasselbe Kaestchen (das ERSTE der Sequenz, hier Temperatur-Minimum)
faelschlich angehakt*" — ein **deterministisches Positions-Muster** (immer das
erste Element der Iterationsreihenfolge `defaultKeys`), keine zufaellige
Teilmenge, wie ein echter Ueberschreib-Race sie erzeugen wuerde.

### Root Cause (belegt)

`WeatherMetricsTab.svelte:1026`:
```svelte
{#if sections.includes('ausblick') && wiz && compareCatalogLoaded}
	<div data-testid="weather-metrics-ausblick">
		<CompareOutlookLayoutControls {wiz} catalog={compareCatalog} {onOutlookCommit} />
	</div>
{/if}
```
Solange der Metrik-Katalog (`GET /api/compare/metrics`, `compareCatalogLoaded`)
noch laedt, existiert der **gesamte** Ausblick-Block — inklusive
`data-testid="weather-metrics-ausblick"` — **nicht im DOM** (bewusst so
gebaut, Kommentar `WeatherMetricsTab.svelte:1023-1025`: "ohne Katalog bleibt
wenigstens der Schalter unerreichbar statt eine leere Liste zu zeigen"). Der
Test/das Reproduktions-Script fragt aber sofort nach dem Tab-Wechsel
(`compare-outlook-metric-selection.staging.spec.ts:574-580`) `box.count()` ab
— ohne auf das Erscheinen des Elements zu warten (`count()` wartet in
Playwright NICHT, anders als z. B. `expect(...).toBeVisible()`). Trifft die
Abfrage in das kurze Fenster zwischen Tab-Wechsel und Katalog-Antwort, ist die
Trefferzahl 0, das Script wertet das als "Einzel-Options-Zeile, andere
Testid-Form" und ueberspringt das Kaestchen dauerhaft — es wird nie geklickt.
Da `temperature` in `defaultKeys` an erster Stelle steht, trifft das Rennen
reproduzierbar zuerst dieses Element (manchmal reicht das Fenster fuer zwei
Eintraege).

Mit explizitem Abwarten des ersten Ausblick-Kaestchens
(`waitFor({state:'attached'})`) VOR Beginn der Klick-Schleife lief das
identische Szenario 3-mal fehlerfrei durch (kombiniert mit Messbeweis 1: 9/9).

**Die Vermutung aus dem Issue ersetzt sich damit vollstaendig** — nicht nur
"halten oder nicht", sondern durch eine andere, tatsaechlich verifizierte
Ursache in einer anderen Datei (`WeatherMetricsTab.svelte:1026` +
Test-Skript-Zeile `compare-outlook-metric-selection.staging.spec.ts:578`,
nicht `CompareTabs.svelte:1350-1361`).

### Betrifft es die Übersicht (Grundauswahl) ebenso?
**Nein, nicht ueber denselben Mechanismus.** Die Grundauswahl-Liste
(`WeatherMetricsTab.svelte:918` ff., Testid-Praefix
`weather-metrics-vergleich-*`) haengt am selben `compareCatalogLoaded`-Flag,
zeigt waehrend des Ladens aber einen **sichtbaren Platzhalter**
(`data-testid="weather-metrics-vergleich-loading"`, Zeile ~899: "Lade
Metriken…") statt komplett zu fehlen — ein Testskript, das erst auf
Sichtbarkeit der Liste wartet, liefe nicht in dieselbe Race. Der
Doppel-Wrapper-Commit-Pfad (Messbeweis 1) betrifft strukturell zwar auch die
Grundauswahl (dieselben zwei Wrapper), aber genau der ist — s. o. — nicht die
Fehlerursache. Eine eigene Messung fuer die Grundauswahl wurde in dieser
Analyse aus Kontingent-/Zeitgruenden NICHT durchgefuehrt (s. Open Questions);
die Uebersichts-Konstruktion (mit Platzhalter) macht das analoge Rennen aber
strukturell unwahrscheinlicher.

### Affected Files (Ort eines moeglichen Fixes — NICHT umgesetzt)
| File | Warum hier |
|------|------------|
| `frontend/e2e/compare-outlook-metric-selection.staging.spec.ts:565-580` | Der Nachweis-Test selbst braucht ein Warten auf das Erscheinen jeder Zeile (`waitFor({state:'attached'})` statt `count()===0 → continue`), bevor er als "keine Multi-Options-Zeile" interpretiert. |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1026` | Optionale Produkt-Frage (kein Bug): der Ausblick-Block zeigt waehrend des Katalog-Ladens **nichts**, waehrend die Grundauswahl einen Platzhalter zeigt — Inkonsistenz, die reale Nutzer:innen bei langsamer Verbindung genauso treffen koennte wie das Testscript (kurzes Zeitfenster ohne sichtbares Element). |

**Nebenwirkungen eines Fixes:** Am Speicherweg selbst (`hubPutQueue`,
`CompareTabs.svelte:735-849`) muss NICHTS geaendert werden — der ist bereits
korrekt, siehe Messbeweis 1. Ein Fix am Testskript ist folgenlos fuer den
Produktivpfad. Ein Fix am Render-Gate in `WeatherMetricsTab.svelte` (z. B.
Platzhalter statt komplettem Fehlen) wuerde den bekannten
Compare-Speicherweg-Bereich beruehren (Editor-Drift-Risikozone,
`reference_compare_save_path_is_root_of_editor_drift`), ist aber optisch, kein
Speicherlogik-Eingriff.

### Scope Assessment
- Diese Analyse: 0 LoC Produktivcode geaendert (nur gelesen + Ad-hoc-Messscripte, geloescht; `test.fixme`↔`test` testweise umgeschaltet und wieder zurueckgesetzt — Worktree ist clean).
- Ein Testskript-Fix (`waitFor` statt `count()===0`) waere trivial (~5-10 LoC in EINER Testdatei).
- Ein optionaler Produkt-Fix (Platzhalter im Ausblick waehrend Katalog-Ladezeit) waere klein (~10-15 LoC, EINE Svelte-Datei), aber eine PO-Entscheidung, keine Notwendigkeit fuer #1423 selbst.

### Aufwand
**Klein.** Kein Fix im Speicherweg noetig. Die Behebung fuer #1423 im engeren
Sinn ist ausschliesslich der Testskript-Fix (`waitFor` statt `count()`-Skip);
das reaktiviert den fixme-Test dauerhaft gruen. Ob zusaetzlich ein
Platzhalter-Fix in `WeatherMetricsTab.svelte:1026` sinnvoll ist (Schutz
gegen ein analoges — bisher nicht real beobachtetes — Zeitfenster bei sehr
langsamer Verbindung eines echten Nutzers), ist eine offene PO-Frage, kein
belegter Bug.

### Open Questions
- Soll die Uebersichts-Auswahl (Grundauswahl) trotz Platzhalter-Schutz
  ebenfalls mit einem echten Netzwerkmitschnitt durchgemessen werden, um die
  "nicht ueber denselben Mechanismus betroffen"-Aussage zu erhaerten? (In
  dieser Analyse nicht gemessen, nur strukturell begruendet.)
- Soll `WeatherMetricsTab.svelte:1026` einen Platzhalter analog der
  Grundauswahl bekommen (Konsistenz + Haertung gegen ein theoretisches,
  bislang nicht bei echten Nutzer:innen beobachtetes Zeitfenster)? Reine
  PO-Entscheidung, keine Voraussetzung fuer den #1423-Fix.
