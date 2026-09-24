---
entity_id: fix_2225_geosphere_registry_alias
type: fix
created: 2026-09-24
updated: 2026-09-24
status: draft
version: "1.0"
tags: [gewitter, cape, model-registry, geosphere, issue-2225]
---

# GeoSphere-Modell bekommt eigenen Registry-Alias statt Rückfall auf meteofrance_arome (Issue #2225)

## Approval

- [ ] Approved

## Purpose

`_MODEL_ALIASES` in `src/app/model_registry.py:43` bildet den Roh-Modellnamen `"AROME"` (klein
`"arome"`) fälschlich auf den kanonischen Schlüssel `"meteofrance_arome"` ab. Gemeldet wird dieser
Rohwert aber ausschließlich von **GeoSphere** (`src/providers/geosphere.py:734`,
`meta.model="AROME"`), nicht von Météo-France — Météo-France meldet sich als `"AROME-HIGHRES"`
(`src/providers/meteofrance.py:1005`) und wird bereits korrekt über einen eigenen Alias-Eintrag
auf `"meteofrance_arome"` abgebildet. GeoSphere braucht einen eigenen kanonischen Schlüssel, damit
eine künftige CAPE-Eichung oder -Fusion nicht versehentlich die Météo-France-Eichtabelle für
GeoSphere-Daten liest.

**PO-relevante Vorentscheidung aus der Analyse-Phase (Freigabe mit dieser Spec):** neuer
kanonischer Schlüssel heißt `"geosphere_arome"`, bekommt **bewusst keinen** Eintrag in
`CAPE_THRESHOLDS_JKG` (keine Eichgrundlage — GeoSphere archiviert AROME nicht rückwirkend, siehe
`docs/specs/modules/feat_1758_geosphere_cape_cin.md:80-85`). `cape_threshold_jkg()` liefert für
`geosphere_arome` weiterhin `None` über den bestehenden `dict.get()`-Fallback — das ist das
gewollte Verhalten, kein Folgefehler.

## Source

- **File:** `src/app/model_registry.py`
- **Identifier:** `_MODEL_ALIASES` (Dict, Zeile 38-47), konkret der Eintrag `"arome": "meteofrance_arome"` (Zeile 43)

**Schicht:** ausschließlich Python-Core (`src/app/model_registry.py`, `tests/tdd/`) — reine
Normalisierungs-Tabelle einer internen Herkunfts-Auflösung, kein Go, kein Frontend, keine
wählbare Metrik betroffen (CAPE ist `selectable=False`).

## Estimated Scope

- **LoC:** ~15 Quellcode (`model_registry.py`: eine Alias-Zeile + Kommentarblock) + ~10 Test
  (zwei bestehende Erwartungswerte + ein neuer Bug-Reproduktionstest) ≈ **~25 gesamt** — weit
  unter dem 250-LoC-Workflow-Limit. Doku-Update in `feat_1758_geosphere_cape_cin.md` zählt nicht
  mit (Doku).
- **Files:** 2 geändert (`model_registry.py`, `test_model_registry_normalization.py`) + 1
  Doku-Datei (Spec-Update, kein Code) + 1 neuer Test (Ablage entscheidet `/40-tdd-red`).
- **Effort:** low — Austausch eines Dict-Werts, keine neue Logik, keine neue Aufrufstelle,
  keine Signaturänderung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `normalize_model_id()` (`model_registry.py:50-61`) | Upstream, unverändert in der Logik | liest `_MODEL_ALIASES`; die einzige geänderte Stelle dieser Fix-Scheibe |
