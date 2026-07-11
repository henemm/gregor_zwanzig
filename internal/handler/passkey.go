package handler

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-webauthn/webauthn/protocol"
	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

var validUsernameRe = regexp.MustCompile(`^[a-zA-Z0-9_-]+$`)

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

// PasskeyLoginDiscoverableBeginHandler starts a Discoverable (usernameless) WebAuthn
// login ceremony with Conditional Mediation. No request body is required — the
// browser will surface all registered passkeys for the RP as an autofill picker.
// Issue #467 — V3 Add-on (Conditional UI / Discoverable Credentials).
func PasskeyLoginDiscoverableBeginHandler(wa *webauthn.WebAuthn, cs *ChallengeStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// BeginDiscoverableMediatedLogin emits "mediation":"conditional" in the
		// top-level JSON — required for the browser to render the inline picker.
		assertion, sessionData, err := wa.BeginDiscoverableMediatedLogin(protocol.MediationConditional)
		if err != nil {
			writeJSONError(w, http.StatusInternalServerError, "begin_failed")
			return
		}

		// UserID MUST stay empty: ValidatePasskeyLogin refuses any session that
		// was initiated with a non-empty UserID (see go-webauthn login.go:254).
		cs.Put(sessionData.Challenge, &ChallengeEntry{
			SessionData: *sessionData,
			UserID:      "",
			ExpiresAt:   time.Now().Add(challengeTTL),
		})

		// Serialise the FULL assertion object (not just assertion.Response) so
		// the top-level "mediation":"conditional" survives the wire — without
		// it the browser falls back to a modal prompt.
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(assertion)
	}
}

