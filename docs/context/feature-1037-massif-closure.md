# Context: feature-1037-massif-closure

Issue: #1037 — Amtliche Alerts Slice 4: Massiv-Betretungsverbote (Korsika/Var)
Part of Epic #1033. Baut auf #1034 (Fundament), #1035 (department_mapper), #1036 (meteo_forets) auf.

## Request Summary

Vierte Quelle für die Official-Alerts-Registry: Präfektur-Betretungsverbote einzelner Wander-Massive
bei akuter Waldbrandgefahr. Undokumentierter, auth-freier JSON-Endpoint pro Département. Ein Ort im
Compare bekommt einen Badge „Zugang gesperrt — [Massiv-Name]", wenn das ihn abdeckende Massiv gesperrt
ist. Mechanismus département-generisch (keine GR20-Hartkodierung, Scope-Korrektur 2026-07-06).

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/official_alerts/base.py` | `OfficialAlertSource`-Protocol + Registry (`register_official_alert_source`, `get_official_alerts_for_location`). NEUE Quelle registrieren. |
| `src/services/official_alerts/models.py` | `OfficialAlert`-Dataclass (source/hazard/level/label/…). Wiederverwenden, kein neues Modell. |
| `src/services/official_alerts/department_mapper.py` | `lookup_department(lat,lon)` → Code (`"83"`, `"2A"`, `"2B"`, …). Wiederverwenden für `covers()`. |
| `src/services/official_alerts/meteo_forets.py` | **Nächstes Vorbild** (Slice 3): pro-Département-Cache, TTL 300s/60s, fail-soft, `covers()`-Bounding-Box, `_warn_once`, Registry-Registration in `__init__.py`. |
| `src/services/official_alerts/vigilance.py` | Vorbild fetch/Cache/`_extract_alerts`-Struktur. |
| `src/services/official_alerts/__init__.py` | Lazy-Registration bei Import — hier `MassifClosureSource()` registrieren. |
| `src/output/renderers/comparison.py:419` | Text-Renderer iteriert `loc_result.official_alerts` **generisch** → gibt `alert.label` aus. |
| `src/output/renderers/email/compare_html.py:144` | `_render_official_alerts_block` iteriert **generisch** über alle `official_alerts`, Level→Farbe. |
| `src/services/comparison_engine.py:187` | Einziger Konsument: `get_official_alerts_for_location(loc.lat, loc.lon)` (nur bei `official_alerts_enabled`, #1040). |
| `docs/specs/modules/issue_1037_official_alerts_massif_closure.md` | **Bereits vorhandene Draft-Spec** (v1.1, created 2026-07-06, NICHT approved). Als Ausgangspunkt für `/30-write-spec`. |

## Existing Patterns

- **Quelle = Klasse mit `name`/`covers`/`fetch`**, per `register_official_alert_source()` in `__init__.py` registriert.
- **`covers()` macht KEINEN API-Call** — nur Geo-Vorfilter (Bounding-Box bei vigilance/meteo_forets; hier: Département-Key in `MASSIF_ZONES`).
- **`fetch()` fail-soft:** fehlender Key/HTTP-Fehler/kaputte Struktur → `[]`, nie Exception (Registry fängt zusätzlich ab, aber Quelle soll selbst sauber sein).
- **Pro-Département Modul-Level-Cache** (`_cache: dict`), TTL 300s Erfolg / 60s Fehlschlag — verhindert Call-pro-Ort-Sturm im selben Compare-Lauf.
- **`OfficialAlert(level=…)`** steuert die HTML-Badge-Farbe: 1-2→G_SUCCESS, 3→G_WARNING, 4+→G_DANGER (`compare_html.py`). Label trägt den Text.

## Wichtige Architektur-Erkenntnis (Renderer)

Beide Renderer sind **bereits generisch** über `official_alerts`. Erzeugt `MassifClosureSource.fetch()` ein
`OfficialAlert(hazard="access_ban", label="Zugang gesperrt — Massif des Maures", level=…)`, erscheint der
Badge automatisch. **Der im Issue genannte „GEÄNDERT comparison_renderers.py" existiert so nicht** — die Datei
heißt `comparison.py`/`compare_html.py` und braucht evtl. gar keine Änderung (in Analyse zu klären: reicht die
generische Zeile, oder ist eine access_ban-spezifische Darstellung gewünscht?).

## Dependencies

- **Upstream:** `department_mapper.lookup_department`, `models.OfficialAlert`, `base.register_official_alert_source`, `httpx`, `radar_service`-Bounding-Box (Frankreich-Filter, wie meteo_forets).
- **Downstream:** `comparison_engine` (Konsument via Registry), Text- + HTML-Renderer (generisch).

## Existing Specs

- `docs/specs/modules/issue_1034_official_alerts_foundation.md` — Registry-Fundament
- `docs/specs/modules/issue_1035_vigilance_source.md` — erste echte Quelle + department_mapper
- `docs/specs/modules/issue_1036_meteo_forets_source.md` — bestes Muster (pro-Département-Cache)
- `docs/specs/modules/issue_1037_official_alerts_massif_closure.md` — **Draft, zu finalisieren**

## Live-Endpoint-Verifikation (2026-07-07, curl)

Endpoint: `https://www.risque-prevention-incendie.fr/static/{DEPT}/import_data/{YYYYMMDD}.json` (auth-frei, HTTP 200).
Struktur bestätigt: `{"massifs": {"<id>": [niveau_j1, niveau_j2]}, "zm": {"<id>": niveau_j1}}`.

