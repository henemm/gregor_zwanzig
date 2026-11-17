package handler

// Issue #3047 Runde 7, Paket p14 — #1544/#1545 AC-6 (Spec
// docs/specs/modules/fix_1544_1545_trip_alarm_zeilen_ableitung.md, „Kein
// Datenverlust“) auf dem LIVE-Weg: der Reiter Wetter waehlt eine Groesse mit
// gesetzter Stufe ab, speichert, nimmt sie spaeter wieder auf. Die Nutzlasten
// haben genau die Form, die die echten Speicherer senden
// (frontend/.../wetter-tab/__tests__/p14_ac6_stufen_bleiben_beim_abwaehlen.test.ts:
// Trip `/weather-config` mit `ampel` + `metrics`, Vergleich `display_config`
// mit `ampel` + `active_metrics`). Geprueft wird die Seite, die beim Neu-Oeffnen
// gelesen wird (GET), mit zwei Nutzern derselben Kennung ueber den echten
// Auth-Kontext. Kein Mock.

import (
	"encoding/json"
	"net/http"
	"reflect"
	"testing"
)

func p14GustZeile(an bool) obj {
	z := obj{"upper": obj{"yellow": 45.0, "orange": 65.0, "red": 85.0}, "alarm_ab": "red"}
	if !an {
		z["enabled"] = false
	}
	return z
}

func p14Lesen(t *testing.T, h http.Handler, path, user string) obj {
	t.Helper()
	w := ampelAnfrage(t, h, "GET", path, user, "de", nil)
	if w.Code != http.StatusOK {
		t.Fatalf("GET %s (%s): %d %s", path, user, w.Code, w.Body.String())
	}
	var o obj
	if err := json.Unmarshal(w.Body.Bytes(), &o); err != nil {
		t.Fatalf("GET %s: %v", path, err)
	}
	return o
}

func p14PruefeStufe(t *testing.T, wo string, dc obj, levels obj) {
	t.Helper()
	if !reflect.DeepEqual(dc["metric_alert_levels"], map[string]interface{}(levels)) {
		t.Errorf("%s: metric_alert_levels verloren/veraendert (AC-6): %v", wo, dc["metric_alert_levels"])
	}
	ampel, _ := dc["ampel"].(map[string]interface{})
	metrics, _ := ampel["metrics"].(map[string]interface{})
	gust, _ := metrics["gust"].(map[string]interface{})
	if gust["alarm_ab"] != "red" {
		t.Errorf("%s: „Alarm ab“ der Boeen verloren (AC-6): %v", wo, gust)
	}
	upper, _ := gust["upper"].(map[string]interface{})
	if upper["red"] != 85.0 || upper["yellow"] != 45.0 {
		t.Errorf("%s: Grenzen der Boeen verloren (AC-6): %v", wo, gust)
	}
}

