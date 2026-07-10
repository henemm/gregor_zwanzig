package mail

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TDD GREEN — Issue #1219: positive Empfänger-Allowlist für Resend-Versand.
// Spec: docs/specs/modules/fix_1219_resend_allowlist.md (AC-1..AC-7)
//
// Go-Pendant zu tests/tdd/test_resend_recipient_allowlist.py. Testet
// loadResendAllowlist()/recipientBlocked() direkt (package-intern, kein
// Export nötig) statt über Send() — das umgeht die testing.Testing()-
// Sonderbehandlung von resendBlocked() (die unter go test JEDEN
// Resend-Host unbedingt sperrt) und prüft die Allowlist-Entscheidung
// isoliert. Kein Netz nötig, kein echter Dial. Fixtures ausschließlich in
// t.TempDir() — die echten data/users/ werden nie angefasst.

// writeUserProfileFixture legt ein Fixture-user.json OHNE email_verified_at
// unter dataDir/users/<userID>/user.json an (unverifiziertes Profil).
func writeUserProfileFixture(t *testing.T, dataDir, userID, mailTo string) {
	t.Helper()
	userDir := filepath.Join(dataDir, "users", userID)
	if err := os.MkdirAll(userDir, 0755); err != nil {
		t.Fatalf("writeUserProfileFixture: %v", err)
	}
	data, err := json.Marshal(map[string]string{"mail_to": mailTo})
	if err != nil {
		t.Fatalf("writeUserProfileFixture: %v", err)
	}
	if err := os.WriteFile(filepath.Join(userDir, "user.json"), data, 0644); err != nil {
		t.Fatalf("writeUserProfileFixture: %v", err)
	}
}

// writeVerifiedUserProfileFixture legt ein Fixture-user.json MIT gesetztem
// email_verified_at an (Issue #1219 Scheibe 1 — verifiziertes Profil).
func writeVerifiedUserProfileFixture(t *testing.T, dataDir, userID, mailTo string) {
	t.Helper()
	userDir := filepath.Join(dataDir, "users", userID)
	if err := os.MkdirAll(userDir, 0755); err != nil {
		t.Fatalf("writeVerifiedUserProfileFixture: %v", err)
	}
	data, err := json.Marshal(map[string]string{
		"mail_to":           mailTo,
		"email_verified_at": "2026-07-10T12:00:00Z",
	})
	if err != nil {
		t.Fatalf("writeVerifiedUserProfileFixture: %v", err)
	}
	if err := os.WriteFile(filepath.Join(userDir, "user.json"), data, 0644); err != nil {
		t.Fatalf("writeVerifiedUserProfileFixture: %v", err)
	}
}

// AC-1: Fremdadresse (kein Nutzerprofil) wird über Resend blockiert.
func TestRecipientBlocked_UnknownAddressBlocked(t *testing.T) {
	dataDir := t.TempDir() // isoliert, KEIN Fixture-Profil
	t.Setenv("GZ_DATA_DIR", dataDir)

	err := recipientBlocked("smtp.resend.com", "unbekannt@example.com")
	if err == nil {
		t.Fatal("AC-1: recipientBlocked() muss eine unbekannte Adresse über Resend blockieren")
	}
	if !strings.Contains(err.Error(), "1219") {
		t.Errorf("AC-1: Fehler muss Issue #1219 nennen, war: %v", err)
	}
}

// AC-2 (Issue #1219 Scheibe 1): echter mail_to eines VERIFIZIERTEN
// Nutzerprofils → erlaubt. Eignungskriterium ist email_verified_at, nicht
// mehr die Namens-Heuristik.
func TestLoadResendAllowlist_ContainsRealUserMailTo(t *testing.T) {
	dataDir := t.TempDir()
	writeVerifiedUserProfileFixture(t, dataDir, "henning", "henning@henemm.com")

	allowlist := loadResendAllowlist(dataDir)
	if !allowlist["henning@henemm.com"] {
		t.Errorf("AC-2: Allowlist muss henning@henemm.com enthalten, war: %v", allowlist)
	}
}

// AC-1 (Issue #1219 Scheibe 1): ein UNVERIFIZIERTES Profil mit neutralem
// Namen (kein "test"/"tdd") wird trotzdem ausgeschlossen — der ursprüngliche
// Bug-Fall (e2e-758@example.com), hier symmetrisch mit einer nicht
// reservierten Domain.
func TestLoadResendAllowlist_ExcludesUnverifiedNeutralProfile(t *testing.T) {
	dataDir := t.TempDir()
	writeUserProfileFixture(t, dataDir, "e2e-758", "e2e-758@gmail.com")

	allowlist := loadResendAllowlist(dataDir)
	if allowlist["e2e-758@gmail.com"] {
		t.Errorf("AC-1: unverifiziertes Profil darf NICHT in der Allowlist landen, war: %v", allowlist)
	}
}

