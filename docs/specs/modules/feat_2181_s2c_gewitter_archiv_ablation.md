---
entity_id: feat_2181_s2c_gewitter_archiv_ablation
type: feature
created: 2026-09-08
updated: 2026-09-08
status: draft
version: "1.0"
tags: [analysis, gewitter, cape, ablation, khw, messwerkzeug]
---

# Gewitter-Signalherkunft — Ablation, CAPE-Zeitverlauf und Stufe-vs-Niederschlag für den KHW-Archiv-Zeitraum (#2181 Scheibe S2c)

## Approval

- [ ] Approved

## Purpose

Prüft drei Thesen aus Issue #2181 gegen den Karnischen Höhenweg (24.08.–05.09.2026, 13 Etappentage) mittels Archiv-Rekonstruktion (nicht nur dem bereits gesicherten Vorhersage-Mitschnitt wie in Scheibe S2a): **T1** (welcher Signalast — Wettercode/CAPE/Blitzpotenzial — trug die erreichte Stufe?), **T3** (lag das CAPE-Maximum am 29.08. an der Wolayersee-Hütte 1-3h vor der ersten Gewitterstunde?), **T4** (wie oft stand eine hohe Stufe bei vorhergesagtem Niederschlag nahe null?). Vorgeschaltet: ein Kalibrier-Abgleich, der prüft, ob die Archiv-Rekonstruktion den bereits gesicherten Mitschnitt überhaupt trifft — ohne bestandenen Abgleich ist die T1-Ablation nicht belastbar.

## Source

- **File:** `src/analysis/thunder_ablation.py` (neue Datei, kein Vorgänger)
- **Identifier:** freie Funktionen, kein Klassen-Interface (identisch zum Muster aus S2a)

**Begründung eigenes Modul statt Erweiterung von `thunder_replay.py`:** unterschiedliche Eingangsgranularität — `thunder_replay.py` verarbeitet bereits tagesaggregierte Mitschnitt-Segmente, `thunder_ablation.py` verarbeitet stündliche Archiv-Zeitreihen an einem Punkt. Gemeinsame Bausteine werden importiert, nicht dupliziert: `waehle_vorlauf_aermste()`, `tageswerte_je_teilmenge()`, `TEILMENGE_PRIMAER` aus `thunder_replay.py`; `thunder_ordinal` aus `app.thunder_scale`.

> **Schicht-Hinweis:** Python-Core (`src/`), reines Analyse-Werkzeug ohne Netz-, DB- oder API-Anbindung. Kein Frontend, keine Go-API betroffen.

## Estimated Scope

