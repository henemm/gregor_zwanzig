---
entity_id: profile_mail_ratelimit
type: bugfix
created: 2026-09-22
updated: 2026-09-22
status: draft
version: "1.0"
tags: [security, bugfix, go-api, rate-limit, auth, mail-bombing, issue-2404]
---

# Rate-Limit für Bestätigungsmails aus dem Profil-Update

## Approval

- [ ] Approved

## Purpose

`PUT /api/auth/profile` löst bei jeder Änderung der wirksamen Kontaktadresse (`email`/`mail_to`) eine Bestätigungsmail an die neu eingetragene Adresse aus — ohne Mengenbegrenzung. Im Unterschied zu Register/Login/Forgot/Reset/Verify/Resend-Verification/Magic-Link (alle über `authmw.NewIPRateLimiter` begrenzt) ist der Profil-Update-Endpoint ungebremst. Ein angemeldeter Nutzer kann so durch wiederholtes Wechseln der Adresse beliebig viele Mails an eine beliebige Fremdadresse auslösen (Mail-Bombing, Betreiberkosten, Absender-Reputation bei Resend). Diese Spec begrenzt ausschließlich den Mail-auslösenden Weg (Adressänderung + Nachversand), ohne das normale Profil-Speichern (Passkey-Hinweis, Anzeigename, Telegram-Trennen) zu beeinträchtigen.

## Source

- **File:** `internal/handler/auth.go`
- **Identifier:** `func UpdateProfileHandler` (Zeile 853), `func ResendVerificationHandler` (Zeile 1178), `func dispatchVerificationMail` (Zeile 1212)

> **Schicht-Hinweis:** Reiner Go-API-Code (`internal/`, `cmd/`). Kein Python-Core-, kein zwingender Frontend-Change.

## Estimated Scope

- **LoC:** production ~140, Tests ~210 → Gesamt ~350, über dem 250-LoC-Limit — `loc_limit_override` in `/40` nötig
- **Files:** 3 Produktivdateien (`internal/handler/auth.go`, `internal/handler/profile_mail_ratelimit.go` neu, `internal/router/router.go`) + `internal/handler/profile_mail_ratelimit_test.go` (neu) + `internal/handler/auth_test.go` (MODIFY, Signaturänderungen)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `golang.org/x/time/rate` | External Library (bereits Projekt-Dependency) | Token-Bucket-Implementierung (`rate.Limiter`, `Reserve()`), Basis für den neuen Limiter |
| `internal/middleware/ratelimit.go` (`IPRateLimiter`) | Go-Struct (Vorbild) | Bauart-Vorlage: Token-Bucket, `map[string]*entry`, `lastSeen`, Cleanup-Goroutine, `Retry-After`-Berechnung — hier aber schlüsselbasiert statt IP-basiert und ohne `http.Handler`-Middleware-Wrapper |
| `internal/handler/premium_sms_ratelimit.go` (`PremiumSmsRateLimiter`) | Go-Struct (Analogie) | Zeigt das etablierte Muster „Limiter als Parameter direkt in den Handler durchgereicht, nicht als HTTP-Middleware" |
| `store.EffectiveContactAddress` / `store.NormalizeEmailAddress` (`internal/store/`) | Go-Funktionen | Liefern die bereits normalisierte (klein geschriebene, getrimmte) Zieladresse als Schlüssel — kein zusätzlicher Case-Fold-Schritt nötig |
| `middleware.UserIDFromContext` (`internal/middleware/auth.go:106`) | Go-Funktion | Liefert die echte `user_id` aus dem Auth-Kontext (CLAUDE.md-Pflicht: nie `"default"`) — in `UpdateProfileHandler` bereits verwendet |
| `store.Store.SaveUser` / `LoadUser` | Go-Methoden | Persistenz — Reihenfolge-kritisch: Limiter-Check MUSS vor `SaveUser` laufen |
| `internal/router/router.go:44-127` | Go-Datei | Sieben bestehende `authmw.NewIPRateLimiter(...)`-Verdrahtungen als Referenzmuster (Wert, Kommentarstil `// Issue #N — ...`) |
| `internal/handler/auth_test.go` | Go-Testdatei (bestehend) | Ruft `UpdateProfileHandler(s, cfg)` und `ResendVerificationHandler(s, cfg)` an mehreren Stellen mit der alten Signatur auf — jede Signaturänderung MUSS dort nachgezogen werden, sonst Compile-Fehler in der gesamten Testsuite |