// AC-2 (voller Guard-Pfad): recipientBlocked() lässt die registrierte,
// verifizierte Adresse durch (kein Fehler).
func TestRecipientBlocked_RealUserMailToAllowed(t *testing.T) {
	dataDir := t.TempDir()
	writeVerifiedUserProfileFixture(t, dataDir, "henning", "henning@henemm.com")
	t.Setenv("GZ_DATA_DIR", dataDir)

	err := recipientBlocked("smtp.resend.com", "henning@henemm.com")
	if err != nil {
		t.Errorf("AC-2: recipientBlocked() darf einen echten, verifizierten Nutzer nicht blockieren, Fehler war: %v", err)
	}
}

// AC-3: Adresse eines Test-Nutzerprofils bleibt blockiert, obwohl mail_to
// formal gesetzt ist.
func TestLoadResendAllowlist_ExcludesTestUser(t *testing.T) {
	dataDir := t.TempDir()
	writeUserProfileFixture(t, dataDir, "tdd-1219-fixture", "tdd-1219-fixture@example.com")

	allowlist := loadResendAllowlist(dataDir)
	if allowlist["tdd-1219-fixture@example.com"] {
		t.Errorf("AC-3: Allowlist darf Test-User-Profile nicht enthalten, war: %v", allowlist)
	}
}

func TestRecipientBlocked_TestUserMailToBlocked(t *testing.T) {
	dataDir := t.TempDir()
	writeUserProfileFixture(t, dataDir, "tdd-1219-fixture", "tdd-1219-fixture@example.com")
	t.Setenv("GZ_DATA_DIR", dataDir)

	err := recipientBlocked("smtp.resend.com", "tdd-1219-fixture@example.com")
	if err == nil {
		t.Fatal("AC-3: recipientBlocked() muss die Adresse eines Test-Nutzerprofils blockieren")
	}
	if !strings.Contains(err.Error(), "1219") {
		t.Errorf("AC-3: Fehler muss Issue #1219 nennen, war: %v", err)
	}
}

// AC-4: Stalwart-Host bleibt unberührt — der Allowlist-Guard greift nur bei
// Resend-Hosts.
func TestRecipientBlocked_StalwartHostGuardInactive(t *testing.T) {
	dataDir := t.TempDir() // isoliert, KEIN Fixture-Profil
	t.Setenv("GZ_DATA_DIR", dataDir)

	err := recipientBlocked("mail.henemm.com", "unbekannt@example.com")
	if err != nil {
		t.Errorf("AC-4: recipientBlocked() darf bei Stalwart-Host nicht greifen, Fehler war: %v", err)
	}
}

// AC-5: Whitespace-/Casing-Normalisierung zwischen Allowlist-Eintrag und
// geprüftem Empfänger — Symmetrie zu Python (_normalize_addr_for_guard).
func TestLoadResendAllowlist_NormalizesStoredValue(t *testing.T) {
	dataDir := t.TempDir()
	writeVerifiedUserProfileFixture(t, dataDir, "henning", " Henning@HENEMM.com ")

	allowlist := loadResendAllowlist(dataDir)
	if !allowlist["henning@henemm.com"] {
		t.Errorf("AC-5a: Allowlist muss den normalisierten Eintrag henning@henemm.com enthalten, war: %v", allowlist)
	}
}

func TestRecipientBlocked_NormalizedRecipientMatchesCleanAllowlistEntry(t *testing.T) {
	dataDir := t.TempDir()
	writeVerifiedUserProfileFixture(t, dataDir, "henning", "henning@henemm.com")
	t.Setenv("GZ_DATA_DIR", dataDir)

	err := recipientBlocked("smtp.resend.com", " Henning@HENEMM.com ")
	if err != nil {
		t.Errorf("AC-5b: ein abweichend geschriebener Empfänger muss trotzdem als erlaubt erkannt werden, Fehler war: %v", err)
	}
}

// AC-6: Blockade wird geloggt/fehlermeldet, ohne die volle Empfängeradresse
// im Klartext preiszugeben.
func TestRecipientBlocked_ErrorDoesNotLeakRawAddress(t *testing.T) {
	dataDir := t.TempDir()
	t.Setenv("GZ_DATA_DIR", dataDir)

	rawAddress := "geheime-testadresse@example.com"
	err := recipientBlocked("smtp.resend.com", rawAddress)
	if err == nil {
		t.Fatal("AC-6: recipientBlocked() muss die unbekannte Adresse blockieren")
	}
	if strings.Contains(err.Error(), rawAddress) {
		t.Errorf("AC-6: Fehlermeldung darf die volle Empfängeradresse nicht im Klartext enthalten, war: %v", err)
	}
}

