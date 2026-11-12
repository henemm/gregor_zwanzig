package handler

// Magic Link / OTP Login per E-Mail (Issue #449).
// Spec: docs/specs/modules/issue_449_magic_link.md
//
// Two endpoints:
//   POST /api/auth/magic-link        — request an 8-digit code via e-mail
//   POST /api/auth/magic-link/verify — exchange a valid code for a session cookie
//
// The OTP-Store is a package-level sync.Map (key: normalized e-mail,
// value: *otpEntry). TTL is 15 minutes; max 3 compared attempts per code.
// Issue #2147: the account is resolved only when the code is redeemed
// (store.ResolveAddressOwner); new users ("m-{8hex}") are created then, never
// on request.
//
// Issue #2961 (ADR-0113): additionally per target address — at most 5 failed
// attempts per 15 minutes across re-requests (magicFailGuard, counted BEFORE
// the comparison), at most 5 code mails per hour, and a still valid code is
// re-sent instead of being replaced.

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"math/big"
	"net/http"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/i18n"
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

// gcOTPStore entfernt abgelaufene Login-OTPs (Issue #2160 AC-15). OTPs mit
// attempts>=3 bleiben bis zum Ablauf. Zusaetzlich verfallene Eintraege der
// Fehlversuchsbremse je Adresse (Issue #2961).
func gcOTPStore(now time.Time) {
	magicFailGuard.gc()
	otpStore.Range(func(k, v any) bool {
		if e := v.(*otpEntry); !now.Before(e.expiresAt) {
			otpStore.CompareAndDelete(k, e)
		}
		return true
	})
}

// removeLoginOTPs entfernt die Login-OTPs der angegebenen Adressen
// (normalisiert, leere uebersprungen) — Kontoloeschung, Issue #2160 AC-11.
func removeLoginOTPs(addresses ...string) {
	for _, a := range addresses {
		if n := store.NormalizeEmailAddress(a); n != "" {
			otpStore.Delete(n)
		}
	}
}

// magicLinkBeforeTakeoverReload ist eine Test-Naht (Issue #2147 Scheibe B1,
// AC-12): im Normalbetrieb nil und damit wirkungslos. Tests koennen sie
// setzen, um zwischen der Zuordnung (ResolveAddressOwner) und dem erneuten
// Laden in resolveMagicLinkAccount eine Zwischenzeit-Aenderung einzuspielen.
var magicLinkBeforeTakeoverReload func(userID string)

