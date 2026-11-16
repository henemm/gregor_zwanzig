package handler

// Issue #3047 Runde 7, Befund E1 (Go-Teil): Ein neues Orts-Briefing aus der
// eigenen Standard-Vorlage schrieb nur `ampel`; ohne `active_metrics` zeigt die
// Mail alle Zeilen, der Editor die Vorlage. Tech-Lead-Entscheidung (Spec
// feat_3047 „Nachtrag Runde 7"): die Neuanlage speichert die Grundauswahl
// ausdruecklich, in der Folge der Vorlage, nur Groessen des Vergleichs-Katalogs
// (Auswertung wie der Editor: erster Katalog-Eintrag je Groesse).

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestF3047E1_NeuerVergleichSchreibtGrundauswahlDerStandardVorlage_ZweiNutzer(t *testing.T) {
	s := newTestStore(t)
	h := v2794Router(s)
	metr := func(eintraege ...obj) []obj { return eintraege }
	an := func(id string) obj { return obj{"metric_id": id, "enabled": true, "use_friendly_format": false} }
	aus := func(id string) obj { return obj{"metric_id": id, "enabled": false, "use_friendly_format": false} }
	faelle := []struct {
		user    string
		metrics []obj
		soll    []interface{}
	}{
		// temperature_night kennt der Vergleichs-Katalog nicht (E6) -> faellt weg.
		{"alice", metr(an("gust"), an("temperature"), an("temperature_night"), aus("thunder"), an("precipitation")),
			[]interface{}{
				map[string]interface{}{"metric_id": "gust", "aggregation": "max"},
				map[string]interface{}{"metric_id": "temperature", "aggregation": "max"},
				map[string]interface{}{"metric_id": "precipitation", "aggregation": "sum"},
			}},
		{"bob", metr(an("cloud_total"), an("wind"), an("freezing_level")),
			[]interface{}{
				map[string]interface{}{"metric_id": "cloud_total", "aggregation": "avg"},
				map[string]interface{}{"metric_id": "wind", "aggregation": "max"},
				map[string]interface{}{"metric_id": "freezing_level", "aggregation": "min"},
			}},
	}
	for _, f := range faelle {
		body := obj{"name": "Ort " + f.user, "kind": "vergleich", "is_default": true,
			"ampel": v2794Ampel(40, "orange"), "metrics": f.metrics}
		if code, resp := v2794Vorlage(t, h, f.user, body); code != http.StatusCreated {
			t.Fatalf("POST Vorlage %s: %d %v", f.user, code, resp)
		}
	}
	for _, f := range faelle {
		w := v2794Anfrage(t, h, "POST", "/api/compare/presets", f.user, "de", validPresetBody())
		if w.Code != http.StatusCreated {
			t.Fatalf("POST /api/compare/presets %s: %d %s", f.user, w.Code, w.Body.String())
		}
		var resp struct {
			ID string `json:"id"`
		}
		_ = json.Unmarshal(w.Body.Bytes(), &resp)
		cp, err := s.WithUser(f.user).LoadComparePreset(resp.ID)
		if err != nil || cp == nil {
			t.Fatalf("LoadComparePreset %s: %v", f.user, err)
		}
		if got := cp.DisplayConfig["active_metrics"]; !reflect.DeepEqual(got, interface{}(f.soll)) {
			t.Errorf("E1 %s: active_metrics %v, erwartet %v (Grundauswahl der Vorlage)", f.user, got, f.soll)
		}
		if cp.DisplayConfig["ampel"] == nil {
			t.Errorf("E1 %s: Ampel der Vorlage fehlt", f.user)
		}
	}
}

// Orts-Standard ohne eine Groesse des Vergleichs-Katalogs: kein leeres
// active_metrics (leer hiesse „keine Zeile"), Bestandsverhalten (nur Ampel).
func TestF3047E1_StandardOhneKatalogGroesseSchreibtKeineLeereAuswahl(t *testing.T) {
	s := newTestStore(t)
	h := v2794Router(s)
	body := obj{"name": "Nacht", "kind": "vergleich", "is_default": true, "ampel": v2794Ampel(40, "orange"),
		"metrics": []obj{{"metric_id": "temperature_night", "enabled": true, "use_friendly_format": false}}}
	if code, resp := v2794Vorlage(t, h, "dora", body); code != http.StatusCreated {
		t.Fatalf("POST Vorlage: %d %v", code, resp)
	}
	w := v2794Anfrage(t, h, "POST", "/api/compare/presets", "dora", "de", validPresetBody())
	if w.Code != http.StatusCreated {
		t.Fatalf("POST: %d %s", w.Code, w.Body.String())
	}
	var resp struct {
		ID string `json:"id"`
	}
	_ = json.Unmarshal(w.Body.Bytes(), &resp)
	cp, _ := s.WithUser("dora").LoadComparePreset(resp.ID)
	if cp == nil || cp.DisplayConfig["ampel"] == nil {
		t.Fatalf("E1: Ampel der Vorlage fehlt: %+v", cp)
	}
	if _, hat := cp.DisplayConfig["active_metrics"]; hat {
		t.Errorf("E1: leeres active_metrics geschrieben: %v", cp.DisplayConfig["active_metrics"])
	}
}

// Ohne Orts-Standard (nur Trip-Standard) bleibt die Neuanlage wie bisher ohne
// display_config: kein erfundenes active_metrics.
func TestF3047E1_OhneOrtsStandardKeineGrundauswahl(t *testing.T) {
	s := newTestStore(t)
	h := v2794Router(s)
	if code, resp := v2794Vorlage(t, h, "carol", obj{"name": "Trip", "kind": "route", "is_default": true}); code != http.StatusCreated {
		t.Fatalf("POST Vorlage: %d %v", code, resp)
	}
	w := v2794Anfrage(t, h, "POST", "/api/compare/presets", "carol", "de", validPresetBody())
	if w.Code != http.StatusCreated {
		t.Fatalf("POST: %d %s", w.Code, w.Body.String())
	}
	var resp struct {
		ID string `json:"id"`
	}
	_ = json.Unmarshal(w.Body.Bytes(), &resp)
	cp, _ := s.WithUser("carol").LoadComparePreset(resp.ID)
	if cp == nil || cp.DisplayConfig["active_metrics"] != nil {
		t.Fatalf("E1: ohne Orts-Standard kein active_metrics erwartet: %+v", cp)
	}
}

// Drift-Waechter: die Go-Tabelle entspricht dem Vergleichs-Katalog, den Python
// ausliefert (tests/fixtures/vergleich_grundauswahl_aggregation.json, gegen
// get_compare_metric_catalog geprueft in
// tests/tdd/test_3047_e1_vergleich_grundauswahl_katalog.py).
func TestF3047E1_AggregationstabelleGleichPythonKatalog(t *testing.T) {
	dir, _ := os.Getwd()
	for i := 0; i < 8; i++ {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			break
		}
		dir = filepath.Dir(dir)
	}
	raw, err := os.ReadFile(filepath.Join(dir, "tests", "fixtures", "vergleich_grundauswahl_aggregation.json"))
	if err != nil {
		t.Fatal(err)
	}
	var soll map[string]string
	if err := json.Unmarshal(raw, &soll); err != nil || len(soll) < 20 {
		t.Fatalf("Fixture nicht lesbar (%v, %d)", err, len(soll))
	}
	if !reflect.DeepEqual(vergleichAggregation, soll) {
		t.Errorf("vergleichAggregation %v != Python-Katalog %v", vergleichAggregation, soll)
	}
}
