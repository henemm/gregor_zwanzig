package handler

// Issue #3155 (Scheibe B4 von #3122) — Spec docs/specs/modules/feat_3155_ein_name_ausblick.md
// AC-8, AC-9, Entscheidung 5: die Orte-Anlage (POST /api/compare/presets) legt die
// Vorbelegung des 3-Tages-Ausblicks als Marke an:
//
//	display_config.placements = {"version": 1, "outlook_reports": [...]}
//
// nach der einen Regel (Ober-Spec Nr. 6): ist allein das Morgen-Briefing eingeschaltet
// ["morning"], sonst ["evening"]. Bewusst OHNE "rows" (das Abo bleibt im Altpfad, die im
// Anlege-Assistenten gewaehlten Ausblick-Metriken/-Formate bleiben wirksam). Mitgeschickte
// "placements" bleiben unangetastet. Zwei Nutzer je Fall (Mandantentrennung, echte user_id
// aus dem Auth-Kontext ueber addUserToContext + WithUser).

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
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
	r.Post(pfadComparePresets3155, CreateComparePresetHandler(s))
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

// marke3155 prueft die Marke: version 1, outlook_reports wie erwartet, KEIN rows.
func marke3155(t *testing.T, wer string, dc map[string]interface{}, soll []string) {
	t.Helper()
	roh, ok := dc["placements"].(map[string]interface{})
	if !ok {
		t.Fatalf("%s: display_config.placements fehlt oder ist kein Objekt: %#v", wer, dc["placements"])
	}
	if v, _ := roh["version"].(float64); v != 1 {
		if vi, isInt := roh["version"].(int); !isInt || vi != 1 {
			t.Errorf("%s: placements.version = %#v, erwartet 1", wer, roh["version"])
		}
	}
	if _, hatRows := roh["rows"]; hatRows {
		t.Errorf("%s: Marke darf KEINE rows tragen (sonst gilt der neue Eingang): %#v", wer, roh["rows"])
	}
	ist := []string{}
	if liste, ok := roh["outlook_reports"].([]interface{}); ok {
		for _, x := range liste {
			if s, ok := x.(string); ok {
				ist = append(ist, s)
			}
		}
	} else if liste, ok := roh["outlook_reports"].([]string); ok {
		ist = append(ist, liste...)
	} else {
		t.Fatalf("%s: placements.outlook_reports fehlt: %#v", wer, roh)
	}
	if !reflect.DeepEqual(ist, soll) {
		t.Errorf("%s: outlook_reports = %v, erwartet %v", wer, ist, soll)
	}
}

// Regel Nr. 6: nur Morgen an -> ["morning"], sonst ["evening"].
var ausblickVorbelegungFaelle3155 = []struct {
	name  string
	slots map[string]interface{}
	soll  []string
}{
	{"morgen_und_abend", slots3155(true, true), []string{"evening"}},
	{"nur_morgen", slots3155(true, false), []string{"morning"}},
	{"nur_abend", slots3155(false, true), []string{"evening"}},
	{"beide_aus", slots3155(false, false), []string{"evening"}},
	// Ohne Slot-Felder greifen die Neu-Preset-Defaults (Morgen an, Abend aus).
	{"ohne_slot_felder_default_nur_morgen", map[string]interface{}{}, []string{"morning"}},
}

func TestOrteAnlage_AusblickMarkeNachRegel_ZweiNutzer(t *testing.T) {
	for _, f := range ausblickVorbelegungFaelle3155 {
		t.Run(f.name, func(t *testing.T) {
			basis := t.TempDir()
			for _, uid := range []string{"nutzer-a-3155", "nutzer-b-3155"} {
				s := store.New(basis, uid)
				antwort := postOrteAnlage3155(t, s, uid, orteBody3155("Orte "+uid, f.slots))
				dcAntwort, _ := antwort["display_config"].(map[string]interface{})
				marke3155(t, uid+" (Antwort)", dcAntwort, f.soll)
				p := einzigesOrteAbo3155(t, s, uid)
				marke3155(t, uid+" (gespeichert)", p.DisplayConfig, f.soll)
				if p.Name != "Orte "+uid {
					t.Errorf("Mandantentrennung: %s liest %q", uid, p.Name)
				}
			}
		})
	}
}

