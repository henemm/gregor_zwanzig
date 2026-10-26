# Context: feat-2346-s4-last-briefing

## Request Summary
#2346 Scheibe S4 (Epic #2345, P6): `GET /api/next-briefings` liefert je Trip und Ortsvergleich zusätzlich `last_briefing`
(Zeitpunkt des letzten tatsächlich versendeten Briefings, `null` wenn nie), abgeleitet in Python aus dem Briefing-Log.
Die gemeinsame Startseiten-Kachel (`SubscriptionCard`) zeigt damit für beide kinds den letzten Versand statt „—".
ACs: AC-1 (vollständig), AC-13, AC-14, AC-15 der Spec `docs/specs/modules/feat_2346_cockpit_paritaet.md`.

## Related Files
| File | Relevance |
|------|-----------|
| `api/routers/internal.py:210` (`next_briefings`, `_je_objekt`) | Endpunkt (Python); Docstring kündigt `last_briefing` schon an; Antwort `{trips, compare}` |
| `src/services/briefing_log.py` | Schreibt `briefing_log.json` je Nutzer (`entity_id`, `entity_type` trip\|compare, `sent_at`, `channels`, `on_demand`); hat nur `append_briefing_log`, **keinen Lese-Helfer** |
| `src/services/next_briefing.py` | Ableitung „nächstes Briefing" — Vorbild für die neue Ableitung `last_briefing` |
| `internal/handler/proxy.go:238` `NextBriefingsProxyHandler` | Go-Proxy, `user_id` nur aus Auth-Kontext; reicht JSON durch (vermutlich keine Änderung nötig) |
| `internal/handler/briefing_history.go` | Go-Leseregel für den Log: Alt-Einträge ohne `entity_id/entity_type` ⇒ `entity_id := trip_id`, `entity_type := "trip"` — Python muss dieselbe Regel anwenden |
| `frontend/src/routes/_home/kachelVersand.ts` | `lastSent` ist beim Trip fest `null`, beim Vergleich aus `letzter_versand` — hier verdrahten |
| `frontend/src/routes/+page.server.ts:34-60` | lädt `next-briefings` bereits als Sammelaufruf; Typ `NextBriefings` lokal |
| `frontend/src/routes/+page.svelte` (Zeilen 60, 155, 227, 414, 648, 660) | reicht `nextBriefings` an Hero und Kacheln |
| `frontend/src/lib/components/shared/versand-tab/nextBriefingText.ts` | Typ `NextBriefing`, `formatNextBriefing` |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts:232` | `relativeLastSent(iso)` — Formatierer für den letzten Versand |
| `tests/tdd/test_next_briefing_endpoint.py` | bestehende Endpunkt-Tests (146 Z.), Erweiterungspunkt |

## Existing Patterns
- Ableitung im Python-Kern, nicht persistiert (ADR-0051 Regel 1); Fehler je Objekt über `_je_objekt` fail-soft.
- Nutzer-Isolation: `user_id` Pflichtparameter ohne Default; Go setzt sie aus dem Auth-Kontext (`appendUserID`).
- Schreibweg des Logs schreibt Trips weiter mit `trip_id`; Lese-Regel für Alt-Einträge liegt in Go (`briefing_history.go`).

## Dependencies
- Upstream: Briefing-Log (#2281), `next_briefing` (#1969, live seit 24.10.), `app.loader.get_data_dir`.
- Downstream: Startseite (Hero + Kacheln), eventuell weitere Konsumenten der Antwort (`naechstesBriefingLader`, Versand-Reiter — Antwort wird nur um ein Feld erweitert).

## Existing Specs
- `docs/specs/modules/feat_2346_cockpit_paritaet.md` — enthält S4 (Zeilen 144-150, AC-13/14/15, Teststrategie). Feldnamen von #1969 sind inzwischen verbindlich.
- `docs/specs/modules/feat_2281_vergleich_versand_historie.md` — Log-Format.

## Risks & Considerations
- **Mandantentrennung (AC-14):** Zwei-Nutzer-Test Pflicht; Log nur aus dem Verzeichnis von `user_id`; nie `"default"`.
- **Was zählt als „tatsächlich versendet"?** Log kennt `on_demand` (Handversand) und `kind`. Spec sagt „letztes tatsächlich versendetes Briefing" — Entscheidung in `/20-analyse`/Spec (Vorschlag: jeder Logeintrag zählt, auch Handversand, weil er zugestellt wurde; Alarme stehen im Alarm-Log, nicht hier).
- **Alt-Einträge** ohne `entity_id/entity_type`: Python-Ableitung muss Go-Leseregel spiegeln, sonst fehlt der letzte Versand bei älteren Trips.
- **Kaputte/fehlende Log-Datei:** fail-soft ⇒ `null`, nie 500; beschädigte Datei nicht verändern (Lesen ist rein lesend).
- **Performance:** Log einmal je Anfrage lesen (Sammelaufruf), nicht je Objekt.
- **Frontend:** `kachelVersand` ruft `relativeLastSent` bereits für den Vergleich; Quelle soll für beide kinds `last_briefing` sein (AC-1: kein `letzter_versand` mehr als Parallelquelle). Mutations-Gegenprobe: Quelle zurück auf `letzter_versand`/`null` muss einen benannten Test röten.
- Kein Schema-/Persistenzeingriff ⇒ `data_schema_backup` nicht relevant, solange nichts persistiert wird.
- Kein Mail-Inhalt betroffen ⇒ kein Mail-Validator nötig.

## Analysis

### Type
Feature (Scheibe S4 von #2346, Epic #2345 P6)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/briefing_log.py` | MODIFY | Lese-Helfer `letzte_briefings(user_id) -> {(entity_type, entity_id): sent_at_iso}`; Alt-Einträge ohne `entity_id/entity_type` ⇒ `trip_id`/`"trip"` (Spiegel der Go-Regel); lesend, defekte Datei ⇒ leer, nie schreiben/beiseitelegen |
| `api/routers/internal.py` | MODIFY | `next_briefings`: Log EINMAL je Anfrage lesen, `last_briefing` (ISO oder `null`) in jede Trip-/Vergleichs-Antwort einfügen; fail-soft |
| `frontend/src/routes/_home/kachelVersand.ts` | MODIFY | `lastSent` für beide kinds aus `nb.last_briefing` via `relativeLastSent`; `letzter_versand` als Quelle entfällt |
| `frontend/src/lib/components/shared/versand-tab/nextBriefingText.ts` | MODIFY | Typ `NextBriefing` um `last_briefing?: string \| null` |
| `tests/tdd/test_next_briefing_endpoint.py` (+ ggf. neue Datei nach Verhalten) | MODIFY/CREATE | AC-13, AC-14 (Zwei-Nutzer), Alt-Eintrag, defekte Datei |
| `frontend/src/routes/_home/__tests__/subscription_kachel_paritaet.test.ts` | MODIFY | AC-15: Trip-Kachel zeigt letzten Versand; Mutations-Gegenprobe Quelle |
| Go `proxy.go` | keine | reicht JSON unverändert durch |

### Scope Assessment
- Files: ~5 produktiv + 2–3 Tests
- Estimated LoC: +120/−10 (ohne Tests)
- Risk Level: LOW — rein lesende Ableitung, kein Schema, kein Mail-Inhalt

### Technical Approach
- Ableitung in Python aus `briefing_log.json` (nicht persistiert, ADR-0051 R1); maximales `sent_at` je `(entity_type, entity_id)`.
- Entscheidung „tatsächlich versendet": jeder Logeintrag zählt, auch Handversand (`on_demand`) — er wurde zugestellt; Alarme stehen im Alarm-Log und zählen nicht.
- Nutzer-Isolation über `get_data_dir(user_id)`; Zwei-Nutzer-Test Pflicht.
- Frontend: eine Quelle (`last_briefing`) für beide kinds; Mutations-Gegenprobe (Quelle zurück auf `letzter_versand`/`null` muss benannten Test röten).

### Dependencies
Briefing-Log #2281, `next_briefing` #1969, Go-Proxy unverändert, `relativeLastSent`.

### Open Questions
- [ ] Keine für den PO. (Handversand zählt mit — technische Entscheidung, in Spec festhalten.)