## Root Cause Analysis

### Aktueller Zustand (BROKEN)

`internal/router/router.go:90`:

```go
r.Put("/api/auth/profile", handler.UpdateProfileHandler(deps.Store, *deps.Config))
```

Kein Rate-Limit, im Gegensatz zu allen sieben anderen `authmw`-Endpunkten (Zeilen 44, 48, 57, 61, 66, 73, 116, 120, 126, 151). `ResendVerificationHandler` (Zeile 75) hat zwar ein IP-Limit (`resendVerifyLimiter`, 5/h), aber `req.Username` kommt aus dem Body — verschiedene IPs oder verschiedene eigene Konten können denselben Zielnutzer bzw. dieselbe Zieladresse treffen, ohne dass ein Limit je Zieladresse existiert.

### Sicherheits-Implikation

- Mail-Bombing: Ein angemeldeter Nutzer kann durch wiederholtes `PUT /api/auth/profile` mit wechselnder Zieladresse beliebig viele Bestätigungsmails an eine fremde Adresse auslösen.
- Betreiberkosten (Resend-Versand) und Absender-Reputationsrisiko bei Massenversand an unbeteiligte Dritte.
- Kein Cross-Account-Schutz: Mehrere eigene oder kompromittierte Konten können gemeinsam dieselbe Opferadresse fluten, da bisher kein adressbezogenes Limit existiert.

## Implementation Details

### Kernbefund: Reihenfolge Speichern/Versand

In `UpdateProfileHandler` läuft `s.SaveUser(*user)` (Zeile ~1080) **vor** `dispatchVerificationMail(s, cfg, userId, user)` (Zeile ~1088). Eine Limiter-Prüfung *innerhalb* von `dispatchVerificationMail` käme strukturell zu spät: Die Zustandsänderung (inkl. `PendingContactAddress`/`PendingContactField`) wäre bereits persistiert, bevor der Versand geprüft würde — genau der vom Issue verbotene Zustand „ausstehend, aber nie bestätigbar". Die Prüfung MUSS deshalb an **beiden Aufrufstellen separat und synchron vor der jeweiligen Wirkung** sitzen, nicht zentral in `dispatchVerificationMail`. `dispatchVerificationMail` selbst bleibt unverändert (kein zusätzlicher Limiter-Parameter, keine dritte Fehlerquelle durch Signatur-Drift).

### 1. Neuer Limiter: `internal/handler/profile_mail_ratelimit.go` (neu)

Schlüsselbasierter Zwei-Ebenen-Limiter nach Vorbild `IPRateLimiter` (Token-Bucket, `sync.Mutex`, Cleanup-Goroutine), aber mit `Allow(userId, address string) bool` statt `http.Handler`-Wrapper und einer dritten Methode `AllowAddressOnly(address string) bool` für den Resend-Pfad (siehe Abschnitt 3):

```
type MailFloodLimiter struct{ mu sync.Mutex; userBuckets, addressBuckets map[string]*entry; rate rate.Limit; burst int; window time.Duration }
func NewMailFloodLimiter(n int, window time.Duration) *MailFloodLimiter
func (l *MailFloodLimiter) Allow(userId, address string) bool
func (l *MailFloodLimiter) AllowAddressOnly(address string) bool
```

