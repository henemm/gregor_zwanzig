---
entity_id: official_alerts_massif_closure
type: module
created: 2026-07-06
updated: 2026-07-07
status: draft
version: "1.4"
tags: [compare, alerts, official-alerts]
---

# Official Alerts — Massiv-Betretungsverbote (Côte d'Azur / Korsika)

## Approval

- [x] Approved (PO 'go', 2026-07-07)

## Purpose

Dritte Quelle: Präfektur-Zugangssperren einzelner Wander-Massive bei akuter Waldbrandgefahr.
**Leitszenario:** Côte d'Azur — Départements Var (83), Alpes-Maritimes (06),
Bouches-du-Rhône (13). Korsika (2A/2B, GR20-Kontext) ist ein zweiter, gleichrangig
unterstützter Anwendungsfall über denselben Mechanismus. Feinste verfügbare Granularität der
drei Slices — laut PO hoher konkreter Urlaubs-Mehrwert im Var. Dritte Implementierungspriorität,
architektonisch der aufwendigste Slice.

## Source

- **File:** `src/services/official_alerts/massif_closure.py`, `massif_zones.py`
- **Identifier:** `MassifClosureSource`

> Datenquelle: kein offizielles API, aber stabiler undokumentierter JSON-Endpoint (live
> verifiziert 2026-07-06 für Var, PO-Beispiel `risque-prevention-incendie.fr/var/`):
> `https://www.risque-prevention-incendie.fr/static/{DEPT}/import_data/{YYYYMMDD}.json`
> (Var `DEPT=83`, Alpes-Maritimes `DEPT=06`, Bouches-du-Rhône `DEPT=13`, Korsika `DEPT=20` — ob
> Korsika weiterhin zusammengefasst oder bereits nach 2A/2B getrennt geführt wird, ist während
> der Implementierung gegen die Live-Antwort zu verifizieren). Struktur:
> `massifs[<massiv_id>] = [niveau_j1, niveau_j2]`, Niveau 1=grün…4/5=rot. Auth-frei. Lizenz
> unklar — kein Attribution-Zwang bekannt, aber Betriebsrisiko (Struktur kann sich ändern)
> mittel-hoch.

## Estimated Scope

