package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// TDD GREEN — Issue #1219 Scheibe 2a-ii: Einlösung des E-Mail-Bestätigungslinks.
// Spec: docs/specs/modules/fix_1219_verify_flow_2a_ii.md (AC-1..AC-8). Echter
// Handler + echter Store + echte Platte, keine Mocks.

// seedVerifyEmailUser writes a minimal user.json with the given id under the
// store's user dir (RMW-friendly seed, mirrors seedVerifyUser in
// profile_verify_send_test.go).
func seedVerifyEmailUser(t *testing.T, s *store.Store, id string) {
	t.Helper()
	if err := s.SaveUser(model.User{ID: id, CreatedAt: time.Now()}); err != nil {
		t.Fatalf("seed user failed: %v", err)
	}
}

// makeVerificationToken hashes plaintext with bcrypt and persists it for
// userId with the given expiry — mirrors dispatchVerificationMail's own
// token creation (auth.go).
func makeVerificationToken(t *testing.T, s *store.Store, userId, plaintext string, expiresAt time.Time) {
	t.Helper()
	hash, err := bcrypt.GenerateFromPassword([]byte(plaintext), bcrypt.DefaultCost)
	if err != nil {
		t.Fatalf("bcrypt hash failed: %v", err)
	}
	if err := s.SaveVerificationToken(userId, model.EmailVerificationToken{
		TokenHash: string(hash),
		ExpiresAt: expiresAt,
	}); err != nil {
		t.Fatalf("SaveVerificationToken failed: %v", err)
	}
}

func postVerifyEmail(h func(w http.ResponseWriter, r *http.Request), body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest("POST", "/api/auth/verify-email", strings.NewReader(body))
	w := httptest.NewRecorder()
	h(w, req)
	return w
}