// AC-8: die im Anlege-Assistenten gewaehlten Ausblick-Metriken und -Formate bleiben
// unveraendert (die Marke ueberschreibt nichts im Altpfad).
func TestOrteAnlage_AusblickMarkeLaesstAssistentenWahlStehen(t *testing.T) {
	basis := t.TempDir()
	uid := "nutzer-a-3155"
	s := store.New(basis, uid)
	postOrteAnlage3155(t, s, uid, orteBody3155("Orte", slots3155(true, true)))
	dc := einzigesOrteAbo3155(t, s, uid).DisplayConfig
	marke3155(t, uid, dc, []string{"evening"})
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

// AC-8: ohne mitgeschickte display_config (Standardvorlage des Nutzers) bekommt das
// neue Abo die Marke ebenfalls; die Vorlage bleibt sonst unveraendert erhalten.
func TestOrteAnlage_AusblickMarkeAuchMitStandardvorlage(t *testing.T) {
	basis := t.TempDir()
	uid := "nutzer-a-3155"
	s := store.New(basis, uid)
	body := orteBody3155("Orte", slots3155(true, false))
	delete(body, "display_config")
	postOrteAnlage3155(t, s, uid, body)
	dc := einzigesOrteAbo3155(t, s, uid).DisplayConfig
	marke3155(t, uid, dc, []string{"morning"})
	if _, ok := dc["active_metrics"]; !ok {
		t.Errorf("Standardvorlage verloren (active_metrics fehlt): %#v", dc)
	}
}

// Tech-Lead-Entscheidung zu #3155: Orte-Anlage mit outlook_enabled=false schreibt die Marke
// mit leerer Liste (leere Liste = aus, ADR-0124 Nr. 6); nur bei eingeschaltetem bzw. fehlendem
// outlook_enabled gilt die Morgen/Abend-Regel. Zwei Nutzer je Fall.
func TestOrteAnlage_AusblickMarkeFolgtOutlookEnabled_ZweiNutzer(t *testing.T) {
	for _, f := range []struct {
		name  string
		extra map[string]interface{}
		soll  []string
	}{
		{"aus_morgen_und_abend", map[string]interface{}{"outlook_enabled": false}, []string{}},
		{"aus_nur_morgen", map[string]interface{}{"outlook_enabled": false, "evening_enabled": false}, []string{}},
		{"an_morgen_und_abend", map[string]interface{}{"outlook_enabled": true}, []string{"evening"}},
		{"an_nur_morgen", map[string]interface{}{"outlook_enabled": true, "evening_enabled": false}, []string{"morning"}},
	} {
		t.Run(f.name, func(t *testing.T) {
			basis := t.TempDir()
			for _, uid := range []string{"nutzer-a-3155", "nutzer-b-3155"} {
				s := store.New(basis, uid)
				felder := slots3155(true, true)
				for k, v := range f.extra {
					felder[k] = v
				}
				postOrteAnlage3155(t, s, uid, orteBody3155("Orte "+uid, felder))
				p := einzigesOrteAbo3155(t, s, uid)
				marke3155(t, uid, p.DisplayConfig, f.soll)
				if p.Name != "Orte "+uid {
					t.Errorf("Mandantentrennung: %s liest %q", uid, p.Name)
				}
			}
		})
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

// AC-9: zwei Nutzer legen je ein Orte-Abo an, einer nur mit Morgen-Briefing; jedes Abo
// traegt nur seine eigene Vorbelegung, keines enthaelt Daten des anderen.
func TestOrteAnlage_AusblickMarke_ZweiNutzerJeEigeneVorbelegung(t *testing.T) {
	basis := t.TempDir()
	a, b := "nutzer-a-3155", "nutzer-b-3155"
	sa, sb := store.New(basis, a), store.New(basis, b)
	postOrteAnlage3155(t, sa, a, orteBody3155("Orte A", slots3155(true, true)))
	postOrteAnlage3155(t, sb, b, orteBody3155("Orte B", slots3155(true, false)))
	pa := einzigesOrteAbo3155(t, sa, a)
	pb := einzigesOrteAbo3155(t, sb, b)
	marke3155(t, a, pa.DisplayConfig, []string{"evening"})
	marke3155(t, b, pb.DisplayConfig, []string{"morning"})
	if pa.Name != "Orte A" || pb.Name != "Orte B" {
		t.Errorf("Mandantentrennung verletzt: A=%q B=%q", pa.Name, pb.Name)
	}
	if pa.UserID != a || pb.UserID != b {
		t.Errorf("user_id nicht aus dem Auth-Kontext: A=%q B=%q", pa.UserID, pb.UserID)
	}
}