**Atomarität ohne Teilverbrauch bei Ablehnung:** `Allow` hält die Mutex über den gesamten Vorgang. Mechanismus je Bucket: `res := bucket.Reserve()`; ist `!res.OK()` oder `res.Delay() > 0` (Token nicht sofort verfügbar), gilt der Bucket als erschöpft, `res.Cancel()` gibt das reservierte Token sofort zurück, kein Verbrauch. Erst wenn **beide** Buckets (User- und Adress-Bucket) eine sofort verfügbare Reservierung liefern, bleiben beide Reservierungen bestehen (= Verbrauch). Schlägt einer der beiden fehl, wird **auch die bereits erfolgreiche Reservierung des anderen per `Cancel()` zurückgegeben** — weder der User- noch der Adress-Bucket verliert bei einer Ablehnung ein Token (AC-7). `AllowAddressOnly` prüft/konsumiert ausschließlich den Adress-Bucket nach demselben Reserve/Cancel-Muster, ohne einen User-Bucket zu berühren.

Cleanup-Goroutine entfernt Einträge beider Maps, die länger als das Fenster ungenutzt sind (Vorbild `cleanupLoop` aus `ratelimit.go`).

Werte (Größenordnung laut Issue): `NewMailFloodLimiter(10, time.Hour)` — 10 Bestätigungsmails pro Stunde je Schlüssel (User-ID und Zieladresse unabhängig voneinander gezählt).

### 2. `UpdateProfileHandler` (`auth.go`)

Prüfung einfügen an der Stelle, an der `sendVerification` auf `true` gesetzt wird (im `switch`-Block um Zeile 1050), vor dem finalen `s.SaveUser(*user)` (Zeile ~1080). Aufruf: `mailLimiter.Allow(userId, newEffective)`. Schlägt die Prüfung fehl:
- Response: `HTTP 429`, `Content-Type: application/json`, Header `Retry-After: <Sekunden>` (identische Berechnung wie `IPRateLimiter.Middleware`: `window.Seconds() / burst` = `3600 / 10` = `360`), Body `{"error":"rate_limit_exceeded"}`
- **Kein** `SaveUser`-Aufruf — weder für die Adressänderung noch für andere im selben Request geänderte Felder (z. B. `display_name`)
- **Kein** `dispatchVerificationMail`-Aufruf
- Der komplette Request wird verworfen (Teil-Save-Entscheidung, siehe unten)

Die Handler-Signatur bekommt einen zusätzlichen Parameter: `func UpdateProfileHandler(s *store.Store, cfg config.Config, mailLimiter *MailFloodLimiter) http.HandlerFunc`.

### 3. `ResendVerificationHandler` (`auth.go`)

**Entscheidung Bucket-Wahl (bindend):** Dieser Endpoint ist unauthentifiziert und nimmt `username` aus dem Body (`req.Username`) — ein Angreifer kann einen beliebigen fremden Zielnutzer angeben. Würde hier `Allow(username, address)` verwendet, könnte ein Fremder gezielt das User-Kontingent des Opfers leerlaufen lassen und diesem so eigene, legitime Profil-Updates blockieren (DoS gegen das Opfer über einen Endpoint, den das Opfer selbst nie aufgerufen hat). Deshalb konsumiert der Resend-Pfad **ausschließlich den Adress-Bucket** über `mailLimiter.AllowAddressOnly(address)` — kein User-Bucket wird berührt (AC-8 prüft dies gezielt).

Prüfung vor dem bestehenden `dispatchVerificationMail(...)`-Aufruf (Zeile ~1199), mit identischer Zieladressen-Auswahl wie `dispatchVerificationMail` selbst (`user.PendingContactAddress`, sonst `EffectiveContactAddress(user)` bzw. `mail_to`/`email`-Fallback — hier dupliziert statt extrahiert, um die Limiter-Check-Signatur einfach zu halten). Bei Limit-Überschreitung: `dispatchVerificationMail` wird **nicht** aufgerufen, die Response bleibt unverändert `200 {"status":"ok"}` (bestehende Privacy-Invariante — Kontoexistenz/Zustand darf von außen nicht unterscheidbar sein, das Limit ist rein intern, kein 429 hier). Das bestehende IP-Limit (`resendVerifyLimiter`, 5/h, `router.go:73`) bleibt unverändert bestehen — das neue Adress-Limit wirkt zusätzlich und deckt den Fall ab, dass verschiedene IPs/Konten denselben Zielnutzer treffen.

