package handler

// Issue #3276 (Epic #3122, Spec feat_3276_vergleich_altfelder_entfernen, AC-7):
// Der Ortsvergleich-Client laesst die sechs Altschluessel (channel_layouts,
// outlook_metrics, outlook_metric_formats, channel_active_metrics,
// hourly_metrics, hourly_metric_formats) kuenftig ganz weg. Der Server darf
// einen solchen Rumpf weder ablehnen noch Defaults setzen, und die im Bestand
// gespeicherten Altwerte bleiben per Top-Level-Merge (mergeConfigMap) erhalten.
//
// Regressionsschutz: dieser Test ist schon vor der Frontend-Aenderung gruen
// (Spec: "keine Go-Aenderung noetig"); er sichert die Voraussetzung, auf der
// das Weglassen im Frontend beruht.

import (
	"encoding/json"
	"reflect"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

var altschluessel3276 = []string{
	"channel_layouts", "outlook_metrics", "outlook_metric_formats",
	"channel_active_metrics", "hourly_metrics", "hourly_metric_formats",
}

func TestApplyComparePresetPatch_3276_OhneAltschluessel_BestandBleibt(t *testing.T) {
	bestand := map[string]interface{}{
		"region":                 "Ortler",
		"channel_layouts":        map[string]interface{}{"email": []interface{}{"temp_max_c"}},
		"outlook_metrics":        []interface{}{"temp_max_c"},
		"outlook_metric_formats": map[string]interface{}{"temp_max_c": true},
		"channel_active_metrics": map[string]interface{}{"sms": []interface{}{}},
		"hourly_metrics":         []interface{}{"temp_c"},
		"hourly_metric_formats":  map[string]interface{}{"temp_c": false},
	}
	original := model.ComparePreset{
		ID: "cp-3276", Name: "A", UserID: "usera", LocationIDs: []string{"loc-a"},
		Schedule: "manual", Profil: "allgemein", HourFrom: 8, HourTo: 17,
		CreatedAt: time.Now().UTC(), DisplayConfig: bestand,
	}
	// Rumpf wie der Ortsvergleich ihn nach #3276 sendet: Teilfelder ohne Altschluessel.
	patch, _ := json.Marshal(map[string]interface{}{
		"hourly_enabled": false,
		"display_config": map[string]interface{}{
			"placements": map[string]interface{}{"rows": []interface{}{map[string]interface{}{"metric": "temp_max_c"}}},
		},
	})
	p, err := applyComparePresetPatch(original, "cp-3276", patch, time.Now().UTC())
	if err != nil {
		t.Fatalf("Rumpf ohne Altschluessel abgelehnt: %v", err)
	}
	for _, k := range altschluessel3276 {
		if !reflect.DeepEqual(p.DisplayConfig[k], bestand[k]) {
			t.Errorf("Altwert %s veraendert: vorher %#v, nachher %#v", k, bestand[k], p.DisplayConfig[k])
		}
	}
	if p.DisplayConfig["placements"] == nil {
		t.Errorf("placements fehlen nach dem Merge")
	}
	if p.DisplayConfig["region"] != "Ortler" {
		t.Errorf("region verloren: %#v", p.DisplayConfig["region"])
	}
}

func TestApplyComparePresetPatch_3276_OhneAltschluessel_KeinServerDefault(t *testing.T) {
	original := model.ComparePreset{
		ID: "cp-3276-neu", Name: "B", UserID: "userb", LocationIDs: []string{"loc-b"},
		Schedule: "manual", Profil: "allgemein", HourFrom: 8, HourTo: 17,
		CreatedAt: time.Now().UTC(), DisplayConfig: map[string]interface{}{"region": "Stubai"},
	}
	patch, _ := json.Marshal(map[string]interface{}{"display_config": map[string]interface{}{"region": "Stubai"}})
	p, err := applyComparePresetPatch(original, "cp-3276-neu", patch, time.Now().UTC())
	if err != nil {
		t.Fatalf("abgelehnt: %v", err)
	}
	for _, k := range altschluessel3276 {
		if _, da := p.DisplayConfig[k]; da {
			t.Errorf("Server setzt Default fuer Altschluessel %s: %#v", k, p.DisplayConfig[k])
		}
	}
}
