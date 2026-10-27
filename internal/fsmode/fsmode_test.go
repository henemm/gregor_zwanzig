package fsmode

import (
	"os"
	"path/filepath"
	"syscall"
	"testing"
)

func perm(t *testing.T, p string) os.FileMode {
	t.Helper()
	fi, err := os.Stat(p)
	if err != nil {
		t.Fatalf("stat %s: %v", p, err)
	}
	return fi.Mode().Perm()
}

func mitUmask(t *testing.T, m int) {
	t.Helper()
	alt := syscall.Umask(m)
	t.Cleanup(func() { syscall.Umask(alt) })
}

var umasks = []struct {
	name string
	m    int
}{{"umask0077", 0o077}, {"umask0022", 0o022}}

func TestMkdirAll_NeueVerzeichnisseInklusiveElternSind0770(t *testing.T) {
	for _, u := range umasks {
		t.Run(u.name, func(t *testing.T) {
			mitUmask(t, u.m)
			base := t.TempDir()
			ziel := filepath.Join(base, "a", "b", "c")
			if err := MkdirAll(ziel); err != nil {
				t.Fatal(err)
			}
			for _, d := range []string{"a", "a/b", "a/b/c"} {
				if got := perm(t, filepath.Join(base, d)); got != DirMode {
					t.Errorf("%s: %#o, erwartet %#o", d, got, DirMode)
				}
			}
		})
	}
}

func TestMkdirAll_BestehendeVerzeichnisseBleibenUnangetastet(t *testing.T) {
	for _, u := range umasks {
		t.Run(u.name, func(t *testing.T) {
			mitUmask(t, u.m)
			base := t.TempDir()
			alt := filepath.Join(base, "alt")
			if err := os.Mkdir(alt, 0o755); err != nil {
				t.Fatal(err)
			}
			if err := os.Chmod(alt, 0o755); err != nil {
				t.Fatal(err)
			}
			if err := MkdirAll(filepath.Join(alt, "neu")); err != nil {
				t.Fatal(err)
			}
			if got := perm(t, alt); got != 0o755 {
				t.Errorf("Bestandsverzeichnis veraendert: %#o", got)
			}
			if got := perm(t, filepath.Join(alt, "neu")); got != DirMode {
				t.Errorf("neues Verzeichnis: %#o, erwartet %#o", got, DirMode)
			}
			// Aufruf auf bereits bestehendem Ziel: kein Fehler, kein Chmod.
			if err := MkdirAll(alt); err != nil {
				t.Fatal(err)
			}
			if got := perm(t, alt); got != 0o755 {
				t.Errorf("Bestandsverzeichnis nach zweitem Aufruf: %#o", got)
			}
		})
	}
}

func TestOpenFile_NeueDateiIst0660(t *testing.T) {
	for _, u := range umasks {
		t.Run(u.name, func(t *testing.T) {
			mitUmask(t, u.m)
			p := filepath.Join(t.TempDir(), "x.lock")
			f, err := OpenFile(p, os.O_RDWR)
			if err != nil {
				t.Fatal(err)
			}
			f.Close()
			if got := perm(t, p); got != FileMode {
				t.Errorf("neue Datei: %#o, erwartet %#o", got, FileMode)
			}
		})
	}
}

func TestOpenFile_BestehendeDateiBehaeltModusUndInhalt(t *testing.T) {
	for _, u := range umasks {
		t.Run(u.name, func(t *testing.T) {
			mitUmask(t, u.m)
			p := filepath.Join(t.TempDir(), "alt.jsonl")
			if err := os.WriteFile(p, []byte("bestand\n"), 0o644); err != nil {
				t.Fatal(err)
			}
			if err := os.Chmod(p, 0o644); err != nil {
				t.Fatal(err)
			}
			f, err := OpenFile(p, os.O_APPEND|os.O_WRONLY)
			if err != nil {
				t.Fatalf("bestehende Datei: %v", err)
			}
			if _, err := f.Write([]byte("neu\n")); err != nil {
				t.Fatal(err)
			}
			f.Close()
			if got := perm(t, p); got != 0o644 {
				t.Errorf("Bestandsdatei veraendert: %#o", got)
			}
			raw, _ := os.ReadFile(p)
			if string(raw) != "bestand\nneu\n" {
				t.Errorf("Inhalt: %q", raw)
			}
		})
	}
}
