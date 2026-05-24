# Context: Bug #350 — LoadMetricPresets behandelt korruptes JSON wie leere Datei

## Request Summary

`internal/store/store.go::LoadMetricPresets()` schluckt sowohl Lese- als auch
JSON-Parse-Fehler still und gibt in beiden Fällen `([], nil)` zurück. Dadurch ist
eine korrupte `metric_presets.json` nicht von einem legitim leeren Zustand zu
unterscheiden — beim nächsten Save (z.B. POST eines Presets) wird die korrupte
Datei mit der leeren Liste überschrieben und alle bestehenden Presets gehen verloren.
Quelle: Adversary-Finding F002 aus #342 (Verdict VERIFIED), pre-existing.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/store/store.go:339-356` | `LoadMetricPresets()` — der Bug: Zeile 345 (Read-Fehler != IsNotExist) + Zeile 349 (Unmarshal-Fehler) geben beide `([], nil)` zurück |
| `internal/store/store.go:443-457` | `SaveMetricPresets()` — überschreibt die Datei bei Save; hier würde der Datenverlust real |
| `internal/handler/metric_preset.go:108-167` | GET/POST/DELETE-Handler — verarbeiten `err != nil` von Load bereits korrekt (→ `500 store_error`), kein Handler-Fix nötig |
| `internal/store/store_test.go:146-320` | Bestehende MetricPreset-Tests (Legacy-Migration, Roundtrip, Horizons-Default) — Anker für neuen Korrupt-JSON-Test |
| `internal/handler/metric_preset_test.go:257-268` | `TestStore_LoadMetricPresets_EmptyWhenNoFile` — bestätigt: File-not-found bleibt legitim leer |

## Existing Patterns

**Alle anderen Load-Funktionen im Store folgen demselben Fehler-Muster** — nur
`LoadMetricPresets` weicht ab. Beispiele aus `store.go`:

- Trip-Load (Z. 138-146): `os.IsNotExist` → `nil, nil`; sonst `return nil, err`; Unmarshal-Fehler → `return nil, err`
- Location-Load (Z. 192-200): identisches Muster
- Subscriptions-Load (Z. 242-252): identisch
- Groups-Load (Z. 512-513): Unmarshal-Fehler → `return nil, uerr`

Der Fix ist also reines **Angleichen an das etablierte Codebase-Muster**, keine neue Erfindung:
- File-not-found (`os.IsNotExist`) → `[]MetricPreset{}, nil` (legitim leer, bleibt)
- Anderer Read-Fehler (Z. 345) → `return nil, err`
- `json.Unmarshal`-Fehler (Z. 349) → `return nil, err` (ggf. mit `fmt.Errorf`-Wrapping)

Da die Handler `err != nil` bereits auf `500 store_error` abbilden, greift der Schutz
sofort: ein korruptes File führt zu 500 statt zu stillem Überschreiben.

## Dependencies

- **Upstream (was Load nutzt):** `os.ReadFile`, `json.Unmarshal`, `migrateMetricPreset()`
- **Downstream (was Load nutzt):** `ListMetricPresetsHandler`, `CreateMetricPresetHandler`, `DeleteMetricPresetHandler` (alle in `metric_preset.go`) — behandeln Fehler bereits korrekt

## Existing Specs

- `docs/specs/modules/epic_138_174_178_metriken_ui.md` — Ursprüngliche Spec für die User-Preset-Persistenz (LoadMetricPresets/SaveMetricPresets, 3 Endpoints)

## Risks & Considerations

- **Risiko gering, Blast-Radius klein:** Reiner Store-Fix, Handler unverändert, Muster
  schon erprobt. Test ohne Mocks möglich (echtes tmp-File mit kaputtem JSON, echtes `Store`).
- **Scope-Entscheidung (PO, 2026-05-24):** Nur Kern-Fix. Der optionale Backup-on-Save-Vorschlag
  (`.backups/metric_presets-<ts>.json`, Retention 10) ist NICHT im Scope — der Kern-Fix
  (Fehler propagieren) verhindert den Datenverlust bereits. Minimal, Sorgsamkeits-Prinzip.
- **Schema-Backup-Hook:** `store.go` ist eine schema-relevante Datei (CLAUDE.md) →
  `data_schema_backup.py` erstellt beim Edit automatisch ein tar.gz-Snapshot von `data/users/`.
- **TDD-Test:** Neuer Test in `store_test.go` — korruptes JSON schreiben, `LoadMetricPresets()`
  muss `err != nil` liefern (nicht `[], nil`). File-not-found-Test bleibt grün.