| DEPT | HTTP | Massive | J1-Level heute | Befund |
|---|---|---|---|---|
| 83 Var | 200 | 9 (831–839) | bis 3 | ✅ AC-1 realistisch erfüllbar (Level ≥2 vorhanden) |
| 13 Bouches-du-Rhône | 200 | 27 | 2 | ✅ verfügbar |
| **06 Alpes-Maritimes** | **404** | — | — | ❌ **Endpoint liefert 06 NICHT** (heute + gestern + `/static/06/` root alle 404) |
| Korsika `20` | 200 | 11 (211, 2024, …) | 1 | ✅ **zusammengefasst als `20`**, NICHT `2A`/`2B` |
| Korsika `2A`/`2B` | 404 | — | — | getrennte Codes werden nicht bedient |

## Risks & Considerations

1. **06 Alpes-Maritimes nicht verfügbar (404):** Issue-Body + Draft-Spec nennen 06 als Zieldépartement,
   der Endpoint liefert dafür aber keine Daten. → Analyse/Spec: 06 aus MVP-Scope streichen ODER mit PO klären.
   ACs verlangen 06 nicht (AC-1 = Var, AC-2 = Korsika), also **kein AC-Blocker**, aber Scope-Klärung nötig.
2. **Korsika = `20`, nicht `2A`/`2B`:** `department_mapper` liefert `"2A"`/`"2B"`. `covers()`/`fetch()` brauchen
   ein Mapping (2A/2B → Source-DEPT `20`). Kein Sonderfall-Code im Sinne der Generizität, aber eine
   Département-Code→Source-DEPT-Abbildung in `MASSIF_ZONES`/Fetch nötig. In Spec sauber fassen.
3. **Massiv-Zonen-Tabelle muss komplett neu recherchiert werden** — auch Korsika: `gr20_zone_massif_ids.py`
   existiert NICHT im Repo (Vorgänger-Projekt, nicht importiert). Zentrum-Koordinaten + Radius je Massiv-ID
   von Hand aus interaktiver Karte / JSON-Keys ableiten. Reale Recherche-Arbeit, keine Portierung.
4. **Undokumentierter Endpoint** kann strukturell brechen → defensiv parsen (fehlende Keys → `[]`), Warnung loggen.
5. **LoC ~250** am oberen Rand — evtl. `loc_limit_override` (mit PO). Zonen-Tabelle ist Daten, aber zählt als Code.
6. **Monitoring** (`last_run`/Fehler-Zähler) als Modul-Level-Status-Dict, wie im Issue gefordert (kein neuer Service).

## Offene Fragen für /20-analyse

- Reicht der generische Renderer, oder access_ban-spezifische Badge-Darstellung? (vermutlich generisch = ja)
- Wie Niveau→level mappen (1–5 der Quelle vs. 1–4 der `OfficialAlert`/Badge-Farblogik)? Ab welchem Niveau „gesperrt"?
- 06 endgültig raus? Korsika-`20`-Mapping-Form.
- Nächstgelegenes-Massiv-Zuordnung: reiner Nearest-Center innerhalb `radius_km`, oder ohne Radius nur nearest?

---

## Analysis (2026-07-07)

### Type
Feature (neue Quelle für bestehende Registry; additiv).

### Amtliche Niveau-Semantik (verifiziert gegen Var-Legende risque-prevention-incendie.fr/var/)
5-stufige Skala mit amtlichen Zugangsregeln:

| Niveau | Farbe | Amtliche Regel | Zugang |
|---|---|---|---|
| 1 | vert | Accès et travaux autorisés | erlaubt |
| 2 | jaune | Accès autorisé, travaux mit Auflagen | erlaubt |
| 3 | orange | Accès **déconseillé**, travaux interdits | abgeraten/eingeschränkt |
| 4 | rouge | Accès **interdit** hors ZAPEF | gesperrt |
| 5 | noir | Accès et travaux interdits (tous massifs) | gesperrt (total) |

