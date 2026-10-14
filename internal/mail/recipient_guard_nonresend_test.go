package mail

import (
	"errors"
	"net"
	"sync/atomic"
	"testing"
	"time"
)

// TDD RED — Issue #1412 Scheibe S5: Go zieht den Empfängerschutz auf JEDEM
// Nicht-Resend-Postausgang nach (Lokalregel wie Python: nur @henemm.com,
// reservierte Test-Domains immer gesperrt, Test-Postfach-Fangnetz bewusst
// aus).
// SPEC: docs/specs/modules/fix_1412_s5_go_empfaengerschutz.md (AC-1..AC-6, AC-8..AC-11)
//
// Aufruf ausschließlich über bestehende Signaturen (recipientBlocked,
// SendWithFallback, ErrGuardBlocked) -- kein Netz außer einem lokalen
// TCP-Listener als zählendem SMTP-Sink (AC-6), kein Mock des Prüflings.
//
// Klassifikation: Block-Fälle (AC-1, AC-3, AC-6, AC-8..AC-11 Block) sind
// vor der Umsetzung ROT; AC-2/AC-5 sowie die Allow-Fälle sind PINNING
// (heute grün, dürfen durch die Umsetzung nicht kippen).

// nonResendHosts: die zwei Host-Klassen aus AC-1 (Stalwart und Loopback).
var nonResendHosts = []string{"mail.henemm.com", "127.0.0.1"}

func isGuardBlock(err error) bool { return errors.Is(err, ErrGuardBlocked) }

// AC-1: Fremdadresse auf Nicht-Resend-Host => ErrGuardBlocked.
func TestRecipientBlocked_NonResendForeignAddressBlocked(t *testing.T) {
	t.Setenv("GZ_DATA_DIR", t.TempDir())
	for _, host := range nonResendHosts {
		for _, to := range []string{"fremd@gmail.com", "andere.person@web.de"} {
			err := recipientBlocked(host, to)
			if !isGuardBlock(err) {
				t.Errorf("AC-1: host=%q to=%q muss ErrGuardBlocked liefern, war: %v", host, to, err)
			}
		}
	}
}

// AC-2 (PINNING): eigene Domain bleibt erlaubt -- Groß-/Kleinschreibung und
// abschließender Punkt ändern nichts.
func TestRecipientBlocked_NonResendOwnDomainAllowed(t *testing.T) {
	t.Setenv("GZ_DATA_DIR", t.TempDir())
	for _, host := range nonResendHosts {
		for _, to := range []string{"henning@henemm.com", "GREGOR-Test@HENEMM.COM", "henning@henemm.com."} {
			if err := recipientBlocked(host, to); err != nil {
				t.Errorf("AC-2: host=%q to=%q muss erlaubt sein, Fehler war: %v", host, to, err)
			}
		}
	}
}

// AC-3: reservierte Test-Domains werden auf Nicht-Resend-Hosts geblockt.
func TestRecipientBlocked_NonResendReservedDomainsBlocked(t *testing.T) {
	t.Setenv("GZ_DATA_DIR", t.TempDir())
	for _, host := range nonResendHosts {
		for _, to := range []string{
			"x@example.com", "x@sub.example.org", "x@foo.test", "x@localhost",
		} {
			err := recipientBlocked(host, to)
			if !isGuardBlock(err) {
				t.Errorf("AC-3: host=%q to=%q (reservierte Domain) muss ErrGuardBlocked liefern, war: %v", host, to, err)
			}
		}
	}
}

// AC-5 (PINNING): Test-Postfach auf lokalem Relay zustellbar -- das
// Fangnetz ist auf dem Nicht-Resend-Zweig bewusst aus.
func TestRecipientBlocked_NonResendTestMailboxStaysDeliverable(t *testing.T) {
	t.Setenv("GZ_DATA_DIR", t.TempDir())
	for _, host := range nonResendHosts {
		for _, to := range []string{
			"gregor-test@henemm.com", "gregor-test+abc@henemm.com", "gregor-test+zz9@henemm.com",
			"gregor-staging@henemm.com",
		} {
			if err := recipientBlocked(host, to); err != nil {
				t.Errorf("AC-5: host=%q to=%q muss zustellbar bleiben, Fehler war: %v", host, to, err)
			}
		}
	}
}

// AC-6: nach einem Empfängerschutz-Block wird KEIN zweiter Versand über den
// Ersatzweg versucht. Fallback-Host ist ein echter lokaler TCP-Listener, der
// jede Verbindung zählt (zählender SMTP-Sink, kein Mock des Prüflings).
func TestSendWithFallback_NonResendGuardBlockDoesNotTouchFallbackSink(t *testing.T) {
	t.Setenv("GZ_DATA_DIR", t.TempDir())
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("Sink-Listener nicht startbar: %v", err)
	}
	defer ln.Close()
	var conns atomic.Int32
	go func() {
		for {
			c, aerr := ln.Accept()
			if aerr != nil {
				return
			}
			conns.Add(1)
			c.Close()
		}
	}()

	primary := MailConfig{Host: "127.0.0.1", Port: 1, User: "u", Pass: "p"}
	fallback := MailConfig{
		Host: "127.0.0.1", Port: ln.Addr().(*net.TCPAddr).Port, User: "u", Pass: "p",
	}
	sendErr := SendWithFallback(primary, fallback, "fremd@gmail.com", resendTestMail())

	if !isGuardBlock(sendErr) {
		t.Errorf("AC-6: Fremdadresse auf Nicht-Resend-Primärweg muss ErrGuardBlocked liefern, war: %v", sendErr)
	}
	time.Sleep(200 * time.Millisecond) // Accept-Goroutine Zeit geben, eine späte Verbindung zu zählen
	if n := conns.Load(); n != 0 {
		t.Errorf("AC-6: Ersatzweg-Sink darf nach Block 0 Verbindungen sehen, zählte %d", n)
	}
}

// AC-8..AC-11 (Go-Seite): C3-20-Sollwerte direkt gegen recipientBlocked,
// zusätzlich zur geteilten Falltabelle. Resend-Zweig mit verifiziertem
// Profil henning@henemm.com (Allowlist), Stalwart-Zweig ohne Profil.
func TestRecipientBlocked_C320Sollwerte(t *testing.T) {
	t.Setenv("GZ_DATA_DIR", allowlistedDataDir(t, "henning@henemm.com"))
	const resendHost = "smtp.resend-fixture.test"
	cases := []struct {
		name          string
		to            string
		blockResend   bool
		blockStalwart bool
	}{
		{"A: Adresse plus Textrest hinter Komma", "henning@henemm.com, garbage", true, true},
		{"B: Adresse plus Textrest per Leerzeichen", "henning@henemm.com garbage", true, true},
		{"C: gequoteter Local-Part", `"x y"@henemm.com`, true, false},
		{"Z1: ungequoteter Anzeigename mit Komma", "Nachname, Vorname <henning@henemm.com>", true, true},
		{"Z2: gequoteter Anzeigename mit Komma", `"Nachname, Vorname" <henning@henemm.com>`, false, false},
	}
	for _, c := range cases {
		if got := isGuardBlock(recipientBlocked(resendHost, c.to)); got != c.blockResend {
			t.Errorf("%s: Resend-Host block=%v, erwartet %v (to=%q)", c.name, got, c.blockResend, c.to)
		}
		if got := isGuardBlock(recipientBlocked("mail.henemm.com", c.to)); got != c.blockStalwart {
			t.Errorf("%s: Stalwart-Host block=%v, erwartet %v (to=%q)", c.name, got, c.blockStalwart, c.to)
		}
	}
}
