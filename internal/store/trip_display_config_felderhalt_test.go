package store_test

// Rework #3020 R1, AC-12 und AC-17 (Merge-Teil): Speichern ohne Aenderung bzw. ein Teil-Update
// von display_config erhaelt alle nicht gesendeten Felder -- insbesondere je Metrik
// `morning_enabled`, `evening_enabled`, `format_mode` in `display_config.metrics`.
// Ersatz fuer die mit #3357 geloeschten feld_erhalt_ohne_ausnahme.test.ts und
// editor_speichern_ohne_aenderung.test.ts, jetzt im Go-Speicherpfad (UpdateTripHandler -> Store).
//
// Spec: docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md (AC-12, AC-17)
// Zwei Nutzer mit derselben Trip-ID; Hilfen in trip_skip_next_erhalt_test.go.

import (
	"reflect"
	"testing"
)

func rw3020MetrikenMitBerichtFlags(fmtWind string) []interface{} {
	return []interface{}{
		map[string]interface{}{"metric_id": "wind", "enabled": true, "morning_enabled": true, "evening_enabled": false, "format_mode": fmtWind},
		map[string]interface{}{"metric_id": "temperature", "enabled": true, "morning_enabled": false, "evening_enabled": true, "format_mode": "raw"},
	}
}

func rw3020Metriken(t *testing.T, dir, nutzer string) interface{} {
	t.Helper()
	return rw3020Teil(t, rw3020Roh(t, dir, nutzer), "display_config")["metrics"]
}

func TestRework3020_SpeichernOhneAenderungErhaeltMetrikFlags_ZweiNutzer(t *testing.T) {
	s, dir := rw3020Store(t)
	rw3020Seed(t, s, rw3020NutzerA, map[string]interface{}{"enabled": true},
		map[string]interface{}{"metrics": rw3020MetrikenMitBerichtFlags("simplified")})
	rw3020Seed(t, s, rw3020NutzerB, map[string]interface{}{"enabled": true},
		map[string]interface{}{"metrics": rw3020MetrikenMitBerichtFlags("raw")})
	vorherA := rw3020Metriken(t, dir, rw3020NutzerA)
	vorherB := rw3020Datei(t, dir, rw3020NutzerB)

	// Speichern ohne Aenderung an den Metriken: Schalter und Warnungswerte gehen, metrics nicht.
	rw3020Put(t, s, rw3020NutzerA, `{"report_config":{"show_stage_stats":true}}`)
	rw3020Put(t, s, rw3020NutzerA, `{"display_config":{"show_night_block":false}}`)

	if nachher := rw3020Metriken(t, dir, rw3020NutzerA); !reflect.DeepEqual(nachher, vorherA) {
		t.Errorf("display_config.metrics von A verändert (morning_enabled/evening_enabled/format_mode):\nvorher  %v\nnachher %v", vorherA, nachher)
	}
	if nachherB := rw3020Datei(t, dir, rw3020NutzerB); string(nachherB) != string(vorherB) {
		t.Errorf("Trip von Nutzer B wurde durch das Speichern von A verändert:\nvorher %s\nnachher %s", vorherB, nachherB)
	}
}

func TestRework3020_TeilUpdateAusblickUndWarnungswerteErhaeltUebrigeFelder_ZweiNutzer(t *testing.T) {
	s, dir := rw3020Store(t)
	dc := func(fmtWind string) map[string]interface{} {
		return map[string]interface{}{
			"metrics":             rw3020MetrikenMitBerichtFlags(fmtWind),
			"metric_alert_levels": map[string]interface{}{"wind": "normal"},
			"placements":          map[string]interface{}{"version": float64(1), "rows": []interface{}{}, "outlook_reports": []interface{}{"evening"}},
			"ampel":               map[string]interface{}{"template": "wandern"},
		}
	}
	rw3020Seed(t, s, rw3020NutzerA, map[string]interface{}{"enabled": true}, dc("simplified"))
	rw3020Seed(t, s, rw3020NutzerB, map[string]interface{}{"enabled": true}, dc("raw"))
	vorherA := rw3020Teil(t, rw3020Roh(t, dir, rw3020NutzerA), "display_config")
	vorherB := rw3020Datei(t, dir, rw3020NutzerB)

	rw3020Put(t, s, rw3020NutzerA, `{"display_config":{"metric_alert_levels":{"wind":"sensibel","gust":"robust"}}}`)
	rw3020Put(t, s, rw3020NutzerA, `{"display_config":{"placements":{"version":1,"rows":[],"outlook_reports":["morning"]}}}`)

	nachA := rw3020Teil(t, rw3020Roh(t, dir, rw3020NutzerA), "display_config")
	if !reflect.DeepEqual(nachA["metric_alert_levels"], map[string]interface{}{"wind": "sensibel", "gust": "robust"}) {
		t.Errorf("metric_alert_levels von A nicht wie gesendet: %v", nachA["metric_alert_levels"])
	}
	pl, _ := nachA["placements"].(map[string]interface{})
	if !reflect.DeepEqual(pl["outlook_reports"], []interface{}{"morning"}) {
		t.Errorf("placements.outlook_reports von A nicht wie gesendet: %v", nachA["placements"])
	}
	for _, feld := range []string{"metrics", "ampel"} {
		if !reflect.DeepEqual(nachA[feld], vorherA[feld]) {
			t.Errorf("display_config.%s von A durch das Teil-Update verändert:\nvorher  %v\nnachher %v", feld, vorherA[feld], nachA[feld])
		}
	}
	for _, alt := range []string{"show_outlook", "multi_day_trend_reports"} {
		if _, da := nachA[alt]; da {
			t.Errorf("Altfeld display_config.%s im gespeicherten Stand von A", alt)
		}
	}
	if nachherB := rw3020Datei(t, dir, rw3020NutzerB); string(nachherB) != string(vorherB) {
		t.Errorf("Trip von Nutzer B wurde durch das Speichern von A verändert:\nvorher %s\nnachher %s", vorherB, nachherB)
	}
}
