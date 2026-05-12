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
