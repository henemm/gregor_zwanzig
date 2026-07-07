# Context: #1035 Amtliche Alerts Slice 2 — Météo-France Vigilance

## Request Summary
Erste echte Quelle für die in #1034 gebaute Official-Alerts-Registry: `VigilanceSource` ruft die
amtliche Météo-France-API ab und liefert Gewitter-/Sturmböen-/Hitze-Warnungen für Frankreich
(Fokus Côte d'Azur, inkl. Korsika) in Compare-Mail (HTML-Badge + Text-Parität).

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/official_alerts/base.py` | `OfficialAlertSource`-Protocol + Registry, hier registriert sich `VigilanceSource` |
| `src/services/official_alerts/models.py` | `OfficialAlert`-Dataclass, die `fetch()` befüllen muss |
| `src/services/official_alerts/__init__.py` | Modul-Init, evtl. Import-Trigger für Lazy-Registration |
| `src/services/comparison_engine.py:180-187` | Ruft `get_official_alerts_for_location()` bereits auf (additiv, nur Erfolgszweig) — **keine Änderung nötig** |
| `src/output/renderers/email/compare_html.py:597,646` | HTML-Badge-Rendering bereits verdrahtet (`_render_official_alerts_block()`) — **keine Änderung nötig** |
| `src/output/renderers/email/design_tokens.py:25-27` | `G_SUCCESS`/`G_WARNING`/`G_DANGER` Level-Farb-Tokens (bereits genutzt von HTML-Renderer) |
| `src/output/renderers/comparison.py:329` `render_comparison_text()` | **MUSS geändert werden** — Text-Renderer kennt `official_alerts` noch nicht (Text-Paritäts-AC aus #1035) |
| `src/providers/brightsky.py`, `src/providers/geosphere.py` | Stilmuster: httpx-Call, Bounding-Box-Konstanten als Modul-Level-Floats, `logger = logging.getLogger(name)` |
| `src/providers/base.py` | Registry-Pattern-Vorlage (Protocol + `runtime_checkable`) |
| `src/services/radar_service.py:38-42` | Geo-Scope-Vorlage: `_AROME_FR_LAT_MIN/MAX/LON_MIN/MAX` Bounding-Box für Frankreich inkl. Korsika — als `covers()`-Vorfilter direkt wiederverwendbar |

## Existing Patterns

- **Registry-Pattern:** `register_official_alert_source(source)` bei Modul-Import aufrufen
  (Lazy-Registration), analog `providers/base.py`. Muss in `official_alerts/__init__.py` oder
  einer zentralen Import-Stelle passieren, sonst bleibt `VigilanceSource` unregistriert.
- **Fail-soft-Aggregation:** `get_official_alerts_for_location()` fängt bereits jede Exception pro
  Quelle ab und loggt nur eine Warnung (kein Crash) — `VigilanceSource.fetch()` darf also werfen,
  muss es aber nicht; sauberer ist `try/except` intern mit leerem Rückgabewert (analog AC-2
  „fail-soft bei fehlenden Zugangsdaten").
- **Bounding-Box-Vorfilter:** `covers()` soll analog `_AROME_FR_*` in `radar_service.py:38-42`
  eine reine Rechteck-Prüfung sein (kein API-Call) — Kosten/Rate-Limit-Schutz vor dem eigentlichen
  Fetch.
- **HTML-Badge fertig, Text-Renderer offen:** Die HTML-Seite ist aus #1034 bereits fertig
  verdrahtet und braucht laut Issue #1035 **keine** Änderung. Die Text-Mail
  (`render_comparison_text()`) hat aktuell keinerlei `official_alerts`-Handling — das ist die
  einzige noch offene Renderer-Arbeit in diesem Slice.

## Dependencies

- **Upstream:** `services.official_alerts.get_official_alerts_for_location()` (fertig aus #1034),
  `httpx` (bereits Projekt-Dependency, siehe `brightsky.py`).
- **Downstream:** `comparison_engine.py` (ruft bereits auf), `compare_html.py` (rendert bereits),
  `render_comparison_text()` (muss neu konsumieren).

## Existing Specs

- `docs/specs/modules/issue_1034_official_alerts_foundation.md` — Fundament-Spec, Interface-Vertrag
  für `OfficialAlertSource`/`OfficialAlert`/Registry ist bindend und darf nicht verändert werden.

## Risiken & Abweichungen vom Issue-Text (WICHTIG für Analyse-Phase)

1. **Auth-Verfahren überholt:** Issue-Body beschreibt OAuth2-Client-Credentials-Flow
   (`meteo_token_provider.py`). Per Kommentar vom 2026-07-06 ist das **überholt**: einfacher
   API-Key-Header `apikey: <GZ_METEOFRANCE_APIKEY>`, Basis-URL `https://public-api.meteofrance.fr`.
   → **Kein** `meteo_token_provider.py` bauen. ENV bereits in Prod-/Staging-`.env` hinterlegt.

2. **Endpunkt-Diskrepanz (kritisch, muss in Analyse-Phase geklärt werden):** Issue-Body nennt
   einen Punkt-Bulletin-Endpoint `/vigilance/public/bulletin?lat=<lat>&lon=<lon>` mit
   `timelaps[].max_colors[].phenomenon_max_color_id`. Der Epic-Kommentar (#1033, 2026-07-06)
   verifiziert dagegen live nur `GET /public/DPVigilance/v1/textesvigilance/encours` (Text-Bulletins,
   kein lat/lon-Parameter, kein Département-Farbcode direkt ersichtlich). Für die Schwester-Quelle
   Météo des forêts (#1036) wurde zusätzlich ein Département-Karten-Endpoint verifiziert
   (`/public/DPMeteoForets/v1/carte/departement/encours?format=json&echeance=J1&id-departement=83`
   → JSON mit `niveau_j1`). Es ist **unklar, ob ein analoger Vigilance-Endpoint
   (`/public/DPVigilance/v1/carte/...` o.ä.) existiert**, der pro Département eine Farbstufe
   liefert — das wäre der natürliche Fetch-Pfad analog zu #1036, statt Text-Bulletins zu parsen.
   → **Vor der Spec-Phase real gegen die Météo-France-API prüfen** (Swagger/Portal), welcher
   Endpoint tatsächlich Département-Farbcodes liefert. Das entscheidet Parser-Design und AC-1-Testfall.

3. **Datei-Pfad im Issue veraltet:** Issue nennt `src/services/comparison_renderers.py` — die
   tatsächliche Datei heißt `src/output/renderers/comparison.py` (Funktion
   `render_comparison_text()`, Zeile 329). Vermutlich Altlast vor dem ADR-0017-Refactor
   (`src/outputs/` → `src/output/channels/`, Commit 7e5afa63).

4. **Département-Mapper ist Neuland im Repo:** Keine existierende Koordinate→Département-Logik
   im Code (Grep negativ). Muss komplett neu geschrieben werden, inkl. Korsika-Split 2A/2B an der
   Grenze bei Sartène (laut Issue aus Vorgänger-Projekt übernehmbar, aber nicht im Repo vorhanden
   — reine Neuimplementierung, referenzierter Vorgänger-Code liegt außerhalb des Repos in einem
   scratchpad-Pfad einer anderen Session und ist ggf. nicht mehr verfügbar).

5. **Namenskollision "vigilance":** `src/output/subject.py` nutzt bereits `"vigilance"` als
   Kategorie-Bezeichnung für SMS-Token (HR/TH-Skala, unabhängiges Konzept, keine Météo-France-
   Bezug). Kein technischer Konflikt (anderer Modul-Namespace), aber bei Grep-Suchen/Docs auf
   Verwechslung achten.

6. **Rate-Limit:** 60 req/min laut Epic-Kommentar (deckt sich mit Issue-Body). Bei Compare mit
   mehreren Orten in kurzer Zeit ggf. Caching pro Département sinnvoll (mehrere Orte in Var landen
   auf demselben Endpoint-Call) — in Analyse-Phase Cache-Bedarf bewerten.

## Analysis

### Type
Feature

### Endpunkt-Diskrepanz GEKLÄRT (echter API-Call, 2026-07-06, Key aus Staging-`.env`)

Der im Issue-Text genannte Punkt-Bulletin-Endpoint (`/vigilance/public/bulletin?lat=&lon=`)
existiert **nicht**. Real verifiziert (HTTP 200, `apikey`-Header):

```
GET https://public-api.meteofrance.fr/public/DPVigilance/v1/cartevigilance/encours
```

Antwort: **eine einzige nationale JSON-Antwort** mit `periods[]` (echeance `"J"` = heute, `"J1"` =
morgen) → `timelaps.domain_ids[]`, je Eintrag:
```json
{"domain_id": "83", "max_color_id": 1,
 "phenomenon_items": [{"phenomenon_id": "3", "phenomenon_max_color_id": 1}, ...]}
```
- `domain_id` ist bereits der Département-Code als String (`"83"`, `"06"`, `"13"`, `"2A"`, `"2B"`,
  ~122 Einträge inkl. `"FRA"`-Gesamtwert und vermutlich Übersee — Scope-Entscheidung nötig, siehe
  unten).
- Live-Stichprobe (2026-07-06 14:00 UTC): `06` (Alpes-Maritimes) und `2A`/`2B` (Korsika) zeigen
  `phenomenon_id "3"` (Orages/Gewitter) auf Farbstufe 2 (gelb); `13` (Bouches-du-Rhône) zeigt
  `phenomenon_id "6"` (Canicule) auf Stufe 2; `83` (Var) komplett grün.
- **Phänomen-ID-Mapping bestätigt** (offizielle Météo-France-Doku, siehe Quellen unten):
  `1`=Vent violent (Sturmböen), `2`=Pluie-inondation, `3`=Orages (Gewitter), `4`=Crues,
  `5`=Neige-verglas, `6`=Canicule (Extreme Hitze), `7`=Grand froid, `8`=Avalanches,
  `9`=Vagues-submersion. Issue-Scope = nur `1`, `3`, `6`.

**Wichtige Konsequenz fürs Design:** Da die API **eine nationale Antwort für alle Départements
gleichzeitig** liefert, braucht `VigilanceSource.fetch(lat, lon)` **nur einen einzigen HTTP-Call**
pro Compare-Lauf (nicht einen pro Ort!) — ein einfacher kurzlebiger In-Memory-Cache
(Modul-Level, TTL ~5–10 Min, kein neues Abstraktions-Framework, keine Wiederverwendung von
`WeatherCacheService` da dieser auf `SegmentWeatherData` typisiert ist) reicht, um bei mehreren
Orten im selben Vergleich nicht mehrfach zu callen. Rate-Limit (60 req/min) ist damit praktisch
irrelevant.

Quellen: [Descriptif technique Vigilance Metropole (PDF)](https://donneespubliques.meteofrance.fr/client/document/descriptiftechnique_vigilancemetropole_donneespubliques_v4_20230911_307.pdf), [meteofrance-api Referenz](https://meteofrance-api.readthedocs.io/en/stable/reference.html)

### Département-Mapper — Scope-Entscheidung nötig (an PO in Spec-Freigabe stellen)

Die API liefert Département-Codes, aber der Aufrufer übergibt Lat/Lon — wir brauchen weiterhin
Koordinate→Département. Keine Polygon-Daten im Projekt, kein neuer Geo-Dependency gewünscht
(Minimalismus-Prinzip). Empfehlung: **Nearest-Centroid-Tabelle**, eine Zeile pro Département
(öffentliche INSEE-Zentroid-Daten), generisch für ganz Metropole+Korsika — keine
Sonderfall-Logik (Korsika ist einfach zwei Tabelleneinträge `"2A"`/`"2B"` wie jeder andere
Département). Deckt AC-4 („kein Sonderfall-Code") strukturell sauber ab, ohne
Polygon-Genauigkeit — für Vigilance (das selbst nur Département-Granularität kennt) ausreichend.
**Offene Frage für Spec-Freigabe:** Volle Metropole (~96 Einträge) jetzt befüllen (passend zu
„landesweit per Design" laut Issue-Text) oder zunächst nur die 5 im Leitszenario genannten
Départements (83, 06, 13, 2A, 2B) mit generischer, erweiterbarer Tabellenstruktur? Tendiere zu
**voll befüllen** — es ist nur Daten, kein Logik-Mehraufwand, und vermeidet eine „halbfertige"
Implementierung.

`covers()` nutzt die bereits bestehende Frankreich-Bounding-Box aus
`radar_service.py:38-42` (`_AROME_FR_LAT_MIN/MAX/LON_MIN/MAX`) als Vorfilter (AC-3) — Code-Wiederverwendung
statt neuer Konstanten.

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/vigilance.py` | CREATE | `VigilanceSource`: `covers()` via France-Bbox-Reuse, `fetch()` mit gecachtem National-Call, Phänomen→Label-Mapping (nur 1/3/6) |
| `src/services/official_alerts/department_mapper.py` | CREATE | Nearest-Centroid-Tabelle + `lookup_department(lat, lon) -> str` |
| `src/services/official_alerts/__init__.py` | MODIFY | Import von `vigilance` triggert `register_official_alert_source()` (Lazy-Registration) |
| `src/output/renderers/comparison.py` | MODIFY | `render_comparison_text()` — eine Zeile pro Ort mit amtlicher Warnung (Text-Paritäts-AC) |
| `docs/specs/modules/issue_1035_vigilance.md` | CREATE | Spec |
| Tests (TDD-Dateien) | CREATE | Echter API-Call-Test (AC-1), Fail-soft-Test ohne ENV (AC-2), Nicht-Frankreich-Test (AC-3), Korsika-Test (AC-4) |

**Kein** `meteo_token_provider.py` (Auth vereinfacht, siehe Risiko 1 oben — bereits vor der
Analyse-Phase per Issue-Kommentar überholt).

### Scope Assessment
- Files: 4 neu, 2 geändert (inkl. Spec) + Tests
- Estimated LoC: ~150–220 src-LoC (Département-Tabelle als Daten zählt mit, aber kompakt: 1 Zeile
  pro Département). Innerhalb des 250-LoC-Workflow-Limits, aber ohne großen Puffer — bei
  voller Metropole-Tabelle ggf. `loc_limit_override` nötig, vorher User fragen (Memory-Regel).
- Risk Level: MEDIUM (echte externe API, aber jetzt real verifiziert und einfacher als
  ursprünglich angenommen — kein OAuth2, ein einziger API-Call pro Compare-Lauf)

### Technical Approach
1. `department_mapper.py`: statische Zentroid-Tabelle (Dict[str, tuple[float,float]]) + einfache
   euklidische Nächste-Nachbar-Suche (kein Geo-Dependency).
2. `vigilance.py`: `covers()` = France-Bbox-Reuse; `fetch()` = gecachter GET gegen
   `cartevigilance/encours` (apikey-Header aus `GZ_METEOFRANCE_APIKEY`, fail-soft bei fehlendem
   ENV → `[]` + einmaliges Warn-Log), Département via Mapper bestimmen, `domain_ids`-Eintrag
   suchen, `phenomenon_items` auf `{1,3,6}` filtern, `OfficialAlert` pro Treffer bauen
   (`level=phenomenon_max_color_id`, `hazard`∈{wind_gust,thunderstorm,extreme_heat}, deutsches
   `label`).
3. Registrierung via Modul-Import-Trigger in `official_alerts/__init__.py` (analog #1034-Vorlage).
4. `render_comparison_text()`: nach dem Score-Block pro Ort eine optionale Zeile
   `⚠️ Amtliche Warnung: <label>` wenn `loc_result.official_alerts` nicht leer.

### Dependencies
- Upstream: `httpx` (vorhanden), `GZ_METEOFRANCE_APIKEY` (ENV, bereits in Prod-/Staging-.env),
  keine neuen PyPI-Pakete.
- Downstream: keine (additiv, HTML-Renderer unverändert).

### Entscheidungen (User, 2026-07-06)
- **Département-Mapper:** volle Metropole-Tabelle (~96 Einträge), nicht nur die 5
  Leitszenario-Départements. Datenquelle: öffentliche INSEE-Zentroid-Daten, während der
  Implementierung zu beschaffen.
- **Zeithorizont:** beide Horizonte (`J`=heute, `J1`=morgen) werden abgebildet, nicht nur „heute".
  `OfficialAlert.valid_from`/`valid_to` (bereits im #1034-Modell vorhanden, keine Schema-Änderung
  nötig) werden aus `begin_validity_time`/`end_validity_time` der jeweiligen `period` befüllt —
  das unterscheidet heute/morgen für den Renderer ohne neues Feld.

### Beobachtung: Badge-Farbmapping aus #1034 passt nicht exakt zu Vigilance-Farbstufen (Follow-up, kein Scope-Fix hier)

`compare_html.py:144-159` (`_render_official_alerts_block`) mappt Level 1–2 → `G_SUCCESS` (grün),
3 → `G_WARNING`, 4+ → `G_DANGER`. Das war beim Schreiben in #1034 eine generische Platzhalter-Skala
ohne reale Quelle. Vigilance nutzt aber genau 4 Farbstufen (1=grün/vert, 2=gelb/jaune, 3=orange,
4=rot/rouge) — Level 2 (gelb, „Achtung geboten") würde mit der aktuellen Logik **grün** (=
„alles gut") gerendert, was der Live-Stichprobe widerspricht (Alpes-Maritimes/Bouches-du-Rhône/
Korsika stehen aktuell auf Gelb). AC-1 dieses Issues verlangt nur den Level-3-Fall (orange), der
bereits korrekt rendert — daher **kein Scope-Fix in #1035** (würde `compare_html.py` anfassen,
was das Issue explizit ausschließt). **Folge-Issue anlegen** sobald die echte Quelle live ist
(Nebenbefund-Pflicht laut Projekt-Konvention).

**Scope-Entscheidung für `fetch()`:** Alerts ab Level ≥2 (gelb) werden geliefert — nicht erst ab
Level ≥3 —, da genau das die PO-Realsituation an der Côte d'Azur gerade abbildet und „Achtung
geboten" ein legitimes Warnsignal ist, auch wenn die Badge-Farbe (Folge-Issue) noch nicht exakt
passt.

## Nächster Schritt
`/30-write-spec`.
