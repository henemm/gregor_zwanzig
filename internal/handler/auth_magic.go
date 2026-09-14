package handler

// Magic Link / OTP Login per E-Mail (Issue #449).
// Spec: docs/specs/modules/issue_449_magic_link.md
//
// Two endpoints:
//   POST /api/auth/magic-link        — request a 6-digit code via e-mail
//   POST /api/auth/magic-link/verify — exchange a valid code for a session cookie
//
// The OTP-Store is a package-level sync.Map (key: normalized e-mail,
// value: *otpEntry). TTL is 15 minutes; max 3 wrong attempts per entry.
// Issue #2147: the account is resolved only when the code is redeemed
// (store.ResolveAddressOwner); new users ("m-{8hex}") are created then, never
// on request.

import (
	"crypto/rand"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// otpEntry is the per-email record stored in otpStore. attempts is mutated
// in place via the pointer — never re-Store the entry.
type otpEntry struct {
	code      string
	expiresAt time.Time
	attempts  int32
}

// otpStore holds active OTP challenges, keyed by lower-cased trimmed e-mail.
var otpStore sync.Map

// magicLinkBeforeTakeoverReload ist eine Test-Naht (Issue #2147 Scheibe B1,
// AC-12): im Normalbetrieb nil und damit wirkungslos. Tests koennen sie
// setzen, um zwischen der Zuordnung (ResolveAddressOwner) und dem erneuten
// Laden in resolveMagicLinkAccount eine Zwischenzeit-Aenderung einzuspielen.
var magicLinkBeforeTakeoverReload func(userID string)

// MagicLinkRequestHandler returns the HTTP handler for POST /api/auth/magic-link.
// Always responds 200 (no user enumeration); generates a 6-digit OTP, stores it
// with a 15-min TTL, and dispatches the OTP-mail asynchronously (10s timeout).
func MagicLinkRequestHandler(s *store.Store, cfg *config.Config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		var req struct {
			Email string `json:"email"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil || strings.TrimSpace(req.Email) == "" {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		// Issue #2147: no account lookup/creation here — the code proves the
		// address, the account is resolved when it is redeemed.
		normalizedEmail := store.NormalizeEmailAddress(req.Email)

		// Generate 6-digit OTP via crypto/rand.
		var b [4]byte
		if _, err := rand.Read(b[:]); err != nil {
			log.Printf("magic-link: rand.Read error: %v", err)
			w.Write([]byte(`{"status":"ok"}`))
			return
		}
		code := fmt.Sprintf("%06d", binary.BigEndian.Uint32(b[:])%1_000_000)

		otpStore.Store(normalizedEmail, &otpEntry{
			code:      code,
			expiresAt: time.Now().Add(15 * time.Minute),
			attempts:  0,
		})

		// Dispatch e-mail in background goroutine with 10s timeout.
		if cfg.SMTPHost == "" {
			log.Printf("magic-link: SMTP not configured, skipping email to %s", normalizedEmail)
		} else {
			mailCfg := mail.MailConfig{
				Host: cfg.SMTPHost,
				Port: cfg.SMTPPort,
				User: cfg.SMTPUser,
				Pass: cfg.SMTPPass,
				From: cfg.SMTPFrom,
			}
			// Issue #2147: the code is an address proof like the verification
			// mail — same Resend special path (the recipient allowlist only
			// knows confirmed accounts, a not-yet-existing one would never
			// receive it).
			msg := mail.BuildMagicLinkMail(code)
			go func(to string, m mail.Mail, c mail.MailConfig) {
				done := make(chan error, 1)
				go func() { done <- sendVerificationMailFn(c, to, m) }()
				select {
				case err := <-done:
					if err != nil {
						log.Printf("magic-link: mail send failed for %s: %v", to, err)
					}
				case <-time.After(20 * time.Second):
					log.Printf("magic-link: mail send timeout (20s) for %s", to)
				}
			}(normalizedEmail, msg, mailCfg)
		}

		w.Write([]byte(`{"status":"ok"}`))
	}
}

// MagicLinkVerifyHandler returns the HTTP handler for POST /api/auth/magic-link/verify.
// Validates code + TTL + attempt-counter, then issues a signed gz_session cookie.
func MagicLinkVerifyHandler(s *store.Store, cfg *config.Config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		var req struct {
			Email string `json:"email"`
			Code  string `json:"code"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		normalizedEmail := store.NormalizeEmailAddress(req.Email)
		if normalizedEmail == "" || req.Code == "" {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		val, ok := otpStore.Load(normalizedEmail)
		if !ok {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid_or_expired_code"}`))
			return
		}
		entry := val.(*otpEntry)

		// Max-attempts gate runs BEFORE code comparison so leaked/correct
		// codes cannot be exploited after the limit is reached.
		if atomic.LoadInt32(&entry.attempts) >= 3 {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"max_attempts_exceeded"}`))
			return
		}

		// TTL gate.
		if time.Now().After(entry.expiresAt) {
			otpStore.Delete(normalizedEmail)
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid_or_expired_code"}`))
			return
		}

		// Code comparison — increment attempts on miss.
		if entry.code != req.Code {
			atomic.AddInt32(&entry.attempts, 1)
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid_or_expired_code"}`))
			return
		}

		// Success: single-use. Only the caller that consumes the entry
		// proceeds — a concurrent second redemption gets the neutral 400
		// (Issue #2147 AC-9).
		if !otpStore.CompareAndDelete(normalizedEmail, entry) {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid_or_expired_code"}`))
			return
		}

		unlock := store.LockEmailAddress(normalizedEmail)
		defer unlock()
		userID, ok := resolveMagicLinkAccount(w, s, normalizedEmail)
		if !ok {
			return
		}
		if !issueSession(w, r, s, userID, cfg.SessionSecret) {
			return
		}
		json.NewEncoder(w).Encode(map[string]string{"id": userID})
	}
}

