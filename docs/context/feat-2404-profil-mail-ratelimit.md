# Context: feat-2404-profil-mail-ratelimit

## Request Summary

S2 aus dem Sammel-Issue #2153 (Epic #2138): `PUT /api/auth/profile` löst bei jeder Adressänderung eine Bestätigungsmail an die neu eingetragene Adresse aus — ohne Mengenbegrenzung. Ein angemeldeter Nutzer kann so beliebig viele Mails an eine fremde Adresse schicken (Mail-Bombing, Betreiberkosten, Absender-Reputation bei Resend). Ziel: den Mail-auslösenden Weg begrenzen, ohne das normale Profil-Speichern (Passkey-Hinweis, Anzeigename, Telegram-Trennen usw.) zu blockieren.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/handler/auth.go:1205-1260` | `dispatchVerificationMail(s, cfg, userId, user)` — **einziger** Choke-Point, der eine Bestätigungsmail verschickt. Ermittelt den Empfänger (`user.PendingContactAddress`, sonst `MailTo`/`Email`), erzeugt ein 24h-Token, versendet asynchron mit 20s-Timeout. Wird von zwei Stellen aufgerufen: |
| `internal/handler/auth.go:1087` | `UpdateProfileHandler` — ruft `dispatchVerificationMail` bei jeder wirksamen Adressänderung eines unbestätigten Kontos oder bei ausstehender Bestätigung eines bestätigten Kontos auf (`sendVerification`-Flag, gesetzt in den Zweigen ab `auth.go:1010`). **Kein Rate-Limit auf `PUT /api/auth/profile`** (`internal/router/router.go:90`). |
| `internal/handler/auth.go:1178-1203` | `ResendVerificationHandler` (`POST /api/auth/verify-email/resend`) — ruft `dispatchVerificationMail` ebenfalls auf. Ist bereits IP-begrenzt: `resendVerifyLimiter := authmw.NewIPRateLimiter(5, time.Hour)` (`router.go:73-76`). Nimmt aber `username` aus dem Body entgegen — Angreifer kann über verschiedene IPs oder verschiedene eigene Konten denselben Zielnutzer/dieselbe Zieladresse treffen, ohne dass ein Limit je Zieladresse existiert. |
| `internal/middleware/ratelimit.go` | `IPRateLimiter` — Token-Bucket **pro IP**, als `http.Handler`-Middleware verdrahtet (`Middleware()` wrappt einen Handler, prüft `clientIP(r)`). Ungeeignet für diese Aufgabe in der jetzigen Form: gebraucht wird eine Begrenzung **pro Nutzer** und **pro Zieladresse**, nicht pro IP — mehrere Nutzer/IPs könnten sonst gemeinsam dieselbe Fremdadresse fluten. Das Muster (Token-Bucket, Cleanup-Goroutine, `map[string]*Entry` mit `lastSeen`) ist aber die etablierte Bauart im Projekt und sollte für einen neuen, generisch **schlüsselbasierten** Limiter wiederverwendet werden (Konstruktor `NewIPRateLimiter(burst, window)` als Vorlage). |
| `internal/handler/premium_sms_ratelimit.go` | `PremiumSmsRateLimiter` — Gegenbeispiel: ein reiner Zähler ohne Zeitfenster/Token-Bucket, prozessweit ein einziger Zähler (kein Schlüssel je Nutzer). Nicht das passende Muster hier, da wir mehrere unabhängige Schlüssel (User-ID, Zieladresse) brauchen. |
| `internal/router/router.go:44-127` | Zeigt alle sieben bestehenden `authmw.NewIPRateLimiter(...)`-Verdrahtungen als Referenzmuster (Wert, Kommentarstil `// Issue #N — ...`). `PUT /api/auth/profile` (Zeile 90) und `GET /api/auth/profile` (Zeile 89) sind bisher ungebremst. |
| `internal/middleware/auth.go:106` | `UserIDFromContext(ctx)` — liefert die echte `user_id` aus dem Auth-Kontext; Pflicht-Quelle laut CLAUDE.md (nie `"default"`). Wird in `UpdateProfileHandler` bereits verwendet (`auth.go:855`). |
| `docs/specs/bugfix/register_rate_limit.md` | Referenz-Spec-Struktur für einen bereits umgesetzten `IPRateLimiter`-Fix (Format: Purpose, Source, Dependencies, Root Cause Analysis) — als Vorlage für die neue Spec geeignet. |
| `docs/specs/bugfix/forgot_reset_rate_limit.md`, `docs/specs/bugfix/login_rate_limit.md` | Zwei weitere Referenz-Specs desselben Musters (IP-Limiter je Endpoint). |
| `internal/handler/auth_test.go` | Bestehende Tests für `UpdateProfileHandler`/`ResendVerificationHandler` — Ansatzpunkt für neue Testfälle (429 bei Überschreitung, Speicherung unterbleibt). |
| `internal/middleware/ratelimit_test.go` | Test-Muster für Token-Bucket-Verhalten (Burst, unabhängige Schlüssel, Header-Präferenz) — als Vorlage für Tests des neuen schlüsselbasierten Limiters. |