Die Handler-Signatur bekommt denselben zusätzlichen Parameter: `func ResendVerificationHandler(s *store.Store, cfg config.Config, mailLimiter *MailFloodLimiter) http.HandlerFunc`.

### 4. Router-Verdrahtung (`internal/router/router.go`)

Eine gemeinsame Instanz, geteilt zwischen beiden Handlern (das Adress-Limit muss endpointübergreifend gelten):

```go
// Issue #2404 — Rate-Limit auf Bestaetigungsmails aus Profil-Update und
// Resend-Verification: je 10/h pro User-ID und pro Zieladresse, verhindert
// Mail-Bombing ueber wiederholte Adresswechsel.
mailFloodLimiter := handler.NewMailFloodLimiter(10, time.Hour)
```

Durchreichen an beide bestehenden Verdrahtungsstellen (Zeile 75: `ResendVerificationHandler`, Zeile 90: `UpdateProfileHandler`).

### Teil-Save-Entscheidung (bindend, keine PO-Frage)

Bei Limit-Überschreitung wird der **gesamte** Request mit 429 abgewiesen, keine Felder werden gespeichert — auch nicht harmlose wie `display_name` im selben Request. Begründung: (a) das Issue verlangt explizit, dass die Adressänderung nicht gespeichert wird; (b) ein Teil-Save würde dem Aufrufer verschleiern, dass ein Teil der Anfrage verworfen wurde, und widerspricht dem bestehenden Muster der Funktion (409/500-Zweige brechen ebenfalls hart ab statt teilweise zu speichern). Konsequenz für Read-Modify-Write (CLAUDE.md): Bei 429 wird `SaveUser` gar nicht erst aufgerufen — es entsteht kein Teil-Zustand, der später gemergt werden müsste.

## Expected Behavior

### Vor Fix (BROKEN)

- **Input:** Angemeldeter Nutzer sendet 50× `PUT /api/auth/profile` mit wechselnder `mail_to`-Adresse (z. B. `opfer+1@example.com`, `opfer+2@example.com`, ... oder wiederholt dieselbe)
- **Output:** Alle 50 Requests werden verarbeitet, alle 50 lösen `dispatchVerificationMail` aus
- **Side effects:** Bis zu 50 Bestätigungsmails an die (ggf. fremde) Zieladresse, unbegrenzt

### Nach Fix (GREEN)

- **Input (1.–10. Adresswechsel desselben Nutzers, < 1h):** `PUT /api/auth/profile` mit wirksamer Adressänderung
- **Output:** Standard-Handler-Antworten (200, Adresse als `PendingContactAddress` gesetzt bzw. sofort übernommen je nach Verifikationsstand), Mail wird verschickt
- **Input (11. Adresswechsel desselben Nutzers, < 1h):** `PUT /api/auth/profile`
- **Output:** HTTP 429, Header `Retry-After: 360`, Body `{"error":"rate_limit_exceeded"}`, Profil bleibt unverändert (kein `SaveUser`)
- **Input (zwei verschiedene Nutzer wechseln beide auf dieselbe Zieladresse, gemeinsam > 10× < 1h):** Ab dem gemeinsamen 11. Versuch 429, unabhängig davon, welches Konto den Request stellt
- **Input (`resend-verification` für einen Nutzer mit bereits ausgeschöpftem Adress-Limit):** `200 {"status":"ok"}`, aber keine Mail wird verschickt, kein Verbrauch eines User-Buckets
- **Side effects:** Profil-Updates ohne Adressänderung (Anzeigename, Passkey-Hinweis, Telegram-Trennen) bleiben vollständig unberührt — kein Limiter-Zugriff, kein 429

## Acceptance Criteria

