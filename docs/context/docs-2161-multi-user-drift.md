# Context: docs-2161-multi-user-drift

## Request Summary
Issue #2161 (letztes offenes Sub-Issue von Epic #2138): Specs und Doku tragen noch
Single-User-Annahmen, die gegen ADR-0003 (Mandantentrennung) driften. Doku auf den
Multi-User-Stand bringen, inerte Validierung `preset.empfaenger` entschärfen,
`config.ini`-Erwähnungen bereinigen, PO-Entscheid zu Öffnung/Preismodell festhalten.

## Abgleich der Issue-Befunde mit `origin/main` (e574fd9ed, 2026-11-02)

| Befund im Issue | Stand heute |
|---|---|
| `inbound_command_channels.md` „Single-User: Sender muss mail_to …", `GZ_MAIL_TO` | **bereits behoben** (#2143/#2144); nur Zeile 920 erwähnt den alten Stand historisch — bleibt |
| `subscriptions_crud.md:35-36, 242-274, 307-309` — `"default"`, kein Locking „V1 Single-User" | **offen** |
| `weather_config_endpoints.md:32-33, 150, 160, 217-219` — dito | **offen** |
| `trip_command_processor.md:425` „Single-User only" | **offen** |
| `architecture.md` Premium-SMS „genau ein Premium-Nutzer" | **bereits behoben** (#2154/#2328, Zeile 355-368 beschreibt Historie korrekt) |
| `strategic-directions.md` ohne Entscheid zu Öffnung/Preismodell/Betreiberrolle | **offen**, braucht PO-Entscheid |
| `README.md:85`, `CLAUDE.md:21` „CLI > ENV > config.ini" | **offen**; `config.ini` wird von keinem Modul in `src/`/`api/` gelesen (grep leer) |
| `internal/handler/compare_preset.go:140-144` validiert inertes `empfaenger` | **offen** |

## Zusätzlich gefunden (nicht im Issue)
- `docs/reference/api_contract.md:1471-1472` — `userID hardcodiert auf "default" (V1)`, „Single-User V1"
- `docs/specs/web_ui.md:124, 160` — „Single-User MVP", „Keine Authentifizierung"
- `docs/specs/modules/sveltekit_setup.md:41, 383` — „Single-User, Credentials aus ENV"
- `docs/specs/_archive/...` — Archiv, bleibt unangetastet

