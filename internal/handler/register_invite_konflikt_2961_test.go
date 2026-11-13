package handler

// Issue #2961 Nachbesserung (Gegenpruefung F7, M31b): endet eine Registrierung
// mit Einladung in 409 (Kennung belegt — auch erst bei der exklusiven Anlage),
// bleibt die Einladung offen.

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

func TestRegistrierungMitEinladung_409LaesstEinladungOffen(t *testing.T) {
	s := newTestStore(t)
	inv := store.NewInviteStore(t.TempDir())
	cfg := config.Config{SessionSecret: schalterSecret2961, Env: "staging"}
	h := RegisterHandlerWithInvites(s, bcrypt.DefaultCost, cfg, inv)

	const n = 6
	tokens := make([]string, n)
	for i := range tokens {
		_, tok, err := inv.Create("premium", "", "admin")
		if err != nil {
			t.Fatal(err)
		}
		tokens[i] = tok
	}
	codes := make([]int, n)
	var wg sync.WaitGroup
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			body := `{"username":"einladungsrennen","password":"geheim-pw-123","email":"e` + string(rune('a'+i)) +
				`@beispiel.de","is_test_user":true,"invite":"` + tokens[i] + `"}`
			req := httptest.NewRequest(http.MethodPost, "/api/auth/register", strings.NewReader(body))
			req.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()
			h.ServeHTTP(w, req)
			codes[i] = w.Code
		}(i)
	}
	wg.Wait()
	gewonnen := 0
	for i, c := range codes {
		_, offen := inv.Peek(tokens[i])
		switch c {
		case http.StatusCreated:
			gewonnen++
			if offen {
				t.Errorf("Einladung des Gewinners %d muss eingeloest sein", i)
			}
		case http.StatusConflict:
			if !offen {
				t.Errorf("Anfrage %d endete mit 409, ihre Einladung muss offen bleiben", i)
			}
		default:
			t.Errorf("Anfrage %d: unerwarteter Status %d", i, c)
		}
	}
	if gewonnen != 1 {
		t.Fatalf("genau eine Registrierung darf gewinnen, gewonnen: %d (%v)", gewonnen, codes)
	}
}
