package store

// Issue #2961 Welle 2, Gegenpruefung F001/F002/F004 (ADR-0116).

import (
	"sync"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

func neuerStoreMitKonten(t *testing.T, ids ...string) *Store {
	t.Helper()
	s := New(t.TempDir(), "default")
	for _, id := range ids {
		if err := s.SaveUser(model.User{ID: id, Tier: "premium"}); err != nil {
			t.Fatalf("SaveUser(%s): %v", id, err)
		}
	}
	return s
}

func rueckadresse(t *testing.T, s *Store, id string) string {
	t.Helper()
	u, err := s.LoadUser(id)
	if err != nil || u == nil {
		t.Fatalf("LoadUser(%s): %v", id, err)
	}
	return u.PremiumSmsReplyTo
}

// F001: zwei gleichzeitige Lernvorgaenge derselben Nummer fuer zwei Konten
// hinterlassen die Nummer bei genau einem Konto (mit -race laufen lassen).
func TestLearnPremiumSmsReplyToGleichzeitigGenauEinInhaber(t *testing.T) {
	for runde := 0; runde < 30; runde++ {
		s := neuerStoreMitKonten(t, "anna", "bert")
		var wg sync.WaitGroup
		for _, id := range []string{"anna", "bert"} {
			wg.Add(1)
			go func(id string) {
				defer wg.Done()
				if err := s.LearnPremiumSmsReplyTo(id, "4917000000081", time.Now()); err != nil {
					t.Errorf("Learn(%s): %v", id, err)
				}
			}(id)
		}
		wg.Wait()
		inhaber := 0
		for _, id := range []string{"anna", "bert"} {
			if rueckadresse(t, s, id) != "" {
				inhaber++
			}
		}
		if inhaber != 1 {
			t.Fatalf("Runde %d: %d Konten tragen die Nummer, erwartet genau 1", runde, inhaber)
		}
	}
}

// F002: eine veraltete Kopie (vor dem Lernen bzw. Trennen geladen) stellt beim
// Speichern weder eine entfernte noch eine an ein anderes Konto gewanderte
// Rueckadresse wieder her.
func TestSaveUserVeralteteKopieStelltRueckadresseNichtWiederHer(t *testing.T) {
	s := neuerStoreMitKonten(t, "anna", "bert")
	if err := s.LearnPremiumSmsReplyTo("anna", "4917000000082", time.Now()); err != nil {
		t.Fatal(err)
	}
	alt, _ := s.LoadUser("anna")

	// Die Nummer wandert zu bert; danach speichert ein veralteter Schreiber anna.
	if err := s.LearnPremiumSmsReplyTo("bert", "+49 170 000 000 82", time.Now()); err != nil {
		t.Fatal(err)
	}
	alt.DisplayName = "Anna"
	if err := s.SaveUser(*alt); err != nil {
		t.Fatal(err)
	}
	if got := rueckadresse(t, s, "anna"); got != "" {
		t.Errorf("an bert gewanderte Nummer bei anna wiederhergestellt: %q", got)
	}
	if u, _ := s.LoadUser("anna"); u.DisplayName != "Anna" {
		t.Errorf("uebrige Felder muessen weiterhin geschrieben werden, DisplayName=%q", u.DisplayName)
	}

	// Trennen bei bert, danach veraltete Kopie von bert speichern.
	altBert, _ := s.LoadUser("bert")
	if err := s.ClearPremiumSmsReply("bert"); err != nil {
		t.Fatal(err)
	}
	if err := s.SaveUser(*altBert); err != nil {
		t.Fatal(err)
	}
	if got := rueckadresse(t, s, "bert"); got != "" {
		t.Errorf("getrennte Rueckadresse bei bert wiederhergestellt: %q", got)
	}
}

// F004: Eindeutigkeit gilt fuer alle Schreibweisen derselben Nummer.
func TestLearnPremiumSmsReplyToEntferntAndereSchreibweisen(t *testing.T) {
	s := neuerStoreMitKonten(t, "anna", "bert", "carl")
	if err := s.LearnPremiumSmsReplyTo("bert", "+4917000000083", time.Now()); err != nil {
		t.Fatal(err)
	}
	if err := s.LearnPremiumSmsReplyTo("carl", "4917000000084", time.Now()); err != nil {
		t.Fatal(err)
	}
	if err := s.LearnPremiumSmsReplyTo("anna", "004917000000083", time.Now()); err != nil {
		t.Fatal(err)
	}
	if got := rueckadresse(t, s, "bert"); got != "" {
		t.Errorf("bert traegt andere Schreibweise derselben Nummer weiter: %q", got)
	}
	if got := rueckadresse(t, s, "carl"); got != "4917000000084" {
		t.Errorf("carl (andere Nummer) veraendert: %q", got)
	}
	if got := rueckadresse(t, s, "anna"); got != "004917000000083" {
		t.Errorf("anna: gespeichert wird die gelieferte Form, bekam %q", got)
	}
}
