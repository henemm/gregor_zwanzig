---
entity_id: feat_2181_s2a_gewitter_mitschnitt_auswertung
type: feature
created: 2026-09-07
updated: 2026-09-07
status: draft
version: "1.0"
tags: [analysis, gewitter, cape, mitschnitt, khw, messwerkzeug]
---

# Auswertungsschicht für den Vorhersage-Mitschnitt — CAPE-Sprossen und HIGH-Häufigkeit (#2181 Scheibe S2a)

## Approval

- [ ] Approved

## Purpose

Misst zwei Thesen aus Issue #2181 gegen den bereits gesicherten Vorhersage-Mitschnitt des Karnischen
Höhenwegs (24.08.–05.09.2026, 13 Etappentage, 2246 Zeilen unter
`/home/hem/gz-messdaten/khw-2026-08-mitschnitt/`): **T2** (feuert die unterste CAPE-Sprosse an fast
jedem Sommertag?) und **T5** (hat die Höchststufe `hoch` auf dem KHW eine Entsprechung in der
Realität, gemessen gegen den in Scheibe S1 korrigierten Maßstab 2:13 nasse Tagesfenster?). Der
Prüfling ist ausschließlich die **Auswertungsschicht** — Vorlauf-Auswahl, Tages-Aggregation,
Dreiwertigkeit und Teilmengen-Wahl —, nicht die Gewitterrechnung selbst.

## Source

- **Neue Datei:** `src/analysis/thunder_replay.py` (kein Vorgänger, neues Paket `src/analysis/`)
- **Identifier:** freie Funktionen, kein Klassen-Interface (siehe Implementation Details)

**Affected Files:**

| File | Change Type | Description |
|------|-------------|--------------|
| `src/analysis/thunder_replay.py` | CREATE | Vorlauf-Auswahl, Tages-Aggregation, Dreiwertigkeit, Teilmengen-Messung |
| `tests/tdd/test_thunder_replay.py` | CREATE | Verhaltensprüfung gegen Fixtures aus echten Mitschnitt-Zeilen |
| `tests/fixtures/khw_2026_08/*.json` | CREATE | Ausgewählte, echte Mitschnitt-Zeilen (mehrere Etappentage, mehrere Segmente, mehrere `source`-Werte, mind. ein `null`-Fall für `cape_max_jkg` und für `thunder_level_max`) |

**Nicht Teil dieser Scheibe:** jede Änderung an `src/services/forecast_capture.py`,
`src/output/metric_format.py`, `src/providers/thunder_enrichment.py` — der Produktivpfad wird nicht
angefasst. Der Abruf- und Report-Teil (Ausführung des Mitschnitt-Auszugs, Protokoll-Text) bleibt
außerhalb des Repos unter `/home/hem/gz-messdaten/`, weil er genau einmal läuft.

> **Schicht-Hinweis:** Python-Core (`src/`), reines Analyse-Werkzeug ohne Netz-, DB- oder
> API-Anbindung. Kein Frontend, keine Go-API betroffen.

## Estimated Scope

