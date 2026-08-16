# Context: feat-1678-lpi-eu-schwellenleiter

Issue #1678 — eigene Schwellenleiter für `lpi_con_max` (ICON-EU, Gebiet `EU_REST`).
Epic #1419 Rang 7 / Entscheidung E1b. Erstellt 2026-08-16 (Phase 1).

## Request Summary

Das Gebiet `EU_REST` (ICON-EU, `lpi_con_max`) wird heute mit der Interim-Leiter
5 / 20 / 50 J/kg bewertet — derselben Größenordnung wie die belegte ICON-D2-Leiter,
obwohl es eine andere physikalische Größe ist. Gemessen ergibt das bis zu Faktor 51
häufigere Einstufungen. Gesucht ist eine eigene, **belegte** Leiter für `EU_REST`.

## Zwei Befunde, die den im Ticket vorgeschlagenen Weg umstoßen

### 1. Der Open-Meteo-Eichweg ist nicht gangbar (gemessen, nicht vermutet)

Das Ticket und `docs/features/gewitter-gesamtkonzept.md` Abschnitt 4.4 setzen voraus,
Open-Meteos Historical Forecast / Previous Runs API liefere die ICON-EU-Läufe, die
Eichung sei „sofort rechenbar". Das trifft für LPI **nicht** zu:

- Open-Meteo lädt LPI **ausschließlich** für ICON-D2, und dort das Feld `lpi`:
  `Sources/App/Icon/IconVariableDownloadable.swift:184-185` —
  `case .lightning_potential: return domain == .iconD2 ? ("lpi", …) : nil // only in icon d2`.
  Für `iconEu` liefert die Variablenauflösung `nil`; `lpi_con_max` kommt im ganzen
  Open-Meteo-Repository nicht vor. Die Filter sind gezielt gesetzt — direkt darüber
  (`:182-183`) wird `cin_ml` für `iconEu` **sehr wohl** geladen.
