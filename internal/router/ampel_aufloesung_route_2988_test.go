package router

// Issue #2988 S2 (Spec rework_2988_ampel_ableitung, AC-7): die Aufloesungs-Route
// am ECHTEN Produktions-Router (AuthMiddleware, Rumpfgrenze, zwei Nutzer). Der
// Python-Kern ist ein Test-Server, der Methode, Pfad und user_id mitschreibt.
//
//   go test ./internal/router/ -run 2988

import (
	"io/fs"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"reflect"
	"strings"
	"sync"
	"testing"
)

func dateien2988(t *testing.T, wurzel string) []string {
	t.Helper()
	var namen []string
	if err := filepath.WalkDir(wurzel, func(p string, d fs.DirEntry, err error) error {
		if err == nil && !d.IsDir() {
			namen = append(namen, p)
		}
		return err
	}); err != nil {
		t.Fatal(err)
	}
	return namen
}

func TestAmpelAufloesungRouteAmEchtenRouter2988(t *testing.T) {
	var mu sync.Mutex
	var nutzer, ziele []string
	kern := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		ziele = append(ziele, r.Method+" "+r.URL.Path)
		nutzer = append(nutzer, strings.Join(r.URL.Query()["user_id"], ","))
		mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ergebnisse": []}`))
	}))
	t.Cleanup(kern.Close)
	t.Setenv("PYTHON_CORE_URL", kern.URL)

	r, s, secret := newBriefingTestRouter(t)
	const pfad = "/api/ampel/aufloesung"
	rumpf := []byte(`{"eintraege": [{"ampel": {"template": "wandern"}}]}`)

	req := httptest.NewRequest(http.MethodPost, pfad, strings.NewReader(string(rumpf)))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusUnauthorized {
		t.Errorf("ohne Anmeldung: Status %d, erwartet 401", w.Code)
	}
	if len(ziele) != 0 {
		t.Fatalf("Kern ohne Anmeldung erreicht: %v", ziele)
	}

	vorher := dateien2988(t, s.DataDir)
	for _, id := range []string{"userA", "userB"} {
		w := doBriefingRequest(t, r, http.MethodPost, pfad+"?user_id=default", rumpf, sessionCookieFor(id, secret))
		if w.Code != http.StatusOK || w.Body.String() != `{"ergebnisse": []}` {
			t.Fatalf("%s: %d %s", id, w.Code, w.Body.String())
		}
	}
	if want := []string{"POST " + pfad, "POST " + pfad}; !reflect.DeepEqual(ziele, want) {
		t.Errorf("Kern-Aufrufe %v, erwartet %v", ziele, want)
	}
	if want := []string{"userA", "userB"}; !reflect.DeepEqual(nutzer, want) {
		t.Errorf("user_id am Kern %v, erwartet %v", nutzer, want)
	}
	if nachher := dateien2988(t, s.DataDir); !reflect.DeepEqual(nachher, vorher) {
		t.Errorf("Aufloesung hat Dateien angelegt oder entfernt: vorher %v, nachher %v", vorher, nachher)
	}

	// 300 KB liegen unter der globalen Grenze (1 MB), aber ueber der des Endpunkts.
	gross := []byte(`{"eintraege": [], "pad": "` + strings.Repeat("x", 300*1024) + `"}`)
	if w := doBriefingRequest(t, r, http.MethodPost, pfad, gross, sessionCookieFor("userA", secret)); w.Code != http.StatusRequestEntityTooLarge {
		t.Errorf("300 KB: Status %d, erwartet 413", w.Code)
	}
	if len(ziele) != 2 {
		t.Errorf("zu grosser Rumpf hat den Kern erreicht: %v", ziele)
	}
}
