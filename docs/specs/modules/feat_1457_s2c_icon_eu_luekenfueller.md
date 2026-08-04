---
entity_id: feat_1457_s2c_icon_eu_luekenfueller
status: draft
type: module
created: 2026-08-04
updated: 2026-08-04
version: "1.0"
tags: [gewitter, provider, dwd, icon-eu, s2c]
---

# DWD ICON-EU als Gewitter-Lückenfüller für Rest-Europa

## Approval

- [x] Approved (PO, 2026-08-04)

## Purpose

Dritte und letzte Scheibe von #1457 (Konzept #1419, Schritt S2): DWD
ICON-EU (grobmaschig, ~6,5 km, liefert nur Blitzpotenzial `lpi_con_max`,
kein Hagel) wird als Gewitterquelle für alle Gebiete eingebaut, die weder
von Météo-France (S2a, FR/Korsika) noch von ICON-D2 (S2b,
DE/Alpen/Österreich) abgedeckt sind — Rest-Europa. Schließt die Landkarte
der Gewittersignal-Beschaffung; danach ist #1457 vollständig.

> ⚠️ **Namensfalle, zweimal bereits eingetreten (S2a `LITOTA3`, S2b lief
> glimpflicher):** `lpi_con_max` ist bislang nur ein Konzept-Kurzname aus
> #1419, **kein bestätigter DWD-Open-Data-Feldname**
> (`docs/reference/decision_matrix.md` Z.36 markiert das ausdrücklich).
> Diese Spec schreibt ihn bewusst nur als Arbeitshypothese fest — AC-6
> verlangt die Live-Prüfung gegen den echten Dienst vor Produktivnutzung.

## Source

- **File:** `src/providers/dwd_eu.py` (neu), `src/providers/base.py`,
  `src/providers/thunder_routing.py`
- **Identifier:** `DwdEuDirectProvider` (neu),
  `DwdEuDirectProvider.fetch_thunder_signals_named()` (neu),
  `_REGIONS`-Eintrag `"EU_REST"` (neu, Catch-all)

**Schicht:** Python-Core (`src/providers/`). Keine Go-API, kein Frontend
— analog S2a/S2b. `thunder_enrichment.py` und `models.py` werden **nicht**
verändert (s. Implementation Details).

## Estimated Scope

- **LoC:** ~150–220 Produktivcode (`dwd_eu.py` neu, `thunder_routing.py`
  +1 Zeile, `base.py` +Registrierungsblock) + ~280–420 Tests =
  **~430–640**
- **Files:** 1 neue Provider-Datei, 2 geändert
  (`thunder_routing.py`, `base.py`), mind. 2 Testdateien neu (Fetch/
  Fail-soft, Live-Namenscheck), 1 Testdatei erweitert
  (`test_thunder_enrichment_shared_path.py` um `"eu_direct"` und
  `"lpi_con_max"` als verbotene Strings — die beiden Einträge stehen dort
  laut S2b-Recherche bereits defensiv vorbereitet)
- **Effort:** medium
  — S2a und S2b sind beide deutlich über ihrer ursprünglichen Schätzung
  gelandet (Live-Namensfallen, empirische Fehlwert-Verifikation, Lauf-
  Fallback-Härtung kosten regelmäßig mehr als der erste Scope-Schnitt
  vorsieht). Dieser Wert ist ein Erwartungswert, kein Versprechen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| DWD ICON-EU Open-Data (`opendata.dwd.de`) | externer Dienst | Neuer Verzeichnispfad, gleiche Domain wie ICON-D2 (S2b) — kein neuer Egress-Freischaltungsbedarf erwartet, aber vor Implementierung gegenprüfen |
| `rasterio` (`MemoryFile`) | Bibliothek | Punktwert aus GRIB2-Antwort lesen, bestehendes Muster aus `dwd.py` |
| `providers.thunder_routing._REGIONS` | intern | Neue, LETZTE Zeile als Catch-all — Reihenfolge ist tragend (s. Risiko 1) |
| `providers.base._load_providers()` | intern | Neuer `register_provider("eu_direct", ...)`-Block |
| `providers.thunder_enrichment._SIGNAL_ZU_FELD` | intern | **Keine Änderung nötig** — `DwdEuDirectProvider` liefert unter dem bestehenden Signal-Key `"lpi"`, der bereits auf `lightning_potential_lpi_jkg` zeigt (S2b) |
| `docs/reference/decision_matrix.md` Z.36 | Dokumentation | Warnt bereits vor `lpi_con_max` als unverifiziert — nach AC-6 aktualisieren |

