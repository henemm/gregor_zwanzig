---
entity_id: multi_user_doc_drift
type: refactor
created: 2026-11-02
updated: 2026-11-02
status: draft
version: "1.0"
workflow: docs-2161-multi-user-drift
tags: [docs, multi-user, adr-0003, epic-2138, issue-2161]
---

# Multi-User-Drift in Specs/Doku bereinigen + inerte empfaenger-Validierung streichen

## Approval

- [ ] Approved

## Purpose

Specs und Doku tragen noch Single-User-Annahmen ("default"-Nutzer, kein Locking, "CLI > ENV > config.ini"), die gegen ADR-0003 (Mandantentrennung) und den Code-Ist-Stand driften. Diese Spec bringt sie auf den heutigen Stand, haelt den PO-Entscheid zu Oeffnung/Preismodell fest (Issue #2161, letztes offenes Sub-Issue von Epic #2138) und streicht die wirkungslose Validierung `preset.empfaenger` in der Go-API.

## Source

- **File:** `internal/handler/compare_preset.go` (einzige Code-Aenderung); Doku-Dateien siehe Scope
- **Identifier:** `func validateComparePreset` (Schleife ueber `p.Empfaenger`, aktuell Zeilen 140-144)

> Schicht-Hinweis: Code-Aenderung ausschliesslich in der Go-API (`internal/handler/`). Kein Frontend, kein Python-Core. Das Feld `Empfaenger` bleibt in `internal/model/compare_preset.go`, im Store und im Frontend-Typ unveraendert.
>
> Querschnitt: Trip/Ortsvergleich-Teilung nicht betroffen (kein neuer Baustein). Mandantentrennung: der Go-Test laeuft mit zwei verschiedenen Nutzern. Kanaele: kein Briefing-/Alarm-Inhalt betroffen.

## Estimated Scope

- **LoC:** Code +~5/-5, Test +~80, Doku +~70/-40
- **Files:** 11 (9 Bestands-Doku-Dateien, 1 Go-Code, 1 Go-Test)
- **Effort:** low

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| internal/handler/compare_preset.go | MODIFY | Validierungsschleife ueber `p.Empfaenger` streichen, Kommentar "inert seit #1452, nur noch round-getrippt" |
| internal/handler/compare_preset_empfaenger_inert_test.go | CREATE | Go-Test echt gegen Handler+Store (temporaeres Datenverzeichnis), zwei Nutzer |
| docs/specs/modules/subscriptions_crud.md | MODIFY | `status: deprecated`, Banner "Stillgelegt durch #1250 (Scheibe 0, ba6fe60d0)", `updated` setzen |
| docs/specs/modules/weather_config_endpoints.md | MODIFY | Subscription-Teil raus; `"default"` durch `s.WithUser(...)` ersetzen; Locking-Stand korrekt; Known Limitations aktualisiert |
| docs/specs/modules/trip_command_processor.md | MODIFY | "Single-User only" durch Multi-User ueber `user_id` im Befehlskontext (#612) ersetzen |
| docs/reference/api_contract.md | MODIFY | Notes ~1471f korrigieren; `empfaenger`-Validierungsregeln (~2714, 2961, 2982) entfernen bzw. als ignoriert/round-getrippt markieren |
| docs/specs/web_ui.md | MODIFY | Abgeloest-Banner (Single-User-Aussagen historisch, heute ADR-0003) |
| docs/specs/modules/sveltekit_setup.md | MODIFY | Abgeloest-Banner (Auth heute ueber Go-API, ADR-0066/0078/0084) |
| README.md | MODIFY | Zeile 85 "CLI > ENV" statt "CLI > ENV > config.ini" |
| CLAUDE.md | MODIFY | Zeile 21 "CLI > ENV" statt "CLI > ENV > config.ini" (Budget-Gate unkritisch, Datei wird kuerzer) |
| docs/project/strategic-directions.md | MODIFY | Neuer Abschnitt `## 2026-11-02 — Entscheid` |

### Out of Scope

- `docs/specs/modules/inbound_command_channels.md` und `docs/features/architecture.md`: bereits behoben (#2143/#2144, #2154/#2328), bleiben unveraendert (Zeile 920 in inbound_command_channels.md ist bewusste Historie).
- `docs/specs/_archive/`: bleibt unangetastet.
- Das Feld `empfaenger` wird NICHT aus Go-Modell, Store, DTO oder Frontend entfernt (sonst gingen Bestandswerte beim naechsten Speichern verloren, Verstoss gegen die Merge-Pflicht #102).
- `api_contract.md` Zeile ~3021 ("default: default for V1" bei einem `user_id`-Parameter) gehoert nicht zu dieser Spec, ausser der Developer findet sie beim Pruefen als eindeutig dieselbe Drift; dann Hinweis im Validate-Bericht statt stillem Mitaendern.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0003 | ADR | Mandantentrennung: Referenz fuer alle Doku-Korrekturen |
| ADR-0066 | ADR | Offene Registrierung mit E-Mail-Bestaetigung (Entscheid-Abschnitt) |
| ADR-0078 | ADR | Admin-Rolle (Entscheid-Abschnitt) |
| ADR-0084 | ADR | Einladungslinks / Level per Admin-Einladung |
| #1250 | Issue | Subscription-Stack entfernt (ba6fe60d0) |
| #1452 | Issue | `empfaenger` inert (`src/services/compare_preset_access.py:39-42`) |
| #1395 / #1396 | Issue | `WithUser`, Trip-Sperre `lockBriefingOr503`, If-Match/ETag |
| #2158 | Issue | Schreibsperre `LockLocation` (`internal/store/location_lock.go`) |
| #612 | Issue | User-Kontext im Befehlsprozessor |
| internal/model/compare_preset.go, internal/store/compare_preset.go | module | Feld `Empfaenger` und nil-zu-[]-Normalisierung bleiben |

## Implementation Details

**Go (verifiziert):** `validateComparePreset` in `internal/handler/compare_preset.go` lehnt aktuell jeden `empfaenger`-Eintrag ohne `@` mit 400 ab. Das Feld wird seit #1452 von keinem Service mehr gelesen (Empfaenger kommen aus dem Nutzerprofil). Die Schleife entfaellt, ein Kommentar benennt den Grund. Handler dekodiert ohne `DisallowUnknownFields`, der Store schreibt das Struct unveraendert; der Wert bleibt damit round-getrippt.

**Locking-Ist-Stand (aus dem Code, nicht pauschal "geloest"):**
- Trip-Schreibpfade (Update, State, weitere Trip-Handler in `internal/handler/trip.go`) und `weather_config.go` (Trip-Config) nutzen `lockBriefingOr503`; PUT mit optionalem `If-Match` (`ifMatchAllows`, `internal/handler/etag.go`). Ohne `If-Match`-Header ist die Pruefung bewusst nicht scharf.
- Location-Schreibpfade (`internal/handler/location.go`, `weather_config.go`) nehmen `s.LockLocation(id)` (#2158).
- Weitere Locks existieren im Store (`address_lock.go`, `quota_lock.go`, `sessions_lock.go`, `briefing_lock.go`); die Doku behauptet nur, was oben belegt ist.

**Doku-Regeln:**
1. Aussage ersetzen durch den Ist-Stand plus Verweis auf das schliessende Issue ("seit #...").
2. Ueberholte Specs (`subscriptions_crud.md`, `web_ui.md`, `sveltekit_setup.md`) nur mit Banner, nicht umschreiben; `subscriptions_crud.md` bleibt am Ort (kein Verschieben nach `_archive/`).
3. `config.ini`: kein Modul in `src/`/`api/` liest sie (`src/app/config.py` ist pydantic-Settings ueber ENV), daher "CLI > ENV".
4. `strategic-directions.md`: Abschnitt `## 2026-11-02 — Entscheid` im bestehenden Format mit Unterabschnitten "Was daraus folgt" und "Abgrenzung". Inhalt (PO-Entscheid Henning, 2026-11-02, per AskUserQuestion): Ist-Zustand wird festgeschrieben. Offene Registrierung mit E-Mail-Bestaetigung; Level Free/Standard/Premium per Antrag oder Admin-Einladung; kostenlos; Henning ist Betreiber; ein Bezahlmodell ist ausdruecklich kein Thema (im Code keine Bezahlfunktion).

## Expected Behavior

- **Input:** POST/PUT `/api/compare-presets` mit `empfaenger: ["kein-at"]` (ansonsten gueltiges Preset).
- **Output:** 2xx statt 400; GET liefert `empfaenger: ["kein-at"]` unveraendert zurueck.
- **Side effects:** Keine. Es werden keine Daten entfernt; die Doku-Aenderungen haben keine Laufzeitwirkung.

## Test Plan

### Automated Tests (TDD RED)

Datei: `internal/handler/compare_preset_empfaenger_inert_test.go` (echt gegen Handler+Store mit `t.TempDir()`-Datenverzeichnis, kein Mock-Theater; Aufbau analog der bestehenden `compare_preset_*_test.go`).

- [ ] Test 1: GIVEN Nutzer A, gueltiges Preset mit `empfaenger: ["kein-at"]` / WHEN POST / THEN nicht 400 (2xx) und Antwort enthaelt den Wert. Heute RED (400).
- [ ] Test 2: GIVEN gespeichertes Preset von Nutzer A / WHEN PUT mit `empfaenger: ["kein-at", "a@b.de"]` / THEN 2xx und anschliessendes GET liefert beide Werte round-getrippt.
- [ ] Test 3: GIVEN zwei Nutzer A und B, beide mit eigenem Preset (A mit `empfaenger: ["kein-at"]`) / WHEN B sein Preset listet und liest / THEN B sieht weder A's Preset noch A's `empfaenger`-Wert; A's Wert bleibt unveraendert.
- [ ] Test 4: GIVEN Preset ohne `empfaenger` / WHEN POST / THEN 2xx, Antwort liefert `[]` (nil-zu-[]-Normalisierung bleibt, kein Regress).

Doku-Pruefungen: kein eigener Test; im Validate-Schritt per `grep` (siehe jeweiliger AC). Nur falls ein Gate das verlangt, als `# doc-compliance-test` markieren.

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter Nutzer mit gueltigem Compare-Preset / When er per POST oder PUT `empfaenger: ["kein-at"]` sendet / Then wird das Preset nicht mehr mit 400 abgelehnt, sondern gespeichert, und ein anschliessendes GET liefert den Wert unveraendert zurueck (Bestandsdaten bleiben erhalten).
  - Test: Go-Test Test 1/2 in `compare_preset_empfaenger_inert_test.go`; vorher rot (400), nachher gruen.

- **AC-2:** Given zwei verschiedene Nutzer A und B mit je eigenen Compare-Presets, A mit `empfaenger: ["kein-at"]` / When B seine Presets abruft / Then sieht B weder A's Preset noch A's `empfaenger`-Wert, und A's Wert bleibt unveraendert gespeichert.
  - Test: Go-Test Test 3 (Mandantentrennung mit zwei Nutzern, `user_id` aus dem Auth-Kontext, nie "default").

- **AC-3:** Given die Spec `docs/specs/modules/subscriptions_crud.md` beschreibt das mit #1250 entfernte Modul / When ein Leser sie oeffnet / Then steht im Frontmatter `status: deprecated` und ganz oben ein Banner "Stillgelegt durch #1250 (Scheibe 0, ba6fe60d0)"; die Datei liegt weiter in `docs/specs/modules/`.
  - Test: Validate-Schritt per `grep -n "status: deprecated\|Stillgelegt durch #1250"` auf die Datei; Treffer in Frontmatter und Banner.

- **AC-4:** Given die Spec `weather_config_endpoints.md` / When ein Leser Scope, Ablauf und Known Limitations liest / Then kommen weder `"default"` als userID noch Subscription (Entitaet, Tag) noch "V1 Single-User" vor, der Ablauf nennt `s.WithUser(...)`, und die Locking-Aussage entspricht dem Code (Trip-PUT `lockBriefingOr503` mit optionalem If-Match/ETag, Location-PUT `LockLocation` seit #2158).
  - Test: Validate-Schritt per `grep -n -i "\"default\"\|subscription\|Single-User"` ohne Treffer in aktiven Aussagen; Gegenpruefung der Locking-Aussage gegen `internal/handler/weather_config.go`.

- **AC-5:** Given die Spec `trip_command_processor.md` / When ein Leser die Known Limitations liest / Then steht dort nicht mehr "Single-User only", sondern dass Befehle ueber `user_id` im Befehlskontext mandantengetrennt verarbeitet werden (seit #612).
  - Test: Validate-Schritt per `grep -n "Single-User only"` ohne Treffer; neue Aussage mit Verweis auf #612 vorhanden.

- **AC-6:** Given `docs/reference/api_contract.md` / When ein Leser die Notes zu Trip/Location-Config (~Zeile 1471f) und die `empfaenger`-Regeln (~2714, 2961, 2982) liest / Then fehlen "userID hardcodiert auf default (V1)" und "Kein File-Locking", und `empfaenger` ist nirgends mehr als "muss `@` enthalten" validiert, sondern als ignoriert und round-getrippt (`@deprecated` #1452) beschrieben.
  - Test: Validate-Schritt per `grep -n "hardcodiert auf\|Kein File-Locking\|muss .@. enthalten\|contains .@." docs/reference/api_contract.md` ohne Treffer in den genannten Stellen.

- **AC-7:** Given `docs/specs/web_ui.md` und `docs/specs/modules/sveltekit_setup.md` mit Single-User-Aussagen / When ein Leser sie oeffnet / Then steht am Dateianfang je ein Abgeloest-Banner: bei web_ui.md "Single-User-Aussagen historisch, heute ADR-0003", bei sveltekit_setup.md "Auth laeuft heute ueber die Go-API (ADR-0066/0078/0084), Single-User-/ENV-Credentials-Aussagen sind ueberholt".
  - Test: Validate-Schritt per `grep -n -i "abgeloest\|abgelöst" ` auf beide Dateien; je ein Treffer im Kopfbereich.

- **AC-8:** Given `README.md` und `CLAUDE.md` nennen die Konfigurations-Prioritaet / When ein Leser sie liest / Then steht dort "CLI > ENV" ohne `config.ini`, und `CLAUDE.md` bleibt innerhalb des Budgets (<=120 Zeilen, <=12 KB).
  - Test: Validate-Schritt per `grep -n "config.ini" README.md CLAUDE.md` ohne Treffer; `uv run pytest tests/test_claude_md_budget.py` gruen.

- **AC-9:** Given `docs/project/strategic-directions.md` / When ein Leser sie oeffnet / Then enthaelt sie den Abschnitt `## 2026-11-02 — Entscheid` mit dem PO-Entscheid (offene Registrierung mit E-Mail-Bestaetigung, Level Free/Standard/Premium per Antrag oder Admin-Einladung, kostenlos, Henning als Betreiber, kein Bezahlmodell) sowie den Unterabschnitten "Was daraus folgt" und "Abgrenzung".
  - Test: Validate-Schritt per `grep -n "## 2026-11-02 — Entscheid\|Was daraus folgt\|Abgrenzung"` auf die Datei; alle drei Treffer im neuen Abschnitt.

- **AC-10:** Given die Aenderungen sind umgesetzt / When die Kern-Tests der betroffenen Go-Pakete und `tests/test_claude_md_budget.py` sowie `tests/test_adr_index_drift.py` laufen / Then sind alle gruen, und `inbound_command_channels.md`, `architecture.md` und `docs/specs/_archive/` sind unveraendert (`git diff --stat` ohne diese Pfade).
  - Test: `go test ./internal/handler/...` plus die beiden Python-Doku-Gate-Tests; `git diff --stat` im Validate-Schritt.

## Known Limitations

- `empfaenger` bleibt als deprecated Feld im Modell und im Frontend-Typ; ein spaeteres Entfernen braucht eine eigene Migration mit Merge fuer Bestandsdaten.
- Doku-Aenderungen werden nicht durch automatisierte Inhaltstests abgesichert (Dateiinhalt-Checks sind laut Test-Politik kein Verhaltensnachweis); die Pruefung erfolgt manuell per grep im Validate-Schritt.
- Die Locking-Aussagen beschreiben den Stand am 2026-11-02; ohne `If-Match`-Header ist die Versionspruefung bewusst nicht scharf.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (Referenz: ADR-0003, ADR-0066, ADR-0078, ADR-0084)
- **Rationale:** Es wird kein Architektur-Entscheid geaendert, nur Doku an bestehende ADRs angeglichen und eine inerte Validierung entfernt. Der Produkt-Entscheid zu Oeffnung/Preismodell steht als datierter Abschnitt in `strategic-directions.md`, nicht als ADR.

## Changelog

- 2026-11-02: Initial spec created (Issue #2161, Epic #2138)
