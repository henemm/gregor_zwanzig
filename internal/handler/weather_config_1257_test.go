package handler

import (
	"net/http/httptest"
	"reflect"
	"sort"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
)

// AC-5: dieselbe Metrik-Kombination via Store-SaveTrip vs. PUT-Handler →
// identische alert_rules (beweist Pfad-Zusammenlegung, Issue #1257).
func TestPutTripWeatherConfig_1257_MatchesStoreSavePath(t *testing.T) {
	cfg := map[string]interface{}{"metrics": []interface{}{
		map[string]interface{}{"metric_id": "gust", "enabled": true},
		map[string]interface{}{"metric_id": "temperature", "enabled": true},
	}}

	sStore := newTestStore(t)
	tripStore := model.Trip{ID: "trip-store-path", Name: "Store Path", DisplayConfig: cfg}
	sStore.SaveTrip(&tripStore)
	loadedStore, _ := sStore.LoadTrip("trip-store-path")

	sHandler := newTestStore(t)
	tripHandler := model.Trip{ID: "trip-handler-path", Name: "Handler Path"}
	sHandler.SaveTrip(&tripHandler)
	r := chi.NewRouter()
	r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(sHandler))
	body := `{"metrics":[{"metric_id":"gust","enabled":true},{"metric_id":"temperature","enabled":true}]}`
	req := httptest.NewRequest("PUT", "/api/trips/trip-handler-path/weather-config", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != 200 {
		t.Fatalf("AC-5: PUT want 200, got %d: %s", w.Code, w.Body.String())
	}
	loadedHandler, _ := sHandler.LoadTrip("trip-handler-path")

	// normalize: ID ist zufaellig (shortID()) und muss aus dem Feld-Vergleich
	// ausgeklammert werden. PairID wird in keinem der beiden Pfade gesetzt
	// (bleibt nil) und ist daher deterministisch — wird mitverglichen.
	normalize := func(rules []model.AlertRule) []model.AlertRule {
		out := make([]model.AlertRule, len(rules))
		copy(out, rules)
		for i := range out {
			out[i].ID = ""
		}
		sort.Slice(out, func(i, j int) bool { return out[i].Metric < out[j].Metric })
		return out
	}
	gotStore := normalize(loadedStore.AlertRules)
	gotHandler := normalize(loadedHandler.AlertRules)
	if !reflect.DeepEqual(gotStore, gotHandler) {
		t.Errorf("AC-5: alert_rules differ (field-by-field, ID ignored):\nstore:   %+v\nhandler: %+v", gotStore, gotHandler)
	}
}
