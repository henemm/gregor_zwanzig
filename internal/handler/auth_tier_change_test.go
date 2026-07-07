package handler

import (
	"bytes"
	"encoding/json"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
)

// TDD RED — Issue #1071 (Epic #1067 Slice 4). These tests will FAIL TO COMPILE
// until model.User gains RequestedTier/RequestedAt and
// RequestTierChangeHandler exists in this package.

func TestRequestTierChange_Success(t *testing.T) {
	s := newTestStore(t)
	if err := s.SaveUser(model.User{ID: "alice", Tier: "free"}); err != nil {
		t.Fatalf("SaveUser failed: %v", err)
	}

	cfg := config.Config{PoEmail: "po@example.com"}
	h := RequestTierChangeHandler(s, cfg)

	body, _ := json.Marshal(map[string]string{"requested_tier": "standard"})
	req := httptest.NewRequest("POST", "/api/auth/tier-change-request", bytes.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "alice"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("AC-1: expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// AC-1 + AC-6: Profile-Response enthaelt requested_tier/requested_at danach.
	profileH := GetProfileHandler(s)
	preq := httptest.NewRequest("GET", "/api/auth/profile", nil)
	preq = preq.WithContext(middleware.ContextWithUserID(preq.Context(), "alice"))
	pw := httptest.NewRecorder()
	profileH.ServeHTTP(pw, preq)

	var resp map[string]interface{}
	if err := json.Unmarshal(pw.Body.Bytes(), &resp); err != nil {
		t.Fatalf("profile response not valid JSON: %v", err)
	}
	if resp["requested_tier"] != "standard" {
		t.Errorf("AC-1: expected requested_tier=standard in profile, got %v", resp["requested_tier"])
	}
	if resp["requested_at"] == nil || resp["requested_at"] == "" {
		t.Errorf("AC-1: expected non-empty requested_at in profile, got %v", resp["requested_at"])
	}
}

func TestRequestTierChange_InvalidTier(t *testing.T) {
	s := newTestStore(t)
	if err := s.SaveUser(model.User{ID: "alice", Tier: "free"}); err != nil {
		t.Fatalf("SaveUser failed: %v", err)
	}
	h := RequestTierChangeHandler(s, config.Config{PoEmail: "po@example.com"})

	body, _ := json.Marshal(map[string]string{"requested_tier": "gold"})
	req := httptest.NewRequest("POST", "/api/auth/tier-change-request", bytes.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "alice"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("AC-2: expected 400, got %d: %s", w.Code, w.Body.String())
	}
	if !bytes.Contains(w.Body.Bytes(), []byte("invalid_tier")) {
		t.Errorf("AC-2: expected error 'invalid_tier', got: %s", w.Body.String())
	}

	// Kein Antrag darf persistiert worden sein.
	user, _ := s.LoadUser("alice")
	if user.RequestedTier != "" {
		t.Errorf("AC-2: expected no persisted request after invalid_tier, got %q", user.RequestedTier)
	}
}

func TestRequestTierChange_AlreadyCurrentTier(t *testing.T) {
	s := newTestStore(t)
	if err := s.SaveUser(model.User{ID: "alice", Tier: "standard"}); err != nil {
		t.Fatalf("SaveUser failed: %v", err)
	}
	h := RequestTierChangeHandler(s, config.Config{PoEmail: "po@example.com"})

	body, _ := json.Marshal(map[string]string{"requested_tier": "standard"})
	req := httptest.NewRequest("POST", "/api/auth/tier-change-request", bytes.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "alice"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("AC-3: expected 400, got %d: %s", w.Code, w.Body.String())
	}
	if !bytes.Contains(w.Body.Bytes(), []byte("already_current_tier")) {
		t.Errorf("AC-3: expected error 'already_current_tier', got: %s", w.Body.String())
	}
}

func TestRequestTierChange_TwoUsersIsolated(t *testing.T) {
	s := newTestStore(t)
	if err := s.SaveUser(model.User{ID: "user_a", Tier: "free"}); err != nil {
		t.Fatalf("SaveUser user_a failed: %v", err)
	}
	if err := s.SaveUser(model.User{ID: "user_b", Tier: "free"}); err != nil {
		t.Fatalf("SaveUser user_b failed: %v", err)
	}
	h := RequestTierChangeHandler(s, config.Config{PoEmail: "po@example.com"})

	bodyA, _ := json.Marshal(map[string]string{"requested_tier": "standard"})
	reqA := httptest.NewRequest("POST", "/api/auth/tier-change-request", bytes.NewReader(bodyA))
	reqA = reqA.WithContext(middleware.ContextWithUserID(reqA.Context(), "user_a"))
	wA := httptest.NewRecorder()
	h.ServeHTTP(wA, reqA)
	if wA.Code != 200 {
		t.Fatalf("AC-4: user_a expected 200, got %d", wA.Code)
	}

	bodyB, _ := json.Marshal(map[string]string{"requested_tier": "premium"})
	reqB := httptest.NewRequest("POST", "/api/auth/tier-change-request", bytes.NewReader(bodyB))
	reqB = reqB.WithContext(middleware.ContextWithUserID(reqB.Context(), "user_b"))
	wB := httptest.NewRecorder()
	h.ServeHTTP(wB, reqB)
	if wB.Code != 200 {
		t.Fatalf("AC-4: user_b expected 200, got %d", wB.Code)
	}

	userA, _ := s.LoadUser("user_a")
	userB, _ := s.LoadUser("user_b")
	if userA.RequestedTier != "standard" {
		t.Errorf("AC-4: user_a.RequestedTier = %q, want standard", userA.RequestedTier)
	}
	if userB.RequestedTier != "premium" {
		t.Errorf("AC-4: user_b.RequestedTier = %q, want premium", userB.RequestedTier)
	}
	if userA.RequestedTier == userB.RequestedTier {
		t.Fatalf("AC-4: cross-user leak — both users ended up with the same requested tier")
	}
}

func TestRequestTierChange_MailFailureDoesNotBlockSave(t *testing.T) {
	s := newTestStore(t)
	if err := s.SaveUser(model.User{ID: "alice", Tier: "free"}); err != nil {
		t.Fatalf("SaveUser failed: %v", err)
	}

	// Absichtlich unerreichbare SMTP-Config (geschlossener Port), analog
	// TestForgotPassword_EmailFallbackWhenMailToEmpty in
	// auth_password_reset_mail_test.go.
	cfg := config.Config{
		PoEmail:  "po@example.com",
		SMTPHost: "127.0.0.1",
		SMTPPort: 1,
		SMTPUser: "u",
		SMTPPass: "p",
		SMTPFrom: "gregor_zwanzig@henemm.com",
	}
	h := RequestTierChangeHandler(s, cfg)

	body, _ := json.Marshal(map[string]string{"requested_tier": "standard"})
	req := httptest.NewRequest("POST", "/api/auth/tier-change-request", bytes.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "alice"))
	w := httptest.NewRecorder()

	start := time.Now()
	h.ServeHTTP(w, req)
	elapsed := time.Since(start)

	if w.Code != 200 {
		t.Fatalf("AC-5: expected 200 despite SMTP failure, got %d: %s", w.Code, w.Body.String())
	}
	if elapsed > 2*time.Second {
		t.Fatalf("AC-5: handler blocked for %v — must return before the mail goroutine's 20s timeout", elapsed)
	}

	user, _ := s.LoadUser("alice")
	if user.RequestedTier != "standard" {
		t.Errorf("AC-5: expected request persisted despite mail failure, got %q", user.RequestedTier)
	}
}

func TestGetProfile_NoRequestedTierFieldsWhenNoRequestMade(t *testing.T) {
	s := newTestStore(t)
	if err := s.SaveUser(model.User{ID: "bob", Tier: "free"}); err != nil {
		t.Fatalf("SaveUser failed: %v", err)
	}
	h := GetProfileHandler(s)
	req := httptest.NewRequest("GET", "/api/auth/profile", nil)
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "bob"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("profile response not valid JSON: %v", err)
	}
	if _, ok := resp["requested_tier"]; ok {
		t.Errorf("AC-6: expected no requested_tier field for user without a request, got %v", resp["requested_tier"])
	}
	if _, ok := resp["requested_at"]; ok {
		t.Errorf("AC-6: expected no requested_at field for user without a request, got %v", resp["requested_at"])
	}
}
