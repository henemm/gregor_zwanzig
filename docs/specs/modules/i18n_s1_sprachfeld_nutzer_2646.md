---
entity_id: i18n_s1_sprachfeld_nutzer_2646
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2646, go, python, model-sonnet]
---

# i18n S1: Sprachfeld `language` am Nutzer (Go schreibt, Go und Python lesen)

**Issue:** #2646 · **Epic:** #2644 · **Modell:** Sonnet · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt 1, 4 (Python-Schnittstelle), 5

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Jeder Nutzer bekommt genau eine Sprache (`de` oder `en`), gespeichert in seiner `user.json` und über das Profil änderbar. Die Go-API schreibt das Feld, Go und Python lesen es über je eine einzige Auflösungsstelle, damit später jeder Kanal (E-Mail, Telegram, SMS, Premium-SMS) und die Weboberfläche dieselbe Sprache sprechen. Bestandsnutzer ohne Feld bleiben deutsch, ihre `user.json` wird nicht angefasst.

## Source

- **File (Go):** `internal/model/user.go`, `internal/store/user.go`, `internal/handler/auth.go`, `internal/middleware/lang_cookie.go` (neu)
- **Identifier (Go):** `model.User.Language`, `(*model.User).Lang()`, `model.IsValidLanguage`, `store.SetUserLanguage`, `middleware.SetLangCookie`, `UpdateProfileHandler`, `RegisterHandlerWithInvites`, `LoginHandler`, `profileResponse`, `toProfileResponse`
- **File (Python):** `src/i18n/__init__.py` (neu), `src/i18n/lang.py` (neu), `src/app/loader.py`
- **Identifier (Python):** `resolve_user_lang`, `language_from_user_dict`, `Lang`, `_parse_user`

