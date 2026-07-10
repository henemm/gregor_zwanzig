package mail

import (
	"strings"
	"testing"
)

// TDD GREEN — Issue #1147: dritte, empfängerseitige Resend-Guard-Linie.
// Spec: docs/specs/modules/issue_1147_resend_recipient_invariant.md (AC-5, AC-6)
//
// recipientBlocked() muss VOR resendBlocked() greifen, damit der Guard auch
// unter `go test` beobachtbar ist (resendBlocked blockiert dort JEDEN
// Resend-Host unbedingt — recipientBlocked muss also zuerst prüfen, um für
// gregor-test@/gregor-staging@ tatsächlich den #1147-Fehler statt des
// generischen #1122-Fehlers zu liefern). Kein Netz nötig: beide Guards
// greifen vor dem Dial, die Tests prüfen den Fehler direkt.

// AC-5: Resend-Host + gregor-test@ → Fehler mit "1147", kein Dial.
//
// Nachtrag Issue #1219 (AC-6): die Fehlermeldung darf die volle
// Empfängeradresse NICHT mehr im Klartext enthalten (Log-/Fehlertext-
// Maskierung) — die ursprüngliche Erwartung "Fehler muss das Test-Postfach
// nennen" ist damit bewusst durch die neue AC-6-Anforderung ersetzt.
func TestSend_ResendHostToGregorTestBlockedWith1147(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "gregor-test@henemm.com", resendTestMail())
	if err == nil {
		t.Fatal("AC-5: Send() mit Resend-Host + gregor-test@ muss einen Fehler liefern")
	}
	if !strings.Contains(err.Error(), "1147") {
		t.Errorf("AC-5: Fehler muss Issue #1147 nennen, war: %v", err)
	}
	if strings.Contains(err.Error(), "gregor-test@henemm.com") {
		t.Errorf("AC-6 (#1219): Fehler darf die volle Empfängeradresse NICHT im Klartext enthalten, war: %v", err)
	}
}

// AC-5/AC-6: Resend-Host + gregor-staging@ → Fehler mit "1147".
func TestSend_ResendHostToGregorStagingBlockedWith1147(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "gregor-staging@henemm.com", resendTestMail())
	if err == nil {
		t.Fatal("AC-5/6: Send() mit Resend-Host + gregor-staging@ muss einen Fehler liefern")
	}
	if !strings.Contains(err.Error(), "1147") {
		t.Errorf("AC-5/6: Fehler muss Issue #1147 nennen, war: %v", err)
	}
}

// AC-6: Host-Großschreibung — case-insensitiv erkannt.
func TestSend_HostUppercaseStillBlockedWith1147(t *testing.T) {
	cfg := MailConfig{Host: "SMTP.RESEND.COM", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "gregor-test@henemm.com", resendTestMail())
	if err == nil || !strings.Contains(err.Error(), "1147") {
		t.Errorf("AC-6: Host-Großschreibung muss trotzdem als Resend erkannt werden, Fehler war: %v", err)
	}
}

// AC-6: Adress-Großschreibung — case-insensitiv erkannt.
func TestSend_AddressUppercaseStillBlockedWith1147(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "GREGOR-TEST@HENEMM.COM", resendTestMail())
	if err == nil || !strings.Contains(err.Error(), "1147") {
		t.Errorf("AC-6: Adress-Großschreibung muss trotzdem erkannt werden, Fehler war: %v", err)
	}
}

// AC-6: Name-Form "Name <addr>" wird auf die reine Adresse reduziert.
func TestSend_NameFormAddressStillBlockedWith1147(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, `"Gregor Test" <gregor-test@henemm.com>`, resendTestMail())
	if err == nil || !strings.Contains(err.Error(), "1147") {
		t.Errorf("AC-6: Name-Form-Adresse muss trotzdem erkannt werden, Fehler war: %v", err)
	}
}