- **LoC:** ~150 (Modul) + ~100 (Tests) — Fixtures zählen nicht als LoC
- **Files:** 2 Code-Dateien + 1 Fixture-Verzeichnis (mehrere Dateien)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.model_registry.cape_ladder_thresholds_jkg(model_id, region)` | Nachschlag (genutzt) | Liefert die geeichte (low, med, high)-CAPE-Leiter — für `icon_d2`×`DE_ALPEN` 300/750/1200 J/kg. Kein hartkodierter Zahlenwert im neuen Modul. |
| `providers.thunder_routing.thunder_region_for(lat, lon)` | Nachschlag (genutzt) | Bestimmt aus den Mitschnitt-Koordinaten das Gebiet (`DE_ALPEN` für den KHW), das an `cape_ladder_thresholds_jkg` geht. |
| `app.models.ThunderLevel` | Enum (genutzt) | Parst die Mitschnitt-Strings `"NONE"/"LOW"/"MED"/"HIGH"` in denselben Enum-Typ, den der Produktivpfad verwendet — kein eigener String-Vergleich. |
| `app.thunder_scale.thunder_ordinal(level)` | Funktion (genutzt) | Kanonische Ordnung (`NONE=0 < LOW=1 < MED=2 < HIGH=3`) für den Tages-Maximum-Vergleich mehrerer Segmente — dieselbe Ordnung wie `max_thunder()`, keine eigene Sortierregel. |
| `output.metric_format` (`_signal_levels()`, `thunder_level_from_signals()`) | **NICHT aufgerufen** (ADR-0025-Beleg) | Die Fusion existiert bereits und liefert bereits `thunder_level_max`/`cape_max_jkg` im Mitschnitt. T2/T5 lesen diese Werte nur nach — eine Nachrechnung der Fusion wäre eine zweite Rechenregel und würde nichts messen. Für die spätere Ablation (T1, Folgescheibe S2b) wird `_signal_levels()` dort direkt gebraucht, hier nicht. |
| `src/services/forecast_capture.py` (Zeilenformat) | Datenformat (gelesen, nicht importiert) | Definiert die JSON-Feldnamen der Fixtures: `fetched_at`, `fenster_start`, `fenster_ende`, `segment_id`, `source`, `werte.cape_max_jkg`, `werte.thunder_level_max`. |

## Implementation Details

### Datenmodell der Mitschnitt-Zeile (Fixture-Format, ungeändert aus `forecast_capture.py`)

```json
{"fetched_at": "2026-08-29T05:00:52.447170+00:00",
 "fenster_start": "2026-08-29T05:00:00+00:00", "fenster_ende": "2026-08-29T06:41:00+00:00",
 "segment_id": 1, "lat": 46.643014, "lon": 12.740327,
 "provider": "openmeteo", "model": "icon_d2", "source": "briefing",
 "werte": {"cape_max_jkg": 0.0, "thunder_level_max": "NONE"}}
```

Ein **Etappentag** ist das UTC-Kalenderdatum von `fenster_start` (alle Segmente eines Wandertags
liegen innerhalb desselben UTC-Kalendertags, da der Tageskorridor `day_window_start_hour`/
`day_window_end_hour` in Mitteleuropa nie über Mitternacht UTC reicht).

### 1. Vorlauf-Auswahl

```
vorlauf(zeile) = parse(zeile.fenster_start) - parse(zeile.fetched_at)

waehle_vorlauf_aermste(zeilen: list[dict]) -> Optional[dict]:
    gueltige = [z for z in zeilen if vorlauf(z) >= timedelta(0)]
    if not gueltige: return None
    return min(gueltige, key=vorlauf)
```

Gruppierung erfolgt je `(etappentag, segment_id)` — mehrere Schreib-Ereignisse desselben Segments
(Dedup-Regel `_schreibgrund`: "aenderung"/"takt") werden auf GENAU eine Zeile reduziert.

### 2. Tages-Aggregation

Für jeden Etappentag werden die je Segment ausgewählten Zeilen zu EINEM Tageswert verdichtet:

```
aggregiere_etappentag(segmentzeilen: list[dict]) -> dict:
    cape_werte = [z["werte"]["cape_max_jkg"] for z in segmentzeilen
                  if z["werte"]["cape_max_jkg"] is not None]
    level_werte = [ThunderLevel(z["werte"]["thunder_level_max"]) for z in segmentzeilen
                   if z["werte"]["thunder_level_max"] is not None]
    return {
        "cape_max_jkg": max(cape_werte) if cape_werte else None,
        "thunder_level_max": max(level_werte, key=thunder_ordinal) if level_werte else None,
    }
