package store

import (
	"os"
	"path/filepath"
	"syscall"
	"testing"
	"time"
)

// Issue #2237: Loeschen eines Ortsvergleich-Presets hinterlaesst keine
// Snapshots mehr; verwaiste .lock-Dateien raeumt RemoveBriefingLockFile ab,
// das der Handler erst NACH dem Freigeben seiner Sperre aufruft (ADR-0083).
// Echtes Dateisystem (t.TempDir), kein Mock.
// Spec: docs/specs/bugfix/fix_2237_staging_testdaten.md (AC-6/7/8).

func cleanupWrite(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(path, []byte(content), 0644); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
}

func cleanupExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func cleanupBriefings(tmp, user string) string {
	return filepath.Join(tmp, "users", user, "briefings")
}

func cleanupSnaps(tmp, user string) string {
	return filepath.Join(tmp, "users", user, "compare_weather_snapshots")
}

// AC-6 (Snapshot-Teil; die Sperrdatei prueft der Handler-Test).
func TestDeleteComparePreset_RaeumtSnapshotsAuf(t *testing.T) {
	tmp := t.TempDir()
	writeBriefingPresetFixture(t, tmp, "cl-a", "cp-a", "vergleich", "A")
	writeBriefingPresetFixture(t, tmp, "cl-a", "cp-ab", "vergleich", "AB")
	b, sn := cleanupBriefings(tmp, "cl-a"), cleanupSnaps(tmp, "cl-a")
	cleanupWrite(t, filepath.Join(sn, "cp-a__loc1.json"), `{"x":1}`)
	cleanupWrite(t, filepath.Join(sn, "cp-a__loc2.json"), `{"x":2}`)
	cleanupWrite(t, filepath.Join(sn, "cp-ab__loc1.json"), `{"x":3}`)
	// Fremddatei mit passendem Praefix, aber ohne .json-Endung: kein Snapshot.
	cleanupWrite(t, filepath.Join(sn, "cp-a__x.txt"), "fremd")

	if err := New(tmp, "cl-a").DeleteComparePreset("cp-a"); err != nil {
		t.Fatalf("DeleteComparePreset: %v", err)
	}
	for _, p := range []string{
		filepath.Join(b, "cp-a.json"),
		filepath.Join(sn, "cp-a__loc1.json"), filepath.Join(sn, "cp-a__loc2.json"),
	} {
		if cleanupExists(p) {
			t.Errorf("sollte entfernt sein: %s", p)
		}
	}
	for _, p := range []string{filepath.Join(sn, "cp-ab__loc1.json"), filepath.Join(b, "cp-ab.json")} {
		if !cleanupExists(p) {
			t.Errorf("fremdes Preset cp-ab darf nicht angefasst werden: %s", p)
		}
	}
	if !cleanupExists(filepath.Join(sn, "cp-a__x.txt")) {
		t.Error("Fremddatei cp-a__x.txt (kein .json) darf nicht entfernt werden")
	}
}

// AC-7 (Snapshot-Teil)
func TestDeleteComparePreset_ZweiNutzer(t *testing.T) {
	tmp := t.TempDir()
	for _, u := range []string{"cl-a", "cl-b"} {
		writeBriefingPresetFixture(t, tmp, u, "cp-x", "vergleich", "X")
		cleanupWrite(t, filepath.Join(cleanupSnaps(tmp, u), "cp-x__loc1.json"), "inhalt-"+u)
	}
	if err := New(tmp, "cl-a").DeleteComparePreset("cp-x"); err != nil {
		t.Fatalf("DeleteComparePreset: %v", err)
	}
	if cleanupExists(filepath.Join(cleanupSnaps(tmp, "cl-a"), "cp-x__loc1.json")) {
		t.Error("Snapshot von A muss weg sein")
	}
	snapB := filepath.Join(cleanupSnaps(tmp, "cl-b"), "cp-x__loc1.json")
	got, err := os.ReadFile(snapB)
	if err != nil || string(got) != "inhalt-cl-b" {
		t.Errorf("Snapshot von B veraendert/entfernt: err=%v inhalt=%q", err, got)
	}
	if !cleanupExists(filepath.Join(cleanupBriefings(tmp, "cl-b"), "cp-x.json")) {
		t.Error("cp-x.json von B muss bleiben")
	}
}

// Kind-Guard: route-Datei ueber den Preset-Pfad unantastbar, samt Snapshot.
func TestDeleteComparePreset_KindGuardLaesstSnapshotsStehen(t *testing.T) {
	tmp := t.TempDir()
	writeBriefingPresetFixture(t, tmp, "cl-a", "cp-t", "route", "T")
	b, sn := cleanupBriefings(tmp, "cl-a"), cleanupSnaps(tmp, "cl-a")
	cleanupWrite(t, filepath.Join(sn, "cp-t__loc.json"), "{}")
	if err := New(tmp, "cl-a").DeleteComparePreset("cp-t"); err != nil {
		t.Fatalf("err: %v", err)
	}
	for _, p := range []string{filepath.Join(b, "cp-t.json"), filepath.Join(sn, "cp-t__loc.json")} {
		if !cleanupExists(p) {
			t.Errorf("darf nicht entfernt werden: %s", p)
		}
	}
}

func TestDeleteComparePreset_Idempotent(t *testing.T) {
	tmp := t.TempDir()
	writeBriefingPresetFixture(t, tmp, "cl-a", "cp-i", "vergleich", "I")
	cleanupWrite(t, filepath.Join(cleanupSnaps(tmp, "cl-a"), "cp-i__l.json"), "{}")
	s := New(tmp, "cl-a")
	if err := s.DeleteComparePreset("cp-i"); err != nil {
		t.Fatalf("erstes Loeschen: %v", err)
	}
	if err := s.DeleteComparePreset("cp-i"); err != nil {
		t.Fatalf("zweites Loeschen: %v", err)
	}
}

