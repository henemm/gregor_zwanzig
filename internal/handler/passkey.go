package handler

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-webauthn/webauthn/protocol"
	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// Passkey/WebAuthn handlers — Issue #450 V1 Add-on.
//
// Five endpoints: Register Begin/Finish (auth-protected), Login Begin/Finish
// (public), and Delete-Credential (auth-protected). Challenge state is held in
// an in-memory ChallengeStore with a 5-minute TTL. Take() is destructive →
// replay attempts on the same challenge fail with 400/401.

const challengeTTL = 5 * time.Minute

// maxWebAuthnBodyBytes caps the request body for the WebAuthn finish endpoints.
// Real attestation/assertion payloads are well below 5 KB; 64 KB gives a generous
// buffer while preventing memory-exhaustion via oversized POSTs (F004).
const maxWebAuthnBodyBytes = 64 * 1024

// writeJSONError writes a JSON error body `{"error":"<code>"}` with the given status.
func writeJSONError(w http.ResponseWriter, status int, code string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]string{"error": code})
}

// PasskeyRegisterBeginHandler starts a new WebAuthn registration ceremony for
// the currently-authenticated user. The challenge is persisted in the
// challenge store for 5 minutes; the client must POST the resulting
// AttestationResponse back to /register/finish within that window.
func PasskeyRegisterBeginHandler(s *store.Store, wa *webauthn.WebAuthn, cs *ChallengeStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		if userID == "" {
			writeJSONError(w, http.StatusUnauthorized, "unauthorized")
			return
		}
		user, err := s.LoadUser(userID)
		if err != nil || user == nil {
			writeJSONError(w, http.StatusNotFound, "not_found")
			return
		}

		creation, sessionData, err := wa.BeginRegistration(user)
		if err != nil {
			writeJSONError(w, http.StatusInternalServerError, "webauthn_begin_failed")
			return
		}

		cs.Put(sessionData.Challenge, &ChallengeEntry{
			SessionData: *sessionData,
			UserID:      userID,
			ExpiresAt:   time.Now().Add(challengeTTL),
		})

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"publicKey": creation.Response})
	}
}

// PasskeyRegisterFinishHandler completes a WebAuthn registration ceremony.
// Parses the AttestationResponse, looks up the pending challenge, verifies the
// attestation via the go-webauthn library, and appends a new credential to the
// user's PasskeyCredentials list.
func PasskeyRegisterFinishHandler(s *store.Store, wa *webauthn.WebAuthn, cs *ChallengeStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		if userID == "" {
			writeJSONError(w, http.StatusUnauthorized, "unauthorized")
			return
		}

		// Cap the body size to prevent memory exhaustion (F004).
		r.Body = http.MaxBytesReader(w, r.Body, maxWebAuthnBodyBytes)

		// Read the body once into a buffer so we can both extract the optional
		// label and feed it to the WebAuthn parser.
		bodyBytes, err := io.ReadAll(r.Body)
		if err != nil {
			writeJSONError(w, http.StatusBadRequest, "invalid_body")
			return
		}

		var labelEnvelope struct {
			Label string `json:"label,omitempty"`
		}
		_ = json.Unmarshal(bodyBytes, &labelEnvelope) // best-effort, ignore decode errors

		parsedResponse, err := protocol.ParseCredentialCreationResponseBody(bytes.NewReader(bodyBytes))
		if err != nil {
			writeJSONError(w, http.StatusBadRequest, "attestation_invalid")
			return
		}

		challenge := parsedResponse.Response.CollectedClientData.Challenge
		entry, ok := cs.Take(challenge)
		if !ok {
			writeJSONError(w, http.StatusBadRequest, "challenge_expired_or_missing")
			return
		}
		if entry.UserID != userID {
			writeJSONError(w, http.StatusBadRequest, "user_mismatch")
			return
		}

		user, err := s.LoadUser(userID)
		if err != nil || user == nil {
			writeJSONError(w, http.StatusNotFound, "not_found")
			return
		}

		credential, err := wa.CreateCredential(user, entry.SessionData, parsedResponse)
		if err != nil {
			writeJSONError(w, http.StatusBadRequest, "attestation_invalid")
			return
		}

		newCred := model.WebAuthnCredential{
			ID:              credential.ID,
			PublicKey:       credential.PublicKey,
			AttestationType: credential.AttestationType,
			Transport:       transportsToStrings(credential.Transport),
			Flags:           credential.Flags,
			Authenticator:   credential.Authenticator,
			CreatedAt:       time.Now().UTC(),
			Label:           labelEnvelope.Label,
		}
		user.PasskeyCredentials = append(user.PasskeyCredentials, newCred)

		if err := s.SaveUser(*user); err != nil {
			writeJSONError(w, http.StatusInternalServerError, "store_error")
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		_ = json.NewEncoder(w).Encode(map[string]any{
			"id":         base64.RawURLEncoding.EncodeToString(newCred.ID),
			"label":      newCred.Label,
			"created_at": newCred.CreatedAt.Format(time.RFC3339),
		})
	}
}

