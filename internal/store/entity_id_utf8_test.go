package store

import "testing"

// Issue #2961 (Fix-Runde F8, Spec AC-8): ungueltiges UTF-8 kann in der
// geteilten JSON-Wahrheitstabelle nicht stehen — dieser Fall ist Go-eigen.
// C1-Steuerzeichen und U+2028/U+2029 stehen zusaetzlich in der Tabelle.
func TestValidEntityID_UngueltigesUTF8UndC1(t *testing.T) {
	for _, id := range []string{
		"a\xffb", "\xc3", "trip\xe2\x80", "\xed\xa0\x80x", // ungueltiges UTF-8 / Surrogat
		"a\u0080b", "\u0085x", "a\u009fb", "a b", " x",
	} {
		if ValidEntityID(id) {
			t.Errorf("ValidEntityID(%q) = true, erwartet false", id)
		}
	}
	for _, id := range []string{"mühlbach", "pollença", "a b", "a�b", "Etappe 2 Sóller"} {
		if !ValidEntityID(id) {
			t.Errorf("ValidEntityID(%q) = false, erwartet true", id)
		}
	}
}
