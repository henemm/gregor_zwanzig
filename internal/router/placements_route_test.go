package router

// Issue #3122 B2 (T2): die Routen der Tabelle "Was steht wo" am ECHTEN
// Produktions-Router (router.New, AuthMiddleware, Rumpfgrenze) -- dort, wo sie
// wirken. Der Python-Kern ist ein Test-Server, der die Anfrage mitschreibt.

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func TestPlacementsRoutenAmEchtenRouter(t *testing.T) {
	var kernAnfragen, erstanlage []*url.URL
	kern := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "/placements/erstanlage") {
			// #3154: Begleitfeld-Abfrage des PUT (eigene Mitschrift).
			erstanlage = append(erstanlage, r.URL)
			_, _ = w.Write([]byte(`{"show_stability_off": false}`))
			return
		}
		kernAnfragen = append(kernAnfragen, r.URL)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"rows": [], "kern": "antwort"}`))
	}))
	t.Cleanup(kern.Close)
	t.Setenv("PYTHON_CORE_URL", kern.URL)

	r, s, secret := newBriefingTestRouter(t)
	trip := model.Trip{
		ID: "p-route", Name: "Router-Trip",
		Stages: []model.Stage{{ID: "S1", Name: "Tag 1", Date: "2026-08-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "Start", Lat: 47.0, Lon: 11.0, ElevationM: 500}}}},
		DisplayConfig: map[string]interface{}{
			"metrics": []interface{}{map[string]interface{}{"metric_id": "wind", "enabled": true}},
		},
	}
	if err := s.WithUser("userA").SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	datei := filepath.Join(s.DataDir, "users", "userA", "briefings", "p-route.json")
	pfad := "/api/briefings/p-route/placements?kind=route"
	cookieA, cookieB := sessionCookieFor("userA", secret), sessionCookieFor("userB", secret)

	// Ohne Anmeldung: die AuthMiddleware weist ab, nichts erreicht Handler oder Kern.
	for _, m := range []string{http.MethodGet, http.MethodPut} {
		req := httptest.NewRequest(m, pfad, strings.NewReader(`{"version": 1, "rows": []}`))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != http.StatusUnauthorized {
			t.Errorf("%s ohne Anmeldung: Status %d, erwartet 401", m, w.Code)
		}
	}

	// GET als Besitzer: Antwort des Kerns, ETag, user_id aus der Anmeldung.
	w := doBriefingRequest(t, r, http.MethodGet, pfad+"&user_id=userB", nil, cookieA)
	if w.Code != http.StatusOK || !strings.Contains(w.Body.String(), `"kern": "antwort"`) {
		t.Fatalf("GET: %d %s", w.Code, w.Body.String())
	}
	etag := w.Header().Get("ETag")
	if etag == "" {
		t.Errorf("GET ohne ETag")
	}
	if len(kernAnfragen) != 1 || kernAnfragen[0].Path != "/api/briefings/p-route/placements" ||
		kernAnfragen[0].Query().Get("user_id") != "userA" || kernAnfragen[0].Query().Get("kind") != "route" {
		t.Errorf("Anfrage an den Kern: %v", kernAnfragen)
	}

	// Fremder Nutzer: 404 fuer GET und PUT, Datei unveraendert, Kern nicht erreicht.
	vorher, _ := os.ReadFile(datei)
	if w := doBriefingRequest(t, r, http.MethodGet, pfad, nil, cookieB); w.Code != http.StatusNotFound {
		t.Errorf("GET fremd: Status %d, erwartet 404", w.Code)
	}
	if w := doBriefingRequest(t, r, http.MethodPut, pfad, []byte(`{"version": 1, "rows": []}`), cookieB); w.Code != http.StatusNotFound {
		t.Errorf("PUT fremd: Status %d, erwartet 404", w.Code)
	}
	if nachher, _ := os.ReadFile(datei); string(nachher) != string(vorher) || len(kernAnfragen) != 1 {
		t.Errorf("fremder Zugriff hat Datei oder Kern erreicht")
	}

	// PUT als Besitzer mit dem Stempel aus dem GET schreibt; derselbe Stempel danach ist veraltet.
	req := httptest.NewRequest(http.MethodPut, pfad, strings.NewReader(`{"version": 1, "rows": [{"metric_id": "wind"}]}`))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("If-Match", etag)
	req.AddCookie(cookieA)
	wPut := httptest.NewRecorder()
	r.ServeHTTP(wPut, req)
	if wPut.Code != http.StatusOK {
		t.Fatalf("PUT: %d %s", wPut.Code, wPut.Body.String())
	}
	if roh, _ := os.ReadFile(datei); !strings.Contains(string(roh), `"placements"`) {
		t.Errorf("PUT hat placements nicht in die Abo-Datei geschrieben")
	}
	if len(erstanlage) != 1 || erstanlage[0].Query().Get("user_id") != "userA" {
		t.Errorf("Begleitfeld-Abfrage beim Kern: %v", erstanlage)
	}
	req2 := httptest.NewRequest(http.MethodPut, pfad, strings.NewReader(`{"version": 1, "rows": []}`))
	req2.Header.Set("Content-Type", "application/json")
	req2.Header.Set("If-Match", etag)
	req2.AddCookie(cookieA)
	w2 := httptest.NewRecorder()
	r.ServeHTTP(w2, req2)
	if w2.Code != http.StatusPreconditionFailed {
		t.Errorf("PUT mit veraltetem Stempel: Status %d, erwartet 412", w2.Code)
	}
}
