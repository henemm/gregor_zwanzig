package store

import (
	"os"
	"path/filepath"
	"testing"
)

// Issue #2237: Loeschen eines Ortsvergleich-Presets / Trips hinterlaesst keine
// Snapshots und keine .lock-Dateien mehr. Echtes Dateisystem (t.TempDir),
// kein Mock. Spec: docs/specs/bugfix/fix_2237_staging_testdaten.md (AC-6/7/8).

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

// AC-6
func TestDeleteComparePreset_RaeumtSnapshotsUndLockAuf(t *testing.T) {
	tmp := t.TempDir()
	writeBriefingPresetFixture(t, tmp, "cl-a", "cp-a", "vergleich", "A")
	writeBriefingPresetFixture(t, tmp, "cl-a", "cp-ab", "vergleich", "AB")
	b, sn := cleanupBriefings(tmp, "cl-a"), cleanupSnaps(tmp, "cl-a")
	cleanupWrite(t, filepath.Join(b, "cp-a.json.lock"), "")
	cleanupWrite(t, filepath.Join(sn, "cp-a__loc1.json"), `{"x":1}`)
	cleanupWrite(t, filepath.Join(sn, "cp-a__loc2.json"), `{"x":2}`)
	cleanupWrite(t, filepath.Join(sn, "cp-ab__loc1.json"), `{"x":3}`)
	// Fremddatei mit passendem Praefix, aber ohne .json-Endung: kein Snapshot.
	cleanupWrite(t, filepath.Join(sn, "cp-a__x.txt"), "fremd")

	if err := New(tmp, "cl-a").DeleteComparePreset("cp-a"); err != nil {
		t.Fatalf("DeleteComparePreset: %v", err)
	}
	for _, p := range []string{
		filepath.Join(b, "cp-a.json"), filepath.Join(b, "cp-a.json.lock"),
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

// AC-7
func TestDeleteComparePreset_ZweiNutzer(t *testing.T) {
	tmp := t.TempDir()
	for _, u := range []string{"cl-a", "cl-b"} {
		writeBriefingPresetFixture(t, tmp, u, "cp-x", "vergleich", "X")
		cleanupWrite(t, filepath.Join(cleanupBriefings(tmp, u), "cp-x.json.lock"), "")
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
	for _, n := range []string{"cp-x.json", "cp-x.json.lock"} {
		if !cleanupExists(filepath.Join(cleanupBriefings(tmp, "cl-b"), n)) {
			t.Errorf("%s von B muss bleiben", n)
		}
	}
}

// Kind-Guard: route-Datei ueber den Preset-Pfad unantastbar, samt Snapshot.
func TestDeleteComparePreset_KindGuardLaesstSnapshotsStehen(t *testing.T) {
	tmp := t.TempDir()
	writeBriefingPresetFixture(t, tmp, "cl-a", "cp-t", "route", "T")
	b, sn := cleanupBriefings(tmp, "cl-a"), cleanupSnaps(tmp, "cl-a")
	cleanupWrite(t, filepath.Join(b, "cp-t.json.lock"), "")
	cleanupWrite(t, filepath.Join(sn, "cp-t__loc.json"), "{}")
	if err := New(tmp, "cl-a").DeleteComparePreset("cp-t"); err != nil {
		t.Fatalf("err: %v", err)
	}
	for _, p := range []string{filepath.Join(b, "cp-t.json"), filepath.Join(b, "cp-t.json.lock"), filepath.Join(sn, "cp-t__loc.json")} {
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

// AC-8
func TestDeleteTrip_EntferntLockDatei(t *testing.T) {
	tmp := t.TempDir()
	writeBriefingPresetFixture(t, tmp, "cl-a", "trip-1", "route", "T")
	lock := filepath.Join(cleanupBriefings(tmp, "cl-a"), "trip-1.json.lock")
	cleanupWrite(t, lock, "")
	if err := New(tmp, "cl-a").DeleteTrip("trip-1"); err != nil {
		t.Fatalf("DeleteTrip: %v", err)
	}
	if cleanupExists(lock) {
		t.Error("trip-1.json.lock muss mit entfernt sein")
	}
}

func TestDeleteTrip_ZweiNutzer(t *testing.T) {
	tmp := t.TempDir()
	for _, u := range []string{"cl-a", "cl-b"} {
		writeBriefingPresetFixture(t, tmp, u, "trip-1", "route", "T")
		cleanupWrite(t, filepath.Join(cleanupBriefings(tmp, u), "trip-1.json.lock"), "")
	}
	if err := New(tmp, "cl-a").DeleteTrip("trip-1"); err != nil {
		t.Fatalf("DeleteTrip: %v", err)
	}
	for _, n := range []string{"trip-1.json", "trip-1.json.lock"} {
		if !cleanupExists(filepath.Join(cleanupBriefings(tmp, "cl-b"), n)) {
			t.Errorf("%s von B muss bleiben", n)
		}
	}
}

// vergleich-Datei ueber den Trip-Pfad: Datei UND Lock bleiben.
func TestDeleteTrip_VergleichBleibtMitLock(t *testing.T) {
	tmp := t.TempDir()
	writeBriefingPresetFixture(t, tmp, "cl-a", "cp-v", "vergleich", "V")
	b := cleanupBriefings(tmp, "cl-a")
	cleanupWrite(t, filepath.Join(b, "cp-v.json.lock"), "")
	if err := New(tmp, "cl-a").DeleteTrip("cp-v"); err != nil {
		t.Fatalf("err: %v", err)
	}
	for _, n := range []string{"cp-v.json", "cp-v.json.lock"} {
		if !cleanupExists(filepath.Join(b, n)) {
			t.Errorf("%s darf nicht entfernt werden", n)
		}
	}
}
