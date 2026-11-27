# Kontext: feat-2993-kind-required-katalog

## Request Summary

Issue #2993 (Folge aus Paritäts-Bestandsaufnahme #1986, Liste `docs/context/feature-1986-paritaets-bestandsaufnahme.md` Z. 49, Punkt 8):
Der Fehlertext zum Code `kind_required` („Briefing-Art fehlt oder ist ungültig (erlaubt: route, vergleich)" / EN „Briefing kind is missing or invalid (allowed: route, vergleich)") steht in mehreren Katalogen. Ziel: eine Quelle; der Paritätstest (geteilte Fixture) entfällt oder bleibt reiner Regressionswächter. Kein Ausfall, priority:medium.

## Wo der Text heute steht (Kopien)

| # | Ort | Schlüssel | Wer liest |
|---|---|---|---|
| 1 | `internal/i18n/messages/{de,en}/fehler.json:10` | `fehler.kind_required` | Go `WriteError(…, "kind_required")` in `internal/handler/briefing_send.go:40`, `briefing_preview.go:28`, `placements.go:53` |
| 2 | `src/i18n/messages/{de,en}/versand.json:24` | `versand.ergebnis.kind_required` | Python `services/send_outcomes.py:18` (`SEND_OUTCOMES`, `error_body`) → `api/routers/briefings_send.py:126`, `api/routers/placements.py:46,67,89` |
| 3 | `frontend/src/lib/i18n/messages/{de,en}/fehler.json:22` | `fehler.code.kind_required` | `frontend/src/lib/i18n/fehlerCode.ts` (`fehlerTextFuerCode`: Code → Katalogtext, generischer Mechanismus für alle Go-Codes, #2660) |
| 4 | `tests/fixtures/send_detail_parity/faelle.json` | `kind_required` | nur Tests: `tests/tdd/test_briefings_send_endpoint.py:417` (Python-Seite) und `internal/handler/briefing_send_test.go:514` (Go-Seite), #2280 F004 |

Sonderfall: `api/routers/validator.py:388` wirft `HTTPException(detail="kind_required")` (Code als detail, kein Katalogtext).

## Erreichbarkeit (wichtig für die Analyse)

- Go prüft `kind` **vor** dem Proxy (`isValidBriefingKind`, `internal/handler/briefing_subscription.go:27`) in Send, Preview und Placements. Ein Nutzer über die Go-API bekommt `kind_required` immer aus Kopie 1 (Go-Katalog), Python wird nicht gerufen (`py.count() == 0` im Go-Test).
- Python-Kopie 2 wird nur erreicht, wenn der Python-Core direkt (intern, Port 8000) ohne/mit falschem `kind` gerufen wird — für Nutzer praktisch unerreichbar, aber von mehreren Python-Tests als Vertrag geprüft (`test_briefings_send_endpoint.py:124-151`, `test_3304_placements_vorschau.py:292-302`, `test_3237_placements_aus_grundauswahl.py:362`, `test_placements_tabelle_endpoint.py:664`, `test_versand_zweisprachig.py:174-176`).
- Frontend-Kopie 3 übersetzt den Code clientseitig; sie ist Teil des generischen Musters „jeder Go-Code hat `fehler.code.<code>`" (#2660), nicht spezifisch für diesen Fall.

## Existing Patterns

- i18n-Konventionen `docs/reference/i18n_konventionen.md`: je Schicht eigener Katalog (Go `internal/i18n/messages`, Python `src/i18n/messages`, Frontend `frontend/src/lib/i18n/messages`); „Nie zwei Schlüssel für denselben Text" (Z. 36) gilt innerhalb einer Schicht. Paritätstests je Schicht (Z. 40). Kein bestehender Mechanismus, dass eine Schicht den Katalog einer anderen liest.
- Bestandsaufnahme #1986 (Z. 52): Python↔Go gilt grundsätzlich als „begründet getrennt — zwei Prozesse/Sprachen, Fixture ist der Zwang". `kind_required` steht dort trotzdem in der Zusammenführungsliste („mittelfristig").
- Weitere Go↔Python-Textgleichheiten existieren (Radar-Intensität `alarm.radar.intensitaet.*`, `mcp.fehler.*` ↔ `api.fehler.mcp_*`) — nicht Teil dieses Issues.
- Vorbild „ein Baustein": `services/send_outcomes.py` ist bereits die eine Python-Zuordnung Code → (Status, Schlüssel), geteilt von Trip und Vergleich.

## Lösungsrichtungen für die Analyse (noch nicht entschieden)

A. **Python verzichtet auf eigenen Text für `kind_required`:** der Fall ist nur ohne Go erreichbar. Python antwortet weiter mit Code `kind_required`, Status 400, aber der Text wird nicht mehr im Python-Katalog gepflegt (z. B. Go bleibt einzige Textquelle). Problem: Python-`error_body` braucht für jeden Code einen Katalogtext; mehrere Python-Tests prüfen `detail`.
B. **Go reicht `kind`-Prüfung an Python durch** (Go validiert nicht mehr selbst): Go-Kopie entfällt für Send — aber Preview und Placements nutzen denselben Go-Text, die Kopie bliebe.
C. **Eine Datei, beide lesen:** z. B. Python lädt den Go-Schlüssel `fehler.kind_required` aus `internal/i18n/messages` — neuer schichtübergreifender Mechanismus, bricht Konvention „je Schicht ein Katalog".
D. **Begründet getrennt belassen**, Fixture als Zwang behalten, Issue mit Begründung schließen (Bestandsaufnahme-Grundsatz Python↔Go).

## Dependencies / Dependents

- Go: `internal/i18n` (embed, Parität de/en), `internal/handler/httperr.go` (`WriteError`), Hardcode-Wächter `internal/i18n/hardcode_guard_test.go`.
- Python: `src/i18n` Loader + Paritätstests (`tests/unit/test_i18n_katalog_paritaet.py` u. a.), `send_outcomes.py` (Vokabular-Test `_vokabular()` in `test_briefings_send_endpoint.py` erwartet alle `hv.ERWARTETE_CODES` im Dict).
- Frontend: `fehlerCode.ts`, `deutsch_unveraendert.test.ts:400` (Golden-Liste der DE-Texte).
- Specs: `docs/specs/modules/feat_2280_handversand_endpoint.md:182` (dokumentiert die Fixture-Lösung), i18n-Specs #2660/#2671/#2675.
- ADR-0104 (Zweisprachigkeit), ADR-0127 (Ein Katalog — betrifft Metrik-Wissen, nicht Fehlertexte, aber gleicher Geist).

## Risks

- Deutsch muss byte-gleich bleiben (Golden-Tests in allen Schichten).
- Ein schichtübergreifender Katalog-Mechanismus (Variante C) wäre eine Entscheidung über das i18n-Datenmodell → ADR-pflichtig, Scope wächst.
- Tests, die `detail` des direkten Python-Aufrufs prüfen, müssen konsistent angepasst werden; kein Verlust der Zusicherung „Go-Nutzer sieht Katalogtext in seiner Sprache".
- Frontend-Kopie folgt einem generischen Muster für alle Go-Codes; sie anzufassen wäre außerhalb des Scopes.

## Analysis

**Type:** Feature (Aufräumen/Zusammenführen), kein Bug.

### Befunde (gegen Code geprüft, Plan-Agent + eigene Lektüre)

- Go braucht `kind` selbst, an **12 Stellen**: `briefing_send.go:40`, `briefing_preview.go:28`, `placements.go:53,245`, `briefing_history.go:47`, `briefing_subscription.go:47,146,163,223` u. a. In `placements.go` wählt `kind` zwischen `LoadTrip` und `LoadComparePreset` im nutzergebundenen Store; im Versand geht `report_type` nur bei `route` mit. Go kann die Prüfung also nicht an Python abgeben.
- `forwardSend` (`send_proxy.go:25-54`) reicht Python-Status und -Body unverändert durch; der Python-Zweig `kind_required` ist trotzdem für Nutzer unerreichbar, weil Go vorher antwortet (Go-Test prüft `py.count()==0`).
- Python prüft `kind` an 4 Stellen (`briefings_send.py:125`, `placements.py:45,66,88`) mit einheitlichem `_error` → `SEND_OUTCOMES` → Katalog `versand.ergebnis.kind_required` (Nutzersprache). Abwehr bei direktem internem Aufruf (Port 8000).
- Kein Laufzeit-Mechanismus, der Python den Go-Katalog lesen lässt; Deploy-Kopplung unbelegt.
- Bestandsaufnahme #1986 führt das Paar unter „Zusammenführbar" (Z. 49, Punkt 8, „mittelfristig"), nennt aber Python↔Go-Paare sonst „begründet getrennt, Fixture ist der Zwang" (Z. 52).

### Varianten

| Variante | Dateien | LoC | Risiko | Doppelung weg? |
|---|---|---|---|---|
| A: Python ohne eigenen Text | 4–6 | ~-60/+40 | Mittel: `error_body` braucht für jeden Code Katalogtext, Sonderpfad nötig; 5 Py-Tests prüfen `detail` | nur Text; Prüfung bleibt doppelt |
| B: Go prüft nicht mehr | 3+ Dateien, 12 Stellen | ~200+ | Hoch: Go braucht `kind` fürs Routing; Go-Schlüssel bleibt | nein |
| C: ein schichtübergreifender Textkatalog (Python liest Go-Datei o. ä.) | 6–8 + ADR | ~150–250 | Hoch: neues i18n-Datenmodell, ADR-pflichtig, Laufzeit-Kopplung | Text ja, neue Kopplung |
| D: begründet getrennt, Fixture-Test als Regressionswächter, Doku-Vermerk, Issue schließen | 1–2 | ~10–20 | Niedrig | nein, aber erzwungen gleich |
| E: FastAPI `Literal` statt eigener Prüfung | 3 + 6 Tests | ~80 | Mittel: 422 im FastAPI-Format, zweites Fehlerformat | Text ja, Vertrag bricht |

### Empfehlung

**D.** Zwei Prozesse prüfen je ihre eigene Eingangsgrenze; Go muss `kind` zum Routing kennen, Python schützt direkte interne Aufrufe. Nutzer sehen nur den Go-Text. Ein echtes Zusammenführen geht nur über C (neuer schichtübergreifender Katalog, ADR), Aufwand ohne Nutzwirkung. Der vorhandene Fixture-Test bleibt als Regressionswächter; i18n-Konventionen erhalten einen Satz „Go↔Python-Textgleichheit wird per geteilter Fixture erzwungen".

### Open Questions

- **PO:** Weicht vom Ziel des Issues (Zusammenführen) und vom Verdikt „zusammenführbar" in #1986 ab → Produkt-Zielkonflikt, PO-Entscheidung D vs. C (C dann als eigenes ADR-Ticket).

### PO-Entscheidung 2026-11-27

PO wählt **„Gemeinsamer Katalog" (Variante C)** statt D. Umsetzung als eigenes ADR-first-Ticket **#3444** („Ein Textkatalog für Go und Python"); `kind_required` ist dort die erste Scheibe. #2993 geht darin auf und wird geschlossen; dieser Workflow endet ohne Code-Änderung.