- **AC-1:** Given ein angemeldetes, bereits bestätigtes Konto (`EmailVerifiedAt` gesetzt) hat sein User-Mail-Limit von 10 Bestätigungsmails pro Stunde bereits ausgeschöpft / When es erneut `PUT /api/auth/profile` mit einer weiteren, bisher unbenutzten wirksamen Adressänderung sendet / Then antwortet der Endpoint mit HTTP 429 und `Retry-After`-Header, es wird keine weitere Bestätigungsmail verschickt und die Adressänderung wird nicht gespeichert (`SaveUser` unterbleibt vollständig).
  - Test: Elf aufeinanderfolgende `PUT /api/auth/profile`-Requests desselben bestätigten Nutzers mit jeweils neuer `mail_to`-Adresse; die ersten zehn antworten mit Erfolg, der elfte mit 429 und gesetztem `Retry-After`; anschließendes `GET /api/auth/profile` zeigt weiterhin den Stand nach dem zehnten Request, nicht den elften.

- **AC-2:** Given zwei unterschiedliche, bereits bestätigte Nutzer-Konten wechseln unabhängig voneinander ihre Kontaktadresse jeweils auf dieselbe fremde Zieladresse / When die Summe beider Wechsel das gemeinsame Adress-Limit von 10 pro Stunde überschreitet / Then greift ab der gemeinsamen elften Anfrage HTTP 429, unabhängig davon, welches der beiden Konten den auslösenden Request stellt (Cross-Account-Flood-Schutz).
  - Test: Bestätigter Nutzer A sendet sechs `PUT /api/auth/profile`-Requests auf `opfer@example.com` (bei bestätigtem Konto bleibt die tatsächliche `oldEffective`-Adresse unverändert, jede Anfrage löst daher erneut den Pending-Zweig und damit Mailversand aus), danach sendet bestätigter Nutzer B fünf Requests auf dieselbe Adresse; die ersten vier von B gehen durch (Summe 10), der fünfte (Summe 11) antwortet 429 — obwohl B selbst sein eigenes User-Limit noch nicht erreicht hat.

- **AC-3:** Given ein Nutzer ändert zunächst auf Adresse A (innerhalb des Limits), danach unabhängig auf Adresse B (ebenfalls innerhalb des Limits) / When beide Adress-Buckets für sich genommen unter 10 Anfragen pro Stunde bleiben / Then funktionieren beide Adressänderungen ungehindert, da Adress-A- und Adress-B-Bucket unabhängig voneinander gezählt werden.
  - Test: Derselbe Nutzer sendet fünf Requests mit Adresse A gefolgt von fünf Requests mit Adresse B (User-Summe 10, aber zwei getrennte Adress-Buckets mit je fünf) — alle zehn Requests antworten mit Erfolg, kein 429.

- **AC-4:** Given das Zieladressen-Limit einer Adresse ist über den Profil-Update-Pfad bereits ausgeschöpft / When derselbe oder ein anderer Nutzer zusätzlich `POST /api/auth/verify-email/resend` für ein Konto mit ausstehender Bestätigung an dieselbe Adresse aufruft / Then bleibt die HTTP-Antwort unverändert `200 {"status":"ok"}` (Privacy-Invariante), aber `dispatchVerificationMail` wird nicht ausgeführt und es wird keine Mail verschickt.
  - Test: Adress-Limit über zehn `PUT /api/auth/profile`-Requests ausschöpfen, danach `POST /api/auth/verify-email/resend` für ein Konto mit `PendingContactAddress` auf derselben Adresse aufrufen; Response-Body ist `{"status":"ok"}`, der Test-Seam (`sendVerificationMailFn`-Aufrufzähler bzw. äquivalenter Beobachtungspunkt) zeigt keinen zusätzlichen Sendeversuch.

