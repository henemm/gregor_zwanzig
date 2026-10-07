---
entity_id: fix_2436_tier_antrag_ehrliche_rueckmeldung
type: bugfix
created: 2026-10-07
updated: 2026-10-07
status: draft
workflow: fix-2436-tier-antrag-ehrliche-rueckmeldung
---

# Tier-Antrag: ehrliche Rückmeldung, wenn der Betreiber nicht benachrichtigt wurde

## Approval

- [ ] Approved

## Purpose

`POST /api/auth/tier-change-request` antwortet heute **vor** dem Mailversand mit
`{"status":"ok"}` und verschickt die Mail an den Betreiber (PO) danach in einer
Goroutine. Fehlt `PO_EMAIL` oder `SMTP_HOST` oder scheitert der Versand, steht das
nur im Log. Der Nutzer liest „Antrag gesendet“ und wartet auf eine Freigabe, von
der der Betreiber nichts weiß. Diese Spec macht drei Dinge: Die Antwort meldet
ehrlich, ob der Betreiber benachrichtigt wurde. Die Konto-Seite zeigt das an.
Der Betrieb sieht im Status-Endpoint eine fehlende Mail-Konfiguration und
unbenachrichtigte Anträge.

**Nicht Gegenstand:** Die Admin-Nutzerliste (#2155 S3) zeigt offene Anträge schon
(`frontend/src/routes/admin/+page.svelte:211`) und bleibt unverändert. Die Bewertung
der neuen Zahlen im externen Monitor `henemm-infra/check-gregor20.sh` ist Sache
des Infra-Repos (Folge-Eintrag dort).

## Source

- **File:** `internal/handler/auth.go`
- **Identifier:** `func RequestTierChangeHandler`

## Estimated Scope

~150 LoC (Go-Handler + Modellfeld + Health-Aggregat + Konto-Seite + Tests)

## Affected Files

| Datei | Änderung |
|---|---|
| `internal/handler/auth.go` | Versand synchron mit Timeout (15 s); Antwort trägt `po_notified`; nach Erfolg `RequestedNotifiedAt` setzen |
| `internal/model/user.go` | neues Feld `RequestedNotifiedAt *time.Time` (`requested_notified_at`, omitempty) |
| `internal/store/user.go` | `SetUserTierAdmin` löscht zusätzlich `requested_notified_at` |
| `internal/scheduler/tier_request_health.go` | `unnotified_count`, `po_mail_configured` |
| `internal/scheduler/scheduler.go` | Scheduler kennt `PoEmail`/`SMTPHost` aus der Config |
| `frontend/src/routes/account/+page.svelte` | ehrlicher Hinweis bei `po_notified:false` und im Pending-Hinweis |
| `frontend/src/lib/types.ts` | `requested_notified_at` im Profil-Typ |

## Design

1. **Synchron statt Fire-and-forget.** Der Handler speichert den Antrag (wie bisher,
   Read-Modify-Write) und versucht dann den Versand mit hartem Timeout von 15 s.
   Ein Level-Antrag ist selten, eine kurze Wartezeit mit „Wird gesendet…“ ist
   vertretbar. Nur so kann die Antwort die Wahrheit sagen.
2. **HTTP 200 bleibt.** Der Antrag *ist* gespeichert und steht in der Admin-Liste.
   Die Antwort heißt `{"status":"ok","po_notified":true|false}`. Ein 5xx wäre
   falsch, weil sonst ein erneuter Klick einen schon gespeicherten Antrag doppelt
   auslöst.
3. **Nachweis in der user.json.** `requested_notified_at` wird nur nach
   erfolgreichem Versand gesetzt. Ein neuer Antrag setzt das Feld zuerst zurück.
   Daraus leiten die Konto-Seite (auch nach einem Reload) und das Health-Aggregat
   ab, ob der Betreiber benachrichtigt wurde.
4. **Betrieb.** `tier_request_health` bekommt `po_mail_configured` (bool) und
   `unnotified_count` (Zahl). Wie bisher gibt es keine Nutzerkennungen, weil der
   Endpoint öffentlich ist.

## Acceptance Criteria

**AC-1:** Given `PO_EMAIL` ist nicht gesetzt, When ein Nutzer einen gültigen Level-Wechsel beantragt, Then wird der Antrag gespeichert und die Antwort lautet HTTP 200 mit `po_notified: false`, nicht mehr mit einem stillen „ok“.

**AC-2:** Given `SMTP_HOST` ist nicht gesetzt, When ein Nutzer einen Level-Wechsel beantragt, Then antwortet der Endpoint mit `po_notified: false` und in der user.json steht kein `requested_notified_at`.

**AC-3:** Given die Mail-Konfiguration ist vollständig, aber der Versand scheitert oder dauert länger als 15 Sekunden, When ein Nutzer beantragt, Then antwortet der Endpoint spätestens nach rund 15 Sekunden mit `po_notified: false`, und der Antrag bleibt gespeichert.

**AC-4:** Given der Versand an den Betreiber gelingt, When ein Nutzer beantragt, Then antwortet der Endpoint mit `po_notified: true`, und `requested_notified_at` ist in der user.json gesetzt.

**AC-5:** Given ein früherer Antrag wurde erfolgreich gemeldet, When derselbe Nutzer einen neuen Antrag stellt und dessen Versand scheitert, Then ist `requested_notified_at` danach leer: Ein alter Nachweis gilt nie für einen neuen Antrag.

**AC-6:** Given die Antwort lautet `po_notified: false`, When der Nutzer auf der Konto-Seite beantragt hat, Then sieht er statt „Antrag gesendet“ einen deutlich erkennbaren Hinweis: Der Antrag ist gespeichert, aber der Betreiber wurde nicht benachrichtigt. Derselbe Hinweis steht im Pending-Bereich auch nach einem Neuladen der Seite.

**AC-7:** Given `PO_EMAIL` oder `SMTP_HOST` fehlt, When der Betrieb `/api/scheduler/status` abruft, Then steht in `tier_request_health` der Wert `po_mail_configured: false`, sonst `true`.

**AC-8:** Given zwei verschiedene Nutzer haben offene Anträge, einer gemeldet und einer nicht, When der Status-Endpoint abgerufen wird, Then gilt `open_count: 2` und `unnotified_count: 1`, und die Antwort enthält keine Nutzerkennung, keinen Namen und keine Adresse.

**AC-9:** Given der Admin gibt einen Antrag über die Admin-Nutzerliste frei, When `SetUserTierAdmin` läuft, Then sind `requested_tier`, `requested_at` und `requested_notified_at` gelöscht, und alle anderen Felder der user.json bleiben erhalten.

## Test Plan

- Go-Kern (`internal/handler/tier_change_honest_feedback_test.go`): AC-1…AC-5. Der Versand läuft über eine neue Paketvariable `sendTierChangeMailFn = mail.SendWithFallback`, nach dem vorhandenen Muster von `sendResetMailFn` und `sendVerificationMailFn` (`auth.go:421`, `:1345`). Die Tests ersetzen nur die Transportgrenze (Erfolg, Fehler, Hänger). Geprüft wird das beobachtbare Ergebnis aus Antwort und user.json. Die vorhandenen Tests in `tier_change_po_email_allowlist_test.go` müssen grün bleiben, weil die Log-Zeilen erhalten bleiben. Zwei Nutzer laufen parallel, damit kein Antrag in die user.json des anderen schreibt.
- Go-Kern (`internal/scheduler/tier_request_health_test.go`): AC-7, AC-8.
- Go-Kern (`internal/store/…`): AC-9 als Roundtrip mit einem unbekannten Fremdfeld.
- Frontend (vitest/Playwright gegen Staging): AC-6.
