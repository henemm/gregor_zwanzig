package store

// TDD RED — Issue #2154 Scheibe A, Artefakt 2 (Bestandsdaten-Migration, AC-10).
// Spec: docs/specs/modules/fix_2154_premium_sms_verknuepfungscode.md v1.0
//
// ABWEICHUNG von der Spec (Test Plan nennt internal/model/premium_sms_migration_test.go):
// die Migration laeuft ueber ListUserIDs/LoadUser/SaveUser und gehoert damit
// ins Paket store. model kann store nicht einbinden — internal/store/user.go:13
// bindet umgekehrt model ein, das waere ein Zyklus.
//
// Geforderte neue Signatur:
//   (*Store).MigrateClearPremiumSmsReplyAddresses() (int, error)  // Anzahl bereinigter Nutzer

import (
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

func TestMigrationClearsExistingReplyAddress(t *testing.T) {
	s := New(t.TempDir(), "default")

	learnedAt := time.Now().UTC().Add(-2 * time.Hour)
	betroffen := model.User{
		ID: "anna", Tier: "premium", Email: "anna@example.invalid",
		MailTo: "anna+briefing@example.invalid", TelegramChatID: "424242",
		PremiumSmsReplyTo: "4917000000007", PremiumSmsReplyAt: &learnedAt,
	}
	unbeteiligt := model.User{ID: "bert", Tier: "free", Email: "bert@example.invalid"}
	for _, u := range []model.User{betroffen, unbeteiligt} {
		if err := s.SaveUser(u); err != nil {
			t.Fatalf("SaveUser(%s): %v", u.ID, err)
		}
	}

	cleared, err := s.MigrateClearPremiumSmsReplyAddresses()
	if err != nil {
		t.Fatalf("AC-10: Migration fehlgeschlagen: %v", err)
	}
	if cleared != 1 {
		t.Errorf("AC-10: erwartet 1 bereinigten Nutzer, gemeldet wurden %d", cleared)
	}

	anna, err := s.LoadUser("anna")
	if err != nil || anna == nil {
		t.Fatalf("AC-10: anna nach der Migration nicht ladbar: %v (%v)", err, anna)
	}
	if anna.PremiumSmsReplyTo != "" || anna.PremiumSmsReplyAt != nil {
		t.Errorf("AC-10: die gelernte Rueckadresse MUSS verworfen sein, bekam to=%q at=%v — eine "+
			"moeglicherweise entfuehrte Nummer bliebe sonst gueltiger Bestaetigungspfad",
			anna.PremiumSmsReplyTo, anna.PremiumSmsReplyAt)
	}

	// Read-Modify-Write mit Merge, nicht Replace (CLAUDE.md "Daten-Schema-Reworks"):
	// eine Migration, die model.User{ID: id} schreibt, erfuellt die Bedingung oben
	// ebenfalls — und loescht dabei das halbe Profil.
	if anna.Email != betroffen.Email || anna.MailTo != betroffen.MailTo ||
		anna.Tier != betroffen.Tier || anna.TelegramChatID != betroffen.TelegramChatID {
		t.Errorf("AC-10: alle uebrigen Profilfelder MUESSEN erhalten bleiben.\nvorher:  %+v\nnachher: %+v",
			betroffen, *anna)
	}

	bert, err := s.LoadUser("bert")
	if err != nil || bert == nil {
		t.Fatalf("AC-10: bert nach der Migration nicht ladbar: %v (%v)", err, bert)
	}
	if bert.Email != unbeteiligt.Email || bert.Tier != unbeteiligt.Tier {
		t.Errorf("AC-10: ein Nutzer ohne Rueckadresse darf unveraendert bleiben.\nvorher:  %+v\nnachher: %+v",
			unbeteiligt, *bert)
	}
}
