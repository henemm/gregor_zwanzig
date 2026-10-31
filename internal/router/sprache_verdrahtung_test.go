package router

// Issue #2675 (i18n G1) — Verdrahtung der Sprach-Middleware im ECHTEN Router.
// Spec: docs/specs/modules/i18n_g1_go_kern_2675.md — AC-1, AC-2 (Adversary F001).
//
// Faengt die Mutation "r.Use(authmw.Lang(deps.Store)) entfernt": ohne die
// Middleware faellt jede Fehlermeldung auf Deutsch zurueck. Echter
// router.New, echter Store in t.TempDir(), echte Sitzungen, kein Mock.

import (
	"encoding/json"
	"net/http"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

func TestRouterFehlermeldungInNutzersprache(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	for id, lang := range map[string]string{"lang-anna": "en", "lang-carl": ""} {
		if err := s.SaveUser(model.User{ID: id, CreatedAt: time.Now(), Language: lang}); err != nil {
			t.Fatalf("SaveUser %s: %v", id, err)
		}
		if err := s.AddSession(id, sessionIDFor(id)); err != nil {
			t.Fatalf("AddSession %s: %v", id, err)
		}
	}
	cases := []struct{ uid, want string }{
		{"lang-anna", "Not found."},
		{"lang-carl", "Nicht gefunden."},
	}
	for _, tc := range cases {
		w := doBriefingRequest(t, r, http.MethodGet, "/api/briefings/unbekannt?kind=route", nil, sessionCookieFor(tc.uid, secret))
		if w.Code != http.StatusNotFound {
			t.Fatalf("%s: Status %d, erwartet 404 (%s)", tc.uid, w.Code, w.Body.String())
		}
		var body map[string]any
		if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
			t.Fatalf("%s: kein JSON: %v (%s)", tc.uid, err, w.Body.String())
		}
		if body["message"] != tc.want || body["code"] != "not_found" || body["error"] != "not_found" {
			t.Errorf("%s: Body %v, erwartet message %q und code/error not_found", tc.uid, body, tc.want)
		}
	}
}
