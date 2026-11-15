package handler

// Issue #3031 (Inhalt je Kanal A1) — Test 8 / AC-10: zwei Nutzer, beide
// Speicherwege der neuen Karte „Inhalt je Kanal und Fläche".
// Spec: docs/specs/modules/feat_3031_inhalt_je_kanal_listen.md
//
// Die Karte im Reiter Wetter speichert IMMER den vollen Stand aller
// Listen-Kanaele in `display_config.channel_layouts` (Trip: PUT
// /api/trips/{id}/weather-config; Vergleich: PUT /api/compare/presets/{id}
// mit If-Match, zusaetzlich `channel_active_metrics` als Uebergang).
// Zugesichert wird serverseitig:
//   - der Stand wird unter der echten Nutzer-Kennung gespeichert (Auth-Kontext,
//     kein Rueckfall auf "default"); Nutzer B mit DERSELBEN Kennung bleibt
//     byte-gleich,
//   - `channel_layouts` wird als Ganzes uebernommen (Reihenfolge, enabled,
//     use_friendly_format je Zeile exakt wie gesendet),
//   - alle uebrigen display_config-Schluessel bleiben erhalten.
//
// Echte Handler, echter Store im Temp-Verzeichnis, kein Mock. Der Speicherweg
// existiert bereits (config_merge.go) — SCHUTZTEST, gruen erwartet.
//
//   go test ./internal/handler/ -run TestKanalInhalt3031

import (
	"encoding/json"
	"net/http"
	"reflect"
	"testing"
)

// kanalInhaltListen: voller Stand der drei Listen-Kanaele in der Form der Karte.
// Telegram umsortiert (gust vorn), SMS mit Aus-Zeile an ihrer Position.
func kanalInhaltListen() obj {
	z := func(id string, an, einfach bool) obj {
		return obj{"metric_id": id, "enabled": an, "use_friendly_format": einfach}
	}
	return obj{
		"email":    []interface{}{z("temperature", true, false), z("gust", true, true), z("wind", true, false)},
		"telegram": []interface{}{z("gust", true, false), z("temperature", true, false), z("wind", true, false)},
		"sms":      []interface{}{z("temperature", true, false), z("gust", false, false), z("wind", true, false)},
	}
}

func kanalInhaltJSON(t *testing.T, v interface{}) string {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatalf("json: %v", err)
	}
	return string(raw)
}

func TestKanalInhalt3031_Trip_ZweiNutzer_VollerStandAlsGanzes(t *testing.T) {
	s := newTestStore(t)
	teil3SeedTrip(t, s, "nutzer-a", teil3AmpelA(), nil)
	teil3SeedTrip(t, s, "nutzer-b", teil3AmpelBAlt(), nil)
	h := teil3TripRouter(s)

	fpB := teil3Fingerprint(t, s, "nutzer-b", teil3TripID)
	vorherA := teil3LoadTrip(t, s, "nutzer-a")

	listen := kanalInhaltListen()
	w := ampelAnfrage(t, h, "PUT", "/api/trips/"+teil3TripID+"/weather-config", "nutzer-a", "de", obj{
		"ampel":           vorherA.DisplayConfig["ampel"],
		"metrics":         vorherA.DisplayConfig["metrics"],
		"channel_layouts": listen,
	})
	if w.Code != http.StatusOK {
		t.Fatalf("A weather-config: %d %s", w.Code, w.Body.String())
	}

	if got := teil3Fingerprint(t, s, "nutzer-b", teil3TripID); got != fpB {
		t.Fatalf("Datei von Nutzer B durch das Speichern von Nutzer A veraendert")
	}

	a := teil3LoadTrip(t, s, "nutzer-a")
	if got, want := kanalInhaltJSON(t, a.DisplayConfig["channel_layouts"]), kanalInhaltJSON(t, listen); got != want {
		t.Errorf("channel_layouts nicht als Ganzes uebernommen:\n got %s\nwant %s", got, want)
	}
	for _, k := range []string{"preset_name", "metric_alert_levels", "alarm_ab_migration", "hourly_enabled"} {
		if !reflect.DeepEqual(a.DisplayConfig[k], vorherA.DisplayConfig[k]) {
			t.Errorf("A display_config[%s] veraendert: vorher %v, nachher %v", k, vorherA.DisplayConfig[k], a.DisplayConfig[k])
		}
	}
	if !reflect.DeepEqual(a.ReportConfig, vorherA.ReportConfig) {
		t.Errorf("A report_config veraendert")
	}

	// Gegenprobe: B liest seinen eigenen (alten) Stand, nicht den von A.
	b := teil3LoadTrip(t, s, "nutzer-b")
	if kanalInhaltJSON(t, b.DisplayConfig["channel_layouts"]) == kanalInhaltJSON(t, listen) {
		t.Errorf("Nutzer B hat die Kanallisten von Nutzer A bekommen")
	}
}