- **LoC:** ~250
- **Files:** 4 (3 neu, 1 geändert — siehe Issue #1037)
- **Effort:** medium-high (obere Grenze durch Neu-Recherche für 3 zusätzliche Départements)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/base.py` (#1034) | Fundament | `OfficialAlertSource`-Protocol, Registry |
| `src/services/official_alerts/department_mapper.py` (#1035) | Wiederverwendung | landesweiter Koordinate → Département-Mapper, keine Neuentwicklung |
| Vorgänger-Projekt `gr20_zone_massif_ids.py` (nur Referenz, nur für Korsika-Daten) | Fachliche Datenquelle | liefert die Korsika-Einträge der generischen Zonen-Tabelle, ist aber NICHT die Architektur |
| Öffentliche Karte/JSON auf risque-prevention-incendie.fr | Neu-Recherche | Massiv-Namen/Zentren für Var/Alpes-Maritimes/Bouches-du-Rhône (kein Vorarbeit-Material vorhanden) |

## Architektur-Entscheidung 1+2 (2026-07-07, PO-Entscheidung nach Adversary Runde 2): Exakte amtliche Polygone, Point-in-Polygon zur Laufzeit

**Historie:** Ursprünglich (v1.0–1.3) war eine Zentrum+Radius-Näherung gewählt, um keine
FlatGeobuf-Laufzeit-Abhängigkeit einzuführen. Zwei Adversary-Runden haben bewiesen, dass diese
Näherung **aktiv falsch informiert**: falsch geratene Massiv-IDs für 13/20 (F004) und
Radius-Fehlzuordnung an Küsten (F005: „Zugang eingeschränkt — Maures" für einen Ort, dessen echtes
Massiv offen ist). Für ein Entscheidungswerkzeug inakzeptabel. **PO-Entscheidung: exakte amtliche
Massiv-Grenzen verwenden, alle drei Regionen (Var/Bouches-du-Rhône/Korsika).**

### Keine neue Laufzeit-Abhängigkeit
- **Offline, einmalig während der Implementierung:** Die amtlichen Polygon-Dateien
  `https://www.risque-prevention-incendie.fr/static/{DEPT}/massifs_{DEPT}.fgb` (DEPT 83/13/20)
  werden mit einem Wegwerf-Werkzeug (z. B. `ogr2ogr` oder `flatgeobuf`+`shapely` in einer
  Scratch-venv **außerhalb** der Produktions-Codebasis) nach GeoJSON konvertiert, vereinfacht
  (Douglas-Peucker, grobe Toleranz — Massiv-Grenzen brauchen keine Meter-Präzision) und als
  **gebündelte statische Datendatei** ins Repo gelegt.
- **Zur Laufzeit** liest die Anwendung nur diese gebündelten Polygone und prüft die Zugehörigkeit
  per **reinem Python-Ray-Casting** (~15 Zeilen, Standardlib) — **kein** FlatGeobuf-Parser, **keine**
  Geometrie-Bibliothek, keine neue `pyproject`-Abhängigkeit. Konform zur Projektregel „keine neuen
  Dependencies ohne Freigabe".

### Datenstruktur
- **Gebündelte Polygon-Daten** (generierte Datendatei, z. B. `massif_polygons.json` oder als
  Konstante in `massif_zones.py`): pro Massiv `{"src": "83", "massif_id": "835",
  "name": "MAURES", "rings": [[[lat,lon],...]]}`. `massif_id` und `name` stammen **direkt aus den
  amtlichen `.fgb`-Properties** (nicht geraten) und werden gegen die Live-JSON-Keys verifiziert.
- **Generizität:** kein Sonderfall-Zweig für Korsika/Côte d'Azur. Korsika liegt unter `src="20"`;
  `src` bestimmt die Fetch-URL des Tages-JSON.

### Matching
```python
class MassifClosureSource:
    name = "massif_closure"

    def covers(self, lat, lon) -> bool:
        return _massif_at(lat, lon) is not None   # Point-in-Polygon über alle gebündelten Massive

    def fetch(self, lat, lon) -> list[OfficialAlert]:
        hit = _massif_at(lat, lon)                 # -> Polygon-Eintrag (src, massif_id, name) | None
        if hit is None:
            return []
        data = _load_cached_daily_json(hit.src)    # Tages-Cache pro Source-DEPT
        return _extract_alert(data, hit)           # Struktur-/Shape-Guard (F001), niveau_j1 -> Alert
```

- `_massif_at(lat, lon)`: prüft den Punkt gegen die Polygone (Ray-Casting). Liegt der Punkt in
  mehreren (Überlappung praktisch keine, aber defensiv): erstes/kleinstes Polygon. Kein
  `department_mapper`, keine Radius-Näherung, keine Fehlzuordnung an Grenzen.
- **06 Alpes-Maritimes:** keine Polygone (Endpoint 404) → Orte dort matchen nur ein 83-Grenzmassiv,
  falls sie geografisch darin liegen; sonst kein Badge (fail-soft, forward-compat).
- **Fail-soft für Orte außerhalb aller Massiv-Polygone:** kein Badge, kein Fehler.

**Monitoring:** leichtgewichtiger Modul-Level-Status (letzter erfolgreicher Fetch, letzter
Fehler) in `massif_closure.py` — Projektregel "kein Job ohne Observability".

## Architektur-Entscheidung 3 (PO 2026-07-07): Niveau→Badge-Abstufung, faktisch korrekt

Die amtliche Legende (verifiziert gegen `risque-prevention-incendie.fr/var/`) definiert eine
5-stufige Skala mit **echten Zugangsregeln** — „gesperrt" (accès interdit) gilt erst ab Niveau 4:

| Niveau | Farbe | Amtliche Regel | Zugang | Badge |
|---|---|---|---|---|
| 1 | vert | Accès et travaux autorisés | erlaubt | **kein Badge** |
| 2 | jaune | Accès autorisé (travaux mit Auflagen) | erlaubt | **kein Badge** |
| 3 | orange | Accès **déconseillé**, travaux interdits | abgeraten | `⚠️ Zugang eingeschränkt — [Massiv]` |
| 4 | rouge | Accès **interdit** hors ZAPEF | gesperrt | `⛔ Zugang gesperrt — [Massiv]` |
| 5 | noir | Accès et travaux interdits (tous massifs) | gesperrt (total) | `⛔ Zugang gesperrt (total) — [Massiv]` |

`_niveau_to_alert(niveau, name)` liefert:
- Niveau < 3 → `None` (kein Alert — Zugang amtlich erlaubt; „Zugang gesperrt" wäre für einen
  Wanderer irreführend).
- Niveau 3 → `OfficialAlert(source="massif_closure", hazard="access_ban", level=3,
  label="Zugang eingeschränkt — {name}")` → Badge-Farbe G_WARNING (orange).
- Niveau 4 → `level=4, label="Zugang gesperrt — {name}"` → Badge-Farbe G_DANGER (rot).
- Niveau ≥5 → `level=5, label="Zugang gesperrt (total) — {name}"` → G_DANGER (rot).

Das `level`-Feld steuert direkt die bestehende Badge-Farblogik in `compare_html.py`
(`_render_official_alerts_block`: 1-2→SUCCESS, 3→WARNING, 4+→DANGER) — keine Renderer-Änderung
nötig.

## Endpoint-Realität (verifiziert 2026-07-07, echte curl-Calls)

`https://www.risque-prevention-incendie.fr/static/{SRC}/import_data/{YYYYMMDD}.json` (auth-frei),
Struktur `{"massifs": {"<id>": [niveau_j1, niveau_j2]}, "zm": {...}}`:

| Source-DEPT | HTTP | Massive | Befund |
|---|---|---|---|
| 83 Var | 200 | 9 | J1-Level heute bis 3 → AC-1 live erfüllbar |
| 13 Bouches-du-Rhône | 200 | 27 | verfügbar |
| 20 Korsika (kombiniert) | 200 | 11 | verfügbar; `2A`/`2B` als eigene Codes = 404 |
| 06 Alpes-Maritimes | **404** | — | Endpoint liefert 06 NICHT → keine 06-Polygone, fail-soft |

## Renderer-Integration (KEINE Änderung nötig)

Text-Renderer (`src/output/renderers/comparison.py`) und HTML-Renderer
(`src/output/renderers/email/compare_html.py::_render_official_alerts_block`) iterieren bereits
**generisch** über `LocationResult.official_alerts` und geben `label` aus bzw. mappen `level` auf
die Badge-Farbe. Der Massiv-Badge erscheint automatisch, sobald `MassifClosureSource` einen
`OfficialAlert` liefert. Der im Issue-Text genannte `comparison_renderers.py` existiert nicht;
die tatsächlich betroffene geänderte Datei ist ausschließlich `__init__.py` (Registrierung).

## Expected Behavior

- **Input:** Lat/Lon eines Ortes.
- **Output:** Liste mit maximal einem `OfficialAlert(hazard="access_ban")` pro Ort, wenn der Ort
  in einem unterstützten Source-DEPT liegt, dort ein kuratiertes Massiv in Reichweite liegt und
  für dieses Massiv aktuell **Niveau ≥3** (J1) gemeldet ist; leer sonst (inkl. Niveau 1-2 = Zugang
  erlaubt).
- **Side effects:** HTTP-Call gegen den Tages-JSON-Endpoint des ermittelten Source-DEPT (mit
  Tages-Cache pro Source-DEPT, um nicht bei jedem Compare-Lauf neu zu laden).

## Acceptance Criteria

- **AC-1:** Given ein **realer Wander-/Ortspunkt im Var** nahe eines kuratierten Massivs (echte
  Koordinaten eines Trailheads/Orts, NICHT das Zonen-Zentrum selbst), dessen abdeckendes Massiv im
  Live-JSON aktuell Niveau ≥3 hat (im Juli realistisch, z. B. Maures/Estérel/Centre Var), When die
  Compare-Mail generiert wird, Then liefert `covers()` für diesen realen Punkt True und die Mail
  zeigt den niveau-abgestuften Badge: bei Niveau 3 „Zugang eingeschränkt — [Massiv-Name]", bei
  Niveau ≥4 „Zugang gesperrt — [Massiv-Name]".
  - Test: echter Call gegen den Live-Endpoint für DEPT=83, kein Mock; reale Ortskoordinaten (kein
    `zone.center`), das zum Testzeitpunkt auf höchstem Niveau (≥3) stehende kuratierte Massiv über
    einen realen zugehörigen Punkt ansprechen, Compare-Mail-HTML auf den passenden Badge-Text
    prüfen. (Falls zum Testzeitpunkt kein Var-Massiv ≥3 ist — im Juli sehr unwahrscheinlich —,
    greift die dokumentierte Known Limitation zur Live-Abhängigkeit.)

- **AC-2:** Given ein **realer Ortspunkt auf Korsika** innerhalb eines amtlichen Massiv-Polygons,
  When `MassifClosureSource` ihn verarbeitet, Then läuft **derselbe Code-Pfad wie für den Var-Ort in
  AC-1** (dasselbe Point-in-Polygon, kein Korsika-Sonderfall-Zweig): `covers()` liefert True,
  `fetch()` ermittelt aus dem getroffenen Polygon den Source-DEPT „20", ruft den echten Live-Endpoint
  für DEPT=20 auf und erzeugt bei Niveau ≥3 einen identisch formatierten Badge.
  - Test: `covers()` für eine reale Korsika-Koordinate innerhalb eines Massiv-Polygons = True;
    `fetch()` gegen den echten DEPT=20-Endpoint (kein Mock) läuft ohne Verzweigung durch dieselben
    Funktionen wie Var; die zurückgegebene `massif_id`/`name` stammen aus den amtlichen
    Polygon-Properties (Attribution korrekt); Badge, falls das Massiv aktuell ≥3 ist, sonst leer.

- **AC-3:** Given ein Ort außerhalb aller amtlichen Massiv-Polygone (z. B. Paris, oder Marseille-
  Innenstadt), When `get_official_alerts_for_location()` aufgerufen wird, Then liefert
  `MassifClosureSource` keinen Badge (`covers()` = False).
  - Test: `covers()` mit Paris-Koordinaten aufrufen, `False` erwarten.

- **AC-4:** Given der JSON-Endpoint liefert eine unerwartete/fehlerhafte Struktur (z. B.
  fehlendes `massifs`-Feld oder ein `niveau`-Wert, der keine `[int, int]`-Liste ist), When
  `fetch()`/`_extract_alert()` aufgerufen wird, Then wird eine Warnung geloggt und `[]`
  zurückgegeben, kein Absturz der Compare-Mail-Generierung.
  - Test: die echte `_extract_alert()`-Funktion gegen kaputte Struktur- UND Value-Shape-Werte
    aufrufen (fehlendes `massifs`, int statt Liste, leere Liste, `[None,None]`, `["3","3"]`,
    `massifs` als Liste) — kein Mock; jeweils `[]` + Log-Eintrag prüfen.

- **AC-5 (Attributions-Korrektheit, neu nach Adversary Runde 2):** Given reale, unabhängig gewählte
  Orte, deren echtes amtliches Massiv bekannt ist (z. B. Le Lavandou → Corniche des Maures,
  Vauvenargues → Sainte-Victoire, Saint-Tropez → Corniche des Maures), When `fetch()` aufgerufen
  wird, Then wird — sofern ein Badge erscheint — der **korrekte** Massiv-Name gezeigt (der des
  Polygons, in dem der Ort liegt), nicht der eines benachbarten/entfernten Massivs; und der Sperrwert
  stammt vom `massif_id` genau dieses Polygons.
  - Test: für jeden Referenzort `_massif_at()` == erwartetes Massiv; `covers()` == True; gegen die
    amtliche Polygon-Zugehörigkeit (Point-in-Polygon) geprüft. Deckt die Adversary-Findings
    F004/F005/F006 ab.

## Known Limitations

- **Alpes-Maritimes (06) liefert keine Live-Daten:** Der Endpoint antwortet für DEPT=06 mit HTTP
  404 (verifiziert 2026-07-07). Keine 06-Polygone gebündelt — Orte im 06 erhalten fail-soft keinen
  Badge (kein Fehler), forward-kompatibel falls der Endpoint 06 später bedient. Grenz-Orte, die
  geografisch in einem 83-Massiv-Polygon liegen (z. B. am Estérel), matchen dieses korrekt.
- **Korsika wird als kombiniertes „20" geführt**, nicht getrennt nach 2A/2B (die Einzel-Codes
  liefern 404). Die Korsika-Polygone tragen `src="20"`.
