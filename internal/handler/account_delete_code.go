package handler

// Lösch-Code fuer die Kontoloeschung (Issue #2160, Spec
// docs/specs/modules/account_deletion.md, ADR-0081).
//
// Eigener Store, getrennt vom Login-OTP-Store (otpStore): Schluessel ist die
// UserID aus dem Auth-Kontext, nie eine Adresse. Ein Login-OTP ist kein
// Lösch-Code und umgekehrt. TTL 15 Minuten, max. 3 Fehlversuche (Zaehler vor
// dem Vergleich), einmalig (CompareAndDelete).

import (
	"crypto/rand"
	"encoding/binary"
	"fmt"
	"log"
	"net/http"
	"sync"
	"sync/atomic"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	deleteCodeTTL         = 15 * time.Minute
	deleteCodeMaxAttempts = 3
)

// deleteCodeEntry ist ein offener Lösch-Code. attempts wird ueber den Zeiger
// in-place mutiert (Muster otpEntry) — den Eintrag nie neu speichern.
type deleteCodeEntry struct {
	code      string
	expiresAt time.Time
	attempts  int32
}

// deleteCodeStore: Schluessel UserID, Wert *deleteCodeEntry.
var deleteCodeStore sync.Map

// consumeDeleteCode prueft code gegen den Lösch-Code von userID und verbraucht
// ihn bei Erfolg. Der Fehlversuchszaehler wird VOR dem Vergleich erhoeht, ein
// gesperrter Code (mehr als 3 Versuche) lehnt auch den richtigen Code ab.
// Bei Erfolg kommt der verbrauchte Eintrag zurueck (fuer restoreDeleteCode).
func consumeDeleteCode(userID, code string, now time.Time) (*deleteCodeEntry, bool) {
	val, ok := deleteCodeStore.Load(userID)
	if !ok {
		return nil, false
	}
	e := val.(*deleteCodeEntry)
	if !now.Before(e.expiresAt) {
		return nil, false
	}
	if atomic.AddInt32(&e.attempts, 1) > deleteCodeMaxAttempts {
		return nil, false
	}
	if e.code != code {
		return nil, false
	}
	if !deleteCodeStore.CompareAndDelete(userID, e) {
		return nil, false
	}
	return e, true
}

// restoreDeleteCode setzt einen verbrauchten Lösch-Code wieder ein, wenn die
// Kaskade danach gescheitert ist (Issue #2160 AC-13: wiederholbar). Gleicher
// Code, gleiche Ablaufzeit, Zaehlerstand wie vor dem erfolgreichen Versuch —
// ein Serverfehler ist kein Fehlversuch. Ein inzwischen neu angeforderter
// Code wird nie ueberschrieben (LoadOrStore).
func restoreDeleteCode(userID string, e *deleteCodeEntry) {
	atomic.AddInt32(&e.attempts, -1)
	deleteCodeStore.LoadOrStore(userID, e)
}

// gcDeleteCodeStore entfernt abgelaufene Lösch-Codes (auch gesperrte erst nach
// Ablauf). Aufgerufen vom Reaper, nie aus einem Konstruktor.
func gcDeleteCodeStore(now time.Time) {
	deleteCodeStore.Range(func(k, v any) bool {
		if e := v.(*deleteCodeEntry); !now.Before(e.expiresAt) {
			deleteCodeStore.CompareAndDelete(k, e)
		}
		return true
	})
}

// StartStoreReaper startet den Ticker, der die In-Memory-/Datei-Stores mit
// Ablaufzeit raeumt (Login-OTPs, Lösch-Codes, Telegram-Tokens). Wird aus
// cmd/server/main.go gestartet, nicht aus Konstruktoren (Issue #2160 AC-15).
// Die zurueckgegebene stop-Funktion beendet den Ticker und wartet, bis die
// Goroutine fertig ist; mehrfacher Aufruf ist harmlos.
func StartStoreReaper(ts *TelegramTokenStore, interval time.Duration) (stop func()) {
	quit := make(chan struct{})
	finished := make(chan struct{})
	go func() {
		defer close(finished)
		ticker := time.NewTicker(interval)
		defer ticker.Stop()
		for {
			select {
			case <-quit:
				return
			case now := <-ticker.C:
				gcOTPStore(now)
				gcDeleteCodeStore(now)
				if ts != nil {
					ts.gc(now)
				}
			}
		}
	}()
	var once sync.Once
	return func() {
		once.Do(func() {
			close(quit)
			<-finished
		})
	}
}