func TestKanalInhalt3031_Vergleich_ZweiNutzer_VollerStandAlsGanzes(t *testing.T) {
	s := newTestStore(t)
	teil3SeedPreset(t, s, "nutzer-a", teil3AmpelA(), nil)
	teil3SeedPreset(t, s, "nutzer-b", teil3AmpelBAlt(), nil)
	h := teil3CompareRouter(s)

	fpB := teil3Fingerprint(t, s, "nutzer-b", teil3PresetID)
	vorherA := teil3LoadPreset(t, s, "nutzer-a")

	listen := kanalInhaltListen()
	aktiv := obj{
		"email":    []interface{}{"temperature", "gust", "wind"},
		"telegram": []interface{}{"gust", "temperature", "wind"},
		"sms":      []interface{}{"temperature", "wind"},
	}
	code := teil3HubPut(t, h, "nutzer-a", obj{"display_config": obj{
		"ampel":                  vorherA.DisplayConfig["ampel"],
		"active_metrics":         vorherA.DisplayConfig["active_metrics"],
		"channel_layouts":        listen,
		"channel_active_metrics": aktiv,
	}})
	if code != http.StatusOK {
		t.Fatalf("A PUT: %d", code)
	}

	if teil3Fingerprint(t, s, "nutzer-b", teil3PresetID) != fpB {
		t.Fatalf("Datei von Nutzer B durch das Speichern von Nutzer A veraendert")
	}

	a := teil3LoadPreset(t, s, "nutzer-a")
	if got, want := kanalInhaltJSON(t, a.DisplayConfig["channel_layouts"]), kanalInhaltJSON(t, listen); got != want {
		t.Errorf("channel_layouts nicht als Ganzes uebernommen:\n got %s\nwant %s", got, want)
	}
	if got, want := kanalInhaltJSON(t, a.DisplayConfig["channel_active_metrics"]), kanalInhaltJSON(t, aktiv); got != want {
		t.Errorf("channel_active_metrics nicht als Ganzes uebernommen:\n got %s\nwant %s", got, want)
	}
	for _, k := range []string{"metric_alert_levels", "alarm_ab_migration", "ideal_ranges"} {
		if !reflect.DeepEqual(a.DisplayConfig[k], vorherA.DisplayConfig[k]) {
			t.Errorf("A display_config[%s] veraendert: vorher %v, nachher %v", k, vorherA.DisplayConfig[k], a.DisplayConfig[k])
		}
	}
	if a.UserID != "nutzer-a" {
		t.Errorf("Preset nicht unter der echten Nutzer-Kennung gespeichert: %q", a.UserID)
	}

	b := teil3LoadPreset(t, s, "nutzer-b")
	if kanalInhaltJSON(t, b.DisplayConfig["channel_layouts"]) == kanalInhaltJSON(t, listen) {
		t.Errorf("Nutzer B hat die Kanallisten von Nutzer A bekommen")
	}
}