## Related Files
| File | Relevance |
|------|-----------|
| docs/specs/modules/subscriptions_crud.md | `"default"`-Store-Aufrufe, Locking-Annahme |
| docs/specs/modules/weather_config_endpoints.md | dito |
| docs/specs/modules/trip_command_processor.md | Known Limitation „Single-User only" |
| docs/reference/api_contract.md | Notes Zeile 1471f; `empfaenger`-Validierungsregel Zeile 2714, 2961, 2982 |
| docs/specs/web_ui.md, docs/specs/modules/sveltekit_setup.md | MVP-Single-User-Aussagen |
| docs/project/strategic-directions.md | Ort für PO-Entscheid (Format: datierter Abschnitt) |
| README.md, CLAUDE.md | `config.ini`-Priorität |
| internal/handler/compare_preset.go:140 | inerte `empfaenger`-Validierung |
| internal/model/compare_preset.go:34 | Feld `Empfaenger` (persistiert, deprecated #1452) |
| internal/store/compare_preset.go:29 | nil→[]-Normalisierung (#1244) |
| frontend/src/lib/types.ts:692, compareEditorSave.ts:486 | Frontend sendet `empfaenger: []` |
| src/services/compare_preset_access.py:39-42 | Beleg: `empfaenger` inert seit #1452 |

## Existing Patterns
- Drift-Bereinigung in Specs: Aussage ersetzen + Verweis auf das schließende Issue (z. B. „seit #2158: …").
- Deprecated-Felder bleiben persistiert (Read-Modify-Write-Pflicht, CLAUDE.md „Daten-Schema-Reworks"); `api_contract.md:2538` markiert `empfaenger` bereits `@deprecated`.
- Locking im Go-Store existiert inzwischen (`internal/store/*_lock.go`, `LoadGroupsLocked` …, #2158/#1433).
- `strategic-directions.md`: datierte Abschnitte `## YYYY-MM-DD — Entscheid` mit „Was daraus folgt"/„Abgrenzung".

## Dependencies
- Upstream: ADR-0003, ADR-0066, ADR-0072, ADR-0084 (Einladungslinks), Ergebnisse der geschlossenen Epic-Issues.
- Downstream: `empfaenger` wird vom Frontend mitgeschickt (immer `[]` bei Neuanlage, Round-Trip bei Bestand); Entfernen aus dem Go-Modell würde Bestandswerte beim Speichern verwerfen.

## Existing Specs
- `docs/specs/modules/subscriptions_crud.md`, `weather_config_endpoints.md`, `trip_command_processor.md`, `inbound_command_channels.md`

## Risks & Considerations
- `empfaenger` aus dem Go-Modell entfernen = Bestandsdaten gehen beim nächsten Save verloren (inert, aber Verstoß gegen Merge-Pflicht) und Frontend-Typ müsste mit. Wahrscheinlich sinnvoller: nur die Validierung streichen, Feld bleibt deprecated persistiert → in Analyse entscheiden.
- Doku-Gates: `test_adr_index_drift.py`, CLAUDE.md-Budget (120 Zeilen/12 KB) bei Änderung an CLAUDE.md beachten.
- PO-Entscheid Öffnung/Preismodell ist eine Produktfrage → per `AskUserQuestion`, nicht selbst festlegen.
- Locking-Aussagen müssen gegen den tatsächlichen Code (welche Entitäten gelockt sind) geprüft werden, nicht pauschal „gelöst".

## Analysis

### Type
Doku-Drift-Bereinigung (Feature/Chore) plus eine kleine Go-Codeänderung. Kein Nutzer-Bug.

### Befunde, die gegen den ursprünglichen Plan sprechen
1. **`subscriptions_crud.md` beschreibt ein gelöschtes Modul.** `internal/handler/subscription.go` und `internal/model/subscription.go` sind mit `ba6fe60d0` (#1250/#1131) entfernt worden. Die Spec auf Multi-User umzuschreiben würde neue Drift erzeugen. Sie wird deshalb **als stillgelegt markiert**: `status: deprecated`, `updated` aktualisiert, Banner „Stillgelegt durch #1250 (Scheibe 0, ba6fe60d0)". Vorbild ist `docs/specs/web_ui.md`, die ebenfalls `status: deprecated` trägt und nicht verschoben wurde. Die Spec wird **nicht** nach `_archive/` verschoben: Darauf verweisen nur historische `docs/context/`-Dateien, und eine Verschiebung bringt nichts zusätzlich.
2. **`weather_config_endpoints.md`** nennt „3 Entitäten" mit Subscription und den Tag `subscription` und hat eine Known Limitation zu „Load-All + lineare Suche". Der Subscription-Teil fällt weg, Trip und Location werden auf den heutigen Code gebracht.
3. **`empfaenger` NICHT aus dem DTO nehmen** (bewusste Abweichung von der Erwartung im Issue). Begründung:
   - Der Handler dekodiert ohne `DisallowUnknownFields`, und der Store schreibt das Struct ohne Raw-Merge unbekannter Keys (`internal/store/compare_preset.go`, `NormalizeComparePreset`).
   - Würde das Feld aus `model.ComparePreset` entfernt, gingen Bestandswerte beim nächsten Speichern still verloren. Das verstößt gegen die Merge-Pflicht (CLAUDE.md „Daten-Schema-Reworks", #102).
   - Deshalb wird nur die inerte Validierung in `internal/handler/compare_preset.go:140-144` gestrichen, mit einem Code-Kommentar „inert seit #1452, nur noch round-getrippt". Das Feld bleibt `@deprecated` (api_contract:2538).
   - Die `empfaenger`-Validierungsregeln in `api_contract.md` (~2714, 2961, 2982) werden entfernt bzw. als „ignoriert, round-getrippt" markiert.
4. **`config.ini` wird nirgends gelesen.** Geprüft wurde breit: `configparser` und `.ini` in `src/`/`api/` liefern keine Treffer, `src/app/config.py` ist pydantic-Settings über ENV. Die Angabe „CLI > ENV > config.ini" wird zu „CLI > ENV" (`README.md:85`, `CLAUDE.md:21`). Die CLAUDE.md wird dadurch nur kürzer, das Budget-Gate ist unkritisch.
5. **`web_ui.md`** ist bereits `status: deprecated` (NiceGUI-Legacy). Ein Kurz-Banner reicht: „Single-User-Aussagen historisch, heute ADR-0003". **`sveltekit_setup.md`** hat `status: draft` und ist ein Migrations-Entwurf. Auch hier ein Banner: Auth läuft heute über die Go-API (Formular, Passkey, Magic-Link, Google-OAuth, ADR-0066/0078/0084), die Aussagen zu Single-User/ENV-Credentials sind überholt.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| docs/specs/modules/subscriptions_crud.md | MODIFY | Frontmatter `status: deprecated`, Banner „stillgelegt durch #1250" |
| docs/specs/modules/weather_config_endpoints.md | MODIFY | Subscription-Teil raus; `"default"` → `s.WithUser(...)` (#1395 S2/#1396 S1); Locking: Trip-PUT `lockBriefingOr503` + If-Match/ETag (#1395 S2, 603601ef0), Location-PUT `LockLocation` (#2158); Known Limitations aktualisiert |
| docs/specs/modules/trip_command_processor.md | MODIFY | „Single-User only" → Multi-User über `user_id` im Befehlskontext (#612, 64012565a) |
| docs/reference/api_contract.md | MODIFY | Notes ~1471f („default"/kein Locking) korrigieren; `empfaenger`-Validierungsregeln (~2714, 2961, 2982) entfernen bzw. als ignoriert markieren |
| docs/specs/web_ui.md, docs/specs/modules/sveltekit_setup.md | MODIFY | Abgelöst-Banner |
| docs/project/strategic-directions.md | MODIFY | Neuer datierter Abschnitt `## 2026-11-02 — Entscheid` zu Öffnung, Preismodell und Betreiberrolle (Inhalt nach PO-Antwort) |
| README.md, CLAUDE.md | MODIFY | „CLI > ENV" statt „CLI > ENV > config.ini" |
| internal/handler/compare_preset.go | MODIFY | Inerte `empfaenger`-Validierung streichen, Kommentar setzen |
| internal/handler/compare_preset_empfaenger_inert_test.go (o. ä.) | CREATE | Go-Test: PUT/POST mit `empfaenger: ["kein-at"]` → 2xx, Wert bleibt round-getrippt (Bestandsdaten bleiben erhalten); zwei Nutzer laut Multi-User-Pflicht |

Unverändert bleiben: `inbound_command_channels.md` (behoben in #2143/#2144; Zeile 920 ist Historie) und `architecture.md` Premium-SMS (behoben in #2154/#2328).

### Scope Assessment
- Files: ~10 (8 Doku, 1 Go-Code, 1 Go-Test)
- Estimated LoC: Code +~5/−5, Test +~60, Doku +~60/−40
- Risk Level: LOW. Die einzige Verhaltensänderung lockert eine Validierung auf einem Feld, das niemand mehr auswertet (`src/services/compare_preset_access.py:39-42`, #1452). Daten werden nicht entfernt.

### Technical Approach
1. Go: Validierungsschleife über `p.Empfaenger` entfernen, Feld und Normalisierung bleiben. Ein RED-Test belegt, dass heute ein Preset mit `empfaenger: ["x"]` mit 400 abgelehnt wird und danach gespeichert wird und den Wert zurückgibt.
2. Doku: jede Single-User-Aussage durch den Ist-Stand ersetzen, mit dem schließenden Issue (#1250, #1395, #1396, #2158, #612, #1452, ADR-0003). Bei überholten Specs nur ein Banner, kein Umschreiben.
3. `strategic-directions.md`: PO-Entscheid als datierter Abschnitt im bestehenden Format („Was daraus folgt" / „Abgrenzung").

### Belegter Ist-Zustand zu Öffnung/Preismodell (für den PO-Entscheid)
- Offene Registrierung mit Pflicht zur E-Mail-Bestätigung (ADR-0066).
- Level Free/Standard/Premium per Antrag (`internal/model/tier.go`, `tier_request_health`) oder per Admin-Einladung (ADR-0084).
- Admin-Rolle laut ADR-0078.
- Keine Bezahlfunktion im Code (grep auf stripe/paypal/payment leer).

### Dependencies
ADR-0003, ADR-0066, ADR-0078, ADR-0084; #1250 (Subscription-Stack entfernt); #1452 (`empfaenger` inert); #1395/#1396 (WithUser, ETag); #2158 (Schreibsperre); #612 (User-Kontext im Befehlsprozessor).

### Open Questions
- [x] PO-Entscheid (Henning, 2026-11-02, per AskUserQuestion): **Ist-Zustand festschreiben**. Offene Registrierung mit E-Mail-Bestätigung, Level Free/Standard/Premium per Antrag oder Admin-Einladung, kostenlos, Henning als Betreiber. Ein Bezahlmodell ist ausdrücklich kein Thema. So wird es als `## 2026-11-02 — Entscheid` in `strategic-directions.md` eingetragen.
