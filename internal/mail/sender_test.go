package mail

import (
	"strings"
	"testing"
)

// TDD RED — Pure-Function Unit-Tests fuer IsTestUser (AC-4) und BuildResetMail (AC-5).
// These tests will FAIL to compile until internal/mail/sender.go and reset.go exist.

func TestIsTestUser(t *testing.T) {
	cases := []struct {
		userID string
		want   bool
	}{
		{"test-alice", true},
		{"TEST-bob", true},
		{"alice-tdd", true},
		{"AliceTDD", true},
		{"default", false},
		{"henning", false},
		{"", false},
	}
	for _, c := range cases {
		if got := IsTestUser(c.userID); got != c.want {
			t.Errorf("IsTestUser(%q) = %v, want %v", c.userID, got, c.want)
		}
	}
}

// TestIsTestUser_Boundary documents the KNOWN false-positive behaviour of
// IsTestUser: any string containing "test" or "tdd" as a substring matches.
// This mirrors src/app/config.py::_is_test_user (intentional). If a prod-user
// registers with such a name, their reset mail goes through Gmail instead of
// Resend — acceptable risk, easy to avoid in setup. See spec Known Limitations.
func TestIsTestUser_Boundary(t *testing.T) {
	if !IsTestUser("contest") {
		t.Errorf("IsTestUser('contest') = false; expected true (known false positive — see spec)")
	}
	if !IsTestUser("tdd-prod-user") {
		t.Errorf("IsTestUser('tdd-prod-user') = false; expected true (known false positive — see spec)")
	}
}

func TestBuildResetMail_LinkContainsPublicHost(t *testing.T) {
	msg := BuildResetMail("https://example.com", "alice", "abc123")
	if !strings.Contains(msg.PlainBody, "https://example.com/reset-password?user=alice&token=abc123") {
		t.Errorf("Plaintext body missing reset link with public host. Body: %s", msg.PlainBody)
	}
	if !strings.Contains(msg.HTMLBody, "https://example.com/reset-password?user=alice&token=abc123") {
		t.Errorf("HTML body missing reset link with public host. Body: %s", msg.HTMLBody)
	}
}

func TestBuildResetMail_Subject(t *testing.T) {
	msg := BuildResetMail("https://gregor20.henemm.com", "alice", "tok")
	if msg.Subject == "" {
		t.Errorf("Reset mail subject is empty")
	}
}

// TestBuildResetMail_UsernameWithAmpersandIsEscaped guards against query-string
// injection: a malicious username MUST NOT be able to overwrite the token
// parameter by injecting "&token=…".
func TestBuildResetMail_UsernameWithAmpersandIsEscaped(t *testing.T) {
	msg := BuildResetMail("https://example.com", "alice&token=evil", "real-token")
	wantEscaped := "user=alice%26token%3Devil"
	if !strings.Contains(msg.PlainBody, wantEscaped) {
		t.Errorf("Plain body missing escaped username %q. Body: %s", wantEscaped, msg.PlainBody)
	}
	if !strings.Contains(msg.HTMLBody, wantEscaped) {
		t.Errorf("HTML body missing escaped username %q. Body: %s", wantEscaped, msg.HTMLBody)
	}
	// The real token MUST still be present after the &token= separator. The
	// raw injection-string "&token=evil" must NEVER appear unescaped.
	if strings.Contains(msg.PlainBody, "alice&token=evil") {
		t.Errorf("Plain body contains raw injection — username not escaped: %s", msg.PlainBody)
	}
}

// TestBuildResetMail_TokenWithSpecialCharsIsEscaped covers Base64-style tokens
// containing '+' and '/' — both reserved in URL query syntax.
func TestBuildResetMail_TokenWithSpecialCharsIsEscaped(t *testing.T) {
	msg := BuildResetMail("https://example.com", "alice", "abc+def/ghi=")
	// url.QueryEscape: '+' → "%2B", '/' → "%2F", '=' → "%3D"
	wantEscaped := "token=abc%2Bdef%2Fghi%3D"
	if !strings.Contains(msg.PlainBody, wantEscaped) {
		t.Errorf("Plain body missing escaped token %q. Body: %s", wantEscaped, msg.PlainBody)
	}
	if !strings.Contains(msg.HTMLBody, wantEscaped) {
		t.Errorf("HTML body missing escaped token %q. Body: %s", wantEscaped, msg.HTMLBody)
	}
}
