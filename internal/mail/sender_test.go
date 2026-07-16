package mail

import (
	"mime"
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
// NOTE (Issue #1219 Adversary F001): IsTestUser() covers ONLY the name-
// substring heuristic. Since Issue #1013, Python's is_test_user_id()
// (src/app/config.py:30) ALSO excludes the fixed ID "tg-live-e2e" and any
// profile with the "is_test_user": true flag — IsTestUser() alone is no
// longer a full mirror of that function. The Resend-Allowlist-Loader
// (loadResendAllowlist/isResendAllowlistTestUser, sender.go) applies all
// three criteria for symmetry with Python; IsTestUser() itself stays
// name-heuristic-only so existing callers (e.g. handler/auth.go:224) are
// unaffected. If a prod-user registers with such a name, their reset mail
// goes through Gmail instead of Resend — acceptable risk, easy to avoid in
// setup. See spec Known Limitations.
func TestIsTestUser_Boundary(t *testing.T) {
	if !IsTestUser("contest") {
		t.Errorf("IsTestUser('contest') = false; expected true (known false positive — see spec)")
	}
	if !IsTestUser("tdd-prod-user") {
		t.Errorf("IsTestUser('tdd-prod-user') = false; expected true (known false positive — see spec)")
	}
}

// TestIsTestUser_TgLiveE2eStaysNameHeuristicOnly (Issue #1265 Fix-Loop 1,
// Adversary Runde-2-Ripple-Fund): die #1265-Konsolidierung auf
// model.IsTestUserID hätte IsTestUser("tg-live-e2e") stillschweigend von
// false auf true umschalten können — genau das würde das Passwort-Reset-/
// Verifikations-Mail-Routing in handler/auth.go (Zeilen 249, 660) für die
// Telegram-E2E-Fixture-ID ändern. Sperrt exakt das Vor-#1265-Verhalten
// (s. TestIsTestUser_Boundary-Docstring: "name-heuristic-only").
func TestIsTestUser_TgLiveE2eStaysNameHeuristicOnly(t *testing.T) {
	if IsTestUser("tg-live-e2e") {
		t.Error("IsTestUser('tg-live-e2e') = true; expected false — bewusst OHNE den " +
			"Fixed-Fixture-Sonderfall aus model.IsTestUserID (kein Ripple-Verhaltenswechsel " +
			"im auth.go-Mail-Routing, Issue #1265 Fix-Loop 1)")
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

// TDD RED — Issue #469: Subject-Header RFC-2047-Encoding.
// These tests fail to compile until encodeMailHeader exists in sender.go.

// TestEncodeMailHeader_ASCIIIdentity — AC-1.
// ASCII-only Subjects MÜSSEN bitidentisch zurückkommen (kein Encoded-Word-Wrapping,
// kein Overhead). Garantiert von Go stdlib mime.QEncoding.Encode.
func TestEncodeMailHeader_ASCIIIdentity(t *testing.T) {
	cases := []string{
		"Hello World",
		"Gregor 20 - Password Reset",
		"Re: [TICKET-123] Update",
		"",
	}
	for _, input := range cases {
		got := encodeMailHeader(input)
		if got != input {
			t.Errorf("encodeMailHeader(%q) = %q, want bitidentisch %q (ASCII-Identity)", input, got, input)
		}
	}
}

// TestEncodeMailHeader_EmDash — AC-2.
// Subject mit Em-Dash (U+2014) MUSS als RFC-2047-Encoded-Word zurückkommen
// mit utf-8 charset und Quoted-Printable-Sequenz =E2=80=94 für den Em-Dash.
func TestEncodeMailHeader_EmDash(t *testing.T) {
	input := "Gregor 20 — Dein Einmalcode"
	got := encodeMailHeader(input)
	// Go stdlib liefert lowercase "=?utf-8?q?..." — case-insensitive prüfen für Robustheit.
	lower := strings.ToLower(got)
	if !strings.HasPrefix(lower, "=?utf-8?q?") {
		t.Errorf("encodeMailHeader(%q) = %q, erwartet Präfix =?utf-8?q? (case-insensitive)", input, got)
	}
	if !strings.HasSuffix(got, "?=") {
		t.Errorf("encodeMailHeader(%q) = %q, erwartet Suffix ?=", input, got)
	}
	if !strings.Contains(got, "=E2=80=94") {
		t.Errorf("encodeMailHeader(%q) = %q, erwartet Em-Dash als Quoted-Printable =E2=80=94", input, got)
	}
}

// TestEncodeMailHeader_Umlaute — AC-3.
// Deutsche Umlaute MÜSSEN korrekt als UTF-8-Bytes in Quoted-Printable enkodiert sein,
// und die gesamte Ausgabe MUSS reines US-ASCII sein (kein Byte ≥ 0x80, RFC-5322 §2.2).
func TestEncodeMailHeader_Umlaute(t *testing.T) {
	input := "Gregor 20 — Passwortzurücksetzung"
	got := encodeMailHeader(input)
	if !strings.Contains(got, "=C3=BC") {
		t.Errorf("encodeMailHeader(%q) = %q, erwartet ü als Quoted-Printable =C3=BC", input, got)
	}
	for i, b := range []byte(got) {
		if b >= 0x80 {
			t.Fatalf("encodeMailHeader(%q) Byte[%d] = 0x%02x ≥ 0x80 — RFC-5322 §2.2 verletzt. Output: %q", input, i, b, got)
		}
	}
}

// TestEncodeMailHeader_Roundtrip — AC-4.
// Der RFC-2047-Decoder (mime.WordDecoder) MUSS aus der Encoder-Ausgabe den
// Original-Subject bitidentisch rekonstruieren — für ASCII wie für Non-ASCII.
func TestEncodeMailHeader_Roundtrip(t *testing.T) {
	cases := []string{
		"Hello World",
		"Gregor 20 — Dein Einmalcode",
		"Gregor 20 — Passwortzurücksetzung",
		"Café — résumé naïve",
		"Größe & Übersicht",
	}
	dec := &mime.WordDecoder{}
	for _, input := range cases {
		encoded := encodeMailHeader(input)
		decoded, err := dec.DecodeHeader(encoded)
		if err != nil {
			t.Errorf("DecodeHeader(%q) [encoded from %q]: %v", encoded, input, err)
			continue
		}
		if decoded != input {
			t.Errorf("Roundtrip-Mismatch: input=%q encoded=%q decoded=%q", input, encoded, decoded)
		}
	}
}

// TestEncodeMailHeader_LongSubjectFolding — AC-5.
// Bei einem >75-Zeichen Subject mit Non-ASCII darf der Encoder Header-Folding
// (mehrere Encoded-Word-Segmente) ausgeben; entscheidend ist der Roundtrip und
// dass die Ausgabe weiterhin reines US-ASCII bleibt. Folding-Guard für die Zukunft.
func TestEncodeMailHeader_LongSubjectFolding(t *testing.T) {
	input := "Gregor 20 — sehr langer Subject mit vielen Wörtern damit das Encoded-Word über die 75-Zeichen-Grenze hinaus geht und Header-Folding ausgelöst wird ä ö ü ß"
	if len(input) <= 75 {
		t.Fatalf("Test-Fixture zu kurz: %d Bytes, brauche >75 für Folding-Trigger", len(input))
	}
	encoded := encodeMailHeader(input)
	// Pure US-ASCII garantiert.
	for i, b := range []byte(encoded) {
		if b >= 0x80 {
			t.Fatalf("Long-Subject encoded Byte[%d] = 0x%02x ≥ 0x80. Output: %q", i, b, encoded)
		}
	}
	// Roundtrip auch nach möglichem Folding.
	dec := &mime.WordDecoder{}
	decoded, err := dec.DecodeHeader(encoded)
	if err != nil {
		t.Fatalf("DecodeHeader(%q): %v", encoded, err)
	}
	if decoded != input {
		t.Errorf("Long-Subject-Roundtrip: input=%q decoded=%q", input, decoded)
	}
}

// TestEncodeMailHeader_BuildersIntegration — AC-6.
// Die aktuellen Subjects aus BuildMagicLinkMail und BuildResetMail (beide mit Em-Dash)
// MÜSSEN nach encodeMailHeader (a) reines US-ASCII sein und (b) durch den RFC-2047-
// Decoder bitidentisch zum Original-Subject rekonstruierbar sein.
// Dies ist der Integrations-Test, der die zwei produktiven Subject-Quellen abdeckt.
func TestEncodeMailHeader_BuildersIntegration(t *testing.T) {
	subjects := []string{
		BuildMagicLinkMail("123456").Subject,
		BuildResetMail("https://example.com", "alice", "tok").Subject,
	}
	dec := &mime.WordDecoder{}
	for _, subject := range subjects {
		if subject == "" {
			t.Errorf("Builder lieferte leeren Subject — Test-Prämisse verletzt")
			continue
		}
		encoded := encodeMailHeader(subject)
		for i, b := range []byte(encoded) {
			if b >= 0x80 {
				t.Errorf("Builder-Subject %q encoded Byte[%d] = 0x%02x ≥ 0x80. Output: %q", subject, i, b, encoded)
				break
			}
		}
		decoded, err := dec.DecodeHeader(encoded)
		if err != nil {
			t.Errorf("DecodeHeader(%q) [Builder-Subject %q]: %v", encoded, subject, err)
			continue
		}
		if decoded != subject {
			t.Errorf("Builder-Roundtrip: subject=%q decoded=%q", subject, decoded)
		}
	}
}