func TestP14_AC6_Trip_AbwaehlenUndWiederAufnehmen_StufeBleibt_ZweiNutzer(t *testing.T) {
	s := newTestStore(t)
	ampelB := obj{"template": "allgemein", "metrics": obj{"gust": p14GustZeile(true)}}
	levelsB := obj{"wind_gust": "sensibel", "temperature": "standard"}
	teil3SeedTrip(t, s, "nutzer-a", teil3AmpelA(), obj{"metric_alert_levels": obj{"wind_gust": "robust"}})
	teil3SeedTrip(t, s, "nutzer-b", ampelB, nil)
	h := teil3TripRouter(s)
	pfad := "/api/trips/" + teil3TripID + "/weather-config"
	fpA := teil3Fingerprint(t, s, "nutzer-a", teil3TripID)

	// B waehlt Boeen ab (Form der echten Trip-Nutzlast).
	w := ampelAnfrage(t, h, "PUT", pfad, "nutzer-b", "de", obj{
		"ampel": obj{"template": "allgemein", "metrics": obj{"gust": p14GustZeile(false)}},
		"metrics": []interface{}{
			obj{"metric_id": "temperature", "enabled": true},
			obj{"metric_id": "gust", "enabled": false},
		},
	})
	if w.Code != http.StatusOK {
		t.Fatalf("B abwaehlen: %d %s", w.Code, w.Body.String())
	}
	p14PruefeStufe(t, "nach Abwahl", p14Lesen(t, h, pfad, "nutzer-b"), levelsB)

	// B nimmt Boeen wieder auf.
	w = ampelAnfrage(t, h, "PUT", pfad, "nutzer-b", "de", obj{
		"ampel": obj{"template": "allgemein", "metrics": obj{"gust": p14GustZeile(true)}},
		"metrics": []interface{}{
			obj{"metric_id": "temperature", "enabled": true},
			obj{"metric_id": "gust", "enabled": true},
		},
	})
	if w.Code != http.StatusOK {
		t.Fatalf("B wieder aufnehmen: %d %s", w.Code, w.Body.String())
	}
	p14PruefeStufe(t, "nach Wieder-Aufnahme", p14Lesen(t, h, pfad, "nutzer-b"), levelsB)

	if got := teil3Fingerprint(t, s, "nutzer-a", teil3TripID); got != fpA {
		t.Fatalf("Datei von A durch B's Speichern veraendert")
	}
	a := teil3LoadTrip(t, s, "nutzer-a")
	if ml, _ := a.DisplayConfig["metric_alert_levels"].(map[string]interface{}); ml["wind_gust"] != "robust" {
		t.Errorf("A's Stufen veraendert: %v", ml)
	}
}

func TestP14_AC6_Vergleich_AbwaehlenUndWiederAufnehmen_StufeBleibt_ZweiNutzer(t *testing.T) {
	s := newTestStore(t)
	ampelB := obj{"template": "allgemein", "metrics": obj{"gust": p14GustZeile(true)}}
	levelsB := obj{"wind_gust": "sensibel"}
	teil3SeedPreset(t, s, "nutzer-a", teil3AmpelA(), obj{"metric_alert_levels": obj{"wind_gust": "robust"}})
	teil3SeedPreset(t, s, "nutzer-b", ampelB, nil)
	h := teil3CompareRouter(s)
	pfad := "/api/compare/presets/" + teil3PresetID
	vorherA := p14Lesen(t, h, pfad, "nutzer-a")

	put := func(wo string, ampel obj, aktiv []interface{}) {
		t.Helper()
		w := ampelAnfrage(t, h, "PUT", pfad, "nutzer-b", "de", obj{
			"display_config": obj{"ampel": ampel, "active_metrics": aktiv},
		})
		if w.Code != http.StatusOK {
			t.Fatalf("B %s: %d %s", wo, w.Code, w.Body.String())
		}
	}
	dcVon := func(o obj) obj { dc, _ := o["display_config"].(map[string]interface{}); return dc }

	put("abwaehlen", obj{"template": "allgemein", "metrics": obj{"gust": p14GustZeile(false)}},
		[]interface{}{obj{"metric_id": "temperature", "aggregation": "max"}})
	p14PruefeStufe(t, "nach Abwahl", dcVon(p14Lesen(t, h, pfad, "nutzer-b")), levelsB)

	put("wieder aufnehmen", obj{"template": "allgemein", "metrics": obj{"gust": p14GustZeile(true)}},
		[]interface{}{obj{"metric_id": "temperature", "aggregation": "max"}, obj{"metric_id": "gust", "aggregation": "max"}})
	p14PruefeStufe(t, "nach Wieder-Aufnahme", dcVon(p14Lesen(t, h, pfad, "nutzer-b")), levelsB)

	nachherA := p14Lesen(t, h, pfad, "nutzer-a")
	if !reflect.DeepEqual(dcVon(nachherA), dcVon(vorherA)) {
		t.Errorf("A's display_config durch B veraendert:\nvorher %v\nnachher %v", dcVon(vorherA), dcVon(nachherA))
	}
}
