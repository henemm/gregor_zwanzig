package handler

// AC-4: zwei (hier viele) gleichzeitige Registrierungen mit demselben
// Einladungs-Token -- genau ein Konto entsteht, alle anderen bekommen
// 400 invite_invalid. Echter Store und echter InviteStore im TempDir.

import (
	"bytes"
	"fmt"
	"net/http"
	"net/http/httptest"
	"sync"
	"sync/atomic"
	"testing"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

func TestRegisterMitEinladung_ParallelRegistrieren_GenauEinKonto(t *testing.T) {
	s := newTestStore(t)
	inv := store.NewInviteStore(t.TempDir())
	_, token, err := inv.Create("premium", "", "admin")
	if err != nil {
		t.Fatal(err)
	}
	h := RegisterHandlerWithInvites(s, bcrypt.MinCost, config.Config{}, inv)

	const n = 12
	var created, invalid int32
	var wg sync.WaitGroup
	start := make(chan struct{})
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			<-start
			body := fmt.Sprintf(`{"username":"racer%d","password":"geheim-pw-123","email":"racer%d@example.org","invite":%q}`, i, i, token)
			w := httptest.NewRecorder()
			h.ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/api/auth/register", bytes.NewReader([]byte(body))))
			switch {
			case w.Code == http.StatusCreated:
				atomic.AddInt32(&created, 1)
			case w.Code == http.StatusBadRequest && bytes.Contains(w.Body.Bytes(), []byte("invite_invalid")):
				atomic.AddInt32(&invalid, 1)
			default:
				t.Errorf("unerwartet %d: %s", w.Code, w.Body.String())
			}
		}(i)
	}
	close(start)
	wg.Wait()
	if created != 1 || invalid != n-1 {
		t.Fatalf("erwartet 1 Konto und %d invite_invalid, bekommen %d / %d", n-1, created, invalid)
	}
	ids, _ := s.ListUserIDs()
	konten := 0
	for _, id := range ids {
		if len(id) >= 5 && id[:5] == "racer" {
			konten++
			u, _ := s.LoadUser(id)
			if u.Tier != "premium" {
				t.Errorf("Konto %s hat Tier %q", id, u.Tier)
			}
		}
	}
	if konten != 1 {
		t.Errorf("auf der Platte %d Konten statt 1", konten)
	}
}
