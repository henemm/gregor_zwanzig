package handler

// TDD RED/NETZ — Issue #2276 Scheibe S1 (AC-1), Epic #2345.
// Spec: docs/specs/modules/rework_2276_s1_netz_und_fundament.md § AC-1
//
// Beweislücke, die dieser Test schliesst: Weg 1 des Compare-PUT
// (PUT /api/compare/presets/{id}, UpdateComparePresetHandler) laeuft seit
// #2285 ueber denselben Merge-Kernel wie Weg 2 (applyComparePresetPatch ->
// mergeBriefingPatch). Die Zusicherung "ein Teil-PUT, das nur ein Feld
// schickt, laesst alle uebrigen Felder unveraendert" ist fuer Weg 1 aber
// NIRGENDS mit einem echten Minimal-Body belegt: die beiden vorhandenen
// Tests, die sie streifen (compare_preset_official_warnings_test.go,
// compare_preset_alert_channel_thresholds_test.go), senden beide weiterhin
// ALLE Pflichtfelder mit und belegen daher nur "ein mitgesendetes Feld
// gewinnt", nicht "ein fehlendes Pflichtfeld wird aus dem Original ererbt".
// Die Scheiben S2-S6 bauen den Ortsvergleich-Hub vollstaendig auf genau
// dieser Zusicherung um.
//
// Erwartung im RED-Lauf: dieser Test ist GRUEN, sobald er existiert — er ist
// ein NETZ fuer bereits ausgeliefertes Verhalten (#2285), kein Treiber fuer
// neuen Code. Sein Waechter-Nachweis ist die Mutations-Gegenprobe (a) der
// Spec: den Merge-Aufruf in applyComparePresetPatch umgehen und den Patch in
// ein frisches model.ComparePreset{} unmarshalen ⇒ dieser Test wird rot
// (400 validation_error statt 200), weil die Pflichtfelder dann leer sind.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
)