## Existing Patterns

- **Ein Limiter-Typ pro Schutzbedarf, instanziiert im Router, injiziert als Middleware oder Parameter.** Alle sieben bestehenden Fälle sind `IPRateLimiter`, gewrappt um einen kompletten Handler. Diese Aufgabe braucht eine Variante ohne HTTP-Middleware-Wrapper, weil die Prüfung *innerhalb* von `dispatchVerificationMail` sitzen soll (nur wenn tatsächlich eine Mail verschickt würde — Analogie zur Heartbeat-Pflicht „nur bei echtem Erfolg", hier: „nur beim echten Sendeversuch") und **zwei** unabhängige Schlüssel prüft (User-ID, Zieladresse).
- **Read-Modify-Write bei Profiländerungen ist Pflicht** (CLAUDE.md, BUG-DATALOSS-GR221) — bei Überschreitung des Limits darf `SaveUser` für die Adressänderung nicht erfolgen; andere Felder derselben Anfrage (Anzeigename etc.) werden aktuell in derselben `SaveUser`-Transaktion gespeichert. Zu klären in der Spec: blockiert eine Limit-Überschreitung nur die Adressänderung oder den ganzen Request?
- **429 + `Retry-After` + JSON-Fehlerkörper** ist das etablierte Antwortformat (`ratelimit.go:78-96`).
- **Kommentarstil:** Jede neue Verdrahtung im Router trägt einen Kommentar `// Issue #N — <Begründung>` über der Zeile.
- **Testdateibenennung nach Verhalten**, nicht nach Issue-Nummer (CLAUDE.md) — z. B. `internal/handler/profile_mail_ratelimit_test.go`, nicht `test_2404.go`.

## Dependencies

- **Upstream:** `golang.org/x/time/rate` (bereits Projekt-Dependency, siehe `ratelimit.go`); `store.Store.LoadUser`/`SaveUser`; `config.Config` (für `dispatchVerificationMail`).
- **Downstream:** Frontend-Aufrufer von `PUT /api/auth/profile` — `frontend/src/routes/+layout.svelte:88` (Passkey-Hinweis, löst **keine** Mail aus), `frontend/src/routes/account/+page.svelte:357` (Adressänderung, löst Mail aus) und `:406` (Telegram-Trennen, löst **keine** Mail aus). Nur Requests, die `email`/`mail_to` wirksam ändern, sind vom neuen Limit betroffen — die übrigen Aufrufer dürfen unverändert funktionieren.
- **Downstream (indirekt):** `ResendVerificationHandler` — teilt sich `dispatchVerificationMail`, profitiert vom selben Limit ohne eigene Änderung, falls die Prüfung dort verankert wird.

## Existing Specs

