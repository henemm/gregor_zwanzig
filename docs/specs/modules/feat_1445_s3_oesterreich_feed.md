---
entity_id: feat_1445_s3_oesterreich_feed
type: feature
created: 2026-08-01
updated: 2026-08-01
status: draft
version: "1.0"
tags: [official-alerts, meteoalarm, warn-egress, quota, austria]
workflow: feat-1445-s3-oesterreich-feed
---

<!-- Issue #1445 -->

# MeteoAlarm Österreich: Auffrischung aus dem kontingentfreien öffentlichen Feed (Scheibe S3)

## Approval

- [ ] Approved

## Purpose

Österreich ist mit 17–21 EDR-Indexseiten je Auffrischung (gegen 3 für Italien) der
Hauptverbraucher des täglich schrumpfenden `api.meteoalarm.org`-Kontingents
(`docs/context/fix-1397-wiederanlauf-ausbruch.md`). Scheibe S1 hat den Weg für Italien
bereits auf den kontingentfreien öffentlichen Feed umgestellt und den EDR-Loop in
`meteoalarm.py` auf `("AT",)` verengt — Österreich blieb dort bewusst ausgespart
(Folge-Scheibe). Diese Scheibe schließt die Lücke: Österreich bezieht amtliche Warnungen
künftig ebenfalls aus `https://feeds.meteoalarm.org/api/v1/warnings/feeds-austria` statt
aus dem EDR-Index — die Punkt→Zone-Auflösung nutzt dabei eine bereits vorhandene, ohnehin
gecachte ZAMG-Antwort (`geosphere_warn._get_cached_warnings()`) weiter, kostet also **keinen
zusätzlichen Netzabruf**. Nach dieser Scheibe fällt der Zugriff auf den gesperrten Host für
beide Länder auf **null** — der eigentliche Verbrauchs-Entlastungseffekt für #1397, den S1
allein noch nicht erreicht hat.

## Source

- **File:** `src/services/official_alerts/meteoalarm_feed.py` (MODIFY — Land-Parameter)
- **Identifier:** `MeteoAlarmFeedSource.__init__(country)`, `_zone_for_point_at`, `_covers_at`,
  `_FEED_PATHS`

> **Schicht-Hinweis:** Ausschließlich Python-Core (`src/services/official_alerts/`). Kein Go-,
> kein Frontend-Anteil. Kein Eingriff in `internal/scheduler/`.

## Estimated Scope

- **LoC:** ~180–230 (Produktivcode + Test-Anpassungen, ohne diese Spec) — **erneut eng am
  250er-Limit**, obwohl der teuerste Teil von S1 (CAP-Mapper-Trennung) bereits erledigt und
  wiederverwendbar ist. Treiber diesmal: die österreichische Zonenauflösung braucht — anders
  als Italiens reine `Optional[str]`-Rückgabe — eine echte Drei-Zustands-Unterscheidung (s.
  Implementation Details Punkt 2), das ist neuer, nicht wiederverwendbarer Code. Sollte der
  tatsächliche Diff das Limit überschreiten, wird die AT-Zonenauflösung als eigene
  Vorab-Scheibe `S3a` (reine Hilfsfunktion + deren Tests, kein Verhaltensunterschied am
  bestehenden `geosphere_warn`-Pfad) ausgekoppelt.
- **Files:** 7 (2 geänderte Python-Quellen, 1 nahezu unveränderte Python-Quelle nur mit
  Dormant-Hinweis, 1 neue Testdatei, 2 neue Fixture-Dateien, 1 erweiterte Fixture-Dokumentation)