- **AC-5:** Given ein Nutzer hat sein User-Mail-Limit noch nicht ausgeschöpft und sendet zwischendurch mehrere `PUT /api/auth/profile`-Requests mit ausschließlich harmlosen Feldern (z. B. `display_name`, ohne `email`/`mail_to` wirksam zu ändern) / When er danach trotzdem volle 10 Adresswechsel durchführt / Then gehen alle 10 Adresswechsel ohne vorzeitiges 429 durch — die harmlosen Requests haben kein Kontingent verbraucht.
  - Test: Fünf `PUT /api/auth/profile`-Requests mit ausschließlich geändertem `display_name` senden, danach zehn Requests mit jeweils neuer Adresse senden — alle zehn Adress-Requests antworten mit Erfolg (kein 429 bereits nach dem fünften Adresswechsel, wie es bei fälschlich mitgezähltem Kontingent der Fall wäre).

- **AC-6:** Given ein Nutzer ändert im selben Request sowohl seine Adresse als auch harmlose Felder (z. B. `display_name`), und sein User- oder das Adress-Mail-Limit ist bereits ausgeschöpft / When dieser kombinierte Request gestellt wird / Then wird der gesamte Request mit HTTP 429 abgelehnt und auch die harmlosen Feldänderungen werden nicht gespeichert (kein Teil-Save).
  - Test: User-Mail-Limit ausschöpfen, danach einen Request mit gleichzeitiger neuer `mail_to`-Adresse UND geändertem `display_name` senden; Antwort ist 429, anschließendes `GET /api/auth/profile` zeigt den unveränderten alten `display_name` — nicht den im 429-Request gesendeten neuen Wert.

- **AC-7:** Given eine fremde Zieladresse X wurde durch ein anderes bestätigtes Konto bereits mit exakt zehn Requests voll ausgeschöpft (Adress-Bucket 10/10), und Nutzer A's eigenes User-Kontingent ist zu diesem Zeitpunkt noch vollständig unbenutzt (0/10) / When A einen einzelnen Request mit derselben Adresse X sendet und dieser mit 429 abgelehnt wird (Adress-Bucket voll) / Then verbraucht diese Ablehnung keinen Token aus A's eigenem User-Bucket — A kann danach noch alle zehn erlaubten Adresswechsel auf eigene, unbenutzte Adressen durchführen, nicht nur neun.
  - Test: Ein anderes bestätigtes Konto sättigt Adresse X mit genau zehn `PUT /api/auth/profile`-Requests (10/10, kein Token mehr frei). Bestätigter Nutzer A sendet danach einen Request mit Adresse X → 429 (Adress-Bucket voll). Direkt im Anschluss sendet A zehn Requests mit jeweils eigenen, bisher unbenutzten Adressen → alle zehn müssen mit 200 antworten. Fehlt das `Cancel()` auf dem User-Bucket bei der Ablehnung, wäre A's User-Bucket durch den abgewiesenen Versuch bereits bei 1/10 und nur neun der zehn Folge-Requests würden gelingen, der zehnte bekäme fälschlich 429 — der Test unterscheidet damit sichtbar zwischen korrektem und fehlendem Cancel-Verhalten.

- **AC-8:** Given ein Angreifer kennt den `username` eines fremden, bereits bestätigten Opfer-Kontos mit einer bestehenden ausstehenden Adressänderung (`PendingContactAddress` gesetzt) / When der Angreifer zehnmal `POST /api/auth/verify-email/resend` mit diesem `username` aufruft, um das Adress-Limit der ausstehenden Adresse auszuschöpfen / Then bleibt das User-Mail-Kontingent des Opfers davon vollständig unberührt — das Opfer kann anschließend selbst per `PUT /api/auth/profile` auf eine völlig andere, frische Adresse wechseln und erhält 200, nicht 429.
  - Test: Opfer-Konto mit bestehender `PendingContactAddress` P vorbereiten. Angreifer ruft zehnmal `POST /api/auth/verify-email/resend` mit `username=<opfer>` auf (sättigt den Adress-Bucket von P, berührt aber laut Implementierungsvorgabe `AllowAddressOnly` keinen User-Bucket). Danach sendet das Opfer selbst `PUT /api/auth/profile` mit einer neuen, bisher unbenutzten Adresse Q ≠ P → erwartet 200. Würde der Resend-Pfad stattdessen `Allow(username, address)` verwenden, wäre das Opfer-User-Kontingent nach den zehn Resend-Aufrufen bereits bei 10/10 und der PUT-Request bekäme fälschlich 429, obwohl das Opfer selbst noch keinen einzigen Adresswechsel vorgenommen hat.

