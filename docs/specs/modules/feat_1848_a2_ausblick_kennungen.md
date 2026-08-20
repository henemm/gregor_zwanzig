---
entity_id: feat_1848_a2_ausblick_kennungen
type: module
created: 2026-08-20
updated: 2026-08-20
status: draft
version: "1.0"
tags: [ausblick, metriken, persistenz, issue-1848]
---

# #1848 A2 — Der Ausblick speichert Kennungen statt Paare

## Approval

- [x] Approved — PO (Henning), 2026-08-20

## Purpose

Der 3-Tages-Ausblick speichert seine Spaltenauswahl heute als Paare aus Groesse und Auswertung
(`{"metric_id": "temperature", "aggregation": "max"}`). Er bekommt damit als einzige Flaeche ein
eigenes, viertes Vokabular — waehrend Kanal-An/Aus, Reihenfolge, SMS-Kuerzel und Schwellwerte
saemtlich ueber die reine Kennung verdrahtet sind. A2 loest dieses Sondervokabular ab: gespeichert
wird nur noch die Kennung, die Auswertungen leitet der Katalog ab.

## Source

- **Python-Core:** `src/app/models.py`, `src/app/loader.py`,
  `src/output/renderers/compare_outlook_metric_ids.py`, `src/services/report_config_resolver.py`
- **Frontend:** `frontend/src/lib/types.ts`,
  `frontend/src/lib/components/shared/weather-metrics-tab/compareMetricSelection.ts`,
  `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte`
- **Go-API:** keine Aenderung — `display_config` ist dort ein opakes `map[string]interface{}`
  (`internal/model/trip.go:111`), der Merge ist flach (`internal/handler/config_merge.go:11-22`)
  und inspiziert Listenelemente nie
- **Identifier:** `UnifiedWeatherDisplayConfig.outlook_metrics`, `resolve_outlook_metrics()`,
  `resolve_trip_outlook_metrics()`, `outlook_columns()`, `toStoredActiveMetrics()`

## Estimated Scope

- **LoC:** ~+160/-85 Produktivcode, dazu Tests (LoC-Override 500 gesetzt)
- **Files:** 7 Produktivdateien, ~17 Testdateien (grosser Teil ueber einen Helfer), 2 Dokumente
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py` | Upstream | `available_aggregations()` liefert die Auswertungen je Kennung; `summary_field_for()` das Datenfeld |
| `src/output/renderers/compare_metric_catalog.py` | Upstream | `key_for()` entscheidet, welche Auswertung im Ausblick ueberhaupt darstellbar ist |
| `src/app/models.py` (`allowed_metric_ids_for_report_type`) | Upstream | Kaskaden-Schnitt gegen die Grundauswahl (Regel D4) |
| `_merge_min_max_pairs()` (#1848 A1) | Downstream | faltet Tief+Hoch zur Spannen-Spalte; darf nicht brechen |
| ADR-0037 / ADR-0055 | Entscheidung | Drei-Werte-Semantik und Trip-Ausblick |

## Implementation Details

### Die Ableitungsregel

```
Kennung  ⇒  alle Auswertungen aus available_aggregations(kennung),
            die eine Zeile im Compare-Katalog haben (key_for != None),
            in der Reihenfolge von available_aggregations()