func newDeleteCode() (string, error) {
	var b [4]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	return fmt.Sprintf("%06d", binary.BigEndian.Uint32(b[:])%1_000_000), nil
}

func buildDeleteCodeMail(code string) mail.Mail {
	plain := fmt.Sprintf(
		"Hallo,\n\nDein Lösch-Code für Gregor 20: %s\n\nMit diesem Code wird dein Konto unwiderruflich gelöscht. Der Code ist 15 Minuten gültig.\n\nFalls du die Löschung nicht angefordert hast, ignoriere diese E-Mail und ändere dein Passwort — jemand hat Zugriff auf eine deiner Anmeldungen.\n",
		code,
	)
	html := fmt.Sprintf(
		`<!DOCTYPE html><html><body style="font-family:sans-serif;line-height:1.5">`+
			`<p>Hallo,</p>`+
			`<p>Dein L&ouml;sch-Code f&uuml;r <strong>Gregor 20</strong>:</p>`+
			`<p style="font-size:2em;font-weight:bold;letter-spacing:0.2em;font-family:monospace">%s</p>`+
			`<p>Mit diesem Code wird dein Konto <strong>unwiderruflich gel&ouml;scht</strong>. Der Code ist 15 Minuten g&uuml;ltig.</p>`+
			`<p>Falls du die L&ouml;schung nicht angefordert hast, ignoriere diese E-Mail und &auml;ndere dein Passwort.</p>`+
			`</body></html>`,
		code,
	)
	return mail.Mail{Subject: "Gregor 20 — Dein Lösch-Code", PlainBody: plain, HTMLBody: html}
}

// sendDeleteCodeMail verschickt synchron (20s-Timeout) ueber den
// Magic-Code-Pfad (Resend-Sonderweg, sendVerificationMailFn).
func sendDeleteCodeMail(cfg config.Config, to, code string) error {
	mailCfg := mail.MailConfig{
		Host: cfg.SMTPHost, Port: cfg.SMTPPort,
		User: cfg.SMTPUser, Pass: cfg.SMTPPass, From: cfg.SMTPFrom,
	}
	done := make(chan error, 1)
	go func() { done <- sendVerificationMailFn(mailCfg, to, buildDeleteCodeMail(code)) }()
	select {
	case err := <-done:
		return err
	case <-time.After(20 * time.Second):
		return fmt.Errorf("mail send timeout (20s)")
	}
}

// RequestDeleteCodeHandler: POST /api/auth/account/delete-code. Erzeugt einen
// 6-stelligen Lösch-Code und schickt ihn ausschliesslich an
// EffectiveContactAddress (nie an die ausstehende Adresse). Gespeichert wird
// erst nach erfolgreichem Versand.
func RequestDeleteCodeHandler(s *store.Store, cfg config.Config, l *MailFloodLimiter) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		user, err := s.LoadUser(userID)
		if err != nil || user == nil {
			writeJSONError(w, http.StatusNotFound, "not_found")
			return
		}
		addr := store.EffectiveContactAddress(user)
		if addr == "" || cfg.SMTPHost == "" {
			log.Printf("delete-code: kein Versand moeglich fuer %s (Adresse/SMTP fehlt)", userID)
			writeJSONError(w, http.StatusBadGateway, "mail_failed")
			return
		}
		if !l.Allow(userID, addr) {
			w.Header().Set("Retry-After", l.RetryAfterHeader())
			writeJSONError(w, http.StatusTooManyRequests, "rate_limit_exceeded")
			return
		}
		code, err := newDeleteCode()
		if err != nil {
			writeJSONError(w, http.StatusInternalServerError, "internal")
			return
		}
		if err := sendDeleteCodeMail(cfg, addr, code); err != nil {
			log.Printf("delete-code: Versand an %s fehlgeschlagen: %v", mail.MaskAddrForLog(addr), err)
			writeJSONError(w, http.StatusBadGateway, "mail_failed")
			return
		}
		deleteCodeStore.Store(userID, &deleteCodeEntry{code: code, expiresAt: time.Now().Add(deleteCodeTTL)})
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"sent"}`))
	}
}