## Implementation Details

```
GEMEINSAMER WEG BLEIBT UNVERAENDERT (PO-Vorgabe seit S2a) — S2c fasst
weder thunder_enrichment.py noch models.py an. Beide S2b-Erweiterungen
(fetch_thunder_signals_named-Protokoll, generalisierter Fill-Waechter,
_SIGNAL_ZU_FELD-Tabelle) sind bereits vorhanden und ausreichend.

1. NEUE Geschwister-Provider-Klasse in NEUER Datei `dwd_eu.py`
   (Entscheidung, nicht Umbau von `dwd.py`):
   - `dwd.py` ist komplett hart auf ICON-D2 verdrahtet (BASE_URL,
     PARAMS, `_build_url` interpoliert `_germany_` fest in den
     Dateinamen, s. Kontext-Dokument Risiko 2) — KEIN Modell-Parameter
     irgendwo, die ganze Datei ist eine Konfiguration.
   - Eine Parametrisierung der bestehenden, gehärteten `DwdDirectProvider`
     (S2b, mehrere Adversary-Fix-Loops) würde diesen Code erneut
     anfassen und regressionsgefährden, ohne fachlichen Gewinn.
   - Stattdessen: neue Klasse `DwdEuDirectProvider` in `dwd_eu.py`,
     analog wie `fr_direct` (`meteofrance.py`) und `de_direct`
     (`dwd.py`) bereits zwei unabhängige Dateien sind — derselbe Schnitt
     wird für den dritten Provider fortgesetzt.
   - Eigene Modulkonstanten (Muster `dwd.py`/`meteofrance.py`):
     eigene `BASE_URL` (ICON-EU-Pfad auf `opendata.dwd.de`, vor
     Implementierung gegen echtes Verzeichnislisting geprüft), eigener
     Dateiname-Builder (ICON-EU-Namensschema unterscheidet sich von
     ICON-D2, VOR Implementierung gegen eine echte Antwort geprüft,
     nicht von `_build_url` in `dwd.py` übernommen).

2. `DwdEuDirectProvider.fetch_thunder_signals_named(location, start, end)`
     -> dict[str, dict[int, Optional[float]]]
   Liefert GENAU EIN Signal unter dem Schlüssel `"lpi"` (nicht
   `"lpi_con_max"` — das ist nur der externe Parametername, kein
   interner Key, s. Design-Entscheidung 2 unten). `fetch_thunder_signals()`
   bleibt dünner Wrapper (Pflichtteil des Protokolls), analog
   `meteofrance.py:508-540` / `dwd.py:441-453`.
   Eigenes Zeitbudget `THUNDER_FETCH_DEADLINE_SECONDS`: hergeleitet aus
   tatsächlicher Abrufzahl (nur `lpi_con_max`, kein Hagel ⇒ ca. 24 statt
   bis zu 48 Abrufen wie ICON-D2) × gemessener Latenz — NICHT von
   ICON-D2 (90s) oder Météo-France (45s) übernommen, eigens hergeleitet
   (AC-4). Eigener Lauf-Sicherheitsabstand mit Rückfall auf ältere Läufe
   bei 404 (Muster `THUNDER_RUN_SAFETY_HOURS`, `meteofrance.py:207`,
   AC-7). Jede Ausnahme -> {}, nie werfen.

3. `thunder_routing.py`: EINE neue Zeile, als LETZTE in `_REGIONS`
   (Catch-all für den Rest der Welt):
     _ThunderRegion("EU_REST", -90.0, 90.0, -180.0, 180.0, "eu_direct")
   MUSS nach den bestehenden FR- und DE_ALPEN-Zeilen stehen — `_REGIONS`
   ist first-match-wins (Modul-Docstring, thunder_routing.py Z.13-17
   nennt S2c bereits explizit als "Lückenfüller für den Rest"). Stünde
   die Zeile früher, würde sie FR und DE_ALPEN verschlucken (AC-8).

4. `base.py::_load_providers()`: neuer
     register_provider("eu_direct", lambda: DwdEuDirectProvider())
   Block, analog den bestehenden fünf Einträgen (Z.221-268).

5. Fehlwert-Marker: VOR erster produktiver Nutzung empirisch gegen echte
   ICON-EU-GRIB2-Dateien prüfen (rasterio `dataset.nodata` o.ä.) — NICHT
   von ICON-D2 (`9999.0`, S2b) übernehmen oder raten (AC-2). Zweimal in
   Folge (`echotop`→`-999.0` widerlegt bei S2a-Analogie, ICON-D2
   9999.0 statt vermuteter -999.0 bei S2b) hat sich Übernahme statt
   Messung als falsch erwiesen — dieselbe Disziplin gilt hier.
```

