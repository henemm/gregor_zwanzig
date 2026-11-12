package main

// Issue #2961 (GA4/GA10) — Warnungen beim Serverstart.
// Spec: docs/specs/modules/security_haertung_2026_11_go_anmeldung.md (AC-12).

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// AC-12: Fuer jede Kennung in GZ_ADMIN_USER_IDS / GZ_QUOTA_EXEMPT_USER_IDS
// ohne Konto erscheint beim Start eine Warnzeile; vorhandene Konten nicht.
func TestStartWarntVorPrivilegiertenKennungenOhneKonto(t *testing.T) {
	dir := t.TempDir()
	s := store.New(dir, "")
	if err := s.SaveUser(model.User{ID: "chef", CreatedAt: time.Now()}); err != nil {
		t.Fatal(err)
	}
	// Verwaister Ordner ohne user.json ist KEIN Konto.
	if err := os.MkdirAll(filepath.Join(dir, "users", "geist"), 0o770); err != nil {
		t.Fatal(err)
	}
	cfg := &config.Config{AdminUserIDs: "chef, fehlt1, geist", QuotaExemptUserIDs: "fehlt2,chef"}

	out := captureLog(t, func() { warnPrivilegedIDsWithoutAccount(s, cfg) })
	for _, id := range []string{"fehlt1", "geist", "fehlt2"} {
		if !strings.Contains(out, id) {
			t.Errorf("Warnung fuer %q fehlt im Log:\n%s", id, out)
		}
	}
	if strings.Contains(out, "chef") {
		t.Errorf("fuer das vorhandene Konto chef darf keine Warnung erscheinen:\n%s", out)
	}
}

// Seed: ein verwaister Ordner der Betreiberkennung blockiert die Erstanlage
// nicht (die Kennung kommt aus der Betreiber-Konfiguration).
func TestSeedLegtKontoInVorhandenemOrdnerOhneUserJSONAn(t *testing.T) {
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, "users", "admin", "trips"), 0o770); err != nil {
		t.Fatal(err)
	}
	s := store.New(dir, "admin")
	captureLog(t, func() { _ = seedAdminUser(s, &config.Config{UserID: "admin", AuthPass: "secret-pass"}) })
	if u, err := s.LoadUser("admin"); err != nil || u == nil {
		t.Fatalf("Seed-Konto erwartet, bekommen u=%v err=%v", u, err)
	}
}
