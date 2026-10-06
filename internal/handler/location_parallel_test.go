package handler

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// Gemeinsame Helfer der #2158-Handler-Wettlauftests (Namenspraefix p2158,
// damit nichts mit bestehenden Helfern kollidiert).

// p2158Do ruft h unter der Kennung user mit method/pattern/url auf.
func p2158Do(h http.HandlerFunc, method, pattern, url, body, user string) *httptest.ResponseRecorder {
	w := httptest.NewRecorder()
	p2158DoW(w, h, method, pattern, url, body, user)
	return w
}

// p2158DoW wie p2158Do, aber mit frei waehlbarem ResponseWriter (Sonden).
func p2158DoW(w http.ResponseWriter, h http.HandlerFunc, method, pattern, url, body, user string) {
	r := chi.NewRouter()
	r.Method(method, pattern, h)
	req := httptest.NewRequest(method, url, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, user)
	r.ServeHTTP(w, req)
}

// p2158Parallel startet alle fns hinter EINER Startbarriere (Kanal, kein
// Sleep) und wartet auf alle. Eine Verklemmung endet nach limit als Fehler.
func p2158Parallel(t *testing.T, limit time.Duration, fns ...func()) {
	t.Helper()
	start := make(chan struct{})
	var wg sync.WaitGroup
	for _, fn := range fns {
		wg.Add(1)
		go func(f func()) {
			defer wg.Done()
			<-start
			f()
		}(fn)
	}
	close(start)
	done := make(chan struct{})
	go func() { wg.Wait(); close(done) }()
	select {
	case <-done:
	case <-time.After(limit):
		t.Fatalf("Vorgaenge nicht innerhalb %v fertig -- Verklemmung?", limit)
	}
}

// AC-1 (#2158): PATCH (group_id) und mehrere PUT-Wetter-Konfigurationen
// desselben Orts laufen gleichzeitig mit DISJUNKTEN Feldern. Ohne Orts-Sperre
// laden alle denselben Stand und der letzte Schreiber ueberschreibt die
// anderen (Lost Update). Der Endstand muss ALLE Aenderungen enthalten.
func TestLocationParallel_PatchUndPutWeatherConfig_KeinLostUpdate(t *testing.T) {
	const iterationen = 150
	const schreiber = 8
	s := store.New(t.TempDir(), "u1")
	verloren := 0
	for it := 0; it < iterationen; it++ {
		id := fmt.Sprintf("ort-%d", it)
		if err := s.SaveLocation(model.Location{ID: id, Name: "Ort", Lat: 47, Lon: 11}); err != nil {
			t.Fatalf("seed: %v", err)
		}
		gid := fmt.Sprintf("g-%d", it)
		fns := []func(){func() {
			w := p2158Do(PatchLocationHandler(s), "PATCH", "/api/locations/{id}", "/api/locations/"+id,
				fmt.Sprintf(`{"group_id":%q}`, gid), "u1")
			if w.Code != 200 {
				t.Errorf("PATCH: %d %s", w.Code, w.Body.String())
			}
		}}
		for k := 0; k < schreiber; k++ {
			k := k
			fns = append(fns, func() {
				w := p2158Do(PutLocationWeatherConfigHandler(s), "PUT", "/api/locations/{id}/weather-config",
					"/api/locations/"+id+"/weather-config", fmt.Sprintf(`{"feld%d":%d}`, k, k), "u1")
				if w.Code != 200 {
					t.Errorf("PUT weather-config: %d %s", w.Code, w.Body.String())
				}
			})
		}
		p2158Parallel(t, 30*time.Second, fns...)

		loc, err := s.LoadLocation(id)
		if err != nil || loc == nil {
			t.Fatalf("laden: %v", err)
		}
		fehlt := []string{}
		if loc.GroupID == nil || *loc.GroupID != gid {
			fehlt = append(fehlt, "group_id")
		}
		for k := 0; k < schreiber; k++ {
			if _, ok := loc.DisplayConfig[fmt.Sprintf("feld%d", k)]; !ok {
				fehlt = append(fehlt, fmt.Sprintf("feld%d", k))
			}
		}
		if len(fehlt) > 0 {
			verloren++
			if verloren <= 3 {
				t.Logf("Iteration %d: Aenderung(en) verloren: %v", it, fehlt)
			}
		}
	}
	if verloren > 0 {
		t.Errorf("Lost Update in %d von %d Durchlaeufen", verloren, iterationen)
	}
}
