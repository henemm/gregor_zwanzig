package handler

// Issue #3155 (Scheibe B4 von #3122), abgeloest durch #3237: die Orte-Anlage legte die
// Vorbelegung des 3-Tages-Ausblicks als Marke placements={"version":1,"outlook_reports":[..]}
// an. Seit #3237 schreibt die Anlage die volle Tabelle aus dem Kern (Nachweis in
// briefing_anlage_tabelle_3237_test.go). Hier bleiben: ohne Kern keine Marke, Assistenten-
// Wahl unveraendert, mitgeschickte placements unangetastet.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const pfadComparePresets3155 = "/api/compare/presets"

// postOrteAnlage3155 legt ein Orte-Abo fuer uid an und gibt die Antwort zurueck.
func postOrteAnlage3155(t *testing.T, s *store.Store, uid string, body map[string]interface{}) map[string]interface{} {
	t.Helper()
	buf, _ := json.Marshal(body)
	r := chi.NewRouter()
	r.Post(pfadComparePresets3155, CreateComparePresetHandler(s, ""))
	req := addUserToContext(httptest.NewRequest(http.MethodPost, pfadComparePresets3155, bytes.NewReader(buf)), uid)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusCreated {
		t.Fatalf("%s POST: erwartet 201, bekam %d: %s", uid, w.Code, w.Body.String())
	}
	var antwort map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &antwort); err != nil {
		t.Fatalf("%s: Antwort kein JSON: %v", uid, err)
	}
	return antwort
}

// einzigesOrteAbo3155 liest das (einzige) gespeicherte Orte-Abo DIESES Nutzers.
func einzigesOrteAbo3155(t *testing.T, s *store.Store, uid string) model.ComparePreset {
	t.Helper()
	presets, err := s.WithUser(uid).LoadComparePresets()
	if err != nil || len(presets) != 1 {
		t.Fatalf("%s: erwartet genau 1 Orte-Abo, bekam %d (%v)", uid, len(presets), err)
	}
	return presets[0]
}

func orteBody3155(name string, extra map[string]interface{}) map[string]interface{} {
	body := map[string]interface{}{"name": name, "schedule": "daily",
		"profil": "wandern", "location_ids": []string{"loc-a"},
		"display_config": map[string]interface{}{
			"active_metrics": []map[string]interface{}{
				{"metric_id": "temperature", "aggregation": "max"},
				{"metric_id": "wind", "aggregation": "max"},
				{"metric_id": "precipitation", "aggregation": "sum"},
			},
			// Im Anlege-Assistenten gewaehlt: Folge und Form des Ausblicks.
			"outlook_metrics":        []string{"precipitation", "wind"},
			"outlook_metric_formats": map[string]interface{}{"wind": true},
		}}
	for k, v := range extra {
		body[k] = v
	}
	return body
}

func slots3155(morgen, abend bool) map[string]interface{} {
	return map[string]interface{}{"morning_enabled": morgen, "morning_time": "07:00:00",
		"evening_enabled": abend, "evening_time": "18:00:00"}
}

// #3237: Go legt keine Ausblick-Marke mehr an (die Tabelle samt
// outlook_reports kommt aus dem Kern, briefing_anlage_tabelle_3237_test.go);
// ohne Kern bleibt display_config ohne placements, alles andere unveraendert.
func TestOrteAnlage_OhneKernKeineMarkeAssistentenWahlBleibt(t *testing.T) {
	basis := t.TempDir()
	uid := "nutzer-a-3155"
	s := store.New(basis, uid)
	postOrteAnlage3155(t, s, uid, orteBody3155("Orte", slots3155(true, true)))
	dc := einzigesOrteAbo3155(t, s, uid).DisplayConfig
	if _, ok := dc["placements"]; ok {
		t.Errorf("Go darf ohne Kern keine placements anlegen: %#v", dc["placements"])
	}
	om, _ := json.Marshal(dc["outlook_metrics"])
	if string(om) != `["precipitation","wind"]` {
		t.Errorf("outlook_metrics veraendert: %s", om)
	}
	of, _ := json.Marshal(dc["outlook_metric_formats"])
	if string(of) != `{"wind":true}` {
		t.Errorf("outlook_metric_formats veraendert: %s", of)
	}
	if _, ok := dc["active_metrics"]; !ok {
		t.Errorf("active_metrics verloren: %#v", dc)
	}
}

// Mitgeschickte placements (z. B. ein Client mit Tabelle) bleiben unangetastet.
func TestOrteAnlage_MitgeschicktePlacementsUnangetastet(t *testing.T) {
	gesendet := map[string]interface{}{
		"version": 1,
		"rows": []interface{}{
			map[string]interface{}{"metric_id": "wind", "places": map[string]interface{}{"sms": false}},
		},
		"outlook_reports": []interface{}{"morning", "evening"},
	}
	for _, f := range []struct {
		name      string
		slots     map[string]interface{}
		placement map[string]interface{}
	}{
		{"tabelle_mit_rows", slots3155(true, true), gesendet},
		{"eigene_marke_ohne_rows", slots3155(true, false),
			map[string]interface{}{"version": 1, "outlook_reports": []interface{}{}}},
	} {
		t.Run(f.name, func(t *testing.T) {
			basis := t.TempDir()
			uid := "nutzer-a-3155"
			s := store.New(basis, uid)
			body := orteBody3155("Orte", f.slots)
			body["display_config"].(map[string]interface{})["placements"] = f.placement
			postOrteAnlage3155(t, s, uid, body)
			dc := einzigesOrteAbo3155(t, s, uid).DisplayConfig
			ist, _ := json.Marshal(dc["placements"])
			soll, _ := json.Marshal(f.placement)
			if string(ist) != string(soll) {
				t.Errorf("mitgeschickte placements veraendert:\n ist  %s\n soll %s", ist, soll)
			}
		})
	}
}
