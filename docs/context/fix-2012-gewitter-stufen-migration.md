# Context: fix-2012-gewitter-stufen-migration

Issue: #2012 — „Bestands-Wertebereiche fuer Gewitter rutschen beim Oeffnen eine Stufe nach unten"

## Request Summary

Die Umrechnung alter Gewitter-Wertebereiche (`percentBoundToOrdinal` in
`corridorEditorState.ts`) stammt aus der 3-Stufen-Welt und bildet auf 0/1/2 ab. Seit #1474 hat
die Skala vier Stufen (0=kein · 1=leicht · 2=mittel · 3=hoch). Bestandswerte erscheinen dadurch
eine Stufe zu niedrig, Stufe 3 ist ueber diesen Pfad unerreichbar.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts:119-133` | `percentBoundToOrdinal` — die fehlerhafte Zuordnung |
| ebd. `:142-155` | `migrateLegacyThunderCorridors` — einziger Aufrufer, schluesselt `thunder_level` → `thunder_level_max` |
| ebd. `:~200` (`buildRoutePool`) | ruft die Migration vor dem Pool-Aufbau auf |
| ebd. `:407` | `ORDINAL_ENUM = ['NONE','LOW','MED','HIGH']` — bei #1474 **korrekt** auf vier Stufen gezogen |
| `frontend/.../corridor-editor/__tests__/routeCorridorPoolCatalogExpansion.test.ts:555-570` | `MIGRATION_CASES` haelt die 3-Stufen-Zuordnung fest (Begruendungstexte nennen 1 = „mittel", 2 = „hoch") |
| `CorridorEditor.svelte:82-84`, `CorridorEditorMobile.svelte` | `computeInitialRoute()` — laeuft bei **jedem** Oeffnen des Wertebereiche-Tabs |

## Messung am Produktivbestand (2026-08-21, `/var/lib/gregor/users`, 170 JSON-Dateien)

Genau **eine** Zeile traegt den Alt-Schluessel:

```
henning/briefings/74de939c.json  ("Lottis Abschiedfahrradtour", Datei-Stand 2026-07-16)
{"metric": "thunder_level", "range": [null, 1], "notify": true, "mark": false}
```

Die drei uebrigen Gewitter-Zeilen (KHW 403, Le Var ×2) tragen bereits `thunder_level_max` mit
`[null, 0]`. Positivkontrolle: der Scan findet 6 Objekte mit nicht-leerem `corridors` und 18
verschiedene Metriken — der Nullbefund fuer Werte > 2 ist nicht trivial wahr.

**Der Datensatz stammt aus der Prozent-Epoche.** Stand `7c42db9f^` (vor 2026-07-30) definierte
`corridorEditorState.ts:33`:

```ts
{ metric: 'thunder_level', label: 'Gewitter', unit: '%', scale: [0, 100], step: 5,
  note: 'Abbruch bei Gewitter', defaultMin: null, defaultMax: 40 }
```

Die gespeicherte `1` ist also **1 Prozent**, keine Stufe. `percentBoundToOrdinal` reicht 0/1/2
aber als „ist schon ordinal" unveraendert durch → angezeigt wird **„leicht"** statt **„kein"**.

⇒ Der einzige betroffene Produktivdatensatz wird falsch angezeigt — ueber den
Durchreich-Zweig, **nicht** ueber den im Issue beschriebenen `> 2`-Zweig. Der Fehler ist damit
breiter als das Ticket ihn beschreibt: die Funktion kann eine Prozentangabe nicht von einer
Stufennummer unterscheiden.

## Erzeuger-Lage: kann heute noch ein Prozentwert entstehen?

**Nein.**

- Frontend: der Gewitter-Eintrag ist aus `ROUTE_METRIC_DEFS` **entfernt** (Kommentar
  `corridorEditorState.ts:44-50`); Gewitter kommt ordinal aus dem Katalog als
  `thunder_level_max`, `ordinalLabels: ['kein','leicht','mittel','hoch']`
  (`corridorEditorState.test.ts:52`, `compareMetricCatalogLoader.ts:234`).
- Go: `thunder_level` existiert nur als `AlertMetric` (`internal/model/trip.go:46`) — das ist die
  **Alarm**-Seite, kein Korridor-Default. Kein Erzeuger.
- Python: `loader.py` / `report_config_resolver.py` lesen `corridors` nur, sie erzeugen keine.

⇒ Die Migration ist **kein toter Code** (ein echter Kunde), aber ein **abgeschlossener
Bestand**: die Menge der zu migrierenden Datensaetze kann nicht mehr wachsen.

## Existing Patterns

- `unknownCorridors`-Pass-Through (`buildRoutePool`, F001 aus #1425 S2): unbekannte Metrik-IDs
  werden **nie verworfen**, sondern unveraendert wieder mitgespeichert (BUG-DATALOSS-Klasse).
- Read-Modify-Write mit Merge bei Persistenz (CLAUDE.md § Daten-Schema-Reworks).

## Risks & Considerations

- **Prozent hatte nie eine Wirkung.** Laut Kommentar `corridorEditorState.ts:44-50` war der
  Stundenwert immer ein Ordinal; ein Prozent-Korridor schloss damit jeden Gewittergrad ein
  (Umkehrung der Absicht). Eine „richtige" Prozent→Stufe-Uebersetzung existiert nicht — jede
  Zuordnung ist Konvention, keine Ableitung. Es gibt auch keine kanonische Quelle dafuer:
  `thunder_ampel_band` (`src/output/metric_format.py:302`) bildet Stufen auf Ampelbaender ab,
  nicht Prozent auf Stufen.
- **Reiner Rueckbau kostet Sichtbarkeit.** Ohne Migration faellt die eine Bestandszeile in den
  `unknownCorridors`-Pass-Through: nicht geloescht, aber im Editor unsichtbar — der Nutzer
  kann seine Gewitter-Einstellung nicht mehr sehen oder aendern.
- **Schreib-Zeitpunkt.** Reines Oeffnen zeigt nur falsch an; sobald im Tab irgendetwas
  geaendert wird, wird der verschobene Wert persistiert.
- **Der Test muss mitgezogen werden**, sonst blockiert er den Fix — er prueft nur nackte
  Zahlen, nie das gerenderte Wort, und blieb deshalb seit #1474 gruen.
- **Keine Tour-Relevanz.** Die KHW-403-Konfiguration steht bereits auf dem neuen Schluessel.
