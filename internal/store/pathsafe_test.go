package store

import (
	"encoding/json"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// TDD RED — Issue #2140 Scheibe 1 (Nutzer-Achse), Store-Ebene. SPEC:
// docs/specs/modules/fix_2140_pfad_traversal_nutzer_kennung.md AC-11, AC-12.
//
// AC-13 (store.ValidUserID) liegt bewusst in einer EIGENEN Datei
// (valid_user_id_test.go) — sie referenziert eine noch nicht existierende
// Funktion und wuerde sonst das gesamte Paket am Kompilieren hindern und
// damit diese verhaltensbasierten Tests unsichtbar machen.
//
// Methodik wie im Handler-Pendant (auth_traversal_test.go): eine
// Traversal-Kennung wie "../bob" landet ueber UserDir("../bob") NICHT im
// Verzeichnis eines gleichnamigen, real registrierten Nutzers unter
// data/users/bob, sondern in einem GESCHWISTER-Verzeichnis von "users"
// (filepath.Join kappt "users" beim Auswerten von ".."). Jeder Test prueft
// deshalb zusaetzlich zum realen Zweitnutzer explizit die tatsaechliche
// Zielposition ueber s.UserDir(id).

func findFilesOutsideUsersTree(t *testing.T, dataDir, filename string) []string {
	t.Helper()
	usersRoot := filepath.Join(dataDir, "users")
	var found []string
	err := filepath.WalkDir(dataDir, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		if d.Name() != filename {
			return nil
		}
		rel, relErr := filepath.Rel(usersRoot, path)
		if relErr == nil && !strings.HasPrefix(rel, "..") {
			return nil
		}
		found = append(found, path)
		return nil
	})
	if err != nil {
		t.Fatalf("WalkDir(%s): %v", dataDir, err)
	}
	return found
}