// AC-4/Regressionsschutz: Resend-Host + normaler Empfänger → NICHT der
// #1147-Guard. Unter go test greift stattdessen der bestehende
// resendBlocked (#1122) — dessen Fehlertext wird geprüft, nicht "1147".
//
// Nachtrag Issue #1219: "someone@example.com" wird per allowlistedDataDir
// als Fixture-Nutzerprofil registriert, damit die neue Allowlist-Prüfung
// selbst nicht greift und weiterhin gezielt resendBlocked() (#1122) geprüft
// wird — genau das ursprüngliche Testziel.
func TestSend_ResendHostNormalRecipientNot1147Guard(t *testing.T) {
	t.Setenv("GZ_DATA_DIR", allowlistedDataDir(t, "someone@example.com"))
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "someone@example.com", resendTestMail())
	if err == nil {
		t.Fatal("Send() mit Resend-Host muss unter go test einen Fehler liefern (#1122)")
	}
	if strings.Contains(err.Error(), "1147") {
		t.Errorf("Der #1147-Guard darf bei normalem Empfänger nicht greifen, Fehler war: %v", err)
	}
	if !strings.Contains(err.Error(), "GZ_RESEND_ALLOWED") {
		t.Errorf("Erwartet den bestehenden #1122-Fehler, war: %v", err)
	}
}

// Nicht-Resend-Host + gregor-test@ → kein 1147-Fehler (Dial-Fehler ist okay,
// da 127.0.0.1:1 unerreichbar ist).
func TestSend_NonResendHostToTestMailboxNot1147Guard(t *testing.T) {
	cfg := MailConfig{Host: "127.0.0.1", Port: 1, User: "u", Pass: "p"}
	err := Send(cfg, "gregor-test@henemm.com", resendTestMail())
	if err == nil {
		t.Fatal("Test-Prämisse verletzt: 127.0.0.1:1 darf nicht erreichbar sein")
	}
	if strings.Contains(err.Error(), "1147") {
		t.Errorf("Guard darf Nicht-Resend-Hosts nicht blockieren, Fehler war: %v", err)
	}
}

// F001 (Adversary Fix-Loop 1, Runde 2): Plus-adressierte Variante
// (gregor-test+foo@henemm.com) muss trotzdem als Test-Postfach erkannt
// werden — lokaler Teil muss vor dem Vergleich am ersten '+' gekappt werden.
func TestSend_PlusAddressedTestMailboxBlockedWith1147(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "gregor-test+foo@henemm.com", resendTestMail())
	if err == nil || !strings.Contains(err.Error(), "1147") {
		t.Errorf("F001: Plus-adressierte Variante muss trotzdem als Test-Postfach erkannt werden, Fehler war: %v", err)
	}
}

// F002a (Adversary Fix-Loop 1, Runde 2): Komma-getrennter to-String
// ("gregor-test@henemm.com, real@example.com") muss pro Teil geprüft werden.
func TestSend_CommaEmbeddedRecipientBlockedWith1147(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "gregor-test@henemm.com, real@example.com", resendTestMail())
	if err == nil || !strings.Contains(err.Error(), "1147") {
		t.Errorf("F002a: Komma-getrennter to-String muss trotzdem blockiert werden, Fehler war: %v", err)
	}
}

// F003a (Adversary Fix-Loop 2, Runde 2): Semikolon-getrennter to-String
// ("gregor-test@henemm.com; real@example.com") muss trotzdem blockiert
// werden — der Trenner-Split muss Semikolon UND Komma abdecken.
func TestSend_SemicolonEmbeddedRecipientBlockedWith1147(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "gregor-test@henemm.com; real@example.com", resendTestMail())
	if err == nil || !strings.Contains(err.Error(), "1147") {
		t.Errorf("F003a: Semikolon-getrennter to-String muss trotzdem blockiert werden, Fehler war: %v", err)
	}
}

// F003b: Semikolon-Split kombiniert mit Plus-Adressierung
// ("gregor-test+foo@henemm.com; real@example.com") muss ebenfalls blockiert
// werden.
func TestSend_SemicolonPlusAddressedRecipientBlockedWith1147(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "gregor-test+foo@henemm.com; real@example.com", resendTestMail())
	if err == nil || !strings.Contains(err.Error(), "1147") {
		t.Errorf("F003b: Semikolon+Plus-adressierter to-String muss trotzdem blockiert werden, Fehler war: %v", err)
	}
}

