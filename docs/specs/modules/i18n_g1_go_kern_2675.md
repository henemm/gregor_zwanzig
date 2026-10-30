---
entity_id: i18n_g1_go_kern_2675
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2675, go, model-sonnet]
---

# i18n G1: Go-i18n-Kern (internal/i18n, Sprache im Request-Kontext, Fehlerobjekt code + message)

**Issue:** #2675 · **Epic:** #2644 · **Modell:** Sonnet · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitte 1, 2, 5

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Ein angemeldeter Nutzer mit Sprache `en` bekommt von der Go-API Fehlermeldungen auf Englisch, ein Nutzer mit `de` oder ohne Einstellung bekommt sie auf Deutsch, und Besucher ohne Konto bekommen sie nach Cookie `gz_lang` beziehungsweise `Accept-Language`. Dazu entsteht das Paket `internal/i18n` (eingebettete Kataloge, `T`, `Tn`, Sprachauflösung), eine Middleware, die die Sprache einmal je Anfrage bestimmt, und das neue Fehlerobjekt `{"code","message"}`. Dieses Paket legt nur das Fundament; die Umstellung der Handler (G2, G3) und der Mails (G4) folgt, hier wird genau ein Weg als Muster umgestellt: die Hilfsfunktion `bailIf`, über die `GET /api/briefings/{id}` und weitere Briefing-/Ortsvergleich-Routen ihre Fehler schreiben.

## Source

- **File:** `internal/i18n/` (neu), `internal/middleware/lang.go` (neu), `internal/handler/httperr.go` (neu), `internal/router/router.go`, `internal/handler/auth.go`, `internal/handler/briefing_subscription.go`
- **Identifier:** `i18n.Lang`, `i18n.Args`, `i18n.T`, `i18n.Tn`, `i18n.Parse`, `i18n.FromContext`, `i18n.WithLang`, `i18n.FromRequest`, `i18n.ErrorBody`, `middleware.Lang`, `middleware.SetLangCookie`, `handler.WriteError`, `handler.WriteErrorWith`, `bailIf`

