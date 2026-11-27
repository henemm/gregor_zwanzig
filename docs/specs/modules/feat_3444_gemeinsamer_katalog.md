---
entity_id: feat_3444_gemeinsamer_katalog
type: feature
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
workflow: feat-3444-gemeinsamer-katalog
tags: [i18n, katalog, adr, go, python]
---

# Gemeinsamer Textkatalog Go/Python: Bereich `geteilt` (ADR-0130) + Scheibe 1 `kind_required`

## Approval

- [ ] Approved

## Purpose

Texte, die in der Go-API und im Python-Core wortgleich ausgegeben werden, sollen aus genau einer Datei kommen statt aus zwei Katalogen, die nur eine Fixture gleich haelt. Diese Spec legt den Mechanismus (Bereich `geteilt`, ADR-0130) fest und zieht als erste Scheibe den Text `kind_required` (Ziel von #2993, ersetzt durch #3444) dorthin um. Deutsch bleibt byte-gleich.

## Source

- **File:** `src/i18n/messages/{de,en}/geteilt.json` (Quelle), `src/i18n/embed.go` (Go-Einbettung), `internal/i18n/catalog.go` (Go-Loader), `src/i18n/catalog.py` (Python-Loader)
- **Identifier:** Bereich `geteilt`; Schluessel `geteilt.fehler.kind_required`; `errorPrefixes`; `BEREICHE`; `send_outcomes`

> **Schicht-Hinweis:** Beruehrt Go-API (`internal/i18n/`) und Python-Core (`src/i18n/`, `src/services/send_outcomes.py`). Das Frontend ist ausgenommen (`fehler.code.*` im Frontend-Katalog bleibt eigenstaendig, PO-Entscheidung #3444).
>
> **Querschnitt:** Mandantentrennung nicht beruehrt (reine Textquelle, keine Nutzerdaten; Sprache kommt wie bisher aus dem Nutzerkonto). Kanaele: kein Briefing- oder Alarm-Inhalt betroffen, nur die Fehlermeldung der Versand-Endpunkte. Trip/Ortsvergleich-Teilung: nicht betroffen.

## Scope

**In Scope:** ADR-0130, gemeinsamer Bereich `geteilt` (eine Datei je Sprache im Python-Baum, von Go eingebettet), Umzug des Fehlertexts `kind_required` dorthin samt Löschung der beiden alten Schlüssel, Wächtertest gegen `geteilt` unter `internal/`, Doku (ADR-Index, ADR-0104, i18n-Konventionen).

**Out of Scope:** Radar-Intensität und MCP-Fehler (Folge-Issues), Frontend-Katalog, jede Änderung am Wortlaut.

## Estimated Scope

- **LoC:** ~150 (Code + Tests); dazu reine Daten-JSON und Doku
- **Files:** 5 Code-Dateien, 6 JSON-Dateien, ca. 7 Test-Dateien inkl. Fixture-Hinweis, 4 Doku-Dateien (ADR-0130 neu, ADR-Index, ADR-0104, i18n_konventionen.md)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/i18n/catalog.go` | Go-Modul | `NewCatalog(fsys)`, `checkKey` (Praefix = Bereichsname), `duplicateCodes` (derselbe Code nie unter zwei Praefixen) |
| `internal/i18n/errorbody.go` | Go-Modul | `errorPrefixes` (Suchkette fuer `WriteError`) |
| `internal/handler/httperr.go` | Go-Modul | `WriteError` nutzt die Suchkette |
| `src/i18n/catalog.py` | Python-Modul | `BEREICHE`, `_lade_sprache`, `get_catalog()` |
| `src/services/send_outcomes.py` | Python-Modul | bildet Schluessel je Code, `error_body` mit `text_key`-Override |
| `tests/fixtures/send_detail_parity/faelle.json` | Fixture | deutscher Wortlaut als Verhaltenswaechter beider Schichten |
| ADR-0104, ADR-0095 | Entscheidung | Basis (je Schicht ein Katalog; Kanal-Paritaet) |

## Implementation Details

Variante V4 aus der Analyse (`docs/context/feat-3444-gemeinsamer-katalog.md`): Quelle im Python-Baum, Go bettet dieselben Dateien ein. Es gibt eine physische Datei je Text und Sprache, Drift ist ausgeschlossen.

1. **Quelle:** `src/i18n/messages/{de,en}/geteilt.json`, Bereich `geteilt`, Schluessel `geteilt.<gruppe>.<element>`. Gepflegt nur dort. Der Wortlaut wird unveraendert aus den alten Schluesseln uebernommen (DE und EN).
2. **Python:** `geteilt` in `BEREICHE` (`src/i18n/catalog.py`); keine neue Lade-Mechanik. Prod-Leserecht ist durch `src/` gegeben (deshalb nicht `internal/`).
3. **Go:** neue Datei `src/i18n/embed.go` (Go-Paket in `src/i18n`, Modul-Wurzel `go.mod` liegt im Repo-Root), `//go:embed messages/de/geteilt.json messages/en/geteilt.json`, exportiert ein `embed.FS`. **Nur** diese zwei Dateien, nicht `messages` ganz (sonst Python-Bereiche in Go). `internal/i18n` laedt den Standardkatalog aus beiden FS (kleiner Merge-Helfer, ca. 15-20 LoC; `loadFile`/`checkKey` unveraendert, Pfadlayout `messages/<lang>/<bereich>.json` passt).
4. **Suchkette:** `geteilt.fehler.` in `errorPrefixes` (`internal/i18n/errorbody.go`) und als Kopie im Waechtertest `internal/handler/fehlercode_katalog_waechter_test.go`.
5. **Scheibe 1 `kind_required`:** Python `send_outcomes` verweist fuer `kind_required` auf `geteilt.fehler.kind_required` (ueber den bestehenden `text_key`-Override). Die alten Schluessel `fehler.kind_required` (Go, `fehler.json` de/en) und `versand.ergebnis.kind_required` (Python, `versand.json` de/en) werden **geloescht**; Go-`duplicateCodes` erzwingt es, Behalten waere wieder eine zweite Quelle. Neuer Schluessel und Loeschung im selben Commit.
6. **Fixture** `send_detail_parity` bleibt als reiner Verhaltenswaechter (HTTP-Ausgabe beider Schichten = deutscher Wortlaut); der Hinweistext darin und in den beiden Verwender-Tests wird angepasst (kein Gleichlauf-Zwang mehr noetig, weil nur noch eine Quelle).
7. **Waechter:** Go-Test, dass der Bereich `geteilt` nicht unter `internal/i18n/messages` liegt (er darf nur aus dem `src`-FS kommen).
8. **ADR-0130** „Gemeinsamer Textkatalog Go/Python" schreibt ADR-0104 fort: Ausnahme von „je Schicht ein Katalog" fuer den Bereich `geteilt`; haelt fest, dass der Konventionssatz „Schluessel werden nie umbenannt oder geloescht" beim Umziehen nach `geteilt` nicht gilt; dokumentiert Deploy-Kopplung (Staging und Prod bauen Go und starten Python aus demselben Checkout/Commit). ADR-Index `docs/adr/README.md` und Rueckverweis in ADR-0104 (Zeile „Ergaenzt durch"). `docs/reference/i18n_konventionen.md`: Namensraeume-Tabelle nennt `geteilt` und die Regel „nur in `src/i18n/messages` pflegen".

### Out of Scope / Folgearbeit (eigene Issues, beim Abschluss anlegen)

- **Radar-Intensitaet:** `alarm.radar.intensitaet.*` (6 Schluessel) nach `geteilt.radar.intensitaet.*`; Python behaelt `hagel`, `regen`; Radar-Mail-Validator mitziehen.
- **MCP-Fehler:** `mcp.fehler.bis_vor_von` / `mcp.fehler.feld_unbekannt` (Go) und `api.fehler.mcp_*` (Python, `api/fehler.py` baut `api.fehler.{code}`) nach `geteilt.fehler.mcp_*`; Zuordnung noetig.
- Frontend-Katalog (`fehler.code.*`) bleibt ausgenommen.

### Betroffene Dateien

| Datei | Change | Beschreibung |
|---|---|---|
| `src/i18n/embed.go` | CREATE | bettet nur `geteilt.json` de/en als `embed.FS` ein |
| `internal/i18n/catalog.go` | MODIFY | Standardkatalog aus `internal/i18n/messages` plus `src`-FS laden |
| `internal/i18n/errorbody.go` | MODIFY | `geteilt.fehler.` in `errorPrefixes` |
| `src/i18n/catalog.py` | MODIFY | `geteilt` in `BEREICHE` |
| `src/services/send_outcomes.py` | MODIFY | `kind_required` -> `geteilt.fehler.kind_required` |
| `src/i18n/messages/{de,en}/geteilt.json` | CREATE | gemeinsame Quelle (2 Dateien) |
| `internal/i18n/messages/{de,en}/fehler.json` | MODIFY | `fehler.kind_required` entfernen (2 Dateien) |
| `src/i18n/messages/{de,en}/versand.json` | MODIFY | `versand.ergebnis.kind_required` entfernen (2 Dateien) |
| `tests/test_versand_zweisprachig.py` | MODIFY | Zeile 173-177 erwartet neuen Schluessel |
| `internal/i18n/uebersetzung_test.go` | MODIFY | Zeile 143 `Has("geteilt.fehler.kind_required")` |
| `tests/unit/test_i18n_katalog_paritaet.py` | MODIFY | Zeile 15-34 Bereichsliste um `geteilt` |
| `internal/i18n/katalog_paritaet_test.go` | MODIFY | Zeile 44 Praesenzliste; Paritaet `geteilt` de/en; neuer Waechter (nicht unter `internal/i18n/messages`) |
| `internal/handler/fehlercode_katalog_waechter_test.go` | MODIFY | Zeile 28 Kopie von `errorPrefixes` |
| `tests/fixtures/send_detail_parity/faelle.json` + Verwender-Tests | MODIFY | nur Hinweistext (Verhaltenswaechter) |
| `docs/adr/0130-gemeinsamer-textkatalog-go-python.md` | CREATE | neues ADR |
| `docs/adr/README.md`, `docs/adr/0104-zweisprachigkeit-de-en.md` | MODIFY | Index-Eintrag, Rueckverweis |
| `docs/reference/i18n_konventionen.md` | MODIFY | Namensraeume-Tabelle + Regel |

Hinweis Scoping: 5 Code-Dateien (Limit 4-5 erfuellt); die JSON-Dateien sind reine Daten, Tests und Doku zaehlen gesondert.

## Expected Behavior

- **Input:** Aufruf eines Versand-Endpunkts mit fehlender oder ungueltiger Briefing-Art (Go-API oder Python-Core direkt), Nutzersprache `de` oder `en`.
- **Output:** HTTP 400, Code `kind_required`, Text in Nutzersprache, im Deutschen byte-gleich zu heute, im Englischen ebenfalls unveraendert. Der Text stammt in beiden Schichten aus `geteilt.json`.
- **Side effects:** keine; keine Bestandsdaten, kein Datenmodell, keine neuen Berechtigungen. Alte Katalogschluessel entfallen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] GIVEN Go-Katalog mit eigenem `src`-FS (Testordner) WHEN der Text in `geteilt.json` geaendert wird THEN liefert Go `T(de, "geteilt.fehler.kind_required")` und `WriteError` den geaenderten Text (kein Mock, echter Katalog-FS).
- [ ] GIVEN Python-Katalog mit eigenem Katalogordner WHEN der Text in `geteilt.json` geaendert wird THEN liefert der Python-Fehlerkoerper `kind_required` den geaenderten Text.
- [ ] GIVEN geladene Kataloge beider Schichten WHEN Schluesselmengen verglichen werden THEN steht der kind_required-Text nur im Bereich `geteilt`, nicht in `fehler`/`versand` (Go bzw. Python).
- [ ] GIVEN `geteilt.json` de/en WHEN Parity-Tests laufen THEN gleiche Schluessel- und Platzhaltermengen in Go und Python; der Go-Standardkatalog enthaelt aus `src` nur `geteilt`-Schluessel.
- [ ] GIVEN eine `geteilt.json` unter `internal/i18n/messages` WHEN der Go-Waechtertest laeuft THEN schlaegt er fehl (Negativprobe im Testordner).
- [ ] GIVEN Fixture `send_detail_parity` WHEN Go-Endpoint und Python-Endpoint `kind_required` antworten THEN entspricht der Text jeweils dem Fixture-Wortlaut (bestehende Tests `tests/tdd/test_briefings_send_endpoint.py:417`, `internal/handler/briefing_send_test.go:514` bleiben gruen).
- [ ] ADR-Praesenz: `tests/test_adr_index_drift.py` gruen; `# doc-compliance-test` fuer ADR-0130, Rueckverweis in ADR-0104 und Konventionstabelle.
- [ ] Bestehende Tests angepasst (siehe Tabelle): `tests/test_versand_zweisprachig.py:173-177`, `internal/i18n/uebersetzung_test.go:143`, `tests/unit/test_i18n_katalog_paritaet.py:15-34`, `internal/i18n/katalog_paritaet_test.go:44`, `internal/handler/fehlercode_katalog_waechter_test.go:28`.

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter Nutzer mit Sprache Deutsch oder Englisch / When er ueber die Go-API einen Briefing-Versand ohne oder mit ungueltiger Briefing-Art ausloest / Then antwortet die API mit Status 400, Code `kind_required` und dem unveraenderten Wortlaut seiner Sprache (Deutsch byte-gleich zum bisherigen Text).
  - Test: Go-Handler-Test fuer Versand, Vorschau und Platzierungen mit Nutzer `de` und Nutzer `en`; Vergleich gegen Fixture `send_detail_parity` bzw. die bisherigen englischen Texte.

