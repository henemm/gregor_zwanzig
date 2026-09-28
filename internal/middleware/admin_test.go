package middleware

// TDD RED — Issue #2155 Scheibe S1 (Admin-Rolle), AC-4 + AC-5.
//
// Spec: docs/specs/modules/admin_rolle_s1.md § "2. Middleware RequireAdmin"
//
// Scheitert heute beim Uebersetzen: RequireAdmin existiert noch nicht.
// Echte http-Handler und ResponseRecorder, kein Mock. Die Nutzerkennung kommt
// wie in Produktion aus dem Auth-Kontext (ContextWithUserID).

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// adminGate baut Middleware + Zaehler-Handler; der Zaehler beweist, ob der
// geschuetzte Handler erreicht wurde.
func adminGate(admins map[string]struct{}) (http.Handler, *int) {
	calls := 0
	inner := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"ok"}`))
	})
	return RequireAdmin(admins)(inner), &calls
}

func doAs(h http.Handler, userID string, withUser bool) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodPost, "/api/scheduler/trip-reports", nil)
	if withUser {
		req = req.WithContext(ContextWithUserID(req.Context(), userID))
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	return w
}

func TestRequireAdmin_Admin_PassesThrough(t *testing.T) {
	h, calls := adminGate(map[string]struct{}{"alice": {}})

	w := doAs(h, "alice", true)

	if w.Code != http.StatusOK {
		t.Fatalf("Admin: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if *calls != 1 {
		t.Fatalf("Admin: geschuetzter Handler muss genau 1x laufen, lief %dx", *calls)
	}
}

func TestRequireAdmin_NormalUser_Gets403JSON_HandlerNotCalled(t *testing.T) {
	h, calls := adminGate(map[string]struct{}{"alice": {}})

	w := doAs(h, "bob", true)

	if w.Code != http.StatusForbidden {
		t.Fatalf("normaler Nutzer: erwartet 403, bekommen %d", w.Code)
	}
	if got := strings.TrimSpace(w.Body.String()); got != `{"error":"forbidden"}` {
		t.Errorf("Body: erwartet %q, bekommen %q", `{"error":"forbidden"}`, got)
	}
	if ct := w.Header().Get("Content-Type"); !strings.HasPrefix(ct, "application/json") {
		t.Errorf("Content-Type: erwartet application/json, bekommen %q", ct)
	}
	if *calls != 0 {
		t.Fatalf("geschuetzter Handler darf NICHT laufen, lief %dx", *calls)
	}
}

// AC-4: leere Menge => niemand kommt durch (fail-closed).
func TestRequireAdmin_EmptySet_EveryoneForbidden(t *testing.T) {
	for name, admins := range map[string]map[string]struct{}{
		"leere Menge": {},
		"nil":         nil,
	} {
		h, calls := adminGate(admins)
		for _, uid := range []string{"alice", "bob", "default", "ops"} {
			if w := doAs(h, uid, true); w.Code != http.StatusForbidden {
				t.Errorf("%s / %q: erwartet 403, bekommen %d", name, uid, w.Code)
			}
		}
		if *calls != 0 {
			t.Errorf("%s: geschuetzter Handler darf nie laufen, lief %dx", name, *calls)
		}
	}
}

// AC-5: leere Kennung => 403, auch wenn (fehlerhaft) ein leerer Schluessel in der Menge steht.
func TestRequireAdmin_EmptyUserID_Forbidden_EvenIfSetContainsEmptyKey(t *testing.T) {
	h, calls := adminGate(map[string]struct{}{"alice": {}, "": {}})

	if w := doAs(h, "", true); w.Code != http.StatusForbidden {
		t.Errorf("leere Kennung im Kontext: erwartet 403, bekommen %d", w.Code)
	}
	if w := doAs(h, "", false); w.Code != http.StatusForbidden {
		t.Errorf("kein Auth-Kontext: erwartet 403, bekommen %d", w.Code)
	}
	if *calls != 0 {
		t.Fatalf("geschuetzter Handler darf nie laufen, lief %dx", *calls)
	}
}

// AC-5: exakter Vergleich — Praefix, Erweiterung und andere Schreibweise sind keine Admins.
func TestRequireAdmin_ExactMatchOnly(t *testing.T) {
	h, calls := adminGate(map[string]struct{}{"alice": {}})

	for _, uid := range []string{"ali", "alice2", "Alice", "ALICE", " alice", "alice "} {
		if w := doAs(h, uid, true); w.Code != http.StatusForbidden {
			t.Errorf("%q: erwartet 403, bekommen %d", uid, w.Code)
		}
	}
	if *calls != 0 {
		t.Fatalf("geschuetzter Handler darf nie laufen, lief %dx", *calls)
	}
}