- **LoC:** ~170-200 (Modul) + ~180-220 (Tests, 12 ACs) — Fixtures zählen nicht als LoC. **Das 250er-Gesamtlimit wird voraussichtlich überschritten** (S2a lag bei ~150+100=250 mit nur 8 ACs) — `loc_limit_override` auf 400 wird empfohlen, mit Begründung "Kalibrier-Abgleich + drei Thesen in einer Scheibe, mehr Funktionen als S2a".
- **Files:** 2 Code-Dateien + 1 Fixture-Verzeichnis
- **Effort:** medium

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/analysis/thunder_ablation.py` | CREATE | Archiv-Stundenzeilen-Verarbeitung: Kalibrier-Abgleich, Ablation (T1), CAPE-Verlauf+Ereignisfenster (T3), Stufe-Niederschlag-Paarung (T4) |
| `tests/tdd/test_thunder_ablation.py` | CREATE | Verhaltensprüfung gegen Fixtures aus echten Archiv-Antworten und Mitschnitt-Zeilen |
| `tests/fixtures/khw_2026_08_archiv/*.json` | CREATE | Aufgezeichnete Archiv-Stunden (Ausgangsmaterial: die echte Live-Probe vom 29.08. an der Wolayersee-Hütte — als reale Rohdaten übernehmen, ergänzt um weitere Testfälle, die die einzelnen ACs gezielt abdecken, z.B. eine Stunde mit hohem LPI und niedrigem CAPE/Wettercode für AC-5) |

**Nicht Teil dieser Scheibe:** der Netzabruf gegen `historical-forecast-api.open-meteo.com` selbst (bleibt außerhalb des Repos unter `/home/hem/gz-messdaten/`, wie bei S1/S2a — genau ein Lauf, kein Wartungswert), jede Änderung an `src/output/metric_format.py`, `src/providers/thunder_enrichment.py` oder anderem Produktivpfad-Code.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.metric_format.thunder_signal_carriers()` | Funktion (genutzt, UNVERÄNDERT) | Nennt jedes Signal, das die Höchststufe trägt — der eigentliche Ablations-Baustein (ADR-0025: keine zweite Fusionsregel) |
| `output.metric_format.thunder_level_from_signals()` | Funktion (genutzt, UNVERÄNDERT) | Fusion für die Stufenberechnung je Stunde |
| `app.model_registry.cape_ladder_thresholds_jkg(model_id, region)` | Nachschlag (vom Aufrufer aufgelöst, als Tupel übergeben) | (low, med, high)-CAPE-Leiter — kein hartkodierter Wert im Modul |
| `app.model_registry.lpi_thresholds_jkg(region)` | Nachschlag (vom Aufrufer aufgelöst, als Tupel übergeben) | (low, med, high)-Blitzpotenzial-Leiter |
| `providers.openmeteo.THUNDER_CODES` | Konstante (importiert, NICHT kopiert) | `{95, 96, 99}` — Wettercode-Ast und T3-Ereignisstunden-Erkennung nutzen dieselbe Konstante wie der Produktivpfad |
| `analysis.thunder_replay.waehle_vorlauf_aermste()` | Funktion (importiert, wiederverwendet) | Kurzvorlauf-Auswahl für den Kalibrier-Abgleich — keine zweite Auswahlregel |
| `analysis.thunder_replay.tageswerte_je_teilmenge()` | Funktion (importiert, wiederverwendet) | Liefert die Mitschnitt-Tageswerte (inkl. `cape_max_jkg`, `thunder_level_max`) für Kalibrierung und T4 |
| `app.models.ThunderLevel` | Enum (genutzt) | Gemeinsamer Stufentyp |
| `app.thunder_scale.thunder_ordinal` | Funktion (genutzt) | Kanonische Stufenordnung für Tages-/Stundenmaximum |

## Implementation Details

### Archiv-Zeilenformat

Aus `historical-forecast-api.open-meteo.com`, Parameter `weather_code,cape,convective_inhibition,lightning_potential,precipitation,showers`, Modell `icon_d2`. Die API liefert parallele Arrays (`hourly.time[]`, `hourly.weather_code[]`, ...). Eine reine Zip-Funktion macht daraus Stundenzeilen — das ist der einzige Parsing-Schritt, alles andere arbeitet auf dieser Zeilenform:

```
stundenzeilen_aus_archiv_antwort(antwort: dict) -> list[dict]:
    # {"time": "2026-08-29T15:00", "weather_code": 96, "cape": 0.0,
    #  "convective_inhibition": 0.0, "lightning_potential": 2.6,
    #  "precipitation": 12.0, "showers": 0.2}
    # Zip ueber antwort["hourly"][...] Arrays, Reihenfolge = Index von "time"
```

### 1. Wettercode-Ast (gemeinsam für T1 und T3)

```
wettercode_stufe(weather_code: Optional[int]) -> Optional[ThunderLevel]:
    if weather_code is None: return None      # keine Aussage
    return ThunderLevel.HIGH if weather_code in THUNDER_CODES else ThunderLevel.NONE
```

Spiegelt `OpenMeteoProvider._parse_thunder_level()` (openmeteo.py:694-716) exakt, als freie Funktion mit der importierten Konstante — keine zweite Kopie der Codes 95/96/99.

### 2. Kalibrier-Abgleich (MUSS vor der T1-Ablation stehen und ACs vor T1 tragen)

```
kalibrier_abgleich_kurzvorlauf_cape(
    mitschnitt_tageswerte_primaer: dict[str, dict],  # aus thunder_replay.tageswerte_je_teilmenge()["primaer"]
    archiv_cape_tagesmaximum: dict[str, Optional[float]],  # Tag -> max(stundenzeile["cape"])
    toleranz_jkg: float,  # vom Aufrufer uebergeben, empfohlen: cape_low_schwelle / 2
) -> dict[str, dict]:
    # je Tag: {"kategorie": "im_toleranzband" | "abweichend" | "kein_vergleichswert",
    #          "differenz_jkg": float | None}
    # "kein_vergleichswert": mitschnitt_tageswerte_primaer[tag]["cape_max_jkg"] is None
    #   ODER Tag fehlt in einer der beiden Quellen
```

Toleranz-Begründung: die Toleranz ist die HALBE untere CAPE-Sprosse des Gebiets (`cape_ladder_thresholds_jkg("icon_d2","DE_ALPEN")[0] / 2` = 150 J/kg) — eine kleinere Abweichung kann die Stufenklassifikation strukturell nicht kippen, eine größere schon. Kein willkürlicher Prozentwert.

### 3. T1 — Ablation je Stunde und Tagesverdichtung

```
ablation_je_stunde(
    stundenzeile: dict,
    cape_ladder: tuple[float, float, float],
    lpi_thresholds: tuple[float, float, float],
) -> dict:
    # ruft thunder_level_from_signals()/thunder_signal_carriers() MIT REALEN REKONSTRUIERTEN
    # ROHWERTEN auf (cin_jkg und lightning_potential_jkg sind NICHT None -- anders als urspruenglich
    # befuerchtet liefert das Open-Meteo-Archiv beide fuer icon_d2, live verifiziert):
    #   wettercode_level = wettercode_stufe(stundenzeile["weather_code"])
    #   lightning_density = None  # FR-only, auf dem KHW strukturell abwesend
    #   cape_jkg = stundenzeile["cape"]
    #   lightning_potential_jkg = stundenzeile["lightning_potential"]
    #   cin_jkg = stundenzeile["convective_inhibition"]
    # {"stufe": ThunderLevel | None, "traeger": list[str]}

ablation_tagesmaximum(
    stundenzeilen_tag: list[dict], cape_ladder, lpi_thresholds,
) -> dict:
    # ruft ablation_je_stunde() fuer jede Stunde, ermittelt die Hoechststufe des Tages
    # (thunder_ordinal), traeger = UNION aller "traeger"-Listen der Stunden, die genau diese
    # Hoechststufe erreichen (nicht nur die erste gefundene Stunde -- AC-6)
    # {"stufe": ThunderLevel | None, "traeger": list[str]}

vergleiche_ablation_mit_mitschnitt(
    ablation_tag: dict, mitschnitt_stufe: Optional[ThunderLevel],
) -> dict:
    # {"mitschnitt_stufe": ..., "ablation_stufe": ..., "traeger": [...],
    #  "ablation_erreicht_mitschnitt_stufe": bool}
    # False, wenn thunder_ordinal(ablation_stufe oder NONE) < thunder_ordinal(mitschnitt_stufe) --
    # eigene, ausgewiesene Kategorie, NICHT stillschweigend einem der drei Aeste zugeschlagen
    # (Radar-Override ist im Mitschnitt eingerechnet, aus der Rekonstruktion strukturell
    # unsichtbar -- Known Limitations)
```

### 4. T3 — CAPE-Zeitverlauf und Ereignisfenster

```
cape_verlauf_und_ereignisfenster(stundenzeilen_tag: list[dict]) -> dict:
    # {"stundenwerte": [(zeit, cape), ...] zeitlich sortiert,
    #  "cape_maximum": (zeit, wert) | None,
    #  "erste_ereignisstunde": zeit | None,  # erste Stunde mit weather_code in THUNDER_CODES
    #  "vorlauf_stunden": float | None}  # erste_ereignisstunde - cape_maximum_zeit in Stunden
    # None-Werte wenn keine Ereignisstunde im Tag -- kein erfundener Wert, keine Exception
```

WICHTIG: kein Sollwert "muss 1-3h sein" im Code oder in den ACs — nur die Rechnung wird geprüft (S2a-Lehre: ACs beschreiben die Messvorschrift, nie das Ergebnis).

### 5. T4 — Stufe-Niederschlag-Paarung

```
niederschlag_tagessumme(stundenzeilen_tag: list[dict]) -> dict:
    # {"niederschlag_mm": sum(precipitation), "schauer_mm": sum(showers)}

stufe_gegen_niederschlag(
    mitschnitt_tageswerte: dict[str, dict],  # thunder_level_max je Tag, aus thunder_replay
    archiv_niederschlag_je_tag: dict[str, dict],  # aus niederschlag_tagessumme() je Tag
) -> dict[str, dict]:
    # je Tag NUR das rohe Tripel: {"stufe": ThunderLevel | None,
    #   "niederschlag_mm": float | None, "schauer_mm": float | None}
    # KEIN Schwellenwert/Interpretationsfeld ("nahe null" etc.) -- das ist Berichtssache
    # ausserhalb des Repos (S2a-Praezedenzfall)
```

## Expected Behavior

- **Input:** Archiv-Stundenzeilen (aus der Zip-Funktion, in Fixtures als versionierte JSON-Dateien mit echten aufgezeichneten Werten), Mitschnitt-Tageswerte (aus `thunder_replay`), Modell-/Gebiets-Schwellen (vom Aufrufer über `model_registry` aufgelöst, als Tupel übergeben).
- **Output:** Kalibrier-Kategorien je Tag; Ablations-Stufe+Träger je Tag inkl. Vergleich mit dem Mitschnitt; CAPE-Verlauf+Ereignisfenster für T3; rohe Stufe-Niederschlag-Paare für T4. Kein Freitext-Bericht — der Bericht entsteht außerhalb des Repos.
- **Side effects:** keine — reine Funktionen, kein Netz-/Datei-Schreib-/DB-Zugriff.

## Acceptance Criteria

- **AC-1:** Given ein Etappentag mit archiv-CAPE-Tagesmaximum und dem kurzvorlauf-nächsten Mitschnitt-`cape_max_jkg` desselben Tages, When der Kalibrier-Abgleich läuft, Then wird die absolute Differenz gegen die Toleranz (halbe LOW-Sprosse, 150 J/kg bei icon_d2×DE_ALPEN) geprüft und der Tag als "im_toleranzband" oder "abweichend" markiert.
  - Test: Fixture-Tag mit archiv-CAPE 500 und mitschnitt-cape 550 (Differenz 50 < Toleranz 150) → "im_toleranzband"; zweiter Fixture-Tag mit Differenz 400 > Toleranz → "abweichend".

- **AC-2:** Given ein Mitschnitt-Tag ohne jede Zeile mit gültigem (nicht-negativem) Vorlauf, When der Kalibrier-Abgleich für diesen Tag läuft, Then wird der Tag als "kein_vergleichswert" markiert, nicht als "im_toleranzband" oder "abweichend".
  - Test: Fixture-Tag mit ausschließlich negativem Vorlauf in den Mitschnitt-Zeilen → Kategorie "kein_vergleichswert".

- **AC-3:** Given eine Archiv-Stunde mit `weather_code=96`, When `ablation_je_stunde` sie auswertet, Then liefert das Ergebnis Stufe HIGH mit "wettercode" als Träger, unabhängig von schwächeren CAPE-/LPI-Werten derselben Stunde.
  - Test: Fixture-Stunde `code=96, cape=0, lpi=0` → `{"stufe": HIGH, "traeger": ["wettercode"]}`.

- **AC-4:** Given eine Archiv-Stunde mit CAPE über der HIGH-Sprosse und CIN > 100 J/kg, When `ablation_je_stunde` sie auswertet, Then wird die CAPE-Stufe gemäß der bestehenden CIN-Dämpfungsregel (`_gedaempft_durch_cin`, ADR-0025) auf höchstens LOW heruntergesetzt, nicht ungedämpft auf HIGH gezählt.
  - Test: Fixture-Stunde `cape=1500` (über HIGH-Sprosse 1200), `cin=150` → CAPE-Ast liefert höchstens LOW.

- **AC-5:** Given eine Archiv-Stunde mit `lightning_potential` über der HIGH-Sprosse und Wettercode/CAPE unterhalb ihrer Sprossen, When `ablation_je_stunde` sie auswertet, Then erscheint "blitzpotenzial" als alleiniger Träger der Höchststufe.
  - Test: Fixture-Stunde `cape` niedrig, `code=2` (kein Gewittercode), `lpi=60` (über HIGH-Sprosse 50) → `traeger == ["blitzpotenzial"]`, Stufe HIGH.

- **AC-6:** Given zwei Stunden desselben Tages, eine mit Träger "wettercode" auf HIGH, eine mit Träger "cape" auf derselben Höchststufe HIGH, When `ablation_tagesmaximum` den Tag verdichtet, Then enthält die Trägerliste des Tages BEIDE Namen.
  - Test: Fixture-Tag mit zwei Stunden, unterschiedliche alleinige Träger derselben Höchststufe → beide Namen in der Tages-Trägerliste.

- **AC-7:** Given ein Etappentag, dessen Mitschnitt-Stufe HIGH zeigt, aber KEINE Archiv-Stunde des Tages HIGH erreicht, When `vergleiche_ablation_mit_mitschnitt` läuft, Then wird `ablation_erreicht_mitschnitt_stufe = False` markiert — nicht stillschweigend einem der drei Äste zugeschlagen.
  - Test: Fixture-Tag Mitschnitt-Stufe HIGH, alle Archiv-Stunden liefern höchstens LOW → `ablation_erreicht_mitschnitt_stufe` ist False, Trägerliste für HIGH bleibt leer.

- **AC-8:** Given eine Archiv-Stunde mit `weather_code=None`, When `ablation_je_stunde` sie auswertet, Then trägt der Wettercode-Ast NICHT zur Stufe bei (fehlt im Signal-Dict) — anders als ein Code, der explizit "kein Gewitter" bedeutet.
  - Test: Fixture-Stunde `weather_code=None`, alle anderen Signale ebenfalls unterhalb/fehlend → Gesamtstufe `None` ("keine Aussage"); Vergleichs-Fixture mit `weather_code=2` und sonst identischen Werten → Gesamtstufe `ThunderLevel.NONE` ("geprüfte Entwarnung").

- **AC-9:** Given ein Fixture-Tag mit Archiv-Stundenwerten, dessen CAPE-Maximum zeitlich vor der ersten Ereignisstunde (Wettercode in `THUNDER_CODES`) liegt, When `cape_verlauf_und_ereignisfenster` den Tag auswertet, Then liefert es die korrekte Stundendifferenz zwischen CAPE-Maximum-Zeitpunkt und erster Ereignisstunde.
  - Test: Fixture (Ausgangsmaterial: die reale 29.08.-Live-Probe, NICHT als vorgeschriebenes Ergebnis, nur als Rohdaten) mit CAPE-Maximum um 13:00 und erster Ereignisstunde 15:00 → `vorlauf_stunden == 2.0`; Test prüft die Rechnung, schreibt kein "muss 1-3h sein"-Kriterium fest.

- **AC-10:** Given ein Fixture-Tag ohne jede Ereignisstunde, When `cape_verlauf_und_ereignisfenster` ausgewertet wird, Then liefert es `erste_ereignisstunde=None` und `vorlauf_stunden=None` — kein Rechenfehler, kein erfundener Wert.
  - Test: Fixture-Tag ausschließlich mit Nicht-Gewitter-Codes → beide Felder `None`.

- **AC-11:** Given eine Mitschnitt-Tages-Stufe HIGH und archiv-Niederschlagssummen, When `stufe_gegen_niederschlag` den Tag paart, Then liefert es NUR das rohe Tripel (Stufe, Niederschlagssumme, Schauersumme) — kein Schwellenwert-Interpretationsfeld wie "nahe null".
  - Test: Rückgabe-Dict eines Tages enthält ausschließlich die drei benannten Rohwerte, keine weiteren bool-Interpretationsfelder.

- **AC-12:** Given ein Etappentag ohne gültige Mitschnitt-Stufe (`None`, "keine Aussage"), When `stufe_gegen_niederschlag` diesen Tag paart, Then bleibt die Stufe im Ergebnis `None` — kollabiert nicht zu `ThunderLevel.NONE`.
  - Test: Fixture-Tag mit `thunder_level_max=None` → Ausgabe-Stufe bleibt `None`.

## Known Limitations

- **Der Radar-Override ist aus der Rekonstruktion strukturell unsichtbar.** `RadarNowcastService` ist im Mitschnitt bereits eingerechnet, aber kein Archiv-Signal — Tage, an denen er gegriffen hat, landen in der Kategorie "ablation_erreicht_mitschnitt_stufe_nicht" (AC-7), was NICHT als Fehler der Ablation zu lesen ist.
- **Vorlauf-Versatz:** der Mitschnitt hält Vorhersagen mit Median 21h Vorlauf, das Archiv liefert je Stunde den reifsten verfügbaren Wert — ein unbesehener Abgleich über den GESAMTEN Mitschnitt würde Vorhersagedrift messen statt Rechenweise-Fehler. Deshalb vergleicht der Kalibrier-Abgleich NUR gegen die kurzvorlauf-nächste Mitschnitt-Teilmenge (`waehle_vorlauf_aermste`).
- **CIN und Blitzpotenzial produktiv vom DWD-Direktabruf, hier von Open-Meteos Archiv-Spiegel des gleichen Modells (`icon_d2`)** — andere Bezugsquelle, dieselbe Modellgröße, kein Verfahrenswechsel; live verifiziert (2026-09-08), dass beide Felder für `icon_d2` mit plausiblen, variierenden Werten geliefert werden (nicht durchgehend Füllwert).
- **T3-Stichprobenwert ist kein vorweggenommener Befund.** Der Wert 2h Vorlauf aus der Live-Probe (29.08., Wolayersee-Hütte) ist Testfall-Rohmaterial für AC-9, kein in der Spec festgeschriebenes Ergebnis der eigentlichen Messung.
- **Blitzdichte bleibt außen vor** — strukturell FR-only (Météo-France-Größe), auf dem KHW (Gebiet DE_ALPEN) nicht vorhanden; die Ablation kennt auf dem KHW nur drei Äste (Wettercode/CAPE/Blitzpotenzial).
- **Toleranzschwelle des Kalibrier-Abgleichs ist eine Auswertungsentscheidung dieser Spec** (halbe LOW-Sprosse), keine im Datenmaterial festgeschriebene Tatsache.
- **`stundenzeilen_aus_archiv_antwort()` (Archiv-Zeilenformat) ist bewusst NICHT im Modul implementiert.** Kein AC verlangt sie, und ihr einziger denkbarer Aufrufer — der externe, einmalige Archiv-Abruf gegen `historical-forecast-api.open-meteo.com` — liegt laut dieser Spec explizit außerhalb des Repos (genau wie schon bei S1/S2a: "genau ein Lauf, kein Wartungswert"). Wer den Bericht erstellt, schreibt diesen Zip-Schritt dort ad-hoc; eine zusätzliche, nur für diese externe Nutzung gedachte Funktion im Repo würde entweder ungetestet bleiben oder Test-LoC für einen Pfad binden, der innerhalb des Repos nichts absichert (Adversary-Finding F003, Verdict-Runde S2c).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0025
- **Rationale:** ADR-0025 legt fest, dass es genau EINE Gewitter-Fusionsquelle gibt (`thunder_level_from_signals()`/`thunder_signal_carriers()` in `metric_format.py`) und keine zweite Berechnung entstehen darf. Diese Spec baut deshalb KEINE eigene Fusionslogik nach: die Ablation ruft die bestehenden Funktionen mit rekonstruierten Rohwerten auf, statt eine zweite Fusionsregel zu schreiben. Der Wettercode-Ast (`wettercode_stufe`) ist keine Ausnahme — er spiegelt `_parse_thunder_level()` mit der importierten `THUNDER_CODES`-Konstante, keine eigene Kalibrierung.

## Changelog

- 2026-09-08: Initial spec created (Issue #2181, Scheibe S2c) — Nachfolger von Scheibe S2a (`feat_2181_s2a_gewitter_mitschnitt_auswertung.md`), deren Known Limitations diese Scheibe explizit als Folgearbeit benennen ("S2b" in der dortigen Terminologie).
