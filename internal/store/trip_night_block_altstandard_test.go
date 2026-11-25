package store_test

// Rework #3020 R1, AC-9 (Server-Teil): ein Alt-Trip ohne Feld `display_config.show_night_block`
// bleibt ohne Feld, wenn der Nutzer speichert, ohne den Nachtblock-Schalter zu beruehren (der
// Python-Kern liest „fehlt“ als „an“; ein still geschriebenes `false`/`true` aenderte den Standard).
// Ersatz fuer den mit #3357 geloeschten trip_night_block_schalter_verdrahtung.test.ts.
//
// Spec: docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md (AC-9)
// Zwei Nutzer mit derselben Trip-ID; Hilfen in trip_skip_next_erhalt_test.go.

import "testing"

func TestRework3020_AltTripOhneNightBlockBleibtOhneFeld_ZweiNutzer(t *testing.T) {
	s, dir := rw3020Store(t)
	dcAlt := func() map[string]interface{} {
		return map[string]interface{}{
			"metrics": []interface{}{map[string]interface{}{"metric_id": "wind", "enabled": true}},
		}
	}
	rw3020Seed(t, s, rw3020NutzerA, map[string]interface{}{"enabled": true}, dcAlt())
	rw3020Seed(t, s, rw3020NutzerB, map[string]interface{}{"enabled": true}, dcAlt())
	vorherB := rw3020Datei(t, dir, rw3020NutzerB)
	if _, da := rw3020Teil(t, rw3020Roh(t, dir, rw3020NutzerA), "display_config")["show_night_block"]; da {
		t.Fatal("Vorbedingung: der Alt-Trip darf show_night_block noch nicht tragen")
	}

	// Die Karte speichert einen anderen Schalter (Großwetterlage, report_config) -- Nachtblock unberührt.
	rw3020Put(t, s, rw3020NutzerA, `{"report_config":{"show_stability":false}}`)
	// Ein anderer Reiter schreibt einen eigenen display_config-Schluessel (Teilfeld-Merge).
	rw3020Put(t, s, rw3020NutzerA, `{"display_config":{"metric_alert_levels":{"wind":"sensibel"}}}`)

	rohA := rw3020Roh(t, dir, rw3020NutzerA)
	if rw3020Teil(t, rohA, "report_config")["show_stability"] != false {
		t.Fatalf("Vorbedingung: der gesendete Schalter muss ankommen: %v", rohA["report_config"])
	}
	if wert, da := rw3020Teil(t, rohA, "display_config")["show_night_block"]; da {
		t.Errorf("Alt-Trip von A trägt nach dem Speichern show_night_block=%v -- das Feld darf nicht neu geschrieben werden", wert)
	}
	if nachherB := rw3020Datei(t, dir, rw3020NutzerB); string(nachherB) != string(vorherB) {
		t.Errorf("Alt-Trip von Nutzer B wurde durch das Speichern von A verändert:\nvorher %s\nnachher %s", vorherB, nachherB)
	}
	if _, da := rw3020Teil(t, rw3020Roh(t, dir, rw3020NutzerB), "display_config")["show_night_block"]; da {
		t.Error("Alt-Trip von Nutzer B trägt plötzlich show_night_block")
	}
}
