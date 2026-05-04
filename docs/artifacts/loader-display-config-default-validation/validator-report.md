# External Validator Report

**Spec:** `docs/specs/modules/loader_display_config_default.md`
**Datum:** 2026-05-03T09:30:00Z
**Server:** https://staging.gregor20.henemm.com
**Validator-User:** validator-issue110

## Test-Methode

- HTTP-Probing gegen `/api/trips` (Go-Backend) und `/api/_internal/trip/{id}/loaded` (Python-Loader-Endpoint, gemaess Spec dafuer ausgelegt, den vollstaendig geladenen Trip mit `display_config` zurueckzugeben)
- Trips mit unterschiedlichen `aggregation`-Auspraegungen via API erzeugt, dann via `/loaded` geladen und die zurueckgegebene `display_config` strukturell geprueft
- Side-Effects gegen Roh-Trip via `GET /api/trips/{id}` verifiziert (vor und nach `/loaded`)
- Cleanup aller Test-Trips am Ende der Validierung

## Checklist

| # | Expected Behavior (aus Spec) | Beweis | Verdict |
|---|------------------------------|--------|---------|
| 1 | Trip-JSON ohne `display_config` und ohne `weather_config`, mit Aggregation-Profil `wintersport` → `Trip.display_config` ist nicht `None`, vom Catalog erzeugt, `trip_id` korrekt gesetzt, `alert_enabled=False` ueberall | `evidence-01-loaded-wintersport.json` (display_config != None, trip_id="validator-fresh-1", 24 Metriken, 10 enabled, 0 alerts) | **PASS** |
| 2 | Profil-spezifischer Default — `allgemein` → andere Metrik-Auswahl als `wintersport` | `evidence-02-loaded-allgemein.json` — 7 enabled (`temperature, wind, gust, precipitation, rain_probability, cloud_total, sunshine`) ohne Wintersport-Metriken | **PASS** |
| 3 | Side effect: keine — JSON-Datei auf Platte wird vom Loader **nicht** modifiziert | Raw-Trip vor und nach mehrfachem `/loaded` byte-identisch (kein `display_config`-Feld in Raw-Daten); zwei aufeinander folgende `/loaded`-Aufrufe liefern unterschiedliche `display_config.updated_at`-Timestamps (09:30:17.976 vs 09:30:20.014) → Default wird in-memory frisch gebaut, nicht persistiert | **PASS** |
| 4 | **Edge:** `data["aggregation"]` fehlt → `profile = ActivityProfile.ALLGEMEIN` (Spec: "Wenn `data['aggregation']` fehlt … → `profile = ActivityProfile.ALLGEMEIN`") | Trip ohne `aggregation`-Feld (`evidence-edge1-raw-no-aggregation.json`) → `/loaded` liefert HTTP 200 mit `aggregation:{profile:"wintersport"}` und 10 enabled Metriken inkl. `wind_chill, snow_depth, fresh_snow` (= Wintersport-Profil, **NICHT** ALLGEMEIN, das nur 7 enabled haben muesste) — `evidence-edge1-loaded-no-aggregation-FAIL.txt` | **FAIL** |
| 5 | **Edge:** `aggregation.profile is None` → `profile = ActivityProfile.ALLGEMEIN` | Trip mit `aggregation:{profile:null}` (`evidence-edge2-raw-null-profile.json`) → `/loaded` liefert HTTP 500 Internal Server Error — `evidence-edge2-loaded-null-profile.txt`. Loader stuerzt komplett ab statt ALLGEMEIN-Fallback einzuziehen | **FAIL** |

## Findings

### Finding 1 — Edge `aggregation.profile is None` crashed den Loader (500)

- **Severity:** CRITICAL
- **Expected:** Spec, Abschnitt *Expected Behavior*, "Edge": "Wenn `data['aggregation']` fehlt oder `aggregation.profile is None` → `profile = ActivityProfile.ALLGEMEIN`." Das heisst: Trip mit `aggregation.profile=null` muss erfolgreich laden mit `display_config` aus dem ALLGEMEIN-Template.
- **Actual:** `GET /api/_internal/trip/validator-edge-null-profile/loaded` antwortet **HTTP 500 Internal Server Error** mit Body "Internal Server Error". Es gibt also keinen Fallback, der Loader bricht ab. Das ist genau das Crash-Szenario, das die Spec laut *Purpose*-Sektion verhindern wollte (frueher: `AttributeError`; jetzt: 500). Die Spec-Zusicherung "jeder geladene Trip besitzt garantiert eine `display_config`" haelt nicht — der Trip kann gar nicht erst geladen werden.
- **Evidence:**
  - `evidence-edge2-raw-null-profile.json` — Roh-Trip auf Platte mit `aggregation.profile=null`
  - `evidence-edge2-loaded-null-profile.txt` — `HTTP/1.1 500 Internal Server Error`
- **Zusatzbefund (Severity HIGH):** Solange ein solcher kaputter Trip im User-Account liegt, antwortet `/loaded` auch fuer **andere** Trips desselben Users mit 500. Beobachtet zwischen 09:26 und 09:27 UTC: `validator-test-no-config`, `validator-test-allgemein`, `validator-test-wandern`, `validator-fresh-1` — alle gleichzeitig 500, sobald `validator-test-empty-agg` und `validator-test-no-agg` noch existierten. Nach Loeschen der kaputten Trips lieferten die anderen wieder 200. Der Loader ist also nicht nur lokal, sondern global anfaellig fuer einen einzelnen kaputten Trip. (Evidence: BashHistory in dieser Session, Zeitstempel 09:26-09:28.)