### PO-Entscheidungen (2026-07-07)
1. **Badge abgestuft ab Niveau 3** (nicht ≥2 wie im ursprünglichen AC-1 — faktisch korrekt):
   - Niveau 1-2 → **kein Badge** (Zugang erlaubt)
   - Niveau 3 → `⚠️ Zugang eingeschränkt — [Massiv-Name]` (Badge-Level 3 → G_WARNING/orange)
   - Niveau 4 → `⛔ Zugang gesperrt — [Massiv-Name]` (Badge-Level 4 → G_DANGER/rot)
   - Niveau 5 → `⛔ Zugang gesperrt (total) — [Massiv-Name]` (Badge-Level 5 → G_DANGER/rot)
   - → **AC-1 muss umformuliert werden:** Nachweis-Schwelle Niveau ≥3 statt ≥2; heute liegen mehrere
     Var-Massive (u.a. Maures 835, Haut Var 833, Centre Var 836) auf Niveau 3 → live erfüllbar.
2. **06 Alpes-Maritimes bleibt im Scope, fail-soft leer:** `MASSIF_ZONES["06"] = []` (leer, da kein
   Live-Feed). `covers()` liefert True (Key vorhanden), `fetch()` erhält 404 → `[]`. Forward-kompatibel,
   sobald der Endpoint 06 bedient. Kein Badge heute, kein Fehler.

### Technischer Ansatz (Tech-Lead-Empfehlung)
- **`massif_zones.py`:** `MassifZone(massif_id: str, name: str, center_lat, center_lon, radius_km)` +
  `MASSIF_ZONES: dict[str, list[MassifZone]]`, **keyed by Source-DEPT** (`"83"`, `"13"`, `"20"`, `"06"`).
  - Var (83): 9 Massive aus amtlicher Seite kuratiert (831 MONTS TOULONNAIS … 835 MAURES … 838 ESTEREL,
    839 ILES D'HYÈRES). Zentrum-Koordinaten von Hand, `radius_km` grob.
  - Bouches-du-Rhône (13): benötigte Teilmenge der 27 Massive (MVP: nur was PO-Orte abdecken).
  - Korsika (20): benötigte Teilmenge der 11 Massive.
  - 06: `[]` (Platzhalter, forward-compat).
  - Helper `_dept_to_source(code)`: `"2A"/"2B" → "20"`, sonst Identität (Mapping-Tabelle, **kein**
    Sonderfall-Zweig → wahrt Generizität).
- **`massif_closure.py`:** `MassifClosureSource` implementiert `OfficialAlertSource`:
  - `covers(lat,lon)`: `src = _dept_to_source(lookup_department(lat,lon))`; True nur wenn `src in MASSIF_ZONES`.
  - `fetch(lat,lon)`: src ermitteln → Tages-JSON `static/{src}/import_data/{YYYYMMDD}.json` laden
    (pro-Source-DEPT Modul-Cache, TTL 300s/60s wie meteo_forets) → nächstes Massiv in
    `MASSIF_ZONES[src]` innerhalb `radius_km` (euklidisch) → `niveau_j1 = massifs[id][0]` →
    ab Niveau ≥3 `OfficialAlert(source="massif_closure", hazard="access_ban", level=niveau, label=…)`.
  - Defensiv: fehlendes `massifs`-Feld / kaputte Struktur → Warnung loggen, `[]`.
  - Monitoring: Modul-Level `_STATUS` dict (`last_run`, `last_error`, `error_count`).
- **`__init__.py`:** `register_official_alert_source(MassifClosureSource())`.
- **Renderer:** **keine Änderung nötig** — `comparison.py:419` (Text) + `compare_html.py:144`
  (`_render_official_alerts_block`) iterieren `official_alerts` generisch; `label` + `level` tragen alles.
  (Der im Issue genannte „comparison_renderers.py" existiert nicht; generische Renderer decken es ab.)

### Affected Files
| File | Change | Description |
|---|---|---|
| `src/services/official_alerts/massif_zones.py` | CREATE | `MassifZone`, `MASSIF_ZONES`, `_dept_to_source` |
| `src/services/official_alerts/massif_closure.py` | CREATE | `MassifClosureSource` (covers/fetch/cache/status) |
| `src/services/official_alerts/__init__.py` | MODIFY | Quelle registrieren |
| `tests/tdd/test_issue_1037_*.py` | CREATE | AC-Tests (echter Live-Call, kein Mock) |

### Scope Assessment
- Files: 3 Code (2 neu, 1 geändert) + 1 Testdatei
- Est. LoC: ~200-250 (Zonen-Tabelle dominiert) — evtl. `loc_limit_override` mit PO
- Risk: MEDIUM (undokumentierter Endpoint, statische Zonen-Näherung; aber additiv + fail-soft)

### Dependencies
Upstream: `department_mapper.lookup_department`, `models.OfficialAlert`, `base.register_official_alert_source`,
`httpx`, `radar_service`-Bounding-Box. Downstream: `comparison_engine` (Registry-Konsument), Renderer (generisch).

### Open Questions
Keine offen — PO-Entscheidungen getroffen. AC-1 wird in der Spec auf Niveau ≥3 umformuliert.
