package mail

import (
	"strings"
	"testing"
)

// TDD RED — Issue #1412 Scheibe S1: ein Guard-Block muss SendWithFallback
// von einem zweiten Sendeversuch abhalten (AC-3); ein echter Netzwerkfehler
// muss weiterhin auf den Ersatzweg ausweichen (AC-4).
// SPEC: docs/specs/modules/fix_1412_s1_guard_am_echten_postausgang.md
//
// AC-3-Nachweisform (bewusste Wahl statt Test-Seam um dialAndSend, siehe
// Spec-Nachweisplan "Go (AC-3)", Alternative-Absatz): SendWithFallback
// erkennt einen Guard-Fehler heute NICHT als solchen — jeder Fehler ohne
// "535" im Text gilt als vorübergehend und löst einen zweiten Sendeversuch
// über fallbackCfg aus (sender.go:534-537). Ein Guard-Block liefert nie
// "535" im Text → SendWithFallback versucht IMMER den Fallback, dessen
// (unerreichbarer) Fehler dann in die zurückgegebene Meldung eingewoben
// wird ("primary: %w; fallback: %v", sender.go:543). Genau dieses Einweben
// ist der beobachtbare Nachweis: nach dem Fix darf ein Guard-Fehler NICHT
// mehr zu einem zweiten Versuch führen — die Fehlermeldung darf dann
// keinen Fallback-Anteil mehr tragen.
//
// Begründung gegen den Seam: net/smtp lässt sich nicht patchen, aber ein
// austauschbares Dial-Handle wäre zusätzliche Produktivcode-Fläche in einem
// Sicherheitspfad — in der RED-Phase ist Produktivcode verboten. Der
// Fehlertext-Nachweis ist ehrlich (er beobachtet echtes
// SendWithFallback-Verhalten, kein Mock) und braucht keine neue
// Abstraktion — deshalb dem Seam vorgezogen (weniger Produktivcode-Fläche).
//
// Ergänzt (nicht ersetzt) durch die Inversion von
// recipient_guard_test.go:282-295 (dort: Fangnetz-Fall
// gregor-test@henemm.com, rawContainsTestMailbox; hier: Allowlist-Fall mit
// einer realistisch aussehenden, aber unverifizierten Adresse — deckt den
// ZWEITEN recipientBlocked-Rückgabepfad ab, sender.go:361-364).
func TestSendWithFallback_AllowlistGuardBlocksWithoutFallbackAttempt(t *testing.T) {
	t.Setenv("GZ_DATA_DIR", t.TempDir()) // isoliert -- keine echten data/users/ anfassen, Allowlist bleibt leer
	primary := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	fallback := MailConfig{Host: "127.0.0.1", Port: 2, User: "u", Pass: "p"}

	err := SendWithFallback(primary, fallback, "unverified-user@gmail.com", resendTestMail())
	if err == nil {
		t.Fatal("AC-3: primärer Empfänger-Guard-Block muss einen Fehler liefern")
	}
	if !strings.Contains(err.Error(), "1147") {
		t.Errorf("AC-3: Fehler muss den primären Allowlist-Guard erkennen lassen, war: %v", err)
	}
	if strings.Contains(err.Error(), "fallback") {
		t.Errorf(
			"AC-3: ein Guard-Block darf KEINEN zweiten Sendeversuch über den "+
				"Ersatzweg auslösen — die Fehlermeldung enthält aber einen "+
				"Fallback-Anteil (Beweis für einen zweiten Versuch), war: %v", err)
	}
}

// AC-4: echter Netzwerkfehler (kein Guard-Grund) auf BEIDEN Wegen — der
// Ersatzweg muss weiterhin versucht werden, das darf der Fix nicht
// verlieren. Deterministisch über unerreichbare lokale Adressen, kein
// echtes Netz nötig (Vorbild: die 127.0.0.1:1-Tests in
// resend_guard_test.go/recipient_guard_test.go). Non-Resend-Hosts → weder
// recipientBlocked noch resendBlocked greifen, der Fehler kommt
// ausschließlich vom Dial — genau die Konstellation, die ein zu weit
// gefasster Guard-Typ-Check (AC-3-Fix) fälschlich als Guard-Fehler
// einstufen und dadurch den Fallback-Versuch unterdrücken könnte.
func TestSendWithFallback_GenuineNetworkErrorStillTriesFallback(t *testing.T) {
	primary := MailConfig{Host: "127.0.0.1", Port: 1, User: "u", Pass: "p"}
	fallback := MailConfig{Host: "127.0.0.1", Port: 2, User: "u", Pass: "p"}

	err := SendWithFallback(primary, fallback, "someone@henemm.com", resendTestMail())
	if err == nil {
		t.Fatal("AC-4: beide Hosts sind unerreichbar -- SendWithFallback muss fehlschlagen")
	}
	if strings.Contains(err.Error(), "1147") || strings.Contains(err.Error(), "GZ_RESEND_ALLOWED") {
		t.Fatalf("Test-Prämisse verletzt: Fehler darf kein Guard-Fehler sein, war: %v", err)
	}
	if !strings.Contains(err.Error(), "primary") || !strings.Contains(err.Error(), "fallback") {
		t.Errorf(
			"AC-4: Fehlermeldung muss belegen, dass BEIDE Versuche tatsächlich "+
				"liefen (primär UND Ersatzweg), war: %v", err)
	}
}