// PasskeyLoginDiscoverableFinishHandler completes a Discoverable login ceremony.
// The browser supplies the user identity via the assertion's userHandle; we look
// up the user via that handle and validate the signature against their stored
// credentials. Issue #467 — V3 Add-on.
func PasskeyLoginDiscoverableFinishHandler(s *store.Store, wa *webauthn.WebAuthn, cs *ChallengeStore, secret string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Cap body size — same as V1 (F004).
		r.Body = http.MaxBytesReader(w, r.Body, maxWebAuthnBodyBytes)

		parsedResponse, err := protocol.ParseCredentialRequestResponseBody(r.Body)
		if err != nil {
			writeJSONError(w, http.StatusUnauthorized, "invalid_credentials")
			return
		}

		// NOTE: Unlike V1 we do NOT clear parsedResponse.Response.UserHandle —
		// the Discoverable flow uses userHandle as the SOLE user identifier.

		challenge := parsedResponse.Response.CollectedClientData.Challenge
		entry, ok := cs.Take(challenge)
		if !ok {
			writeJSONError(w, http.StatusUnauthorized, "invalid_credentials")
			return
		}

		// DiscoverableUserHandler: load user by userHandle (== user.ID bytes).
		discoverableHandler := func(rawID, userHandle []byte) (webauthn.User, error) {
			u, lerr := s.LoadUser(string(userHandle))
			if lerr != nil || u == nil {
				return nil, lerr
			}
			return u, nil
		}

		user, credential, err := wa.ValidatePasskeyLogin(discoverableHandler, entry.SessionData, parsedResponse)
		if err != nil || user == nil || credential == nil {
			writeJSONError(w, http.StatusUnauthorized, "invalid_credentials")
			return
		}

		mu, ok := user.(*model.User)
		if !ok {
			writeJSONError(w, http.StatusUnauthorized, "invalid_credentials")
			return
		}

		// Update SignCount + LastUsedAt on the matching persisted credential.
		now := time.Now().UTC()
		for i, pc := range mu.PasskeyCredentials {
			if bytes.Equal(pc.ID, credential.ID) {
				mu.PasskeyCredentials[i].Authenticator.SignCount = credential.Authenticator.SignCount
				mu.PasskeyCredentials[i].Authenticator.CloneWarning = credential.Authenticator.CloneWarning
				mu.PasskeyCredentials[i].LastUsedAt = now
				break
			}
		}
		if err := s.SaveUser(*mu); err != nil {
			writeJSONError(w, http.StatusInternalServerError, "store_error")
			return
		}

		userID := mu.WebAuthnName()
		token := middleware.SignSession(userID, secret)
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
		_ = json.NewEncoder(w).Encode(map[string]string{"id": userID})
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

// PasskeyRegisterPublicBeginHandler starts a public WebAuthn registration ceremony.
// No session required — takes {"username","email"}, validates, checks availability,
// and returns a WebAuthn challenge. Issue #466 — V2 Add-on.
func PasskeyRegisterPublicBeginHandler(s *store.Store, wa *webauthn.WebAuthn, cs *ChallengeStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Username string `json:"username"`
			Email    string `json:"email"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSONError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		if len(req.Username) < 3 || len(req.Username) > 50 || !validUsernameRe.MatchString(req.Username) {
			writeJSONError(w, http.StatusBadRequest, "validation_failed")
			return
		}
		if !strings.Contains(req.Email, "@") {
			writeJSONError(w, http.StatusBadRequest, "validation_failed")
			return
		}
		if s.UserExists(req.Username) {
			writeJSONError(w, http.StatusConflict, "user_already_exists")
			return
		}

		tempUser := &model.User{ID: req.Username}
		creation, sessionData, err := wa.BeginRegistration(tempUser)
		if err != nil {
			writeJSONError(w, http.StatusInternalServerError, "webauthn_begin_failed")
			return
		}

		cs.Put(sessionData.Challenge, &ChallengeEntry{
			SessionData: *sessionData,
			UserID:      req.Username,
			Email:       req.Email,
			ExpiresAt:   time.Now().Add(challengeTTL),
		})

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"publicKey": creation.Response})
	}
}

// PasskeyRegisterPublicFinishHandler completes a public WebAuthn registration.
// Verifies attestation, creates a passwordless user, and sets gz_session cookie.
// Issue #466 — V2 Add-on.
func PasskeyRegisterPublicFinishHandler(s *store.Store, wa *webauthn.WebAuthn, cs *ChallengeStore, secret string, cfg config.Config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		r.Body = http.MaxBytesReader(w, r.Body, maxWebAuthnBodyBytes)

		bodyBytes, err := io.ReadAll(r.Body)
		if err != nil {
			writeJSONError(w, http.StatusBadRequest, "invalid_body")
			return
		}

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

		// Race protection: username may have been claimed between Begin and Finish.
		if s.UserExists(entry.UserID) {
			writeJSONError(w, http.StatusConflict, "user_already_exists")
			return
		}

		tempUser := &model.User{ID: entry.UserID}
		credential, err := wa.CreateCredential(tempUser, entry.SessionData, parsedResponse)
		if err != nil {
			writeJSONError(w, http.StatusBadRequest, "attestation_invalid")
			return
		}

		now := time.Now().UTC()
		newUser := model.User{
			ID:        entry.UserID,
			Email:     entry.Email,
			CreatedAt: now,
			PasskeyCredentials: []model.WebAuthnCredential{{
				ID:              credential.ID,
				PublicKey:       credential.PublicKey,
				AttestationType: credential.AttestationType,
				Transport:       transportsToStrings(credential.Transport),
				Flags:           credential.Flags,
				Authenticator:   credential.Authenticator,
				CreatedAt:       now,
			}},
		}
		if err := s.SaveUser(newUser); err != nil {
			writeJSONError(w, http.StatusInternalServerError, "store_error")
			return
		}
		s.ProvisionUserDirs(entry.UserID)

		// Issue #1226: passwortloses Konto durchläuft denselben #1219-Double-Opt-In
		// wie die anderen beiden Kontoerstellungspfade — sonst bliebe die im
		// Begin-Schritt übermittelte Adresse dauerhaft unverifiziert.
		dispatchVerificationMail(s, cfg, entry.UserID, &newUser)

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
		w.WriteHeader(http.StatusCreated)
		_ = json.NewEncoder(w).Encode(map[string]string{"id": entry.UserID})
	}
}
