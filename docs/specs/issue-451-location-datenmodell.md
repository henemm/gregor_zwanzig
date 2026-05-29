# Spec: Issue #451 — Location-Datenmodell (Lücken schließen)

**Status:** draft  
**Workflow:** issue-451-location-datenmodell  
**LoC-Schätzung:** ~57  
**Dateien:** 5

---

## Kontext

Das Location-Backend (Go) ist bereits vollständig implementiert. Diese Spec schließt drei konkrete Lücken, die für die neuen Orts-Vergleich-Features (#441–#443) benötigt werden.

---

## Lücke 1: `GET /api/locations/{id}` fehlt

**Problem:** Es gibt keinen Single-Resource-Endpoint. Clients müssen die ganze Liste laden um eine Location nachzuschlagen.

**Lösung:** Handler + Route hinzufügen.

### `internal/handler/location.go` — neuer Handler

```go
func LocationHandler(s *store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        userID := middleware.UserIDFromContext(r.Context())
        s = s.WithUser(userID)
        id := chi.URLParam(r, "id")
        loc, err := s.LoadLocation(id)
        if err != nil || loc == nil {
            http.Error(w, "not found", http.StatusNotFound)
            return
        }
        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(loc)
    }
}
```

### `cmd/server/main.go` — neue Route

```go
r.Get("/api/locations/{id}", handler.LocationHandler(store))
```

---

## Lücke 2: Python `SavedLocation` — 3 Felder fehlen

**Problem:** `SavedLocation` in `src/app/user.py` fehlen `group`, `timezone`, `created_at`. Deserialisierungsverlust wenn Python Locations vom API empfängt.

**Lösung:** 3 optionale Felder ergänzen (rückwärtskompatibel via `field(default=None)`).

```python
@dataclass(frozen=True)
class SavedLocation:
    id: str
    name: str
    lat: float
    lon: float
    elevation_m: int
    # bestehende optionale Felder ...
    group: Optional[str] = None        # NEU
    timezone: Optional[str] = None     # NEU  
    created_at: Optional[str] = None   # NEU (ISO-8601 String)
```

---

## Lücke 3: Test für `GET /api/locations/{id}`

In `internal/handler/location_write_test.go` (oder separatem File):

- **Test 1:** GET auf existierende Location → 200 + korrektes JSON
- **Test 2:** GET auf nicht-existierende ID → 404

---

## Akzeptanzkriterien

| AC | Beschreibung |
|----|-------------|
| AC-1 | `GET /api/locations/{id}` liefert 200 + Location-JSON für bekannte ID |
| AC-2 | `GET /api/locations/{id}` liefert 404 für unbekannte ID |
| AC-3 | `SavedLocation` deserialisiert `group`, `timezone`, `created_at` verlustfrei |
| AC-4 | Bestehende Tests laufen unverändert durch |

---

## Betroffene Dateien

| Datei | Änderung |
|-------|---------|
| `internal/handler/location.go` | +25 LoC: `LocationHandler` Funktion |
| `cmd/server/main.go` | +1 LoC: Route registrieren |
| `internal/handler/location_write_test.go` | +20 LoC: 2 Tests für GET/{id} |
| `src/app/user.py` | +6 LoC: 3 optionale Felder |
| `tests/test_user.py` | +5 LoC: Deserialisierungs-Test |

**Gesamt: ~57 LoC** (weit unter 250-Limit)
