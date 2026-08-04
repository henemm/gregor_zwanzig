# Context: S2b — DWD ICON-D2 liefert Gewittersignale für Alpen/Österreich/Deutschland (#1457)

## Request Summary

Zweite Scheibe des Gewitter-Konzepts #1419: Nach Météo-France (S2a, live seit
2026-08-03) soll DWD ICON-D2 für Deutschland/Alpen/Österreich Blitzpotenzial
(`lpi`/`lpi_max`) und Hagel (`grau_gsp`) liefern — über denselben gemeinsamen
Mechanismus, den S2a bereits gebaut hat. Auslöser: die nächste Tour geht zum
Karnischen Höhenweg (Grenze Österreich/Italien), dort liefert die heutige
Zuständigkeit (GeoSphere) kein Gewittersignal.

## Related Files

| File | Relevance |
|------|-----------|
| `src/providers/dwd.py` | `DwdDirectProvider` — hier muss `fetch_thunder_signals` (Protokoll `ThunderSignalProvider`) ergänzt werden. Bestehendes Muster: `_fetch_series(param, lat, lon, run, deadline_at)` lädt EINE volle ICON-D2-Rasterdatei je Parameter+Zeitschritt (kein serverseitiger Punkt-Query, anders als Météo-France-WCS) und liest EINEN Pixel |
| `src/providers/thunder_routing.py` | Gewitter-Zuständigkeitstabelle, heute nur `FR → fr_direct`. S2b braucht einen zweiten Eintrag für das ICON-D2-Gebiet (43,17–58,09 N), **mit Vorrang vor GeoSphere** (`region_routing` bleibt für Schnee/Temperatur unverändert bei `at_direct`) |
| `src/providers/thunder_enrichment.py` | Der EINE gemeinsame Anschluss (`enrich_thunder`) — darf laut Spec-AC-8/PO-Vorgabe „keine Einzellösungen" NICHT providerspezifisch geändert werden. **Schreibt heute ausschließlich in `dp.lightning_density_per_km2_3h`** |
| `src/providers/base.py:71` | `ThunderSignalProvider`-Protokoll — `fetch_thunder_signals(location, start, end) -> dict[int, Optional[float]]`, EIN Rückgabewert je Stunde |
| `src/app/models.py:146` | `ForecastDataPoint.lightning_density_per_km2_3h: Optional[float]` (S2a-Feld, Météo-France-Skala). `cape_jkg` (Zeile 108) existiert bereits, ist aber ein **anderes** Signal (Open-Meteo-Ensemble-CAPE), nicht DWDs `lpi` |
| `src/providers/meteofrance.py:512-541` | Referenzimplementierung `fetch_thunder_signals` (S2a) — Fail-soft, `None` statt `0`, AC-2/AC-6-Muster |
| `docs/reference/api_contract.md:194` | Dokumentiert `lightning_density_per_km2_3h` explizit als **bewusst eigenes Feld — NICHT zusammengelegt** mit dem DWD-Blitzpotenzial |
| `docs/adr/0041-*.md` | Zuständigkeit einer Quelle nach Endpunkt-Art — Muster für `thunder_routing` als zweite, größenabhängige Tabelle |
| `docs/specs/modules/provider_dwd.md` | Bestehende Spec des DWD-Direktproviders (S2a-Vorbild: `feat_1457_s2a_blitzdichte_meteofrance.md`) |

## Existing Patterns

- **Geteilter Mechanismus (S2a):** Protokoll (`base.ThunderSignalProvider`) + Zuständigkeitstabelle (`thunder_routing.py`) + EIN Anreicherungspunkt (`thunder_enrichment.py`, hängt im regulären Rückgabeweg von `OpenMeteoProvider.fetch_forecast`). Eine neue Quelle wird wirksam, indem sie (a) das Protokoll erfüllt und (b) in der Tabelle steht — die Anreicherungsstelle bleibt unangetastet.
- **DWD-Fetch-Muster:** `_fetch_series` lädt sequentiell einen Request je Zeitschritt (kein Rechteck-/Sammelabruf wie bei Météo-France nötig, weil jede Datei ohnehin ganz Deutschland abdeckt) — die Erweiterung um zwei Parameter (`lpi`, `grau_gsp`) folgt exakt demselben Aufruf-Muster wie `t_2m`/`u_10m`/`v_10m`/`tot_prec`.
- **Fehlwert-Marker:** `_precip_series_from_cumulative` zeigt das etablierte Muster für Rohwert-Transformation vor dem Domänen-Feld.

## Dependencies

- **Upstream:** `ThunderSignalProvider`-Protokoll, `thunder_routing.thunder_provider_for()`, `providers.base.get_provider()`, ICON-D2-Open-Data (`opendata.dwd.de`) für `lpi`/`lpi_max`/`grau_gsp`.
- **Downstream:** `thunder_enrichment.enrich_thunder()` (ruft das Protokoll auf), alle Verbraucher von `ForecastDataPoint` (Alarm-Lauf, Trip-Briefing, Ortsvergleich) — sobald ein neues Feld existiert, wird es dort noch nicht dargestellt (das ist bewusst S3, Stufenbildung).