> **Schicht-Hinweis:** Go-API (`internal/`, Port 8090) schreibt; Python-Core (`src/`) liest. Kein Frontend-Code (Umschalter und Konto-Auswahl folgen in #2648). Der Pfad zum Nutzerprofil heißt im Repo `/api/auth/profile`; der in den Konventionen genannte `/api/me` existiert nicht und wird nicht angelegt.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `internal/model/user.go` | MODIFY | Feld `Language string \`json:"language,omitempty"\``, Konstanten `LangDe`/`LangEn`, `IsValidLanguage(string) bool`, `(*User).Lang() string` (leer/unbekannt → `de`) |
| `internal/store/user.go` | MODIFY | `SetUserLanguage(id, lang string) error` über `mergeUserJSON` (Merge auf Roh-Ebene, fremde Felder bleiben); Marker `// gz-store-scope-exempt: …` wie bei `SetUserOnboardingFlags` |
| `internal/middleware/lang_cookie.go` | CREATE | `SetLangCookie(w, r, lang, publicHost)`: `gz_lang`, `Path=/`, `MaxAge=31536000`, `SameSite=Lax`, `Secure` über `CookieSecure(r, publicHost)`, nicht HttpOnly |
| `internal/handler/auth.go` | MODIFY | `authRequest.Language`; Registrierung validiert, speichert, setzt Cookie; `profileResponse.Language` (`json:"language"`) aus `u.Lang()`; `UpdateProfileHandler` nimmt `language` (Pointer-Feld) an; `LoginHandler` setzt Cookie mit `user.Lang()` |
| `internal/model/user_language_test.go` | CREATE | `Lang()` und `IsValidLanguage` |
| `internal/handler/profile_language_test.go` | CREATE | Profil lesen/schreiben, zwei Nutzer, Merge, ungültiger Wert, Cookie |
| `internal/handler/register_language_test.go` | CREATE | Registrierung mit/ohne/ungültiger Sprache, Cookie |
| `src/i18n/__init__.py` | CREATE | Exportiert `Lang`, `resolve_user_lang`, `language_from_user_dict` (Paket #2662 ergänzt `t`, `tn`) |
| `src/i18n/lang.py` | CREATE | Einzige Auflösungsstelle: `language_from_user_dict(data)` und `resolve_user_lang(user_id, data_dir=None)` |
| `src/app/loader.py` | MODIFY | `_parse_user`: `UserPreferences.language` aus `language_from_user_dict` statt `prefs_data.get("language","de")` |
| `tests/test_user_language_resolution.py` | CREATE | `resolve_user_lang` ohne Mock gegen Temp-`data_dir`, zwei Nutzer |
| `tests/test_loader_user_language.py` | CREATE | `load_user_from_dict` mit Top-Level-Feld, Preferences-Feld, ohne Feld |

### Querschnitts-Prüfpunkte

- **Trip/Ortsvergleich-Teilung:** nicht berührt; die Sprache hängt am Nutzer, nicht am Trip oder Ortsvergleich.
- **Mandantentrennung:** Die Nutzerkennung kommt im Handler aus `middleware.UserIDFromContext(r.Context())`, in Python als Pflichtparameter `user_id` (kein Default, kein `"default"`; `tests/test_user_id_default_guard.py` bleibt grün). Getestet mit zwei verschiedenen Nutzern (AC-1, AC-6).
- **Kanäle:** nicht direkt berührt (kein Briefing-Inhalt). Die Python-Auflösung ist die eine Stelle, über die E-Mail, Telegram, SMS und Premium-SMS später dieselbe Sprache beziehen (ADR-0095).

## Estimated Scope

- **LoC:** ca. 150-170 Produktcode (Go ca. 95, Python ca. 60), Tests zusätzlich
- **Files:** 12 (7 Produktcode-Dateien, 5 Testdateien)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2645 (S0) | package | ADR-0104 akzeptiert, Vertrag beschreibt `language`/`invalid_language`/`gz_lang` |
| `store.mergeUserJSON`, `SetUserOnboardingFlags` | function | Muster für Merge-Schreiber, der unbekannte Felder erhält |
| `middleware.CookieSecure`, `middleware.SetSessionCookie` | function | Muster für Cookie-Attribute |
| `app.loader.get_data_dir`, `get_data_root`, `VALID_USER_ID_RE` | function | Pfadlogik wie `src/app/config.py` (`with_user_profile`), inklusive Schutz vor unsicheren Kennungen |
| `tests/test_user_id_default_guard.py`, `internal/store/user_scope_guard_test.go` | test | Wächter, die grün bleiben müssen |
| ADR-0101 | adr | Read-Modify-Write mit Merge |

## Implementation Details

**Go: Modell.** Neben den übrigen Profilfeldern in `internal/model/user.go`:

```go
const (LangDe = "de"; LangEn = "en")
func IsValidLanguage(s string) bool { return s == LangDe || s == LangEn }
func (u *User) Lang() string { if IsValidLanguage(u.Language) { return u.Language }; return LangDe }
```

**Go: Profil lesen.** `profileResponse` bekommt `Language string \`json:"language"\`` (ohne `omitempty`), `toProfileResponse` setzt `u.Lang()`. Nutzer ohne gespeichertes Feld erhalten `"de"`; ihre `user.json` bleibt byte-identisch, weil nur gelesen wird.

**Go: Profil schreiben.** In `UpdateProfileHandler` (`auth.go`) kommt `Language *string \`json:"language"\`` in die `update`-Struktur. Direkt nach dem Dekodieren, VOR jedem Schreibzugriff: ist das Feld gesendet und `!model.IsValidLanguage(*update.Language)` (strikt, kein Trimmen, kein Großschreiben, leer ist ungültig), Antwort 400 mit `{"error":"invalid_language"}` im bestehenden Stil. Zwei Wege:

1. Nur `language` gesendet (alle anderen Felder `nil`): `s.SetUserLanguage(userId, lang)` (Merge), frisch laden, `toProfileResponse` zurückgeben, Cookie setzen. Dieser Weg löst keine Bestätigungsmail und keinen SMS-Code aus, weil kein Adressfeld beteiligt ist. Er steht neben dem vorhandenen Frühpfad für die Onboarding-Flags.
2. Gemischter Request: `user.Language = *update.Language` am geladenen Objekt, `SaveUser` am Ende wie bei den übrigen Feldern (das Feld ist typisiert, es überlebt jeden `SaveUser`). Cookie nach erfolgreichem Speichern setzen.

**Go: Registrierung und Login.** `authRequest` erhält `Language string \`json:"language,omitempty"\``. In `RegisterHandlerWithInvites` nach den Passwort-/E-Mail-Prüfungen und VOR `SaveUser`/Einladungseinlösung: ist `req.Language != ""` und ungültig, 400 `{"error":"invalid_language"}` (kein Konto, Einladung nicht verbraucht); gültig → `user.Language = req.Language`; leer → Feld bleibt leer. Nach `SaveUser` und vor dem 201: `middleware.SetLangCookie(w, r, user.Lang(), cfg.PublicHost)`. In `LoginHandler` nach erfolgreichem `issueSession`: `middleware.SetLangCookie(w, r, user.Lang(), publicHost)`.

**Go: Store.** `SetUserLanguage` nutzt `mergeUserJSON` und schreibt nur `m["language"]`:

```go
func (s *Store) SetUserLanguage(id, lang string) error {
	return s.mergeUserJSON(id, func(m map[string]json.RawMessage) { m["language"], _ = json.Marshal(lang) })
}
```

**Python.** `src/i18n/lang.py`:

```python
Lang = Literal["de", "en"]
def language_from_user_dict(data: dict) -> Lang   # Top-Level "language" > "preferences"."language" > "de"
def resolve_user_lang(user_id: str, data_dir: str | Path | None = None) -> Lang
```

`resolve_user_lang` liest `<root>/users/<user_id>/user.json`, wobei `root` bei `data_dir=None` aus `get_data_root()` kommt (importiert lokal in der Funktion, weil `app.loader` und `app.config` einander importieren; Muster `is_test_user_id`). Eine unsichere Kennung (`VALID_USER_ID_RE` passt nicht), eine fehlende oder kaputte Datei, ein Lesefehler und jeder Wert außerhalb {`de`,`en`} ergeben `de` ohne Ausnahme. Es gibt keinen Prozess- oder Modulzustand.

In `_parse_user` (`loader.py:1204`) wird `language=prefs_data.get("language", "de")` zu `language=language_from_user_dict(user_data)`.

**Beispiel vorher → nachher (Loader, `src/app/loader.py:1206`):**
`language=prefs_data.get("language", "de"),` → `language=language_from_user_dict(user_data),`.

**Allowlist-Eintrag:** keiner (Backend-Paket vor den Ratschen). **Golden-Fixture:** keine; der deutsche Pfad ist hier ein reiner Lesezugriff. **Validator, Token-Wächter:** nicht berührt.

## Expected Behavior

- **Input:** `GET`/`PUT /api/auth/profile` mit Sitzung; `POST /api/auth/register` mit optionalem `language`; Python-Aufruf `resolve_user_lang(user_id)`.
- **Output:** Profil enthält `"language":"de"|"en"`; Registrierung und Profil setzen bei gültigem Wert `gz_lang`; Python liefert `"de"` oder `"en"`.
- **Side effects:** `user.json` erhält das Feld `language` nur beim ersten Setzen (per Merge); alle anderen Felder bleiben unverändert. Ungültige Anfragen schreiben nichts.

## Acceptance Criteria

- **AC-1:** Given Nutzer A mit gespeicherter Sprache `en` und Nutzer B ohne Sprachfeld / When beide ihr Profil über `GET /api/auth/profile` abrufen / Then erhält A `en` und B `de`, und die `user.json` von B ist danach byte-identisch zu vorher.
  - Test: internal/handler/profile_language_test.go — echter Router-/Handler-Aufruf mit zwei Sitzungen gegen ein Temp-Datenverzeichnis, Vergleich der Dateibytes von B.

- **AC-2:** Given ein angemeldeter Nutzer / When er `PUT /api/auth/profile` mit `{"language":"fr"}` (oder `""`, `"EN"`) sendet / Then antwortet die API mit 400 und `{"error":"invalid_language"}`, und seine `user.json` ist byte-identisch zu vorher.
  - Test: internal/handler/profile_language_test.go — drei ungültige Werte, je Dateibytes vor/nach vergleichen.

- **AC-3:** Given eine `user.json` mit `display_name`, `mail_to` und einem dem Modell unbekannten Zusatzfeld / When der Nutzer nur `{"language":"en"}` sendet bzw. `language` zusammen mit `display_name` / Then enthält die Datei danach `"language":"en"`, alle übrigen Felder (auch das unbekannte) bleiben erhalten, und es wird weder eine Bestätigungsmail noch ein SMS-Code ausgelöst.
  - Test: internal/handler/profile_language_test.go — Datei vor/nach als JSON-Objekte vergleichen; Versand-Naht (`sendVerificationMailFn`) zählt Aufrufe, erwartet 0.

- **AC-4:** Given eine Registrierung / When `language` mit `en` mitgeschickt wird / Then enthält die neue `user.json` `"language":"en"`; ohne `language` fehlt das Feld; mit `"fr"` antwortet die API 400 `invalid_language`, es entsteht kein Konto und ein mitgesendeter Einladungstoken bleibt unverbraucht.
  - Test: internal/handler/register_language_test.go — drei Registrierungen gegen Temp-Store, Existenz und Inhalt der `user.json`, Einladungsstatus.

- **AC-5:** Given Registrierung, Anmeldung und ein Profil-Update mit `language` / When die Antwort geprüft wird / Then enthält sie `Set-Cookie: gz_lang=<sprache>` mit `Path=/`, `Max-Age=31536000`, `SameSite=Lax`, ohne `HttpOnly`, und `Secure` genau bei https.
  - Test: internal/handler/profile_language_test.go und internal/handler/register_language_test.go — Cookie-Attribute aus der echten Antwort (http und https-PublicHost).

- **AC-6:** Given Nutzer A mit `en` in seiner `user.json` und Nutzer B ohne Feld, ein unbekannter Nutzer, eine kaputte Datei und die unsichere Kennung `../bob` / When Python `resolve_user_lang` je Kennung aufruft / Then liefert es `en` für A, sonst jeweils `de`, ohne Ausnahme, und der Aufruf für B liest nie die Datei von A.
  - Test: tests/test_user_language_resolution.py — echte Dateien in einem Temp-`data_dir`, kein Mock.

- **AC-7:** Given ein Nutzer-Dictionary / When `load_user_from_dict` es lädt / Then ergibt sich `preferences.language` aus Top-Level-`language`, ersatzweise aus `preferences.language`, sonst `de`; ein Wert wie `fr` wird zu `de`.
  - Test: tests/test_loader_user_language.py — vier Eingaben gegen die echte Ladefunktion.

## Known Limitations

- Annahme: Der Fehler bei ungültiger Sprache folgt dem heutigen Antwortstil `{"error":"invalid_language"}`; die Umstellung auf `{"code","message"}` übernimmt Paket #2675 (G1).
- Annahme: `GET /api/auth/profile` liefert die wirksame Sprache (`de` bei fehlendem Feld), nicht den leeren Rohwert; das erfüllt ADR-0104 Nr. 9 („Nutzer ohne Feld bleiben deutsch") und die AC-Skizze des Issues. Die Konventionen nennen „de/en/leer"; der Leerfall entfällt in der Antwort. Paket #2675 muss einen Nutzer ohne Feld deshalb ebenfalls als `de` behandeln (kein Vorrang für Cookie oder `Accept-Language` bei angemeldeten Nutzern).
- Annahme: `PUT` akzeptiert nur `de`/`en` in Kleinschreibung; ein leerer Wert setzt die Sprache nicht zurück.
- Der Cookie `gz_lang` von Login und Registrierung erreicht den Browser nur, wenn das Frontend die Set-Cookie-Header weiterreicht (Login-Action in #2648); die Antwort auf `PUT /api/auth/profile` erreicht den Browser direkt.
- Die Python-Auflösung liest die Datei bei jedem Aufruf; ein Zwischenspeicher ist bewusst nicht Teil dieses Pakets (kein globaler Zustand).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (Nr. 1, 2, 9), ADR-0101
- **Rationale:** Die Sprache gehört dem Nutzer und hat je Schicht genau eine Auflösungsstelle; Schreiben geschieht per Merge, damit Bestandsdaten nie verloren gehen.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
