package scheduler

// Issue #2624 AC-4: die Lauf-Zustandsdatei je Nutzer entsteht mit 0660,
// auch unter Prod-Umask 0077.

import (
	"os"
	"path/filepath"
	"syscall"
	"testing"
)

func TestDateimodi_UserRunState_0660_UnterUmask077(t *testing.T) {
	alt := syscall.Umask(0o077)
	defer syscall.Umask(alt)
	dir := t.TempDir()
	u := newUserRunState(dir)
	u.Record("job", "alice", "ok", "")

	p := filepath.Join(dir, schedulerUserStateFileName)
	fi, err := os.Stat(p)
	if err != nil {
		t.Fatalf("Zustandsdatei nicht geschrieben: %v", err)
	}
	if got := fi.Mode().Perm(); got != 0o660 {
		t.Errorf("Zustandsdatei: %#o, erwartet 0660", got)
	}
}
