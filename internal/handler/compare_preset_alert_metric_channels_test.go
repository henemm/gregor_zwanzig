package handler

// Issue #1895 Scheibe S1 (Epic #1230) — Kanalzuordnung je Metrik, Parität auf
// dem Ortsvergleich. Spec: docs/specs/modules/alert_metric_channels.md,
// AC-2/AC-5.
//
// RED-Bauform wie im Trip-Geschwister-File: gemessen wird ausschliesslich der
// ausgelieferte HTTP-Antwortkoerper, kein Go-Struct-Feld. Heute rot, weil
// `model.ComparePreset` das Feld nicht kennt — der Vergleich-PUT mergt den
// Schluessel zwar generisch (mergeBriefingPatch), der anschliessende
// typisierte json.Unmarshal (compare_preset.go:292-300) verwirft ihn aber
// wieder, sodass das GET ihn nie ausliefert.
//
// AC-5 bewacht deshalb NICHT einen neu geschriebenen Merge (den gibt es auf
// diesem Pfad nicht), sondern das Struct-Feld selbst: ohne Feld ueberlebt der
// Schluessel den Unmarshal nicht (Spec, AC-5 Hinweis).

import (
	"net/http"
	"reflect"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func amcCompareRouter(s *store.Store) *chi.Mux {
	r := chi.NewRouter()
	r.Get("/api/compare/presets/{id}", GetComparePresetHandler(s))
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	return r
}

func amcSeedPreset(t *testing.T, s *store.Store, user, id, name string) {
	t.Helper()
	preset := model.ComparePreset{
		ID:          id,
		Name:        name,
		UserID:      user,
		LocationIDs: []string{"loc-a", "loc-b", "loc-c"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		CreatedAt:   time.Now().UTC(),
	}
	if err := s.WithUser(user).SaveComparePresets([]model.ComparePreset{preset}); err != nil {
		t.Fatalf("SaveComparePresets(%s/%s): %v", user, id, err)
	}
}

// amcPresetPutBody traegt die Pflichtfelder aus Testbequemlichkeit mit (Muster
// compare_preset_alert_channel_thresholds_test.go) und ergaenzt die zu
// pruefende Metrik-Kanal-Zuordnung.
func amcPresetPutBody(channels map[string]interface{}) map[string]interface{} {
	return map[string]interface{}{
		"name":                  "AMC-Vergleich",
		"schedule":              "manual",
		"profil":                "SUMMER_TREKKING",
		"hour_from":             8,
		"hour_to":               17,
		"location_ids":          []string{"loc-a", "loc-b", "loc-c"},
		"empfaenger":            []string{"a@example.com"},
		"alert_metric_channels": channels,
	}
}

// AC-2: Roundtrip PUT -> GET auf dem Ortsvergleich, getrennt fuer zwei Nutzer.
// Beide Presets tragen ABSICHTLICH DIESELBE ID — sonst bewiese der Test keine
// Mandantentrennung.
func TestComparePresetAlertMetricChannels_RoundtripIsolatedPerUser(t *testing.T) {
	s := newTestStore(t)
	r := amcCompareRouter(s)
	const id = "cp-1895-ac2"

	amcSeedPreset(t, s, "alice", id, "Alice-Vergleich")
	amcSeedPreset(t, s, "bob", id, "Bob-Vergleich")

	alice := map[string]interface{}{"rain": map[string]interface{}{"telegram": true}}
	bob := map[string]interface{}{"wind": map[string]interface{}{"email": true}}

	if w := amcReq(t, r, http.MethodPut, "/api/compare/presets/"+id, "alice",
		amcPresetPutBody(alice)); w.Code != http.StatusOK {
		t.Fatalf("PUT alice: erwartet 200, bekam %d: %s", w.Code, w.Body.String())
	}
	if w := amcReq(t, r, http.MethodPut, "/api/compare/presets/"+id, "bob",
		amcPresetPutBody(bob)); w.Code != http.StatusOK {
		t.Fatalf("PUT bob: erwartet 200, bekam %d: %s", w.Code, w.Body.String())
	}

	gotAlice := amcChannelsOf(t, amcBodyMap(t, amcReq(t, r, http.MethodGet, "/api/compare/presets/"+id, "alice", nil)))
	if !reflect.DeepEqual(gotAlice, alice) {
		t.Errorf("AC-2 alice: erwartet %v, bekam %v", alice, gotAlice)
	}

	gotBob := amcChannelsOf(t, amcBodyMap(t, amcReq(t, r, http.MethodGet, "/api/compare/presets/"+id, "bob", nil)))
	if !reflect.DeepEqual(gotBob, bob) {
		t.Errorf("AC-2 bob: erwartet %v, bekam %v", bob, gotBob)
	}
}

// AC-5: Ein Vergleich-PUT, der nur EINE Metrik mitschickt, darf die uebrigen
// Metriken nicht loeschen.
func TestComparePresetAlertMetricChannels_SingleMetricPutPreservesOtherMetrics(t *testing.T) {
	s := newTestStore(t)
	r := amcCompareRouter(s)
	const id = "cp-1895-ac5"
	amcSeedPreset(t, s, "alice", id, "AC5-Vergleich")

	initial := map[string]interface{}{
		"rain": map[string]interface{}{"telegram": true},
		"wind": map[string]interface{}{"email": true},
	}
	if w := amcReq(t, r, http.MethodPut, "/api/compare/presets/"+id, "alice",
		amcPresetPutBody(initial)); w.Code != http.StatusOK {
		t.Fatalf("PUT (Vorbelegung): erwartet 200, bekam %d: %s", w.Code, w.Body.String())
	}

	// PUT aendert NUR "rain"; "wind" fehlt im Unterobjekt komplett.
	if w := amcReq(t, r, http.MethodPut, "/api/compare/presets/"+id, "alice",
		amcPresetPutBody(map[string]interface{}{
			"rain": map[string]interface{}{"telegram": false, "sms": true},
		})); w.Code != http.StatusOK {
		t.Fatalf("PUT (nur rain): erwartet 200, bekam %d: %s", w.Code, w.Body.String())
	}

	got := amcChannelsOf(t, amcBodyMap(t, amcReq(t, r, http.MethodGet, "/api/compare/presets/"+id, "alice", nil)))

	wantRain := map[string]interface{}{"telegram": false, "sms": true}
	if !reflect.DeepEqual(got["rain"], wantRain) {
		t.Errorf("AC-5: rain nicht uebernommen — erwartet %v, bekam %v", wantRain, got["rain"])
	}
	wantWind := map[string]interface{}{"email": true}
	if !reflect.DeepEqual(got["wind"], wantWind) {
		t.Errorf("AC-5: wind vom rain-PUT geloescht — erwartet %v (unangetastet), bekam %v", wantWind, got["wind"])
	}
}
