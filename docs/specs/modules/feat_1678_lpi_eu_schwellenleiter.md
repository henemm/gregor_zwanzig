---
entity_id: feat_1678_lpi_eu_schwellenleiter
type: feature
created: 2026-08-16
updated: 2026-08-16
status: draft
version: "1.0"
tags: [gewitter, lpi, icon-eu, model-registry, thunder-fusion, issue-1678]
---

# ICON-EU bekommt eine eigene, belegte LPI-Schwellenleiter statt der Interim-Werte 5/20/50 (Issue #1678)

## Approval

- [x] Approved (PO, 2026-08-16)

## Purpose

Das Gebiet `EU_REST` (ICON-EU, Feld `lpi_con_max`) wird heute mit der Interim-Leiter
5/20/50 J/kg bewertet — Zahlen in derselben Größenordnung wie die belegte ICON-D2-Leiter
(1/30/50), obwohl es sich um eine **andere physikalische Größe** handelt. Gemessen führt
das zu bis zu 51× häufigeren Einstufungen bei gleicher Wetterlage (Gesamtkonzept 4.3).
Diese Arbeit ersetzt die Interim-Zeile durch eine Leiter, deren drei Werte aus der
DWD-Veröffentlichung stammen, die die Größe eingeführt hat.

**Der im Issue vorgeschlagene Weg (Eichskript nach Muster #1592 gegen die Open-Meteo
Historical Forecast API) entfällt** — er ist nicht gangbar und auch nicht nötig,
s. Abschnitt „Verworfene Alternativen".

## Source

- **File:** `src/app/model_registry.py`
- **Identifier:** `LPI_THRESHOLDS_JKG` / `lpi_thresholds_jkg()`

Schicht: **Python-Core / Domain-Backend** (`src/app/`, `src/providers/`, `src/output/`).
Keine Go-, keine Frontend-Beteiligung — die Leiter wirkt ausschließlich serverseitig in
der Gewitter-Fusion.

## Estimated Scope

- **LoC:** ~+80 / −15 (davon ~50 Test)
- **Files:** 4 Code/Test + 2 Doku
- **Effort:** low (Mechanik) / medium (Begründungspflicht)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/providers/thunder_routing.py` `_REGIONS` | liest | liefert `EU_REST` als Gebietsnamen (first-match-wins) |
| `src/providers/thunder_enrichment.py` `_fuse_thunder_levels()` | Konsument | löst die Leiter je Reihe auf und reicht sie durch |
| `src/output/metric_format.py` `_signal_levels()` | Konsument | wendet die drei Sprossen auf `lightning_potential_lpi_jkg` an |
| `src/providers/dwd_eu.py` | Datenquelle | holt `lpi_con_max` von `opendata.dwd.de`, mappt auf Feld `lpi` |

## Implementation Details

### Die neue Leiter

```python
LPI_THRESHOLDS_JKG: Dict[str, Tuple[float, float, float]] = {
    "DE_ALPEN": (1.0, 30.0, 50.0),    # unveraendert (Issue #1679, Bina et al. 2022)
    "EU_REST":  (7.14, 23.81, 86.16), # NEU (Issue #1678, Schroeder et al. 2022)
}
```

### Herleitung jeder einzelnen Sprosse

Quelle für alle drei Zahlen: **Schröder, Göcke, Köhler (2022), „Subgrid scale Lightning
Potential Index for ICON with parameterized convection", Reports on ICON Issue 010,
DOI 10.5676/DWD_pub/nwv/icon_010** — die DWD-Arbeit, mit der `LPI_CON_MAX` am 23.11.2022
für ICON-EU eingeführt wurde.

| Sprosse | Wert | Herleitung |
|---|---|---|
| leicht | **7,14** | Tab. 3, p=1/3: empfindlichste kalibrierte Nachweisschwelle („blitzt es überhaupt"). Direkte Entsprechung zu ICON-D2s Nachweisschwelle LPI > 1 J/kg, aus der die unterste DE_ALPEN-Sprosse gebildet wurde. **Die einzige als Schwelle publizierte Sprosse.** |
| mittel | **23,81** | Tab. 3, p=1: Punkt, an dem die Fläche mit Schwellenüberschreitung im Jahresmittel **gleich groß** ist wie die von LINET beobachtete Blitzfläche. Ab hier ist das Signal nicht mehr vorsorglich überzeichnet. |
| hoch | **86,16** | `LPI_c` = 86,16 J/kg, Sättigungskonstante der Arbeit; oberes Ende des sinnvollen Wertebereichs („for LPI > 100 J/kg the effect of KOI is not significant anymore"). |

Warum überhaupt eine eigene Leiter: `lpi_con_max` ist laut DWD Database Reference Manual
Kap. 6.5 eine andere Diagnostik als `lpi` — gleiche Formelstruktur, aber Aufwind und
Hydrometeore stammen aus dem Bechtold-Tiedtke-Konvektionsschema (Hydrometeore nach
Lopez 2016 approximiert) statt aus aufgelöster Strömung: *„the LPI can be calculated only
in a convection-permitting model setup"*.

### Verworfene Alternativen (mit Grund)

1. **Eichskript gegen die Open-Meteo Historical Forecast API** (der im Issue und im
   Gesamtkonzept 4.4 vorgeschlagene Weg): **nicht gangbar.** Open-Meteo lädt LPI
   ausschließlich für ICON-D2 und dort das Feld `lpi`
   (`Sources/App/Icon/IconVariableDownloadable.swift:184-185`:
   `return domain == .iconD2 ? ("lpi", …) : nil // only in icon d2`). `lpi_con_max` kommt
   dort nicht vor; die ICON-EU-Seite des Vergleichs existiert nicht und entsteht auch
   durch Warten nicht.