## Expected Behavior

- **Input:** eine Position außerhalb des FR- und DE_ALPEN-Zuständigkeits-
  gebiets (z. B. Iberische Halbinsel, Balkan, Skandinavien) mit Zeitraum
- **Output:** dieselbe Vorhersage wie heute, zusätzlich mit gefülltem
  Blitzpotenzial-Feld (`lightning_potential_lpi_jkg`) an diesen Orten;
  `hail_potential_grau_gsp` bleibt dort weiterhin `None` (ICON-EU liefert
  kein Hagelsignal, beabsichtigt)
- **Side effects:** zusätzliche HTTP-Abrufe an `opendata.dwd.de` (1 neuer
  Parameter × bis zu 24 Zeitschritte je Ort und Lauf)

## Acceptance Criteria

- **AC-1 (Wirkungs-Nachweis, Ende-zu-Ende):** Given eine Position außerhalb
  des FR- und DE_ALPEN-Gebiets (z. B. Madrid, 40,4 N / -3,7 O) / When eine
  Vorhersage über den **regulären** Weg abgerufen wird
  (`OpenMeteoProvider.fetch_forecast`, funktionierende Hauptquelle, kein
  Ausfall) / Then trägt mindestens ein Zeitpunkt einen
  Blitzpotenzial-Wert aus DWD ICON-EU, während dieselbe Abfrage heute für
  dieses Feld durchgängig leer bleibt.
  - Test: Gegen eine aufgezeichnete ICON-EU-Antwort (`lpi_con_max`-
    Fixture) wird der komplette Weg `DwdEuDirectProvider.fetch_thunder_
    signals_named` → `thunder_routing.thunder_provider_for` →
    `thunder_enrichment.enrich_thunder` → `ForecastDataPoint`
    durchgespielt und der Wert am Datenpunkt nachgewiesen. Gegenprobe:
    Wird der Aufruf aus dem regulären Rückgabeweg von `fetch_forecast`
    entfernt und nur isoliert gegen die Provider-Methode getestet, muss
    dieser Test — anders als ein reiner Methodentest — rot werden.
    **Warum diese Formulierung Pflicht ist:** Bei S2a waren AC-1 bis
    AC-6 vollständig erfüllt und der Adversary hatte VERIFIED erteilt,
    obwohl die Blitzdichte nie einen Nutzer erreichte — der Anschluss
    ans Produktivsystem fehlte. Für S2c ist das Risiko strukturell
    kleiner (der Anschluss hängt bereits zweifach produktiv), trotzdem
    beweist nur dieses AC die Wirkung statt der reinen Fähigkeit.

- **AC-2:** Given DWD liefert für einen Zeitpunkt keinen Wert, ODER
  liefert den (bei Implementierung empirisch verifizierten) Sentinel-
  Fehlwert-Marker / When die Vorhersage gebaut wird / Then bleibt das
  Blitzpotenzial-Feld **`None`** — nie `0` und nie der rohe Sentinel-
  Wert.
  - Test: Eine Fixture ohne Wert für eine Stunde erzeugt an diesem
    Zeitpunkt `None`; eine zweite Fixture mit dem verifizierten
    Sentinel-Rohwert erzeugt ebenfalls `None`. Ein Test, der `0` oder
    den rohen Sentinel-Wert erwartet, muss fehlschlagen.

