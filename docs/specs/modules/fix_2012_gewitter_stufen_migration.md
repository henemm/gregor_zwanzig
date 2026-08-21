---
entity_id: fix_2012_gewitter_stufen_migration
type: bugfix
created: 2026-08-21
updated: 2026-08-21
status: draft
version: "1.1"
tags: [trip, corridor-editor, thunder, migration, wertebereiche]
---

# Trip-Wertebereiche: Gewitter-Prozent-Migration auf die 4-Stufen-Skala nachziehen (#2012)

## Approval

- [ ] Approved

## Purpose

`percentBoundToOrdinal()` rechnet gespeicherte Gewitter-Wertebereiche vom
Alt-Schluessel `thunder_level` (Prozent-Epoche) auf die Ordinalskala des
neuen Schluessels `thunder_level_max` um. Die Funktion stammt aus der
3-Stufen-Welt (NONE/MED/HIGH, `percentBoundToOrdinal` bildet auf 0/1/2 ab).
Seit #1474 hat die Skala vier Stufen (0=kein, 1=leicht, 2=mittel, 3=hoch,
`_THUNDER_ORDINAL_LABELS`). Die Migration wurde dabei nicht nachgezogen:
Bestandswerte erscheinen eine Stufe zu niedrig, Stufe 3 ("hoch") ist ueber
diesen Pfad nicht erreichbar. Zusaetzlich enthaelt die Funktion einen
konzeptionell falschen Durchreich-Zweig (`v === 0 || v === 1 || v === 2` ->
"ist schon ordinal") — die Funktion laeuft ausschliesslich auf Zeilen mit
dem Alt-Schluessel `thunder_level`, und dieser Schluessel trug per
Definition immer die Prozent-Einheit (Stand `7c42db9f^`, vor der
Skalen-Umstellung durch #1425). Eine gespeicherte `1` ist 1 Prozent, keine
Stufe — der Durchreich-Zweig deutet sie faelschlich als Ordinalwert.

Diese Spec korrigiert `percentBoundToOrdinal()` auf eine reine
Prozent-zu-Stufe-Zuordnung ohne Sonderzweig, koppelt die Zielstufen
strukturell an die bewachte kanonische Enum-Quelle `ORDINAL_ENUM` statt an
neue Zahlenliterale, und zieht den bestehenden Migrations-Testfall
(`MIGRATION_CASES`) auf die korrekte 4-Stufen-Zuordnung.

## Wirkung

Der Fehler ist nicht rein kosmetisch. Der migrierte Ordinalwert wird
serverseitig als echte Schwelle gegen den gemessenen Gewitterwert
verglichen: `corridor_inside()` in `src/services/corridor_threshold.py:96-104`
(Δ-Benachrichtigung, normalisiert per `thunder_ordinal()`) und
`is_marked()` in `src/output/renderers/email/corridor_mark.py:49-57`
(Markierung in der Trip-Mail). Reines **Oeffnen** des Wertebereiche-Reiters
zeigt den Wert nur falsch an — sobald der Nutzer dort etwas aendert und
speichert, wird die verschobene Schwelle **wirksam**: aus einer Vorgabe
„melde ab mittel" wird faktisch „melde ab leicht" (eine Stufe empfindlicher
als eingestellt). Der Fix betrifft also sowohl die Anzeige als auch die
tatsaechliche Alarm-/Markier-Schwelle, sobald gespeichert wird.

## Source

- **File:** `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts`
- **Identifier:** `percentBoundToOrdinal()` (Zeile 119-133),
  `migrateLegacyThunderCorridors()` (Zeile 142-155, einziger Aufrufer),
  `ORDINAL_ENUM` (Zeile 407, kanonische Stufen-Quelle)

> **Schicht-Hinweis:** Reines SvelteKit-Frontend (TypeScript). Kein Go-API-,
> kein Python-Core-Eingriff — die Migration lebt ausschliesslich im
> Client-seitigen Lade-Pfad des Trip-Wertebereiche-Editors
> (`buildRoutePool()`, `context="route"`). Die Wirkung (s. o.) entsteht,
> weil der bereits migrierte, gespeicherte Wert spaeter unveraendert von
> Python gelesen wird — dort ist nichts zu aendern.

## Estimated Scope

- **LoC:** ~40-70 (kleiner Funktionskern, ueberwiegend Testfall-Korrektur
  plus drei Kommentarstellen)
- **Files:** 4
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `migrateLegacyThunderCorridors()` (`corridorEditorState.ts:142-155`) | function | Einziger Aufrufer von `percentBoundToOrdinal()` — ruft sie unabhaengig fuer `range[0]` (Untergrenze) und `range[1]` (Obergrenze) auf; bleibt selbst unveraendert |
| `buildRoutePool()` (`corridorEditorState.ts:187-233`) | function | Ruft `migrateLegacyThunderCorridors()` VOR dem Aufbau der `present`-Map auf (Zeile 199-201) — diese Reihenfolge ist Voraussetzung fuer Nicht-Doppel-Speicherung und bleibt unveraendert |
| `ORDINAL_ENUM` (`corridorEditorState.ts:407`, `['NONE','LOW','MED','HIGH']`) | data | Einzige Whitelist-Position des lokalen Kopie-Wächters `thunderScaleLocalCopyGuard.test.ts` (`CANONICAL_SYMBOLS`) — `percentBoundToOrdinal()` leitet die Zielstufen ab jetzt ueber `ORDINAL_ENUM.indexOf('MED'\|'HIGH')` statt ueber eigene Zahlenliterale, damit die Funktion strukturell an die kanonische Kette haengt, nicht daneben |
| `thunderScaleLocalCopyGuard.test.ts` (`frontend/src/lib/components/shared/weather-metrics-tab/__tests__/`) | gate | Waechter gegen lokale Nachbauten der Gewitter-Stufenskala (#1480) — erkennt `percentBoundToOrdinal()` selbst NICHT (Rueckgabewerte sind Zahlen, keine Stufen-Woerter/-Arrays; Funktionsname enthaelt weder "thunder" noch "gewitter"), genau deshalb ist die direkte Kopplung an `ORDINAL_ENUM` in dieser Spec verlangt statt einer Umbenennung |
| `_THUNDER_ORDINAL_LABELS` (`src/output/renderers/compare_metric_catalog.py:115-122`) | data | Kanonische Quelle der vier Stufennamen (`['kein','leicht','mittel','hoch']`, seit #1474) — Referenzpunkt fuer die korrekte Zuordnung, wird selbst nicht geaendert |
| `corridor_inside()` / `corridor_threshold.py:96-104` | function | Liest den migrierten Ordinalwert als echte Δ-Alarm-Schwelle — unveraendert, aber die Wirkung dieser Spec entsteht hier (s. „Wirkung") |
| `is_marked()` / `corridor_mark.py:49-57` | function | Liest den migrierten Ordinalwert als Markier-Schwelle in der Trip-Mail — unveraendert, aber die Wirkung dieser Spec entsteht hier (s. „Wirkung") |
| `MIGRATION_CASES` (`__tests__/routeCorridorPoolCatalogExpansion.test.ts:555-568`) | test | Haelt die (falsche) 3-Stufen-Zuordnung samt Begruendungstexten fest — muss auf die neue Zuordnung gezogen werden. Von den 12 Faellen aendern sich 9 (alle ausser `[null,0]→[null,0]`, `[null,33]→[null,0]`, `[null,null]→[null,null]`) |
| Speicher-Test „Speichern nach der Migration schreibt genau EINEN Gewitter-Eintrag" (`__tests__/routeCorridorPoolCatalogExpansion.test.ts:613-637`) | test | Erwartet aktuell `range: [null, 1]` fuer den Eingabewert `[null, 40]` (Zeile 629) — muss auf `[null, 2]` gezogen werden |
| Idempotenz-Test „ein bereits migrierter Korridor bleibt beim erneuten Laden unveraendert" (`__tests__/routeCorridorPoolCatalogExpansion.test.ts:639-651`) | test | Eingabe traegt bereits den neuen Schluessel `thunder_level_max` mit `range:[null,1]` — durchlaeuft `percentBoundToOrdinal()` gar nicht (der Schluesselvergleich in `migrateLegacyThunderCorridors()` greift nur bei `thunder_level`). Bleibt unveraendert gruen und dient als Negativ-Beleg fuer AC-4; **keine Aenderung noetig** |
| Einziger Produktiv-Bestandsdatensatz (`henning/briefings/74de939c.json`, Stand 2026-07-16) | data | `{"metric":"thunder_level","range":[null,1],"notify":true,"mark":false}` — 1 Prozent, wird nach dem Fix zu `[null, 0]` ("bis kein") statt bisher `[null, 1]` ("bis leicht") |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts` | MODIFY | (1) `percentBoundToOrdinal()` (Zeile 119-133): Sonderzweig `if (v === 0 \|\| v === 1 \|\| v === 2) return v;` entfaellt ersatzlos — jede Zahl wird als Prozent gedeutet. Drittelung auf vier Zielstufen: `null -> null`, `0-33 -> ORDINAL_ENUM.indexOf('NONE')` (0, kein), `34-66 -> ORDINAL_ENUM.indexOf('MED')` (2, mittel), `67-100 -> ORDINAL_ENUM.indexOf('HIGH')` (3, hoch) — ueber die kanonische Enum-Quelle abgeleitet, keine neuen Zahlenliterale (s. Implementation Details Punkt 2). (2) Docstring-Kommentar der Funktion (Zeile 119-126) auf die neue Zuordnung korrigiert. (3) Datei-Kopfkommentar Zeile 13 ("kein/mittel/hoch") auf die seit #1474 gueltigen vier Stufen ("kein/leicht/mittel/hoch") korrigiert (reine Doku-Korrektur, keine Verhaltensaenderung). |
| `frontend/src/lib/components/shared/corridor-editor/__tests__/routeCorridorPoolCatalogExpansion.test.ts` | MODIFY | `MIGRATION_CASES` (Zeile 555-568): 9 von 12 Faellen auf die neue Zuordnung gezogen, Begruendungstexte nennen die heutigen Stufennamen (kein/leicht/mittel/hoch), nicht die alten. Neuer Testfall prueft das **angezeigte Stufenwort** ueber `_THUNDER_ORDINAL_LABELS`-Index, nicht nur die nackte Zahl. Speicher-Test Zeile 613-637: Erwartungswert `range: [null, 1]` -> `[null, 2]`. Idempotenz-Test Zeile 639-651 bleibt **unveraendert** (s. Dependencies). |
| `tests/tdd/test_alert_metric_mapping_parity.py` | MODIFY | Kommentarstelle Zeile 135-137 ("kein/mittel/hoch", "Ordinal-Stundenwert 0/1/2") auf die seit #1474 gueltige 4-Stufen-Beschreibung ("kein/leicht/mittel/hoch", 0/1/2/3) korrigiert — reine Doku-Korrektur, die dokumentierte Ausnahme selbst (Bedingungen, Wirkung) bleibt inhaltlich unveraendert. |

## Implementation Details

**1. Neue Zuordnung (ersetzt den bisherigen Funktionskoerper vollstaendig):**

```
null            -> null
0 - 33 (Prozent) -> ORDINAL_ENUM.indexOf('NONE')  (0, kein)
34 - 66          -> ORDINAL_ENUM.indexOf('MED')   (2, mittel)
67 - 100         -> ORDINAL_ENUM.indexOf('HIGH')  (3, hoch)
```

Beide Grenzen (`range[0]`, `range[1]`) werden weiterhin unabhaengig
voneinander umgerechnet (unveraendert gegenueber dem Bestand — nur die
Zuordnungstabelle selbst aendert sich).

**2. Warum ueber `ORDINAL_ENUM.indexOf(...)` statt ueber die Zahlen `2`/`3`:**
`percentBoundToOrdinal()` ist die Stelle, die #2012 verursacht hat — und sie
ist dem lokalen Kopie-Waechter `thunderScaleLocalCopyGuard.test.ts` (#1480)
strukturell unsichtbar: Regel A/C des Waechters erkennen Stufen-**Woerter**
(Arrays/Objektschluessel bzw. String-Branches in Funktionen mit "thunder"/
"gewitter" im Namen) — `percentBoundToOrdinal()` arbeitet aber mit rohen
Zahlen und heisst weder "thunder" noch "gewitter". Eine Umbenennung allein
wuerde sie nicht in die Scanflaeche des Waechters ziehen (Regel C verlangt
zusaetzlich Stufen-**Woerter** in den Zweigen, keine Zahlen). Damit die
Funktion trotzdem an der kanonischen Kette (`ORDINAL_ENUM` -> Katalog ->
`ordinalLabels` -> `scale`) haengt statt eine vierte, unbewachte Kopie der
Skala zu fuehren, leitet sie die beiden migrierten Zielstufen ueber
`ORDINAL_ENUM.indexOf('MED')` bzw. `ORDINAL_ENUM.indexOf('HIGH')` ab.
`ORDINAL_ENUM` ist der einzige Eintrag in `CANONICAL_SYMBOLS` des
Waechters — ein kuenftiger Skalenwechsel (Umbenennung/Umsortierung der
Stufen) verschiebt die Bedeutung dieser Migration dann automatisch mit,
statt sie ein zweites Mal stillschweigend zurueckzulassen.

**3. Warum der Sonderzweig entfaellt:** `percentBoundToOrdinal()` wird
ausschliesslich von `migrateLegacyThunderCorridors()` aufgerufen, und die
laeuft ausschliesslich auf Korridor-Zeilen mit dem Alt-Schluessel
`thunder_level`. Dieser Schluessel trug in seiner gesamten Lebenszeit
(bis zur Ablösung durch `thunder_level_max` in #1425) ausschliesslich
Prozentwerte (`scale: [0, 100]`, Stand `7c42db9f^`). Es gibt keinen
Erzeuger, der unter diesem Schluessel je eine Ordinalzahl gespeichert hat
(s. Restrisiko unten). Der bisherige "ist schon ordinal"-Zweig loeste
dieses nicht existente Problem auf Kosten der tatsaechlichen Faelle: eine
gespeicherte `1` (1 Prozent) wurde unveraendert als Stufe 1 ("leicht")
durchgereicht statt als Stufe 0 ("kein") erkannt zu werden.

**4. Warum Stufe 1 ("leicht") ueber die Migration nicht erreichbar ist:**
Die Stufe "leicht" existierte in der Prozent-Epoche nicht — die 3-Stufen-Welt
kannte nur kein/mittel/hoch. Kein Bestandswert aus dieser Epoche kann "leicht"
gemeint haben. Die Drittelung bildet deshalb bewusst auf {0, 2, 3} ab, nicht
auf die vier gleich breiten Viertel {0, 1, 2, 3} — das wuerde eine Bedeutung
erfinden, die der Bestandswert nie hatte.

**5. Konkrete Beispiel-Umrechnungen (zur Verifikation der Testfaelle):**

| Prozentwert | Alte Ausgabe (fehlerhaft) | Neue Ausgabe |
|---|---|---|
| `null` | `null` | `null` |
| `[null, 40]` (ausgelieferter Alt-Default) | `[null, 1]` ("bis leicht") | `[null, 2]` ("bis mittel") |
| `[null, 1]` (einziger Produktiv-Datensatz) | `[null, 1]` ("bis leicht") | `[null, 0]` ("bis kein") |
| `[null, 100]` | `[null, 2]` ("bis hoch", Stufe 3 unerreichbar) | `[null, 3]` ("bis hoch") |

**6. Was unveraendert bleibt:** `migrateLegacyThunderCorridors()` selbst
(Schluesselwechsel `thunder_level` -> `thunder_level_max`, Erhalt von
`notify`/`mark`) und die Aufrufreihenfolge in `buildRoutePool()` (Migration
laeuft vor der `present`-Map-Bildung — Voraussetzung dafuer, dass der
Alt-Korridor nicht zusaetzlich als "unbekannt" in `unknownCorridors`
landet und beim naechsten Speichern doppelt persistiert wird). Zeilen, die
bereits `thunder_level_max` heissen, durchlaufen `percentBoundToOrdinal()`
gar nicht (der Schluesselvergleich in `migrateLegacyThunderCorridors()`
prueft exakt auf `thunder_level`) — Idempotenz ist damit strukturell
gegeben, nicht ueber diese Funktion. `corridor_threshold.py` und
`corridor_mark.py` (Python-Core) lesen den bereits migrierten Wert
unveraendert — kein Python-Eingriff (s. „Wirkung").

## Expected Behavior

- **Input:** Ein gespeicherter Trip-Korridor mit Alt-Schluessel
  `thunder_level` und einem Prozent-Wertebereich (`range: [min, max]`,
  `min`/`max` je `null` oder `0-100`).
- **Output:** Nach dem Laden des Wertebereiche-Editors erscheint die Zeile
  unter dem Schluessel `thunder_level_max` mit dem gemaess der Tabelle in
  Implementation Details Punkt 5 umgerechneten Ordinalwert (0/2/3, nie 1).
  `notify`/`mark` sind unveraendert uebernommen. Sobald der Nutzer speichert,
  ist dieser Wert die tatsaechliche Δ-Alarm- und Markier-Schwelle (s.
  „Wirkung").
- **Side effects:** Bereits migrierte Zeilen (Schluessel `thunder_level_max`)
  sind unberuehrt. Alle anderen Korridor-Metriken (`wind_gust`,
  `precipitation_sum`, `temperature_min`, `temperature_max`, `snow_line`)
  sind unberuehrt. Kein Server-seitiger Migrations-Job — die Umrechnung
  laeuft ausschliesslich beim Laden im Frontend, wie bisher.

## Acceptance Criteria

- **AC-1:** Given ein gespeicherter Alt-Korridor `{metric:"thunder_level",
  range:[null,40]}` (der ausgelieferte Default "bis 40 Prozent"), When der
  Wertebereiche-Editor laedt (`buildRoutePool`), Then erscheint er als
  `{metric:"thunder_level_max", range:[null,2]}` — angezeigt als "bis
  mittel", nicht mehr als "bis leicht".
  - Test: `routeCorridorPoolCatalogExpansion.test.ts`, aktualisierter
    `MIGRATION_CASES`-Fall; die Assertion prueft zusaetzlich
    `_THUNDER_ORDINAL_LABELS[row.max] === 'mittel'` (angezeigtes Wort, nicht
    nur der Index).

- **AC-2:** Given ein gespeicherter Alt-Korridor mit dem einzigen im
  Produktivbestand vorkommenden Wert `{metric:"thunder_level",
  range:[null,1]}` (1 Prozent), When der Wertebereiche-Editor laedt, Then
  erscheint er als `{metric:"thunder_level_max", range:[null,0]}` ("bis
  kein") — nicht mehr als "bis leicht" wie vor dem Fix.
  - Test: `routeCorridorPoolCatalogExpansion.test.ts`, neuer
    `MIGRATION_CASES`-Fall fuer den Produktiv-Wert `[null,1]`, prueft
    `row.max === 0` und `_THUNDER_ORDINAL_LABELS[0] === 'kein'`.

- **AC-3:** Given ein gespeicherter Alt-Korridor `{metric:"thunder_level",
  range:[null,100]}` (Prozent-Maximum), When der Wertebereiche-Editor laedt,
  Then erscheint er als `{metric:"thunder_level_max", range:[null,3]}` — die
  Stufe "hoch" ist damit ueber die Migration erstmals erreichbar (vor dem
  Fix strukturell unmoeglich).
  - Test: `routeCorridorPoolCatalogExpansion.test.ts`, aktualisierter
    `MIGRATION_CASES`-Fall, prueft `row.max === 3`.

- **AC-4:** Given ein bereits migrierter Korridor
  `{metric:"thunder_level_max", range:[null,1]}` (Stufe "leicht", echter
  Ordinalwert unter dem NEUEN Schluessel), When der Wertebereiche-Editor
  laedt, Then bleibt der Wert unveraendert `[null,1]` — die Korrektur der
  Prozent-Zuordnung wirkt sich nicht auf bereits migrierte Zeilen aus
  (Idempotenz ueber den Schluesselwechsel, nicht ueber `percentBoundToOrdinal`).
  - Test: bestehender Test „ein bereits migrierter Korridor bleibt beim
    erneuten Laden unveraendert" (`routeCorridorPoolCatalogExpansion.test.ts:639-651`)
    laeuft unveraendert gruen.

- **AC-5:** Given ein Korridor mit beidseitig gesetztem Wertebereich
  `{metric:"thunder_level", range:[0,100]}`, When der Wertebereiche-Editor
  laedt, Then werden Unter- und Obergrenze unabhaengig voneinander
  umgerechnet zu `range:[0,3]` — nicht zu einem einheitlichen Wert fuer
  beide Grenzen.
  - Test: `routeCorridorPoolCatalogExpansion.test.ts`, aktualisierter
    `MIGRATION_CASES`-Fall "beide Grenzen unabhaengig voneinander".

- **AC-6:** Given `percentBoundToOrdinal()` leitet die beiden migrierten
  Zielstufen ueber `ORDINAL_ENUM.indexOf('MED')` bzw.
  `ORDINAL_ENUM.indexOf('HIGH')` ab statt ueber eigene Zahlenliterale `2`/`3`,
  When der Funktionsquelltext gepruest wird, Then enthaelt er keinen rohen
  Zahlenliteral-Rueckgabewert `2` oder `3` fuer die beiden Prozent-Zweige —
  die Migration haengt strukturell an der einzigen von
  `thunderScaleLocalCopyGuard.test.ts` bewachten kanonischen Quelle, nicht
  an einer eigenen, unbewachten Zahl.
  - Test A (Verhalten, traegt die Zusicherung): die Migrations-Tests
    vergleichen die Zielstufen gegen `ORDINAL_ENUM.indexOf('MED')` bzw.
    `ORDINAL_ENUM.indexOf('HIGH')` statt gegen die Literale `2`/`3` — eine
    zusaetzliche Stufe in `ORDINAL_ENUM` verschiebt damit die Bedeutung der
    migrierten Grenzen nicht, sondern zieht die Erwartung mit.
  - Test B (Struktur, sekundaer): Struktur-Test in
    `corridorEditorState.test.ts` (analog `thunderScaleLocalCopyGuard.test.ts`)
    prueft den Quelltext von `percentBoundToOrdinal` auf Abwesenheit roher
    Zahlenliterale `2`/`3` als Rueckgabewert. Ergaenzt Test A, ersetzt ihn
    nicht — ein reiner Quelltext-Scan ist kein Verhaltensnachweis.

## Known Limitations

- **Restrisiko bei einer echten Ordinalzahl unter dem Alt-Schluessel:**
  Sollte irgendwo doch ein `thunder_level`-Korridor mit einer tatsaechlichen
  Stufenzahl (statt Prozent) gespeichert sein, wuerde diese jetzt faelschlich
  als Prozent gedeutet — eine gespeicherte `2` wuerde zu Stufe 0 ("kein")
  statt zur gemeinten Stufe "mittel". Diese Spec akzeptiert dieses Restrisiko
  bewusst: Der Alt-Schluessel trug laut Katalog-Definition (Stand
  `7c42db9f^`) ausschliesslich Prozentwerte, und der gesamte
  Produktivbestand (170 Dateien, `/var/lib/gregor/users`, Stand 2026-08-21)
  enthaelt genau eine `thunder_level`-Zeile — mit dem Wert `1`, konsistent
  mit der Prozent-Deutung. Es gibt keinen Code-Pfad, der seit der
  Skalen-Umstellung (#1425) noch einen `thunder_level`-Korridor erzeugt
  (weder Frontend noch Go noch Python) — die Menge der betroffenen
  Datensaetze kann nicht mehr wachsen.
- Kein Server-seitiger Migrations-Job — die Umrechnung greift erst, wenn der
  betroffene Trip ueber den Wertebereiche-Editor geladen wird (unveraendert
  gegenueber dem Bestand vor dieser Spec).
- **Nebenbefund, NICHT Teil dieser Spec:** `__tests__/corridorMarkSupport.test.ts:75`
  fuehrt `'thunder_level'` weiterhin in `TRIP_MARKABLE_METRICS` —
  `supportsMark()` ist rein namensbasiert und von der Skala unabhaengig,
  bleibt also von diesem Fix folgenlos unberuehrt. Kein Handlungsbedarf.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Korrektur einer bestehenden Umrechnungstabelle auf
  eine bereits an anderer Stelle etablierte Skala (`_THUNDER_ORDINAL_LABELS`
  / `ORDINAL_ENUM`, seit #1474). Kein neuer Provider, kein neuer Kanal, keine
  neue Auth-/Persistenz-Entscheidung, kein neues Datenformat — der
  `Corridor`-Datentyp und sein Speicherformat bleiben unveraendert.

## Changelog

- 2026-08-21: Initial spec created
- 2026-08-21: Ergaenzt um Abschnitt „Wirkung" (Δ-Alarm-/Markier-Wirkung, nicht
  nur Anzeige), Kopplung an `ORDINAL_ENUM` statt neuer Zahlenliterale (AC-6),
  zwei zusaetzliche Kommentar-Korrekturstellen (`corridorEditorState.ts:13`,
  `test_alert_metric_mapping_parity.py:135-137`), Klarstellung zum
  Idempotenz-Test (Zeile 639-651 bleibt unveraendert), Nebenbefund-Hinweis
  `corridorMarkSupport.test.ts:75`.