## Files to Modify

| Datei | Änderung | LoC |
|---|---|---|
| `internal/handler/profile_mail_ratelimit.go` (neu) | `MailFloodLimiter` Struct, `NewMailFloodLimiter`, `Allow`, `AllowAddressOnly`, `cleanupLoop` | ~90 |
| `internal/handler/auth.go` | Limiter-Parameter in `UpdateProfileHandler`- und `ResendVerificationHandler`-Signatur, Prüfung + 429-Antwort an beiden Aufrufstellen | ~40 |
| `internal/router/router.go` | Instanziierung `mailFloodLimiter`, Durchreichen an beide Handler-Verdrahtungen | ~10 |
| `internal/handler/profile_mail_ratelimit_test.go` (neu) | Unit-Tests für `MailFloodLimiter` (Burst, unabhängige Schlüssel, Reserve/Cancel-Verhalten) + Handler-Integrationstests für AC-1 bis AC-8 | ~190 |
| `internal/handler/auth_test.go` | Bestehende Aufrufe von `UpdateProfileHandler(s, cfg)`/`ResendVerificationHandler(s, cfg)` auf die neue Signatur (zusätzlicher Limiter-Parameter) nachziehen | ~20 |

Gesamt: 5 Dateien (2 neu, 3 Code-Änderungen). ~350 LoC.

## Risk Analysis

- **Restart resettet Limiter:** Akzeptiert, analog `register_rate_limit.md` — Restarts sind nicht angreifergesteuert, Single-Instanz-Deployment macht persistenten Limiter-State unnötig.
- **Resend-Pfad als DoS-Vektor gegen fremde User-Kontingente:** Erkannt und durch die Bucket-Wahl in Implementation Details Abschnitt 3 entschärft — `ResendVerificationHandler` konsumiert ausschließlich `AllowAddressOnly`, nie den User-Bucket eines fremden Zielkontos. Ohne diese Trennung könnte ein Angreifer über wiederholte Resend-Aufrufe mit fremdem `username` gezielt das legitime Profil-Update-Kontingent des Opfers leerlaufen lassen — abgesichert durch AC-8.
- **Race zwischen konkurrierenden Requests desselben Schlüssels:** `Allow`/`AllowAddressOnly` halten die Mutex über den gesamten Reserve/Cancel-Vorgang beider Buckets — zwei gleichzeitige Requests desselben Nutzers oder derselben Adresse werden serialisiert geprüft, kein TOCTOU-Fenster zwischen Prüfung und Verbrauch.
- **Teilverbrauch bei Ablehnung:** Durch das Reserve/Cancel-Muster (siehe Implementation Details) verliert weder der User- noch der Adress-Bucket ein Token, wenn der jeweils andere Bucket die Ablehnung verursacht — abgesichert durch AC-7.
- **Memory-Leak:** Cleanup-Goroutine entfernt analog `IPRateLimiter` alle Einträge (beide Maps), die länger als das Fenster ungenutzt sind.
- **Echte Nutzer:** 10 Adresswechsel/Stunde je Nutzer und je Zieladresse liegen weit über jedem realistischen Bedarf (eine Adressänderung ist ein seltener Vorgang, nicht Teil des Normalbetriebs).

## Known Limitations