- **AC-3:** Given der Abruf von Blitzpotenzial über ICON-EU scheitert
  vollständig (Serverfehler, Zeitüberschreitung, Netzfehler) / When eine
  Vorhersage abgerufen wird / Then wird sie **trotzdem vollständig
  geliefert**, nur ohne das neue Feld — der Fehler kippt die Vorhersage
  nicht.
  - Test: Ein Abruf, der eine Ausnahme wirft, führt zu einer
    vollständigen Vorhersage mit Temperatur und Wind und leerem
    Blitzpotenzial-Feld. Gegenprobe: Wird das Werfen im
    Anreicherungspfad zugelassen, muss der Test rot werden.

- **AC-4 (eigenes, hergeleitetes Zeitbudget):** Given die ICON-EU-
  Gewitterabrufe brauchen ungewöhnlich lange / When das eigene
  Zeitbudget der Anreicherung erschöpft ist / Then bricht **nur die
  Anreicherung** ab, die Grundvorhersage behält ihr eigenes,
  unangetastetes Budget, UND das neue Budget ist nachweislich aus der
  tatsächlichen Abrufzahl (≈24, nur `lpi_con_max`) × gemessener Latenz
  hergeleitet — nicht von ICON-D2 (90s) oder Météo-France (45s)
  übernommen.
  - Test: Mit künstlich kleingesetztem Anreicherungsbudget gegen einen
    langsamen lokalen Server endet der Aufruf innerhalb der Grenze und
    liefert die Grundvorhersage; die Anzahl der noch erfolgten Abrufe
    belegt, dass nicht auf das große Budget gewartet wurde (Muster:
    `tests/tdd/test_thunder_budget_and_failsoft.py`, Aufrufe zählen
    statt Laufzeit messen). Zusätzlich: ein Kommentar/Test-Docstring an
    der Konstante hält die Herleitung (Abrufzahl × Latenz) fest, damit
    die nächste Ableitung nicht wieder geraten wird.

- **AC-5 (generalisierter Fill-Wächter greift bereits, keine neue
  Tabellenzeile nötig):** Given eine Vorhersagereihe, die von einer
  vorangegangenen Anreicherung bereits `lightning_potential_lpi_jkg`
  trägt (Feld wird über den bestehenden Signal-Key `"lpi"` gefüllt, s.
  Implementation Details Punkt 2) / When `enrich_thunder` **ein zweites
  Mal** auf dieselbe Reihe aufgerufen wird / Then löst das **keinen**
  erneuten DWD-ICON-EU-Abruf aus.
  - Test: `enrich_thunder` wird zweimal nacheinander auf dieselbe
    bereits angereicherte Reihe (Ort im EU_REST-Gebiet) aufgerufen; die
    Anzahl der Provider-Abrufe (Spy/Zähler) bleibt bei 1. Da der
    generalisierte Fill-Wächter (S2b) bereits gegen alle aus
    `_SIGNAL_ZU_FELD` bekannten Felder prüft, wird hier **keine**
    Änderung an `thunder_enrichment.py` erwartet — der Test beweist,
    dass das bereits gilt, ohne dass S2c dort etwas anfassen muss.

- **AC-6 (Namensfallen-AC, PFLICHT, Live-Schicht):** Given der im
  Produktivcode hinterlegte DWD-ICON-EU-Parametername für Blitzpotenzial
  (als Konstante, nicht im Test wiederholt) / When gegen das echte
  DWD-Open-Data-Verzeichnis (`opendata.dwd.de`) geprüft wird / Then
  existiert der Parameter-Ordner bzw. die erwartete Datei tatsächlich —
  kein lautloser 404.
  - Test: Live-Test (Marker `live`, läuft nicht im Commit-Gate, Vorbild
    `tests/tdd/test_dwd_thunder_parameter_names_live.py`), liest den
    Parameternamen aus der Konstante im Produktivcode (`dwd_eu.py`) und
    prüft per HTTP-Anfrage gegen den aktuellsten veröffentlichten
    ICON-EU-Lauf, dass die Datei existiert (200, nicht 404). **Warum
    Pflicht:** Exakt dieser Fehler (`LITOTA3`) ließ bei S2a jeden Abruf
    lautlos in 404 laufen, während 24 aufgezeichnete Tests grün blieben;
    `lpi_con_max` ist laut `decision_matrix.md` Z.36 bislang genauso
    unverifiziert.

