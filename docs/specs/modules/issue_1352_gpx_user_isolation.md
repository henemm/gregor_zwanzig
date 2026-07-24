---
entity_id: issue_1352_gpx_user_isolation
type: bug
created: 2026-07-24
updated: 2026-07-24
status: draft
version: "1.0"
tags: [gpx, mandantentrennung, security, cross-user]
---

# GPX-Upload-Nutzer-Isolation

## Approval

- [ ] Approved

## Purpose

`POST /api/gpx/parse` legt jede hochgeladene GPX-Datei aktuell im fest verdrahteten,
geteilten Verzeichnis `data/users/default/gpx/` ab — unabhängig davon, welcher Nutzer
eingeloggt ist. Gleichnamige Dateien verschiedener Nutzer überschreiben sich gegenseitig,
und ein präparierter Dateiname kann gezielt in den Ordner eines anderen Nutzers schreiben.
Diese Spec bringt den GPX-Upload auf das im Python-Core etablierte Muster: Upload-Ziel wird
aus der echten `user_id` des Auth-Kontexts über `get_data_dir(user_id)` aufgelöst.

## Source

- **File:** `api/routers/gpx.py`
- **Identifier:** `parse_gpx()`
- **File:** `src/services/gpx_processing.py`
- **Identifier:** `process_gpx_upload()`, `gpx_to_stage_data()`, `process_bulk_gpx_uploads()`

**Schicht:** Python-Core (`api/routers/`, `src/services/`). Die Go-Schicht
(`internal/handler/proxy.go::GpxProxyHandler`) liefert die `user_id` bereits korrekt über
`appendUserID` und wird **nicht** geändert.

## Estimated Scope

