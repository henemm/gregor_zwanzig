package store

import "testing"

// Issue #2961 (ADR-0114 Punkt 2): Go ist strenger als die geteilte
// Wahrheitstabelle (tests/fixtures/entity_id_pattern_parity/faelle.json) —
// Steuerzeichen sowie "?", "#" und "%" sind in Entitaets-Kennungen gesperrt.
// Diese Faelle stehen bewusst NICHT in der geteilten Tabelle, solange die
// Python-Seite (app.loader.VALID_ENTITY_ID_RE) nicht nachgezogen ist; die
// Bestandsfaelle der Tabelle bleiben gueltig.
func TestValidEntityID_SperrtUpstreamSteuerzeichen(t *testing.T) {
	for _, id := range []string{
		"a?b", "?", "a#b", "#x", "a%3Fb", "%", "a\nb", "\tx", "a\x7fb", "a\x1fb", "x\r",
	} {
		if ValidEntityID(id) {
			t.Errorf("ValidEntityID(%q) = true, erwartet false", id)
		}
	}
	for _, id := range []string{
		"trip123", "cp-a1b2c3d4", "hochfügen", "pollença", "zillertal-t-glich",
		"gr221-mallorca", "a1b2c3d4", "mühl bach", "x.y", "a_b",
	} {
		if !ValidEntityID(id) {
			t.Errorf("ValidEntityID(%q) = false, erwartet true (Bestandsschutz)", id)
		}
	}
}
