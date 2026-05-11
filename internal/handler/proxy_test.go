// Bug #200 — appendUserID darf user_id-Spoofing nicht erlauben.
//
// Spec: docs/specs/bugfix/bug_200_notify_user_id_spoofing.md
package handler

import (
	"net/url"
	"strings"
	"testing"
)

// AC-1: leere rawQuery + userID → nur user_id
func TestAppendUserID_EmptyQuery(t *testing.T) {
	got := appendUserID("", "alice")
	if got != "user_id=alice" {
		t.Errorf("got %q, want %q", got, "user_id=alice")
	}
}

// AC-2: bestehende Query ohne user_id bleibt erhalten + user_id wird ergänzt
func TestAppendUserID_PreservesOtherParams(t *testing.T) {
	got := appendUserID("foo=bar", "alice")
	values, err := url.ParseQuery(got)
	if err != nil {
		t.Fatalf("parse error: %v", err)
	}
	if values.Get("foo") != "bar" {
		t.Errorf("foo missing: %v", values)
	}
	if values.Get("user_id") != "alice" {
		t.Errorf("user_id missing or wrong: %v", values)
	}
}

// AC-3: client-side user_id wird ersetzt (Anti-Spoofing)
func TestAppendUserID_ReplacesSpoofedUserID(t *testing.T) {
	got := appendUserID("user_id=bob", "alice")
	values, err := url.ParseQuery(got)
	if err != nil {
		t.Fatalf("parse error: %v", err)
	}
	// Only ONE user_id, and it MUST be alice
	uids := values["user_id"]
	if len(uids) != 1 {
		t.Errorf("expected exactly 1 user_id, got %d: %v", len(uids), uids)
	}
	if values.Get("user_id") != "alice" {
		t.Errorf("user_id must be alice (authenticated), got %q", values.Get("user_id"))
	}
	if strings.Contains(got, "bob") {
		t.Errorf("result must NOT contain bob: %q", got)
	}
}

// AC-4: Mehrere gespoofte user_id werden alle ersetzt
func TestAppendUserID_ReplacesMultipleSpoofed(t *testing.T) {
	got := appendUserID("user_id=bob&other=x&user_id=eve", "alice")
	values, err := url.ParseQuery(got)
	if err != nil {
		t.Fatalf("parse error: %v", err)
	}
	if values.Get("other") != "x" {
		t.Errorf("other=x must survive: %v", values)
	}
	uids := values["user_id"]
	if len(uids) != 1 || uids[0] != "alice" {
		t.Errorf("expected single user_id=alice, got %v", uids)
	}
	if strings.Contains(got, "bob") || strings.Contains(got, "eve") {
		t.Errorf("spoofed values must be removed: %q", got)
	}
}

// AC-5: leerer userID → rawQuery unverändert
func TestAppendUserID_NoAuthLeavesQueryUnchanged(t *testing.T) {
	got := appendUserID("foo=bar", "")
	if got != "foo=bar" {
		t.Errorf("got %q, want %q (unchanged)", got, "foo=bar")
	}
}

// Edge: malformed query → drop, keep only authenticated user_id
func TestAppendUserID_MalformedQueryDroppedSafely(t *testing.T) {
	got := appendUserID("%ZZ-broken", "alice")
	values, err := url.ParseQuery(got)
	if err != nil {
		t.Fatalf("result must be parseable: %v", err)
	}
	if values.Get("user_id") != "alice" {
		t.Errorf("authenticated user_id must survive: %v", values)
	}
}
