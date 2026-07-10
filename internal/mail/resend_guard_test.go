package mail

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TDD RED — Issue #1122: Resend Default-Deny im Go-Sendepfad.
// Spec: docs/specs/modules/issue_1122_resend_default_deny.md
//
// Send() MUSS jeden Resend-Host VOR dem Netzwerk-Dial ablehnen, wenn
// (a) der Prozess unter `go test` läuft (testing.Testing()) — auch mit Token,
// (b) GZ_RESEND_ALLOWED nicht auf "1" steht.
// Kein Netz nötig: der Guard greift vor dem Dial, die Tests prüfen den Fehler.

func resendTestMail() Mail {
	return Mail{Subject: "guard", PlainBody: "guard", HTMLBody: "<p>guard</p>"}
}

// allowlistedDataDir registriert jede Adresse in addresses als mail_to eines
// eigenen Fixture-Nutzerprofils in einem isolierten t.TempDir() (Issue
// #1219) und setzt GZ_DATA_DIR per t.Setenv darauf (automatisch
// zurückgesetzt am Testende). Damit besteht recipientBlocked() die neue
// Allowlist-Prüfung für genau diese Adressen, ohne die ECHTEN data/users/
// anzufassen — nötig für Tests, die eigentlich resendBlocked() (#1122)
// prüfen wollen, nicht die Allowlist-Mitgliedschaft selbst.
func allowlistedDataDir(t *testing.T, addresses ...string) string {
	t.Helper()
	dataDir := t.TempDir()
	for i, addr := range addresses {
		userDir := filepath.Join(dataDir, "users", "fixture-"+string(rune('a'+i)))
		if err := os.MkdirAll(userDir, 0755); err != nil {
			t.Fatalf("allowlistedDataDir: Fixture-Setup fehlgeschlagen: %v", err)
		}
		data, err := json.Marshal(map[string]string{"mail_to": addr})
		if err != nil {
			t.Fatalf("allowlistedDataDir: JSON-Marshal fehlgeschlagen: %v", err)
		}
		if err := os.WriteFile(filepath.Join(userDir, "user.json"), data, 0644); err != nil {
			t.Fatalf("allowlistedDataDir: Fixture-Setup fehlgeschlagen: %v", err)
		}
	}
	return dataDir
}

// AC-4: Unter go test ist Resend gesperrt — auch OHNE gesetztes Token.
//
// Nachtrag Issue #1219: "user@example.com" wird per allowlistedDataDir als
// Fixture-Nutzerprofil registriert, damit recipientBlocked() (die neue
// Allowlist-Prüfung) NICHT zuerst greift und dieser Test weiterhin gezielt
// resendBlocked() (#1122) prüft — genau das ursprüngliche Testziel.
func TestSend_ResendHostBlockedUnderGoTest(t *testing.T) {
	t.Setenv("GZ_DATA_DIR", allowlistedDataDir(t, "user@example.com"))
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "user@example.com", resendTestMail())
	if err == nil {
		t.Fatal("AC-4: Send() mit Resend-Host muss unter go test einen Fehler liefern — Mail wäre über Resend gegangen!")
	}
	if !strings.Contains(err.Error(), "GZ_RESEND_ALLOWED") || !strings.Contains(err.Error(), "1122") {
		t.Errorf("AC-4: Guard-Fehler muss GZ_RESEND_ALLOWED und Issue #1122 nennen, war: %v", err)
	}
}

// AC-4 (Token-Leak): Auch MIT GZ_RESEND_ALLOWED=1 bleibt Resend unter go test gesperrt.
func TestSend_ResendHostBlockedEvenWithTokenUnderGoTest(t *testing.T) {
	t.Setenv("GZ_DATA_DIR", allowlistedDataDir(t, "user@example.com"))
	t.Setenv("GZ_RESEND_ALLOWED", "1")
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "user@example.com", resendTestMail())
	if err == nil {
		t.Fatal("AC-4: Ein in die Test-Umgebung geleaktes Token darf go test NICHT zum Resend-Versand befähigen")
	}
	if !strings.Contains(err.Error(), "GZ_RESEND_ALLOWED") {
		t.Errorf("AC-4: Guard-Fehler erwartet, war: %v", err)
	}
}

// Case-Insensitivity: SMTP.RESEND.COM ist derselbe Dienst.
func TestSend_ResendHostBlockedCaseInsensitive(t *testing.T) {
	t.Setenv("GZ_DATA_DIR", allowlistedDataDir(t, "user@example.com"))
	cfg := MailConfig{Host: "SMTP.RESEND.COM", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "user@example.com", resendTestMail())
	if err == nil || !strings.Contains(err.Error(), "GZ_RESEND_ALLOWED") {
		t.Errorf("Guard muss Host case-insensitive prüfen, Fehler war: %v", err)
	}
}

// AC-5: Nicht-Resend-Hosts werden vom Guard NICHT blockiert. 127.0.0.1:1 ist
// unerreichbar → es darf ein Dial-Fehler kommen, aber KEIN Guard-Fehler.
func TestSend_NonResendHostNotBlockedByGuard(t *testing.T) {
	cfg := MailConfig{Host: "127.0.0.1", Port: 1, User: "u", Pass: "p"}
	err := Send(cfg, "user@example.com", resendTestMail())
	if err == nil {
		t.Fatal("Test-Prämisse verletzt: 127.0.0.1:1 darf nicht erreichbar sein")
	}
	if strings.Contains(err.Error(), "GZ_RESEND_ALLOWED") {
		t.Errorf("AC-5: Guard darf Nicht-Resend-Hosts nicht blockieren, Fehler war: %v", err)
	}
}

// AC-5: SendWithFallback ist über Send() für BEIDE Configs abgedeckt — ein
// Resend-Fallback wird ebenso verweigert (kein Schlupfloch über den Fallback-Pfad).
func TestSendWithFallback_ResendFallbackAlsoBlocked(t *testing.T) {
	t.Setenv("GZ_DATA_DIR", allowlistedDataDir(t, "user@example.com"))
	primary := MailConfig{Host: "127.0.0.1", Port: 1, User: "u", Pass: "p"}
	fallback := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := SendWithFallback(primary, fallback, "user@example.com", resendTestMail())
	if err == nil {
		t.Fatal("SendWithFallback mit Resend-Fallback muss fehlschlagen — sonst leakt der Fallback-Pfad über Resend")
	}
	if !strings.Contains(err.Error(), "GZ_RESEND_ALLOWED") {
		t.Errorf("Fallback-Fehler muss den Resend-Guard nennen, war: %v", err)
	}
}
