package handler

import (
	"encoding/json"
	"fmt"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/store"
)

// AC-5 (#2158): verschiedene Metrik-Vorlagen eines Nutzers werden gleichzeitig
// angelegt, geaendert und geloescht. metric_presets.json ist eine Sammeldatei;
// ohne Vorlagen-Sperre geht je Durchlauf mindestens eine Aenderung verloren.
func TestMetricPresetParallel_CreatePatchDelete_AlleAenderungenErhalten(t *testing.T) {
	const iterationen = 100
	const neue = 6
	schlecht := 0
	for it := 0; it < iterationen; it++ {
		s := store.New(t.TempDir(), "u1")
		idOf := func(name string) string {
			w := p2158Do(CreateMetricPresetHandler(s), "POST", "/api/metric-presets", "/api/metric-presets",
				fmt.Sprintf(`{"name":%q}`, name), "u1")
			if w.Code != 201 {
				t.Fatalf("seed %s: %d %s", name, w.Code, w.Body.String())
			}
			var p struct {
				ID string `json:"id"`
			}
			_ = json.Unmarshal(w.Body.Bytes(), &p)
			return p.ID
		}
		patchID := idOf("zu-aendern")
		delID := idOf("zu-loeschen")

		fns := []func(){
			func() {
				p2158Do(PatchMetricPresetHandler(s), "PATCH", "/api/metric-presets/{id}",
					"/api/metric-presets/"+patchID, `{"description":"geaendert"}`, "u1")
			},
			func() {
				p2158Do(DeleteMetricPresetHandler(s), "DELETE", "/api/metric-presets/{id}",
					"/api/metric-presets/"+delID, "", "u1")
			},
		}
		for k := 0; k < neue; k++ {
			k := k
			fns = append(fns, func() {
				p2158Do(CreateMetricPresetHandler(s), "POST", "/api/metric-presets", "/api/metric-presets",
					fmt.Sprintf(`{"name":"neu-%d"}`, k), "u1")
			})
		}
		p2158Parallel(t, 30*time.Second, fns...)

		ps, err := s.LoadMetricPresets()
		if err != nil {
			t.Fatalf("laden: %v", err)
		}
		bad := len(ps) != neue+1 // zu-aendern + neue, zu-loeschen weg
		for _, p := range ps {
			if p.ID == delID {
				bad = true
			}
			if p.ID == patchID && p.Description != "geaendert" {
				bad = true
			}
		}
		if bad {
			schlecht++
		}
	}
	if schlecht > 0 {
		t.Errorf("Lost Update in metric_presets.json in %d von %d Durchlaeufen", schlecht, iterationen)
	}
}
