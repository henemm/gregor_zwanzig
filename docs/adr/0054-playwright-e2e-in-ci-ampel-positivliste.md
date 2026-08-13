# ADR-0054: Playwright-E2E-Klickpfade in die CI-Ampel — isolierter Stack, Positivliste statt Ausschlussliste

- **Status:** Akzeptiert (PO-Freigabe 2026-08-13)
- **Datum:** 2026-08-13
- **Bezug:** GitHub-Issue #1771 Scheibe 2, Spec
  `docs/specs/modules/fix_1771_s2_playwright_ci_ampel.md`. Schreibt ADR-0006 („keine
  gemockten Tests, echte E2E") und ADR-0028 (Proxy-Ziel auf Staging als Default) fort.

## Kontext

Kein Playwright-Spec lief bisher in der CI-Ampel. Der Issue-Kommentar vom 2026-08-12 schlug
vor, die „lokal lauffähigen" Specs ohne Staging-Zugangsdaten direkt in die Ampel zu hängen —
das ist am laufenden System widerlegt: der „lokale" Lauf ist tatsächlich lokales Frontend
gegen den geteilten, dauerhaft laufenden Staging-Go-Server (`GZ_API_BASE=http://localhost:8091`
proxied auf `gregor-api-staging.service`); auf einem GitHub-Runner (`ubuntu-latest`) existiert
davon nichts. Eine Stichprobenmessung (72 Testfälle, 15 Dateien) gegen Staging im
Normalbetrieb ergab **22 rote Fälle (30,6 %)** — fast jeder dritte Test ist heute rot, ohne
dass jemand etwas geändert hätte.

## Entscheidung

1. **Eigener, paralleler CI-Job `e2e`** (kein `needs:`, startet zeitgleich mit `test`), der
   einen **eigenen, im Runner selbst hochgefahrenen Stack** (Python-Core + Go-Server, beide
   offline über `GZ_TEST_FIXTURE_DIR`) gegen eine **wachstumsbeschränkte Positivliste**
   (`.github/ci_e2e_specs.txt`) fährt — nicht den geteilten Staging-Server.
2. **Positivliste statt Ausschlussliste**, Richtungsumkehr zu `.github/ci_tdd_excludes.txt`:
   Eine Ausschlussliste setzt eine grüne Grundmenge voraus; hier ist sie es nachweislich
   nicht (30,6 % rot in der Stichprobe). Die neue Liste darf nur **wachsen**, nie schrumpfen —
   was nicht drauf steht, verpflichtet zu nichts. Aufnahme nur nach Filter A (strukturell:
   keine `waitForTimeout`/`test.skip`/`test.fixme`, keine `.staging.spec.ts`, keine
   wertprüfenden Wetter-Specs, und zwei am Code bestätigte strukturell kaputte Dateien
   ausgeschlossen — hartkodierter Hauptrepo-Pfad bzw. `__dirname` in einem ESM-Modul; gemessener
   Pool nach diesem Filter: 87 Dateien) UND Filter B (3× hintereinander grün im
   `workflow_dispatch`-Vermessungslauf im Runner — belegt am 2026-08-13: 36 Dateien / 173
   Testfälle, zwei Folgeläufe je 173 expected / 0 unexpected / 0 skipped).
3. **Drei Bedingungen statt einer** (`.github/scripts/e2e_gate.py`, als eigene Datei statt
   YAML-Einzeiler, damit sie selbst testbar ist — `tests/unit/test_e2e_ci_gate.py`):
   `unexpected == 0`, `skipped == 0`, `expected >= E2E_MIN_EXECUTED`. Ohne die dritte
   Bedingung wäre ein Lauf grün, in dem der Stack nie hochkam und kein Test lief — „0 Tests,
   0 rot" ist kein Beweis, sondern ein Bericht über gar nichts.
4. **`GZ_PORT=8091` Pflicht, `GZ_SESSION_SECRET` bewusst ungesetzt** für den isolierten
   Stack (`frontend/e2e/ci-stack.sh`) — Details in der Spec, Implementation-Detail 2.
5. **Klarstellung zu ADR-0028:** Dessen Verwerfung von „Isolation über `GZ_DATA_DIR`" als
   *technisch nicht tragfähig* ist **verjährt**. Der damals zitierte Hartkodierungs-Fund
   (`scheduler_dispatch_service.py:141`, `data_root = "data"`) ist mit #1133 behoben —
   `get_data_root()` (`src/app/loader.py:1088-1107`) respektiert `GZ_DATA_DIR` heute
   (Priorität `_DATA_ROOT` > `GZ_DATA_DIR` > `"data"`), und `scheduler_dispatch_service.py`
   nimmt `data_root` inzwischen als expliziten Parameter statt ihn zu hardcoden. Diese Scheibe
   nutzt genau das: der isolierte CI-Stack bekommt eine eigene, leere `GZ_DATA_DIR`. Die
   Nutzung von `GZ_E2E_API_PROXY_TARGET` ist dagegen **kein** Abweichen von ADR-0028 — der
   Override ist dort ausdrücklich vorgesehen.
6. **Merge-Regel:** „5 GitHub-Actions-Checks" wird zu „6 Checks" (inkl. `e2e`) — ein neuer PR
   wird erst gemergt, wenn auch `e2e` grün ist.

## Verworfene Alternativen

- **Die vom Issue-Kommentar vorgeschlagenen „141/157 lokal lauffähigen" Specs direkt
  übernehmen** — verworfen: am laufenden System widerlegt (siehe Kontext); der Lauf hängt am
  geteilten Staging-Server, den es auf dem Runner nicht gibt.
- **`frontend-test` um E2E-Specs erweitern** — verworfen: `frontend-test` kostet heute 64s und
  ist der schnelle Signalgeber für Node-Unit-Tests; ein E2E-Anhängsel würde das zerstören.
- **Ausschlussliste (Ratsche wie `ci_tdd_excludes.txt`) statt Positivliste** — verworfen: setzt
  eine grüne Grundmenge voraus, die die Stichprobenmessung (30,6 % rot) widerlegt.
- **Volllauf über alle 921 Tests als Vorbedingung** — verworfen: würde die Scheibe sprengen und
  die Sanierung von 78–81 `waitForTimeout`-Stellen sowie 35 konditionalen Skips erzwingen,
  bevor überhaupt ein Job existiert. Bleibt per `workflow_dispatch` als Wachstumswerkzeug für
  Folge-Scheiben verfügbar.
- **Auswertung als `python3 -c "..."`-Einzeiler direkt in der YAML** — verworfen: wäre von
  keinem Test erreichbar, die zentrale Zusicherung dieser Scheibe (AC-4) bliebe selbst
  unbewacht.

## Konsequenzen

- **Positiv:** Erstmals laufen Playwright-E2E-Klickpfade in der CI-Ampel, ohne den geteilten
  Staging-Server zu berühren oder die schnelle `frontend-test`-Lane zu verlangsamen. Die
  Auswertungslogik ist im Kern testbar (`tests/unit/`), ohne Netz und ohne Runner.
- **Negativ / Preis:** Nur eine kuratierte Teilmenge (36 Dateien / 173 belegt grüne
  Testfälle) läuft regulär — der Großteil der 921 Testfälle bleibt vorerst unbewacht in der
  CI-Ampel (weiterhin nur per manueller `frontend`-Session gegen Staging lauffähig). Zwei
  getrennte Schwellen (`E2E_MIN_SPECS=36`, `E2E_MIN_EXECUTED=173`, exakt belegt ohne Puffer
  nach unten — ein Puffer wäre bei 15 der 36 Dateien mit ≤3 Testfällen selbst ein Loch,
  Adversary-Fund F006) erhöhen die Konfigurationsfläche; das Verschwinden einer gelisteten
  Datei wird zusätzlich über eine Existenzprüfung vor dem Playwright-Lauf gefangen.
- **Folgepflichten:** Jede Erweiterung der Positivliste braucht einen belegten
  Filter-B-Vermessungslauf (3× grün im Runner) — lokale Zahlen zählen laut
  `ci_tdd_excludes.txt`-Lektion nicht als Beleg für CI-Grün. Regel-Budget-Prüfdatum
  2026-11-11: mindestens ein PR, in dem die Lane eine Regression fängt, die die anderen fünf
  Checks durchlassen — sonst Rückbau.
