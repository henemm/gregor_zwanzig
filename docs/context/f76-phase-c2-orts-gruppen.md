# Context: F76 Phase C2 — Orts-Gruppen

## Request Summary
Locations in Gruppen/Ordner organisieren (Skigebiete Tirol, Surfspots PT). Sidebar zeigt hierarchische Baumstruktur mit Expand/Collapse. Jeder Ort gehoert zu genau einer Gruppe. Gruppen als Ganzes fuer Vergleich waehlbar.

## Ist-Zustand
- Locations sind **flach** — keine Gruppen, keine Ordner
- Sidebar (C1) zeigt alle Locations als flache Checkbox-Liste
- Location-Modell hat kein `group`-Feld
- Subscriptions referenzieren Locations direkt per ID-Array

## Soll-Zustand (aus approved Spec)
```
▼ Skigebiete Tirol
    ☑ Stubaier Gletscher
    ☑ Hintertux
    ☐ Axamer Lizum
▼ Surfspots Portugal
    Nazare
    Peniche
▶ Wandern Mallorca (3)

[+ Gruppe]  [+ Ort]
```

## Related Files

### Backend (Go)
| File | Relevance |
|------|-----------|
| `internal/model/location.go` | Location struct — braucht `Group *string` Feld |
| `internal/store/store.go` | File-based JSON Storage, LoadLocations sortiert alphabetisch |
| `internal/handler/location.go` | CRUD Handler, validateLocation() |

### Frontend (SvelteKit)
| File | Relevance |
|------|-----------|
| `frontend/src/routes/compare/+page.svelte` | Sidebar mit flacher Location-Liste (C1), Checkboxen |
| `frontend/src/routes/compare/+page.server.ts` | Laedt `/api/locations` |
| `frontend/src/lib/components/LocationForm.svelte` | Location Create/Edit Form — braucht Gruppen-Dropdown |
| `frontend/src/lib/types.ts` | Location Interface — braucht `group?` Feld |

### Specs
| File | Relevance |
|------|-----------|
| `docs/specs/ux_redesign_navigation.md` | Approved Spec, Section 3: Orts-Vergleich Sidebar mit Gruppen |

## Aenderungen noetig

### 1. Go Location Model
Neues optionales Feld: `Group *string json:"group,omitempty"`

### 2. TypeScript Interface
Neues optionales Feld: `group?: string`

### 3. LocationForm
Gruppen-Dropdown oder Textfeld beim Erstellen/Bearbeiten eines Orts

### 4. Compare Sidebar
- Locations nach `group` gruppieren
- Expand/Collapse pro Gruppe
- Gruppen-Checkbox (alle Orte der Gruppe an/aus)
- Ungroupierte Orte als eigene Sektion

### 5. Kein neuer API-Endpoint
Group ist nur ein Feld auf Location — kein eigener CRUD fuer Gruppen noetig. Gruppen ergeben sich aus den eindeutigen `group`-Werten aller Locations.

## Design-Entscheidung: Gruppen als Feld vs. eigene Entitaet

**Feld auf Location (empfohlen):**
- `group` ist ein optionaler String auf jedem Location-Objekt
- Gruppen sind implizit — alle Locations mit demselben `group`-Wert bilden eine Gruppe
- Kein neuer CRUD-Endpoint, kein neues Modell
- Umbenennen einer Gruppe = alle Locations dieser Gruppe updaten
- Pro: Einfach, kein Schema-Aenderung, abwaertskompatibel
- Contra: Umbenennen ist N Updates statt 1

**Eigene Entitaet:**
- Neues Group-Modell, neuer Store, neue Endpoints
- Pro: Saubere Trennung, Umbenennen ist 1 Update
- Contra: Overengineered fuer 5-20 Orte pro User

## Risiken
- Bestehende Locations haben kein `group` → muessen als "Ungroupiert" dargestellt werden
- Subscriptions referenzieren Location-IDs, nicht Gruppen → kein Bruch
- LocationForm braucht eine Moeglichkeit, existierende Gruppen auszuwaehlen ODER neue zu erstellen