- **AC-2:** Given der Text in `geteilt.json` wird in einem Test-Katalogordner geaendert / When Go (`WriteError`) und Python (Fehlerkoerper) den Fehler `kind_required` erzeugen / Then geben beide Schichten den geaenderten Text aus, weil beide aus derselben Quelldatei lesen.
  - Test: Go-Test mit eigenem Katalog-FS und Python-Test mit eigenem Katalogordner, jeweils echter Katalog, kein Mock.

- **AC-3:** Given der Python-Core wird direkt (intern) aufgerufen / When ein Versand mit fehlender Briefing-Art gesendet wird und der Nutzer Englisch eingestellt hat / Then antwortet er mit Status 400, Code `kind_required` und dem englischen Text aus `geteilt.json`; fuer Deutsch mit dem deutschen Text.
  - Test: Python-Endpoint-Test (bestehende Versand-Tests) mit zwei Nutzern verschiedener Sprache.

- **AC-4:** Given die geladenen Standardkataloge von Go und Python / When ihre Schluesselmengen geprueft werden / Then kommt der Text von `kind_required` ausschliesslich unter `geteilt.fehler.kind_required` vor, und die alten Schluessel `fehler.kind_required` und `versand.ergebnis.kind_required` existieren in keiner Schicht mehr.
  - Test: Schluesselmengen-Test ueber die geladenen Kataloge beider Schichten.