- Limiter-State ist prozesslokal (wie `IPRateLimiter`): Bei Neustart der Go-API werden alle Buckets zurückgesetzt. Akzeptiert — Restarts sind nicht angreifergesteuert, und Single-Instanz-Deployment (Systemd, je 1 Prozess Prod/Staging) macht einen gemeinsamen Backend-Store unnötig.
- Adress-Bucket-Schlüssel ist die normalisierte Zieladresse (`EffectiveContactAddress`/`NormalizeEmailAddress`). Zwei orthografisch unterschiedliche, aber technisch gleichwertige Adressvarianten (z. B. mit `+`-Tag-Suffix bei Gmail) werden als unterschiedliche Schlüssel behandelt — kein Schutz gegen Adress-Aliasing, das ist bewusst außerhalb des Scopes (S2 behandelt reines Mengenlimit, keine Adress-Aliasing-Erkennung).
- Kein Logging der 429-Events in dieser Scheibe. Falls künftig ein Audit-Trail gewünscht ist, kann ein `log.Printf` analog zu bestehenden Limiter-Stellen ergänzt werden.

## Bewusst NICHT im Scope

- SMS-Nummer-Verifikation (Sammel-Issue #2153, Scheibe S3)
- SMS-Tageslimit (Sammel-Issue #2153, Scheibe S4)
- Quoten (Sammel-Issue #2153, Scheibe S5)
- Adress-Aliasing-Erkennung (z. B. `+`-Tag-Normalisierung über die bestehende `NormalizeEmailAddress` hinaus)
- Persistenter Limiter-State über Restarts hinweg (Redis o. ä.) — analog zur Begründung in `register_rate_limit.md`, aktuell nicht nötig
- Frontend-Änderungen an `account/+page.svelte` — nur falls in `/50-implement` eine fehlende generische 429-Behandlung auffällt, sonst kein Scope-Zuwachs

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Ergänzung eines bestehenden, bereits mehrfach etablierten Musters (schlüsselbasierter Token-Bucket-Limiter, Analogie `IPRateLimiter`/`PremiumSmsRateLimiter`). Keine neue Architektur-Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth-Paradigma) betroffen.

## Bezug

- GitHub Issue: [henemm/gregor_zwanzig#2404](https://github.com/henemm/gregor_zwanzig/issues/2404) — S2 aus Sammel-Issue #2153
- Sammel-Issue: [henemm/gregor_zwanzig#2153](https://github.com/henemm/gregor_zwanzig/issues/2153)
- Epic: [henemm/gregor_zwanzig#2138](https://github.com/henemm/gregor_zwanzig/issues/2138) (Multi-User)
- Referenz-Format: `docs/specs/bugfix/register_rate_limit.md`, `docs/specs/bugfix/forgot_reset_rate_limit.md`, `docs/specs/bugfix/login_rate_limit.md`
- Reihenfolge-Voraussetzung: Issue #2147 Scheibe B2 (Pending-Contact-Adressänderungs-Mechanik, `switch`-Block in `UpdateProfileHandler`)

## Changelog

- 2026-09-22: Initial spec created based on Issue #2404 analysis (Kontext-Dokument `docs/context/feat-2404-profil-mail-ratelimit.md`)
- 2026-09-22: Nach Advisor-Review 1 überarbeitet — fehlende Pflicht-Abschnitte (Root Cause Analysis, Files to Modify, Risk Analysis) ergänzt, Resend-Bucket-Entscheidung (nur Adress-Bucket, kein fremdes User-Kontingent) dokumentiert, `Retry-After`-Header spezifiziert, Verifikationsstand in AC-1/AC-2 präzisiert, AC-5 beobachtbar umformuliert, AC-7 für Nicht-Teilverbrauch bei Ablehnung ergänzt
- 2026-09-22: Nach Advisor-Review 2 korrigiert — AC-7-Zählung war off-by-one und bewies das Gegenteil (Request wäre erlaubt statt abgewiesen worden), auf „Adresse zuvor voll ausgeschöpft, A's Versuch abgewiesen" korrigiert; AC-8 ergänzt, um die Resend-Bucket-Entscheidung (`AllowAddressOnly` statt `Allow(username, address)`) testbar zu machen
