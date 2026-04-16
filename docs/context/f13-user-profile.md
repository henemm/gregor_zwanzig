# F13 Phase 4: User-Profil mit Channel-Einstellungen

## Analyse-Ergebnis (2026-04-16)

### Scoping-Entscheidung: Split in 4a + 4b

**Phase 4a (Go-Seite):** User-Model erweitern, API-Endpoints, Directory-Provisioning
**Phase 4b (Python-Seite):** Services lesen Channel-Settings aus user.json statt .env

### Phase 4a: Go User-Profil

#### Ist-Zustand
- `model.User` hat nur: id, email, password_hash, created_at
- Registration erstellt user.json aber KEINE Unterordner
- Kein API-Endpoint um User-Profil zu lesen/aktualisieren

#### Soll-Zustand
- `model.User` bekommt Channel-Felder: mail_to, signal_phone, signal_api_key, telegram_chat_id
- `PUT /api/auth/profile` — eigenes Profil aktualisieren
- `GET /api/auth/profile` — eigenes Profil lesen
- Registration erstellt Unterordner (locations, trips, etc.)

#### Betroffene Dateien (4)

| Datei | Änderung | LoC |
|-------|----------|-----|
| `internal/model/user.go` | Channel-Felder hinzufügen | +5 |
| `internal/handler/auth.go` | ProfileHandler (GET/PUT) + Verzeichnis-Provisioning bei Register | +60 |
| `internal/store/user.go` | ProvisionUserDirs Methode | +15 |
| `cmd/server/main.go` | Route-Registration | +3 |

**Gesamt: 4 Dateien, ~80 LoC**