2. **Nur die belegte unterste Sprosse setzen, oben `None`** (analog zur CAPE-Deckelung):
   **wirkungsverkehrend.** `metric_format.py:423-426` verlangt alle drei Sprossen; ist eine
   `None`, trägt das Blitzpotenzial **gar kein** Signal bei — LPI verstummte in ganz
   `EU_REST`.
3. **Tabelle 3 wörtlich als Leiter (7,14 / 11,78 / 23,81):** senkt mittel und hoch und
   verschlimmert damit genau die Über-Einstufung, die dieses Ticket behebt. Zudem sind die
   drei p-Werte drei Kalibrierungen **derselben** Ja/Nein-Frage bei unterschiedlicher
   Fehlalarm-Toleranz — als Stärke-Sprossen gelesen vermischte das die Achse „Stärke"
   (kein/leicht/mittel/hoch) mit der Achse „Sicherheit" (möglich/wahrscheinlich/akut),
   die laut PO-Korrektur zu #1474 strikt getrennt bleiben.
4. **Verhältnis-Übertragung der D2-Leiter (× 7,14 → 214/357):** „hoch" wäre praktisch
   unerreichbar; die Linearitäts-Annahme ist durch die eigene Messung widerlegt (das
   Missverhältnis schrumpft von 51× bei Schwelle 5 auf 8,7× bei Schwelle 50).

## Expected Behavior

- **Input:** `thunder_region_for(lat, lon) == "EU_REST"` und ein Datenpunkt mit
  `lightning_potential_lpi_jkg` (aus ICON-EU `lpi_con_max`).
- **Output:** `thunder_level` des Datenpunkts, gebildet über die neue Leiter.
- **Side effects:** Keine. Kein neuer Mechanismus, keine Signatur-Änderung, kein
  Persistenz-Schema betroffen. Die Alles-oder-nichts-Regel und die
  Kein-stiller-Rückfall-Regel bleiben unangetastet.

## Acceptance Criteria

Alle Stufen-ACs werden am **Wirkort** geprüft — ein Datenpunkt läuft durch die produktive
Fusion (`thunder_level_from_signals()`) mit der aus `lpi_thresholds_jkg("<Gebiet>")`
aufgelösten Leiter. Geprüft wird die entstehende Stufe, **nie** der Tabelleninhalt.

- **AC-1:** Given ein Datenpunkt im Gebiet `EU_REST` mit Blitzpotenzial 60 J/kg / When die
  Gewitterstufe über die produktive Fusion gebildet wird / Then ist sie `MED` — heute ist
  sie `HIGH`, weil 60 die alte Hoch-Schwelle 50 überschreitet; die neue Hoch-Sprosse liegt
  bei 86,16.
  - Test: 60 J/kg durch die Fusion, erwartete Blitzpotenzial-Stufe `MED`.

- **AC-2:** Given ein Datenpunkt im Gebiet `EU_REST` mit Blitzpotenzial 21 J/kg / When die
  Gewitterstufe gebildet wird / Then ist sie `LOW` — heute ist sie `MED`, weil 21 die alte
  Mittel-Schwelle 20 überschreitet; die neue Mittel-Sprosse liegt bei 23,81.
  - Test: 21 J/kg durch die Fusion, erwartete Blitzpotenzial-Stufe `LOW`.