// PasskeyLoginBeginHandler starts a WebAuthn login ceremony for the supplied
// username. Public endpoint — no session required. Returns 401 with the same
// generic error message whether the user is unknown or has no passkeys, to
// avoid trivial enumeration.
func PasskeyLoginBeginHandler(s *store.Store, wa *webauthn.WebAuthn, cs *ChallengeStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Username string `json:"username"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Username == "" {
			writeJSONError(w, http.StatusBadRequest, "invalid_request")
			return
		}

		user, err := s.LoadUser(req.Username)
		if err != nil || user == nil || len(user.PasskeyCredentials) == 0 {
			writeJSONError(w, http.StatusUnauthorized, "invalid_credentials")
			return
		}

		assertion, sessionData, err := wa.BeginLogin(user)
		if err != nil {
			writeJSONError(w, http.StatusInternalServerError, "webauthn_begin_failed")
			return
		}

		cs.Put(sessionData.Challenge, &ChallengeEntry{
			SessionData: *sessionData,
			UserID:      req.Username,
			ExpiresAt:   time.Now().Add(challengeTTL),
		})

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"publicKey": assertion.Response})
	}
}

// PasskeyLoginFinishHandler completes a WebAuthn login ceremony, validates the
// assertion via go-webauthn, persists the updated SignCount/LastUsedAt on the
// matched credential, and sets a session cookie with the same shape as the
// classic Username/Password login flow.
func PasskeyLoginFinishHandler(s *store.Store, wa *webauthn.WebAuthn, cs *ChallengeStore, secret string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Cap the body size to prevent memory exhaustion (F004).
		r.Body = http.MaxBytesReader(w, r.Body, maxWebAuthnBodyBytes)

		parsedResponse, err := protocol.ParseCredentialRequestResponseBody(r.Body)
		if err != nil {
			writeJSONError(w, http.StatusUnauthorized, "invalid_credentials")
			return
		}

		// Identifier-First flow: the userHandle from the authenticator is
		// redundant here because we keyed the challenge to a known username at
		// Begin-time. Clearing it skips the library's userHandle-match check,
		// which is only meaningful for discoverable (passwordless) credentials.
		parsedResponse.Response.UserHandle = nil

		challenge := parsedResponse.Response.CollectedClientData.Challenge
		entry, ok := cs.Take(challenge)
		if !ok {
			writeJSONError(w, http.StatusUnauthorized, "invalid_credentials")
			return
		}

		user, err := s.LoadUser(entry.UserID)
		if err != nil || user == nil {
			writeJSONError(w, http.StatusUnauthorized, "invalid_credentials")
			return
		}

		credential, err := wa.ValidateLogin(user, entry.SessionData, parsedResponse)
		if err != nil {
			writeJSONError(w, http.StatusUnauthorized, "invalid_credentials")
			return
		}

		// Update SignCount + LastUsedAt on the matching persisted credential.
		now := time.Now().UTC()
		for i, pc := range user.PasskeyCredentials {
			if bytes.Equal(pc.ID, credential.ID) {
				user.PasskeyCredentials[i].Authenticator.SignCount = credential.Authenticator.SignCount
				user.PasskeyCredentials[i].Authenticator.CloneWarning = credential.Authenticator.CloneWarning
				user.PasskeyCredentials[i].LastUsedAt = now
				break
			}
		}
		if err := s.SaveUser(*user); err != nil {
			writeJSONError(w, http.StatusInternalServerError, "store_error")
			return
		}

		token := middleware.SignSession(entry.UserID, secret)
		secure := r.Header.Get("X-Forwarded-Proto") == "https" || r.TLS != nil
		http.SetCookie(w, &http.Cookie{
			Name:     "gz_session",
			Value:    token,
			Path:     "/",
			HttpOnly: true,
			SameSite: http.SameSiteLaxMode,
			MaxAge:   86400,
			Secure:   secure,
		})

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{"id": entry.UserID})
	}
}

// PasskeyDeleteCredentialHandler removes a single registered Passkey from the
// authenticated user's credential list. Refuses to remove the last passkey of
// a passwordless user (lock-out protection) — in V1 this branch is defensive
// because every user is guaranteed to have a PasswordHash.
func PasskeyDeleteCredentialHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		if userID == "" {
			writeJSONError(w, http.StatusUnauthorized, "unauthorized")
			return
		}

		// Prefer chi.URLParam; fall back to the last URL path segment so the
		// handler can be exercised from unit tests that drive it directly
		// without going through a chi router.
		credIDB64 := chi.URLParam(r, "id")
		if credIDB64 == "" {
			credIDB64 = lastPathSegment(r.URL.Path)
		}
		if credIDB64 == "" {
			writeJSONError(w, http.StatusBadRequest, "missing_credential_id")
			return
		}
		credID, err := base64.RawURLEncoding.DecodeString(credIDB64)
		if err != nil {
			writeJSONError(w, http.StatusBadRequest, "invalid_credential_id")
			return
		}

		user, err := s.LoadUser(userID)
		if err != nil || user == nil {
			writeJSONError(w, http.StatusNotFound, "not_found")
			return
		}

		// Lock-out protection: refuse to delete the last passkey of a
		// password-less user (defensive — V1 always has a PasswordHash).
		if user.PasswordHash == "" && len(user.PasskeyCredentials) <= 1 {
			writeJSONError(w, http.StatusBadRequest, "cannot_remove_last_passkey_without_password")
			return
		}

		filtered := user.PasskeyCredentials[:0]
		for _, pc := range user.PasskeyCredentials {
			if !bytes.Equal(pc.ID, credID) {
				filtered = append(filtered, pc)
			}
		}
		user.PasskeyCredentials = filtered

		if err := s.SaveUser(*user); err != nil {
			writeJSONError(w, http.StatusInternalServerError, "store_error")
			return
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{"status": "deleted"})
	}
}

// transportsToStrings converts the library's typed transports to the plain
// strings we persist in user.json (kept stable across library upgrades).
func transportsToStrings(in []protocol.AuthenticatorTransport) []string {
	if len(in) == 0 {
		return nil
	}
	out := make([]string, 0, len(in))
	for _, t := range in {
		out = append(out, string(t))
	}
	return out
}

// lastPathSegment returns the last non-empty segment of an URL path, with any
// trailing slash trimmed. Returns "" for an empty path.
func lastPathSegment(p string) string {
	p = strings.TrimRight(p, "/")
	if i := strings.LastIndex(p, "/"); i >= 0 {
		return p[i+1:]
	}
	return p
}