- **Badge erst ab Niveau ≥3:** Niveau 1-2 bedeuten amtlich „Zugang erlaubt" und erzeugen bewusst
  keinen Badge. „Zugang gesperrt" (Text) erscheint erst ab Niveau 4 (amtlich „accès interdit");
  Niveau 3 = „Zugang eingeschränkt". Das weicht bewusst vom ursprünglichen Issue-AC (≥2 = gesperrt)
  ab, um faktisch korrekt zu sein (PO-Entscheidung 2026-07-07).
- **AC-1/AC-2 sind live-abhängig:** Ob ein Badge erscheint, hängt vom tagesaktuellen Niveau ab. Im
  Juli sind Var-Massive regelmäßig ≥3 (AC-1 erfüllbar); Korsika kann tagesweise komplett auf Niveau
  1 stehen — AC-2 weist dann die Pfad-Generizität + korrekte Attribution nach, nicht zwingend einen
  Live-Badge. AC-5 (Attribution) ist dagegen live-unabhängig.
- **Polygone sind vereinfacht** (Douglas-Peucker, grobe Toleranz zur Dateigrößen-Reduktion) — an den
  Rändern (wenige Meter/Dutzende Meter) kann die Zugehörigkeit minimal von der amtlichen Grenze
  abweichen. Praktisch irrelevant für Ortszentren/Trailheads; für den MVP akzeptiert.
