package handler

// Frischer Nachweis vor sicherheitsrelevanten Kontoaenderungen (Issue #2961,
// GA3, ADR-0115). Verallgemeinert den Nachweis der Kontoloeschung (ADR-0081):
// aktuelles Passwort ODER ein Code an die bisherige, wirksame Adresse
// (account_delete_code.go, eigener Store reauthCodeStore). Ein gelungener
// Nachweis gilt 10 Minuten fuer genau diese Sitzung dieses Nutzers.
//
// Gesperrt sind ohne Nachweis: Wechsel von mail_to oder email (Profil-PUT),
// Passkey hinzufuegen (begin/finish) und entfernen. Die Sperre sitzt als
// Huelle an den Routen (RequireFreshReauth, RequireReauthForAddressChange).

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"sync"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const reauthGrantTTL = 10 * time.Minute

// reauthGrants: Schluessel userID + "\x00" + sessionID, Wert Ablaufzeit.
// Prozessintern wie die Codes: ein Neustart verlangt den Nachweis erneut.
var reauthGrants sync.Map

func reauthKey(userID, sessionID string) string { return userID + "\x00" + sessionID }

// grantReauth vermerkt einen gelungenen Nachweis fuer (userID, sessionID).
func grantReauth(userID, sessionID string, now time.Time) time.Time {
	until := now.Add(reauthGrantTTL)
	reauthGrants.Store(reauthKey(userID, sessionID), until)
	return until
}

// hasFreshReauth: gibt es fuer genau diese Sitzung dieses Nutzers einen
// Nachweis, der noch nicht abgelaufen ist? Leere Kennungen haben nie einen.
func hasFreshReauth(userID, sessionID string, now time.Time) bool {
	if userID == "" || sessionID == "" {
		return false
	}
	v, ok := reauthGrants.Load(reauthKey(userID, sessionID))
	return ok && now.Before(v.(time.Time))
}

// gcReauthGrants entfernt abgelaufene Nachweise (Reaper).
func gcReauthGrants(now time.Time) {
	reauthGrants.Range(func(k, v any) bool {
		if !now.Before(v.(time.Time)) {
			reauthGrants.CompareAndDelete(k, v)
		}
		return true
	})
}

// sessionIDFromRequest liest die Sitzungskennung aus dem (von AuthMiddleware
// bereits geprueften) Cookie. Leer, wenn keins da ist.
func sessionIDFromRequest(r *http.Request, secret string) string {
	c, err := r.Cookie("gz_session")
	if err != nil {
		return ""
	}
	uid, sid, ok := middleware.SessionFromCookie(c.Value, secret)
	if !ok || uid != middleware.UserIDFromContext(r.Context()) {
		return ""
	}
	return sid
}

func writeReauthRequired(w http.ResponseWriter, r *http.Request) {
	WriteError(w, r, http.StatusForbidden, "reauth_required", nil)
}

// RequireFreshReauth laesst die Anfrage nur mit frischem Nachweis dieser
// Sitzung durch (Passkey hinzufuegen/entfernen).
func RequireFreshReauth(secret string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uid := middleware.UserIDFromContext(r.Context())
		if !hasFreshReauth(uid, sessionIDFromRequest(r, secret), time.Now()) {
			writeReauthRequired(w, r)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// addressFieldsChange ist das Aenderungs-Praedikat fuer email/mail_to — das
// gleiche wie in UpdateProfileHandler (normalisiert verglichen; leer zaehlt
// als Wert, Leeren ist also auch eine Aenderung).
func addressFieldsChange(u *model.User, email, mailTo *string) bool {
	if email != nil && store.NormalizeEmailAddress(*email) != store.NormalizeEmailAddress(u.Email) {
		return true
	}
	return mailTo != nil && store.NormalizeEmailAddress(*mailTo) != store.NormalizeEmailAddress(u.MailTo)
}

// RequireReauthForAddressChange: der Profil-PUT verlangt einen frischen
// Nachweis nur, wenn er email oder mail_to tatsaechlich aendert. Der Rumpf
// wird gelesen und unveraendert an next weitergereicht (die globale
// Groessengrenze greift davor). Unlesbares JSON entscheidet der Handler.
func RequireReauthForAddressChange(s *store.Store, secret string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, err := io.ReadAll(r.Body)
		if err != nil {
			WriteError(w, r, http.StatusBadRequest, "invalid_request", nil)
			return
		}
		r.Body = io.NopCloser(bytes.NewReader(body))
		var felder struct {
			Email  *string `json:"email"`
			MailTo *string `json:"mail_to"`
		}
		uid := middleware.UserIDFromContext(r.Context())
		if json.Unmarshal(body, &felder) == nil && (felder.Email != nil || felder.MailTo != nil) {
			u, lerr := s.LoadUser(uid)
			if lerr == nil && u != nil && addressFieldsChange(u, felder.Email, felder.MailTo) &&
				!hasFreshReauth(uid, sessionIDFromRequest(r, secret), time.Now()) {
				writeReauthRequired(w, r)
				return
			}
		}
		next.ServeHTTP(w, r)
	})
}

// ReauthHandler: POST /api/auth/reauth mit {password?, code?}. Prueft den
// Nachweis wie die Kontoloeschung und vermerkt ihn 10 Minuten fuer diese
// Sitzung. Antwort {"status":"ok","valid_until":RFC3339}.
func ReauthHandler(s *store.Store, secret string) http.HandlerFunc {
	// Hoechstens 5 falsche Passwoerter je Nutzer und 15 Minuten (vor dem
	// Vergleich gezaehlt), wie beim Passwortwechsel.
	guard := newAttemptGuard(5, 15*time.Minute, 15*time.Minute)
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		sessionID := sessionIDFromRequest(r, secret)
		if userID == "" || sessionID == "" {
			WriteError(w, r, http.StatusUnauthorized, "unauthorized", nil)
			return
		}
		var req struct {
			Password string `json:"password"`
			Code     string `json:"code"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req) // kaputter Rumpf = kein Nachweis
		user, err := s.LoadUser(userID)
		if err != nil || user == nil {
			WriteError(w, r, http.StatusNotFound, "not_found", nil)
			return
		}
		switch {
		case req.Password != "":
			if !guard.Reserve(userID) {
				w.Header().Set("Retry-After", "900")
				WriteError(w, r, http.StatusTooManyRequests, "rate_limit_exceeded", nil)
				return
			}
			if user.PasswordHash == "" ||
				bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(req.Password)) != nil {
				WriteError(w, r, http.StatusForbidden, "wrong_password", nil)
				return
			}
			guard.Success(userID)
		case req.Code != "":
			if _, ok := consumeAccountCode(&reauthCodeStore, userID, req.Code, time.Now()); !ok {
				WriteError(w, r, http.StatusForbidden, "invalid_code", nil)
				return
			}
		default:
			WriteError(w, r, http.StatusBadRequest, "reauth_required", nil)
			return
		}
		until := grantReauth(userID, sessionID, time.Now())
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{
			"status": "ok", "valid_until": until.UTC().Format(time.RFC3339),
		})
	}
}