### Finding 2 — Edge `aggregation` fehlt: kein ALLGEMEIN-Fallback, sondern wintersport-Default

- **Severity:** HIGH
- **Expected:** Spec, *Expected Behavior*, "Edge": Trip ohne `aggregation`-Feld → Default-Config aus dem **ALLGEMEIN**-Template (laut Vergleichsmessung: 7 enabled Metriken, ohne Wintersport-spezifische).
- **Actual:** Trip ohne `aggregation`-Key wird mit **wintersport**-Default geladen — 10 enabled Metriken inkl. `wind_chill`, `snow_depth`, `fresh_snow`, identisch zum bewussten Wintersport-Trip (`evidence-01`). Vermutliche Ursache: Persistenz-Schicht / DTO-Default fuellt `aggregation` mit `wintersport` auf, lange bevor der Spec-zitierte Loader-Code die `else`-Variante "data['aggregation'] fehlt" erreicht. Der ALLGEMEIN-Pfad ist damit auf realen Daten unerreichbar.
- **Evidence:**
  - `evidence-edge1-raw-no-aggregation.json` — Roh-Trip ohne `aggregation`
  - `evidence-edge1-loaded-no-aggregation-FAIL.txt` — `aggregation:{profile:"wintersport"}`, 10 enabled Metriken inkl. snow-spezifischer
  - Vergleichswert ALLGEMEIN: `evidence-02-loaded-allgemein.json` — 7 enabled Metriken, keine Snow-Metriken
- **Hinweis:** Diese Beobachtung steht nicht in direktem Widerspruch zur Spec-*Purpose* (`display_config != None`), aber sie widerspricht dem expliziten *Edge*-Punkt im Expected-Behavior-Block, dass Profil = ALLGEMEIN sein soll.

## Was der Validator NICHT pruefen konnte

- **Backfill-Skript** (`scripts/backfill_display_config_issue111.py`, Spec v1.1): Das ist ein Disk-Operations-Skript. Ohne Filesystem-Zugriff (Validator-Isolation) nicht ueberpruefbar. Nicht Teil von *Expected Behavior*, daher nicht im Verdict reflektiert.
- **`weather_config`-Migration-Pfad:** Wird in der Spec als bestehend ("`elif weather_config is not None: ...`") behandelt, ist nicht Teil der neuen Behavior. Nicht geprueft.
- **Der Test `test_alert_enabled` (in der Spec erwaehnt):** Test-Code, kein Spec-Verhalten.
- **Konkreter Bezug auf `gr221-mallorca.json` / `zillertal-mit-steffi.json`:** Diese Trips gehoeren User `default`, nicht dem Validator-User; per Spec-Definition (Persistenz-Verhalten am API-Layer) durfte ich keinen direkten Filesystem-Zugriff nehmen. Stattdessen wurde das *Schema* der Edge-Faelle (kein display_config, kein weather_config, keine aggregation) ueber neu erzeugte Validator-Trips reproduziert.

## Verdict: BROKEN

### Begruendung

Die *Purpose*-Aussage der Spec — "jeder geladene Trip besitzt garantiert eine `display_config`" — ist nicht eingehalten:

- **Hauptpfad** (kein `display_config`, kein `weather_config`, gueltiges `aggregation.profile`) funktioniert wie spezifiziert (Tests 1-3 PASS).
- **Edge-Pfad `aggregation.profile is None`** crasht den Loader mit HTTP 500 — der Trip ist damit gar nicht ladbar, und die zugesagte Garantie haelt nicht (Test 5 FAIL, Severity CRITICAL). Der Bug, den die Spec laut *Purpose* heilen wollte (frueher `AttributeError`), ist zu einem 500-Crash verschoben, nicht behoben.
- **Edge-Pfad `aggregation` fehlt** liefert zwar erfolgreich eine `display_config`, aber im falschen Profil (wintersport statt ALLGEMEIN) — direkter Widerspruch zum explizit niedergeschriebenen Edge-Verhalten (Test 4 FAIL).
- **Zusatzbefund Severity HIGH:** Ein einziger kaputter Trip im User-Account macht `/loaded` fuer ALLE anderen Trips desselben Users unbenutzbar (Cross-Trip-500-Propagation).

Der Implementierungs-Stand erfuellt die Hauptlinie der Spec, aber zwei der drei dokumentierten Verhaltensgarantien sind verletzt — eine davon mit kritischem Schweregrad. Verdict daher **BROKEN**.

## Empfohlene Fix-Stossrichtung (informativ, nicht Teil des Verdicts)

- Loader muss `aggregation.profile is None` defensive auf `ActivityProfile.ALLGEMEIN` mappen, bevor er an `build_default_display_config_for_profile` weiterreicht — der `if aggregation is not None and getattr(...) is not None`-Guard im Spec-Codeblock ist offenbar nicht implementiert (oder wird umgangen, weil `aggregation` durch DTO-Default nie `None` wird).
- Cross-Trip-500-Propagation gehoert separat untersucht: ein kaputter Trip darf andere Trips nicht runterziehen.
