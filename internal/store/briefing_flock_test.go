package store

import (
	"errors"
	"os"
	"path/filepath"
	"syscall"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// Vertrag aus ADR-0083: Go und Python sperren DIESELBE Datei
// data/users/<uid>/briefings/<id>.json.lock per flock(LOCK_EX). Der Pfad wird
// hier bewusst LITERAL zusammengebaut und nicht ueber ein Produktivsymbol
// bezogen -- sonst bewiese der Test nur, dass der Code mit sich selbst einig ist.
func p2158LockPfad(dataDir, uid, id string) string {
	return filepath.Join(dataDir, "users", uid, "briefings", id+".json.lock")
}

// p2158HalteFlock haelt einen FREMDEN flock (eigener fd) und liefert die
// Freigabe-Funktion.
func p2158HalteFlock(t *testing.T, path string) (release func()) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0o600)
	if err != nil {
		t.Fatalf("open lock: %v", err)
	}
	if err := syscall.Flock(int(f.Fd()), syscall.LOCK_EX); err != nil {
		f.Close()
		t.Fatalf("flock: %v", err)
	}
	released := false
	release = func() {
		if !released {
			released = true
			_ = syscall.Flock(int(f.Fd()), syscall.LOCK_UN)
			f.Close()
		}
	}
	t.Cleanup(release)
	return release
}

func p2158Trip(id, name string) *model.Trip {
	return &model.Trip{
		ID: id, Name: name,
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}}}},
	}
}

// AC-6 (#2158), Store-Teil: Haelt ein fremder Prozess (hier: eigener fd) den
// flock auf <id>.json.lock, darf Sperre+Speichern eines Trips NICHT
// abschliessen, bis der fremde Halter freigibt; danach schreibt es.
func TestBriefingFlock_FremderFlockBlockiertSpeichern_FreigabeLaesstDurch(t *testing.T) {
	dir := t.TempDir()
	s := New(dir, "u1")
	release := p2158HalteFlock(t, p2158LockPfad(dir, "u1", "t1"))

	done := make(chan struct{})
	go func() {
		defer close(done)
		unlock := s.LockBriefing("t1")
		defer unlock()
		_ = s.SaveTrip(p2158Trip("t1", "Neu"))
	}()

	select {
	case <-done:
		t.Fatal("Speichern lief durch, obwohl ein fremder flock auf t1.json.lock gehalten wird")
	case <-time.After(500 * time.Millisecond): // nur die Negativpruefung wartet kurz
	}
	release()
	select {
	case <-done:
	case <-time.After(10 * time.Second):
		t.Fatal("Speichern schliesst nach Freigabe des fremden flock nicht ab")
	}
	got, err := s.LoadTrip("t1")
	if err != nil || got == nil || got.Name != "Neu" {
		t.Fatalf("nach Freigabe wurde nicht geschrieben: %v %+v", err, got)
	}
}

// AC-7 (#2158), Go-Seite: Haelt Go LockBriefing, ist die gemeinsame
// Sperrdatei <id>.json.lock fuer einen anderen Prozess (hier: roher
// nicht-blockierender flock) gesperrt -- nach Freigabe wieder frei. Die
// Python-Seite prueft gegen denselben literalen Pfad.
func TestBriefingFlock_GoHaeltLockBriefing_RoherFlockBekommtEWOULDBLOCK(t *testing.T) {
	dir := t.TempDir()
	s := New(dir, "u1")
	path := p2158LockPfad(dir, "u1", "t1")

	unlock := s.LockBriefing("t1")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0o600)
	if err != nil {
		unlock()
		t.Fatalf("open: %v", err)
	}
	defer f.Close()
	ferr := syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB)
	if !errors.Is(ferr, syscall.EWOULDBLOCK) {
		unlock()
		t.Fatalf("LockBriefing haelt den flock auf %s nicht (erwartet EWOULDBLOCK, bekam %v)", path, ferr)
	}
	unlock()
	if err := syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		t.Fatalf("nach unlock() muss der flock frei sein: %v", err)
	}
}

// AC-12 (#2158), Go-Seite: zwei Nutzer, GLEICHE Trip-ID. Nutzer A ist extern
// gesperrt -> A wartet; Nutzer B (eigene Sperrdatei im eigenen Ordner) schreibt
// sofort durch. Endstaende liegen je im richtigen Nutzerordner.
func TestBriefingFlock_ZweiNutzerGleicheTripId_GetrennteSperren(t *testing.T) {
	dir := t.TempDir()
	sA := New(dir, "userA")
	sB := New(dir, "userB")
	releaseA := p2158HalteFlock(t, p2158LockPfad(dir, "userA", "t1"))

	speichere := func(s *Store, name string) chan struct{} {
		done := make(chan struct{})
		go func() {
			defer close(done)
			unlock := s.LockBriefing("t1")
			defer unlock()
			_ = s.SaveTrip(p2158Trip("t1", name))
		}()
		return done
	}
	doneA := speichere(sA, "A")
	doneB := speichere(sB, "B")

	select {
	case <-doneB:
	case <-time.After(3 * time.Second):
		t.Fatal("Nutzer B wurde durch die Sperre von Nutzer A blockiert")
	}
	select {
	case <-doneA:
		t.Fatal("Nutzer A schrieb trotz fremdem flock auf seiner Sperrdatei")
	case <-time.After(300 * time.Millisecond):
	}
	if _, err := os.Stat(p2158LockPfad(dir, "userB", "t1")); err != nil {
		t.Errorf("Nutzer B hat keine eigene Sperrdatei im eigenen Ordner: %v", err)
	}
	releaseA()
	select {
	case <-doneA:
	case <-time.After(10 * time.Second):
		t.Fatal("Nutzer A schliesst nach Freigabe nicht ab")
	}
	a, _ := sA.LoadTrip("t1")
	b, _ := sB.LoadTrip("t1")
	if a == nil || a.Name != "A" || b == nil || b.Name != "B" {
		t.Fatalf("Mandantentrennung verletzt: A=%+v B=%+v", a, b)
	}
}