- **AC-3:** Given ein Datenpunkt im Gebiet `EU_REST` mit Blitzpotenzial 6 J/kg / When die
  Gewitterstufe gebildet wird / Then ist sie `NONE` („kein Gewitter") — heute ist sie `LOW`,
  weil 6 die alte Nachweisschwelle 5 überschreitet; die neue liegt bei 7,14.
  - Test: 6 J/kg durch die Fusion, erwartete Blitzpotenzial-Stufe `NONE`.

- **AC-4:** Given ein Datenpunkt im Gebiet `EU_REST` mit Blitzpotenzial 90 J/kg / When die
  Gewitterstufe gebildet wird / Then ist sie `HIGH` — die oberste Sprosse bleibt erreichbar
  und wird nicht zur toten Zusicherung. (Bewusst kein RED-Nachweis: dieser Wert ergibt vor
  und nach der Änderung `HIGH`; der Test bewacht, dass das Anheben der Sprosse die Stufe
  nicht abschafft.)
  - Test: 90 J/kg durch die Fusion, erwartete Blitzpotenzial-Stufe `HIGH`.

- **AC-5:** Given dieselben vier Blitzpotenzial-Werte (6, 21, 60, 90 J/kg) / When sie im
  Gebiet `DE_ALPEN` statt `EU_REST` bewertet werden / Then ergeben sie unverändert `LOW`,
  `LOW`, `HIGH`, `HIGH` nach der Leiter 1/30/50 — die ICON-D2-Einstufung bleibt von dieser
  Arbeit unberührt.
  - Test: dieselbe Fusion, nur mit `lpi_thresholds_jkg("DE_ALPEN")`.

- **AC-6:** Given das Gebiet `FR` / When ein Datenpunkt dort mit gesetztem Blitzpotenzial
  durch die Fusion läuft / Then trägt das Blitzpotenzial **kein** Signal bei (kein Eintrag
  `blitzpotenzial`), weil `lpi_thresholds_jkg("FR")` weiterhin `None` liefert — FR bewertet
  Blitzdichte, nicht LPI.
  - Test: Fusion eines FR-Datenpunkts; geprüft wird die Abwesenheit des
    Blitzpotenzial-Signals, nicht nur der `None`-Rückgabewert der Registry.

- **AC-7:** Given die Registry / When `LPI_THRESHOLDS_JKG` gelesen wird / Then trägt sie
  genau die zwei Gebiete `DE_ALPEN` (1,0 / 30,0 / 50,0) und `EU_REST` (7,14 / 23,81 /
  86,16), je Gebiet streng monoton steigend, und kein `FR`.
  - Test: Bestandsprüfung der Tabelle inklusive Monotonie beider Zeilen (ersetzt die heute
    auf 5/20/50 festgenagelte Zusicherung in
    `tests/tdd/test_lpi_threshold_region_table.py:69-77`).

## Known Limitations

1. **Nur die unterste Sprosse ist als Schwelle publiziert.** 23,81 ist als
   Kalibrierungspunkt publiziert, aber nicht als Stärke-Sprosse; 86,16 ist eine
   Formelkonstante der Arbeit, keine publizierte Warnschwelle. Beide oberen Sprossen sind
   damit **belegte Interpretation**, nicht belegte Zielsetzung der Quelle. Eine bessere
   Ableitung bräuchte eine eigene Klimatologie aus DWD-GRIB-Läufen über eine
   Konvektionssaison — bewusst nicht Teil dieser Arbeit (PO-Vorgabe: kein
   Grundlagenforschungs-Aufwand).
2. **Auflösungslücke:** Schröder et al. kalibrierten auf ICON-20 (≈20 km, ICON-EU-EPS
   Member 1), nicht auf das deterministische ICON-EU mit 6,5 km. Der Bericht macht keine
   Aussage zur Auflösungsabhängigkeit der Schwellen.
3. **Aggregationsfenster:** Das DWD-Handbuch nennt für `LPI_CON_MAX` χ = 1, 3 oder 6 h je
   nach Vorhersagestunde. Wir holen nur `FORECAST_HOURS = 1..24` (`dwd_eu.py:87`) und haben
   am GRIB-Kopf 60 min gemessen (`dwd_eu.py:42-45`) — im genutzten Bereich also 1 h. Eine
   spätere Ausweitung des Vorhersagehorizonts verschöbe die Leiter still nach oben.
4. **Die Unterscheidung hängt allein an der Region.** `dwd_eu.py:108` bildet `lpi_con_max`
   auf dasselbe interne Feld `lpi` ab wie ICON-D2; nur `_REGIONS` (first-match-wins)
   trennt die Leitern. Ein Umbau dort würde die Leiterwahl still falsch machen.
5. **Keine der beiden Haupttouren ist betroffen:** Karnischer Höhenweg (≈46,6 N / 12,8 O)
   liegt in `DE_ALPEN`, GR20/Korsika (≈42,2 N / 9,07 O) in `FR`. `EU_REST` betrifft Nord-,
   Ost- und Südeuropa.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — die Grundsatzentscheidung „je Quelle eine eigene Leiter,
  geeicht auf dieselbe Bedeutung" ist mit ADR-0048 („CAPE ≠ CAPE") und Issue #1679 bereits
  getroffen. Diese Arbeit füllt die dort ausgelassene Zeile.
- **Rationale:** Kein neuer Mechanismus, keine geänderte Schnittstelle, keine neue
  Datenquelle — ausschließlich belegte Werte in eine bestehende Tabelle.

## Changelog

- 2026-08-16: Initial spec created (Issue #1678)