- **AC-7:** Given der Standard-Lauf-Ermittler könnte einen noch nicht
  veröffentlichten ICON-EU-Lauf berechnen / When Blitzpotenzial abgerufen
  wird und der gewählte Lauf mit 404 antwortet / Then fällt der Abruf auf
  einen älteren Lauf zurück (mindestens einmal), während der Nullpunkt
  der Stunden-Offsets am Lauf der Grundvorhersage bleibt.
  - Test: Gegen einen echten lokalen HTTP-Server (Muster
    `tests/tdd/test_thunder_run_fallback.py`), der auf den jüngsten Lauf
    mit 404 antwortet, wird nachgewiesen, dass ein älterer Lauf
    erfolgreich abgefragt wird. Konkreter Sicherheitsabstand (Stunden)
    wird erst bei Implementierung gegen echte ICON-EU-Verfügbarkeit
    gemessen, nicht geraten.

- **AC-8 (Routing-Reihenfolge ist tragend):** Given eine Position in
  Frankreich UND eine Position in Deutschland/Alpen/Österreich / When die
  Gewitter-Zuständigkeit bestimmt wird, nachdem die neue Catch-all-Zeile
  `"EU_REST"` in `_REGIONS` ergänzt wurde / Then liefert
  `thunder_provider_for` weiterhin `"fr_direct"` bzw. `"de_direct"` —
  **nicht** `"eu_direct"`.
  - Test: Für einen französischen und einen deutschen/alpinen Testort
    wird nach Einbau der neuen Zeile nachgewiesen, dass beide weiterhin
    ihren jeweils bestehenden Provider erhalten. Gegenprobe: Wird die
    neue Zeile vor FR/DE_ALPEN einsortiert, muss dieser Test rot werden
    (first-match-wins verschluckt sonst beide bestehenden Gebiete).

- **AC-9 (gemeinsamer Weg bleibt frei von Provider-/Parameternamen):**
  Given der Anreicherungsweg `thunder_enrichment.py` / When nach dem
  Wortlaut der Datei gesucht wird / Then enthält sie **weder**
  `"eu_direct"` **noch** `"lpi_con_max"` als Zeichenkette.
  - Test: Erweiterung des bestehenden Verbotene-Begriffe-Tests
    `tests/tdd/test_thunder_enrichment_shared_path.py` um beide Strings
    (laut Kontext-Dokument dort bereits defensiv vorbereitet). Beweist:
    S2c hat den gemeinsamen Anschluss NICHT angefasst — nur Routing-
    Zeile und neue Provider-Klasse kamen hinzu.

