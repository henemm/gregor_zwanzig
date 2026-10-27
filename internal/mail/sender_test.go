package mail

import (
	"mime"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// TestIsTestUser prueft das Mail-Routing-Praedikat ueber das geladene Profil
// (Issue #2152, AC-10 — ersetzt die frueheren Tests TestIsTestUser /
// TestIsTestUser_Boundary / TestIsTestUser_TgLiveE2eStaysNameHeuristicOnly,
// die die "test"/"tdd"-Namens-Heuristik als akzeptierten False Positive
// festpinnten). Entscheidend ist NUR das Flag is_test_user oder die feste
// Fixture-ID tg-live-e2e:
//   - "test-alice"/"AliceTDD"/"contest"/"tdd-prod-user" ohne Flag sind KEINE
//     Testkonten mehr — das ist der Bug-Fix (Reset-Mail echter Nutzer mit
//     solchem Namen laeuft ueber Resend statt Gmail/Test-SMTP).
//   - "tg-live-e2e" ist jetzt AUCH im Mail-Pfad Testkonto: bewusste
//     Vereinheitlichung mit Scheduler/Store auf model.IsTestAccount (die
//     #1265-Fix-Loop-1-Sonderbehandlung "name-heuristic-only" entfaellt),
//     damit die Fixture nie Verifikations-/Reset-Mails ueber Resend ausloest.
func TestIsTestUser(t *testing.T) {
	cases := []struct {
		name string
		u    *model.User
		want bool
	}{
		{"test-alice ohne Flag", &model.User{ID: "test-alice"}, false},
		{"AliceTDD ohne Flag", &model.User{ID: "AliceTDD"}, false},
		{"contest ohne Flag", &model.User{ID: "contest"}, false},
		{"tdd-prod-user ohne Flag", &model.User{ID: "tdd-prod-user"}, false},
		{"default", &model.User{ID: "default"}, false},
		{"henning", &model.User{ID: "henning"}, false},
		{"leere ID", &model.User{ID: ""}, false},
		{"test-alice mit Flag", &model.User{ID: "test-alice", IsTestUser: true}, true},
		{"admin mit Flag", &model.User{ID: "admin", IsTestUser: true}, true},
		{"tg-live-e2e ohne Flag", &model.User{ID: "tg-live-e2e"}, true},
		{"TG-LIVE-E2E ohne Flag", &model.User{ID: "TG-LIVE-E2E"}, true},
	}
	for _, c := range cases {
		if got := IsTestUser(c.u); got != c.want {
			t.Errorf("IsTestUser(%s) = %v, want %v", c.name, got, c.want)
		}
	}
}

// ---------------------------------------------------------------------------
// TDD RED — Issue #2152, AC-6: Mail-Routing-Praedikat liest das geladene
// Profil (Flag), nicht den rohen Namen. Spec: docs/specs/modules/testkonto_profilfeld.md
//
// Erwartete GREEN-Signatur (entsteht in /50, der Compile-Fehler dieses Pakets
// ist das beabsichtigte RED):
//
//	func IsTestUser(u *model.User) bool   // = model.IsTestAccount(u)
//
// Aufrufer handler/auth.go:371,1225 und auth_oauth.go:352 laden das Profil
// vorher per store.LoadUser. Die frueheren Tests TestIsTestUser_Boundary /
// TestIsTestUser_TgLiveE2eStaysNameHeuristicOnly (String-Signatur, Heuristik)
// sind in GREEN durch TestIsTestUser oben ersetzt (AC-10).
//
// Luecke, dokumentiert fuer den Adversary: die AC-6-Zusicherung wirkt in
// handler/auth.go:371 (Weiche Resend/Gmail im Reset-Pfad). Dort gibt es keine
// Versand-Naht (nur sendVerificationMailFn fuer den Verifikationspfad), daher
// prueft dieser Test das Praedikat, nicht die Weiche.
// ---------------------------------------------------------------------------

// TestIsTestUser_ProfilfeldStattName_AC6 — "protester" ohne Flag laeuft ueber
// Resend (false); "mitarbeiter42" mit Flag ueber Test-SMTP (true).
func TestIsTestUser_ProfilfeldStattName_AC6(t *testing.T) {
	if IsTestUser(&model.User{ID: "protester"}) {
		t.Error("IsTestUser(protester ohne Flag) = true; expected false — " +
			"Reset-Mail eines echten Nutzers muss ueber Resend laufen (AC-6)")
	}
	if IsTestUser(&model.User{ID: "contest"}) {
		t.Error("IsTestUser(contest ohne Flag) = true; expected false — " +
			"der frueher akzeptierte False Positive entfaellt (Spec Known Limitations)")
	}
	if !IsTestUser(&model.User{ID: "mitarbeiter42", IsTestUser: true}) {
		t.Error("IsTestUser(mitarbeiter42 mit Flag) = false; expected true")
	}
	if IsTestUser(nil) {
		t.Error("IsTestUser(nil) = true; expected false (nil-sicher, kein Panic)")
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
