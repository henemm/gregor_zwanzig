# Context: fix-2687-saveuser-merge

## Request Summary
`Store.SaveUser` schreibt `user.json` aus dem typisierten `model.User` und verwirft dabei alle Felder, die das Modell nicht kennt (Verstoß gegen ADR-0101 „Read-Modify-Write mit Merge, niemals Replace"). Ziel: unbekannte Felder bleiben erhalten, bewusst geleerte `omitempty`-Felder (z. B. `PendingSmsTo`) bleiben geleert. Issue #2687, Epic #2138 (Strang A, go-live-pflicht), Nebenbefund aus #2646.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/store/user.go:78` | `SaveUser`: `json.MarshalIndent(user)` + `writeFileLogged` = Replace. Hier entsteht der Verlust. |
| `internal/store/user.go:120` | `mergeUserJSON(id, mutate)`: Roh-Map-Merge, existiert bereits (genutzt von `SetUserLanguage`, `SetUserDisabled`, `SetUserOnboardingFlags`, `SetUserTestMailSentAt`, `SetUserTier`). Setzt aber voraus, dass die Datei existiert. |
| `internal/model/user.go:10` | `model.User` mit ~35 JSON-Feldern, fast alle `omitempty`. Quelle der „bekannten Schlüssel". |
| `internal/handler/auth.go` (Profil-PUT ab ~1122, SaveUser an 1456/1573) | Mischpfad `display_name` + weitere Felder |
| 25 weitere Aufrufer (`auth.go`, `auth_oauth.go`, `auth_magic.go`, `passkey.go`, `telegram_connect.go`, `sms_verify.go`, `premium_sms_connect.go`, `store/premium_sms_migration.go`, `cmd/server/main.go:147`) | Alle profitieren von der zentralen Korrektur; keiner muss geändert werden. |
| `internal/store/dateimodi_einstiegspunkte_test.go:24`, `dateimodi_default_acl_test.go:33,135,142` | Bestehende Tests: SaveUser legt Verzeichnis/Datei neu an (Erstanlage ohne vorhandene Datei muss weiter gehen) |
| `internal/store/user_onboarding_merge_test.go` | Muster für Merge-Tests (unbekanntes Fremdfeld) |
| `docs/adr/0101-read-modify-write-mit-merge.md` | Normative Vorgabe |

## Existing Patterns
- `mergeUserJSON`: Datei lesen → `map[string]json.RawMessage` → mutieren → `MarshalIndent` → `writeFileLogged`. Unbekannte Felder bleiben, weil nie typisiert.
- Typisierte Felder werden im Modell kommentiert „TYPISIERT, damit sie jeden SaveUser-Schreiber überstehen" — Workaround für genau dieses Problem; die zentrale Lösung macht ihn künftig unnötig, ohne ihn zu entfernen.
- Schlüssel-Löschung bei leerem Wert: `delete(m, key)` (omitempty-Form).

## Lösungsrichtung (für /20-analyse zu prüfen)
In `SaveUser`: vorhandene `user.json` als Roh-Map laden (fehlt sie: wie bisher schreiben). Die Menge der dem Modell bekannten JSON-Schlüssel per Reflection über die `json`-Tags von `model.User` ermitteln. Alle bekannten Schlüssel aus der Roh-Map entfernen, dann das serialisierte Modell darüber legen. Ergebnis: unbekannte Felder bleiben, `omitempty`-leere bekannte Felder verschwinden (nicht wiederbelebt), gesetzte Felder werden aktualisiert.

## Dependencies
- Upstream: `fsmode.MkdirAll`, `writeFileLogged`, `ValidUserID`.
- Downstream: sämtliche Auth-/Profil-/Kanal-Verknüpfungspfade (~25 Aufrufer); Python-Core liest `user.json` (`src/app/config.py::with_user_profile`) und darf keine neuen Pflichtfelder sehen.

## Existing Specs
- Keine Spec zu `SaveUser`. Neue Spec nötig (`docs/specs/modules/…`), mit `## Acceptance Criteria` (created ≥ 2026-05-11).

## Risks & Considerations
- **Blast Radius hoch:** jede Kontenänderung läuft darüber; Regression = Login/Profil kaputt. Bestehende Store- und Handler-Tests müssen grün bleiben.
- **Beschädigte vorhandene user.json:** Verhalten festlegen (Vorschlag: wie bisher überschreiben statt Fehler, damit ein Konto nicht dauerhaft unspeicherbar wird; oder bewusst Fehler). In der Analyse entscheiden.
- **Feldumbenennung/Schema-Migration:** Reflection-Ansatz behandelt umbenannte Altfelder als „unbekannt" und behält sie. Vertretbar, in der Spec benennen.
- **Verschachtelte Strukturen** (`passkey_credentials`): ganzer Schlüssel gehört dem Modell, wird als Ganzes ersetzt; unbekannte Unterfelder innerhalb von Passkey-Einträgen bleiben nicht erhalten (außerhalb des Issue-Umfangs).
- **Nebenläufigkeit:** Read-Modify-Write ohne Sperre bleibt Lost-Update-anfällig wie heute; ADR-0083 deckt die Schreibsperre. Nicht Teil dieses Issues.
- **Pflicht-Test:** Zwei verschiedene Nutzer (Mandantentrennung), Zusatzfeld bleibt beim gemischten Profil-PUT, `PendingSmsTo` bleibt geleert. Pre-Snapshot-Hook `data_schema_backup.py` löst bei Edits an `internal/model/*.go` aus (hier voraussichtlich nur `internal/store/user.go`).

## Analysis

### Type
Bug (ADR-0101-Verstoß: Replace statt Merge)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| internal/store/user.go | MODIFY | `SaveUser`: vorhandene user.json als Roh-Map laden, bekannte Schlüssel (Reflection über json-Tags von `model.User`) entfernen, serialisiertes Modell darüberlegen, unbekannte Felder bleiben |
| internal/store/user_saveuser_merge_test.go | CREATE | Verhaltenstests: Zusatzfeld bleibt, `PendingSmsTo` bleibt geleert, Erstanlage ohne Datei, kaputte Datei, zwei Nutzer |
| docs/specs/modules/saveuser_merge.md | CREATE | Spec mit ACs |

### Scope Assessment
- Files: 1 Quelle + 1 Test + 1 Spec
- Estimated LoC: +40/-3 (Quelle), ~+120 Test
- Risk Level: MEDIUM (zentraler Schreibpfad für ~25 Aufrufer, aber Änderung lokal und rückwärtskompatibel)

### Technical Approach
- Nur `SaveUser` ändern; keine Aufrufer anfassen.
- Bekannte Schlüssel: Reflection über die Top-Level-Felder von `model.User` (Tag-Name vor dem Komma, `-` ignorieren). Keine eingebetteten Structs oder `MarshalJSON` im Modell (geprüft) ⇒ Reflection ist vollständig.
- Ablauf: Datei lesen → fehlt: wie bisher schreiben. Vorhanden: Roh-Map; alle bekannten Schlüssel löschen; Modell marshalen → in Map entpacken → darüberlegen; MarshalIndent; `writeFileLogged`.
- Entscheidung beschädigte vorhandene Datei: wie bisher überschreiben (kein Fehler), damit das Konto nicht dauerhaft unspeicherbar wird; per Test festgeschrieben und geloggt.
- Leere `omitempty`-Felder: Schlüssel entfernt, nicht wiederbelebt (Schlüssel wird vorab gelöscht und vom Modell nicht neu gesetzt).
- Verschachtelte Strukturen (`passkey_credentials`) werden als Ganzes ersetzt; unbekannte Unterfelder gehen verloren (außerhalb des Issue-Umfangs, in Spec benennen).
- Schlüsselreihenfolge: Map-Marshal sortiert alphabetisch ⇒ Dateiinhalt ändert sich formal, semantisch gleich; Python-Core liest per JSON, unkritisch.
- Nebenläufigkeit: Lost-Update bleibt wie heute (ADR-0083), nicht Teil.

### Dependencies
Upstream: `fsmode.MkdirAll`, `writeFileLogged`, `ValidUserID`. Downstream: alle SaveUser-Aufrufer (auth*, passkey, telegram_connect, sms_verify, premium_sms_connect, premium_sms_migration, cmd/server/main.go); Python `with_user_profile` liest nur.

### Open Questions
- [x] Beschädigte Datei: überschreiben (entschieden, s. o.)
- Keine offenen PO-Fragen.
