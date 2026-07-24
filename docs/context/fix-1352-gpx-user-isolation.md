# Context: fix-1352-gpx-user-isolation

Issue: [#1352](https://github.com/henemm/gregor_zwanzig/issues/1352) — GPX-Upload schreibt cross-user in geteilten `default`-Ordner

## Request Summary

`POST /api/gpx/parse` legt jede hochgeladene GPX-Datei im fest verdrahteten Verzeichnis
`data/users/default/gpx/` ab — unabhängig vom eingeloggten Nutzer. Gleichnamige Dateien
verschiedener Nutzer überschreiben sich. Das Upload-Ziel muss über die echte `user_id`
aus dem Auth-Kontext aufgelöst werden (`get_data_dir(user_id) / "gpx"`).

## Befund am laufenden System (Prod, 2026-07-24, gemessen als `claude-gregor`)

| Verzeichnis | Dateien | Neuester Zeitstempel |
|---|---|---|
| `data/users/default/gpx/` | 22 | 12. Juli 2026 |
| `data/users/henning/gpx/` | 23 | 20. Mai 2026 (eingefroren) |

Deutung: Die per-Nutzer-Ordner stammen aus der Datenpfad-Migration (#1265, 20. Mai) und
werden seitdem **nicht mehr beschrieben**. Alle Uploads danach (5./11./12. Juli) landen in
`default/`. Der Bug ist damit live bestätigt, nicht nur aus dem Code abgeleitet.

## Related Files

| Datei | Relevanz |
|---|---|
| `api/routers/gpx.py:10-27` | Endpoint; nimmt **keinen** `user_id`-Parameter entgegen und reicht kein `upload_dir` durch |
| `src/services/gpx_processing.py:37-38` | Modul-Konstanten `_DEFAULT_UPLOAD_DIR` / `_GPX_UPLOAD_DIR` = `Path("data/users/default/gpx")` |
| `src/services/gpx_processing.py:41-70` | `process_gpx_upload` — schreibt real (`upload_dir.mkdir`, `saved_path.write_bytes`) |
| `src/services/gpx_processing.py:195-256` | `gpx_to_stage_data` — Default-Argument `upload_dir=_GPX_UPLOAD_DIR` |
| `src/services/gpx_processing.py:259-299` | `process_bulk_gpx_uploads` — gleiches Default-Argument |
| `src/app/loader.py:1031-1060` | `get_data_root()` / `get_data_dir(user_id)` — der vorgeschriebene Auflösungsweg |
| `internal/handler/proxy.go:398-429` | `GpxProxyHandler` — hängt `user_id` **bereits korrekt** an (Z. 402-405 via `appendUserID`) |
| `internal/handler/proxy.go:147-159` | `appendUserID` — überschreibt client-gesetzte `user_id` (Defense-in-Depth) |
| `internal/store/user.go:84` | legt `gpx/` je Nutzer bereits an — Zielordner existiert |
| `internal/router/router.go:151` | Route-Registrierung hinter der globalen Auth-Middleware |

## Existing Patterns

- **Kanonisches `user_id`-Muster im Python-Core:** `user_id: str = Query(...)` — **pflicht**,
  kein Default. Vorbilder: `api/routers/preview.py:32,58,88,131`, `api/routers/notify.py:21`,
  `api/routers/internal.py:30`. `preview.py:9-11` dokumentiert das Sicherheitsmodell:
  der Go-Proxy injiziert die `user_id` aus der Session, ein client-gesetzter Wert wird
  überschrieben.
- **Datenverzeichnis-Auflösung:** immer `get_data_dir(user_id)` bzw. `get_data_root()` —
  nie relative Pfad-Literale. Docstring in `loader.py` warnt explizit, dass direktes Lesen
  von `GZ_DATA_DIR` die Test-Isolation (#1133) aushebelt. `gpx_processing.py` verletzt genau das.

## Dependencies

- **Upstream (was wir benutzen):** `app.loader.get_data_dir`, `core.gpx_parser.parse_gpx`,
  Segmentierungspipeline (`hybrid_segmentation`, `segment_builder`, `elevation_analysis`).
- **Downstream (was uns benutzt):**
  - `api/routers/gpx.py` → Go-Proxy → Frontend:
    `frontend/src/lib/api.ts:50`, `frontend/src/lib/components/trip-new/TripNewEditor.svelte:253`,
    `frontend/src/routes/gpx-upload/+page.svelte:54` (alle ohne eigenes `user_id` — korrekt,
    der Go-Proxy setzt es).
  - Tests: `tests/tdd/test_gpx_proxy.py`, `tests/unit/test_gpx_import_in_trip_dialog.py`,
    `tests/tdd/test_issue_1004_startzeit_ssot.py`.
  - E2E: `frontend/e2e/issue-1158-*.spec.ts`, `issue-776-*.spec.ts`, `issue-774-*.spec.ts`
    warten auf `/api/gpx/parse` — brechen, wenn der Endpoint 422 zurückgibt.
  - `process_bulk_gpx_uploads` hat **keinen** Produktiv-Aufrufer (nur Tests) — Altlast aus der
    NiceGUI-Zeit.

## Existing Specs

- `docs/specs/modules/gpx_proxy.md` — führt „Authentifizierung / Benutzer-Isolation" ausdrücklich
  als **Out of Scope**. Das ist der dokumentarische Ursprung des Bugs und muss mitgezogen werden.
- `docs/specs/modules/gpx_multi_import.md` — beschreibt `process_bulk_gpx_uploads`.
- `docs/specs/modules/gpx_parser.md` — reine Parser-Ebene, nicht betroffen.

## Risks & Considerations

1. **Signatur-Bruch:** Der Modul-Docstring erklärt die Signatur von `gpx_to_stage_data`
   für ausdrücklich stabil („API-Contract"). Bestehende Tests rufen mit `upload_dir=tmp_path`
   auf. Ein Umbau muss diese Aufrufform tragen und darf trotzdem keinen stillen
   `default`-Rückfall behalten.
2. **Pflicht- vs. Optional-Parameter:** Wird `user_id` zum Pflichtfeld, antwortet der
   Python-Core auf direkte Aufrufe ohne Kennung mit 422. Über den Go-Proxy kann das nicht
   passieren; direkte Aufrufe auf Port 8000/8001 (Test- und Diagnosewege) müssen angepasst werden.
3. **Bestandsdaten:** Es gibt **keinen fachlichen Leser** der abgelegten GPX-Dateien (kein
   `glob`, kein `parse_gpx()` auf gespeicherte Pfade außerhalb des unmittelbaren Parse-Vorgangs)
   — eine Datenmigration ist fachlich nicht nötig. **Aber:** `tests/tdd/test_gpx_proxy.py:12`
   liest eine konkrete Datei aus `data/users/default/gpx/` als Fixture (`_SAMPLE_GPX`). Der
   Ordner darf also nicht geleert werden; die Kernaussage „wird nirgends wieder gelesen" gilt
   nur fachlich, nicht test-technisch.
4. **Zwei-Nutzer-Nachweis ist Pflicht** (CLAUDE.md): gleicher Dateiname, zwei Nutzer, keine
   gegenseitige Überschreibung — auf Staging zu zeigen.
5. **Test-Isolationsschulden:** `tests/tdd/test_gpx_proxy.py:51-56` biegt heute `cwd` um, weil
   der Pfad relativ ist. Nach dem Fix ist dieser Workaround überflüssig und sollte fallen.

---

# Analysis

Ergebnis aus zwei unabhängigen Läufen: `analysis-challenger` (Gegenprüfung der Ursache) und
`Plan` (technische Bewertung). Beide Berichte sind hier eingearbeitet.

## Type

**Bug** — Verletzung der Mandantentrennung auf einem Produktivpfad.

## Ursache — bestätigt

Einzige Schreibquelle für GPX-Dateien ist `process_gpx_upload` (`src/services/gpx_processing.py:63-64`),
erreicht ausschließlich über `api/routers/gpx.py:23`. Kein zweiter Schreibpfad (Go-Seite legt in
`internal/store/user.go:84` nur den leeren Ordner an; die NiceGUI-Module wurden in Epic #129
vollständig nach `services/gpx_processing.py` extrahiert). Der Fehler ist damit einstellig.

## Zusätzlicher Befund: Pfad-Ausbruch über den Dateinamen (NEU, in Scope)

`src/services/gpx_processing.py:64` setzt `saved_path = upload_dir / filename` mit ungeprüftem
`filename` aus dem Multipart-Header; einzige Prüfung ist die `.gpx`-Endung (Z. 60-61).
Praktisch nachgerechnet:

```
Path("data/users/alice/gpx") / "../../bob/gpx/x.gpx"
  → .../data/users/bob/gpx/x.gpx
```

Ein Upload mit präpariertem Dateinamen schreibt also **gezielt** in den Ordner eines anderen
Nutzers. Das ist dieselbe Verletzung wie #1352, nur absichtlich statt versehentlich — würde nur
die Ordner-Auflösung repariert, bliebe dieser Weg offen. **Deshalb in Scope**, nicht als
Nebenbefund ausgelagert (CLAUDE.md-Triage (b) wäre erfüllt, aber es ist derselbe Funktionskörper
und dieselbe Schutzgut-Verletzung). Gegenmaßnahme: `Path(filename).name` statt rohem `filename`.

Die `user_id` selbst ist **nicht** traversal-fähig: Go validiert Benutzernamen gegen
`^[a-zA-Z0-9_-]+$` (`internal/handler/passkey.go:23`).

## Geprüfte Gegenargumente

| Frage | Ergebnis |
|---|---|
| Zweiter Schreibpfad? | Nein — einziger Produktiv-Aufrufer `api/routers/gpx.py:23` |
| Route hinter Auth? | Ja — `AuthMiddleware` (`internal/middleware/auth.go:31-50`), `/api/gpx/parse` **nicht** auf der Allowlist ⇒ ohne Session 401 |
| Kann `appendUserID` leer liefern? | Praktisch nein — hinter der Middleware ist `UserIDFromContext` immer gesetzt; 422 über den Proxy also ausgeschlossen |
| Python-Core von außen erreichbar? | Nein — gemessen: `127.0.0.1:8000`, `127.0.0.1:8001`, `127.0.0.1:8090`, keine öffentliche Bindung |
| Fachlicher Leser der Altdateien? | Nein — nur eine Test-Fixture (s. Risiko 3) |

## Affected Files (with changes)

| Datei | Art | Beschreibung |
|---|---|---|
| `src/services/gpx_processing.py` | MODIFY | Modul-Konstanten `_DEFAULT_UPLOAD_DIR`/`_GPX_UPLOAD_DIR` ersatzlos löschen; `upload_dir` in allen drei Funktionen zum Pflicht-Parameter ohne Default; `filename` über `Path(filename).name` entschärfen |
| `api/routers/gpx.py` | MODIFY | `user_id: str = Query(...)` (Pflicht, kein Default — Muster `preview.py:32`); `upload_dir = get_data_dir(user_id) / "gpx"` auflösen und durchreichen |
| `tests/tdd/test_gpx_proxy.py` | MODIFY | `user_id` an allen Endpoint-Aufrufen ergänzen (6 von 7 Tests brechen sonst mit 422); `monkeypatch.chdir`-Workaround (Z. 50-56) entfernen — die autouse-Fixture `_isolate_data_root` greift nach dem Umbau von selbst; **neuer Zwei-Nutzer-Test** |
| `docs/specs/modules/gpx_proxy.md` | MODIFY | „Authentifizierung / Benutzer-Isolation" aus *Out of Scope* herausnehmen — dokumentarischer Ursprung des Bugs |

Unbetroffen (verifiziert): `tests/unit/test_gpx_import_in_trip_dialog.py` und
`tests/tdd/test_issue_1004_startzeit_ssot.py` rufen die Service-Funktionen direkt mit explizitem
`upload_dir=tmp_path`; die drei Playwright-Specs laufen über den Go-Proxy, der `user_id` bereits setzt.

## Scope Assessment

- Dateien: 4 (3 Code/Test + 1 Spec)
- Geschätzte LoC: ca. +30 / -12 (Doku zählt nicht) — deutlich unter dem 250er-Limit, kein Override
- Risiko: **MEDIUM** (Produktivpfad, aber eng begrenzt und vollständig testbar)

## Technical Approach

**Auflösung gehört in den Router, nicht in das Service-Modul.**

1. `src/services/gpx_processing.py`: Defaults weg. Fehlt `upload_dir`, gibt es einen `TypeError`
   statt eines stillen Rückfalls auf einen geteilten Ordner — die Fehlerklasse wird strukturell
   unmöglich statt nur an einer Stelle repariert. Bestehende Testaufrufer übergeben `upload_dir`
   ohnehin schon explizit, für sie ändert sich nichts.
2. `api/routers/gpx.py`: `user_id` als Pflicht-Query, `get_data_dir(user_id) / "gpx"` auflösen.
   Damit gibt es genau **eine** Stelle, an der ein Upload-Ziel entsteht, und sie hängt an der
   echten Sitzung.
3. `filename` an der Schreibstelle auf den reinen Dateinamen reduzieren.
4. `process_bulk_gpx_uploads` zieht mit (Default entfernen), wird **nicht** gelöscht: fünf aktive
   Tests hängen daran, und das Löschen wäre eine eigene Entscheidung gegen `gpx_multi_import.md`.

**Reihenfolge:** Schritt 1 und 2 sind atomar zusammen mit der Testanpassung zu committen —
dazwischen ist der Baum notwendigerweise rot.

## Nachweisführung

- **Kern (deterministisch, ohne Netz):** Zwei Uploads über `TestClient` mit **gleichem Dateinamen,
  unterschiedlichem Inhalt** für `user_id=alice` und `user_id=bob`; danach beide Zieldateien lesen
  und Byte-Inhalte vergleichen. Echte Datei-I/O unter isoliertem Tmp-Root (`_isolate_data_root`,
  `tests/conftest.py`), kein Mock.
- **Traversal:** Upload mit `filename="../../bob/gpx/x.gpx"` landet in `alice/gpx/x.gpx`,
  **nicht** bei `bob`.
- **Staging:** zwei Sitzungen über `storageState`, gleicher Dateiname hochgeladen, danach die
  beiden Nutzerordner auf dem Staging-Host vergleichen.

## Open Questions

Keine offenen Punkte für die Spezifikation.