## Existing Specs

- `docs/specs/modules/feat_1457_s2a_blitzdichte_meteofrance.md` — S2a-Vorbild, inkl. aller Adversary-Lehren
- `docs/specs/modules/provider_dwd.md` — Basis-Spec DWD-Provider

## Risks & Considerations

### 🔴 Zentrale offene Design-Frage: der gemeinsame Anschluss kennt nur EIN Feld

`thunder_enrichment.py::enrich_thunder()` schreibt heute hart codiert in
**genau ein** Modellfeld (`lightning_density_per_km2_3h`). DWDs Blitzpotenzial
(`lpi`, Energiegröße, Messwerte ~88) ist laut eigener Spec-Vorgabe (Abschnitt
3 des Issues, api_contract.md:194) **zwingend ein separates Feld** —
Zusammenlegen mit der Météo-France-Dichte (~0,1–0,2) wäre der stille Fehler,
den dieses Epic gerade verhindern soll.

Das Protokoll `ThunderSignalProvider.fetch_thunder_signals` liefert aber nur
`dict[int, Optional[float]]` — EIN Wert je Stunde, kein Signal, welchem Feld
er zuzuordnen ist. Der gemeinsame Anschluss darf laut AC-8/PO-Vorgabe
"keine Einzellösungen" aber keinen providerspezifischen Sonderfall bekommen.

**Muss in der Spec-Phase entschieden werden**, z. B. durch eine kleine,
protokollseitige Erweiterung (Signal-Art als Teil der Rückgabe statt als
Provider-Sonderfall) — keine Entscheidung, die sich beim Implementieren
nebenbei ergeben darf.

### Hagel (`grau_gsp`) ist ein ZWEITES neues Feld — dieselbe Frage doppelt

Kommt zur obigen Frage hinzu: Blitzpotenzial UND Hagel sollen laut PO-Vorgabe
beide in dieser Scheibe kommen ("Blitz-Potenzial und Hagel sind der Kern").
Das ist keine zusätzliche Zuständigkeitszeile, sondern ein **zweites** neues
Datenfeld mit derselben strukturellen Frage wie oben.

### Fehlwert-Marker (bekannt aus Vorarbeit, Issue-Kommentar 2026-08-02)

`echotop` liefert `-999.0` als Fehlwert-Marker (nicht Teil dieser Scheibe,
nur zur Erinnerung an das Muster). Für `lpi`/`lpi_max` und `grau_gsp` selbst
ist noch **nicht geprüft**, ob und welcher Fehlwert-Marker existiert — laut
PO-Vorgabe „nicht raten", gegen mehrere Läufe/DWD-Beschreibung prüfen.

### Budget/Kosten — vermutlich unkritisch, aber nicht nachgemessen

Anders als bei Météo-France (WCS-Rechteck) lädt DWD ohnehin eine volle
Rasterdatei je Parameter+Zeitschritt, unabhängig vom Ort — zwei neue
Parameter bedeuten zusätzlich 2 × 24 = 48 Downloads je Ort und Lauf (analog
zu den bestehenden 4 Basis-Parametern). Die bekannte Mehrfach-Download-
Ineffizienz bei mehreren Orten (identische Datei wird pro Ort erneut
geladen) ist ein **vorbestehendes** Verhalten der Grundvorhersage, nicht neu
durch S2b eingeführt — vermutlich kein Scope dieser Scheibe, aber bei der
Analyse kurz gegenprüfen (nicht raten).

### Bewusst NICHT in dieser Scheibe (PO-Abgrenzung aus Issue)

- Keine feineren Größen (`cape_ml`, `cin_ml`, `sdi_2`, `uh_max`, `echotop`,
  `dbz_cmax`) — die gehören in S3 (Stufenbildung).
- Kein Anfassen des Anreicherungswegs über das hinaus, was zur Lösung der
  Feld-Frage oben nötig ist.
- Keine Sammelabruf-/Bündelungs-Logik wie bei Météo-France (S2a) — DWDs
  Dateien decken ohnehin ganz Deutschland ab, ein Bounding-Box-Mechanismus
  ergibt hier keinen Sinn.

## Analysis (Plan/Sonnet-Bewertung + Hinweis Nachbar-Session #1474)

### Type
Feature (Standard Track)

### Lösung für die zentrale Design-Frage: additive Protokoll-Erweiterung

Empfehlung (3 Optionen bewertet): **neue optionale Protokoll-Methode**
`fetch_thunder_signals_named(location, start, end) -> dict[str, dict[int, Optional[float]]]`
— analog zum bereits etablierten Erweiterungsmuster `fetch_thunder_signals_multi`
(optional, `getattr`-Check in `thunder_enrichment.py`, Fallback auf die
bestehende Einzelwert-Methode). Verworfen: (a) bestehende Signatur hart
ändern — bricht S2a/Météo-France, hohes Regressionsrisiko; (c) Provider
deklariert Feldnamen selbst — verteilt die Signal→Feld-Kenntnis auf zwei
Stellen statt einer.