- **LoC:** ~+30/-12 (Doku zählt nicht mit)
- **Files:** 4 (2 Code, 1 Test, 1 Spec-Pflege)
- **Effort:** low-medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.loader.get_data_dir` | python function | Löst das per-Nutzer-Datenverzeichnis auf (`data/users/<user_id>/`); kanonischer Auflösungsweg, ersetzt die fest verdrahteten Modul-Konstanten |
| `internal/handler/proxy.go::GpxProxyHandler` | go handler | Liefert `user_id` bereits korrekt als Query-Param an den Python-Endpoint (unverändert) |
| `tests/conftest.py::_isolate_data_root` | pytest fixture (autouse) | Test-Isolation für `get_data_dir()`/`get_data_root()` (Issue #1133); ersetzt den bisherigen `monkeypatch.chdir`-Workaround in `test_gpx_proxy.py` |

## Implementation Details

Auflösung des Upload-Ziels gehört in den Router, nicht ins Service-Modul:

1. `api/routers/gpx.py`: `user_id: str = Query(...)` als Pflichtparameter (analog
   `api/routers/preview.py:32`), `upload_dir = get_data_dir(user_id) / "gpx"` auflösen und an
   `gpx_to_stage_data()` durchreichen.
2. `src/services/gpx_processing.py`: Modul-Konstanten `_DEFAULT_UPLOAD_DIR`/`_GPX_UPLOAD_DIR`
   ersatzlos entfernen. `upload_dir` wird in `process_gpx_upload`, `gpx_to_stage_data` und
   `process_bulk_gpx_uploads` zum Pflicht-Parameter ohne Default — ein fehlendes `upload_dir`
   führt zu einem sofortigen `TypeError` statt einem stillen Rückfall auf einen geteilten Ordner.
3. Schreibstelle in `process_gpx_upload`: `saved_path = upload_dir / Path(filename).name` statt
   des rohen `filename`, damit ein präparierter Name wie `"../../bob/gpx/x.gpx"` nicht mehr aus
   dem eigenen Nutzerordner ausbrechen kann.
4. `process_bulk_gpx_uploads` bekommt dieselbe Pflicht-Parameter-Behandlung, bleibt aber als
   Funktion bestehen (fünf aktive Tests hängen daran; kein eigener Löschentscheid gegen
   `gpx_multi_import.md`).
5. **Adversary-Nachtrag (F001):** `get_data_dir()` (`src/app/loader.py:1053-1060`) macht ein
   reines Path-Join ohne Sanitisierung der `user_id` — eine präparierte Kennung wie
   `"../users/bob"` schrieb nachweislich in den Ordner eines anderen Nutzers, auch nachdem
   Schritt 3 den Dateinamen absichert. `api/routers/gpx.py:20` führt dazu
   `_VALID_USER_ID = re.compile(r"^[a-zA-Z0-9_-]+$")` ein; `:34-35` prüft die `user_id` gegen
   dieses Muster vor jedem Pfadbau und vor `file.read()` — bei Nichttreffer
   `HTTPException(400, "invalid_user_id")`. Das Muster ist identisch zu dem, das die
   Go-Registrierung bereits erzwingt (`internal/handler/passkey.go:23`).

Schritte 1-3 sind atomar zusammen mit der Testanpassung zu committen — dazwischen ist der Baum
notwendigerweise rot.

## Expected Behavior

- **Input:** SvelteKit sendet weiterhin `POST /api/gpx/parse` mit GPX-Datei als Multipart-Field
  `file`; der Go-Proxy hängt die `user_id` der aktuellen Sitzung als Query-Param an (unverändert).
- **Output:** Gleiches JSON-Format wie bisher (`name`, `date`, `waypoints[]`) — die fachliche
  Antwort ändert sich nicht.
- **Side effects:** Die hochgeladene GPX-Datei wird im Ordner des tatsächlich hochladenden
  Nutzers abgelegt (`data/users/<user_id>/gpx/`) statt im geteilten `default`-Ordner. Ein Aufruf
  ohne gültige `user_id` schreibt gar nichts und schlägt fehl, statt in einen geteilten Ordner
  auszuweichen.

## Acceptance Criteria

- **AC-1:** Given zwei unterschiedliche Nutzer laden je eine eigene GPX-Datei hoch / When der
  Upload abgeschlossen ist / Then liegt die Datei im Datenordner des jeweils hochladenden
  Nutzers, und im Ordner des anderen Nutzers taucht keine neue Datei auf.
  - Test: Zwei Uploads über `TestClient`, einmal als `alice`, einmal als `bob`, danach beide
    Nutzerordner auflisten und prüfen, dass jede Datei nur beim jeweils hochladenden Nutzer
    erscheint.

- **AC-2:** Given zwei Nutzer laden eine Datei mit exakt demselben Dateinamen, aber
  unterschiedlichem Inhalt hoch / When beide Uploads nacheinander laufen / Then bleiben beide
  Inhalte vollständig erhalten — keiner überschreibt den anderen.
  - Test: Upload `wanderung.gpx` (Inhalt A) als `alice`, danach Upload `wanderung.gpx`
    (Inhalt B) als `bob`; anschließend beide gespeicherten Dateien lesen und byte-genau mit den
    jeweils erwarteten Original-Inhalten vergleichen.

- **AC-3:** Given ein Nutzer lädt eine GPX-Datei mit einem präparierten Dateinamen hoch, der
  Verzeichnis-Aufstiege enthält (z.B. `../../bob/gpx/x.gpx`) / When der Upload verarbeitet wird
  / Then landet die Datei im eigenen Ordner des hochladenden Nutzers unter ihrem reinen
  Dateinamen, nicht im Ordner eines anderen Nutzers und nicht außerhalb des Datenbaums.
  - Test: Upload als `alice` mit Dateinamen `"../../bob/gpx/x.gpx"`; danach prüfen, dass die
    Datei bei `alice` liegt und der Ordner von `bob` unverändert bleibt (keine neue/veränderte
    Datei dort).

- **AC-4:** Given eine Anfrage an den Upload-Endpoint ohne erkennbaren Nutzer / When die Anfrage
  verarbeitet wird / Then wird sie abgewiesen, und es entsteht kein neuer Eintrag in einem
  geteilten oder nutzerlosen Ordner.
  - Test: `POST /api/gpx/parse` ohne `user_id`-Parameter absetzen; Response ist ein
    Fehlerstatus, und der Inhalt des `default`-Ordners bleibt unverändert (kein neuer Dateieintrag).

- **AC-5:** Given eine gültige GPX-Datei, wie sie vor dieser Änderung erfolgreich verarbeitet
  wurde / When derselbe Upload nach der Änderung erneut durchgeführt wird / Then liefert die
  Antwort dieselben fachlichen Daten (Name, Datum, Wegpunkte mit Position und Höhe) wie zuvor.
  - Test: Bestehender Regressionstest mit realer Komoot-GPX-Fixtur, der `name`, `date` und die
    Struktur/Anzahl der `waypoints[]` prüft, weiterhin grün.

- **AC-6:** Given eine Anfrage an den Upload-Endpoint gibt als Nutzerkennung einen Wert an, der
  Pfadanteile enthält (z.B. `../users/bob`) oder sonst keinen brauchbaren Ordnernamen bezeichnet
  / When der Upload verarbeitet wird / Then wird die Anfrage abgewiesen, und der Ordner des davon
  betroffenen anderen Nutzers bleibt byte-genau unverändert; echte Nutzerkennungen werden
  weiterhin ganz normal akzeptiert.
  - Test: `tests/tdd/test_gpx_upload_user_isolation.py::test_praeparierte_nutzerkennung_bricht_nicht_in_fremden_ordner_aus`,
    `::test_unbrauchbare_nutzerkennung_wird_abgewiesen`,
    `::test_echte_nutzerkennungen_werden_weiterhin_akzeptiert`.

## Known Limitations

- Der Altbestand in `data/users/default/gpx/` (22 Dateien, Stand 24. Juli 2026) wird durch
  diese Änderung nicht migriert oder gelöscht — es gibt keinen fachlichen Leser dieser Dateien
  außerhalb des unmittelbaren Parse-Vorgangs, aber eine Test-Fixture in `test_gpx_proxy.py`
  hängt an einer konkreten Datei darin.
- Ein direkter Aufruf des Python-Core ohne Nutzerkennung (z.B. testweise gegen Port 8000/8001)
  antwortet nach dieser Änderung mit einem Validierungsfehler statt stillem Rückfall. Das ist
  unkritisch, da die Python-Core-Ports nachweislich nur lokal gebunden sind
  (127.0.0.1:8000/8001/8090) und von außen nicht erreichbar sind.
- `process_bulk_gpx_uploads` bleibt bestehen (fünf aktive Tests hängen daran), erhält aber
  dieselbe Pflicht-Parameter-Behandlung wie die anderen beiden Funktionen.
- Folgearbeit (dokumentarisch, nicht Teil dieser Spec): `docs/specs/modules/gpx_proxy.md`
  streicht „Authentifizierung / Benutzer-Isolation" aus der *Out-of-Scope*-Liste, da dies der
  dokumentarische Ursprung des Bugs war.
- Die `user_id`-Prüfung (`_VALID_USER_ID` in `api/routers/gpx.py`) deckt ausschließlich diesen
  einen Endpoint ab. Die übrigen ~27 Aufrufer von `get_data_dir()` im Python-Core (Scheduler,
  Alarme, Briefings, Trip-/Compare-Persistenz u.a.) bleiben ungeprüft — eine zentrale
  Absicherung in `get_data_dir()` selbst ist bewusst nicht Teil dieser Spec, weil eine zu strenge
  zentrale Prüfung dort produktiv laufende Jobs stillegen könnte, ohne dass das hier isoliert
  getestet wäre. Das ist ein eigener, künftiger Vorgang.
- Das Muster `_VALID_USER_ID` muss synchron zu `internal/handler/passkey.go:23` bleiben — ändert
  sich dort die für die Registrierung erlaubte Zeichenmenge, muss diese Prüfung nachziehen,
  sonst werden neu registrierbare, aber hier noch nicht erlaubte Nutzerkennungen fälschlich
  abgewiesen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0003 (Konsequente Mandantentrennung, kein `"default"`-Fallback)
- **Rationale:** Diese Änderung setzt eine bereits getroffene Architekturentscheidung
  (Isolation pro Nutzer unter `data/users/<user_id>/`, kein `"default"`-Fallback) auf einem
  bislang übersehenen Pfad durch — sie ändert die Entscheidung nicht, sondern korrigiert eine
  Abweichung davon.

## Changelog

- 2026-07-24: Initial spec (Issue #1352)
- 2026-07-24: AC-6 ergaenzt — user_id-Validierung nach Adversary-Befund F001
