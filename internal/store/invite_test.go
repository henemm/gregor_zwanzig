package store

// Admin-Einladungslinks (Spec admin_einladungslinks_2519): globaler
// InviteStore mit Hash-Speicherung und atomarer Einloesung. Echte Dateien
// im TempDir, kein Mock.

import (
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
)

func neuerInviteStore(t *testing.T) (*InviteStore, string) {
	t.Helper()
	dir := t.TempDir()
	return NewInviteStore(dir), dir
}

func TestInviteStore_TokenWirdNurAlsHashGespeichert(t *testing.T) {
	st, dir := neuerInviteStore(t)
	inv, token, err := st.Create("standard", "Tante Erna", "alice")
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if token == "" || len(token) < 32 {
		t.Fatalf("Token zu kurz/leer: %q", token)
	}
	raw, err := os.ReadFile(filepath.Join(dir, "invites.json"))
	if err != nil {
		t.Fatalf("invites.json fehlt: %v", err)
	}
	if strings.Contains(string(raw), token) {
		t.Errorf("Token-Klartext steht in invites.json")
	}
	sum := sha256.Sum256([]byte(token))
	if want := hex.EncodeToString(sum[:]); !strings.Contains(string(raw), want) || inv.TokenHash != want {
		t.Errorf("Hash in Datei/Datensatz ist nicht SHA-256 des Tokens (want %s)", want)
	}
	if inv.Tier != "standard" || inv.Note != "Tante Erna" || inv.CreatedBy != "alice" || inv.ID == "" {
		t.Errorf("Datensatz unvollstaendig: %+v", inv)
	}
}

func TestInviteStore_UeberlebtNeustart(t *testing.T) {
	st, dir := neuerInviteStore(t)
	_, token, _ := st.Create("premium", "", "alice")
	st2 := NewInviteStore(dir)
	if _, ok := st2.Peek(token); !ok {
		t.Errorf("offene Einladung nach Neustart nicht mehr gefunden")
	}
	if got := st2.List(); len(got) != 1 {
		t.Errorf("List nach Neustart: %d Eintraege, erwartet 1", len(got))
	}
}

func TestInviteStore_RedeemNurEinmal_UndRollbackGibtFrei(t *testing.T) {
	st, _ := neuerInviteStore(t)
	inv, token, _ := st.Create("premium", "", "alice")
	got, ok, err := st.Redeem(token, "neu1")
	if err != nil || !ok || got.Tier != "premium" {
		t.Fatalf("erste Einloesung: ok=%v err=%v inv=%+v", ok, err, got)
	}
	if _, ok, _ := st.Redeem(token, "neu2"); ok {
		t.Errorf("zweite Einloesung darf scheitern")
	}
	if _, ok := st.Peek(token); ok {
		t.Errorf("benutzte Einladung darf nicht mehr offen sein")
	}
	if err := st.Rollback(inv.ID); err != nil {
		t.Fatalf("Rollback: %v", err)
	}
	if _, ok := st.Peek(token); !ok {
		t.Errorf("nach Rollback muss die Einladung wieder offen sein")
	}
	if _, ok, _ := st.Redeem(token, "neu3"); !ok {
		t.Errorf("nach Rollback wieder einloesbar")
	}
}

func TestInviteStore_UnbekanntesUndWiderrufenesTokenWirdAbgelehnt(t *testing.T) {
	st, _ := neuerInviteStore(t)
	inv, token, _ := st.Create("free", "", "alice")
	if _, ok, _ := st.Redeem("gibt-es-nicht", "x"); ok {
		t.Errorf("unbekanntes Token eingeloest")
	}
	if err := st.Revoke(inv.ID); err != nil {
		t.Fatalf("Revoke: %v", err)
	}
	if _, ok, _ := st.Redeem(token, "x"); ok {
		t.Errorf("widerrufenes Token eingeloest")
	}
	if _, ok := st.Peek(token); ok {
		t.Errorf("widerrufenes Token gilt als offen")
	}
}

func TestInviteStore_RevokeBenutzteEinladungIstFehler(t *testing.T) {
	st, _ := neuerInviteStore(t)
	inv, token, _ := st.Create("free", "", "alice")
	if _, ok, _ := st.Redeem(token, "neu"); !ok {
		t.Fatal("Einloesung")
	}
	if err := st.Revoke(inv.ID); err != ErrInviteUsed {
		t.Errorf("Revoke benutzt: erwartet ErrInviteUsed, bekommen %v", err)
	}
	if err := st.Revoke("unbekannt"); err != ErrInviteNotFound {
		t.Errorf("Revoke unbekannt: erwartet ErrInviteNotFound, bekommen %v", err)
	}
}

// AC-4: N Goroutinen loesen dasselbe Token ein -- genau eine gewinnt.
func TestInviteStore_ParallelEinloesen_GenauEinGewinner(t *testing.T) {
	st, dir := neuerInviteStore(t)
	_, token, _ := st.Create("premium", "", "alice")
	const n = 50
	var wins int32
	var wg sync.WaitGroup
	start := make(chan struct{})
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			<-start
			if _, ok, err := st.Redeem(token, "u"+string(rune('a'+i%26))+string(rune('a'+i/26))); ok && err == nil {
				atomic.AddInt32(&wins, 1)
			}
		}(i)
	}
	close(start)
	wg.Wait()
	if wins != 1 {
		t.Errorf("erwartet genau 1 Gewinner, bekommen %d", wins)
	}
	if got := NewInviteStore(dir).List(); len(got) != 1 || got[0].UsedBy == "" {
		t.Errorf("persistierter Zustand: %+v", got)
	}
}
