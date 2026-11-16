package handler

// Issue #3047 (Spec feat_3047 §7 T4, AC-16): ein neuer Trip aus der
// Standardvorlage behaelt die Vorlagen-Folge. Ohne `order`/`bucket` sortiert
// der Editor (metricsEditor.autoAssign) und der Python-Loader
// (auto_distribute) die Auswahl nach interner Prioritaet um.
//
// Kein Mock: echte Handler, echter Store auf t.TempDir(), user_id aus dem
// Auth-Kontext, zwei Nutzer mit unterschiedlicher Folge.

import (
	"fmt"
	"net/http"
	"reflect"
	"testing"
)

func TestF3047_NeuerTripAusVorlageBehaeltVorlagenFolge(t *testing.T) {
	s := newTestStore(t)
	h := v2794Router(s)
	faelle := []struct {
		user  string
		folge []string
	}{
		{"alice", []string{"gust", "temperature", "precipitation", "wind"}},
		{"bob", []string{"wind", "precipitation", "temperature", "gust"}},
	}
	for _, f := range faelle {
		metrics := []obj{}
		for _, id := range f.folge {
			metrics = append(metrics, obj{"metric_id": id, "enabled": true, "use_friendly_format": false})
		}
		// Eine abgewaehlte Metrik bekommt keine Spaltenposition.
		metrics = append(metrics, obj{"metric_id": "thunder", "enabled": false, "use_friendly_format": false})
		body := obj{"name": "Standard " + f.user, "kind": "route", "is_default": true, "metrics": metrics}
		if code, resp := v2794Vorlage(t, h, f.user, body); code != http.StatusCreated {
			t.Fatalf("POST Vorlage %s: %d %v", f.user, code, resp)
		}
	}
	for _, f := range faelle {
		if w := v2794Anfrage(t, h, "POST", "/api/trips", f.user, "de", v2794NeuerTrip("t-neu")); w.Code != http.StatusCreated {
			t.Fatalf("POST /api/trips %s: %d %s", f.user, w.Code, w.Body.String())
		}
		trip, err := s.WithUser(f.user).LoadTrip("t-neu")
		if err != nil || trip == nil {
			t.Fatalf("LoadTrip %s: %v", f.user, err)
		}
		liste, _ := trip.DisplayConfig["metrics"].([]interface{})
		var folge []string
		for _, e := range liste {
			m, _ := e.(map[string]interface{})
			if m["enabled"] != true {
				if _, hat := m["bucket"]; hat {
					t.Errorf("%s: abgewaehlte %v traegt bucket", f.user, m["metric_id"])
				}
				continue
			}
			if m["bucket"] != "primary" {
				t.Errorf("%s: %v ohne bucket primary: %v", f.user, m["metric_id"], m)
			}
			if got := fmt.Sprint(m["order"]); got != fmt.Sprint(len(folge)) {
				t.Errorf("%s: %v order %s, erwartet %d (Vorlagen-Folge)", f.user, m["metric_id"], got, len(folge))
			}
			folge = append(folge, fmt.Sprint(m["metric_id"]))
		}
		if !reflect.DeepEqual(folge, f.folge) {
			t.Errorf("%s: gespeicherte Folge %v, erwartet %v", f.user, folge, f.folge)
		}
	}
}
