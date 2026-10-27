package store

// Issue #2624: Neu angelegte Verzeichnisse (0770) und Dateien (0660) muessen
// unter Default-ACL die Gruppen-Schreibrechte behalten. Geprueft wird am Ort
// der Wirkung: echte Store-Aufrufe unter Prozess-Umask 0077 (Prod-Umask),
// danach Stat() auf jedem entstandenen Pfad.

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func setzeUmask077(t *testing.T) {
	t.Helper()
	alt := syscall.Umask(0o077)
	t.Cleanup(func() { syscall.Umask(alt) })
}

// schreibeAlleEntitaeten legt ein Konto an und schreibt je Entitaet eine Datei.
func schreibeAlleEntitaeten(t *testing.T, root, userID string) {
	t.Helper()
	s := New(root, userID)
	if err := s.ProvisionUserDirs(userID); err != nil {
		t.Fatalf("ProvisionUserDirs: %v", err)
	}
	if err := s.SaveUser(model.User{ID: userID}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	if err := s.SaveTrip(&model.Trip{ID: "trip-" + userID, Name: "T"}); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	if err := s.SaveLocation(model.Location{ID: "loc-" + userID, Name: "L"}); err != nil {
		t.Fatalf("SaveLocation: %v", err)
	}
	if err := s.SaveGroup(model.Group{ID: "grp-" + userID, Name: "G"}); err != nil {
		t.Fatalf("SaveGroup: %v", err)
	}
	if err := s.SaveMetricPresets([]model.MetricPreset{{ID: "mp-" + userID, Name: "M"}}); err != nil {
		t.Fatalf("SaveMetricPresets: %v", err)
	}
	if err := s.SaveComparePreset(model.ComparePreset{ID: "cmp-" + userID, Name: "C", UserID: userID}); err != nil {
		t.Fatalf("SaveComparePreset: %v", err)
	}
	if err := s.AddSession(userID, "sess-"+userID); err != nil {
		t.Fatalf("AddSession: %v", err)
	}
	// Briefing-Lock (Datei entsteht beim ersten Sperren)
	s.LockBriefing("brief-" + userID)()
}

func pruefeModi(t *testing.T, wurzel string) (dirs, files int) {
	t.Helper()
	err := filepath.Walk(wurzel, func(p string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(wurzel, p)
		if info.IsDir() {
			dirs++
			if got := info.Mode().Perm(); got != 0o770 {
				t.Errorf("Verzeichnis %s: Modus %#o, erwartet 0770", rel, got)
			}
		} else {
			files++
			if got := info.Mode().Perm(); got != 0o660 {
				t.Errorf("Datei %s: Modus %#o, erwartet 0660", rel, got)
			}
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	return
}

// AC-1/AC-2/AC-3: zwei Konten nacheinander, beide Baeume rekursiv geprueft.
func TestDateimodi_ZweiKontenNeuAngelegt_0770_0660_UnterUmask077(t *testing.T) {
	setzeUmask077(t)
	root := filepath.Join(t.TempDir(), "data")
	for _, uid := range []string{"alice", "bob"} {
		schreibeAlleEntitaeten(t, root, uid)
	}
	if fi, err := os.Stat(filepath.Join(root, "users")); err != nil || fi.Mode().Perm() != 0o770 {
		t.Errorf("users/-Verzeichnis: %v %v, erwartet 0770", fi, err)
	}
	for _, uid := range []string{"alice", "bob"} {
		dirs, files := pruefeModi(t, filepath.Join(root, "users", uid))
		if dirs == 0 || files < 7 {
			t.Fatalf("%s: zu wenig geprueft (dirs=%d files=%d) -- Test waere vakuum", uid, dirs, files)
		}
	}
	// Mandantentrennung: Konto A sieht keine Daten von B.
	locs, err := New(root, "alice").LoadLocations()
	if err != nil {
		t.Fatal(err)
	}
	for _, l := range locs {
		if l.ID == "loc-bob" {
			t.Fatalf("alice sieht Ort von bob")
		}
	}
}

// AC-4: Einladungen (data/invites) ebenfalls 0660/0770.
func TestDateimodi_Einladungen_0660(t *testing.T) {
	setzeUmask077(t)
	root := filepath.Join(t.TempDir(), "data")
	is := NewInviteStore(root)
	if _, _, err := is.Create("free", "n", "admin"); err != nil {
		t.Fatalf("Create: %v", err)
	}
	pruefeModi(t, root)
}

// AC-7: Bestand bleibt unangetastet bzw. wandert beim Schreiben auf 0660.
func TestDateimodi_Bestand_VerzeichnisBleibt0755_DateiWird0660_InhaltErhalten(t *testing.T) {
	setzeUmask077(t)
	root := filepath.Join(t.TempDir(), "data")
	dir := filepath.Join(root, "users", "carol")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	s := New(root, "carol")
	if err := s.SaveUser(model.User{ID: "carol", Email: "bestand@example.org"}); err != nil {
		t.Fatal(err)
	}
	p := filepath.Join(dir, "user.json")
	if err := os.Chmod(p, 0o644); err != nil {
		t.Fatal(err)
	}
	if err := s.SaveUser(model.User{ID: "carol", Email: "bestand@example.org"}); err != nil {
		t.Fatal(err)
	}
	di, _ := os.Stat(dir)
	if di.Mode().Perm() != 0o755 {
		t.Errorf("Bestandsverzeichnis veraendert: %#o", di.Mode().Perm())
	}
	fi, _ := os.Stat(p)
	if fi.Mode().Perm() != 0o660 {
		t.Errorf("Bestandsdatei nach Schreiben: %#o, erwartet 0660", fi.Mode().Perm())
	}
	raw, _ := os.ReadFile(p)
	if !strings.Contains(string(raw), "bestand@example.org") {
		t.Errorf("Bestandsinhalt verloren: %s", raw)
	}
}

// AC-1/AC-2 ergaenzend: echte Default-ACL. Ehrlich: Skip ohne ACL-Dateisystem
// ist KEIN Gate -- dann bewacht allein der Modus-Test oben.
func TestDateimodi_DefaultACL_MaskeBleibtSchreibbar(t *testing.T) {
	for _, tool := range []string{"setfacl", "getfacl"} {
		if _, err := exec.LookPath(tool); err != nil {
			t.Skipf("%s fehlt -- kein ACL-Beweis auf diesem Runner", tool)
		}
	}
	root := filepath.Join(t.TempDir(), "data")
	if err := os.MkdirAll(root, 0o770); err != nil {
		t.Fatal(err)
	}
	if out, err := exec.Command("setfacl", "-d", "-m", "g::rwX", root).CombinedOutput(); err != nil {
		t.Skipf("Dateisystem ohne ACL-Unterstuetzung: %v %s", err, out)
	}
	setzeUmask077(t)
	schreibeAlleEntitaeten(t, root, "dora")
	check := func(pfad, erwartet string) {
		out, err := exec.Command("getfacl", "-c", pfad).CombinedOutput()
		if err != nil {
			t.Fatalf("getfacl %s: %v", pfad, err)
		}
		if !strings.Contains(string(out), erwartet) {
			t.Errorf("%s: erwartet %q, ist:\n%s", pfad, erwartet, out)
		}
	}
	check(filepath.Join(root, "users", "dora", "locations"), "mask::rwx")
	check(filepath.Join(root, "users", "dora", "sessions.json"), "mask::rw-")
}