- Bestätigt in der Doku (<https://open-meteo.com/en/docs/dwd-api>): „lightning potential
  and updraft are only in ICON D2".
- ⇒ Ein Perzentil-Abgleich `lpi_con_max` ↔ `lpi` über Open-Meteo ist unmöglich: die
  ICON-EU-Seite des Vergleichs existiert dort nicht, und Warten hilft nicht.
- Passt zum eigenen Code: `lpi_con_max` kommt bei uns direkt von `opendata.dwd.de`
  (GRIB2, `src/providers/dwd_eu.py:77`, `:205-217`) — Open-Meteo ist an diesem Pfad
  nicht beteiligt.

### 2. Eine publizierte Leiter existiert — aus genau der DWD-Arbeit, die die Größe eingeführt hat

**Schröder, Göcke, Köhler (2022), „Subgrid scale Lightning Potential Index for ICON with
parameterized convection", Reports on ICON Issue 010, DOI 10.5676/DWD_pub/nwv/icon_010.**

Tabelle 3 (S. 15) — Kalibrierung gegen LINET-Blitzbeobachtung, 366 Vorhersagen 03/2019–02/2020:

| p | LFD [day⁻¹km⁻¹] | **LPI (subgrid) [J/kg]** | MLPI [J/kg] |
|---|---|---|---|
| 1/3 | 0,0381 | **7,14** | 4,92 |
| 0,5 | 0,0809 | **11,78** | 10,99 |
| 1 | 0,2557 | **23,81** | 27,72 |

⚠️ **Wichtige Lesart — das ist KEINE Schwere-Leiter.** Die drei Werte sind drei
*alternative* Kalibrierungen **derselben** Ja/Nein-Frage („blitzt es in dieser Gitterzelle
in dieser Stunde?") bei unterschiedlich angesetzter Trefferwahrscheinlichkeit `p`
(Bericht S. 14, Gl. 2/3): bei p=1 ist die Fläche mit Schwellenüberschreitung im
Jahresmittel **gleich groß** wie die beobachtete Blitzfläche, bei p=1/3 dreimal so groß
(empfindlicher, mehr Fehlalarm). Sie als (leicht, mittel, hoch) zu übernehmen wäre eine
Fehldeutung der Quelle — das ist der zentrale Klärungspunkt für Phase 2.

Belegt ist damit **die unterste Sprosse**: „ab hier blitzt es überhaupt" liegt für
subgrid-LPI bei **7,14 J/kg** (empfindlich) bis **23,81 J/kg** (flächentreu) — gegenüber
**1 J/kg** bei aufgelöstem LPI (ICON-D2, ASR 2022). Für die oberen zwei Sprossen gibt es
für `lpi_con_max` **keine** publizierte Entsprechung.

### 3. `lpi_con_max` ist belegt eine andere Größe als `lpi`

DWD Database Reference Manual, Kap. 6.5:
- `LPI`: „calculated as a vertical integral of the squared updraft velocity weighted by a
  function that essentially contains the graupel concentration … **the LPI can be
  calculated only in a convection-permitting model setup**".
- `LPI_CON_MAX`: „… based on Lynn and Yair (2010) and Lopez (2016) … **only that the
  updraft velocity and hydrometeors are taken from the Bechtold-Tiedke convection
  scheme**. The variable contains the maximum since the last output."

Gleiche Einheit, gleiche Formelstruktur, **andere Eingangsgrößen** (approximierte
Hydrometeore). Bestätigt die Annahme im Gesamtkonzept 4.3 („verschiedene Physik") und
widerlegt den Kommentar in `src/providers/dwd_eu.py:90-95` („fachlich dieselbe Größe").

## Related Files

| Datei | Relevanz |
|---|---|
| `src/app/model_registry.py:145-167` | `LPI_THRESHOLDS_JKG` (DE_ALPEN 1/30/50, EU_REST 5/20/50 interim) + `lpi_thresholds_jkg(region)`. **Der zu ändernde Ort.** |
| `src/providers/thunder_enrichment.py:121,171-178,243` | Einziger Produktivaufrufer: holt die Leiter je Region und reicht sie an `_fuse_thunder_levels()` |
| `src/providers/thunder_enrichment.py:95-146` | `_fuse_thunder_levels(...)` — `lpi_low, lpi_med, lpi_high = lpi_thresholds or (None,None,None)`, gibt sie als `lpi_low_min/med_min/high_min` weiter |
| `src/providers/dwd_eu.py:77,87,97,205-217` | Abruf `lpi_con_max` von `opendata.dwd.de`, `FORECAST_HOURS = 1..24`, URL-Template |
| `src/providers/dwd_eu.py:100-108` | Mappt `lpi_con_max` → internes Feld `lpi` (derselbe Signalschlüssel wie ICON-D2 — der Ursprung der Gleichsetzung) |
| `src/providers/thunder_routing.py:63-67` | `_REGIONS` first-match-wins: FR → `fr_direct`, DE_ALPEN → `de_direct`, EU_REST (ganze Welt) → `eu_direct` |
| `src/output/metric_format.py:295,524` | Ausgabeseite, verweist auf die Leiter |
| `scripts/eichung_cape_schwelle.py` | Vorbild-Muster #1592 (einmaliges Eichskript → statische Tabelle) — **hier NICHT anwendbar**, s.o. |
| `docs/features/gewitter-gesamtkonzept.md:509-617` | Abschnitte 4.1–4.5: Messung, Ursachenanalyse, Meteoalarm-Prinzip |

## Existing Specs

- `docs/specs/modules/feat_1679_lpi_schwellen_region_tabelle.md` — legte die Gebietstabelle an
- `docs/specs/modules/feat_1679_cin_paarung_cape_leiter.md`
- `docs/specs/modules/fix_1592_s1_cape_modellschwelle.md` — Vorbild-Muster (CAPE)
- `docs/context/gewitter-1679-lpi-schwellen.md`

## Wächter / Tests

| Test | Zusicherung |
|---|---|
| `tests/tdd/test_lpi_threshold_region_table.py:69-77` | **Nagelt die Zahlen fest**: `LPI_THRESHOLDS_JKG` hat GENAU 2 Einträge, `DE_ALPEN == (1.0,30.0,50.0)`, `EU_REST == (5.0,20.0,50.0)`, kein `FR`. **Muss mit dieser Arbeit angepasst werden.** |
| `tests/tdd/test_lpi_threshold_region_table.py:91-178,252-259` | Lookup-Verhalten: unbekannte/fehlende Region → `None`, `FR` → `None` |
| `tests/tdd/test_thunder_potential_level_classification.py:29-39` | Einstufung liest die Leiter aus der Registry (nicht hartkodiert) |
| `tests/tdd/test_thunder_ladder_shared_across_signals.py:34-41,106-109` | Dieselbe Leiter über mehrere Signale |
| `tests/tdd/test_thunder_enrichment_fuses_level_shared_path.py:399-500` | Fusion nutzt die EU_REST-Leiter |
| `tests/tdd/test_thunder_origin_*.py` (7 Dateien) | Herkunftsanzeige führt die Leiter mit — Ausgabe an neun Orten |

## Dependencies

- **Upstream:** `providers.thunder_routing.thunder_region_for()` liefert die Region; `dwd_eu` liefert den Rohwert
- **Downstream:** `_fuse_thunder_levels()` → `thunder_level` → alle neun Gewitter-Ausgabeorte (Trip-Briefing, Ortsvergleich, Ausblick, SMS-Kürzel, Herkunftsanzeige) **und die Gewitter-Alarme**

## Risks & Considerations

1. **Zahlen sind heute festgenagelt** (`test_lpi_threshold_region_table.py:76`) — der Test ist Teil der Arbeit, nicht Kollateralschaden.
2. **Direkte Alarmwirkung** — aber **nicht** auf den beiden Haupttouren: Der Karnische
   Höhenweg (≈46,6 N / 12,8 O) fällt ins DE_ALPEN-Rechteck (43,17–58,09 N / −3,95–20,35 O),
   GR20/Korsika (≈42,2 N / 9,07 O) ins FR-Rechteck (41,3–51,1 N / −5,2–9,7 O, dort
   Blitzdichte statt LPI). `EU_REST` trifft v.a. Nord-, Ost- und Südeuropa — die Wirkung
   ist real, liegt aber außerhalb der heute gefahrenen Touren. Eine höhere Leiter senkt
   dort die Alarmhäufigkeit.
3. **Auflösungslücke im Beleg.** Schröder et al. kalibrierten auf **ICON-20** (≈20 km, ICON-EU-EPS Member 1), nicht auf das deterministische ICON-EU mit 6,5 km. Übertragung ist plausibel, aber nicht belegt — gehört als Known Limitation in die Spec.
4. **Aggregationsfenster:** Das Manual nennt für `LPI_CON_MAX` χ = 1, 3 **oder** 6 h je nach Vorhersagestunde. Wir holen nur `FORECAST_HOURS = 1..24` (`dwd_eu.py:87`) und haben am GRIB-Kopf 60 min gemessen (`dwd_eu.py:42-45`) — Risiko im genutzten Bereich gering, sollte aber als Invariante festgehalten werden.
5. **Interner Feldschlüssel bleibt geteilt:** `dwd_eu.py:108` bildet `lpi_con_max` auf dasselbe interne Feld `lpi` ab wie ICON-D2. Die Unterscheidung hängt allein an der Region — solange `_REGIONS` first-match-wins bleibt, trägt das; ein Umbau dort würde die Leiterwahl still falsch machen.
6. **Kein Eichskript nötig.** Der ursprünglich geplante Aufwand (Saison-Klimatologie) entfällt — was bleibt, ist eine belegte Tabellenzeile plus Herleitungsdokumentation. Das verschiebt den Schwerpunkt von „rechnen" zu „richtig lesen und begründen".

---

## Analysis (Phase 2)

### Type
Feature (Kalibrierungs-Änderung an einer Datentabelle, kein Bug — die Interim-Leiter war
in #1679 bewusst so gesetzt).

### Zwei harte Randbedingungen aus dem Code

1. **Die Leiter ist eine STÄRKE-Skala, keine Sicherheits-Skala.** `ThunderLevel`
   kein/leicht/mittel/hoch beschreibt, wie stark das Gewitter ist; möglich/wahrscheinlich/
   akut ist eine andere Achse (PO-Korrektur 2026-08-03 zu #1474). Sprossen aus
   Trefferwahrscheinlichkeiten zu bilden, ohne das zu benennen, würde beide Achsen
   vermischen.
2. **Alles-oder-nichts:** `metric_format.py:423-426` — ist auch nur EINE der drei Sprossen
   `None`, trägt das Blitzpotenzial **gar kein** Signal zur Fusion bei. Die naheliegende
   ehrliche Lösung „nur die belegte unterste Sprosse setzen, oben `None`"
   (Muster der CAPE-Deckelung) ist damit **nicht** billig zu haben — sie hieße, LPI
   verstummt in ganz `EU_REST`. Es müssen drei Zahlen sein.

### Was belegt ist — und was nicht

Sauber vergleichbar sind nur die **Nachweisschwellen** („blitzt es überhaupt"):
ICON-D2 aufgelöster LPI **> 1 J/kg** (ASR 2022, Grundlage der DE_ALPEN-Leiter) ↔
ICON-EU subgrid-LPI **7,14 J/kg** (Schröder et al. 2022, Tab. 3, empfindlichste
Kalibrierung). Die unterste Sprosse ist damit belegt ableitbar.

Für die oberen zwei Sprossen gibt es für `lpi_con_max` **keine** publizierte Entsprechung.
Die DE_ALPEN-Werte 30/50 stammen aus COSMO-D2-Verifikation auf 2,2 km — ein anderes
Kalibrierziel, nicht übertragbar.

### Drei Kandidaten für die Leiter

| | leicht | mittel | hoch | Herkunft | Wirkung ggü. heute (5/20/50) |
|---|---|---|---|---|---|
| **A** „Tabelle 3 wörtlich" | 7,14 | 11,78 | 23,81 | alle drei publiziert | mittel und hoch **sinken** → **mehr** Über-Einstufung. Verfehlt das Ticketziel. Zudem sind die drei Werte dieselbe Ja/Nein-Frage bei verschiedener Fehlalarm-Toleranz — als Stärke-Sprossen gelesen wäre das ein Achsen-Mix. |
| **B** „Nachweis → flächentreu → Sättigung" **(empfohlen)** | 7,14 | 23,81 | 86,16 | p=1/3 (Nachweis) · p=1 (Modellfläche = beobachtete Blitzfläche) · `LPI_c` (Sättigungskonstante) — alle drei Zahlen aus derselben Arbeit | alle drei Sprossen **steigen** → weniger Über-Einstufung in `EU_REST`. Richtung stimmt. |
| **C** „Verhältnis-Übertragung" | 7,14 | 214 | 357 | D2-Leiter × 7,14 (Nachweis-Verhältnis) | „hoch" praktisch unerreichbar (Bericht: LPI > 100 J/kg ist selten) — stille Fähigkeitsverluste. Zudem widerlegt die eigene Messung die Linearitäts-Annahme: das Missverhältnis schrumpft von 51× (bei 5) auf 8,7× (bei 50). |

**Empfehlung B.** Sie nutzt ausschließlich Zahlen aus der DWD-Arbeit, die die Größe
eingeführt hat, ist monoton, bewegt alle Sprossen in die vom Ticket geforderte Richtung
und macht die Spannweite der Größe explizit: 7,14 = „hier fängt es an", 23,81 = „so viel
Fläche wie tatsächlich Blitze beobachtet werden", 86,16 = „oberes Ende des sinnvollen
Wertebereichs".

**Ehrlich dazugesagt (Known Limitations der Spec):**
- Nur die unterste Sprosse ist als *Schwelle* publiziert. 23,81 ist als
  Kalibrierungspunkt publiziert, aber nicht als Stärke-Sprosse; 86,16 ist eine
  Formelkonstante, keine publizierte Schwelle. Beides ist **Interpretation** — belegt in
  der Herleitung, nicht in der Zielsetzung der Quelle.
- Kalibriert wurde auf **ICON-20** (≈20 km, ICON-EU-EPS Member 1), nicht auf das
  deterministische ICON-EU mit 6,5 km.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/app/model_registry.py:145-158` | MODIFY | `EU_REST`-Zeile + Herleitungs-Kommentar mit Quellenangabe |
| `tests/tdd/test_lpi_threshold_region_table.py:69-77` | MODIFY | Nagelt heute `(5.0, 20.0, 50.0)` fest |
| `tests/tdd/test_lpi_eu_rest_ladder.py` | CREATE | Verhaltens-Nachweis: ein `EU_REST`-Datenpunkt, der heute `hoch` bekommt, bekommt nach der Änderung `mittel`/`leicht` |
| `src/providers/dwd_eu.py:90-95` | MODIFY | Kommentar „fachlich dieselbe Größe" ist am DWD-Handbuch widerlegt |
| `docs/features/gewitter-gesamtkonzept.md:563-581` | MODIFY | Abschnitt 4.4 behauptet einen Open-Meteo-Eichweg, den es für LPI nicht gibt |

### Scope Assessment
- Dateien: 5 (2 Code, 2 Test, 2 Doku — Doku zählt nicht aufs LoC-Limit)
- Geschätzt: **+80 / −15 LoC** (davon ~50 Test)
- Risiko: **MEDIUM** — kleine Änderung, aber direkte Alarmwirkung in `EU_REST`

### Technischer Ansatz
Reine Tabellen-Änderung. Kein Eichskript, kein neuer Mechanismus, keine
Schnittstellen-Änderung — `lpi_thresholds_jkg()` und die Alles-oder-nichts-Regel bleiben
unangetastet. Der Nachweis muss am **Wirkort** geführt werden (Einstufung eines
Datenpunkts über `thunder_level_from_signals`), nicht nur am Tabelleneintrag.

### Open Questions
- [ ] Leiter-Kandidat B bestätigen (Freigabe kommt mit den ACs in Phase 3)

## Quellen

- <https://www.dwd.de/EN/ourservices/reports_on_icon/pdf_einzelbaende/2022_10.pdf> (Schröder et al. 2022)
- <https://www.dwd.de/DWD/forschung/nwv/fepub/icon_database_main.pdf> (Database Reference Manual)
- <https://www.dwd.de/DE/fachnutzer/forschung_lehre/numerische_wettervorhersage/nwv_aenderungen/_functions/DownloadBox_modellaenderungen/icon/pdf_2022/pdf_icon_global_23_11_2022.pdf> (Modelländerung 23.11.2022: LPI_CON_CI_MAX → LPI_CON_MAX für ICON-EU)
- <https://github.com/open-meteo/open-meteo/blob/main/Sources/App/Icon/IconVariableDownloadable.swift> (LPI nur ICON-D2)
- <https://asr.copernicus.org/articles/19/29/2022/> (COSMO-D2 LPI, Basis der DE_ALPEN-Leiter)
- <https://nhess.copernicus.org/articles/12/1969/2012/> (Klein Tank et al. 2012, einheitliche Wiederkehrperioden — Meteoalarm-Methodik)
