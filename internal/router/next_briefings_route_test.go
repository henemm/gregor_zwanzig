package router

// Issue #1969 (Nächstes Briefing), AC-13 (Router-Teil).
// SPEC: docs/specs/modules/feat_1969_naechstes_briefing.md
//
// Verdrahtungs-Nachweis ueber den ECHTEN Produktions-Router (inkl. globaler
// AuthMiddleware und echter Session-Cookies). Reihenfolge ist Absicht: der
// anonyme 401 waere auch OHNE Route gruen (AuthMiddleware greift global) —
// erst der authentifizierte Aufruf, der den Fake erreichen muss, beweist die
// Route.

import (
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

func TestNextBriefingsRoute_WiredAuthenticatedAndUserIsolated_AC13(t *testing.T) {
	var mu sync.Mutex
	var seen []url.Values
	py := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/_internal/next-briefings" {
			http.NotFound(w, r)
			return
		}
		mu.Lock()
		seen = append(seen, r.URL.Query())
		mu.Unlock()
		uid := r.URL.Query().Get("user_id")
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"trips":{"trip-`+uid+`":{"at":null,"reason":"paused"}},"compare":{"preset-`+uid+`":{"at":null,"reason":"manual"}}}`)
	}))
	defer py.Close()

	r, cfg, s := newCoreAuthSweepRouter(t, py.URL)
	for _, uid := range []string{"nbUserA", "nbUserB"} {
		if err := s.SaveUser(model.User{ID: uid, CreatedAt: time.Now()}); err != nil {
			t.Fatalf("SaveUser %s: %v", uid, err)
		}
		if err := s.AddSession(uid, sessionIDFor(uid)); err != nil {
			t.Fatalf("AddSession %s: %v", uid, err)
		}
	}
	get := func(uid, path string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(http.MethodGet, path, nil)
		if uid != "" {
			req.AddCookie(sessionCookieFor(uid, cfg.SessionSecret))
		}
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		return w
	}

	// 1) A authentifiziert, mit manipulierter Query ?user_id=B.
	w := get("nbUserA", "/api/next-briefings?user_id=nbUserB")
	if w.Code == http.StatusNotFound || w.Code == http.StatusMethodNotAllowed {
		t.Fatalf("VERDRAHTUNG FEHLT: GET /api/next-briefings antwortet %d — Route nicht im Produktions-Router: %s", w.Code, w.Body.String())
	}
	if w.Code != http.StatusOK {
		t.Fatalf("200 erwartet, %d bekommen: %s", w.Code, w.Body.String())
	}
	body := w.Body.String()
	if !strings.Contains(body, "trip-nbUserA") || !strings.Contains(body, "preset-nbUserA") {
		t.Errorf("Antwort muss die IDs von A tragen: %s", body)
	}
	if strings.Contains(body, "nbUserB") {
		t.Errorf("A sieht eine ID von B (Cross-User-Leck): %s", body)
	}
	mu.Lock()
	if len(seen) != 1 || len(seen[0]["user_id"]) != 1 || seen[0].Get("user_id") != "nbUserA" {
		t.Errorf("Python-Core muss genau einmal mit user_id=nbUserA gerufen werden, bekam %v", seen)
	}
	seen = nil
	mu.Unlock()

	// 2) B sieht seine eigenen IDs, keine von A.
	wB := get("nbUserB", "/api/next-briefings")
	if wB.Code != http.StatusOK {
		t.Fatalf("B: 200 erwartet, %d bekommen: %s", wB.Code, wB.Body.String())
	}
	if !strings.Contains(wB.Body.String(), "trip-nbUserB") || strings.Contains(wB.Body.String(), "nbUserA") {
		t.Errorf("B muss genau seine IDs sehen: %s", wB.Body.String())
	}
	mu.Lock()
	seen = nil
	mu.Unlock()

	// 3) Ohne Session: 401, der Python-Core wird nie erreicht (kein "default").
	wAnon := get("", "/api/next-briefings?user_id=nbUserB")
	if wAnon.Code != http.StatusUnauthorized {
		t.Errorf("ohne Session 401 erwartet, %d bekommen: %s", wAnon.Code, wAnon.Body.String())
	}
	mu.Lock()
	defer mu.Unlock()
	if len(seen) != 0 {
		t.Errorf("ohne Session darf der Python-Core nicht gerufen werden, bekam %v", seen)
	}
}
