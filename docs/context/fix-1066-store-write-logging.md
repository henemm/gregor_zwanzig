# Context & Analyse: fix-1066-store-write-logging

## Request Summary
Nach dem Berechtigungs-Vorfall (#1066, Sofort-Fix bereits live) soll die **Code-seitige
Diagnostik-Lücke** geschlossen werden: Schreibfehler im Persistenz-Pfad (`internal/store/`)
werden heute stumm zum generischen `{"error":"store_error"}` verdichtet — der echte OS-Fehler
(z.B. „permission denied") geht verloren. Ziel: Schreibfehler **serverseitig loggen** (mit
Pfad + Ursache), damit die nächste Berechtigungs-Regression sofort diagnostizierbar ist.

**Abgegrenzt:** Monitoring/Schreib-Selftest ist Folge-Issue #1120 — NICHT Teil dieses Workflows.

## Related Files
| Datei | Relevanz |
|-------|----------|
| `internal/store/trip.go:128` | `SaveTrip` → `os.WriteFile` (der konkret gemeldete Pfad) |
| `internal/store/user.go:78,101` | `SaveUser`, Password-Reset — 2 Schreibstellen |
| `internal/store/group.go:152` | `SaveGroups` |
| `internal/store/subscription.go:120` | Subscriptions |
| `internal/store/compare_preset.go:59` | Orts-Vergleich-Presets |
| `internal/store/location.go:91` | Orte |
| `internal/store/metric_preset.go:142` | Metrik-Presets |
| `internal/handler/trip.go:275-280` | Handler-Grenze: `err != nil` → `500 store_error` (loggt NICHT) |

**8 produktive `os.WriteFile`-Stellen in `internal/store/`** (Test-Dateien ausgenommen).

## Existing Patterns
- **Logging-Konvention:** `log.Printf` ist Standard (52 Vorkommen; kein slog, kein Custom-Logger).
- **Store loggt bereits selbst:** `trip.go:34/40`, `location.go:37/43` nutzen
  `log.Printf("skip %s: read error: %v", ...)` für Lese-/JSON-Fehler in den List-Funktionen.
  → Der Store ist der **richtige, bereits etablierte Ort** fürs Logging von I/O-Fehlern.
- **Response-Trennung:** Handler geben bewusst generisches `store_error` (kein Pfad-Leak an Client).

## Empfohlener Ansatz (Analyse)
**Zentraler Helper statt 8× Copy-Paste** — DRY + einheitliches Format:

- Neuer package-privater Helper in `internal/store/`, z.B.
  `func writeFileLogged(path string, data []byte) error`:
  - `err := os.WriteFile(path, data, 0644)`
  - bei `err != nil`: `log.Printf("store: write %s failed: %v", path, err)` **und**
    `return fmt.Errorf("write %s: %w", path, err)` (Kontext via `%w`, idiomatisch).
- Alle **8** produktiven `os.WriteFile(...)`-Aufrufe darauf umstellen.
- **Response bleibt `store_error`** — kein Dateipfad an den Client (Security).

Warum Store-Layer (Option A) statt Handler-Layer (Option B): Der Store ist der **einzige
Choke-Point** für alle Schreiber (Handler, Scheduler, CLI). Ein Punkt loggt alles; Handler-seitig
gäbe es ~15 verstreute `store_error`-Stellen (auth.go ×5, subscription.go ×5, …). Das Issue
selbst zeigt auf den Store („alle `os.WriteFile`-Aufrufe unter `internal/store/`").

## Dependencies
- **Upstream:** `os.WriteFile`, `log`, `fmt` (alle Standard, teils schon importiert).
- **Downstream:** Aufrufer prüfen nur `err != nil` (kein `errors.Is`/String-Match auf die
  konkrete Fehlermeldung gefunden) → Wrapping mit `%w` ist rückwärtskompatibel.

## Existing Specs
- `docs/specs/modules/epic_135_step2_trip_detail_actions.md` — `UpdateTripStateHandler` (#153).
- Kein bestehender Spec deckt das Store-Fehler-Logging ab → neue Mini-/Standard-Spec.

## Risks & Considerations
- **Kein Pfad-Leak an Client:** Nur serverseitig loggen; HTTP-Response unverändert `store_error`.
- **`%w`-Wrapping ändert Fehlertext:** unkritisch, da keine Caller den String matchen.
- **TDD ohne Mock:** Store auf Temp-Dir, Datei einmal schreiben, dann `os.Chmod(...,0444)` →
  echter `os.WriteFile`-Fehler (Tests laufen als `hem`, nicht root). Log-Ausgabe via
  `log.SetOutput(buf)` real einfangen (kein Mock — echtes `log`-Paket-Verhalten) und Pfad +
  Ursache im Buffer prüfen. RED vor Fix (kein Log, roher Fehler), GREEN nach Fix.
- **0644-Subtilität:** Bei existierender Datei ignoriert `os.WriteFile` `perm` — reine Doku,
  kein Verhaltensfix nötig.
