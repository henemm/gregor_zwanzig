# Context: feat-3327-archiv-seed

## Request Summary
Das Funktionsseiten-Bild `archiv` zeigt ein leeres Archiv. Der Prüfkonto-Seed soll idempotent einen
zweiten, fiktiven Trip anlegen und archivieren; danach Archiv-Bild DE+EN neu aufnehmen, Alt-Text und
Runbook nachziehen (Issue #3327, Teil von #3318).

## Related Files
| File | Relevance |
|------|-----------|
| `scripts/staging_pruefkonto_mockupdaten.py` | Seed; `fuehre_seed` (Z. 507), `sichere_datensatz` (Z. 401, GET→POST/PUT mit `_merge`), `soll_trip` (Z. 252) |
| `tests/tdd/test_staging_pruefkonto_mockupdaten.py` | Fake-Go-API (`_crud`, `_trip_merge_wie_go` Z. 312); braucht Route `PATCH /api/trips/{id}/state` |
| `internal/handler/trip.go` Z. 625–700 | `UpdateTripStateHandler`: Body `{"archived": true}` setzt `archived_at=now`; `{"state":...}` wirkt nicht |
| `internal/handler/trip.go` Z. 293 | PUT ohne `archived_at` auf archivierten Trip = Reaktivierung (Quote geprüft) → Merge muss `archived_at` erhalten |
| `frontend/src/routes/archiv/+page.server.ts` | Archiv listet Trips mit `archived_at != null`, Detail „N Etappen", Datum = `archived_at[:10]` |
| `frontend/src/routes/trips/+page.server.ts:20` | Trip-Liste blendet archivierte Trips aus |
| `scripts/funktionen_screenshots.py` Z. 278 | `--nur archiv` nimmt `/archiv` auf (max_hoehe 440) |
| `frontend/src/lib/i18n/messages/{de,en}/funktionen.json:140` | Alt-Text `funktionen.bild.archiv.alt` |
| `docs/runbooks/funktionen_screenshots.md` Z. 60–87 | Sichtprüfungs-Tabelle (Zeile `archiv`) und Abschnitt „Bekannte Schwäche Archiv-Bild" |
| `docs/runbooks/staging_pruefkonto_seed.md`, `docs/specs/modules/feat_2967_pruefkonto_mockupdaten.md` | Seed-Runbook/Spec, Bestand des Prüfkontos beschreiben |

## Existing Patterns
- Feste eigene IDs mit Präfix `gz2967-…`, Upsert per `sichere_datensatz` (GET 404 → POST, sonst PUT nur bei Abweichung, `_merge` = `{**ist, **soll}`).
- `_merge` erhält Fremdfelder wie `archived_at`, solange `soll` sie nicht enthält → Idempotenz: Zustand-PATCH nur, wenn `archived_at` fehlt.
- Fake-API bildet Go-Verhalten nach (`_trip_merge_wie_go`), PUT ersetzt (RMW ist Client-Pflicht).

## Dependencies
- Upstream: Go-API `/api/trips`, `/api/trips/{id}/state`; Tarif Premium vor Anlage (Quote).
- Downstream: Elementlisten-Abgleich #2913 nutzt `ELEMENTLISTE_TRIP_ID` (nur GR221-Hub); Trip-Liste filtert archivierte aus → kein Einfluss auf Trip-Liste. Cockpit zeigt beendete Trips nicht. Archiv-Seite zeigt künftig einen Eintrag.

## Risks & Considerations
- PUT auf den archivierten Trip ohne `archived_at` würde ihn reaktivieren → Test, dass zweiter Lauf keinen Schreibzugriff/keine Reaktivierung erzeugt.
- Versand: fiktiver Trip mit Etappen in der Vergangenheit + archiviert → kein Briefing-Versand.
- Nur fiktive Daten (öffentliches Repo); nie PO-Trips berühren.
- Screenshot + Sichtprüfung gegen Staging (Seed läuft auf dem Host gegen Staging).

## Analysis

### Type
Feature (Prüfdaten/Doku, kein Produktverhalten geändert)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/staging_pruefkonto_mockupdaten.py` | MODIFY | Konstanten `ARCHIV_TRIP_ID = "gz2967-archiv-…"`, Name/Etappen (fiktiv, 2–3 Etappen in der Vergangenheit); `soll_archiv_trip()`; Methode `sichere_archiviert(trip)` (PATCH `/api/trips/{id}/state` `{"archived": true}` nur wenn `archived_at` fehlt); Aufruf in `fuehre_seed` nach dem Haupt-Trip (nach Tarif) |
| `tests/tdd/test_staging_pruefkonto_mockupdaten.py` | MODIFY | Fake-Go-API: Route `PATCH /api/trips/{id}/state` (setzt/entfernt `archived_at`), PUT-Reaktivierung wie Go (fehlt `archived_at` im Body ⇒ entfernt); Tests: erster Lauf archiviert, zweiter Lauf schreibt nichts und reaktiviert nicht, Haupt-Trip bleibt aktiv, Archiv-Trip nachträglich verändert (Soll-Abweichung) ⇒ PUT behält `archived_at` |
| `frontend/src/lib/i18n/messages/de/funktionen.json`, `en/funktionen.json` | MODIFY | Alt-Text `funktionen.bild.archiv.alt` an Bildinhalt (ein archivierter Trip mit Etappenzahl und Datum) |
| `frontend/static/…/archiv*.png` (DE+EN, Pfad laut `funktionen_screenshots.py`) | MODIFY | Neu aufgenommen per `--nur archiv` gegen Staging nach Seed-Lauf |
| `docs/runbooks/funktionen_screenshots.md` | MODIFY | Sichtprüfungszeile `archiv` aktualisieren, Abschnitt „Bekannte Schwäche Archiv-Bild" entfernen/ersetzen |
| `docs/runbooks/staging_pruefkonto_seed.md`, `docs/specs/modules/feat_2967_pruefkonto_mockupdaten.md` | MODIFY | Bestand des Prüfkontos um archivierten Trip ergänzen |

### Scope Assessment
- Files: ~7 (+2 Bilddateien)
- Estimated LoC: +~90 / -~10 (Seed ~30, Tests ~50, Doku/Texte ~20)
- Risk Level: LOW — nur Staging-Prüfkonto, feste eigene IDs, keine Produktlogik

### Technical Approach
1. Archiv-Trip über den bestehenden Upsert `sichere_datensatz("/api/trips", soll_archiv_trip())` anlegen. `_merge` = `{**ist, **soll}` erhält `archived_at` aus dem Ist-Stand, solange `soll` es nicht enthält ⇒ kein Reaktivieren (Go `trip.go:293` würde sonst reaktivieren und die Quote prüfen). Zweiter Lauf: `_enthaelt(ist, soll)` ⇒ kein Schreibzugriff.
2. Danach `sichere_archiviert`: nur wenn `archived_at` im Ergebnis fehlt ⇒ `PATCH /api/trips/{id}/state` mit `{"archived": true}` (nicht `{"state": …}`, das wirkt nicht). Go setzt `archived_at = now` ⇒ Archivdatum = Datum des ersten Seed-Laufs, bleibt danach stabil.
3. Keine Kanal-/Wetter-/Tabellen-Konfiguration am Archiv-Trip (nicht nötig fürs Bild, weniger Fläche). Etappen-Daten in der Vergangenheit.
4. Rückgabe/Ausgabe von `main` unverändert (`ELEMENTLISTE_TRIP_ID` bleibt GR221) ⇒ #2913 unberührt.
5. Danach Seed auf Staging laufen lassen, `funktionen_screenshots.py --nur archiv` DE+EN, Sichtprüfung, Alt-Text und Runbooks nachziehen.

### Verifizierte Annahmen
- Versandsperre: Trip-Briefing (`next_briefing.py:188`, `loader.py:1832` filtert archivierte Trips), Dispatch (`scheduler_dispatch_service.py:118`) überspringen `archived_at` ⇒ kein Versand.
- Trip-Liste (`trips/+page.server.ts:20`) blendet archivierte Trips aus; Elementlisten-Abgleich #2913 nutzt nur die GR221-ID ⇒ verträglich.
- Archiv-Seite zeigt Name, „N Etappen", Datum `archived_at[:10]`.
- Quote: Anlage passiert, solange der Trip noch aktiv ist (zählt kurz), Prüfkonto ist Premium (`sichere_tarif` vorher) ⇒ unkritisch.

### Dependencies
- Go-API `/api/trips` (GET/POST/PUT) und `/api/trips/{id}/state` (PATCH); Tarif Premium vor Anlage.
- Downstream nur Archiv-Seite und Funktionsseiten-Bild.

### Open Questions
- keine (Name/Etappen des fiktiven Trips legt der Tech Lead in der Spec fest: fiktiv, kein PO-Bezug)
