package handler

// Issue #2793 S2a — Gewitter-„Alarm ab“ nie gelb (ADR-0106 P2, Spec
// docs/specs/modules/feat_2793_s2_alarm_stufenwechsel.md §2, AC-8) und
// Erhalt des Migrations-Merkers display_config.alarm_ab_migration (§5).
//
// Echte Handler und echter Store im Temp-Verzeichnis (Helfer aus
// ampel_validierung_test.go), zwei Nutzer: alice schreibt, bob bleibt gleich.

import (
	"encoding/json"
	"net/http"
	"strings"
	"testing"
)

func gewitterGelb() obj {
	return obj{"template": "allgemein", "metrics": obj{"thunder": obj{"alarm_ab": "yellow"}}}
}

// AC-8: Trip, Vergleich und eigene Vorlage lehnen Gewitter alarm_ab "yellow"
// mit 400 ampel_ungueltig in der Anfragesprache ab; nichts wird geschrieben.
func TestGewitterAlarmAbGelb_WirdAufAllenSchreibwegenAbgelehnt(t *testing.T) {
	texte := map[string]string{"de": "Die Ampel ist ungültig", "en": "The traffic light is invalid"}
	for lang, prefix := range texte {
		for _, weg := range ampelSchreibwege(gewitterGelb()) {
			s := newTestStore(t)
			ampelSeed(t, s, "alice")
			ampelSeed(t, s, "bob")
			vorherA, vorherB := ampelStand(t, s, "alice"), ampelStand(t, s, "bob")
			w := ampelAnfrage(t, ampelRouter(s), weg.method, weg.path, "alice", lang, weg.body)
			var body struct{ Code, Message string }
			_ = json.Unmarshal(w.Body.Bytes(), &body)
			name := lang + " " + weg.method + " " + weg.path
			if w.Code != http.StatusBadRequest || body.Code != "ampel_ungueltig" || !strings.HasPrefix(body.Message, prefix) {
				t.Fatalf("%s: %d %s", name, w.Code, w.Body.String())
			}
			if ampelStand(t, s, "alice") != vorherA || ampelStand(t, s, "bob") != vorherB {
				t.Fatalf("%s: gespeicherte Daten trotz Ablehnung geaendert", name)
			}
		}
	}
}

func TestGewitterAlarmAbGelb_PatchEigeneVorlageAbgelehnt_OrangeErlaubt(t *testing.T) {
	s := newTestStore(t)
	ampelSeed(t, s, "bob")
	h := ampelRouter(s)
	w := ampelAnfrage(t, h, "POST", "/api/metric-presets", "alice", "de",
		obj{"name": "Mein Gipfel", "metrics": []string{"wind"}, "ampel": ampelGueltig()})
	var p struct{ ID string }
	_ = json.Unmarshal(w.Body.Bytes(), &p)
	vorherBob := ampelStand(t, s, "bob")
	presets, _ := s.WithUser("alice").LoadMetricPresets()
	raw, _ := json.Marshal(presets)
	vorherAlice := string(raw)
	for _, lang := range []string{"de", "en"} {
		w = ampelAnfrage(t, h, "PATCH", "/api/metric-presets/"+p.ID, "alice", lang, obj{"ampel": gewitterGelb()})
		if w.Code != http.StatusBadRequest || !strings.Contains(w.Body.String(), `"code":"ampel_ungueltig"`) {
			t.Fatalf("PATCH %s: %d %s", lang, w.Code, w.Body.String())
		}
	}
	presets, _ = s.WithUser("alice").LoadMetricPresets()
	raw, _ = json.Marshal(presets)
	if string(raw) != vorherAlice || ampelStand(t, s, "bob") != vorherBob {
		t.Fatal("abgelehnter PATCH hat Daten veraendert")
	}
	for _, stufe := range []string{"never", "orange", "red"} {
		ok := obj{"metrics": obj{"thunder": obj{"alarm_ab": stufe}}}
		if w = ampelAnfrage(t, h, "PATCH", "/api/metric-presets/"+p.ID, "alice", "de", obj{"ampel": ok}); w.Code != http.StatusOK {
			t.Fatalf("PATCH Gewitter %s: %d %s", stufe, w.Code, w.Body.String())
		}
	}
}

// §5: der Merker der Migration und metric_alert_levels ueberleben das
// Speichern anderer display_config-Felder (Trip und Vergleich), bob bleibt gleich.
func TestMigrationsMerker_UeberlebtSpeichernAndererFelder(t *testing.T) {
	s := newTestStore(t)
	for _, u := range []string{"alice", "bob"} {
		ampelSeed(t, s, u)
		us := s.WithUser(u)
		trip, _ := us.LoadTrip("t1")
		trip.DisplayConfig["alarm_ab_migration"] = "2793"
		trip.DisplayConfig["metric_alert_levels"] = obj{"wind_gust": "sensibel"}
		if err := us.SaveTrip(trip); err != nil {
			t.Fatal(err)
		}
		cp, _ := us.LoadComparePreset("c1")
		cp.DisplayConfig["alarm_ab_migration"] = "2793"
		cp.DisplayConfig["metric_alert_levels"] = obj{"thunder_level": "off"}
		if err := us.SaveComparePreset(*cp); err != nil {
			t.Fatal(err)
		}
	}
	vorherB := ampelStand(t, s, "bob")
	h := ampelRouter(s)
	for _, weg := range []struct {
		method, path string
		body         obj
	}{
		{"PUT", "/api/trips/t1", obj{"display_config": obj{"theme": "hell"}}},
		{"PUT", "/api/trips/t1/weather-config", obj{"theme": "dunkel"}},
		{"PUT", "/api/compare/presets/c1", obj{"display_config": obj{"theme": "hell"}}},
		{"PUT", "/api/briefings/c1?kind=vergleich", obj{"display_config": obj{"theme": "dunkel"}}},
	} {
		if w := ampelAnfrage(t, h, weg.method, weg.path, "alice", "de", weg.body); w.Code != http.StatusOK {
			t.Fatalf("%s %s: %d %s", weg.method, weg.path, w.Code, w.Body.String())
		}
	}
	us := s.WithUser("alice")
	trip, _ := us.LoadTrip("t1")
	cp, _ := us.LoadComparePreset("c1")
	for name, dc := range map[string]map[string]interface{}{"trip": trip.DisplayConfig, "vergleich": cp.DisplayConfig} {
		if dc["alarm_ab_migration"] != "2793" || dc["metric_alert_levels"] == nil || dc["ampel"] == nil {
			t.Fatalf("%s: Merker/Altstufen/Ampel verloren: %v", name, dc)
		}
	}
	if ampelStand(t, s, "bob") != vorherB {
		t.Fatal("bob wurde veraendert")
	}
}