- **Nur die drei bereitgestellten Départements** (83/13/20) sind gebündelt. Weitere Regionen sind
  inkrementell nachrüstbar, indem ihre Polygone ergänzt werden — der Mechanismus ändert sich nicht.
- **Korsika-Abdeckung ist eine Quellen-Limitation (F008):** Das amtliche Tages-JSON für DEPT=20
  meldet nur **11** Massive (jene unter aktivem Restriktionsregime, `procedure!=0`) — verifiziert
  2026-07-07: gebündelte 11 IDs == Tages-JSON-Keys. Reale GR20-Kernorte in nicht gemeldeten
  Massiven (z. B. Vizzavona, Asco, Restonica-Tavignano) liefern daher `covers()=False`/keinen Badge
  — nicht wegen unserer Kuration, sondern weil die Quelle für diese Massive **keine** Sperrdaten
  bereitstellt. Sobald die Quelle sie meldet, sind ihre Polygone additiv nachrüstbar.
- **Département-übergreifende Massiv-Dopplung (F009):** Einzelne Bergketten (z. B. Sainte-Baume)
  werden von zwei Départements (83 und 13) unabhängig geführt, ggf. mit unterschiedlichem
  Tagesniveau. `fetch()` wertet **alle** Polygone aus, in denen der Punkt liegt (`massifs_at`), und
  liefert die **strengste** Sperrstufe (höchstes Niveau) — sicherste Information für den Wanderer.