- **Effort:** medium-high (Drei-Zustands-Unterscheidung ist die sicherheitskritische Neuerung
  dieser Scheibe, s. Purpose der Aufgabenstellung)

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/official_alerts/meteoalarm_feed.py` | MODIFY | `MeteoAlarmFeedSource` bekommt einen Konstruktor-Parameter `country: Literal["IT", "AT"]`; `_FEED_PATHS` löst `feeds-italy`/`feeds-austria` auf; `covers()` verzweigt auf den bestehenden DPC-Bbox-Weg (IT) oder einen neuen INCA-Bbox-Weg (AT, analog `GeoSphereWarnSource.covers()`); `fetch()` ruft je nach Land `_zone_for_point` (IT, unverändert) oder `_zone_for_point_at` (AT, neu) auf und wertet deren unterschiedliches Rückgabe-Kontrakt aus (s. Implementation Details Punkt 2); der gemeinsame Malformations-/Reihenfolge-Schutz (F003/F005 aus S1) bleibt für beide Länder ein einziger Codepfad |
| `src/services/official_alerts/__init__.py` | MODIFY | `register_official_alert_source(MeteoAlarmSource())` entfällt (EDR-Apparat wird nicht mehr aufgerufen, Randbedingung "kein Parallelbetrieb"); `MeteoAlarmFeedSource()` wird zu zwei Instanzen `MeteoAlarmFeedSource("IT")` und `MeteoAlarmFeedSource("AT")`; `MeteoAlarmSource`-Import/`__all__`-Eintrag entfällt aus der öffentlichen Registry-Oberfläche (Klasse bleibt über ihren eigenen Modulpfad erreichbar) |
| `src/services/official_alerts/meteoalarm.py` | MODIFY | Nur ein Dormant-Hinweis im Klassen-Docstring von `MeteoAlarmSource` ("seit #1445 S3 nicht mehr registriert, Code bleibt für den Äquivalenznachweis erhalten") — **kein Verhaltens-Code entfernt**, siehe Randbedingung "EDR-Apparat wird NICHT zurückgebaut" |
| `tests/tdd/test_meteoalarm_feed_oesterreich.py` | CREATE | Fetch-Mapping AT, Drei-Zustands-Unterscheidung, Verbrauchsdisziplin (inkl. Null-Zusatzabrufe gegen ZAMG), Äquivalenznachweis, Isolation |
| `tests/fixtures/meteoalarm_feed/feed_austria_sample.json` | CREATE | Kuratierter Ausschnitt (reale, unveränderte Einträge) aus dem AT-Feed, analog `feed_italy_sample.json` |
| `tests/fixtures/meteoalarm_feed/edr_snapshot_at.json` | CREATE | Zur selben Minute aufgezeichneter EDR-Ausschnitt (AT) für den Äquivalenztest — **Pflicht-Gate, s. Test Plan zur Zeitfenster-Abhängigkeit** |
| `tests/fixtures/meteoalarm_feed/zamg_snapshot_at.json` | CREATE | Adversary-Fund F2 (S3 Fix-Loop): dritte, zur SELBEN Minute wie `edr_snapshot_at.json` gezogene Aufzeichnung — die echte ZAMG-Antwort je Tourpunkt, damit `test_ac5_...` über `_ZamgServer` läuft statt gegen das echte `warnungen.zamg.at` — **ebenfalls Teil des AC-5-Pflicht-Gates** |
| `tests/fixtures/meteoalarm_feed/README.md` | MODIFY | Abschnitt für die neuen AT-Fixtures, analog dem bestehenden IT-Abschnitt |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.official_alerts.warn_egress.cached_fetch` | module | Einziger erlaubter Abrufweg für den AT-Feed, wie bereits für IT (S1) |
| `services.official_alerts.warn_egress.log_zone_drift` / `mark_fetch_incomplete` | module | Wiederverwendeter Diagnose-/Ausfall-Kanal (aus #1434), jetzt zusätzlich für die AT-Drei-Zustands-Logik genutzt |
| `services.official_alerts.geosphere_warn._get_cached_warnings` (`geosphere_warn.py:69-104`) | module | **Zentrale Wiederverwendung dieser Scheibe:** liefert die bereits gecachte, koordinaten-scoped ZAMG-Antwort inkl. `gemeindenr` — kein eigener Netzabruf. Funktioniert nur, solange `GeoSphereWarnSource` VOR `MeteoAlarmFeedSource("AT")` in der Registry-Reihenfolge steht (s. Known Limitations) |
| `services.radar_service._INCA_LAT_MIN/_MAX/_LON_MIN/_MAX` | module | AT-Bbox-Vorfilter für `covers()`, bereits von `GeoSphereWarnSource` und `MeteoAlarmSource` verwendet — keine neue Konstante |
| `services.official_alerts.meteoalarm._group_and_map_info_entries` | module | Geteilte, formatunabhängige Mapper-Hälfte aus S1 — unverändert, jetzt für beide Länder über denselben JSON-Sammelweg genutzt |
| `services.official_alerts.meteoalarm.MeteoAlarmSource` | module | Bleibt Code, wird aber NICHT mehr registriert (Randbedingung "kein Parallelbetrieb") — dient nur noch der Äquivalenzaufnahme (einmaliger Vergleichsabruf außerhalb des Produktivpfads) |
| `services.official_alerts.base.get_official_alerts_with_status` (`base.py:90-146`) | module | Wertet `unavailable` weiterhin aus `covering`/`failed` über ALLE registrierten Quellen für denselben Punkt ab — Grund für AC-8 (Isolation an der AT/IT-Grenze) |
| `data/diagnostics/warn_service_calls.jsonl` | data | Nachweisquelle für AC-4 (kein Eintrag mit `host=api.meteoalarm.org` für AT nach dieser Scheibe) |
| `docs/context/fix-1397-wiederanlauf-ausbruch.md` | reference | Vollständige Analyse; diese Spec entspricht der dortigen Scheibe S3 |
| `docs/specs/modules/feat_1445_s1_feed_bestandsquelle.md` | spec | Schwesterscheibe Italien — S3 folgt derselben Bauart, referenziert dieselben Adversary-Lehren (F001/F003/F005) |
| `docs/specs/_archive/modules/issue_1085_geosphere_warn_source.md` | spec | Ursprüngliche `GeoSphereWarnSource`-Spec, dort dokumentiertes, akzeptiertes Restrisiko F002 (404-Cache kann einen echten ZAMG-Ausfall maskieren) — von dieser Scheibe geerbt, nicht neu eingeführt (s. Known Limitations) |
| `docs/specs/modules/fix_1397_meteoalarm_coverage_budget.md` | spec | Bisheriger EDR-Verbrauchsmechanismus — nach dieser Scheibe für AT nicht mehr aufgerufen, Mechanismus selbst bleibt Code |
| `docs/artifacts/feat-1445-s1-feed-bestandsquelle/adversary-dialog.md` | reference | Fünf Findings aus S1 (F001–F005) — Randbedingung dieser Scheibe: keines davon darf sich für AT wiederholen |

## Implementation Details

1. **Land-Parameter statt zweiter Klasse:** `MeteoAlarmFeedSource(country="IT"|"AT")` — ein
   Code, zwei Instanzen (`MeteoAlarmFeedSource("IT")`, `MeteoAlarmFeedSource("AT")`), analog
   dem im Projekt etablierten Muster "ein Code, Parameter statt Zwilling"
   (`context="route"|"vergleich"` im Frontend). `_FEED_PATHS = {"IT": "/api/v1/warnings/feeds-italy",
   "AT": "/api/v1/warnings/feeds-austria"}`, eigener Cache-Schlüssel je Land (wie bisher `_CACHE_KEY`,
   jetzt `country`-abhängig) — ein AT-Feed-Abruf und ein IT-Feed-Abruf bleiben zwei unabhängige
   Cache-Einträge, keine gegenseitige Invalidierung.

2. **Die zentrale Festlegung — Österreichs Zonenauflösung braucht drei Zustände, nicht zwei:**
   Italiens `_zone_for_point()` liefert `Optional[str]`, und `None` bedeutet dort in JEDEM Fall
   "unavailable" — das ist für Italien richtig, weil `_zone_at()` eine reine, lokale
   Geometrie-Berechnung ohne Netzabruf ist: ein Punkt außerhalb aller 187 DPC-Zonen (Küste,
   Lagune, See) liegt trotzdem innerhalb des italienischen Zuständigkeitsbereichs — es gibt nur
   keine passende Fläche in unseren Daten, und das ist ununterscheidbar von einem echten
   Ausfall, also der sichere Rückzug (S1 Implementation Details Punkt 4). Für Österreich gilt
   das NICHT: `geosphere_warn._get_cached_warnings()` liefert einen **dreiwertigen** Zustand
   über ihren Rückgabewert, der bereits alle nötige Information trägt:
   - `None` → der ZAMG-Abruf ist selbst fehlgeschlagen (Netzwerkfehler, Zeitüberschreitung,
     5xx) → **Fall 2, "ich weiß es nicht"** → `unavailable=True`.
   - ein Dict OHNE auswertbare `gemeindenr` (das schließt sowohl den echten
     „außerhalb Österreichs, ZAMG antwortet 404"-Fall als auch einen strukturell
     unerwartet leeren 200er ein, s. Known Limitations zur Ununterscheidbarkeit) →
     **Fall 1, "hier gelten keine österreichischen Warnungen"** → leere Liste, KEIN
     `mark_fetch_incomplete()`.
   - ein Dict MIT `gemeindenr` → EMMA-Zone = `"AT" + gemeindenr[:3]` (verifiziert:
     Villach 20201→AT202, Tamsweg 50510→AT505, Wien 90101→AT901, Graz 60101→AT601,
     Innsbruck 70101→AT701, Salzburg 50101→AT501, Bregenz 80207→AT802, Linz 40101→AT401,
     Eisenstadt 10101→AT101, Sankt Pölten 30201→AT302, Lienz 70716→AT707, Zell am See
     50628→AT506, Sillian/KHW 70728→AT707) → **Fall 3, normaler Betrieb**, weiter wie beim
     IT-Weg (Feed abrufen, `_group_and_map_info_entries` anwenden).

   `_zone_for_point_at(lat, lon)` liefert deshalb NICHT `Optional[str]`, sondern unterscheidet
   die drei Fälle explizit in ihrem Rückgabewert (z. B. ein Tupel `(zone: Optional[str],
   fetch_failed: bool)`), damit `fetch()` bei "Zone unbestimmbar, Netz aber ok" (Fall 1) NICHT
   denselben `mark_fetch_incomplete()`-Zweig auslöst wie bei "ZAMG-Abruf fehlgeschlagen"
   (Fall 2). Der gemeinsame Malformations-/Reihenfolge-Schutz im Feed-Auswerteteil von
   `fetch()` (F003/F005 aus S1, Zonenzugehörigkeit VOR Malformationsprüfung) bleibt für beide
   Länder EIN Codepfad — nur die Zuordnung "Punkt → EMMA-ID davor" ist länderspezifisch.

3. **Kein Kilometer-Rückfall, keine neue Geodatei für AT:** anders als bei Italien ist keine
   Präfix-Tabelle nötig — die EMMA-Ableitung ist eine reine Zeichenkettenoperation auf einem
   bereits vorhandenen Feld derselben, ohnehin abgerufenen Antwort.

4. **Null zusätzliche Netzabrufe — mit einer Reihenfolge-Abhängigkeit:** `_zone_for_point_at()`
   ruft `geosphere_warn._get_cached_warnings(lat, lon)` auf — denselben modul-globalen,
   30-Minuten-TTL-Cache, den `GeoSphereWarnSource.fetch()` für denselben Punkt ohnehin befüllt.
   Das funktioniert als "Null zusätzliche Abrufe" NUR, wenn `GeoSphereWarnSource` in der
   Registry-Reihenfolge VOR `MeteoAlarmFeedSource("AT")` steht (aktuell der Fall, s.
   `__init__.py`) — beide werden für denselben Punkt innerhalb desselben
   `get_official_alerts_with_status()`-Durchlaufs aufgerufen, sodass der zweite Aufruf immer
   einen Cache-Treffer auf denselben gerundeten Koordinaten vorfindet. Diese Kopplung wird als
   Kommentar an beiden Registrierungszeilen in `__init__.py` festgehalten (s. Known Limitations
   zur Zerbrechlichkeit dieser Ordnungsannahme).

5. **`covers()` für AT — INCA-Bbox, kein Département-Ausschluss nötig:** anders als bei Italiens
   `covers()` (DPC-Bbox + französischer Ausschluss, weil der IT-Bbox-Fehlgriff Randbedingung 3
   aus S1 auslösen konnte) braucht AT keinen analogen Ausschluss: Ein Grenzpunkt, der zwar
   innerhalb der INCA-Bbox, aber tatsächlich außerhalb Österreichs liegt, wird bereits über
   Fall 1 (ZAMG 404 → `not_covered_statuses`, KEIN `mark_fetch_incomplete()`) sauber als "nicht
   zuständig" behandelt — das feine Gatter läuft hier schon in `fetch()` selbst, nicht erst als
   separate bbox-Verfeinerung. Das ist der entscheidende strukturelle Unterschied zu Italiens
   EDR-Bbox-Problem aus S1 Implementation Details Punkt 7: dort hatte der EDR-Indexabruf KEIN
   Pro-Punkt-Signal für "nicht zuständig", hier hat er eines (der ZAMG-404-Weg).

6. **Registrierung:** `MeteoAlarmFeedSource("AT")` NACH `GeoSphereWarnSource()` (Punkt 4) UND
   NACH `MeteoAlarmFeedSource("IT")` (Konsistenz, keine funktionale Notwendigkeit), VOR
   `DpcSource()`. `MeteoAlarmSource` wird aus der Registrierungsliste entfernt — damit ist
   Randbedingung "kein dauerhafter Parallelbetrieb" (`base.py:146`) automatisch erfüllt, ohne
   `meteoalarm.py` selbst anfassen zu müssen: eine nicht registrierte Quelle zählt nirgends in
   `covering`/`failed` mit.

7. **`OfficialAlert.source` bleibt `"meteoalarm"`** für beide Länder (wie in S1 Punkt 8
   entschieden) — nur der interne Abrufweg ändert sich, bestehende Downstream-Verträge bleiben
   unberührt.

8. **LoC-Risiko explizit benannt (analog S1 Punkt 9):** Die Drei-Zustands-Logik aus Punkt 2 ist
   der einzige wirklich neue, nicht wiederverwendbare Teil dieser Scheibe. **Entscheidung für
   diese Spec:** bleibt Teil von S3, weil sie nicht sinnvoll isoliert werden kann, ohne die
   Sicherheits-Randbedingung (Fall 1 ≠ Fall 2) über zwei Scheiben zu verteilen. **Sollte der
   tatsächliche Diff beim Commit-Gate über das 250er-Limit treiben**, wird die AT-Zonenauflösung
   als eigene Vorab-Scheibe `S3a` ausgekoppelt (s. Estimated Scope).

## Expected Behavior

- **Input:** Koordinate eines beobachteten Orts in Österreich.
- **Output:** unverändert `list[OfficialAlert]` über `get_official_alerts_for_location()` /
  `get_official_alerts_with_status()` — jetzt gespeist aus dem öffentlichen Feed statt dem
  kontingentierten EDR-Index, mit Zonenauflösung über die bereits gecachte ZAMG-Antwort.
- **Side effects:** Netz-Abrufe gegen `api.meteoalarm.org` fallen für AT (und damit insgesamt,
  da IT bereits seit S1 auf null steht) auf null; ein Feed-Abruf je Auffrischungsfenster gegen
  `feeds.meteoalarm.org` (~2,4 MB); keine zusätzlichen Abrufe gegen `warnungen.zamg.at`
  (Wiederverwendung des `GeoSphereWarnSource`-Caches); zusätzliche Journal-Zeilen im
  bestehenden Diagnose-Kanal bei nicht auflösbaren bzw. fehlgeschlagenen Punkten.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1 (`tests/tdd/test_meteoalarm_feed_oesterreich.py`): GIVEN ein Punkt liegt
  innerhalb Österreichs UND die injizierte ZAMG-Antwort trägt keine `gemeindenr` (simuliert
  HTTP 404 über `not_covered_statuses`) WHEN die amtlichen Warnungen für diesen Punkt ermittelt
  werden THEN liefert das Ergebnis eine leere Liste UND `unavailable=False`.
- [ ] Test 2 (`tests/tdd/test_meteoalarm_feed_oesterreich.py`): GIVEN der injizierte
  ZAMG-Abruf schlägt fehl (Netzwerkfehler, kein 404) WHEN die amtlichen Warnungen für einen
  österreichischen Punkt ermittelt werden THEN liefert das Ergebnis `unavailable=True`.
- [ ] Test 3 (`tests/tdd/test_meteoalarm_feed_oesterreich.py`): GIVEN ZAMG liefert erfolgreich
  eine `gemeindenr`, deren abgeleitete EMMA-Zone im aktuellen Feed keine gültige Warnung trägt
  WHEN die amtlichen Warnungen für diesen Punkt ermittelt werden THEN liefert das Ergebnis eine
  leere Liste UND `unavailable=False`.
- [ ] Test 4 (`tests/tdd/test_meteoalarm_feed_oesterreich.py`): GIVEN mehrere österreichische
  Punkte werden innerhalb desselben Auffrischungsfensters abgefragt WHEN die amtlichen
  Warnungen ermittelt werden THEN löst höchstens ein echter Netzabruf gegen den AT-Feed dieses
  Fenster aus, UND kein einziger dieser Aufrufe erzeugt einen zusätzlichen echten Netzabruf
  gegen `warnungen.zamg.at` über das hinaus, was `GeoSphereWarnSource` ohnehin ausgelöst hätte,
  UND im Diagnose-Journal taucht kein Eintrag mit `host=api.meteoalarm.org` auf.
- [ ] Test 5 (`tests/tdd/test_meteoalarm_feed_oesterreich.py`, Äquivalenz-Pflicht-Gate): GIVEN
  die DREI zur selben Minute aufgezeichneten Fixtures (EDR-Ausschnitt AT, Feed-Ausschnitt AT,
  UND — Adversary-Fund F2, S3 Fix-Loop — ZAMG-Ausschnitt AT je Tourpunkt, damit der Test über
  `_ZamgServer` läuft statt gegen das echte `warnungen.zamg.at`) für eine Liste realer
  Tourpunkte inkl. des Karnischen Höhenwegs auf österreichischer Seite WHEN beide
  Ergebnismengen für dieselben Punkte gebildet werden THEN ist die Feed-Ergebnismenge eine
  Obermenge der EDR-Ergebnismenge. Fehlt eine der drei Aufzeichnungen, bleibt der Test rot mit
  einer Meldung, die benennt, welche fehlt (s. `tests/fixtures/meteoalarm_feed/README.md`).
- [ ] Test 6 (`tests/tdd/test_meteoalarm_feed_oesterreich.py`): GIVEN der Feed-Abruf für
  Österreich liefert eine syntaktisch gültige, aber strukturell leere Antwort (kein
  auswertbarer `"warnings"`-Listen-Schlüssel) WHEN die amtlichen Warnungen für einen
  abgedeckten österreichischen Ort ermittelt werden THEN liefert der Aufruf `unavailable=True`
  statt einer leeren, als "keine Warnung" interpretierbaren Liste.
- [ ] Test 7 (`tests/tdd/test_meteoalarm_feed_oesterreich.py`): GIVEN im AT-Feed liegt genau
  der Eintrag für die Zone des abgefragten Orts strukturell kaputt vor (fehlendes/leeres
  `alert`) WHEN die amtlichen Warnungen für diesen Ort ermittelt werden THEN liefert der Aufruf
  `unavailable=True` statt die Warnung stillschweigend zu verlieren.
- [ ] Test 8 (`tests/tdd/test_meteoalarm_feed_oesterreich.py`): GIVEN ein einzelner
  strukturell kaputter Eintrag liegt irgendwo im AT-Feed für eine ANDERE Zone als die des
  abgefragten Orts UND gleichzeitig schlägt der Feed-Abruf für einen italienischen Ort fehl
  WHEN die amtlichen Warnungen für den (vollständig bedienbaren) österreichischen Ort ermittelt
  werden THEN bleibt dessen Ergebnis unbeeinträchtigt (`unavailable=False`, seine eigene
  korrekte Warnung erscheint) — weder der fremde kaputte Eintrag im eigenen Land noch der
  Ausfall im jeweils anderen Land färbt es ein.
- [ ] Test 9 (`tests/tdd/test_meteoalarm_feed_italien.py`, Regression): GIVEN
  `MeteoAlarmFeedSource` bekommt durch diese Scheibe einen Land-Parameter WHEN die bestehenden
  IT-Tests mit `MeteoAlarmFeedSource("IT")` statt `MeteoAlarmFeedSource()` instanziiert werden
  THEN bleibt jedes bisherige IT-Testergebnis unverändert grün.

## Acceptance Criteria

- **AC-1:** Given ein Ort liegt nachweislich außerhalb Österreichs (die zuständige
  österreichische Quelle antwortet mit "nicht zuständig"), When die amtlichen Warnungen für
  diesen Ort ermittelt werden, Then erscheint keine österreichische Warnung im Ergebnis, und
  das Ergebnis wird NICHT als "amtliche Warnungen nicht abrufbar" gemeldet.
  - Test: Test 1 oben — leere Liste, `unavailable=False` bei ZAMG-404.

- **AC-2:** Given die österreichische Zuordnungsquelle ist zum Abrufzeitpunkt nicht erreichbar
  (Netzwerkfehler, Zeitüberschreitung, Serverfehler), When die amtlichen Warnungen für einen
  betroffenen österreichischen Ort ermittelt werden, Then meldet das Ergebnis "amtliche
  Warnungen aktuell nicht abrufbar" statt fälschlich eine warnungsfreie Lage zu zeigen.
  - Test: Test 2 oben — `unavailable=True` bei fehlgeschlagenem ZAMG-Abruf.

- **AC-3:** Given ein Ort in Österreich ist eindeutig einer Zone zugeordnet, für die aktuell
  keine gültige amtliche Warnung besteht, When die amtlichen Warnungen für diesen Ort ermittelt
  werden, Then liefert das Ergebnis eine leere, nicht als Ausfall markierte Liste.
  - Test: Test 3 oben — Ruhe-Fall, `unavailable=False`, leere Warnungsliste.

- **AC-4:** Given mehrere Orte in Österreich werden innerhalb desselben Auffrischungsfensters
  abgefragt, When die amtlichen Warnungen ermittelt werden, Then löst höchstens ein echter
  Netzabruf gegen den neuen Feed-Weg dieses Fenster aus, kein zusätzlicher Netzabruf gegen die
  bereits genutzte Zuordnungsquelle entsteht, und im Diagnose-Journal erscheint kein Eintrag
  gegen den bisherigen kontingentierten Warndienst für Österreich.
  - Test: Test 4 oben — Zählung echter Netzaufrufe (Feed + ZAMG) über mehrere Abfragen, plus
    Journal-Abwesenheit von `host=api.meteoalarm.org`.

- **AC-5:** Given ein zur selben Minute aufgezeichneter Vergleichsabruf über den bisherigen
  kontingentierten Weg und die neue Quelle liegen für eine Liste realer österreichischer
  Tourpunkte vor, When beide Ergebnismengen gegenübergestellt werden, Then enthält die neue
  Quelle mindestens alle Warnungen, die der bisherige Weg für dieselben Punkte lieferte.
  - Test: Test 5 oben — Obermengen-Vergleich gegen aufgezeichnete Fixtures (Pflicht-Gate).
  - **PO-Entscheidung 2026-08-01:** Der Product Owner hat die Auslieferung freigegeben, bevor
    dieser Nachweis (`edr_snapshot_at.json`/`zamg_snapshot_at.json`) vorliegt — Grundlage ist ein
    am selben Tag geführter Kreuzvergleich gegen die Ursprungsquelle GeoSphere Austria an acht
    realen Orten (darunter Sillian und Lienz am Karnischen Höhenweg), der keine einzige fehlende
    Warnung zeigte, dazu 117 grüne Tests und zwei bestandene Gegenproben. Der zugehörige Test
    (`test_ac5_feed_menge_ist_obermenge_der_edr_menge_fuer_reale_tourpunkte`) bleibt
    `@pytest.mark.xfail(strict=True, ...)`, bis das eigentliche Anbieter-Tageskontingent
    (gesperrt bis 2026-08-01T15:45 UTC) wieder verfügbar ist und der Vergleich nachgezogen wird —
    danach wird die Markierung entfernt.

- **AC-6:** Given die neue Quelle liefert eine syntaktisch gültige, aber strukturell
  unbrauchbare Antwort (kein auswertbarer Warnungsbestand), When die amtlichen Warnungen für
  einen betroffenen österreichischen Ort ermittelt werden, Then meldet das Ergebnis "amtliche
  Warnungen aktuell nicht abrufbar" statt einer leeren, als "keine Warnung" interpretierbaren
  Liste.
  - Test: Test 6 oben — strukturell leere Gesamtantwort löst `unavailable=True` aus.

- **AC-7:** Given genau der Warnungseintrag für die Zone des abgefragten Orts liegt in der
  neuen Quelle strukturell kaputt vor, When die amtlichen Warnungen für diesen Ort ermittelt
  werden, Then verschwindet die Warnung nicht stillschweigend, sondern das Ergebnis meldet
  "amtliche Warnungen aktuell nicht abrufbar".
  - Test: Test 7 oben — kaputter Einzeleintrag der eigenen Zone löst `unavailable=True` aus,
    statt leer zu bleiben.

- **AC-8:** Given ein strukturell kaputter Einzeleintrag betrifft eine andere Zone als die des
  abgefragten Orts, ODER die amtliche Warnungsermittlung für das jeweils andere Land ist zum
  selben Zeitpunkt gestört, When die amtlichen Warnungen für einen vollständig bedienbaren
  österreichischen Ort ermittelt werden, Then bleibt dessen Ergebnis davon unberührt — weder
  ein fremder Defekt im eigenen Land noch ein Ausfall des anderen Landes darf einen korrekt
  bedienbaren Ort als "nicht abrufbar" einfärben.
  - Test: Test 8 oben — fremder kaputter Eintrag (eigenes Land) + gleichzeitiger IT-Ausfall,
    betroffener AT-Ort bleibt `unavailable=False` mit korrekter eigener Warnung.

## Antrag-Ergänzung für `docs/specs/data_sources.md`

**Status:** PENDING — Genehmigung durch den Product Owner erforderlich vor Umsetzung dieser
Scheibe. Ergänzt den in S1 gestellten Antrag (dort nur `feeds-italy` beschrieben) um den
zweiten Pfad derselben, bereits genehmigten Domäne.

| Merkmal | Wert |
|---|---|
| Endpunkt | `https://feeds.meteoalarm.org/api/v1/warnings/feeds-austria` |
| Auth | keine (öffentlich, kein API-Key) |
| Kontingent | keines bekannt/dokumentiert |
| Inhalt | identisch zum IT-Feed strukturiert, zusätzlich auf **Deutsch** (`language: de-DE`) |
| Umfang je Abruf | ~2,4 MB / 1220 Einträge (709 aktuell gültig, live gemessen 2026-07-31) |

**Begründung:** wie S1 — ersetzt ausschließlich den Transportweg der bereits genutzten
MeteoAlarm-Warndaten für das zweite von zwei bislang aktiven Ländern, kein neuer
Datenlieferant.

**Risiko:** wie S1, hier zusätzlich verschärft durch die AT-spezifische
Drei-Zustands-Auflösung (s. Implementation Details Punkt 2) — dagegen steht als Gegenmaßnahme
AC-1/AC-2 als Pflicht-Gate.

## Known Limitations

- **Der EDR-Index-Apparat wird NICHT zurückgebaut.** `meteoalarm.py` bleibt vollständiger Code,
  nur nicht mehr registriert. Der Rückbau ist eine eigene Folgescheibe nach hinreichend langer
  Beobachtung der neuen Quelle in Produktion (Begründung: der Äquivalenznachweis dieser Scheibe
  ist ein einmaliger Fixture-Vergleich, kein Dauerbetrieb-Beleg).
- **Geerbtes, nicht neu eingeführtes Restrisiko (F002 aus #1085):** `geosphere_warn.py:82-89`
  cacht jede 404-Antwort 24 Stunden lang als "nicht zuständig" (Erfolg). Ein ECHTER
  ZAMG-Eigenausfall, der sich zufällig ebenfalls als HTTP 404 äußert (statt 5xx/Timeout), würde
  über diesen Pfad 24 Stunden lang als Fall 1 ("hier gelten keine österreichischen Warnungen")
  erscheinen statt als Fall 2 ("ich weiß es nicht") — genau die in der Aufgabenstellung benannte
  Verwechslungsgefahr. Dieses Risiko ist bereits in #1085 dokumentiert und dort bewusst
  akzeptiert (324 sinnlose Abrufe/Tag vs. ein seltenes, unbeobachtetes Fehlerbild). **Neu durch
  diese Scheibe ist der vergrößerte Wirkradius:** vor S3 hätte ein solcher maskierter Ausfall
  nur `GeoSphereWarnSource`s eigene Warnungen betroffen; nach S3 hängt zusätzlich die gesamte
  MeteoAlarm-Marken-Warnung für den betroffenen Punkt an derselben gecachten Antwort. Ein echter
  Fix (z. B. Unterscheidung über einen zweiten Signalweg) ist NICHT Teil dieser Scheibe — sie
  überträgt lediglich ein bereits akzeptiertes Risiko auf einen zweiten Verbraucher, führt es
  nicht neu ein.
- **Registrierungsreihenfolge als stille Voraussetzung.** "Null zusätzliche ZAMG-Abrufe" gilt
  nur, solange `GeoSphereWarnSource` vor `MeteoAlarmFeedSource("AT")` registriert bleibt (s.
  Implementation Details Punkt 4). Würde `GeoSphereWarnSource` je entfernt oder umsortiert,
  bricht diese Eigenschaft — nicht katastrophal (es entstünde einfach ein regulärer, gecachter
  ZAMG-Abruf), aber unbemerkt, bis ein Verbrauchs-Audit es auffällt.
- **Kein Kilometer-Rückfall für Fall 2.** Analog S1: ein tatsächlicher ZAMG-Ausfall meldet
  "nicht abrufbar", rät keine Nachbarzone.
- **Kein Bestand über Prozessneustarts persistiert**, wie bei S1.
- **Kreuzvalidierung nur punktuell.** Wie S1: AC-5 ist ein einmalig aufgezeichneter
  Fixture-Vergleich zum Implementierungszeitpunkt, kein fortlaufender Live-Abgleich.
- **Aufnahme-Zeitfenster für AC-5 kostet Kontingent.** Anders als bei Italien (~3 Abrufe) kostet
  die EDR-Vergleichsaufnahme für Österreich **17–21 Abrufe** — muss in ein Zeitfenster mit
  offenem Tageskontingent gelegt werden (s. Test Plan). Bis dahin bleibt der zugehörige Test
  bewusst ROT, nicht übersprungen (Präzedenz S1: ein übersprungener Sicherheitsnachweis ist von
  einem bestandenen nicht zu unterscheiden).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0039 — „Amtliche Warnungen kommen aus dem kontingentfreien MeteoAlarm-Feed statt aus der mengenbegrenzten EDR-Index-API", geschrieben am 2026-08-01, Status Akzeptiert. Datei: `docs/adr/0039-amtliche-warnungen-aus-kontingentfreiem-feed.md`. Die Empfehlung dieser Spec ist damit umgesetzt.
- **Rationale:** S1 hatte "ADR-Nr.: keine" begründet, weil der Wechsel damals nur einen von
  zwei Ländern und nur den Transportweg betraf, während Provider und Architektur-Rolle
  unverändert blieben (ADR-0016, ADR-0018 weiter gültig). Mit dieser Scheibe ändert sich die
  Lage: der Bezugsweg für die GESAMTE MeteoAlarm-Marke (beide bislang aktiven Länder) wechselt
  vollständig und dauerhaft von einem authentifizierten, kontingentierten EDR-Index auf einen
  unauthentifizierten öffentlichen Feed-Snapshot — kein Übergangszustand mehr, sondern der neue
  Regelfall. Das ist nicht nur eine Transport-, sondern auch eine **Auth-Entscheidung** im
  Sinne von CLAUDE.md ("vor Änderungen an Entscheidungsflächen... Auth... dort nachsehen"): der
  produktive Pfad braucht `GZ_METEOALARM_APIKEY` künftig nicht mehr. Zusätzlich legt diese
  Scheibe das Muster fest, an dem sich #1442 (weitere Länder) orientieren wird — genau der Fall,
  für den ADRs laut `docs/adr/README.md` gedacht sind: eine Entscheidung, die nicht still
  rückgängig gemacht werden soll, wenn ein künftiger Bearbeiter aus Bequemlichkeit doch wieder
  auf den EDR-Index zurückgreift. **Empfehlung:** ein neues ADR "MeteoAlarm-Datenbezug: 
  öffentlicher CAP-Feed statt kontingentierter EDR-Index" anlegen, das ADR-0016 (additiver
  externer Alert-Typ, unverändert gültig) ergänzt statt ersetzt. Die Entscheidung selbst
  (Quellenwechsel bestätigen) ist laut S1-Spec ohnehin als offene PO-Frage vermerkt — diese
  Scheibe macht sie erstmals vollständig und damit endgültig, was aus Sicht dieser Spec den
  Ausschlag für ein ADR gibt. Die konkrete ADR-Datei ist nicht Teil dieser Spec-Phase, sondern
  ein Folgeschritt nach PO-Freigabe.

## Changelog

- 2026-08-01: Initial spec created (Issue #1445, Scheibe S3 — Feed-Bestandsquelle Österreich,
  EDR-Index-Aufruf entfällt vollständig für beide Länder; Folge-Scheibe S4 MQTT laut
  `docs/context/fix-1397-wiederanlauf-ausbruch.md`)