// MagicLinkRequestHandler returns the HTTP handler for POST /api/auth/magic-link.
// Always responds 200 (no user enumeration); generates an 8-digit OTP (or
// re-sends the still valid one), stores it with a 15-min TTL, and dispatches
// the OTP-mail asynchronously.
func MagicLinkRequestHandler(s *store.Store, cfg *config.Config) http.HandlerFunc {
	requestLimiter := NewMailFloodLimiter(magicRequestsPerHour, time.Hour)
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		var req struct {
			Email string `json:"email"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil || strings.TrimSpace(req.Email) == "" {
			WriteError(w, r, http.StatusBadRequest, "invalid_request", nil)
			return
		}

		// Issue #2147: no account lookup/creation here — the code proves the
		// address, the account is resolved when it is redeemed.
		normalizedEmail := store.NormalizeEmailAddress(req.Email)

		// Issue #2961: per-address mail budget. Over budget the answer stays
		// the same neutral 200 — only no mail goes out (no enumeration).
		if !requestLimiter.AllowAddressOnly(normalizedEmail) {
			log.Printf("magic-link: per-address request limit reached for %s", mail.MaskAddrForLog(normalizedEmail))
			w.Write([]byte(`{"status":"ok"}`))
			return
		}

		code, err := currentOrNewLoginCode(normalizedEmail)
		if err != nil {
			log.Printf("magic-link: code generation failed: %v", err)
			w.Write([]byte(`{"status":"ok"}`))
			return
		}

		// Dispatch e-mail in background goroutine with 10s timeout.
		if cfg.SMTPHost == "" {
			log.Printf("magic-link: SMTP not configured, skipping email to %s", mail.MaskAddrForLog(normalizedEmail))
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
			// Issue #2678: kein Konto vor dem Einloesen -> Anfragesprache.
			msg := mail.BuildMagicLinkMail(i18n.FromContext(r.Context()), code)
			go func(to string, m mail.Mail, c mail.MailConfig) {
				done := make(chan error, 1)
				go func() { done <- sendVerificationMailFn(c, to, m) }()
				select {
				case err := <-done:
					if err != nil {
						log.Printf("magic-link: mail send failed for %s: %v", mail.MaskAddrForLog(to), err)
					}
				case <-time.After(20 * time.Second):
					log.Printf("magic-link: mail send timeout (20s) for %s", mail.MaskAddrForLog(to))
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
			WriteError(w, r, http.StatusBadRequest, "invalid_request", nil)
			return
		}

		normalizedEmail := store.NormalizeEmailAddress(req.Email)
		if normalizedEmail == "" || req.Code == "" {
			WriteError(w, r, http.StatusBadRequest, "invalid_request", nil)
			return
		}

		val, ok := otpStore.Load(normalizedEmail)
		if !ok {
			WriteError(w, r, http.StatusBadRequest, "invalid_or_expired_code", nil)
			return
		}
		entry := val.(*otpEntry)

		// Issue #2961: per-address failure budget, counted BEFORE the
		// comparison. While locked even the correct code is refused with the
		// same neutral answer as a wrong one.
		if !magicFailGuard.Reserve(normalizedEmail) {
			WriteError(w, r, http.StatusBadRequest, "invalid_or_expired_code", nil)
			return
		}

		// TTL gate.
		if time.Now().After(entry.expiresAt) {
			otpStore.CompareAndDelete(normalizedEmail, entry)
			WriteError(w, r, http.StatusBadRequest, "invalid_or_expired_code", nil)
			return
		}

		// Per-code gate: claim a comparison slot atomically BEFORE comparing,
		// so concurrent requests cannot exceed the limit.
		if !claimOTPAttempt(entry) {
			WriteError(w, r, http.StatusBadRequest, "max_attempts_exceeded", nil)
			return
		}
		if subtle.ConstantTimeCompare([]byte(entry.code), []byte(req.Code)) != 1 {
			WriteError(w, r, http.StatusBadRequest, "invalid_or_expired_code", nil)
			return
		}

		// Success: single-use. Only the caller that consumes the entry
		// proceeds — a concurrent second redemption gets the neutral 400
		// (Issue #2147 AC-9).
		if !otpStore.CompareAndDelete(normalizedEmail, entry) {
			WriteError(w, r, http.StatusBadRequest, "invalid_or_expired_code", nil)
			return
		}
		magicFailGuard.Success(normalizedEmail)

		unlock := store.LockEmailAddress(normalizedEmail)
		defer unlock()
		userID, ok := resolveMagicLinkAccount(w, r, s, normalizedEmail)
		if !ok {
			return
		}
		if !issueSession(w, r, s, userID, cfg.SessionSecret, cfg.PublicHost) {
			return
		}
		json.NewEncoder(w).Encode(map[string]string{"id": userID})
	}
}

const (
	otpCodeDigits        = 8
	otpTTL               = 15 * time.Minute
	otpMaxAttempts       = 3
	magicRequestsPerHour = 5
)

var otpCodeSpace = big.NewInt(100_000_000) // 10^otpCodeDigits

// newLoginCode draws a uniformly distributed 8-digit code from crypto/rand
// (rand.Int rejects out-of-range samples — no modulo bias).
func newLoginCode() (string, error) {
	n, err := rand.Int(rand.Reader, otpCodeSpace)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("%0*d", otpCodeDigits, n.Int64()), nil
}

// otpUsable: unexpired and comparisons left.
func otpUsable(e *otpEntry, now time.Time) bool {
	return now.Before(e.expiresAt) && atomic.LoadInt32(&e.attempts) < otpMaxAttempts
}

// currentOrNewLoginCode returns the still usable code of address or stores a
// fresh one. A running code is never replaced, so a third party cannot
// invalidate the owner's code by requesting another one.
func currentOrNewLoginCode(address string) (string, error) {
	now := time.Now()
	if v, ok := otpStore.Load(address); ok && otpUsable(v.(*otpEntry), now) {
		return v.(*otpEntry).code, nil
	}
	code, err := newLoginCode()
	if err != nil {
		return "", err
	}
	fresh := &otpEntry{code: code, expiresAt: now.Add(otpTTL)}
	for {
		v, loaded := otpStore.LoadOrStore(address, fresh)
		if !loaded {
			return code, nil
		}
		old := v.(*otpEntry)
		if otpUsable(old, now) {
			return old.code, nil
		}
		if otpStore.CompareAndSwap(address, old, fresh) {
			return code, nil
		}
	}
}

// claimOTPAttempt reserves one comparison on e; false once all
// otpMaxAttempts comparisons are used.
func claimOTPAttempt(e *otpEntry) bool {
	for {
		cur := atomic.LoadInt32(&e.attempts)
		if cur >= otpMaxAttempts {
			return false
		}
		if atomic.CompareAndSwapInt32(&e.attempts, cur, cur+1) {
			return true
		}
	}
}

// resolveMagicLinkAccount maps the proven address to exactly one account
// (Issue #2147, Spec magic_link_adress_eindeutigkeit.md §4). The caller holds
// store.LockEmailAddress. Returns false when a response was already written.
func resolveMagicLinkAccount(w http.ResponseWriter, r *http.Request, s *store.Store, address string) (string, bool) {
	fail := func(status int, code string) (string, bool) {
		WriteError(w, r, status, code, nil)
		return "", false
	}
	owner, resolution, err := s.ResolveAddressOwner(address)
	if err != nil {
		log.Printf("magic-link: address resolution failed: %v", err)
		return fail(http.StatusInternalServerError, "internal_error")
	}
	switch resolution {
	case store.AddressFree:
		user, err := createMagicLinkUser(s, address)
		if err != nil {
			log.Printf("magic-link: createMagicLinkUser error: %v", err)
			return fail(http.StatusInternalServerError, "internal_error")
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
				return fail(http.StatusBadRequest, "invalid_or_expired_code")
			}
			now := time.Now().UTC()
			user.EmailVerifiedAt = &now
			if err = s.SaveUser(*user); err == nil {
				err = s.ClearSessions(owner.ID)
			}
		}
		if err != nil {
			log.Printf("magic-link: takeover of unconfirmed account %s failed: %v", owner.ID, err)
			return fail(http.StatusInternalServerError, "internal_error")
		}
		return owner.ID, true
	}
	log.Printf("magic-link: address not uniquely assignable — login refused")
	return fail(http.StatusBadRequest, "invalid_or_expired_code")
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
		model.MarkOnboardingPending(&user)
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