- **AC-5:** Given die Bereichsdateien `geteilt.json` fuer `de` und `en` / When die Paritaetstests beider Schichten laufen / Then haben `de` und `en` dieselben Schluessel und Platzhalter, und der Go-Standardkatalog enthaelt aus dem `src`-Baum nur den Bereich `geteilt`, keinen Python-Bereich.
  - Test: `internal/i18n/katalog_paritaet_test.go` und `tests/unit/test_i18n_katalog_paritaet.py`.

- **AC-6:** Given eine Datei `geteilt.json` wird unter `internal/i18n/messages` abgelegt / When die Go-Tests laufen / Then schlaegt der Waechtertest fehl, damit der gemeinsame Bereich nur in `src/i18n/messages` gepflegt wird.
  - Test: Go-Test mit Negativprobe in einem temporaeren Katalogordner.

- **AC-7:** Given ADR-0130 wurde angelegt / When der ADR-Index und die Konventionsdokumente geprueft werden / Then ist ADR-0130 im Index eingetragen (`tests/test_adr_index_drift.py` gruen), ADR-0104 verweist darauf, und `docs/reference/i18n_konventionen.md` nennt den Bereich `geteilt` mit der Regel „nur in `src/i18n/messages` pflegen".
  - Test: `tests/test_adr_index_drift.py` plus Dokumentationstest mit `# doc-compliance-test` (reine Doku-Praesenz).