- **AC-10 (Abgrenzung, keine Stufenbildung, keine Ausgaben-Änderung):**
  Given das Blitzpotenzial-Feld ist für einen ICON-EU-Datenpunkt gefüllt
  / When Ausgaben gerendert werden (SMS, Trip-Briefing,
  `thunder_level`-Berechnung) / Then bleiben diese Ausgaben
  **unverändert** gegenüber dem Stand ohne ICON-EU — keine eigene
  Einstufungs- oder Schwellenlogik entsteht in dieser Scheibe.
  - Test: Ein Regressionstest rendert dieselbe Vorhersage einmal mit und
    einmal ohne gesetztes `lightning_potential_lpi_jkg` (ICON-EU-
    Herkunft) und vergleicht `thunder_level` sowie den gerenderten
    SMS-/Briefing-Text — beide müssen identisch sein. Gegenprobe: Fließt
    das Feld in eine bestehende Einstufungsfunktion ein, muss dieser
    Test rot werden (#1474, separate Scheibe, baut die Schwellenlogik).

## Known Limitations

1. **`lpi_con_max` ist zum Zeitpunkt dieser Spec-Freigabe kein
   bestätigter DWD-Abrufname**, nur ein Konzept-Kurzname aus #1419
   (`decision_matrix.md` Z.36). AC-6 verlangt die Live-Prüfung als
   Implementierungsvoraussetzung, kein Show-Stopper für die
   Spec-Freigabe selbst.
2. **Fehlwert-Marker für ICON-EU ist unbekannt** und wird NICHT von
   ICON-D2 (`9999.0`) übernommen — eigene empirische Messung gegen echte
   GRIB2-Dateien ist Implementierungsvoraussetzung (AC-2). Zweimal in
   Folge (S2a, S2b) hat sich Übernahme aus Analogie als falsch erwiesen.
3. **Kein Hagel-Signal bei ICON-EU.** `hail_potential_grau_gsp` bleibt
   für Rest-Europa dauerhaft `None` — das ist beabsichtigt (#1419 nennt
   für "Übriges Europa" nur Blitzpotenzial), keine Lücke, die eine
   Folgescheibe schließen müsste.
4. **Feldwahl bewusst: Wiederverwendung statt eigenes Feld.**
   `lightning_potential_lpi_jkg` wird für ICON-EU-Orte mit demselben
   Feldnamen wie für ICON-D2-Orte (S2b) befüllt, obwohl die Maschenweite
   grob (~6,5 km) statt fein (2,2 km) ist. Fachlich dieselbe Energiegröße
   (J/kg), daher keine Herkunfts-Verwechslungsgefahr auf Nutzerebene
   erwartet — die Herkunfts-Transparenz (welcher Provider lieferte den
   Wert) bleibt intern über `thunder_routing.thunder_provider_for()`
   rekonstruierbar, falls später gebraucht. Diese Entscheidung ist mit
   dieser Spec getroffen, keine offene Frage mehr.
5. **Eigenes Zeitbudget muss ins Gesamtbudget des Alarm-Laufs passen.**
   AC-4 verlangt die Herleitung aus tatsächlicher Abrufzahl × Latenz,
   aber ob die Summe aus drei parallel möglichen Provider-Zeitbudgets
   (FR + DE_ALPEN + EU_REST, falls ein Lauf mehrere Gebiete berührt) das
   übergeordnete Budget des Gesamtlaufs sprengt, ist bei
   Implementierung explizit gegenzuprüfen — nicht nur isoliert je
   Provider.
6. **Downstream unverändert.** Stufenbildung (`thunder_level_from_
   signals()`) liest `lightning_potential_lpi_jkg` weiterhin nicht (auch
   nach S2b nicht) — S2c liefert nur Rohwerte, keine nutzersichtbare
   Änderung (konsistent mit S2a/S2b-Abgrenzung, AC-10).
7. **Keine Bündelungs-/Sammelabruf-Logik**, analog S2b-Begründung: jede
   ICON-EU-Datei deckt ohnehin ihr gesamtes Modellgebiet ab, ein
   Bounding-Box-Mechanismus ergäbe keinen fachlichen Gewinn. Die
   bekannte Mehrfach-Download-Ineffizienz bei mehreren Orten ist
   vorbestehendes Verhalten, nicht neu durch S2c eingeführt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — Referenz auf **ADR-0041** (Zuständigkeit
  einer Warn-Quelle nach Art des Endpunkts).
- **Rationale:** Wie bereits bei S2b begründet: Die eigentliche
  Architektur-Entscheidung — eine ZWEITE, größenabhängige
  Zuständigkeitstabelle (`thunder_routing.py`) getrennt von
  `region_routing.py`, mit Rechteck-Zuständigkeit und first-match-wins-
  Rangfolge (Muster C von ADR-0041) — wurde bereits mit S2a getroffen.
  S2c wendet dieses Muster ein drittes Mal an (Catch-all-Zeile) und
  fügt einen dritten, unabhängigen Provider in einer eigenen Datei
  hinzu — strukturell identisch zum bereits etablierten Schnitt
  (`meteofrance.py`/`dwd.py` als getrennte Dateien für getrennte
  Provider). Kein neuer Entscheidungstyp, keine neue ADR nötig.

## Changelog

- 2026-08-04: Initial spec created (Issue #1457 S2c, Konzept #1419,
  Vorbilder S2a `feat_1457_s2a_blitzdichte_meteofrance.md` und S2b
  `feat_1457_s2b_gewitter_dwd_alpen.md`, die S2c bereits als reinen
  Tabellenzeilen-Zusatz vorgeplant hatten — Recherche zeigt zusätzlich
  einen dritten, unabhängigen Provider mit eigener Basis-URL/eigenem
  Dateinamen-Schema als nötig).