// AC-1: ein PUT mit GENAU EINEM flachen Feld (`name`) und OHNE jedes
// Pflichtfeld wird angenommen (200, nicht 400) und laesst alle nicht
// gesendeten Felder unveraendert — flach wie verschachtelt.
func TestUpdateComparePreset_SingleFieldPatch_PreservesEverythingElse(t *testing.T) {
	s := newTestStore(t)

	created := time.Now().UTC().Add(-48 * time.Hour)
	original := model.ComparePreset{
		ID:          "cp-2276-s1-ac1",
		Name:        "Zillertal taeglich",
		UserID:      "user1",
		LocationIDs: []string{"loc-mayrhofen", "loc-ginzling", "loc-hintertux"},
		Schedule:    "daily",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    7,
		HourTo:      19,
		Empfaenger:  []string{"a@example.com", "b@example.com"},
		// Alle VIER Kanaele gesetzt — #1461 hatte nur zwei in der Fixture,
		// der generische Merge-Kernel muss alle vier gleich behandeln.
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{
			Email:      alertThresholdStrPtr("MODERATE"),
			Telegram:   alertThresholdStrPtr("HIGH"),
			Sms:        alertThresholdStrPtr("SEVERE"),
			PremiumSms: alertThresholdStrPtr("EXTREME"),
		},
		// Mindestens zwei Quellen: so belegt die Assertion auch Laenge UND
		// Reihenfolge, nicht nur "irgendein Eintrag ueberlebt".
		OfficialWarnings: &model.OfficialWarningsConfig{
			Enabled: true,
			Sources: []string{"geosphere_warn", "meteoalarm"},
		},
		CreatedAt: created,
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	// DER Prüfling: ein Minimal-Body. Kein schedule, kein profil, kein
	// hour_from/hour_to, keine location_ids, keine empfaenger.
	buf, _ := json.Marshal(map[string]interface{}{"name": "Zillertal taeglich (umbenannt)"})

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-2276-s1-ac1", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	// Der eigentliche Beweis: die Pflichtfeldpruefung (validateComparePreset)
	// muss mit den aus `original` ererbten Werten bestehen. Ein 400 hiesse,
	// der Merge zieht die fehlenden Pflichtfelder NICHT aus dem Original.
	if w.Code != http.StatusOK {
		t.Fatalf("Minimal-PUT abgelehnt: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	if len(loaded) != 1 {
		t.Fatalf("erwartet genau 1 gespeicherter Ortsvergleich, bekommen %d", len(loaded))
	}
	p := loaded[0]

	if p.Name != "Zillertal taeglich (umbenannt)" {
		t.Errorf("das eine gesendete Feld muss gewinnen: erwartet umbenannt, bekommen %q", p.Name)
	}

	// --- flache Pflichtfelder: bytegleich zum Original ---
	if p.Schedule != original.Schedule {
		t.Errorf("schedule vom Minimal-PUT ueberschrieben: erwartet %q, bekommen %q", original.Schedule, p.Schedule)
	}
	if p.Profil != original.Profil {
		t.Errorf("profil vom Minimal-PUT ueberschrieben: erwartet %q, bekommen %q", original.Profil, p.Profil)
	}
	if p.HourFrom != original.HourFrom || p.HourTo != original.HourTo {
		t.Errorf("Tagesfenster vom Minimal-PUT ueberschrieben: erwartet %d-%d, bekommen %d-%d",
			original.HourFrom, original.HourTo, p.HourFrom, p.HourTo)
	}
	if got, want := jsonOf(t, p.LocationIDs), jsonOf(t, original.LocationIDs); got != want {
		t.Errorf("location_ids vom Minimal-PUT veraendert: erwartet %s, bekommen %s", want, got)
	}
	if got, want := jsonOf(t, p.Empfaenger), jsonOf(t, original.Empfaenger); got != want {
		t.Errorf("empfaenger vom Minimal-PUT veraendert: erwartet %s, bekommen %s", want, got)
	}

	// --- verschachtelt (1): alle VIER Alarm-Kanal-Schwellen ---
	if p.AlertChannelThresholds == nil {
		t.Fatalf("alert_channel_thresholds vom Minimal-PUT geloescht (nil)")
	}
	for _, c := range []struct {
		name string
		got  *string
		want string
	}{
		{"email", p.AlertChannelThresholds.Email, "MODERATE"},
		{"telegram", p.AlertChannelThresholds.Telegram, "HIGH"},
		{"sms", p.AlertChannelThresholds.Sms, "SEVERE"},
		{"premium_sms", p.AlertChannelThresholds.PremiumSms, "EXTREME"},
	} {
		if c.got == nil || *c.got != c.want {
			t.Errorf("alert_channel_thresholds.%s vom Minimal-PUT verloren: erwartet %q, bekommen %v",
				c.name, c.want, c.got)
		}
	}

	// --- verschachtelt (2): amtliche Warnquellen, Laenge UND Reihenfolge ---
	if p.OfficialWarnings == nil {
		t.Fatalf("official_warnings vom Minimal-PUT geloescht (nil)")
	}
	if !p.OfficialWarnings.Enabled {
		t.Errorf("official_warnings.enabled vom Minimal-PUT zurueckgesetzt")
	}
	if got, want := jsonOf(t, p.OfficialWarnings.Sources), jsonOf(t, original.OfficialWarnings.Sources); got != want {
		t.Errorf("official_warnings.sources vom Minimal-PUT veraendert: erwartet %s, bekommen %s", want, got)
	}
}

// jsonOf vergleicht Listen bytegleich (Laenge UND Reihenfolge) mit einer
// lesbaren Fehlermeldung — reflect.DeepEqual meldet im Fehlerfall nichts,
// was man ohne Debugger deuten koennte.
func jsonOf(t *testing.T, v interface{}) string {
	t.Helper()
	b, err := json.Marshal(v)
	if err != nil {
		t.Fatalf("json.Marshal: %v", err)
	}
	return string(b)
}