## Known Limitations

- Nur `kind_required` zieht um; Radar-Intensitaet und MCP-Fehler bleiben bis zu ihren Folge-Issues doppelt (ohne Gleichlauf-Waechter, wie bisher).
- `src/i18n` wird zum Go-Paket; Python ignoriert die `.go`-Datei. `go vet`/`go test ./...` sehen das neue Paket (ohne eigene Tests).

## Risiken

- Go-Build laeuft nur im vollen Checkout (CI `ci.yml:339`, Deploy aus demselben Baum): `src/` ist dort vorhanden. Ein Build mit abgeschnittenem Baum bricht ab.
- `duplicateCodes` schlaegt fehl, wenn der alte Go-Schluessel nicht im selben Commit entfernt wird.
- Deutsch byte-gleich: Text wird nur verschoben; Fixture-Tests beider Schichten und Golden-Tests sichern ihn.
- Verbleibende Kopie von `errorPrefixes` im Waechtertest muss mitgepflegt werden (sonst Drift-Fehlalarm).
- Frontend-Katalog hat denselben Text (`fehler.code.kind_required`) weiter separat, bewusst ausgenommen.

## Definition of Done

- AC-1 bis AC-7 durch die benannten Tests belegt, Go- und Python-Kernschicht grün (`go test ./...`, betroffene pytest-Dateien), alle 6 CI-Checks grün.
- Adversary-Verdict VERIFIED inkl. Mutations-Gegenprobe.
- Staging-Nachweis (`/e2e-verify`, de und en) für den Fehlerfall fehlende Briefing-Art; Prod-Deploy mit Selftest Exit 0.
- ADR-0130, ADR-Index, ADR-0104-Verweis und i18n-Konventionen aktualisiert; Folge-Issues Radar und MCP angelegt; #2993 geschlossen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0130 (neu, schreibt ADR-0104 fort)
- **Rationale:** Abweichung von „je Schicht ein Katalog" (ADR-0104) ist ADR-pflichtig; V4 (Quelle in `src/i18n/messages`, Go-Einbettung per `embed.go`) vermeidet Drift ohne Generator und ohne neue Leserechte auf dem Server.

## Changelog

- 2026-11-27: Initial spec created