// AC-7: die abgelöste 2-Adressen-Denylist bleibt über die Allowlist blockiert.
func TestRecipientBlocked_LegacyDenylistAddressesStillBlocked(t *testing.T) {
	dataDir := t.TempDir() // isoliert, KEIN Fixture-Profil
	t.Setenv("GZ_DATA_DIR", dataDir)

	for _, addr := range []string{"gregor-test@henemm.com", "gregor-staging@henemm.com"} {
		err := recipientBlocked("smtp.resend.com", addr)
		if err == nil {
			t.Errorf("AC-7: %q muss weiterhin blockiert werden (Regressionsschutz für die abgelöste Denylist)", addr)
		}
	}
}

// Fail-soft: ein fehlendes data_dir/users-Verzeichnis liefert eine leere
// Allowlist statt eines Crashs.
func TestLoadResendAllowlist_MissingUsersDirIsFailSoft(t *testing.T) {
	dataDir := filepath.Join(t.TempDir(), "does-not-exist")

	allowlist := loadResendAllowlist(dataDir)
	if len(allowlist) != 0 {
		t.Errorf("fehlendes users-Verzeichnis muss eine leere Allowlist liefern, war: %v", allowlist)
	}
}

// writeUserProfileFixtureFull legt ein Fixture-user.json mit mail_to UND
// optionalem is_test_user-Flag an (Issue #1219 Adversary F001 — Symmetrie
// zu Python is_test_user_id(), config.py:30-50).
func writeUserProfileFixtureFull(t *testing.T, dataDir, userID, mailTo string, isTestUser bool) {
	t.Helper()
	userDir := filepath.Join(dataDir, "users", userID)
	if err := os.MkdirAll(userDir, 0755); err != nil {
		t.Fatalf("writeUserProfileFixtureFull: %v", err)
	}
	profile := map[string]any{"mail_to": mailTo}
	if isTestUser {
		profile["is_test_user"] = true
	}
	data, err := json.Marshal(profile)
	if err != nil {
		t.Fatalf("writeUserProfileFixtureFull: %v", err)
	}
	if err := os.WriteFile(filepath.Join(userDir, "user.json"), data, 0644); err != nil {
		t.Fatalf("writeUserProfileFixtureFull: %v", err)
	}
}

// F001 (Adversary Runde 1, Issue #1219 — CRITICAL): ein NEUTRAL benanntes
// Profil (kein "test"/"tdd" im Namen) mit explizitem is_test_user:true-Flag
// muss trotzdem von der Allowlist ausgeschlossen werden — Symmetrie zu
// Python is_test_user_id() (config.py:30-50, Issue #1013), das dieses Flag
// bereits prüft. Vor dem F001-Fix war dieser Test ROT, weil IsTestUser()
// (reine Namens-Heuristik) das Profil-Flag nicht kannte.
func TestLoadResendAllowlist_ExcludesNeutralNamedProfileWithTestUserFlag(t *testing.T) {
	dataDir := t.TempDir()
	writeUserProfileFixtureFull(t, dataDir, "neutral-profile-name", "neutral@example.com", true)

	allowlist := loadResendAllowlist(dataDir)
	if allowlist["neutral@example.com"] {
		t.Errorf("F001: Allowlist darf ein Profil mit is_test_user:true NICHT enthalten, selbst bei neutralem Namen, war: %v", allowlist)
	}
}

// F001b (Adversary Runde 1, Issue #1219 — CRITICAL): die feste Fixture-ID
// "tg-live-e2e" muss ausgeschlossen werden — Symmetrie zu Python
// is_test_user_id() (user_id == "tg-live-e2e"). Vor dem F001-Fix war dieser
// Test ROT, weil IsTestUser("tg-live-e2e") false liefert (kein "test"/"tdd"-
// Substring).
func TestLoadResendAllowlist_ExcludesTgLiveE2eFixtureID(t *testing.T) {
	dataDir := t.TempDir()
	writeUserProfileFixture(t, dataDir, "tg-live-e2e", "tg-live-e2e@example.com")

	allowlist := loadResendAllowlist(dataDir)
	if allowlist["tg-live-e2e@example.com"] {
		t.Errorf("F001b: Allowlist darf die Fixture-ID tg-live-e2e NICHT enthalten, war: %v", allowlist)
	}
}