> **Schicht-Hinweis:** Reine Go-API (`internal/`). Kein Python-Code, kein Frontend-Code. Die Python- und die Frontend-Kataloge entstehen in P1 (#2662) und S2 (#2647); hier gilt nur Konventionen Abschnitt 5.
>
> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** `bailIf` und damit die Fehlertexte sind für beide Briefing-Arten (`kind=route|vergleich`) dieselben; es gibt keinen Trip- oder Compare-eigenen Fehlerpfad. Go hat keinen Katalog-Bereich `allgemein`; geteilte Texte liegen in `fehler.*`.
> - **Mandantentrennung:** Die Middleware lädt die Sprache ausschließlich für die `user_id` aus dem Auth-Kontext (`middleware.UserIDFromContext`), nie einen Fallback `"default"`. Ohne Nutzerkennung wird nichts geladen. Zwei Nutzer mit verschiedenen Sprachen in einem Testserver (AC-4).
> - **Kanäle:** Das Paket berührt keinen Briefing- oder Alarm-Inhalt. E-Mail, Telegram, SMS und Premium-SMS bleiben unverändert; Konto-Mails folgen in G4.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `internal/i18n/i18n.go` | CREATE | `Lang`, `De`, `En`, `Args`, `Parse`, `CookieName = "gz_lang"`, `Default` (Standardkatalog), Paket-Funktionen `T`, `Tn`, `Has` |
| `internal/i18n/catalog.go` | CREATE | `//go:embed messages`, `Catalog`, `NewCatalog(fs.FS) (*Catalog, error)`, Laden aller `messages/<lang>/<bereich>.json`, Schlüssel- und Präfixprüfung, Platzhalter-Ersetzung, Fallback-Log einmal je Schlüssel |
| `internal/i18n/request.go` | CREATE | `FromContext`, `WithLang`, `FromRequest`, Parser für `Accept-Language` |
| `internal/i18n/errorbody.go` | CREATE | `ErrorBody(lang, code, args) map[string]any` (Suchkette, Alt-Felder `error`/`detail`) |
| `internal/i18n/messages/de/{fehler,auth,konto,fach,mail}.json` | CREATE | fünf Dateien; `fehler.json` mit den 12 Start-Schlüsseln (siehe unten), die übrigen vier als `{}` |
| `internal/i18n/messages/en/{fehler,auth,konto,fach,mail}.json` | CREATE | gleiche fünf Dateien, englisch |
| `internal/middleware/lang.go` | CREATE | `Lang(users UserLoader)`, `UserLoader`, `SetLangCookie` |
| `internal/handler/httperr.go` | CREATE | `WriteError`, `WriteErrorWith` |
| `internal/router/router.go` | MODIFY | `r.Use(authmw.Lang(deps.Store))` direkt nach `AuthMiddleware` (Zeile 43) |
| `internal/handler/auth.go` | MODIFY | Cookie `gz_lang` in `issueSessionWithoutVerificationGate` (deckt alle Anmeldewege), `RegisterHandlerWithInvites`, `UpdateProfileHandler` |
| `internal/handler/briefing_subscription.go` | MODIFY | `bailIf(w, r, cond, status, code)` ruft `WriteError`; 17 Aufrufer erhalten `r` |
| `internal/handler/briefing_history.go`, `internal/handler/briefing_preview.go`, `internal/handler/compare_preset.go` | MODIFY | je ein bzw. vier `bailIf`-Aufrufer erhalten `r` (1 + 1 + 4) |
| `docs/reference/api_contract.md` | MODIFY | in Abschnitt 0 (Konventionen) neuer Unterabschnitt „Fehlerobjekt `code`/`message`" |
| `internal/i18n/uebersetzung_test.go` | CREATE | `T`, `Tn`, Platzhalter, Fallback |
| `internal/i18n/katalog_paritaet_test.go` | CREATE | Paritätstest (`// doc-compliance-test`) |
| `internal/i18n/sprachwahl_anfrage_test.go` | CREATE | Auflösungsreihenfolge, `Accept-Language` |
| `internal/middleware/sprache_zwei_nutzer_test.go` | CREATE | Middleware mit zwei Nutzern, Cookie-Attribute |
| `internal/handler/fehlerobjekt_sprache_test.go` | CREATE | `WriteError` und `GET /api/briefings/{id}` aus Nutzersicht |

## Estimated Scope

- **LoC:** ca. 370 Code ohne Katalogdaten und Tests (i18n-Paket ~250, Middleware ~80, `httperr.go` ~35, Handler-Anpassungen ~60 geänderte Zeilen). Das liegt über dem Workflow-Limit von 250: `workflow.py set-field loc_limit_override 500` einplanen.
- **Files:** 28 (16 neue Code- und Katalogdateien, 6 geänderte Go-Dateien, 1 Doku, 5 Testdateien)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2646 (S1) | Paket | `model.User.Language`, `model.User.Lang()`, `PUT /api/auth/profile` mit `language`, Register mit `language` (Voraussetzung, vorher gemergt) |
| `internal/model` (`model.User`) | Modul | `FromRequest(r, user *model.User)`; `model` importiert `i18n` nie (kein Zyklus) |
| `internal/store` (`LoadUser`) | Modul | liefert das Nutzerprofil für die Middleware über die Schnittstelle `UserLoader` |
| `internal/middleware` (`UserIDFromContext`, `CookieSecure`) | Modul | Nutzerkennung aus dem Auth-Kontext, `Secure`-Attribut des Cookies |
| `docs/reference/i18n_glossar.md` | Doku | Wortwahl der englischen Texte |
| ADR-0104 | ADR | Sprache am Nutzer, Auflösungsreihenfolge |
| #2677 (G3), #2676 (G2), #2678 (G4), #2679 (G5) | Pakete | Folgepakete; G5 darf direkt nach diesem Paket starten |

## Implementation Details

**1. Paket `internal/i18n`** (Signaturen laut Konventionen Abschnitt 5, nichts davon ändern).

```go
type Lang string
const (De Lang = "de"; En Lang = "en")
type Args map[string]any
func Parse(s string) Lang                                   // "en" -> En, alles andere -> De
func T(lang Lang, key string, args Args) string
func Tn(lang Lang, key string, count int, args Args) string // count==1 -> key+".one", sonst key+".other"; {count} ist implizit
func Has(key string) bool                                   // Schlüssel im de-Katalog vorhanden
func FromContext(ctx context.Context) Lang                  // Default De
func WithLang(ctx context.Context, lang Lang) context.Context
func FromRequest(r *http.Request, user *model.User) Lang
func ErrorBody(lang Lang, code string, args Args) map[string]any
```

- `catalog.go`: `//go:embed messages` und `fs.WalkDir`. Jede Datei `messages/<lang>/<bereich>.json` ist ein flaches `{"schlüssel": "Text"}`. Beim Laden wird geprüft: Schlüssel passt auf `^[a-z0-9_.]+$` mit 2 bis 4 Segmenten und beginnt mit `<bereich>.`; Verstoß liefert einen Fehler mit Dateiname und Schlüssel. Der Standardkatalog `Default` wird in `init()` über `NewCatalog(embedFS)` gebaut (Fehler = `panic`, weil ein kaputter Einbettungs-Stand ein Programmierfehler ist). `NewCatalog(fs.FS)` ist exportiert, damit Tests mit `testing/fstest.MapFS` arbeiten, ohne den echten Katalog zu verändern.
- Platzhalter: jedes `{name}` wird durch `fmt.Sprint(args["name"])` ersetzt; ein Platzhalter ohne Argument bleibt sichtbar als `{name}` stehen. Fehlt ein `en`-Schlüssel, wird der `de`-Text ausgegeben und einmal je Prozess und Schlüssel `i18n fallback: <key>` geloggt (`sync.Map`). Fehlt der Schlüssel in beiden Sprachen, kommt der Schlüssel selbst zurück (ebenfalls einmal geloggt).
- `FromRequest(r, user)`: (1) `user != nil` und `user.Language` ist `de` oder `en` gewinnt, (2) Cookie `gz_lang` mit genau `de` oder `en`, (3) `Accept-Language`: Einträge nach `q` absteigend (Standard `q=1`, `q=0` ignoriert), erster Eintrag, dessen Hauptsprache vor dem `-` `de` oder `en` ist, (4) `De`. Ein ungültiger Cookie-Wert wird ignoriert, nicht als `de` gewertet.

**2. Suchkette und Alt-Felder in `ErrorBody`.** Der Fehlercode `code` ist snake_case und stabil. Die Meldung wird in dieser Reihenfolge gesucht (erster Treffer im `de`-Katalog gewinnt): zuerst, falls `args["variante"]` ein nicht leerer String `v` ist, die Schlüssel `fehler.<code>_<v>`, `auth.fehler.<code>_<v>`, `konto.fehler.<code>_<v>`, `fach.fehler.<code>_<v>`; danach dieselben vier Präfixe mit `<code>` ohne Variante. Ohne Treffer gilt `fehler.unbekannt` mit `{code}`. Das Ergebnis ist `{"code": code, "message": <Text>, "error": code, "detail": <detail>}`: `error` ist ein Übergangsfeld mit demselben Wert wie `code` (bisherige Clients lesen `error`), `detail` ist `args["detail"]`, wenn dort ein nicht leerer String steht, sonst `message`. Ein Code darf nur in einem der vier Bereiche vorkommen (Paritätstest prüft Doppelungen).

**3. `internal/handler/httperr.go`.**

```go
func WriteError(w http.ResponseWriter, r *http.Request, status int, code string, args i18n.Args) {
	WriteErrorWith(w, r, status, code, args, nil)
}
// WriteErrorWith ergaenzt das Fehlerobjekt um Zusatzfelder (z. B. "resource", "compare_presets").
func WriteErrorWith(w http.ResponseWriter, r *http.Request, status int, code string, args i18n.Args, extra map[string]any) {
	body := i18n.ErrorBody(i18n.FromContext(r.Context()), code, args)
	for k, v := range extra { body[k] = v }
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}
```

Header wie `Retry-After` setzt der Aufrufer vor dem Aufruf.

**4. Middleware `internal/middleware/lang.go`.** `type UserLoader interface{ LoadUser(id string) (*model.User, error) }` (`*store.Store` erfüllt sie). `Lang(users)` liest `UserIDFromContext`; nur bei nicht leerer Kennung wird `users.LoadUser(uid)` aufgerufen. Ein Ladefehler wird geloggt und wie „kein Nutzer" behandelt (die Anfrage wird nie abgebrochen). Dann `ctx = i18n.WithLang(ctx, i18n.FromRequest(r, user))`. `SetLangCookie(w, r, lang, publicHost)` setzt `gz_lang` mit `Path=/`, `Max-Age=31536000`, `SameSite=Lax`, `Secure` über `CookieSecure(r, publicHost)`, **nicht** `HttpOnly`.

**5. Cookie bei Login, Register, Profil-Update (`internal/handler/auth.go`).** Es wird nur gesetzt, wenn der Nutzer eine gespeicherte Sprache hat (`user.Language != ""`); sonst bleibt die Browser-Vorbelegung unberührt.
- `issueSessionWithoutVerificationGate` (Zeile 257): das Profil `u` wird derzeit nur innerhalb der `if`-Kette geladen (Zeile 261). `u` vor die Kette ziehen (`u, err := s.LoadUser(userId)`), die Fehlerzweige unverändert lassen, und nach `middleware.SetSessionCookie(...)` (Zeile 288) bei `u != nil && u.Language != ""` `middleware.SetLangCookie(w, r, i18n.Parse(u.Language), publicHost)` aufrufen. Das ist die einzige Stelle aller Anmeldewege (Passwort, Magic-Link, Passkey, Google).
- `RegisterHandlerWithInvites`: vor der 201-Antwort (Zeile 194) mit der gespeicherten `user.Language` und `cfg.PublicHost`.
- `UpdateProfileHandler`: nach erfolgreichem `SaveUser` (Zeile 1394), vor der Antwort (Zeile 1413), mit der gespeicherten Sprache.

**6. Beispiel-Umstellung (Muster für G2/G3).** `internal/handler/briefing_subscription.go:36-42`, vorher:

```go
func bailIf(w http.ResponseWriter, cond bool, status int, code string) bool {
	if !cond { return false }
	writeJSON(w, status, map[string]string{"error": code})
	return true
}
```

nachher:

```go
func bailIf(w http.ResponseWriter, r *http.Request, cond bool, status int, code string) bool {
	if !cond { return false }
	WriteError(w, r, status, code, nil)
	return true
}
```

Aufrufer, z. B. Zeile 76: `bailIf(w, trip == nil, http.StatusNotFound, "not_found")` wird zu `bailIf(w, r, trip == nil, http.StatusNotFound, "not_found")`. Die Codes der 23 Aufrufer (`validation_error`, `store_error`, `not_found`, `bad_request`, `kind_required`) sind alle in `fehler.json` angelegt, das Alt-Feld `error` bleibt gleich, bestehende Tests mit `{"error":"not_found"}` bleiben grün. `writeBriefingKindRequired` (Zeile 30) bleibt unverändert und wird in G3 umgestellt.

**7. Start-Schlüssel `fehler.json`** (`de` | `en`):

| Schlüssel | de | en |
|---|---|---|
| `fehler.not_found` | Nicht gefunden. | Not found. |
| `fehler.unauthorized` | Bitte melde dich an. | Please sign in. |
| `fehler.forbidden` | Dafür fehlt dir die Berechtigung. | You do not have permission to do this. |
| `fehler.store_error` | Die Daten konnten nicht gespeichert oder geladen werden. Bitte versuche es später erneut. | The data could not be saved or loaded. Please try again later. |
| `fehler.validation_error` | Die Eingabe ist ungültig. | The input is invalid. |
| `fehler.bad_request` | Die Anfrage ist ungültig. | The request is invalid. |
| `fehler.invalid_request` | Die Anfrage ist ungültig. | The request is invalid. |
| `fehler.internal_error` | Interner Fehler. Bitte versuche es später erneut. | Internal error. Please try again later. |
| `fehler.kind_required` | Briefing-Art fehlt oder ist ungültig (erlaubt: route, vergleich) | Briefing kind is missing or invalid (allowed: route, vergleich) |
| `fehler.rate_limit_exceeded` | Zu viele Anfragen. Bitte versuche es später erneut. | Too many requests. Please try again later. |
| `fehler.service_unavailable` | Der Dienst ist gerade nicht verfügbar. | The service is currently unavailable. |
| `fehler.unbekannt` | Unbekannter Fehler ({code}). | Unknown error ({code}). |

Der `de`-Text von `fehler.kind_required` ist der heutige Wortlaut aus `briefing_send.go:30`.

**8. `docs/reference/api_contract.md`.** Neuer Unterabschnitt in Abschnitt 0: Fehlerobjekt `{"code": "<snake_case>", "message": "<Text in Nutzersprache>"}`; Übergangsfelder `error` (= `code`) und `detail` (= `message`, bzw. technischer Zusatz); Zusatzfelder je Endpunkt bleiben möglich; Sprachauflösung und Cookie `gz_lang`; Hinweis, dass Antworten des Python-Cores unverändert durchgereicht werden. Die bestehenden Formen (`{"error":…}`, Form A in 10.1) werden mit G2/G3 vereinheitlicht und dort nachgeführt.

**9. Allowlist-Eintrag.** Keiner: die Ratsche (G5) existiert noch nicht. G5 Teil 1 startet direkt nach diesem Paket.

## Expected Behavior

- **Input:** HTTP-Anfragen an die Go-API, angemeldet (Cookie `gz_session`) oder öffentlich, mit optionalem Cookie `gz_lang` und Header `Accept-Language`.
- **Output:** Fehlerantworten der umgestellten Pfade als `application/json` mit `code`, `message`, `error`, `detail`; `message` in der aufgelösten Sprache. Anmelde-, Register- und Profil-Antworten tragen bei gespeicherter Sprache zusätzlich `Set-Cookie: gz_lang=…`.
- **Side effects:** Je authentifizierter Anfrage ein Lesezugriff auf `data/users/<user_id>/user.json` (ohne Zwischenspeicher, wie die Sitzungsprüfung). Einmaliges Log `i18n fallback: <key>` je Schlüssel, falls ein `en`-Text fehlt.

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter Nutzer mit gespeicherter Sprache `en` / When er `GET /api/briefings/unbekannt?kind=route` aufruft / Then antwortet die API mit 404, `code` `not_found` und der englischen `message` „Not found.", das Übergangsfeld `error` lautet weiter `not_found`.
  - Test: internal/handler/fehlerobjekt_sprache_test.go — echter Router mit `AuthMiddleware` und `Lang`, echtes Nutzerverzeichnis im Temp-Ordner, Sitzungs-Cookie des `en`-Nutzers; geprüft wird der ausgelieferte JSON-Body.

- **AC-2:** Given ein angemeldeter Nutzer mit Sprache `de` und ein Besucher ohne Anmeldung mit `Accept-Language: de` / When beide dieselbe Fehlerantwort auslösen / Then lautet die `message` auf Deutsch („Nicht gefunden."), und ein Besucher mit `Accept-Language: en-US,en;q=0.9,de;q=0.8` bekommt die englische.
  - Test: internal/handler/fehlerobjekt_sprache_test.go — dieselbe Anfrage mit und ohne Sitzung; öffentliche Anfrage über die echte Kette `Lang` + `WriteError` auf einem Test-Endpunkt (kein Spiegel-Mock der Auflösung).

- **AC-3:** Given Nutzer ohne gespeicherte Sprache, Cookie `gz_lang=en` und `Accept-Language: de` / When eine Anfrage ankommt / Then gilt `en` (Cookie vor Header); hat der Nutzer dagegen `language=de` gespeichert und das Cookie `en`, gilt `de` (Nutzer vor Cookie); ein Cookie mit Wert `fr` wird ignoriert.
  - Test: internal/i18n/sprachwahl_anfrage_test.go — `FromRequest` mit allen Kombinationen der Reihenfolge Nutzer > Cookie > `Accept-Language` > `de`, inklusive `q`-Werten und unbekanntem Cookie-Wert.

- **AC-4:** Given zwei Nutzer A (`en`) und B (`de`) im selben Testserver / When beide gleichzeitig (parallele Anfragen) dieselbe Fehlerantwort auslösen / Then bekommt jeder ausschließlich die Meldung seiner Sprache, und die `user.json` beider Nutzer bleibt byte-identisch.
  - Test: internal/middleware/sprache_zwei_nutzer_test.go — parallele Anfragen mit beiden Sitzungen gegen die echte Kette; kein globaler Sprachzustand; Dateivergleich vor und nach den Anfragen.

- **AC-5:** Given der Katalog, in dem für einen Schlüssel der `en`-Text fehlt oder die Platzhalter von `de` und `en` abweichen / When `go test ./internal/i18n/...` läuft / Then schlägt der Test fehl und nennt den Schlüssel; der echte Katalog besteht den Test, und ein Fehlercode kommt in höchstens einem der vier Bereiche `fehler`, `auth`, `konto`, `fach` vor.
  - Test: internal/i18n/katalog_paritaet_test.go (`// doc-compliance-test`, Paritätstest) — die Prüffunktion wird zusätzlich mit absichtlich fehlerhaften `fstest.MapFS`-Katalogen aufgerufen und muss dort scheitern.

- **AC-6:** Given ein Nutzer mit gespeicherter Sprache `en` / When er sich anmeldet (Passwort, Magic-Link, Passkey oder Google), sich registriert oder sein Profil speichert / Then setzt die Antwort das Cookie `gz_lang=en` mit `Path=/`, `Max-Age=31536000`, `SameSite=Lax`, ohne `HttpOnly` und mit `Secure` bei https; ein Nutzer ohne gespeicherte Sprache bekommt kein `gz_lang`.
  - Test: internal/middleware/sprache_zwei_nutzer_test.go — echte Handler `LoginHandler`, `RegisterHandlerWithInvites`, `UpdateProfileHandler` mit Temp-Datenverzeichnis; geprüft werden `Set-Cookie`-Attribute für zwei Nutzer (mit und ohne Sprache).

- **AC-7:** Given ein Katalog, in dem nur `de` einen Plural-Schlüssel und einen Platzhalter-Text hat / When `Tn(En, "x", 1, …)`, `Tn(En, "x", 2, …)` und `T(En, "x", Args{"name":"Anna"})` aufgerufen werden / Then wählt `Tn` `.one` bei 1 und `.other` sonst mit gesetztem `{count}`, `T` ersetzt `{name}`, und der fehlende `en`-Text fällt auf den `de`-Text zurück, wobei der Fallback genau einmal je Schlüssel geloggt wird.
  - Test: internal/i18n/uebersetzung_test.go — `NewCatalog(fstest.MapFS{…})`, Log-Ausgabe über `log.SetOutput` mitgelesen; zwei Aufrufe desselben Schlüssels erzeugen eine Logzeile.

## Known Limitations

- **Annahme (Übergangsfelder):** `WriteError` schreibt zusätzlich `error` (= `code`) und `detail`, weil rund 70 Stellen im Frontend und viele Go-Tests das Alt-Feld lesen. Ein Abbau der Felder ist nicht Teil des Epics #2644 (Nebenbefund).
- **Annahme (Cookie nur bei gespeicherter Sprache):** Nutzer ohne `language` bekommen kein `gz_lang`, damit die Browser-Vorbelegung nicht überschrieben wird.
- **Annahme (Katalogpfade):** Es gilt die Verzeichnisstruktur `internal/i18n/messages/{de,en}/<bereich>.json` aus den Konventionen (Abschnitt 2); die ältere Schreibweise `messages/{de,en}.json` im ADR-0104 ist durch die Konventionen überholt.
- **Annahme (Suchkette):** Die Konventionen nennen den Schlüssel `fehler.<code>`; damit G2 und G3 ihre Codes ohne Merge-Konflikt in `auth`, `konto` und `fach` ablegen können, durchsucht `ErrorBody` die vier Präfixe nacheinander. Der Parameter `variante` wird gebraucht, wo ein Code heute mehrere deutsche Texte trägt (G3).
- Der `AuthMiddleware`-Pfad (401, 503) läuft vor der Sprach-Middleware und bleibt in G1 unverändert; G3 stellt ihn um und löst die Sprache dort über `i18n.FromRequest(r, nil)`.
- Fehlerantworten ohne Sprach-Middleware (direkte Handler-Aufrufe in Tests) fallen auf `de` zurück.
- Pro authentifizierter Anfrage eine zusätzliche Dateileseoperation; ein Zwischenspeicher ist bewusst nicht vorgesehen (gleiche Begründung wie bei der Sitzungsprüfung).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** Die Sprache ist eine Nutzereigenschaft mit genau einem Auflösungsweg je Schicht; `internal/i18n` ist der Go-Weg ohne neue Abhängigkeit.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