- **Fail-soft bei fehlender/kaputter Polygon-Datei (F007):** `_load_massifs()` fängt Lade-/Parse-
  Fehler ab → `MASSIFS=[]` (Massiv-Sperren stumm deaktiviert), und der Registry-Aufruf in
  `comparison_engine` ist zusätzlich in `try/except` gekapselt — ein Datei-Problem legt weder die
  anderen Alert-Quellen noch die Compare-Mail lahm.
- Massiv-Grenzen können sich amtlich ändern, ohne dass die gebündelten Polygone automatisch
  nachziehen — jährliche Stichprobe vor der Sommersaison empfohlen (Betriebs-Playbook-Notiz).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0016 (siehe #1034 für Details zum übergeordneten additiven Alert-Typ)
- **Rationale:** Die FlatGeobuf-Abweichung und die Département-Generizität sind slice-lokale
  Scoping-/Architektur-Entscheidungen (Dependency-Vermeidung, Vermeidung einer
  GR20-Hartkodierung angesichts des jetzt primären Côte-d'Azur-Szenarios), keine eigene
  ADR-würdige Grundsatzfrage — dokumentiert hier und im Epic-Feature-Dokument
  (`docs/features/epic-1033-compare-official-alerts.md`).

## Changelog

- 2026-07-06: Initial spec created (Epic #1033, Issue #1037)
- 2026-07-06: Scope-Korrektur (PO): Côte d'Azur (Var/Alpes-Maritimes/Bouches-du-Rhône) als
  primäres Leitszenario, Mechanismus auf generischen Département-Lookup umgestellt
  (`MASSIF_ZONES` statt GR20-hartkodierter `massif_ids.py`), Korsika-Daten aus dem
  Vorgängerprojekt sind nur noch Dateninhalt, nicht Architektur.
- 2026-07-06: Präzisierung: AC-1 mit konkretem Var-Beispiel (Massif des Maures/Estérel,
  Juli-Plausibilität Niveau ≥2), FlatGeobuf-Nutzung als einmalige Offline-Ableitung (kein
  Laufzeit-Parser) explizit dokumentiert.
- 2026-07-07 (v1.4, nach Adversary Runde 2 BROKEN + PO-Entscheidung „echte Grenzen, alle 3
  Regionen"): **Umstieg von Zentrum+Radius-Näherung auf exakte amtliche Polygone** mit
  Point-in-Polygon zur Laufzeit (gebündelte, offline aus den amtlichen `.fgb` erzeugte GeoJSON-
  Polygone + reines Python-Ray-Casting; KEINE neue Laufzeit-Abhängigkeit). Behebt F004 (falsch
  geratene IDs für 13/20 — Namen/IDs kommen jetzt direkt aus den Polygon-Properties), F005
  (Radius-Fehlzuordnung an Küsten) und F006 (Fall-through). Neu: **AC-5 Attributions-Korrektheit**
  gegen reale Referenzorte. `MassifZone`/`MASSIF_ZONES`/`_nearest_zone_pooled` werden durch die
  Polygon-Struktur + `_massif_at()` ersetzt.
- 2026-07-07 (v1.3, nach Adversary Runde 1 BROKEN): Matching auf **gepoolte Radius-Suche**
  umgestellt (kein `department_mapper`-Gate mehr) — behebt F002 (reale Grenz-Orte wie
  Estérel/Draguignan wurden fehlgeroutet und bekamen keinen Badge). Zonen-Zentren = echte
  Massiv-Geografie statt künstlich Richtung Präfektur verschoben. `_extract_alert` härtet die
  Value-Shape (F001). Îles-d'Hyères-Radius vergrößert (F003). AC-1/AC-2-Tests auf **reale
  Nutzer-Koordinaten** verschärft (nicht mehr selbstreferenziell auf `zone.center`).
- 2026-07-07 (v1.2, nach Live-Endpoint-Verifikation + PO-Entscheidungen):
  - **MASSIF_ZONES keyed by Source-DEPT** („83"/„13"/„20"/„06"); `_dept_to_source` bildet Korsika
    2A/2B → „20" ab (Endpoint führt Korsika kombiniert; 2A/2B einzeln = 404).
  - **06 fail-soft leer:** Endpoint liefert 06 nicht (404) → `MASSIF_ZONES["06"]=[]`, forward-compat.
  - **Niveau→Badge-Abstufung (AC 3):** Badge erst ab Niveau ≥3; 3=„Zugang eingeschränkt",
    4=„Zugang gesperrt", 5=„Zugang gesperrt (total)". AC-1 entsprechend auf Niveau ≥3 umformuliert
    (statt ≥2), faktisch korrekt gegenüber der amtlichen Zugangs-Legende.
  - **AC-2 auf Pfad-Generizität geschärft** (live-Niveau-unabhängig testbar).
  - **Renderer-Klarstellung:** keine Renderer-Änderung nötig (generische Iteration); einzig
    geänderte Datei ist `__init__.py` (Registrierung). `comparison_renderers.py` aus dem Issue-Text
    existiert nicht.
  - **Kein Vorarbeit-Material:** `gr20_zone_massif_ids.py` ist nicht im Repo; auch Korsika neu kuratiert.
