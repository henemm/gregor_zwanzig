package store

// Issue #2624 (Adversary F001): jeder Schreib-Einstiegspunkt muss das
// Nutzerverzeichnis SELBST mit 0770 anlegen -- im echten Registrierungspfad
// laeuft SaveUser VOR ProvisionUserDirs. Je Subtest: frischer, leerer
// Datenbaum, genau EIN Schreibaufruf, Umask 0077; danach Modus aller unter
// users/ entstandenen Verzeichnisse (0770) und Dateien (0660).

import (
	"path/filepath"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

func TestDateimodi_JederEinstiegspunktLegtNutzerverzeichnisSelbstAn(t *testing.T) {
	const uid = "erin"
	exp := time.Now().Add(time.Hour)
	faelle := []struct {
		name      string
		schreiben func(s *Store) error
	}{
		{"SaveUser", func(s *Store) error { return s.SaveUser(model.User{ID: uid}) }},
		{"SaveResetToken", func(s *Store) error {
			return s.SaveResetToken(uid, model.PasswordResetToken{TokenHash: "h", ExpiresAt: exp})
		}},
		{"SaveLinkCode", func(s *Store) error {
			return s.SaveLinkCode(uid, model.PremiumSmsLinkCode{CodeHash: "h", CreatedAt: time.Now()})
		}},
		{"SaveVerificationToken", func(s *Store) error {
			return s.SaveVerificationToken(uid, model.EmailVerificationToken{TokenHash: "h", ExpiresAt: exp})
		}},
		{"SaveSmsVerification", func(s *Store) error {
			return s.SaveSmsVerification(uid, model.SmsVerificationCode{CodeHash: "h", ExpiresAt: exp, Number: "+4915100000000"})
		}},
		{"SaveTrip", func(s *Store) error { return s.SaveTrip(&model.Trip{ID: "t1", Name: "T"}) }},
		{"SaveLocation", func(s *Store) error { return s.SaveLocation(model.Location{ID: "l1", Name: "L"}) }},
		{"SaveGroup", func(s *Store) error { return s.SaveGroup(model.Group{ID: "g1", Name: "G"}) }},
		{"SaveMetricPresets", func(s *Store) error {
			return s.SaveMetricPresets([]model.MetricPreset{{ID: "m1", Name: "M"}})
		}},
		{"SaveComparePreset", func(s *Store) error {
			return s.SaveComparePreset(model.ComparePreset{ID: "c1", Name: "C", UserID: uid})
		}},
		{"SaveBriefing", func(s *Store) error {
			return s.SaveBriefing(&model.BriefingSubscription{ID: "b1", Kind: "route"})
		}},
		{"AddSession", func(s *Store) error { return s.AddSession(uid, "sess-1") }},
		{"LockBriefing", func(s *Store) error { s.LockBriefing("b1")(); return nil }},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			setzeUmask077(t)
			root := filepath.Join(t.TempDir(), "data")
			s := New(root, uid)
			if err := f.schreiben(s); err != nil {
				t.Fatalf("%s: %v", f.name, err)
			}
			dirs, files := pruefeModi(t, filepath.Join(root, "users"))
			// users/ + users/<uid>/ mindestens, und die geschriebene Datei.
			if dirs < 2 || files < 1 {
				t.Fatalf("zu wenig entstanden (dirs=%d files=%d) -- Test waere vakuum", dirs, files)
			}
		})
	}
}