```

Diese Tages-Aggregation muss — als Gegenprobe gegen die echten Fixture-Daten — dasselbe
`cape_max_jkg` liefern, das ein simples Maximum über ALLE (ungefilterten) Zeilen desselben
Etappentags in den Original-Mitschnittdateien ergibt (AC-3).

### 3. Dreiwertigkeit

`None` (Feld fehlt im JSON / Wert ist `null`, "keine Aussage") · `ThunderLevel.NONE`
("geprüfte Entwarnung") · `ThunderLevel.LOW/MED/HIGH` (eine echte Stufe) dürfen an keiner Stelle der
Auswertung auf zwei Zustände kollabieren. Dieselbe Regel gilt für `cape_max_jkg`: `None` (kein
Messwert) und `0.0` (gemessen, unterhalb jeder Schwelle) sind verschiedene Aussagen.

### 4. Teilmengen-Festlegung

```
TEILMENGE_PRIMAER = frozenset({"briefing", "briefing_nacht"})   # tatsaechlich versendet
TEILMENGE_NUR_ALARM = frozenset({"alarm"})                       # separat ausgewiesen (Zirkularitaetsrisiko)
# "alle Quellen" = keine Filterung
```

Begründung Primärteilmenge: `briefing`/`briefing_nacht` sind die Zeilen, die tatsächlich in einem an
den Wanderer versendeten Briefing mündeten — die einzige Teilmenge, die die Frage "was hat der
Wanderer erfahren?" beantwortet. `alarm` wird bewusst NICHT als Primärquelle gewählt: ein
Alarm wird durch Schwellenüberschreitung selbst ausgelöst, eine T2/T5-Zählung auf dieser Teilmenge
wäre teilweise zirkulär. `trend`, `vorschau`, `unbekannt` sind interne Abrufe ohne garantierten
Wanderer-Kontakt. Jede Messfunktion liefert deshalb **drei** parallele Zahlen (Primär, alle Quellen,
nur Alarm) statt einer einzigen — die Empfindlichkeit gegenüber der Wahl ist damit sichtbarer
Bestandteil der Ausgabe, kein nachgereichter Kommentar.

### CAPE-Sprossen-Zählung (T2) und HIGH-Häufigkeit (T5)

```
cape_sprossen_treffer(tageswerte: dict[str, dict], schwellen: tuple[float, float, float]) -> dict:
    # je Sprosse (low/med/high aus schwellen): Anzahl Etappentage ueber der Sprosse,
    # Anzahl darunter, Anzahl "keine Aussage" (cape_max_jkg is None) -- drei Zaehler je Sprosse

hoch_haeufigkeit(tageswerte: dict[str, dict]) -> dict:
    # Anzahl Etappentage mit thunder_level_max == HIGH, getrennt von
    # "andere Stufe" (LOW/MED/NONE) und "keine Aussage" (None)
