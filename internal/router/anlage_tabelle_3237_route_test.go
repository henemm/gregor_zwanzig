package router

// Issue #3237 (Spec feat_3237_altpfad_entfernen, AC-2, Adversary Lauf 2 F001):
// JEDE Anlage-Route am ECHTEN Produktions-Router (router.New mit
// PythonCoreURL aus der Konfiguration) schreibt die Tabelle "Was steht wo"
// aus dem Kern: POST /api/compare/presets (so legt die Oberflaeche einen
// Orts-Vergleich an) und POST /api/briefings fuer kind=route UND
// kind=vergleich. Der Kern ist ein Test-Server mit fester Antwort, der
// mitschreibt, was ankommt -- keine Fachlogik. Zwei Nutzer je Route.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
)

const kernTabelle3237Router = `{"placements": {"version": 1, "rows": [
  {"metric_id": "wind", "places": {"email": true, "telegram": true, "sms": false, "outlook": true}}],
  "outlook_reports": ["morning"], "kern_marke": "router-3237"}}`

func TestAnlage3237AlleAnlageRoutenAmEchtenRouterSchreibenKernTabelle(t *testing.T) {
	var mu sync.Mutex
	var anfragen []*url.URL
	kern := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		anfragen = append(anfragen, r.URL)
		mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		if strings.HasSuffix(r.URL.Path, "/placements/erstanlage") {
			_, _ = w.Write([]byte(kernTabelle3237Router))
			return
		}
		_, _ = w.Write([]byte(`{}`))
	}))
	t.Cleanup(kern.Close)
	t.Setenv("PYTHON_CORE_URL", kern.URL)

	r, s, secret := newBriefingTestRouter(t)

	faelle := []struct {
		name, pfad, kind string
		body             func(nutzer string) []byte
	}{
		{"compare-presets", "/api/compare/presets", "vergleich", func(string) []byte {
			return []byte(quotePresetJSON("Router 3237"))
		}},
		{"briefings-route", "/api/briefings", "route", func(nutzer string) []byte {
			return minimalRouteCreateBody("r3237-"+nutzer, "Router 3237")
		}},
		{"briefings-vergleich", "/api/briefings", "vergleich", func(string) []byte {
			return minimalVergleichCreateBody("Router 3237")
		}},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			for _, nutzer := range []string{"userA", "userB"} {
				mu.Lock()
				vorher := len(anfragen)
				mu.Unlock()
				w := doBriefingRequest(t, r, http.MethodPost, f.pfad+"?user_id=fremd", f.body(nutzer), sessionCookieFor(nutzer, secret))
				if w.Code != http.StatusCreated {
					t.Fatalf("%s POST %s: %d %s", nutzer, f.pfad, w.Code, w.Body.String())
				}
				var antwort map[string]interface{}
				if err := json.Unmarshal(w.Body.Bytes(), &antwort); err != nil {
					t.Fatalf("Antwort kein JSON: %v", err)
				}
				id, _ := antwort["id"].(string)
				if id == "" {
					t.Fatalf("Antwort ohne id: %s", w.Body.String())
				}
				mu.Lock()
				neu := append([]*url.URL(nil), anfragen[vorher:]...)
				mu.Unlock()
				if len(neu) != 1 || neu[0].Path != "/api/briefings/"+id+"/placements/erstanlage" ||
					neu[0].Query().Get("kind") != f.kind || neu[0].Query().Get("user_id") != nutzer {
					t.Errorf("%s: Tabellen-Abfrage beim Kern %v, erwartet eine fuer %s/%s", nutzer, neu, id, f.kind)
				}
				roh, err := os.ReadFile(filepath.Join(s.DataDir, "users", nutzer, "briefings", id+".json"))
				if err != nil {
					t.Fatalf("%s: Abo nicht gespeichert: %v", nutzer, err)
				}
				var abo map[string]interface{}
				if err := json.Unmarshal(roh, &abo); err != nil {
					t.Fatalf("Abo-Datei kein JSON: %v", err)
				}
				dc, _ := abo["display_config"].(map[string]interface{})
				tab, _ := dc["placements"].(map[string]interface{})
				rows, _ := tab["rows"].([]interface{})
				if len(rows) != 1 || tab["kern_marke"] != "router-3237" {
					t.Errorf("%s: gespeichertes Abo traegt nicht die Kern-Tabelle: %#v", nutzer, dc["placements"])
				}
			}
		})
	}
}