- Keine Spec für `dispatchVerificationMail` oder `UpdateProfileHandler` speziell zum Mailversand gefunden — `docs/specs/modules/user_auth_endpoints.md` und `docs/specs/modules/user_profile_channels.md` beschreiben angrenzende Endpunkte, keine Überschneidung mit Rate-Limiting.
- Referenz-Format: `docs/specs/bugfix/register_rate_limit.md`, `forgot_reset_rate_limit.md`, `login_rate_limit.md`.

## Risks & Considerations

- **Kein Cross-User-Datenleck-Risiko** — die Prüfung liest/schreibt nur Zähler-State, keine Nutzerdaten; `user_id` kommt bereits korrekt aus `UserIDFromContext`.
- **Fehlerfall darf die Speicherung nicht halb durchführen:** Wenn im selben Request sowohl Adresse als auch andere Felder (z. B. Anzeigename) geändert werden und das Mail-Limit greift, muss die Spec festlegen, ob der ganze Request 429 zurückgibt (nichts gespeichert) oder ob die anderen Felder gespeichert werden und nur die Adressänderung verworfen wird. Empfehlung: ganzer Request 429, kein Teil-Save — vermeidet stillen Datenverlust der Adressabsicht und hält das Verhalten für den Nutzer nachvollziehbar.
- **Grenze je Zieladresse muss über Konten hinweg gelten** (mehrere Angreifer-Konten, eine Opfer-Adresse) — reine Pro-User-Begrenzung reicht laut Ticket-Erwartung nicht aus.
- **Cleanup/Memory:** Wie bei `IPRateLimiter` muss der neue Limiter alte Einträge aufräumen (Cleanup-Goroutine nach Vorbild), sonst wächst die Map unbegrenzt mit jeder neuen User-ID/Adresse.
- **`ResendVerificationHandler` nimmt eine fremde `username`** — das bestehende IP-Limit (5/h) bleibt, das neue Zieladressen-Limit greift zusätzlich über `dispatchVerificationMail` und deckt damit auch den Fall ab, dass verschiedene IPs denselben Zielnutzer treffen.
- **Kein SMS-Bezug** — S2 betrifft ausschließlich Mail; SMS-Tageslimit ist S4 (separates Ticket), SMS-Nummer-Verifikation S3.
- **`dispatchVerificationMail` ist `func`, nicht Methode eines Structs** — der neue Limiter muss als zusätzlicher Parameter durchgereicht werden (Signaturänderung an beiden Aufrufstellen: `UpdateProfileHandler`, `ResendVerificationHandler`), analog zu `PremiumSmsRateLimiter`, der ebenfalls als Parameter durchgereicht wird statt global.

## Analysis

*Schritt 2a (Explore-Agenten) übersprungen — die dort verlangten Punkte (betroffene Dateien, bestehende Specs, Dependencies) liegen bereits vollständig mit Zeilenangaben im obigen `/10-context`-Ergebnis vor; eine Wiederholung hätte nur reproduziert, was schon auf der Platte steht. Stattdessen gezielte Nachrecherche zur einen offenen Design-Frage (Reihenfolge Speichern/Versand) unten.*