```

Beide Funktionen nehmen bereits aggregierte Tageswerte (Ergebnis von Schritt 2) entgegen — sie
kennen weder Segmente noch Vorlauf, damit jede Zuständigkeit einzeln testbar bleibt.

## Expected Behavior

- **Input:** Pfad zu den 13 Mitschnitt-JSONL-Dateien (in Fixtures: einzelne Zeilen als versionierte
  JSON-Fixtures), Modell-ID + Gebiet (`icon_d2`, `DE_ALPEN`) für die CAPE-Leiter.
- **Output:** Für T2 drei Zählungen je Sprosse (über/unter/keine Aussage) × drei Teilmengen; für T5
  vier Zählungen (hoch/andere Stufe/Entwarnung/keine Aussage) × drei Teilmengen. Kein
  Freitext-Bericht — der Bericht selbst entsteht außerhalb des Repos.
- **Side effects:** keine — reine Funktionen ohne Netz-, Datei-Schreib- oder DB-Zugriff. Lesen
  erfolgt ausschließlich aus dem übergebenen Fixture-/Mitschnitt-Datenstrukturen, nicht aus
  `GZ_...`-Umgebungsvariablen oder Live-Diensten.

## Acceptance Criteria

- **AC-1:** Given mehrere Mitschnitt-Zeilen desselben Etappentags und desselben `segment_id` mit
  unterschiedlichem `fetched_at` (unterschiedlicher Vorlauf), When die Vorlauf-Auswahl läuft, Then
  wird genau die Zeile mit dem kleinsten NICHT-negativen Vorlauf zurückgegeben.
  - Test: Fixture mit 3 Zeilen desselben Segments/Tages, unterschiedliche `fetched_at`-Werte; Test
    identifiziert die erwartete Zeile über ihren `fetched_at`-Wert, nicht über Dateiinhalt-String-Suche.

- **AC-2:** Given eine Mitschnitt-Zeile, deren `fetched_at` NACH `fenster_start` liegt (negativer
  Vorlauf), When die Vorlauf-Auswahl über eine Zeilenmenge läuft, die NUR diese eine Zeile enthält,
  Then liefert die Auswahl `None` — die Zeile wird verworfen, auch wenn keine Alternative existiert.
  - Test: Fixture mit genau einer Zeile mit negativem Vorlauf; Test prüft Rückgabewert `None`.

- **AC-3:** Given die je Segment ausgewählten Zeilen eines Etappentags, When der Tageswert
  aggregiert wird, Then entspricht das aggregierte `cape_max_jkg` dem Maximum über **genau diese
  ausgewählten** Zeilen — und eine verworfene Zeile desselben Tages und Segments, die einen
  GRÖSSEREN Vorlauf und zugleich einen HÖHEREN `cape_max_jkg` trägt, verändert das Ergebnis nicht.
  - Test: Fixture mit einem Etappentag, in dem eine ältere Vorhersage (größerer Vorlauf) einen
    höheren CAPE-Wert trägt als die jüngste desselben Segments; Test prüft, dass der Tageswert den
    Wert der **jüngsten** Zeile trägt und nicht den höheren älteren. Ein Durchlauf, der über alle
    ungefilterten Zeilen maximiert, muss an diesem Test scheitern.

- **AC-4:** Given eine Mitschnitt-Zeile mit `werte.thunder_level_max = null`, When Tageswerte
  klassifiziert werden, Then zählt der betroffene Tag weder als `ThunderLevel.NONE` (Entwarnung)
  noch als eine der drei Stufen, sondern erscheint ausschließlich im Zähler "keine Aussage" von
  `hoch_haeufigkeit()`.
  - Test: Fixture-Tag mit ausschließlich `thunder_level_max: null` in allen Segmentzeilen; Test
    prüft, dass `hoch_haeufigkeit()["keine_aussage"] == 1` und sowohl `["hoch"]` als auch
    `["entwarnung"]` für diesen Tag NICHT erhöht sind.

- **AC-5:** Given eine Mitschnitt-Zeile mit `werte.cape_max_jkg = null` und eine andere mit
  `werte.cape_max_jkg = 0.0`, When `cape_sprossen_treffer()` beide Tage auswertet, Then werden sie
  unterschiedlich gezählt — die erste als "keine Aussage", die zweite als "unter der Sprosse" — für
  jede der drei Sprossen einzeln.
  - Test: zwei Fixture-Tage (einer `null`, einer `0.0`); Test prüft für alle drei Sprossen, dass die
    beiden Tage in unterschiedlichen Zählkategorien landen.

- **AC-6:** Given der vollständige Mitschnitt mit den sechs vorkommenden `source`-Werten (unbekannt,
  alarm, trend, briefing, briefing_nacht, vorschau), When `cape_sprossen_treffer()` und
  `hoch_haeufigkeit()` ausgeführt werden, Then liefert jede Funktion DREI benannte Teilergebnisse im
  selben Rückgabewert: Primär (`source` ∈ {briefing, briefing_nacht}), "alle Quellen" (ungefiltert)
  und "nur alarm" (`source` == alarm) — nicht nur eines davon.
  - Test: Fixture mit Zeilen aus mindestens vier verschiedenen `source`-Werten (davon mind. eine
    `briefing`- und eine `alarm`-Zeile mit unterschiedlichem CAPE-Wert); Test prüft, dass sich die
    drei Teilergebnisse in mindestens einer Kennzahl unterscheiden, und dass alle drei im
    Rückgabe-Dict vorhanden sind.

- **AC-7:** Given Tageswerte mit bekanntem `cape_max_jkg`, When gegen die drei Sprossen aus
  `cape_ladder_thresholds_jkg("icon_d2", "DE_ALPEN")` geprüft wird, Then liefert
  `cape_sprossen_treffer()` für JEDE der drei Sprossen (low/med/high) eine EIGENE Zählung "Anzahl
  Etappentage über der Sprosse" — als drei getrennte Zahlen im Ergebnis, nicht als eine
  kombinierte Kennzahl.
  - Test: Fixture-Tage mit `cape_max_jkg`-Werten, die gezielt genau eine, genau zwei bzw. alle drei
    Sprossen überschreiten (z.B. 350, 800, 1300 J/kg); Test prüft, dass die drei Sprossen-Zähler
    unterschiedliche Werte tragen und jeweils genau die Tage zählen, die über der jeweiligen Sprosse
    liegen.

- **AC-8:** Given mehrere Segment-Zeilen desselben UTC-Kalendertags mit unterschiedlichen
  `segment_id`, When die Zeilen zu einem Etappentag gruppiert werden, Then landen alle Zeilen mit
  demselben Kalenderdatum von `fenster_start` in genau einer Gruppe, unabhängig von `segment_id` —
  und Zeilen eines ANDEREN Kalendertags landen nicht in dieser Gruppe.
  - Test: Fixture mit Zeilen aus zwei aufeinanderfolgenden Etappentagen, je mehrere `segment_id`;
    Test prüft Gruppengröße und dass keine Zeile im falschen Tag landet.

## Known Limitations

- **T1 (Ablation), T3 (CAPE-Zeitverlauf 29.08.) und T4 (Stufe vs. Niederschlag)** sind NICHT Teil
  dieser Scheibe. Sie brauchen eine Archiv-Rekonstruktion (Stundenwerte statt Mitschnitt) und ein
  vorgeschaltetes Kalibrier-Gate (CAPE-Abgleich auf der Kurzvorlauf-Teilmenge ≤ 6 h), das
  entscheidet, ob die Rekonstruktion überhaupt aussagefähig ist — Folgescheibe S2b.
- **Der Radar-Override** (`RadarNowcastService`) ist im Mitschnitt bereits eingerechnet — eine
  `HIGH`-Stufe kann von ihm angehoben worden sein. Diese Scheibe kann NICHT unterscheiden, ob eine
  HIGH-Stufe vom Radar oder von CAPE/Wettercode/LPI kam; das ist erst mit der Ablation (T1, S2b)
  möglich.
- **T2 misst den ROHEN `cape_max_jkg`-Wert gegen die Schwellenleiter, nicht die fusionierte,
  CIN-gedämpfte Stufe.** Ein Etappentag kann also "über der MED-Sprosse" zählen, obwohl die im
  Mitschnitt geführte `thunder_level_max` (nach CIN-Dämpfung) niedriger ausfiel — das ist
  beabsichtigt: T2 fragt nach dem rohen Signal, nicht nach dem Endergebnis der Fusion.
- **CIN und LPI haben im Mitschnitt keinen Vergleichswert** (nur `cape_max_jkg` und
  `thunder_level_max` werden geführt) — beide Größen können mit dieser Scheibe nicht nachgemessen
  werden.
- **Die Wahl der Primär-Teilmenge (`briefing`+`briefing_nacht`) ist eine Auswertungsentscheidung
  dieser Spec**, keine im Mitschnitt festgeschriebene Tatsache — AC-6 verlangt deshalb die parallele
  Empfindlichkeitsangabe gegenüber den beiden anderen Teilmengen.
- **ADR-0048** (modellabhängige Schwellen statt einer Zahl) ist bekannt verletzt (#2182) — hier nur
  erwähnt, nicht Gegenstand dieser Scheibe.
- **Das Mitschreiben der Signalherkunft** (`thunder_level_signals`) im Mitschnitt selbst ist kein
  Teil dieser Scheibe — eigener Designpunkt, eigenes Ticket (siehe Kontextdokument, Abschnitt
  "Abgetrennt").
- **Die Menge der Etappentage ist eine Entscheidung des AUFRUFERS, nicht der Daten.**
  `tageswerte_je_teilmenge(zeilen, etappentage=None)` zählt in der Vorgabe-Betriebsart **jeden** Tag,
  für den eine gültige Vorhersage existiert; mit `etappentage=<Menge von ISO-Datumsstrings>` zählen
  ausschließlich die übergebenen Tage (ein Tag außerhalb fällt heraus, auch wenn er gültige Werte
  trägt; ein genannter Tag ohne Vorhersage wird nicht erfunden). Gegen den KHW-Mitschnitt liefert
  die Auswertung ohne `etappentage` **15** Tage (2026-08-22 bis 2026-09-05), weil der Mitschnitt
  zwei Tage vor Tourbeginn ansetzt — der 22. und 23.08. tragen volle, gültige Werte in allen drei
  Teilmengen (22.08.: 40 J/kg primär bzw. 50 sonst, NONE; 23.08.: 100 bzw. 90, NONE). **Maßgeblich
  für die Auswertung von T2 und T5 sind jedoch die 13 Tourtage 2026-08-24 bis 2026-09-05**
  (PO-Entscheid vom 2026-09-07), weil nur dieser Nenner mit dem S1-Maßstab „2:13" zusammenpasst.
  Das Auswertungsmodul kennt diesen Zeitraum bewusst nicht; er wird beim Aufruf übergeben.
- **`keine_aussage` feuert gegen den echten KHW-Bestand nie.** In jeder Teilmenge und für jede
  Sprosse ist die Kennzahl exakt 0 — an allen 13 Tourtagen lag mindestens eine gültige Vorhersage
  mit Wert vor. Die Dreiwertigkeit (AC-4/AC-5) ist umgesetzt und fixture-geprüft, sie schlägt gegen
  diese Daten aber nicht an. Das ist eine Eigenschaft der Daten, keine Lücke der Umsetzung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0025
- **Rationale:** ADR-0025 legt fest, dass es genau EINE Gewitter-Fusionsquelle gibt
  (`_signal_levels()`/`thunder_level_from_signals()` in `metric_format.py`) und keine zweite
  Berechnung entstehen darf. Diese Spec baut deshalb bewusst KEINE eigene Fusionslogik nach: T2 und
  T5 lesen ausschließlich die bereits vom Produktivpfad berechneten Werte (`cape_max_jkg`,
  `thunder_level_max`) aus dem Mitschnitt und werten sie nach; für die CAPE-Sprossen wird nur die
  bereits geeichte Schwellenleiter (`model_registry.cape_ladder_thresholds_jkg()`) nachgeschlagen,
  die CIN-Dämpfung wird NICHT nachgerechnet (siehe Known Limitations). ADR-0048 gilt als bekannt
  verletzt (#2182) und wird von dieser Scheibe nicht adressiert.

## Changelog

- 2026-09-07: Initial spec created (Issue #2181, Scheibe S2a)
- 2026-09-07: AC-3 korrigiert — die Referenz war das Maximum über ALLE ungefilterten Zeilen des
  Kalendertags und widersprach damit AC-1: eine ältere Vorhersage mit höherem `cape_max_jkg` hätte
  den Tageswert bestimmt und die Vorlauf-Auswahl wirkungslos gemacht. Neue Fassung misst gegen die
  ausgewählte Zeilenmenge und verlangt einen Test, an dem eine Maximierung über alle Zeilen
  **scheitert**.
