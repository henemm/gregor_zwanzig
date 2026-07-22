# Context: feat-1348-warn-isolation-2b (Scheibe 2b — Test/Staging von echten Warn-APIs abschneiden)

## Request Summary
Die 4 amtlichen Warn-Host im Egress-Wächter-Inventar (Scheibe A) von `TEST_ACCESS`
auf `BLOCKED` umstellen, damit Test/Staging die echten Warn-APIs nicht mehr
erreichen (Kontingent-Schonung). Nicht-Live-Tests, die die echten APIs treffen,
auf `@pytest.mark.live` verschieben (gehören in die Live-Schicht).

## Belege (Code)
- Wächter ist im deterministischen Kern **aktiv** (`conftest._egress_guard`,
  autouse; ausgenommen nur `live`/`email`/`staging`-Marker + `test_egress_guard`).
- 4 Warn-Host aktuell `TEST_ACCESS` (`src/app/egress_guard.py:36-40`):
  `api.meteoalarm.org`, `warnungen.zamg.at`, `public-api.meteofrance.fr`
  (Vigilance + Météo-Forêts teilen ihn), `www.risque-prevention-incendie.fr`.
- **`public-api.meteofrance.fr` teilt sich KEINEN Host mit einem Wetter-Provider**
  — das Wetter-„meteofrance" läuft über open-meteo (`api.open-meteo.com/v1/meteofrance`,
  `openmeteo.py:112`). Blockieren ist wetter-sicher.
- Wetter-/Radar-Host (`dataset.api.hub.geosphere.at`, `api.brightsky.dev`,
  `radar-api.protezionecivile.it`) sind KEINE Warn-Dienste (eigene Fixture-Isolation
  via `GZ_TEST_FIXTURE_DIR`) — NICHT Teil von 2b.
- Nach AC-11 laufen die Warn-Dienste über `warn_egress.cached_fetch`: bei BLOCKED
  wirft `httpx` `EgressBlockedError`, `cached_fetch` fängt es (Failure-Cache +
  `None`) → Dienst liefert `[]` fail-soft. Test **crasht** nicht, bekommt nur `[]`
  → Tests, die NON-EMPTY Warndaten asserten, schlagen fehl → müssen `@live`.

## Betroffene Test-Dateien
| Datei | Tests | schon @live | Nicht-live (Kandidaten für Umzug, falls echter Call) |
|---|---|---|---|
| `test_issue_1035_vigilance_source.py` | 6 | 3 | 3 |
| `test_issue_1036_meteo_forets_source.py` | 3 | 0 | 3 |
| `test_issue_1037_massif_closure.py` | 10 | 3 | 7 |
| `test_issue_1085_geosphere_warn.py` | 6 | 0 | 6 |

**Nur die verschieben, die WIRKLICH einen echten Call machen und Daten asserten**
— Parsing-Tests mit konstruierten Daten (kein Netz) bleiben Kern-Tests. Der
GREEN-Lauf zeigt via Testausfall genau, welche.

## Design (In-Framework, ohne neuen Mechanismus)
BLOCKED (nicht Attrappe): Scheibe A kennt nur `TEST_ACCESS`/`BLOCKED`. Attrappe
mit aufgezeichneten Warndaten wäre ein NEUER Mechanismus (eigene, größere Scheibe).

## Bekannte Konsequenz
Staging zeigt danach **keine echten amtlichen Warnungen** mehr (immer leer) →
Warnungs-*Darstellung* auf Staging nicht mehr prüfbar. Für das Ziel
(Kontingent-Schonung) korrekt; Attrappe = optionale Folge-Scheibe.

## Risks
- Regressionsarm: **nur** die echten-API-Tests auf `@live`, keine Parsing-Tests
  aufweichen. Gezielte Regression auf die 4 Test-Dateien + `test_egress_guard`.
- Wächter-Änderung ist eine reine Inventar-Datenzeile (4× `TEST_ACCESS`→`BLOCKED`),
  Mechanik unangetastet.