// AC-1: gültiger Token → 200, EmailVerifiedAt gesetzt (nahe now), Token
// gelöscht — UND (Adversary-Fix-Loop F001) RMW-Nachweis: alle anderen
// Profilfelder bleiben unverändert. Zusatzfelder werden hier lokal gesetzt
// (nicht im gemeinsamen seedVerifyEmailUser-Helper), damit die übrigen
// AC-Tests unberührt bleiben.
func TestVerifyEmailHandler_ValidToken_VerifiesAndDeletesToken_AC1(t *testing.T) {
	s := newTestStore(t)
	before := time.Now()
	const (
		annaDisplayName = "Anna Beispiel"
		annaMailTo      = "anna-empfang@x.de"
		annaTier        = "standard"
	)
	if err := s.SaveUser(model.User{
		ID:          "anna",
		CreatedAt:   before,
		DisplayName: annaDisplayName,
		MailTo:      annaMailTo,
		Tier:        annaTier,
	}); err != nil {
		t.Fatalf("AC-1: seed with profile fields failed: %v", err)
	}
	makeVerificationToken(t, s, "anna", "plaintext-token", before.Add(24*time.Hour))

	h := VerifyEmailHandler(s)
	w := postVerifyEmail(h.ServeHTTP, `{"user":"anna","token":"plaintext-token"}`)

	if w.Code != 200 {
		t.Fatalf("AC-1: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]string
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil || resp["status"] != "ok" {
		t.Errorf("AC-1: expected {status:ok}, got %s", w.Body.String())
	}

	user, err := s.LoadUser("anna")
	if err != nil || user == nil {
		t.Fatalf("AC-1: LoadUser failed: %v", err)
	}
	if user.EmailVerifiedAt == nil {
		t.Fatal("AC-1: EmailVerifiedAt must be set after successful verification")
	}
	if user.EmailVerifiedAt.Before(before.Add(-time.Minute)) || user.EmailVerifiedAt.After(time.Now().Add(time.Minute)) {
		t.Errorf("AC-1: EmailVerifiedAt %v not close to now", user.EmailVerifiedAt)
	}

	// RMW-Nachweis (Adversary F001): Verifikation darf NUR EmailVerifiedAt
	// setzen — alle anderen zuvor gesetzten Profilfelder müssen exakt
	// erhalten bleiben (kein Replace, echtes Read-Modify-Write).
	if user.DisplayName != annaDisplayName {
		t.Errorf("AC-1 RMW: DisplayName must be unchanged, want %q, got %q", annaDisplayName, user.DisplayName)
	}
	if user.MailTo != annaMailTo {
		t.Errorf("AC-1 RMW: MailTo must be unchanged, want %q, got %q", annaMailTo, user.MailTo)
	}
	if user.Tier != annaTier {
		t.Errorf("AC-1 RMW: Tier must be unchanged, want %q, got %q", annaTier, user.Tier)
	}

	tok, err := s.LoadVerificationToken("anna")
	if err != nil {
		t.Fatalf("AC-1: LoadVerificationToken errored: %v", err)
	}
	if tok != nil {
		t.Error("AC-1: token must be deleted after successful verification")
	}
}

// AC-2: abgelaufener Token → 400 token expired, EmailVerifiedAt bleibt nil, Token bleibt.
func TestVerifyEmailHandler_ExpiredToken_Returns400AndKeepsState_AC2(t *testing.T) {
	s := newTestStore(t)
	seedVerifyEmailUser(t, s, "bea")
	makeVerificationToken(t, s, "bea", "plaintext-token", time.Now().Add(-1*time.Minute))

	h := VerifyEmailHandler(s)
	w := postVerifyEmail(h.ServeHTTP, `{"user":"bea","token":"plaintext-token"}`)

	if w.Code != 400 {
		t.Fatalf("AC-2: expected 400, got %d", w.Code)
	}
	if !strings.Contains(w.Body.String(), "token expired") {
		t.Errorf("AC-2: expected 'token expired' error, got %s", w.Body.String())
	}
	user, _ := s.LoadUser("bea")
	if user.EmailVerifiedAt != nil {
		t.Error("AC-2: EmailVerifiedAt must remain nil on expired token")
	}
	tok, _ := s.LoadVerificationToken("bea")
	if tok == nil {
		t.Error("AC-2: expired token must NOT be deleted")
	}
}

// AC-3: falscher Klartext-Token → 400 invalid token, keine Zustandsänderung.
func TestVerifyEmailHandler_WrongToken_Returns400AndKeepsState_AC3(t *testing.T) {
	s := newTestStore(t)
	seedVerifyEmailUser(t, s, "carl")
	makeVerificationToken(t, s, "carl", "correct-token", time.Now().Add(24*time.Hour))

	h := VerifyEmailHandler(s)
	w := postVerifyEmail(h.ServeHTTP, `{"user":"carl","token":"wrong-token"}`)

	if w.Code != 400 {
		t.Fatalf("AC-3: expected 400, got %d", w.Code)
	}
	if !strings.Contains(w.Body.String(), "invalid token") {
		t.Errorf("AC-3: expected 'invalid token' error, got %s", w.Body.String())
	}
	user, _ := s.LoadUser("carl")
	if user.EmailVerifiedAt != nil {
		t.Error("AC-3: EmailVerifiedAt must remain nil on wrong token")
	}
	tok, _ := s.LoadVerificationToken("carl")
	if tok == nil {
		t.Error("AC-3: token must NOT be consumed by a failed attempt")
	}
}

// AC-4: kein Token für user → 400 invalid token.
func TestVerifyEmailHandler_NoTokenExists_Returns400_AC4(t *testing.T) {
	s := newTestStore(t)
	seedVerifyEmailUser(t, s, "dana")

	h := VerifyEmailHandler(s)
	w := postVerifyEmail(h.ServeHTTP, `{"user":"dana","token":"anything"}`)

	if w.Code != 400 {
		t.Fatalf("AC-4: expected 400, got %d", w.Code)
	}
	if !strings.Contains(w.Body.String(), "invalid token") {
		t.Errorf("AC-4: expected 'invalid token' error, got %s", w.Body.String())
	}
}

// AC-5: As Token mit user=B eingereicht → B nicht verifiziert, As Token bleibt.
func TestVerifyEmailHandler_CrossUserTokenDoesNotVerifyOther_AC5(t *testing.T) {
	s := newTestStore(t)
	seedVerifyEmailUser(t, s, "userA")
	seedVerifyEmailUser(t, s, "userB")
	makeVerificationToken(t, s, "userA", "a-token", time.Now().Add(24*time.Hour))

	h := VerifyEmailHandler(s)
	w := postVerifyEmail(h.ServeHTTP, `{"user":"userB","token":"a-token"}`)

	if w.Code != 400 {
		t.Fatalf("AC-5: expected 400, got %d", w.Code)
	}
	userB, _ := s.LoadUser("userB")
	if userB.EmailVerifiedAt != nil {
		t.Error("AC-5: userB must not be verified by userA's token")
	}
	tokA, _ := s.LoadVerificationToken("userA")
	if tokA == nil {
		t.Error("AC-5: userA's token must remain untouched")
	}
}

// AC-6: erfolgreiche Einlösung, dann derselbe POST nochmal → 400 (kein Replay).
func TestVerifyEmailHandler_ReplayAfterSuccess_Returns400_AC6(t *testing.T) {
	s := newTestStore(t)
	seedVerifyEmailUser(t, s, "eddy")
	makeVerificationToken(t, s, "eddy", "one-time-token", time.Now().Add(24*time.Hour))

	h := VerifyEmailHandler(s)
	body := `{"user":"eddy","token":"one-time-token"}`

	w1 := postVerifyEmail(h.ServeHTTP, body)
	if w1.Code != 200 {
		t.Fatalf("AC-6: first call expected 200, got %d: %s", w1.Code, w1.Body.String())
	}

	w2 := postVerifyEmail(h.ServeHTTP, body)
	if w2.Code != 400 {
		t.Fatalf("AC-6: replay expected 400, got %d: %s", w2.Code, w2.Body.String())
	}
}

// AC-7: Request ohne gz_session-Cookie durch die AuthMiddleware-Kette gegen
// die registrierte Route erreicht den Handler (Public-Allowlist), nicht 401.
func TestVerifyEmailHandler_PublicRoute_NotBlockedByAuthMiddleware_AC7(t *testing.T) {
	s := newTestStore(t)
	seedVerifyEmailUser(t, s, "finn")
	makeVerificationToken(t, s, "finn", "finn-token", time.Now().Add(24*time.Hour))

	wrapped := middleware.AuthMiddleware("test-secret-32-chars-minimum-ok!")(VerifyEmailHandler(s))
	req := httptest.NewRequest("POST", "/api/auth/verify-email", strings.NewReader(`{"user":"finn","token":"finn-token"}`))
	w := httptest.NewRecorder()
	wrapped.ServeHTTP(w, req)

	if w.Code == 401 {
		t.Fatalf("AC-7: request without cookie must reach the handler (public allowlist), got 401: %s", w.Body.String())
	}
	if w.Code != 200 {
		t.Fatalf("AC-7: expected handler status 200, got %d: %s", w.Code, w.Body.String())
	}
}

// AC-8: leerer Body / fehlendes Feld → 400 invalid request, ohne Store-Zugriff.
func TestVerifyEmailHandler_EmptyOrIncompleteBody_Returns400_AC8(t *testing.T) {
	s := newTestStore(t)
	h := VerifyEmailHandler(s)

	for _, body := range []string{`{}`, `{"user":"someone"}`, `{"token":"tok"}`} {
		w := postVerifyEmail(h.ServeHTTP, body)
		if w.Code != 400 {
			t.Errorf("AC-8: body %q expected 400, got %d", body, w.Code)
		}
		if !strings.Contains(w.Body.String(), "invalid request") {
			t.Errorf("AC-8: body %q expected 'invalid request' error, got %s", body, w.Body.String())
		}
	}
}
