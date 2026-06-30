//go:build integration

package mail

import (
	"net/url"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/emersion/go-imap/v2"
	"github.com/emersion/go-imap/v2/imapclient"
)

// TDD GREEN — Integration test (AC-7). Only runs with -tags=integration.
// Sends a real reset mail through Gmail SMTP, then verifies via IMAP against
// Stalwart that the mail landed in the inbox and contains the expected
// reset link.

func TestPasswordResetMail_RealGmailRoundtrip(t *testing.T) {
	if os.Getenv("GZ_GOOGLE_SMTP_HOST") == "" {
		t.Skip("GZ_GOOGLE_SMTP_HOST not set — integration test requires Gmail SMTP config")
	}
	if os.Getenv("GZ_IMAP_HOST") == "" {
		t.Skip("GZ_IMAP_HOST not set — integration test requires Stalwart IMAP config")
	}

	cfg := MailConfig{
		Host: os.Getenv("GZ_GOOGLE_SMTP_HOST"),
		Port: 587, // STARTTLS
		User: os.Getenv("GZ_GOOGLE_SMTP_USER"),
		Pass: os.Getenv("GZ_GOOGLE_SMTP_PASS"),
		From: os.Getenv("GZ_GOOGLE_SMTP_USER"),
	}
	token := "integration-token-" + time.Now().Format("20060102150405")
	username := "test-alice"
	msg := BuildResetMail("https://gregor20.henemm.com", username, token)
	recipient := os.Getenv("GZ_IMAP_USER") + "@henemm.com"

	if err := Send(cfg, recipient, msg); err != nil {
		t.Fatalf("Send failed: %v", err)
	}

	// Build the URL-encoded link we expect to find in the body. BuildResetMail
	// uses url.QueryEscape — match that exact form to defend against re-coding
	// surprises in test vs. production.
	expectedLink := "/reset-password?user=" + url.QueryEscape(username) + "&token=" + url.QueryEscape(token)
	if !waitForResetMailInInbox(t, expectedLink, 60*time.Second) {
		t.Fatalf("Reset mail with link %q not found in inbox after 60s", expectedLink)
	}
}

// AC-3: SendWithFallback liefert Mail via Stalwart wenn Primary (127.0.0.1:1) nicht erreichbar.
func TestSendWithFallback_AC3_DeliverViaStalwartFallback(t *testing.T) {
	if os.Getenv("GZ_IMAP_HOST") == "" {
		t.Skip("GZ_IMAP_HOST not set — integration test requires Stalwart config")
	}
	imap_user := os.Getenv("GZ_TEST_IMAP_USER")
	if imap_user == "" {
		imap_user = os.Getenv("GZ_IMAP_USER")
	}
	imap_pass := os.Getenv("GZ_TEST_IMAP_PASS")
	if imap_pass == "" {
		imap_pass = os.Getenv("GZ_IMAP_PASS")
	}
	if imap_user == "" || imap_pass == "" {
		t.Skip("GZ_IMAP_USER/PASS not set")
	}

	primaryCfg := MailConfig{Host: "127.0.0.1", Port: 1, User: "resend", Pass: "fake"}
	fallbackCfg := MailConfig{
		Host: os.Getenv("GZ_IMAP_HOST"), Port: 587,
		User: imap_user, Pass: imap_pass,
		From: "gregor_zwanzig@henemm.com",
	}
	token := "ac3-fallback-" + time.Now().Format("20060102150405")
	recipient := imap_user + "@henemm.com"
	msg := BuildResetMail("https://gregor20.henemm.com", "test-ac3", token)

	if err := SendWithFallback(primaryCfg, fallbackCfg, recipient, msg); err != nil {
		t.Fatalf("SendWithFallback returned error: %v", err)
	}
	if !waitForResetMailInInbox(t, token, 60*time.Second) {
		t.Fatalf("AC-3: Mail mit Token %q nicht im IMAP-Postfach nach 60s", token)
	}
}