// F003c: Zwei nur durch Leerzeichen (kein Komma/Semikolon) getrennte
// Adressen in einem Fragment ("gregor-test@henemm.com real@example.com")
// müssen ebenfalls blockiert werden — scheitert mail.ParseAddress an einem
// Fragment, muss ein Whitespace-Roh-Split einspringen.
func TestSend_WhitespaceEmbeddedRecipientBlockedWith1147(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "gregor-test@henemm.com real@example.com", resendTestMail())
	if err == nil || !strings.Contains(err.Error(), "1147") {
		t.Errorf("F003c: Whitespace-getrennter to-String muss trotzdem blockiert werden, Fehler war: %v", err)
	}
}

// F003d (AC-4-Negativfall): zwei echte, semikolon-getrennte Adressen dürfen
// den #1147-Guard NICHT auslösen — der Trennzeichen-Fix darf keine
// False-Positives für normale Empfänger erzeugen. Unter go test greift
// stattdessen der bestehende resendBlocked (#1122).
//
// Nachtrag Issue #1219: beide Adressen werden per allowlistedDataDir als
// Fixture-Nutzerprofile registriert, damit die neue Allowlist-Prüfung selbst
// nicht greift und nur die Trennzeichen-Logik geprüft wird.
func TestSend_TwoRealRecipientsSemicolonSeparatedNot1147Guard(t *testing.T) {
	t.Setenv("GZ_DATA_DIR", allowlistedDataDir(t, "real-a@example.com", "real-b@example.com"))
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "real-a@example.com; real-b@example.com", resendTestMail())
	if err == nil {
		t.Fatal("Send() mit Resend-Host muss unter go test einen Fehler liefern (#1122)")
	}
	if strings.Contains(err.Error(), "1147") {
		t.Errorf("F003d: Der #1147-Guard darf bei zwei echten, semikolon-getrennten Empfängern nicht greifen, Fehler war: %v", err)
	}
}

// F004 (Adversary Fix-Loop 3, Runde 3, Go-Pin-Test): gequoteter
// Anzeigename mit eingebettetem Semikolon (`"Foo; Bar" <gregor-test@…>`)
// muss trotzdem blockiert werden. Go war von F004 nie betroffen —
// mail.ParseAddress parst RFC5322-konform und findet die Adresse trotz des
// Semikolons im Anzeigenamen. Dieser Test schreibt das bereits korrekte
// Verhalten fest, damit die Python/Go-Asymmetrie nie unbemerkt entsteht.
func TestSend_QuotedDisplayNameWithSemicolonBlockedWith1147(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, `"Foo; Bar" <gregor-test@henemm.com>`, resendTestMail())
	if err == nil || !strings.Contains(err.Error(), "1147") {
		t.Errorf("F004: gequoteter Anzeigename mit Semikolon muss trotzdem als Test-Postfach erkannt werden, Fehler war: %v", err)
	}
}

// F005 (Adversary Fix-Loop 4, Runde 4): Steuerzeichen (\r \n \v \f \x00) in
// einem Anzeigenamen dürfen den Guard nicht durch Parser-Verwirrung umgehen.
// Strukturelle Antwort: Steuerzeichen aus dem rohen `to`-String entfernen,
// DANACH den rohen (nicht zerlegten) String gegen die Test-Postfach-Literale
// scannen — immun gegen jede Zerlege-Umgehung.

// F005a: CRLF im Anzeigenamen — Guard muss trotzdem greifen.
func TestSend_CRLFInDisplayNameBlockedWith1147(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "\"Foo\r\nBar\" <gregor-test@henemm.com>", resendTestMail())
	if err == nil || !strings.Contains(err.Error(), "1147") {
		t.Errorf("F005a: CRLF im Anzeigenamen muss trotzdem als Test-Postfach erkannt werden, Fehler war: %v", err)
	}
}

// F005b: einzelnes \r im Anzeigenamen — Guard muss trotzdem greifen.
func TestSend_BareCRInDisplayNameBlockedWith1147(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "\"A\rB\" <gregor-staging@henemm.com>", resendTestMail())
	if err == nil || !strings.Contains(err.Error(), "1147") {
		t.Errorf("F005b: einzelnes \\r im Anzeigenamen muss trotzdem als Test-Postfach erkannt werden, Fehler war: %v", err)
	}
}

