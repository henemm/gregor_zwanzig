package router

// Issue #3304 (Teil A von #3041; Spec feat_3304_was_steht_wo_vorschau, AC-6,
// AC-8, AC-9, AC-10): die Vorschau-Route der Tabelle "Was steht wo" am ECHTEN
// Produktions-Router (router.New, AuthMiddleware, Rumpfgrenze). Der
// Python-Kern ist ein Test-Server, der Methode, Pfad und Query mitschreibt.
//
//   go test ./internal/router/ -run 3304

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

type kernAufruf3304 struct{ methode, pfad, userID, kind string }

func TestPlacementsVorschauRouteAmEchtenRouter3304(t *testing.T) {
	var mu sync.Mutex
	var aufrufe []kernAufruf3304
	kern := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		aufrufe = append(aufrufe, kernAufruf3304{r.Method, r.URL.Path,
			r.URL.Query().Get("user_id"), r.URL.Query().Get("kind")})
		mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"stored": false, "kern": "antwort"}`))
	}))
	t.Cleanup(kern.Close)
	t.Setenv("PYTHON_CORE_URL", kern.URL)

	r, s, secret := newBriefingTestRouter(t)
	// AC-10: ein Abo mit der Kennung "placements" darf den Vorschau-Pfad nicht kapern.
	trip := model.Trip{
		ID: "placements", Name: "Trip namens placements",
		Stages: []model.Stage{{ID: "S1", Name: "Tag 1", Date: "2026-08-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "Start", Lat: 47.0, Lon: 11.0, ElevationM: 500}}}},
	}
	if err := s.WithUser("userA").SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	datei := filepath.Join(s.DataDir, "users", "userA", "briefings", "placements.json")
	vorher, _ := os.ReadFile(datei)
	cookieA := sessionCookieFor("userA", secret)
	entwurf := []byte(`{"id": "neu", "name": "Entwurf", "user_id": "userB",
		"stages": [{"id": "S1", "name": "D1", "date": "2026-08-01",
		"waypoints": [{"id": "W1", "name": "P", "lat": 47.0, "lon": 11.0, "elevation_m": 500}]}]}`)
	pfad := "/api/briefings/placements/vorschau"

	// AC-6: ohne Anmeldung weist die AuthMiddleware ab, der Kern bleibt unberuehrt.
	req := httptest.NewRequest(http.MethodPost, pfad+"?kind=route", strings.NewReader(string(entwurf)))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusUnauthorized {
		t.Errorf("ohne Anmeldung: Status %d, erwartet 401", w.Code)
	}
	if len(aufrufe) != 0 {
		t.Fatalf("Kern ohne Anmeldung erreicht: %v", aufrufe)
	}

	// AC-10 / AC-5: angemeldet -> Vorschau-Handler, POST an den Kern-Pfad der
	// Vorschau mit user_id aus der Anmeldung; nie als Abo "placements" gelesen.
	for _, kind := range []string{"route", "vergleich"} {
		w := doBriefingRequest(t, r, http.MethodPost, pfad+"?kind="+kind+"&user_id=userB", entwurf, cookieA)
		if w.Code != http.StatusOK || !strings.Contains(w.Body.String(), `"kern": "antwort"`) {
			t.Fatalf("Vorschau %s: %d %s", kind, w.Code, w.Body.String())
		}
		if et := w.Header().Get("ETag"); et != "" {
			t.Errorf("Vorschau %s mit ETag %q", kind, et)
		}
	}
	if len(aufrufe) != 2 {
		t.Fatalf("Kern-Aufrufe %v, erwartet zwei Vorschauen", aufrufe)
	}
	for i, kind := range []string{"route", "vergleich"} {
		a := aufrufe[i]
		if a.methode != http.MethodPost || a.pfad != pfad || a.userID != "userA" || a.kind != kind {
			t.Errorf("Kern-Aufruf %d: %+v, erwartet POST %s user_id=userA kind=%s", i, a, pfad, kind)
		}
		if a.pfad == "/api/briefings/placements/placements" {
			t.Errorf("Vorschau als Abo \"placements\" gelesen")
		}
	}

	// AC-8: 300 KB liegen unter der globalen Grenze (1 MB), aber ueber der
	// Grenze der Vorschau (256 KB) -> 413 ohne Kern-Aufruf.
	gross := []byte(`{"pad": "` + strings.Repeat("x", 300*1024) + `"}`)
	if w := doBriefingRequest(t, r, http.MethodPost, pfad+"?kind=route", gross, cookieA); w.Code != http.StatusRequestEntityTooLarge {
		t.Errorf("300 KB: Status %d, erwartet 413", w.Code)
	}
	if len(aufrufe) != 2 {
		t.Errorf("zu grosser Koerper hat den Kern erreicht: %v", aufrufe[2:])
	}

	// AC-9: der GET-Weg des Abos "placements" bleibt der GET-Weg (mit ETag),
	// und keine Vorschau hat die Datei veraendert.
	wGet := doBriefingRequest(t, r, http.MethodGet, "/api/briefings/placements/placements?kind=route", nil, cookieA)
	if wGet.Code != http.StatusOK || wGet.Header().Get("ETag") == "" {
		t.Errorf("GET des Abos placements: %d ETag=%q", wGet.Code, wGet.Header().Get("ETag"))
	}
	if len(aufrufe) != 3 || aufrufe[2].methode != http.MethodGet ||
		aufrufe[2].pfad != "/api/briefings/placements/placements" {
		t.Errorf("GET des Abos placements am Kern: %v", aufrufe)
	}
	if nachher, _ := os.ReadFile(datei); string(nachher) != string(vorher) {
		t.Errorf("Vorschau hat die Abo-Datei veraendert")
	}
}