| `effective_cape_model_id()` (`model_registry.py:64-72`) | Upstream, unverändert | ruft `normalize_model_id()` auf `meta.model`/`meta.fallback_model` auf — einzige Stelle, die Provider-Metadaten in die Registry einspeist |
| `cape_threshold_jkg()` (`model_registry.py:135-142`) | Downstream, unverändert im Code | `CAPE_THRESHOLDS_JKG.get((model_id, region))` liefert für `("geosphere_arome", *)` bereits heute `None` (kein Eintrag) — bestehendes Verhalten, hier nur genutzt, nicht verändert |
| `cape_ladder_thresholds_jkg()` (`model_registry.py:253-268`) | Downstream, unverändert im Code | verankert `low` an `cape_threshold_jkg()`; liefert für `geosphere_arome` ebenfalls `None` für die GESAMTE Leiter (gleiche Invariante wie jede andere unbekannte Kombination) |
| `src/services/weather_metrics.py:1002` | Aufrufer, unverändert | `cape_model_id=effective_cape_model_id(timeseries.meta)` — reicht das neue Ergebnis unbedingt durch, ohne den Provider gesondert zu prüfen |
| `src/providers/thunder_enrichment.py:305-307` | Aufrufer, unverändert | `cape_ladder_thresholds_jkg(effective_cape_model_id(reihe.meta), region)` mit `region = thunder_region_for(lat, lon)` — für den AT-Cross-Provider-Fallback (#1141) liefert `thunder_region_for()` `"DE_ALPEN"` (GeoSphere-Gitter liegt in `_REGIONS`-Zeile `DE_ALPEN`, `thunder_routing.py:75`, Bereich lat 43.17-58.09/lon -3.95-20.35 deckt Österreich ab) |
| `src/services/weather_change_detection.py:781-786,843` | Aufrufer, unverändert, **verifiziert unberührt** | Der `cape_model_id`-Vergleich (Zeile 843) wird erst NACH dem None-Guard (Zeile 785-786: `if old_value is None or new_value is None: continue`) erreicht. GeoSphere setzt `cape_jkg` auf der primären Vorhersage nicht (`geosphere.py:790-827,875-891`), `cape_max_jkg` bleibt für GeoSphere-Daten also `None` — der Vergleichspfad wird für GeoSphere-Daten strukturell nie erreicht, weder heute noch nach dem Fix |
| `docs/specs/modules/feat_1758_geosphere_cape_cin.md:83-85` | zu aktualisieren (Doku) | benennt den hier behobenen Fehler wörtlich als "bestehenden, latenten Nebenbefund, gebucht in #1199" — Satz muss auf "behoben in #2225" umgestellt werden |
| `tests/tdd/test_model_registry_normalization.py` | zu korrigieren | legt das heutige, falsche Verhalten an drei Stellen fest (s. Implementation Details) |

## Implementation Details

```python
# src/app/model_registry.py, Zeile 38-47 (_MODEL_ALIASES)
_MODEL_ALIASES: Dict[str, str] = {
    "icon_d2": "icon_d2",
    "icon-d2": "icon_d2",
    "meteofrance_arome": "meteofrance_arome",
    "arome-highres": "meteofrance_arome",
    "arome": "geosphere_arome",          # <- geaendert (war: "meteofrance_arome")
    "icon_eu": "icon_eu",
    "metno_nordic": "metno_nordic",
    "ecmwf_ifs04": "ecmwf_ifs04",
}
```

Der Kommentarblock direkt über der Alias-Tabelle (Zeile 34-37: *"Roh-Bezeichner je Modellwelt ->
kanonischer Schluessel ... Jede Schreibweise derselben Modellwelt MUSS auf denselben Wert
abbilden"*) bleibt inhaltlich gültig, bekommt aber einen ergänzenden Satz: `"arome"` (GeoSphere)
und `"arome-highres"` (Météo-France) sind **verschiedene Modellwelten**, die zufällig ähnlich
benannt sind — deshalb zwei Ziel-Schlüssel, kein gemeinsamer.

**Kein neuer Eintrag in `CAPE_THRESHOLDS_JKG` (Zeile 120-132).** `cape_threshold_jkg()`
(Zeile 135-142) liefert für `("geosphere_arome", <beliebige Region>)` bereits über den
bestehenden `dict.get()`-Fallback `None` — kein Sonderfall, keine Code-Änderung nötig.

**Testanpassung** (`tests/tdd/test_model_registry_normalization.py`, drei Stellen):
1. Zeile 34: `("AROME", "meteofrance_arome"),` → `("AROME", "geosphere_arome"),`
2. Zeile 80: `assert arome == "meteofrance_arome"` → `assert arome == "geosphere_arome"`
   (im selben Test bleibt Zeile 81 `assert icon == "icon_d2"` unverändert; der Docstring des
   Tests, Zeile 68-71, "AROME und icon_d2 MUESSEN sich unterscheiden", bleibt inhaltlich richtig)
3. Zeile 31 (Kommentar über der Parametrisierung: *"# AROME-Familie: Open-Meteo,
   Meteo-France-Direktwort, GeoSphere-Wort"*) wird präzisiert: GeoSphere-Wort ist keine
   AROME-**Familie** mehr im Sinne dieser Tabelle, sondern ein eigener Zweig — Kommentar entsprechend
   umformulieren (z. B. zwei Kommentarzeilen statt einer, getrennt nach Météo-France- und
   GeoSphere-Zweig).
4. Docstring des Moduls, Zeile 7-11 (Aufzählung, was `normalize_model_id()` bündelt) — Beispiel
   `` `meteofrance_arome`/`AROME-HIGHRES`/`AROME` `` nennt `AROME` fälschlich als
   Météo-France-Schreibweise; auf die korrekte Zuordnung (Météo-France: `AROME-HIGHRES`;
   GeoSphere: `AROME`, eigener Schlüssel) umstellen.

**Neuer Bug-Reproduktionstest** (Ablage entscheidet `/40-tdd-red`, z. B. in
`test_model_registry_normalization.py` oder einer neuen Datei): muss den Bug auf Systemebene über
`effective_cape_model_id()` **verkettet mit** `cape_threshold_jkg()`/`cape_ladder_thresholds_jkg()`
zeigen — nicht nur isoliert das Alias-Dict prüfen (s. AC-1 unten, das ist die eigentliche
Gegenprobe: ein Test, der nur `normalize_model_id("AROME") == "geosphere_arome"` prüft, wäre schon
vor dem Fix teilweise grün täuschend, weil `cape_threshold_jkg()` für einen NICHT existierenden
Schlüssel ohnehin `None` liefert — das eigentliche Bug-Symptom ist die FALSCHE Herkunftsangabe
selbst, nicht direkt ein falscher Schwellenwert).

## Expected Behavior

- **Input:** `ForecastMeta(provider=Provider.GEOSPHERE, model="AROME", grid_res_km=2.5, ...)` —
  exakt die Form, die `geosphere.py:732-738` bei jeder GeoSphere-Primärvorhersage erzeugt.
- **Output:** `effective_cape_model_id(meta)` liefert `"geosphere_arome"` (vorher fälschlich
  `"meteofrance_arome"`). `cape_threshold_jkg("geosphere_arome", "DE_ALPEN")` liefert `None`
  (vorher fälschlich `380.0` — der für Météo-France geeichte DE_ALPEN-Wert).
  `cape_ladder_thresholds_jkg("geosphere_arome", "DE_ALPEN")` liefert `None` für die gesamte
  Leiter (vorher fälschlich `(380.0, 1000.0, 2500.0)`, s. `fix_2178_cape_leiter_absolutwerte.md`
  für die Herkunft der festen MED/HIGH-Werte).
- **Side effects:** keine beobachtbaren, **verifiziert**: GeoSphere setzt `cape_jkg` auf der
  primären Vorhersage nicht (`geosphere.py:790-827,875-891`) — `cape_max_jkg` ist für
  GeoSphere-Daten heute wie nach dem Fix `None`. Der einzige heute erreichbare Pfad, auf dem sich
  das fälschlich zugeordnete Label überhaupt auswirken könnte (`cape_ladder_thresholds_jkg()` in
  `thunder_enrichment.py:305-307`, AT-Cross-Provider-Fallback #1141), liefert wegen des
  `cape_jkg is None`-Guards in `_signal_levels()` (`metric_format.py`, `cape_threshold_jkg`
  KEYWORD-ONLY ohne Default) ohnehin kein CAPE-Signal zur Fusion. Der
  `cape_model_id`-Vergleich in `weather_change_detection.py:843` wird durch den vorgelagerten
  None-Guard (Zeile 785-786) für GeoSphere-Daten strukturell nie erreicht. Kein Snapshot- oder
  Migrationsbedarf (kein Treffer für die Kollision in `data/users/*/*.json`, Kontext-Recherche
  bereits durchgeführt).

## Acceptance Criteria

- **AC-1:** Given eine GeoSphere-Primärvorhersage mit `ForecastMeta(provider=Provider.GEOSPHERE,
  model="AROME", grid_res_km=2.5)` / When `effective_cape_model_id(meta)` aufgerufen und das
  Ergebnis in `cape_threshold_jkg(ergebnis, "DE_ALPEN")` sowie
  `cape_ladder_thresholds_jkg(ergebnis, "DE_ALPEN")` weitergereicht wird / Then liefert
  `effective_cape_model_id(meta)` `"geosphere_arome"`, UND `cape_threshold_jkg("geosphere_arome",
  "DE_ALPEN")` liefert `None`, UND `cape_ladder_thresholds_jkg("geosphere_arome", "DE_ALPEN")`
  liefert `None` für die gesamte Leiter.
  - Test: neuer Bug-Reproduktionstest (Ablage `/40-tdd-red`), ruft die drei Funktionen
    verkettet auf einer echten `ForecastMeta`-Instanz auf — kein isolierter Dict-Zugriff.
  - Gegenprobe: Bliebe der Alias-Eintrag unverändert bei `"meteofrance_arome"`, läge
    `cape_threshold_jkg("meteofrance_arome", "DE_ALPEN")` bei `380.0` (bestehender, für
    Météo-France geeichter Wert aus `CAPE_THRESHOLDS_JKG`) und `cape_ladder_thresholds_jkg(...)`
    bei `(380.0, 1000.0, 2500.0)` statt `None` — der Test muss diesen Rückfall fangen, indem er
    NICHT nur auf `"geosphere_arome"` als String prüft, sondern auf das tatsächliche
    `None`-Ergebnis der nachgelagerten Eichfunktionen.

- **AC-2:** Given eine Météo-France-Primärvorhersage mit `ForecastMeta(model="AROME-HIGHRES")` /
  When `effective_cape_model_id(meta)` aufgerufen wird / Then liefert sie unverändert
  `"meteofrance_arome"` — Regressionsschutz, dass die Korrektur NICHT versehentlich auch den
  Météo-France-Pfad umbiegt.
  - Test: `test_ac4_normalize_model_id_buendelt_vokabular_auf_kanonischen_schluessel`
    (`tests/tdd/test_model_registry_normalization.py`, Parametrisierung
    `("AROME-HIGHRES", "meteofrance_arome")`) bleibt unverändert grün.
  - Gegenprobe: Würde bei der Korrektur versehentlich auch `"arome-highres":
    "meteofrance_arome"` auf `"geosphere_arome"` umgestellt, würde dieser Test rot — das ist der
    bestehende Schutz, der durch diese Fix-Scheibe nicht brechen darf.

- **AC-3:** Given der (korrigierte) Test `test_ac4_gegenprobe_zwei_schreibweisen_derselben_
  modellwelt_kollidieren_nicht_mit_anderer_welt` (`tests/tdd/test_model_registry_normalization.py:
  68-81`) / When er nach der Korrektur läuft / Then prüft er `normalize_model_id("AROME") ==
  "geosphere_arome"` UND `normalize_model_id("AROME") != normalize_model_id("icon_d2")` — die
  bestehende Kollisions-Gegenprobe bleibt erhalten, nur der erwartete Zielwert ändert sich.
  - Test: dieselbe Testfunktion, Zeile 80 angepasst (s. Implementation Details Punkt 2).
  - Gegenprobe: Bliebe Zeile 80 unverändert bei `"meteofrance_arome"`, wäre der Test nach dem
    Fix ROT (weil `arome` jetzt `"geosphere_arome"` liefert) — dieser rote Zustand ist der
    Beleg, dass der Test überhaupt etwas Konkretes prüft, statt permissiv zu sein.

- **AC-4:** Given zwei fabrizierte `ForecastMeta`-Instanzen, eine mit `model="AROME"`
  (GeoSphere-Form), eine mit `model="AROME-HIGHRES"` (Météo-France-Form), beide sonst identisch /
  When `effective_cape_model_id()` für beide aufgerufen wird / Then liefern beide
  UNTERSCHIEDLICHE kanonische Schlüssel (`"geosphere_arome"` vs. `"meteofrance_arome"`) — vorher
  kollidierten beide auf denselben Schlüssel.
  - Test: neuer oder erweiterter Test in `test_model_registry_normalization.py`, der beide
    Ergebnisse nebeneinander vergleicht (`!=`), nicht nur je einzeln gegen einen erwarteten String.
  - Gegenprobe: Eine Implementierung, die versehentlich beide Rohwerte weiterhin auf denselben
    Schlüssel abbildet (z. B. durch einen Copy-Paste-Fehler beim Ändern der Alias-Zeile), würde
    hier NICHT auffallen, wenn AC-1/AC-2 isoliert geprüft würden, aber sehr wohl bei diesem
    direkten `!=`-Vergleich.

## Known Limitations

- **Kein aktiver, heute sichtbarer Fehlalarm wird durch diesen Fix behoben** — verifiziert (s.
  Expected Behavior → Side effects): GeoSphere liefert auf der primären Vorhersage kein
  `cape_jkg`, der additive GeoSphere-CAPE/CIN-Pfad (#1758) umgeht `model_registry` ohnehin über
  eigene Felder (`cape_geosphere_jkg`, `src/app/models.py:195-201`). Dieser Fix ist präventiv
  ("maximale Qualität", PO-Vorgabe #1419 Abschnitt 2a) für den Moment, in dem eine künftige
  Änderung `cape_geosphere_jkg` in das gemeinsame `cape_jkg`-Feld überführt oder GeoSphere in die
  CAPE-Fallback-Kette einträgt.
- **`geosphere_arome` bleibt dauerhaft ohne Eichung** in `CAPE_THRESHOLDS_JKG` — bewusst, keine
  offene Lücke (s. Purpose). Eine künftige Eichung wäre ein separates Ticket, sobald GeoSphere
  eine rückwirkende Archivquelle für AROME anbietet.
- **Kein nutzersichtbarer Ausgabe-Unterschied:** die drei Mail-Renderer
  (`compact.py:316`, `html.py:531`, `plain.py:392`) lesen den ROHEN `meta.model`-Wert
  (`"AROME"`), nicht das normalisierte Ergebnis dieser Registry — der angezeigte Modellname
  ändert sich durch diesen Fix nicht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine — reine Korrektur eines fehlerhaften Alias-Eintrags in einer bestehenden
  Normalisierungstabelle, kein neues Muster.
- **Rationale:** Das Alias-Muster ("mehrere Rohwerte pro Modellwelt auf einen kanonischen
  Schlüssel") existiert bereits (`_MODEL_ALIASES`, u. a. Präzedenzfall #2178 für die
  CAPE-Leiter-Konstanten in derselben Datei ohne eigenes ADR). Diese Fix-Scheibe ändert nur den
  ZIELWERT eines einzelnen Dict-Eintrags — keine Entscheidung über Kanäle, Provider-Auswahl,
  Datenmodell/Persistenz, Auth, Editor-Paradigma oder Test-/Deploy-Strategie. Die betroffene Doku
  (`feat_1758_geosphere_cape_cin.md:83-85`) wird in derselben PR aktualisiert statt durch ein
  neues ADR abgelöst.

## Changelog

- 2026-09-24: Initial spec created (Issue #2225).