// --- RemoveBriefingLockFile: jeder Schutz hat seinen eigenen Test ---------

// Verwaiste Sperrdatei (keine .json, niemand haelt sie) wird entfernt; die
// gleichnamige Sperrdatei von Nutzer B bleibt.
func TestRemoveBriefingLockFile_VerwaistWirdEntferntNurEigenerNutzer(t *testing.T) {
	tmp := t.TempDir()
	lockA := filepath.Join(cleanupBriefings(tmp, "cl-a"), "x1.json.lock")
	lockB := filepath.Join(cleanupBriefings(tmp, "cl-b"), "x1.json.lock")
	cleanupWrite(t, lockA, "")
	cleanupWrite(t, lockB, "")
	New(tmp, "cl-a").RemoveBriefingLockFile("x1")
	if cleanupExists(lockA) {
		t.Error("verwaiste Sperrdatei von A muss entfernt sein")
	}
	if !cleanupExists(lockB) {
		t.Error("Sperrdatei von B darf nicht angefasst werden")
	}
}

// .json vorhanden => Sperrdatei ist Betriebsmittel und bleibt.
func TestRemoveBriefingLockFile_JsonVorhandenBleibt(t *testing.T) {
	tmp := t.TempDir()
	writeBriefingPresetFixture(t, tmp, "cl-a", "x2", "vergleich", "V")
	lock := filepath.Join(cleanupBriefings(tmp, "cl-a"), "x2.json.lock")
	cleanupWrite(t, lock, "")
	New(tmp, "cl-a").RemoveBriefingLockFile("x2")
	if !cleanupExists(lock) {
		t.Error("Sperrdatei mit vorhandener .json darf nicht entfernt werden")
	}
}

// Von aussen gehaltener flock (z. B. Python-Kern) => Datei bleibt, sonst
// koennten zwei Prozesse parallel "die" Sperre halten.
func TestRemoveBriefingLockFile_BelegteSperreBleibt(t *testing.T) {
	tmp := t.TempDir()
	lock := filepath.Join(cleanupBriefings(tmp, "cl-a"), "x3.json.lock")
	cleanupWrite(t, lock, "")
	f, err := os.OpenFile(lock, os.O_RDWR, 0)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if err := syscall.Flock(int(f.Fd()), syscall.LOCK_EX); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = syscall.Flock(int(f.Fd()), syscall.LOCK_UN) }()
	New(tmp, "cl-a").RemoveBriefingLockFile("x3")
	if !cleanupExists(lock) {
		t.Error("belegte Sperrdatei darf nicht entfernt werden")
	}
}

// Prozess-Mutex: haelt ein Go-Aufrufer den Schluessel noch, wartet das
// Entfernen, bis er freigibt (sonst koennte er die Datei gerade oeffnen).
func TestRemoveBriefingLockFile_WartetAufProzessMutex(t *testing.T) {
	tmp := t.TempDir()
	lock := filepath.Join(cleanupBriefings(tmp, "cl-a"), "x5.json.lock")
	cleanupWrite(t, lock, "")
	s := New(tmp, "cl-a")
	release, _ := s.lockBriefing("x5", -1)
	done := make(chan struct{})
	go func() { s.RemoveBriefingLockFile("x5"); close(done) }()
	select {
	case <-done:
		release()
		t.Fatal("RemoveBriefingLockFile lief trotz gehaltenem Prozess-Mutex durch")
	case <-time.After(200 * time.Millisecond):
	}
	if !cleanupExists(lock) {
		t.Fatal("Sperrdatei bei gehaltenem Mutex entfernt")
	}
	release()
	select {
	case <-done:
	case <-time.After(5 * time.Second):
		t.Fatal("nach Freigabe nicht fortgesetzt")
	}
	if cleanupExists(lock) {
		t.Error("nach Freigabe muss die verwaiste Sperrdatei entfernt sein")
	}
}

// Ungueltige Id: kein Pfadausbruch, die Datei ausserhalb briefings/ bleibt.
func TestRemoveBriefingLockFile_UngueltigeIdLoeschtNichts(t *testing.T) {
	tmp := t.TempDir()
	evil := filepath.Join(tmp, "users", "cl-a", "evil.json.lock")
	cleanupWrite(t, evil, "")
	New(tmp, "cl-a").RemoveBriefingLockFile("../evil")
	if !cleanupExists(evil) {
		t.Error("ungueltige Id hat eine Datei ausserhalb briefings/ entfernt")
	}
}

// Leerer Nutzer: es wird nichts entfernt (kein Pfad users//briefings).
func TestRemoveBriefingLockFile_LeererNutzerLoeschtNichts(t *testing.T) {
	tmp := t.TempDir()
	lock := filepath.Join(tmp, "users", "briefings", "x6.json.lock")
	cleanupWrite(t, lock, "")
	New(tmp, "").RemoveBriefingLockFile("x6")
	if !cleanupExists(lock) {
		t.Error("leerer Nutzer hat eine Sperrdatei entfernt")
	}
}

// Fehlende Sperrdatei: kein Fehler, und es wird keine neu angelegt.
func TestRemoveBriefingLockFile_FehltLegtNichtsAn(t *testing.T) {
	tmp := t.TempDir()
	b := cleanupBriefings(tmp, "cl-a")
	if err := os.MkdirAll(b, 0755); err != nil {
		t.Fatal(err)
	}
	New(tmp, "cl-a").RemoveBriefingLockFile("x4")
	if cleanupExists(filepath.Join(b, "x4.json.lock")) {
		t.Error("RemoveBriefingLockFile hat eine Sperrdatei angelegt")
	}
}