// AC-4: Auth-Fehler (535) → sofortiger Abbruch, Fallback wird NICHT versucht.
// Test-Strategie: Primary = Stalwart mit falschem Passwort (→ echte 535-Antwort).
// Fallback = Stalwart mit korrekten Creds (würde Mail liefern wenn 535-Guard kaputt wäre).
// Nachweis: SendWithFallback gibt Fehler zurück → kein IMAP-Fund → 535-Guard hat gegriffen.
func TestSendWithFallback_AC4_NoFallbackOnAuthError(t *testing.T) {
	if os.Getenv("GZ_IMAP_HOST") == "" {
		t.Skip("GZ_IMAP_HOST not set — integration test requires Stalwart config")
	}
	imapUser := os.Getenv("GZ_TEST_IMAP_USER")
	if imapUser == "" {
		imapUser = os.Getenv("GZ_IMAP_USER")
	}
	imapPass := os.Getenv("GZ_TEST_IMAP_PASS")
	if imapPass == "" {
		imapPass = os.Getenv("GZ_IMAP_PASS")
	}
	if imapUser == "" || imapPass == "" {
		t.Skip("GZ_IMAP_USER/PASS not set")
	}

	imapHost := os.Getenv("GZ_IMAP_HOST")

	// Primary: echte Stalwart-Verbindung mit FALSCHEM Passwort → 535 Auth-Fehler
	primaryCfg := MailConfig{
		Host: imapHost, Port: 587,
		User: imapUser, Pass: "DELIBERATELY-WRONG-PASSWORD-AC4-TEST",
		From: "gregor_zwanzig@henemm.com",
	}
	// Fallback: korrekte Creds — würde Mail zustellen wenn 535-Guard nicht greift
	fallbackCfg := MailConfig{
		Host: imapHost, Port: 587,
		User: imapUser, Pass: imapPass,
		From: "gregor_zwanzig@henemm.com",
	}

	token := "ac4-no-fallback-" + time.Now().Format("20060102150405")
	recipient := imapUser + "@henemm.com"
	msg := BuildResetMail("https://gregor20.henemm.com", "test-ac4", token)

	err := SendWithFallback(primaryCfg, fallbackCfg, recipient, msg)

	// 535 Guard muss greifen: SendWithFallback gibt Fehler zurück
	if err == nil {
		t.Fatal("AC-4: SendWithFallback muss bei Auth-Fehler (535) einen Fehler zurückgeben")
	}
	// Fehler-String muss 535 enthalten (Auth-Fehler-Nachweis)
	if !strings.Contains(err.Error(), "535") {
		t.Fatalf("AC-4: Fehler-String muss '535' enthalten, got: %v", err)
	}
	// Wichtigste Assertion: kein Fallback-Mail zugestellt
	// Wenn Fallback trotzdem lief, würde die Mail im Postfach landen
	found := waitForResetMailInInbox(t, token, 15*time.Second)
	if found {
		t.Fatal("AC-4: Mail wurde trotz 535-Auth-Fehler zugestellt — 535-Guard hat NICHT gegriffen!")
	}
}

// waitForResetMailInInbox polls the Stalwart INBOX every 3s for UNSEEN messages
// containing the expected link substring. Once found, the message is marked
// \Seen + \Deleted and expunged to keep the inbox clean.
func waitForResetMailInInbox(t *testing.T, expectedSubstring string, timeout time.Duration) bool {
	t.Helper()
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if found := scanInboxOnce(t, expectedSubstring); found {
			return true
		}
		time.Sleep(3 * time.Second)
	}
	return false
}

func scanInboxOnce(t *testing.T, expectedSubstring string) bool {
	t.Helper()
	addr := os.Getenv("GZ_IMAP_HOST") + ":" + os.Getenv("GZ_IMAP_PORT")
	c, err := imapclient.DialTLS(addr, nil)
	if err != nil {
		t.Logf("IMAP dial: %v", err)
		return false
	}
	defer c.Close()

	if err := c.Login(os.Getenv("GZ_IMAP_USER"), os.Getenv("GZ_IMAP_PASS")).Wait(); err != nil {
		t.Logf("IMAP login: %v", err)
		return false
	}
	if _, err := c.Select("INBOX", nil).Wait(); err != nil {
		t.Logf("IMAP select: %v", err)
		return false
	}

	searchData, err := c.UIDSearch(&imap.SearchCriteria{
		NotFlag: []imap.Flag{imap.FlagSeen},
	}, nil).Wait()
	if err != nil {
		t.Logf("IMAP search: %v", err)
		return false
	}
	uids := searchData.AllUIDs()
	if len(uids) == 0 {
		return false
	}

	uidSet := imap.UIDSetNum(uids...)
	fetchOpts := &imap.FetchOptions{
		UID:         true,
		BodySection: []*imap.FetchItemBodySection{{Specifier: imap.PartSpecifierText}},
	}
	msgs, err := c.Fetch(uidSet, fetchOpts).Collect()
	if err != nil {
		t.Logf("IMAP fetch: %v", err)
		return false
	}

	for _, m := range msgs {
		for _, bs := range m.BodySection {
			if strings.Contains(string(bs.Bytes), expectedSubstring) {
				// Mark seen + deleted to keep the inbox clean across runs.
				oneUID := imap.UIDSetNum(m.UID)
				_, _ = c.Store(oneUID, &imap.StoreFlags{
					Op:    imap.StoreFlagsAdd,
					Flags: []imap.Flag{imap.FlagSeen, imap.FlagDeleted},
				}, nil).Collect()
				_, _ = c.Expunge().Collect()
				return true
			}
		}
	}
	return false
}