// AC-11: LoadUser/SaveUser/DeleteUser mit einer Traversal-Kennung muessen
// jeweils einen Fehler liefern, ohne den realen Zweitnutzer zu beruehren.
//
// Heutiger Stand (RED):
//   - LoadUser("../bob"):  Ziel-Datei existiert nicht -> (nil, nil), KEIN Fehler
//   - SaveUser({ID:"../bob"}): schreibt klaglos ausserhalb des Baums, KEIN Fehler
//   - DeleteUser("../bob"): os.RemoveAll auf nicht existierendes Verzeichnis
//     liefert ebenfalls KEINEN Fehler
func TestPathTraversal_UserMethods_RejectInvalidID_AC11(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")

	// Real registrierter zweiter Nutzer — muss in JEDEM Teiltest unberuehrt bleiben.
	realHash := "$2a$04$realbobhashplaceholderxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
	if err := s.SaveUser(model.User{ID: "bob", PasswordHash: realHash, CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser(bob): %v", err)
	}
	bobFile := filepath.Join(s.UserDir("bob"), "user.json")
	bobBefore, err := os.ReadFile(bobFile)
	if err != nil {
		t.Fatalf("ReadFile(bob): %v", err)
	}

	t.Run("LoadUser", func(t *testing.T) {
		u, err := s.LoadUser("../bob")
		if err == nil {
			t.Errorf("AC-11: LoadUser(\"../bob\") expected an error, got user=%+v err=nil", u)
		}
	})

	t.Run("SaveUser", func(t *testing.T) {
		err := s.SaveUser(model.User{ID: "../bob", PasswordHash: "x", CreatedAt: time.Now()})
		if err == nil {
			t.Error("AC-11: SaveUser({ID:\"../bob\"}) expected an error, got nil")
		}
		if _, statErr := os.Stat(filepath.Join(s.UserDir("../bob"), "user.json")); statErr == nil {
			t.Error("AC-11: SaveUser must not create a file outside the users tree")
		}
	})

	t.Run("DeleteUser", func(t *testing.T) {
		err := s.DeleteUser("../bob")
		if err == nil {
			t.Error("AC-11: DeleteUser(\"../bob\") expected an error, got nil")
		}
	})

	bobAfter, err := os.ReadFile(bobFile)
	if err != nil {
		t.Fatalf("ReadFile(bob) after attack: %v", err)
	}
	if string(bobBefore) != string(bobAfter) {
		t.Error("AC-11: real second user's user.json must stay byte-identical")
	}
}

// AC-12: AddSession/RemoveSession/HasSession/ClearSessions mit einer
// Traversal-userId muessen jeweils einen Fehler liefern (HasSession:
// (false, error)), ohne eine sessions.json ausserhalb des Nutzerbaums
// zu hinterlassen.
//
// Heutiger Stand (RED): alle vier Methoden liefern nil/false ohne Fehler,
// UND AddSession/ClearSessions schreiben tatsaechlich eine sessions.json
// ausserhalb des Baums (Geschwister von "users").
func TestPathTraversal_SessionMethods_RejectInvalidID_AC12(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")

	if err := s.AddSession("../bob", "sess-attack-1"); err == nil {
		t.Error("AC-12: AddSession(\"../bob\", ...) expected an error, got nil")
	}
	if err := s.RemoveSession("../bob", "sess-attack-1"); err == nil {
		t.Error("AC-12: RemoveSession(\"../bob\", ...) expected an error, got nil")
	}
	has, err := s.HasSession("../bob", "sess-attack-1")
	if err == nil {
		t.Errorf("AC-12: HasSession(\"../bob\", ...) expected (false, error), got (%v, nil)", has)
	}
	if err := s.ClearSessions("../bob"); err == nil {
		t.Error("AC-12: ClearSessions(\"../bob\") expected an error, got nil")
	}

	if outside := findFilesOutsideUsersTree(t, tmpDir, "sessions.json"); len(outside) > 0 {
		t.Errorf("AC-12: found sessions.json outside data/users/: %v", outside)
	}
}

// -----------------------------------------------------------------------
// F001 (Fix-Loop #2140): Direkttests fuer die uebrigen Spec-Methoden
// -----------------------------------------------------------------------

// seedTraversalVictim baut den Aufbau, an dem sich eine fehlende Sperre
// ZEIGT: einen realen Nutzer "bob" IM Nutzerbaum und daneben einen
// vollstaendigen Opfer-Datensatz GENAU dort, wo UserDir("../bob") landet
// (Geschwister von "users", siehe Methodik-Kommentar oben).
//
// Ohne diesen Opfer-Datensatz waeren die Lese- und Loeschmethoden nicht
// pruefbar: sie liefern auf einem leeren Zielpfad auch ungeprueft klaglos
// "nichts gefunden" — die Sperre koennte ersatzlos entfallen, ohne dass ein
// Test es merkt.
func seedTraversalVictim(t *testing.T) (*Store, string) {
	t.Helper()
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")

	if err := s.SaveUser(model.User{ID: "bob", PasswordHash: "bobs-real-hash", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser(bob): %v", err)
	}

	victim := s.UserDir("../bob")
	if err := os.MkdirAll(victim, 0755); err != nil {
		t.Fatalf("MkdirAll(%s): %v", victim, err)
	}
	files := map[string]any{
		"user.json":               model.User{ID: "../bob", PasswordHash: "victim-hash", CreatedAt: time.Now()},
		"password_reset.json":     model.PasswordResetToken{TokenHash: "victim-reset", ExpiresAt: time.Now().Add(time.Hour)},
		"email_verification.json": model.EmailVerificationToken{TokenHash: "victim-verify", ExpiresAt: time.Now().Add(time.Hour)},
		"sessions.json":           sessionFile{Sessions: []Session{{ID: "victim-sess", CreatedAt: time.Now()}}},
	}
	for name, v := range files {
		data, err := json.Marshal(v)
		if err != nil {
			t.Fatalf("Marshal(%s): %v", name, err)
		}
		if err := os.WriteFile(filepath.Join(victim, name), data, 0644); err != nil {
			t.Fatalf("WriteFile(%s): %v", name, err)
		}
	}
	return s, victim
}

// mustRead liefert den Inhalt einer Opfer-Datei; fehlt sie, ist das ein
// Testabbruch (der Aufbau haette sie angelegt).
func mustRead(t *testing.T, path string) string {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("ReadFile(%s): %v", path, err)
	}
	return string(data)
}

// F001: Die Spec (Source-Sektion) nennt elf user.go-Methoden plus fuenf
// Sessions-Einstiege. LoadUser/SaveUser/DeleteUser sind oben abgedeckt,
// AddSession/RemoveSession/HasSession/ClearSessions in AC-12 — hier folgen
// die uebrigen, damit KEINE der Sperren spurlos verschwinden kann.
//
// Je Methode wird beides geprueft: der Fehler (bzw. false bei UserExists)
// UND die ausbleibende Wirkung auf den Opfer-Datensatz ausserhalb des
// Nutzerbaums.
func TestPathTraversal_RemainingUserMethods_RejectInvalidID_AC11(t *testing.T) {
	const attack = "../bob"

	t.Run("ProvisionUserDirs", func(t *testing.T) {
		s, victim := seedTraversalVictim(t)
		if err := s.ProvisionUserDirs(attack); err == nil {
			t.Error("AC-11: ProvisionUserDirs(\"../bob\") expected an error, got nil")
		}
		for _, sub := range []string{"locations", "gpx", "weather_snapshots"} {
			if _, err := os.Stat(filepath.Join(victim, sub)); err == nil {
				t.Errorf("AC-11: ProvisionUserDirs must not create %q outside the users tree", sub)
			}
		}
	})

	t.Run("SaveResetToken", func(t *testing.T) {
		s, victim := seedTraversalVictim(t)
		before := mustRead(t, filepath.Join(victim, "password_reset.json"))
		if err := s.SaveResetToken(attack, model.PasswordResetToken{TokenHash: "attacker", ExpiresAt: time.Now().Add(time.Hour)}); err == nil {
			t.Error("AC-11: SaveResetToken(\"../bob\", ...) expected an error, got nil")
		}
		if after := mustRead(t, filepath.Join(victim, "password_reset.json")); before != after {
			t.Error("AC-11: SaveResetToken must not overwrite a file outside the users tree")
		}
	})

	t.Run("LoadResetToken", func(t *testing.T) {
		s, _ := seedTraversalVictim(t)
		token, err := s.LoadResetToken(attack)
		if err == nil {
			t.Error("AC-11: LoadResetToken(\"../bob\") expected an error, got nil")
		}
		if token != nil {
			t.Errorf("AC-11: LoadResetToken must not read a token outside the users tree, got %+v", token)
		}
	})

	t.Run("DeleteResetToken", func(t *testing.T) {
		s, victim := seedTraversalVictim(t)
		if err := s.DeleteResetToken(attack); err == nil {
			t.Error("AC-11: DeleteResetToken(\"../bob\") expected an error, got nil")
		}
		if _, err := os.Stat(filepath.Join(victim, "password_reset.json")); err != nil {
			t.Error("AC-11: DeleteResetToken must not remove a file outside the users tree")
		}
	})

	t.Run("SaveVerificationToken", func(t *testing.T) {
		s, victim := seedTraversalVictim(t)
		before := mustRead(t, filepath.Join(victim, "email_verification.json"))
		if err := s.SaveVerificationToken(attack, model.EmailVerificationToken{TokenHash: "attacker", ExpiresAt: time.Now().Add(time.Hour)}); err == nil {
			t.Error("AC-11: SaveVerificationToken(\"../bob\", ...) expected an error, got nil")
		}
		if after := mustRead(t, filepath.Join(victim, "email_verification.json")); before != after {
			t.Error("AC-11: SaveVerificationToken must not overwrite a file outside the users tree")
		}
	})

	t.Run("LoadVerificationToken", func(t *testing.T) {
		s, _ := seedTraversalVictim(t)
		token, err := s.LoadVerificationToken(attack)
		if err == nil {
			t.Error("AC-11: LoadVerificationToken(\"../bob\") expected an error, got nil")
		}
		if token != nil {
			t.Errorf("AC-11: LoadVerificationToken must not read a token outside the users tree, got %+v", token)
		}
	})

	t.Run("DeleteVerificationToken", func(t *testing.T) {
		s, victim := seedTraversalVictim(t)
		if err := s.DeleteVerificationToken(attack); err == nil {
			t.Error("AC-11: DeleteVerificationToken(\"../bob\") expected an error, got nil")
		}
		if _, err := os.Stat(filepath.Join(victim, "email_verification.json")); err != nil {
			t.Error("AC-11: DeleteVerificationToken must not remove a file outside the users tree")
		}
	})

	t.Run("UserExists", func(t *testing.T) {
		s, _ := seedTraversalVictim(t)
		// Am Zielpfad LIEGT eine user.json — ohne Sperre antwortet die
		// Methode deshalb "ja, den gibt es".
		if s.UserExists(attack) {
			t.Error("AC-11: UserExists(\"../bob\") expected false, got true")
		}
	})

	t.Run("LoadSessions", func(t *testing.T) {
		s, _ := seedTraversalVictim(t)
		sessions, err := s.LoadSessions(attack)
		if err == nil {
			t.Error("AC-12: LoadSessions(\"../bob\") expected an error, got nil")
		}
		if len(sessions) > 0 {
			t.Errorf("AC-12: LoadSessions must not read a guest list outside the users tree, got %+v", sessions)
		}
	})
}
