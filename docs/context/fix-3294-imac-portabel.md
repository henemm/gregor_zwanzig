# Context: fix-3294-imac-portabel (Issue #3294)

## Request Summary
Gregor-Sitzungen sollen auf dem iMac (macOS, ggf. neuere Go-Version) ohne Sonderhandgriffe laufen
(Teil von henemm-infra#487). Drei Befunde: Go-Test rot unter Go 1.27, Resolver-Test braucht
127.0.0.2, SessionStart-Hook ruft einen nur auf dem Server vorhandenen Pfad auf.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/trip.go:153-162` | `writeTripDecodeError` vergleicht `UnmarshalTypeError.Field == "stages.grundtempo_kmh"` |
| `internal/handler/trip_stage_tempo_3197_test.go:111` | `TestStageTempo3197_Ungueltig422` (AC-8 aus #3197) |
| `internal/resolver/link_abruf_haertung_ergaenzung_test.go:23` | `TestLinkAbruf_EgressWaechterWirdJeAbrufGefragt` lauscht auf 127.0.0.2 |
| `internal/egress/guard.go:18` | Wächter-Freigabe kennt nur `localhost`/`127.0.0.1` |
| `.claude/settings.json:126` | SessionStart-Hook `bash /home/hem/claude-mq/check-messages.sh` |
| `/home/hem/claude-mq/check-messages.sh` | leitet Instanz aus `$PWD` ab (`/home/hem/gregor_zwanzig*` → gregor), Secret liegt nur auf dem Server |
| `go.mod` | `go 1.25.0`, keine `toolchain`-Zeile |

## Analyse (Ursachen, gemessen 2026-11-23)

### 1. Go 1.27 → 400 statt 422
Nachgestellt mit `GOTOOLCHAIN=go1.27.0`: Nur die Fälle `"3"` und `true` scheitern. Ursache:
`encoding/json` in Go 1.27 setzt im `UnmarshalTypeError.Field` den Array-Index mit
(`stages.1.grundtempo_kmh`), Go 1.25 nicht (`stages.grundtempo_kmh`). Minimalbeispiel im
Scratchpad bestätigt. Der exakte String-Vergleich greift deshalb nicht → 400.
Fix: Feldpfad ohne numerische Segmente vergleichen (versionsunabhängig).

Vollständiger `go test ./...` unter 1.27: einzige weitere Auffälligkeit
`TestGoogleLink_AC3_BestaetigterInhaberWirdVerknuepft/exakt`, einzeln unter 1.27 und 1.25
dreimal grün → Lastflake, nicht versionsbedingt (Nebenbefund).

**Toolchain-Zeile:** `toolchain go1.25.x` in `go.mod` ist laut Go-Toolchain-Regeln eine
*Mindest*version: eine lokal neuere Go-Version (1.27) wird trotzdem benutzt. Die Zeile würde
also nicht „festnageln“. Festnageln ginge nur per `GOTOOLCHAIN=go1.25.0` je Rechner — genau
der Sonderhandgriff, der wegfallen soll. Tech-Lead-Entscheidung: Ursache beheben, Code
versionsunabhängig machen; keine wirkungslose Toolchain-Zeile. CI und Server bleiben auf 1.25.

### 2. 127.0.0.2 auf macOS
macOS `lo0` hat nur 127.0.0.1 (und `::1`). Der Test braucht eine Loopback-Adresse, die NICHT
in der Wächter-Freigabe steht; 127.0.0.1 (anderer Port) taugt nicht, weil der Wächter
127.0.0.1 freigibt. `::1` ist Loopback, nicht freigegeben und auf macOS vorhanden.
Fix: erst 127.0.0.2, sonst `[::1]`; nur wenn beides fehlt, Skip mit Begründung.

### 3. Start-Hook
Neues Skript `.claude/hooks/mq_check_messages.sh`: lokal vorhandenes Server-Skript direkt
aufrufen, sonst per `ssh -o ConnectTimeout=3 -o BatchMode=yes henemm` auf dem Server im
Gregor-Ordner (Instanz-Ableitung über `$PWD`), nicht erreichbar → still `exit 0`.
Pfad und SSH-Ziel per Umgebungsvariable überschreibbar (Testbarkeit, andere Rechner).

## Existing Patterns
- Hooks in `.claude/settings.json` mit `${CLAUDE_PROJECT_DIR}/.claude/hooks/...`
- Go-Tests nutzen `t.Skip` mit Begründung für plattformabhängige Voraussetzungen

## Risks & Considerations
- SessionStart darf nie blockieren: ssh mit kurzen Timeouts, `ServerAliveInterval`, Fehler schlucken.
- Kein Secret auf dem iMac (henemm-security#219): Abfrage läuft auf dem Server.
- Fehlercode 422 vs. 400 für andere Felder darf sich nicht ändern (nur grundtempo_kmh in stages).