### Type
Feature (Hardening/Security-Scheibe S2 aus Epic #2138, Sammel-Issue #2153)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/auth.go` | MODIFY | `UpdateProfileHandler`: Limiter-Prüfung **vor** `s.SaveUser(*user)` einfügen, wenn `sendVerification == true`; bei Limit-Überschreitung 429, kein Save, kein Dispatch. `ResendVerificationHandler`: Limiter-Prüfung vor `dispatchVerificationMail(...)`. Beide Signaturen bekommen einen zusätzlichen Limiter-Parameter. |
| `internal/handler/profile_mail_ratelimit.go` (neu) oder `internal/middleware/ratelimit.go` (erweitert) | CREATE/MODIFY | Neuer schlüsselbasierter Limiter nach Vorbild `IPRateLimiter` (Token-Bucket, Cleanup-Goroutine), aber mit `Allow(userId, address string) bool` statt HTTP-Middleware-Wrapper — prüft und konsumiert **zwei** unabhängige Buckets (User-ID, normalisierte Zieladresse) atomar; schlägt einer der beiden fehl, gilt der ganze Check als fehlgeschlagen. |
| `internal/router/router.go` | MODIFY | Instanziierung des neuen Limiters (Werte in Spec, Größenordnung 10/h je Schlüssel laut Issue), Durchreichen an `UpdateProfileHandler`/`ResendVerificationHandler` (Zeilen ~89–90, ~Resend-Wiring). Kommentar `// Issue #2404 — ...` nach etabliertem Stil. |
| `internal/handler/auth_test.go` bzw. neue Testdatei `internal/handler/profile_mail_ratelimit_test.go` | CREATE/MODIFY | 429 bei Überschreitung (Save unterbleibt, Response-Body prüfbar), unabhängige Schlüssel (zwei Nutzer, eine Zieladresse ⇒ gemeinsam begrenzt; ein Nutzer, zwei Adressen ⇒ getrennt begrenzt), Case-Fold der Zieladresse, `ResendVerificationHandler` teilt sich das Adress-Limit mit `UpdateProfileHandler`. |

### Scope Assessment
- Files: 3 Produktivdateien (auth.go, neue/erweiterte Limiter-Datei, router.go) + 1–2 Testdateien
- Estimated LoC: production ~120–160, Tests ~150–220 (Repo-Testdichte hier hoch — u. a. wegen zwei-Nutzer-Pflicht aus CLAUDE.md) → **Gesamt vermutlich über dem 250-LoC-Limit**, `loc_limit_override` in `/40` wahrscheinlich nötig
- Risk Level: MEDIUM — kein Cross-User-Datenleck (reiner Zähler-State), aber Eingriff in eine vielfach genutzte, bereits mehrfach gehärtete Handler-Funktion (Read-Modify-Write, Adress-Sperren, TOCTOU-Schutz aus #2147) — Reihenfolge-Fehler dort sind erfahrungsgemäß teuer (siehe unten)

### Technical Approach

**Kernbefund (Nachrecherche zur Reihenfolge):** In `UpdateProfileHandler` (`auth.go`, aktuell ~Zeile 1071) läuft `s.SaveUser(*user)` **vor** dem Aufruf `dispatchVerificationMail(s, cfg, userId, user)` (~Zeile 1087). Der Versand selbst ist zwar asynchron (Goroutine, 20s-Timeout), aber die eigentliche *Zustandsänderung* — inkl. `PendingContactAddress`/`PendingContactField` — ist zu diesem Zeitpunkt bereits persistiert. Eine Limiter-Prüfung **innerhalb** von `dispatchVerificationMail` (wie ursprünglich angedacht) käme daher strukturell zu spät: Sie könnte den Mailversand verhindern, aber nicht mehr die Speicherung der Adressänderung — genau der vom Issue explizit verbotene Zustand „ausstehend, aber nie bestätigbar" (kein Token-Versand, aber `PendingContactAddress` bereits gesetzt).

**Konsequenz für den Zuschnitt:** Die Prüfung muss an **beiden Aufrufstellen separat und synchron vor der jeweiligen Wirkung** sitzen, nicht zentral in `dispatchVerificationMail`:
1. **`UpdateProfileHandler`:** Prüfung einfügen an der Stelle, an der `sendVerification` auf `true` ermittelt wird (im `switch`-Block, vor dem finalen `s.SaveUser(*user)`). Zielschlüssel ist `newEffective` (= `store.EffectiveContactAddress(...)`, bereits über `NormalizeEmailAddress` klein geschrieben/getrimmt — der vom Kontext ursprünglich befürchtete Case-Fold-Bypass entfällt dadurch, da diese Normalisierung schon existiert). Schlägt die Prüfung fehl: 429 zurückgeben, **kein** `SaveUser`-Aufruf, **kein** `dispatchVerificationMail`-Aufruf — der komplette Request wird verworfen (kein Teil-Save, siehe Entscheidung unten).
2. **`ResendVerificationHandler`:** Prüfung vor dem bestehenden `dispatchVerificationMail(...)`-Aufruf, mit demselben Zielschlüssel (`user.PendingContactAddress`, sonst `EffectiveContactAddress(user)` — identische Auswahllogik wie in `dispatchVerificationMail` selbst, dort dupliziert statt extrahiert, um die Signatur des Limiter-Checks einfach zu halten). Bei Limit-Überschreitung: Mail wird **nicht** verschickt, Response bleibt unverändert `200 {"status":"ok"}` (bestehende Privacy-Invariante — Kontoexistenz/Zustand darf von außen nicht unterscheidbar sein — bleibt gewahrt, das Limit ist rein intern).
3. `dispatchVerificationMail` selbst bleibt unverändert — sie bekommt keinen Limiter-Parameter, da die Prüfung jetzt vor ihrem Aufruf an beiden Stellen erledigt ist. Das vermeidet zusätzlich eine dritte Fehlerquelle (Signatur-Drift zwischen den beiden Call-Sites).

**Teil-Save-Entscheidung (Tech-Lead, nicht PO-Frage):** Bei Limit-Überschreitung wird der **gesamte** Request mit 429 abgewiesen, keine Felder werden gespeichert — auch wenn im selben Request z. B. auch `display_name` geändert wurde. Begründung: (a) das Issue selbst verlangt explizit, dass die Adressänderung nicht gespeichert wird; (b) ein Teil-Save (andere Felder ja, Adresse nein) würde dem Aufrufer verschleiern, dass ein Teil der Anfrage verworfen wurde, und widerspricht dem Nachvollziehbarkeits-Prinzip aus den bestehenden 409/500-Zweigen derselben Funktion, die ebenfalls hart abbrechen statt teilweise zu speichern. Für den seltenen Fall (Adressänderung + andere Felder im selben Request, Limit erreicht) kann der Nutzer die harmlosen Felder in einem zweiten Request ohne Adressänderung erneut senden.

**Limiter-Bauart:** Neuer schlüsselbasierter Zwei-Ebenen-Limiter nach Vorbild `IPRateLimiter` (`internal/middleware/ratelimit.go`): Token-Bucket pro Schlüssel, Cleanup-Goroutine, aber `Allow(userId, address string) bool` statt HTTP-Middleware-Wrapper (Analogie zu `PremiumSmsRateLimiter`, die ebenfalls nicht als `http.Handler`-Middleware, sondern als direkt aufrufbarer Parameter existiert). Intern zwei unabhängige Bucket-Maps (User-ID-Schlüssel, Adress-Schlüssel); `Allow` konsumiert testbar beide atomar — schlägt einer fehl, gilt der Check als negativ (konkrete Semantik bei Teilverbrauch: Spec).

### Dependencies
- **Upstream:** `golang.org/x/time/rate` (bereits Projekt-Dependency), `store.EffectiveContactAddress`/`store.NormalizeEmailAddress` (liefern bereits normalisierten, kleingeschriebenen Schlüssel), `store.Store.SaveUser`/`LoadUser`.
- **Reihenfolge:** Limiter-Typ zuerst (eigenständig testbar ohne HTTP), danach Verdrahtung in `router.go`, zuletzt die beiden Call-Site-Änderungen in `auth.go` (dort ist die Reihenfolge-Korrektheit — Check vor Save — die eigentliche sicherheitsrelevante Änderung).
- **Downstream:** Keine Frontend-Änderung nötig — `account/+page.svelte` muss nur den bereits etablierten 429-Fehlerfall (analog Login/Register) plausibel anzeigen; zu prüfen in `/50-implement`, ob dort bereits eine generische 429-Behandlung existiert oder eine ergänzt werden muss.

### Open Questions
*(keine — Teil-Save- und Reihenfolge-Frage sind oben als Tech-Lead-Entscheidung getroffen, nicht offen für PO)*