```

🔴 **Die Quelle ist `available_aggregations()`, NICHT `summary_fields.keys()`.** Gemessen:
`precipitation` und `thunder` tragen in `summary_fields` zusaetzlich `onset`, und
`summary_field_for('precipitation','onset')` loest auch auf. Ueber `summary_fields` abgeleitet
entstuenden also `onset`-Spalten. `available_aggregations()` filtert gegen
`_AGGREGATION_ORDER = ("min","max","avg","sum")` und laesst `onset` fallen.

### Verlustfreiheit — gemessen, nicht behauptet

Von 23 Kennungen im Compare-Katalog tragen **zwei** mehr als eine Auswertung (`temperature`,
`wind_chill`); bei den uebrigen 21 bestimmt die Kennung ihr Datenfeld eindeutig. Der
Spalten-Diff „alle Katalog-Paare der Kennung" gegen „abgeleitete Menge" ist fuer alle 23
identisch.

Einschraenkung offengelegt: bei 22 der 23 waren die Eingabelisten literal gleich, dort ist die
Gleichheit trivial. Echte Varianz gibt es nur bei `temperature` (`['max','min']` gegen
`['min','max']`), und sie ist folgenlos, weil `_merge_min_max_pairs()` Tief und Hoch ueber die
**Auswertung** zuordnet, nicht ueber die Position (`compare_outlook_metric_ids.py:186-189`).

### Vertraeglichkeit: der Leser versteht beide Formate — dauerhaft

Gemessen: der heutige Leser gibt bei reinen Kennungen `[]` zurueck, **nicht `None`**. `[]` heisst
in der Drei-Werte-Semantik „bewusst geleert" — der Ausblick-Block wird also **abgeschaltet**
statt auf die sieben Standardspalten zurueckzufallen. Beide Formate verwerfen einander still,
keine Seite wirft eine Ausnahme.

Daraus folgt: die Formattoleranz ist **keine Uebergangskruecke**, sondern Dauerzustand. Und
„Eintrag unauflösbar" darf nie denselben Zustand erzeugen wie „bewusst geleert".

## Expected Behavior

- **Input:** `display_config.outlook_metrics` als Liste von Zeichenketten (neu) **oder** von
  Paar-Objekten (Bestand) **oder** abwesend/`null` **oder** `[]`
- **Output:** dieselben Ausblick-Spalten wie heute, in denselben vier Ausgaben (HTML-Mail,
  Klartext, Kompaktmail, Telegram), in beiden Flaechen (Trip und Ortsvergleich)
- **Side effects:** Beim naechsten Speichern wird die Auswahl im Kennungsformat zurueckgeschrieben.
  Der bedingte Schreibpfad (`is not None`) bleibt, damit „nie gewaehlt" von „bewusst geleert"
  unterscheidbar bleibt.

## Acceptance Criteria

- **AC-1:** Given ein Trip ohne bisherige Ausblick-Auswahl / When der Nutzer im Editor
  „Niederschlag" und „Böen" fuer den 3-Tages-Ausblick waehlt und speichert / Then steht in der
  gespeicherten Datei unter `display_config.outlook_metrics` die Liste `["precipitation","gust"]`
  aus reinen Zeichenketten, ohne Objekte und ohne Auswertungsangabe.
  - Test: Speichern ueber den Editor-Pfad, danach die abgelegte JSON-Datei lesen und die
    Elementform pruefen.

- **AC-2:** Given ein Bestands-Trip, dessen Datei die Altform mit den beiden Paaren
  `{"metric_id":"temperature","aggregation":"min"}` und
  `{"metric_id":"temperature","aggregation":"max"}` enthaelt / When der Trip geladen wird / Then
  enthaelt die aufgeloeste Auswahl die Kennung `temperature` **genau einmal**, und die
  Auswahlreihenfolge der uebrigen Eintraege bleibt erhalten.
  - Test: Datei mit Altform-Inhalt laden, aufgeloeste Auswahl auszaehlen.

- **AC-3:** Given ein Trip, dessen gespeicherte Ausblick-Auswahl ausschliesslich unauflösbare
  Eintraege enthaelt / When das Briefing gerendert wird / Then erscheint der 3-Tages-Ausblick mit
  den sieben festen Standardspalten und eine Warnung wird protokolliert — der Block verschwindet
  **nicht**, denn „unauflösbar" ist etwas anderes als „bewusst geleert".
  - Test: Briefing mit unauflösbarer Auswahl rendern, Ausblick-Block im Ergebnis nachweisen.

- **AC-4:** Given die Kennung `temperature` ist fuer den Ausblick gewaehlt / When das Briefing
  gerendert wird / Then zeigt die Ausblick-Tabelle **genau eine** Temperatur-Spalte, deren Zelle
  Tief und Hoch mit Schraegstrich vereint (Form `9/27`), und zwar uebereinstimmend in HTML-Mail,
  Klartext, Kompaktmail und Telegram.
  - Test: Alle vier Ausgaben aus derselben Auswahl erzeugen und die Temperatur-Zelle vergleichen.

- **AC-5:** Given die Kennung `precipitation` ist gewaehlt, die im Zentralregister neben `sum`
  auch `onset` als Feld fuehrt / When die Spalten abgeleitet werden / Then entsteht **genau eine**
  Niederschlags-Spalte (die Summe) und keine zusaetzliche Spalte aus `onset`.
  - Test: Spaltenableitung fuer `precipitation` und `thunder` auszaehlen und benennen.

- **AC-6:** Given eine Ausblick-Auswahl mit mehreren Groessen / When Kopfzeile und Wertzeilen
  erzeugt werden / Then steht in jeder Spalte der Wert unter der zu ihm gehoerenden Beschriftung,
  und dieses Ergebnis ist ueber wiederholte Laeufe in frisch gestarteten Prozessen unveraendert.
  - Test: Beschriftung-Wert-Zuordnung pruefen, dazu ein Lauf in frischem Prozess mit abweichendem
    `PYTHONHASHSEED`.

- **AC-7:** Given ein Trip, der noch nie eine Ausblick-Auswahl gespeichert hat / When der Nutzer
  eine **andere** Einstellung aendert und speichert / Then bleibt `outlook_metrics` in der Datei
  weiterhin **abwesend** und der Ausblick zeigt die sieben festen Standardspalten; eine
  ausdruecklich geleerte Auswahl (`[]`) schaltet den Block dagegen weiterhin ab.
  - Test: Beide Faelle getrennt speichern und die Datei sowie die gerenderte Ausgabe pruefen.

- **AC-8:** Given der Nutzer oeffnet die Ausblick-Auswahl / When er die Liste der waehlbaren
  Groessen betrachtet / Then erscheint fuer Temperatur und fuer gefuehlte Temperatur **je ein
  einziger Eintrag** („Temperatur", „Gefühlte Temperatur") statt getrennter Eintraege fuer Minimum
  und Maximum — und zwar in **beiden** Flaechen, im Trip-Editor wie im Ortsvergleich-Editor.
  - Test: Auswahlliste in beiden Flaechen aufbauen und die Eintraege je Groesse auszaehlen.

- **AC-9:** Given ein Ortsvergleich, in dem der Nutzer „Temperatur" und „Wind" fuer den Ausblick
  waehlt / When er speichert und anschliessend die Vorschau oeffnet / Then zeigt die Vorschau eine
  Temperatur-Spalte als Spanne und eine Wind-Spalte als Einzelwert — die Auswahl kommt also
  unveraendert durch Speichern und Wiederlesen zurueck.
  - Test: Rundlauf Editor → Speichern → Vorschau, Spaltenformen pruefen.

- **AC-10:** Given zwei verschiedene Nutzer mit je eigener Ausblick-Auswahl / When beide speichern
  und danach ihre Trips laden / Then sieht jeder ausschliesslich seine eigene Auswahl, und keine
  der beiden Auswahlen erscheint beim jeweils anderen.
  - Test: Zwei Nutzerkennungen, getrennte Auswahl, kreuzweise gelesen.

- **AC-11:** Given die Schnittstellen-Referenz beschreibt das Speicherformat des Ausblicks / When
  A2 ausgeliefert ist / Then nennt sie das Kennungsformat, benennt die Altform als weiterhin
  lesbar und fuehrt den Trip neben dem Ortsvergleich als schreibende Flaeche auf.
  - Test: `# doc-compliance-test` gegen `docs/reference/api_contract.md`.