// F005c: Null-Byte im Anzeigenamen — Guard muss trotzdem greifen.
func TestSend_NullByteInDisplayNameBlockedWith1147(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "\"A\x00B\" <gregor-test@henemm.com>", resendTestMail())
	if err == nil || !strings.Contains(err.Error(), "1147") {
		t.Errorf("F005c: Null-Byte im Anzeigenamen muss trotzdem als Test-Postfach erkannt werden, Fehler war: %v", err)
	}
}

// F005d: Steuerzeichen-Anzeigename kombiniert mit Plus-Adressierung.
func TestSend_PlusAddressedControlCharDisplayNameBlockedWith1147(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "\"X\r\nY\" <gregor-test+abc@henemm.com>", resendTestMail())
	if err == nil || !strings.Contains(err.Error(), "1147") {
		t.Errorf("F005d: Steuerzeichen+Plus-adressierter Anzeigename muss trotzdem blockiert werden, Fehler war: %v", err)
	}
}

// F005e (AC-4-Negativfall 1): echter Plus-Tag-Empfänger ohne Steuerzeichen
// darf den #1147-Guard NICHT auslösen.
//
// Nachtrag Issue #1219: die BASIS-Adresse "real@example.com" (ohne Plus-Tag
// -- Allowlist-Einträge werden nicht plus-gekappt, der Empfänger-Query aber
// schon, siehe normalizedAddrForGuard) wird per allowlistedDataDir
// registriert, damit die neue Allowlist-Prüfung selbst nicht greift und nur
// die Plus-Tag-Normalisierung geprüft wird.
func TestSend_RealRecipientPlusTagNot1147Guard(t *testing.T) {
	t.Setenv("GZ_DATA_DIR", allowlistedDataDir(t, "real@example.com"))
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "real+tag@example.com", resendTestMail())
	if err != nil && strings.Contains(err.Error(), "1147") {
		t.Errorf("F005e: #1147-Guard darf bei echtem Plus-Tag-Empfänger nicht greifen, Fehler war: %v", err)
	}
}

// F005f (AC-4-Negativfall 2): Anzeigename mit CRLF, dessen Adresse KEIN
// Test-Postfach ist, darf den #1147-Guard NICHT auslösen — sonst würde ein
// legitimer Empfänger mit kaputtem Namen den eigenen Versand blockieren.
//
// Nachtrag Issue #1219: "real@example.com" wird per allowlistedDataDir
// registriert, damit die neue Allowlist-Prüfung selbst nicht greift und nur
// die Steuerzeichen-Behandlung geprüft wird.
func TestSend_ControlCharRealRecipientNot1147Guard(t *testing.T) {
	t.Setenv("GZ_DATA_DIR", allowlistedDataDir(t, "real@example.com"))
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	err := Send(cfg, "\"Weird\r\nName\" <real@example.com>", resendTestMail())
	if err != nil && strings.Contains(err.Error(), "1147") {
		t.Errorf("F005f: #1147-Guard darf bei echtem Empfänger mit Steuerzeichen-Anzeigenamen nicht greifen, Fehler war: %v", err)
	}
}

// AC-5: SendWithFallback — primary=Resend+gregor-test@ liefert einen
// #1147-Fehler ohne "535" im Text, daher versucht SendWithFallback
// automatisch die Fallback-Config. Der zurückkommende Fehler muss vom
// Fallback-Versuch stammen (beweist: der Guard-Error führte zum
// Fallback-Versuch, nicht zum sofortigen Abbruch).
func TestSendWithFallback_RecipientGuardTriggersFallbackAttempt(t *testing.T) {
	primary := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_x"}
	fallback := MailConfig{Host: "127.0.0.1", Port: 1, User: "u", Pass: "p"}
	err := SendWithFallback(primary, fallback, "gregor-test@henemm.com", resendTestMail())
	if err == nil {
		t.Fatal("SendWithFallback muss fehlschlagen (primary blockiert, fallback unerreichbar)")
	}
	if !strings.Contains(err.Error(), "fallback") {
		t.Errorf("Fehler muss den Fallback-Versuch erkennen lassen, war: %v", err)
	}
	if !strings.Contains(err.Error(), "1147") {
		t.Errorf("Fehler muss den primären #1147-Guard-Fehler enthalten, war: %v", err)
	}
}
