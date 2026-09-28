package router

// TDD RED — Issue #2155 Scheibe S2 (Admin-Rolle), AC-6, AC-7.
//
// Spec: docs/specs/modules/admin_rolle_s2_status_token.md
//
// POST /api/debug/trigger-radar-alert (nur bei GZ_ENV=staging registriert)
// steht nicht mehr auf der Public-Allowlist und haengt hinter RequireAdmin.
// Das Proxy-Ziel ist ein httptest-Server, der Aufrufe zaehlt und den
// empfangenen user_id-Query mitschreibt.
//
// RED-Signal heute: /api/debug/ ist Allowlist-Praefix — ohne Sitzung und als
// Nicht-Admin geht die Anfrage durch (200 statt 401/403), und ein
// mitgeschicktes ?user_id=fremde-id erreicht Python unveraendert (ohne
// Auth-Kontext greift appendUserID nicht).
//
// Genau 401 (nicht nur "nicht 200") ohne Sitzung: bliebe das Praefix auf der
// Allowlist und kaeme nur RequireAdmin dazu, liefe RequireAdmin ohne Kontext
// und antwortete 403 — dieser Test faengt diese Halb-Umsetzung.

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
)

const debugPfad = "/api/debug/trigger-radar-alert"

type debugZiel struct {
	mu      sync.Mutex
	aufrufe int
	userIDs []string
	srv     *httptest.Server
}

func neuesDebugZiel(t *testing.T) *debugZiel {
	t.Helper()
	z := &debugZiel{}
	z.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		z.mu.Lock()
		if r.URL.Path == debugPfad {
			z.aufrufe++
			z.userIDs = append(z.userIDs, r.URL.Query().Get("user_id"))
		}
		z.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"sent","from":"python-core"}`))
	}))
	t.Cleanup(z.srv.Close)
	return z
}

func (z *debugZiel) stand() (int, []string) {
	z.mu.Lock()
	defer z.mu.Unlock()
	return z.aufrufe, append([]string(nil), z.userIDs...)
}

// AC-6: ohne Sitzung 401, normaler Nutzer 403 (Ziel unberuehrt), Admin 200.
func TestDebugTrigger_NoSession401_User403_Admin200(t *testing.T) {
	ziel := neuesDebugZiel(t)
	r, secret := s2Router(t, s2Optionen{statusToken: s2Token, admins: "alice", staging: true, pythonZiel: ziel.srv.URL})

	if w := trigger(t, r, secret, http.MethodPost, debugPfad, ""); w.Code != http.StatusUnauthorized {
		t.Errorf("ohne Sitzung: erwartet genau 401, bekommen %d: %s", w.Code, w.Body.String())
	}
	if n, _ := ziel.stand(); n != 0 {
		t.Fatalf("ohne Sitzung darf das Python-Ziel nicht erreicht werden, Zaehler=%d", n)
	}

	w := trigger(t, r, secret, http.MethodPost, debugPfad, "bob")
	if w.Code != http.StatusForbidden {
		t.Errorf("bob (kein Admin): erwartet 403, bekommen %d: %s", w.Code, w.Body.String())
	}
	if got := strings.TrimSpace(w.Body.String()); got != `{"error":"forbidden"}` {
		t.Errorf("bob: Body erwartet %q, bekommen %q", `{"error":"forbidden"}`, got)
	}
	if n, _ := ziel.stand(); n != 0 {
		t.Fatalf("bob darf das Python-Ziel nicht erreichen, Zaehler=%d", n)
	}

	w = trigger(t, r, secret, http.MethodPost, debugPfad, "alice")
	if w.Code != http.StatusOK {
		t.Errorf("alice (Admin): erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), "python-core") {
		t.Errorf("alice: Antwort muss die des Python-Ziels sein, bekommen %q", w.Body.String())
	}
	if n, _ := ziel.stand(); n != 1 {
		t.Errorf("alice: Python-Ziel muss genau 1x erreicht werden, Zaehler=%d", n)
	}
}

// AC-7: ein mitgeschickter user_id-Query wird verworfen — Python bekommt
// ausschliesslich die Kennung der Admin-Sitzung.
func TestDebugTrigger_ForeignUserIDQuery_ReplacedBySessionUser(t *testing.T) {
	ziel := neuesDebugZiel(t)
	r, secret := s2Router(t, s2Optionen{statusToken: s2Token, admins: "alice", staging: true, pythonZiel: ziel.srv.URL})

	for _, pfad := range []string{
		debugPfad + "?user_id=fremde-id",
		debugPfad + "?user_id=default",
		debugPfad + "?user_id=fremde-id&user_id=bob",
	} {
		if w := trigger(t, r, secret, http.MethodPost, pfad, "alice"); w.Code != http.StatusOK {
			t.Errorf("alice %s: erwartet 200, bekommen %d: %s", pfad, w.Code, w.Body.String())
		}
	}
	n, ids := ziel.stand()
	if n != 3 {
		t.Fatalf("erwartet 3 Aufrufe am Python-Ziel, Zaehler=%d", n)
	}
	for i, id := range ids {
		if id != "alice" {
			t.Errorf("Aufruf %d: Python empfing user_id=%q, erwartet ausschliesslich %q (Sitzung)", i+1, id, "alice")
		}
	}
}
