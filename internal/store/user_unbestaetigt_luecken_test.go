package store

// Issue #2961, Fix-Runde: Testluecken M23, M30, M37 der Gegenpruefung.

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// M23: ein Konto mit ausstehender Adressaenderung gilt nie als unbestaetigte Anmeldung.
func TestIsUnconfirmedSignup_AusstehendeAenderungNie(t *testing.T) {
	tok := &model.EmailVerificationToken{TokenHash: "x"}
	u := &model.User{ID: "m23", CreatedAt: time.Now()}
	if !IsUnconfirmedSignup(u, tok) {
		t.Fatal("Messaufbau: ohne ausstehende Aenderung ist es eine unbestaetigte Anmeldung")
	}
	u.PendingContactAddress = "neu@beispiel.de"
	if IsUnconfirmedSignup(u, tok) {
		t.Fatal("mit ausstehender Aenderung darf es keine unbestaetigte Anmeldung sein")
	}
}

// M30: ist user.json ein Verweis, gilt der Ordner als nicht leer.
func TestKontoordnerLeer_VerweisAlsUserJSON(t *testing.T) {
	s := &Store{DataDir: t.TempDir()}
	if err := s.SaveUser(model.User{ID: "m30", CreatedAt: time.Now()}); err != nil {
		t.Fatal(err)
	}
	ziel := filepath.Join(t.TempDir(), "fremd.json")
	if err := os.WriteFile(ziel, []byte(`{"id":"m30"}`), 0o600); err != nil {
		t.Fatal(err)
	}
	pfad := filepath.Join(s.UserDir("m30"), "user.json")
	if err := os.Remove(pfad); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(ziel, pfad); err != nil {
		t.Fatal(err)
	}
	if ok, _ := s.IsAccountDirPristine("m30"); ok {
		t.Fatal("ein Verweis als user.json darf nicht als leer gelten")
	}
}

// M37: ReplaceableAddressHolders verlangt den leeren Ordner.
func TestReplaceableAddressHolders_VerlangtLeerenOrdner(t *testing.T) {
	s := &Store{DataDir: t.TempDir()}
	for _, id := range []string{"m37-leer", "m37-voll"} {
		if err := s.SaveUser(model.User{ID: id, Email: id + "@beispiel.de", CreatedAt: time.Now()}); err != nil {
			t.Fatal(err)
		}
		if err := s.SaveVerificationToken(id, model.EmailVerificationToken{TokenHash: "x", ExpiresAt: time.Now()}); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.WriteFile(filepath.Join(s.UserDir("m37-voll"), "groups.json"), []byte(`[]`), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, ok, err := s.ReplaceableAddressHolders("m37-leer@beispiel.de"); err != nil || !ok {
		t.Fatalf("leerer Ordner: ersetzbar erwartet, bekommen %v %v", ok, err)
	}
	if _, ok, _ := s.ReplaceableAddressHolders("m37-voll@beispiel.de"); ok {
		t.Fatal("Ordner mit Nutzinhalt darf nicht ersetzbar sein")
	}
}