## Known Limitations

- **Die Halbauswahl entfaellt.** Fuer Temperatur und gefuehlte Temperatur laesst sich nach A2
  nicht mehr „nur das Hoch" anzeigen — die Kennung liefert zwangslaeufig die Spanne. Das ist der
  gemessene, einzige Informationsverlust der Umstellung und entspricht dem PO-Entscheid
  („Nur-das-Hoch-Zeigen entfaellt"). Der von A1 gebaute Einzelwert-Zweig bleibt fuer diese beiden
  Groessen bestehen, wird aber unerreichbar; er traegt weiterhin alle uebrigen Kennungen.
- **Rueckrollen nach der Auslieferung ist nicht verlustfrei.** Ein zurueckgerollter Stand liest
  Kennungen als unauflösbar und schaltet den Ausblick-Block ab. Heute ist die Exposition null
  (keine einzige gespeicherte Auswahl in Produktion und Staging, gemessen 2026-08-20 mit
  Positivkontrolle); sie entsteht erst mit der Nutzung.
- **`avg` bleibt aussen vor.** `temperature/avg` hat keine Compare-Katalogzeile und ist damit
  weiterhin nicht waehlbar. Bekaeme es eine, erzeugt die Ableitung zwei Spalten (Spanne +
  Mittelwert) mit asymmetrischer Beschriftung („Temperatur" und „Temperatur Mittel"). Das
  Verhalten ist definiert; die Entscheidung darueber gehoert zu A3.
- **Der Ortsvergleich schneidet weiterhin nicht gegen eine Grundauswahl** (ADR-0053) — A2 aendert
  daran nichts.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** Nachtrag an ADR-0055 (kein neues ADR)
- **Rationale:** ADR-0037 legte das Paar-Vokabular fest, ADR-0055 uebertrug es auf den Trip. A2
  aendert die **Speicherform**, nicht die Entscheidung ueber Semantik oder Zustaende — die
  Drei-Werte-Semantik bleibt woertlich gueltig. Ein Nachtrag mit der neuen Elementform genuegt;
  ein ablosendes ADR waere irrefuehrend, weil die eigentliche Entscheidung unveraendert bleibt.

## Changelog

- 2026-08-20: Initial spec created (Phase 3, Workflow `feat-1848-a2-outlook-kennungen`)
