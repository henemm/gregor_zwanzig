---
entity_id: saveuser_merge
type: module
created: 2026-11-03
updated: 2026-11-03
status: draft
version: "1.0"
tags: [go, store, user, adr-0101, datenverlust]
---

# SaveUser: Read-Modify-Write mit Merge

## Approval

- [ ] Approved

## Purpose

`Store.SaveUser` soll die Datei `user.json` nicht mehr komplett aus dem typisierten Modell neu schreiben, sondern mit der vorhandenen Datei zusammenführen. Felder, die das Modell nicht kennt, gehen dadurch bei keinem Konto-Schreibvorgang mehr verloren (ADR-0101, Issue #2687, Epic #2138).

## Source

- **File:** `internal/store/user.go`
- **Identifier:** `Store.SaveUser` (Go-API-Schicht; keine Änderung am Python-Core, am Frontend oder am Modell `internal/model/user.go`)

> **Schicht:** Go-API (`internal/store`). Python-Core liest `user.json` nur (`src/app/config.py::with_user_profile`).
> **Trip/Ortsvergleich-Teilung:** nicht berührt (reine Konto-Persistenz).
> **Kanäle:** kein Briefing- oder Alarm-Inhalt betroffen.
> **Mandantentrennung:** `SaveUser` arbeitet auf `user.ID` des übergebenen Nutzers; getestet mit zwei verschiedenen Nutzern.

## Estimated Scope

- **LoC:** ca. 40 Quelle, ca. 120 Test
- **Files:** 2 (`internal/store/user.go`, neue `internal/store/user_saveuser_merge_test.go`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `fsmode.MkdirAll` | intern | Nutzerverzeichnis anlegen (unverändert) |
| `writeFileLogged` | intern | Datei schreiben (unverändert) |
| `model.User` | intern | Quelle der „bekannten" JSON-Schlüssel (Top-Level-Felder samt `json`-Tag) |
| ~25 `SaveUser`-Aufrufer | intern | `auth*`, `passkey`, `telegram_connect`, `sms_verify`, `premium_sms_connect`, `premium_sms_migration`, `cmd/server/main.go`: bleiben unverändert |

## Implementation Details

```
SaveUser(user):
  ID prüfen, Verzeichnis anlegen                      (wie bisher)
  modellJSON = Marshal(user)  -> Map "modell"
  vorhanden  = user.json lesen
  - Datei fehlt                -> modell schreiben    (wie bisher)
  - anderer Lesefehler (keine Leserechte, user.json ist Verzeichnis):
        Fehler zurückgeben, NICHT überschreiben (kein Datenverlust)
  - Datei vorhanden, lesbares JSON-Objekt:
        roh = Datei als map[string]RawMessage
        für jeden bekannten Schlüssel (Reflection über json-Tags
        der Top-Level-Felder von model.User, "-" ignoriert): delete(roh, key)
        roh ← modell darüberlegen
        schreiben (MarshalIndent)
  - Datei vorhanden, aber kein gültiges JSON-Objekt (auch exakt `null`):
        warnen (Log) und modell schreiben wie bisher (Konto bleibt speicherbar)
```

Wirkung: unbekannte Schlüssel bleiben; gesetzte bekannte Schlüssel werden aktualisiert; bekannte `omitempty`-Schlüssel mit leerem Wert verschwinden und werden nicht wiederbelebt (z. B. `pending_sms_to`).

## Expected Behavior

- **Input:** `model.User` mit gültiger Kennung.
- **Output:** `user.json` = unbekannte Alt-Felder + vollständiger Modellstand.
- **Side effects:** Schlüsselreihenfolge in der Datei wird alphabetisch (Map-Serialisierung), inhaltlich gleich; Python-Core liest per JSON, unkritisch.

## Acceptance Criteria

- **AC-1:** Given eine vorhandene `user.json` mit einem dem Modell unbekannten Zusatzfeld / When `SaveUser` mit geändertem `display_name` aufgerufen wird / Then enthält die Datei danach das Zusatzfeld unverändert und den neuen `display_name`.
  - Test: Datei mit Fremdfeld anlegen, `SaveUser`, Datei als Roh-Map prüfen.

- **AC-2:** Given eine `user.json` mit gesetztem `pending_sms_to` / When `SaveUser` mit leerem `PendingSmsTo` aufgerufen wird / Then fehlt der Schlüssel `pending_sms_to` in der Datei (nicht wiederbelebt) und ein gleichzeitig vorhandenes Zusatzfeld bleibt erhalten.
  - Test: Roh-Map nach `SaveUser` auf Abwesenheit des Schlüssels und Anwesenheit des Zusatzfelds prüfen.

- **AC-3:** Given ein Konto ohne vorhandene `user.json` (auch ohne Verzeichnis) / When `SaveUser` aufgerufen wird / Then wird Verzeichnis und Datei wie bisher neu angelegt und `LoadUser` liefert den gespeicherten Nutzer.
  - Test: Erstanlage, `LoadUser` vergleicht Felder.

- **AC-4:** Given eine vorhandene `user.json`, die kein gültiges JSON-Objekt ist / When `SaveUser` aufgerufen wird / Then schlägt der Aufruf nicht fehl, die Datei enthält danach den gültigen Modellstand (Konto bleibt speicherbar).
  - Test: Datei mit Müll füllen, `SaveUser` ohne Fehler, `LoadUser` korrekt.

- **AC-5:** Given zwei verschiedene Nutzer A und B, beide mit eigenem Zusatzfeld / When `SaveUser` für A läuft / Then bleibt die Datei von B byte-identisch und das Zusatzfeld von A bleibt erhalten.
  - Test: Zwei Nutzer, Datei B vor/nach vergleichen (Mandantentrennung).

- **AC-6:** Given ein Nutzer mit Passkey-Einträgen und Zusatzfeld / When `SaveUser` mit geänderten Passkey-Daten läuft / Then wird `passkey_credentials` als Ganzes durch den Modellstand ersetzt und das Zusatzfeld bleibt erhalten.
  - Test: Roh-Map prüfen; dokumentiert zugleich die Grenze (unbekannte Unterfelder in Passkey-Einträgen gehen verloren).

- **AC-7:** Given ein vollständig gefülltes `model.User` / When `SaveUser` und danach `LoadUser` laufen / Then ist der geladene Nutzer gleich dem gespeicherten (Round-Trip), und die bestehenden Store- und Handler-Tests zu Konten bleiben grün.
  - Test: Round-Trip-Vergleich; bestehende Suiten `internal/store` und `internal/handler` unverändert grün.

## Known Limitations

- Unbekannte Unterfelder **innerhalb** verschachtelter bekannter Strukturen (`passkey_credentials`) bleiben nicht erhalten (Schlüssel gehört dem Modell, wird als Ganzes ersetzt).
- Altfelder nach einer Umbenennung im Modell gelten als „unbekannt" und bleiben stehen.
- Lost-Update bei gleichzeitigen Schreibern bleibt wie bisher; die Schreibsperre ist Gegenstand von ADR-0083, nicht dieses Issues.
- Die „TYPISIERT, damit sie jeden SaveUser-Schreiber überstehen"-Kommentare im Modell bleiben unangetastet (kein Rückbau in diesem Issue).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0101
- **Rationale:** ADR-0101 verlangt Read-Modify-Write mit Merge statt Replace. Die Korrektur sitzt zentral in `SaveUser`, damit alle ca. 25 Aufrufer profitieren, ohne einzeln angepasst zu werden. Kein neues ADR nötig, da keine Abweichung von einer bestehenden Entscheidung.

## Changelog

- 2026-11-03: Erstfassung (Issue #2687)
- 2026-11-03: Implementation Details präzisiert (Adversary-Befunde F001/F002): Lesefehler außer „Datei fehlt" = Fehler statt Überschreiben; `null`-Datei wird wie kaputtes JSON behandelt. Tests: `TestSaveUserMerge_LesefehlerUeberschreibtNicht`, `TestSaveUserMerge_AC4_NullDateiBleibtSpeicherbar`. Beides sind Implementierungsdetails innerhalb der freigegebenen ACs (Schutz der Bestandsdaten, ADR-0101; `null` fällt unter AC-4 „kein gültiges JSON-Objekt"), keine neuen Akzeptanzkriterien.
