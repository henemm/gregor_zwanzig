# F13 Phase 1: User-Scoped Go Store

## Analyse-Ergebnis (2026-04-15)

### Ist-Zustand
- Auth-Middleware extrahiert `userId` aus Session-Cookie → Context ✅
- `UserIDFromContext(ctx)` existiert, wird aber **nie aufgerufen** ❌
- Store wird einmal beim Start mit `cfg.UserID = "default"` initialisiert
- 20 Handler bekommen alle denselben Store
- Proxy-Handler leiten keine userId an Python weiter
- Python-Loader akzeptieren `user_id` Parameter (Default: "default")

### Architektur-Entscheidung: `Store.WithUser()`

**Gewählt:** Option B — `s.WithUser(userId)` pro Request im Handler.

**Begründung:**
- Handler-Signaturen bleiben unverändert (`Handler(s *store.Store)`)
- `main.go` braucht keine Änderung
- Kein neuer Cross-Package-Import (handler → store bleibt)
- `WithUser("")` ist No-Op → bestehende Tests laufen unverändert
- Allocation-cheap (zwei Strings kopieren)

### Betroffene Dateien (6)

| Datei | Änderung | LoC |
|-------|----------|-----|
| `internal/store/store.go` | `WithUser()` Methode | +3 |
| `internal/handler/location.go` | userId-Extraktion in 4 Handlers | +9 |
| `internal/handler/trip.go` | userId-Extraktion in 5 Handlers | +11 |
| `internal/handler/subscription.go` | userId-Extraktion in 5 Handlers | +11 |
| `internal/handler/weather_config.go` | userId-Extraktion in 6 Handlers | +13 |
| `internal/handler/proxy.go` | userId an Python weiterleiten | +20 |

**Gesamt: ~65 LoC, 0 gelöscht**

### Risiko-Analyse

1. **Bestehende Tests:** `WithUser("")` ist No-Op → alle Tests laufen ohne Änderung
2. **Health/Status Endpoints:** Bypass Auth-Middleware, nutzen keinen Store → kein Problem
3. **Python-Kompatibilität:** `user_id=default` als Query-Param = identisch zum Default
4. **Import-Richtung:** handler → middleware ist unidirektional, kein Zyklus
