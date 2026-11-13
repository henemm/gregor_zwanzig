package store

// Issue #2961 (GA6, ADR-0115): Sicherheitsfelder der user.json schreibt nur
// UpdateUser bzw. ein Merge-Setter, der frisch laedt. Ein veralteter
// SaveUser-Schreiber (Profil, Passkey-Angebot, Telegram ...) setzt sie nie
// zurueck — auch nicht, wenn er parallel zu einem Passwort-Reset oder einer
// Admin-Sperre laeuft.

import (
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

func sicherheitsKonto(t *testing.T, s *Store, id string) {
	t.Helper()
	if err := s.SaveUser(model.User{
		ID: id, Email: id + "@example.com", PasswordHash: "alt-" + id, CreatedAt: time.Now(),
		PasskeyCredentials: []model.WebAuthnCredential{{ID: []byte("pk-" + id)}},
		OAuthProvider:      "google", OAuthSub: "sub-" + id, Tier: "standard",
	}); err != nil {
		t.Fatalf("anlegen: %v", err)
	}
}

func TestSaveUser_VeralteterSchreiberSetztSicherheitsfelderNichtZurueck(t *testing.T) {
	s := &Store{DataDir: t.TempDir()}
	sicherheitsKonto(t, s, "anna")
	veraltet, err := s.LoadUser("anna")
	if err != nil || veraltet == nil {
		t.Fatalf("laden: %v", err)
	}

	jetzt := time.Now().UTC().Truncate(time.Second)
	if _, err := s.UpdateUser("anna", func(u *model.User) error {
		u.PasswordHash = "neu"
		u.PasskeyCredentials = nil
		u.OAuthProvider, u.OAuthSub = "", ""
		u.EmailVerifiedAt = &jetzt
		return nil
	}); err != nil {
		t.Fatalf("UpdateUser: %v", err)
	}
	if err := s.SetUserDisabled("anna", true); err != nil {
		t.Fatal(err)
	}
	if err := s.SetUserTier("anna", "premium"); err != nil {
		t.Fatal(err)
	}

	veraltet.DisplayName = "Anna"
	if err := s.SaveUser(*veraltet); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	u, _ := s.LoadUser("anna")
	if u.DisplayName != "Anna" {
		t.Errorf("Profilfeld des veralteten Schreibers fehlt: %q", u.DisplayName)
	}
	if u.PasswordHash != "neu" {
		t.Errorf("password_hash zurueckgesetzt: %q", u.PasswordHash)
	}
	if len(u.PasskeyCredentials) != 0 {
		t.Errorf("entfernte Passkeys wieder da: %d", len(u.PasskeyCredentials))
	}
	if u.OAuthSub != "" || u.OAuthProvider != "" {
		t.Errorf("geloeste Google-Verknuepfung wieder da: %q/%q", u.OAuthProvider, u.OAuthSub)
	}
	if !u.Disabled {
		t.Errorf("Admin-Sperre zurueckgesetzt")
	}
	if u.Tier != "premium" {
		t.Errorf("tier zurueckgesetzt: %q", u.Tier)
	}
	if u.EmailVerifiedAt == nil || !u.EmailVerifiedAt.Equal(jetzt) {
		t.Errorf("email_verified_at zurueckgesetzt: %v", u.EmailVerifiedAt)
	}
}

// Neuanlage (keine user.json vorhanden) schreibt weiterhin alle Felder.
func TestSaveUser_NeuanlageSchreibtSicherheitsfelder(t *testing.T) {
	s := &Store{DataDir: t.TempDir()}
	sicherheitsKonto(t, s, "bert")
	u, _ := s.LoadUser("bert")
	if u.PasswordHash != "alt-bert" || len(u.PasskeyCredentials) != 1 || u.OAuthSub != "sub-bert" || u.Tier != "standard" {
		t.Fatalf("Neuanlage unvollstaendig: %+v", u)
	}
}

// Parallel: viele veraltete Profil-Schreiber gegen Passwort-Reset und
// Admin-Sperre, fuer ZWEI Nutzer gleichzeitig. Der Sicherheitswert ueberlebt
// immer, und kein Nutzer erhaelt Werte des anderen. Mit -race laufen lassen.
func TestUserJSON_ParalleleSchreiberSicherheitswertUeberlebt(t *testing.T) {
	s := &Store{DataDir: t.TempDir()}
	for _, id := range []string{"cara", "dora"} {
		sicherheitsKonto(t, s, id)
	}
	for runde := 0; runde < 20; runde++ {
		var wg sync.WaitGroup
		for _, id := range []string{"cara", "dora"} {
			id := id
			veraltet, _ := s.LoadUser(id)
			for i := 0; i < 8; i++ {
				wg.Add(1)
				go func(i int) {
					defer wg.Done()
					kopie := *veraltet
					kopie.DisplayName = fmt.Sprintf("%s-%d", id, i)
					if err := s.SaveUser(kopie); err != nil {
						t.Errorf("SaveUser: %v", err)
					}
				}(i)
			}
			wg.Add(2)
			go func() {
				defer wg.Done()
				if _, err := s.UpdateUser(id, func(u *model.User) error {
					u.PasswordHash = "reset-" + id
					u.PasskeyCredentials = nil
					return nil
				}); err != nil {
					t.Errorf("UpdateUser: %v", err)
				}
			}()
			go func() {
				defer wg.Done()
				if err := s.SetUserDisabled(id, true); err != nil {
					t.Errorf("SetUserDisabled: %v", err)
				}
			}()
		}
		wg.Wait()
		for _, id := range []string{"cara", "dora"} {
			u, err := s.LoadUser(id)
			if err != nil || u == nil {
				t.Fatalf("laden %s: %v", id, err)
			}
			if u.PasswordHash != "reset-"+id || len(u.PasskeyCredentials) != 0 || !u.Disabled {
				t.Fatalf("Runde %d, %s: Sicherheitswert verloren: hash=%q passkeys=%d disabled=%v",
					runde, id, u.PasswordHash, len(u.PasskeyCredentials), u.Disabled)
			}
			if u.ID != id || u.Email != id+"@example.com" {
				t.Fatalf("Runde %d: fremde Werte in %s: %+v", runde, id, u)
			}
		}
		// fuer die naechste Runde wieder herstellen
		for _, id := range []string{"cara", "dora"} {
			id := id
			if _, err := s.UpdateUser(id, func(u *model.User) error {
				u.PasswordHash = "alt-" + id
				u.PasskeyCredentials = []model.WebAuthnCredential{{ID: []byte("pk-" + id)}}
				return nil
			}); err != nil {
				t.Fatal(err)
			}
			if err := s.SetUserDisabled(id, false); err != nil {
				t.Fatal(err)
			}
		}
	}
}

// UpdateUser auf ein fehlendes Konto ist ein Fehler, kein stilles Anlegen.
func TestUpdateUser_FehlendesKontoIstFehler(t *testing.T) {
	s := &Store{DataDir: t.TempDir()}
	if _, err := s.UpdateUser("niemand", func(u *model.User) error { return nil }); err == nil {
		t.Fatal("erwartet Fehler fuer fehlendes Konto")
	}
	if s.UserExists("niemand") {
		t.Fatal("UpdateUser darf kein Konto anlegen")
	}
}
