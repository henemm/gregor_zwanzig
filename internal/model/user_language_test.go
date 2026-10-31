package model

// Issue #2646 (i18n S1) — die wirksame Nutzersprache. Spec:
// docs/specs/modules/i18n_s1_sprachfeld_nutzer_2646.md (Go: Modell).
//
// Zusicherung: genau "de" und "en" sind gueltig (strikt, Kleinschreibung,
// leer ungueltig); Lang() liefert fuer leer/unbekannt "de".

import "testing"

func TestIsValidLanguageNurDeUndEn(t *testing.T) {
	gueltig := []string{"de", "en"}
	ungueltig := []string{"", "fr", "EN", "De", " en", "en ", "deu", "english"}
	for _, s := range gueltig {
		if !IsValidLanguage(s) {
			t.Errorf("IsValidLanguage(%q) = false, erwartet true", s)
		}
	}
	for _, s := range ungueltig {
		if IsValidLanguage(s) {
			t.Errorf("IsValidLanguage(%q) = true, erwartet false (strikt, kein Trimmen/Grossschreiben)", s)
		}
	}
}

func TestUserLangLeerOderUnbekanntIstDeutsch(t *testing.T) {
	cases := map[string]string{
		"":   LangDe,
		"de": LangDe,
		"en": LangEn,
		"fr": LangDe,
		"EN": LangDe,
	}
	for gespeichert, want := range cases {
		u := &User{ID: "anna", Language: gespeichert}
		if got := u.Lang(); got != want {
			t.Errorf("User{Language:%q}.Lang() = %q, erwartet %q", gespeichert, got, want)
		}
	}
	if LangDe != "de" || LangEn != "en" {
		t.Errorf("Konstanten falsch: LangDe=%q LangEn=%q", LangDe, LangEn)
	}
}
