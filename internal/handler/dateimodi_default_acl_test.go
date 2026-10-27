package handler

// Issue #2624 AC-4: die Telegram-Token-Datei entsteht ueber CreateTemp (0600)
// und muss vor dem Umbenennen auf 0660 gesetzt werden.

import (
	"os"
	"path/filepath"
	"syscall"
	"testing"
)

func TestDateimodi_TelegramTokenDatei_0660_UnterUmask077(t *testing.T) {
	alt := syscall.Umask(0o077)
	defer syscall.Umask(alt)
	dir := t.TempDir()
	ts := NewTelegramTokenStore(dir)
	if _, err := ts.IssueToken("alice"); err != nil {
		t.Fatalf("IssueToken: %v", err)
	}
	fi, err := os.Stat(filepath.Join(dir, "telegram_tokens.json"))
	if err != nil {
		t.Fatal(err)
	}
	if got := fi.Mode().Perm(); got != 0o660 {
		t.Errorf("Token-Datei: %#o, erwartet 0660", got)
	}
}