// resolveMagicLinkAccount maps the proven address to exactly one account
// (Issue #2147, Spec magic_link_adress_eindeutigkeit.md §4). The caller holds
// store.LockEmailAddress. Returns false when a response was already written.
func resolveMagicLinkAccount(w http.ResponseWriter, s *store.Store, address string) (string, bool) {
	fail := func(status int, body string) (string, bool) {
		w.WriteHeader(status)
		w.Write([]byte(body))
		return "", false
	}
	owner, resolution, err := s.ResolveAddressOwner(address)
	if err != nil {
		log.Printf("magic-link: address resolution failed: %v", err)
		return fail(http.StatusInternalServerError, `{"error":"internal error"}`)
	}
	switch resolution {
	case store.AddressFree:
		user, err := createMagicLinkUser(s, address)
		if err != nil {
			log.Printf("magic-link: createMagicLinkUser error: %v", err)
			return fail(http.StatusInternalServerError, `{"error":"internal error"}`)
		}
		return user.ID, true
	case store.AddressOwned:
		if owner.EmailVerifiedAt != nil {
			return owner.ID, true
		}
		// Issue #2147 Scheibe B1 (AC-12): Test-Naht VOR dem Neuladen, damit ein
		// Test eine Zwischenzeit-Aenderung (Zugangsdaten oder Adresse) genau
		// zwischen Zuordnung und Neuladen einspielen kann.
		if magicLinkBeforeTakeoverReload != nil {
			magicLinkBeforeTakeoverReload(owner.ID)
		}
		// Credential-less, unconfirmed account: confirm it (read-modify-write)
		// and end its old sessions BEFORE issuing the new one.
		user, err := s.LoadUser(owner.ID)
		if err == nil && user == nil {
			err = fmt.Errorf("account vanished")
		}
		if err == nil {
			// Issue #2147 Scheibe B1 (AC-12): das frisch geladene Konto muss X
			// weiterhin als wirksame Kontaktadresse tragen und weiterhin OHNE
			// Zugangsdaten sein — sonst hat es die Zwischenzeit veraendert und
			// die Uebernahme wird verweigert (dieselbe neutrale Antwort wie bei
			// jeder anderen Mehrdeutigkeit).
			if store.HasLoginCredentials(user) || store.EffectiveContactAddress(user) != address {
				log.Printf("magic-link: takeover of account %s refused — account changed since assignment", owner.ID)
				return fail(http.StatusBadRequest, `{"error":"invalid_or_expired_code"}`)
			}
			now := time.Now().UTC()
			user.EmailVerifiedAt = &now
			if err = s.SaveUser(*user); err == nil {
				err = s.ClearSessions(owner.ID)
			}
		}
		if err != nil {
			log.Printf("magic-link: takeover of unconfirmed account %s failed: %v", owner.ID, err)
			return fail(http.StatusInternalServerError, `{"error":"internal error"}`)
		}
		return owner.ID, true
	}
	log.Printf("magic-link: address not uniquely assignable — login refused")
	return fail(http.StatusBadRequest, `{"error":"invalid_or_expired_code"}`)
}

// createMagicLinkUser provisions a new user with ID format "m-{8hex}".
// Tries up to 3 random IDs before giving up (collision is extremely unlikely).
func createMagicLinkUser(s *store.Store, email string) (*model.User, error) {
	for attempt := 0; attempt < 3; attempt++ {
		idBytes := make([]byte, 4)
		if _, err := rand.Read(idBytes); err != nil {
			return nil, err
		}
		id := fmt.Sprintf("m-%s", hex.EncodeToString(idBytes))
		if s.UserExists(id) {
			continue
		}
		now := time.Now().UTC()
		user := model.User{
			ID:              id,
			Email:           email,
			MailTo:          email,
			CreatedAt:       now,
			EmailVerifiedAt: &now, // the redeemed code proved the address
		}
		if err := s.SaveUser(user); err != nil {
			return nil, err
		}
		if err := s.ProvisionUserDirs(id); err != nil {
			return nil, err
		}
		return &user, nil
	}
	return nil, fmt.Errorf("could not generate unique user ID after 3 attempts")
}