**Zuordnung Signalname → Modellfeld** lebt an EINER Stelle in
`thunder_enrichment.py` (kleine Lookup-Tabelle) — kennt weiterhin keinen
Providernamen, nur ein Signal-Vokabular (AC-8 bleibt gewahrt).

**Heikelster Punkt:** der bestehende "schon gefüllt"-Wächter
(`thunder_enrichment.py:85`, prüft heute nur `lightning_density_per_km2_3h`)
muss auf "irgendein aus der Tabelle bekanntes Feld" verallgemeinert werden —
sonst verhindert ein Météo-France-Ort (dessen DWD-Felder naturgemäß leer
bleiben) fälschlich einen zweiten Abrufversuch, oder umgekehrt wird ein
Teilausfall (nur `lpi` kam, `grau_gsp` nicht) falsch als "schon versucht"
behandelt.

### Scope Assessment
- Produktivcode: ~165-230 Zeilen (`base.py`, `thunder_enrichment.py`,
  `models.py`, `dwd.py`, `thunder_routing.py`)
- Tests: ~250-400 Zeilen (Erweiterung des S2a-Regressionsschutzes +
  DWD-spezifische Fetch-/Fail-soft-Tests + Fixtures)
- Spec-Dokument: ~150-250 Zeilen
- Risk Level: MEDIUM (additiv, aber der Fill-Wächter im gemeinsamen Pfad
  braucht besondere Sorgfalt — genau dort saßen bei S2a mehrfach die
  Adversary-Funde)

### 🔴 Warnung aus paralleler Session (MQ-Nachricht, ungeprüft von uns, ernst zu nehmen)

Eine andere, parallel laufende Sitzung (baut #1474, hat heute S2a
ausgeliefert) meldet unaufgefordert drei Punkte, exakt aus der eigenen
Erfahrung mit demselben Fehlerbild bei Météo-France:

1. **Abrufnamen sind nicht die Kurzformen aus der Fachliteratur.** `lpi`,
   `lpi_max`, `grau_gsp` sind KEINE bestätigten DWD-Open-Data-Feldnamen —
   bei Météo-France hieß die Falle `LITOTA3` (kam beim echten Dienst 0-mal
   vor, jeder Abruf lief lautlos in 404, alle Tests trotzdem grün, weil sie
   nur aufgezeichnete Dateien lasen). **Vor der Implementierung**: echtes
   Verzeichnis auf `opendata.dwd.de` prüfen, plus ein Live-Test (Marker
   `live`, Vorbild `tests/tdd/test_thunder_coverage_name_live.py`), der den
   im PRODUKTIVCODE stehenden Namen gegen das Angebot prüft (Name muss aus
   dem Code gelesen werden, nicht im Test wiederholt).
2. Modell-Lauf-Wahl braucht denselben Sicherheitsabstand-Fix wie S2a
   (Standard-`_latest_run` könnte einen noch nicht veröffentlichten Lauf
   berechnen) — für ICON-D2 eigens prüfen, Nullpunkt der Stunden-Offsets
   bleibt am ursprünglichen Lauf.
3. **Schwellenwerte für `lpi` liegen in #1474 bereits vor** (>1 J/kg leicht,
   ≥30 mittel, ≥50 hoch — nur die untere Grenze gilt als belastbar). #1474
   baut `thunder_level_from_signals()` mit einer Tabelle je Signal, fusioniert
   über `max_thunder()`. **Für uns heißt das: S2b liefert nur den rohen Wert
   ins neue Feld — KEINE eigene Einstufungs-/Schwellenlogik bauen.** Das
   deckt sich mit der PO-Abgrenzung "keine Stufenbildung" oben — bestätigt
   die Grenze, statt sie zu verschieben. Feldname im Modell vor Spec-Freigabe
   gegen #1474 abgleichen (Namenskollision vermeiden), sobald deren Spec
   verfügbar ist.

### Dependencies (Reihenfolge)
1. Abrufnamen UND Fehlwert-Marker empirisch gegen echte DWD-Dateien klären
   (blockiert `dwd.py`, unabhängig vom Protokoll-Design)
2. Protokoll-Erweiterung + generalisierter Fill-Wächter (S2a-kritisch, RED
   zuerst)
3. `models.py`: zwei neue Felder (parallel zu 2 möglich)
4. `dwd.py`: Implementierung (abhängig von 1 + 2)
5. `thunder_routing.py`: neue Zeile
6. Doku (`api_contract.md`, Spec)
7. Tests: gemeinsamer Pfad zuerst (Regressionsschutz S2a), dann DWD-spezifisch

### Open Questions
- [ ] Echte DWD-Abrufnamen für Blitzpotenzial/Hagel (nicht `lpi`/`grau_gsp`
      annehmen)
- [ ] Fehlwert-Marker für die beiden neuen Größen (kein Analogieschluss von
      `echotop`)
- [ ] Feldnamen im Modell mit #1474 abgleichen, sobald deren Spec vorliegt
