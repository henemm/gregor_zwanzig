package store

// Issue #2961 (ADR-0115): "leer" ist eine Positivliste. Alles ausser
// user.json, sessions.json, email_verification.json, password_reset.json und
// den LEEREN Standardverzeichnissen locations/, gpx/, weather_snapshots/
// heisst "nicht leer" — und ein nicht leerer Ordner wird nie verschoben.

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

func TestKontoordnerLeer_Positivliste(t *testing.T) {
	s := &Store{DataDir: t.TempDir()}
	anlegen := func(id string) string {
		if err := s.SaveUser(model.User{ID: id, CreatedAt: time.Now()}); err != nil {
			t.Fatal(err)
		}
		if err := s.ProvisionUserDirs(id); err != nil {
			t.Fatal(err)
		}
		for _, f := range []string{"sessions.json", "email_verification.json", "password_reset.json"} {
			if err := os.WriteFile(filepath.Join(s.UserDir(id), f), []byte(`{}`), 0o600); err != nil {
				t.Fatal(err)
			}
		}
		return s.UserDir(id)
	}
	leer := anlegen("leer")
	if ok, err := s.IsAccountDirPristine("leer"); err != nil || !ok {
		t.Fatalf("frisch registriertes Konto muss leer sein: %v %v", ok, err)
	}
	_ = leer

	faelle := map[string]func(dir string){
		"trip":    func(d string) { _ = os.MkdirAll(filepath.Join(d, "briefings"), 0o700) },
		"log":     func(d string) { _ = os.WriteFile(filepath.Join(d, "briefing_log.json"), []byte(`[]`), 0o600) },
		"gpx":     func(d string) { _ = os.WriteFile(filepath.Join(d, "gpx", "a.gpx"), []byte(`x`), 0o600) },
		"sperre":  func(d string) { _ = os.WriteFile(filepath.Join(d, "x.json.lock"), nil, 0o600) },
		"verweis": func(d string) { _ = os.Symlink("/tmp", filepath.Join(d, "anderes")) },
		"gruppen": func(d string) { _ = os.WriteFile(filepath.Join(d, "groups.json"), []byte(`[]`), 0o600) },
	}
	for name, mach := range faelle {
		mach(anlegen("voll-" + name))
		if ok, _ := s.IsAccountDirPristine("voll-" + name); ok {
			t.Errorf("%s: Ordner mit Nutzinhalt gilt faelschlich als leer", name)
		}
		if _, err := s.QuarantineUser("voll-"+name, time.Now()); !errors.Is(err, ErrAccountDirNotPristine) {
			t.Errorf("%s: nicht leerer Ordner darf nicht verschoben werden: %v", name, err)
		}
		if !s.UserExists("voll-" + name) {
			t.Errorf("%s: Konto muss bleiben", name)
		}
	}

	ziel, err := s.QuarantineUser("leer", time.Date(2026, 11, 13, 1, 2, 3, 0, time.UTC))
	if err != nil {
		t.Fatal(err)
	}
	if filepath.Dir(ziel) != filepath.Join(s.DataDir, AblageVerzeichnis) || filepath.Base(ziel) != "leer-20261113T010203Z" {
		t.Errorf("Ablageziel unerwartet: %s", ziel)
	}
	if _, err := os.Stat(filepath.Join(ziel, "user.json")); err != nil {
		t.Errorf("Inhalt muss in der Ablage liegen: %v", err)
	}
	if s.UserExists("leer") {
		t.Error("Konto muss aus users/ verschwunden sein")
	}
}

// F-A: unter der Sperre wird erneut geprueft, ob das Konto noch eine
// unbestaetigte Anmeldung ist — ein inzwischen bestaetigtes (oder mit
// ausstehender Adressaenderung) wird nie verschoben.
func TestQuarantineUser_InzwischenBestaetigtWirdNichtVerschoben(t *testing.T) {
	s := &Store{DataDir: t.TempDir()}
	for _, id := range []string{"best", "pend"} {
		if err := s.SaveUser(model.User{ID: id, Email: id + "@beispiel.de", CreatedAt: time.Now()}); err != nil {
			t.Fatal(err)
		}
		if err := s.SaveVerificationToken(id, model.EmailVerificationToken{TokenHash: "x", ExpiresAt: time.Now()}); err != nil {
			t.Fatal(err)
		}
	}
	jetzt := time.Now().UTC()
	if _, err := s.UpdateUser("best", func(u *model.User) error { u.EmailVerifiedAt = &jetzt; return nil }); err != nil {
		t.Fatal(err)
	}
	if _, err := s.UpdateUser("pend", func(u *model.User) error { u.PendingContactAddress = "neu@beispiel.de"; return nil }); err != nil {
		t.Fatal(err)
	}
	for _, id := range []string{"best", "pend"} {
		if _, err := s.QuarantineUser(id, time.Now()); !errors.Is(err, ErrNotUnconfirmedSignup) {
			t.Errorf("%s: erwartet ErrNotUnconfirmedSignup, bekommen %v", id, err)
		}
		if !s.UserExists(id) {
			t.Errorf("%s muss in users/ bleiben", id)
		}
	}
}
