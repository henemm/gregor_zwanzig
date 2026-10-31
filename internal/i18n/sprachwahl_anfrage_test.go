package i18n

// Issue #2675 (i18n G1) — Aufloesungsreihenfolge der Sprache je Anfrage.
// Spec: docs/specs/modules/i18n_g1_go_kern_2675.md — AC-3.
//
// Reihenfolge: Nutzer > Cookie gz_lang > Accept-Language > de. Echte
// http.Request-Objekte, echtes model.User.

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func anfrage(cookie, accept string) *http.Request {
	r := httptest.NewRequest(http.MethodGet, "/api/briefings/x", nil)
	if cookie != "" {
		r.AddCookie(&http.Cookie{Name: CookieName, Value: cookie})
	}
	if accept != "" {
		r.Header.Set("Accept-Language", accept)
	}
	return r
}

func TestFromRequestReihenfolge(t *testing.T) {
	cases := []struct {
		name           string
		userLang       *string // nil = kein Nutzer (oeffentlich)
		cookie, accept string
		want           Lang
	}{
		// AC-3
		{"Nutzer ohne Sprache, Cookie en vor Header de", strp(""), "en", "de", En},
		{"Nutzer de vor Cookie en", strp("de"), "en", "en", De},
		{"Nutzer en vor Cookie de und Header de", strp("en"), "de", "de", En},
		{"Cookie fr wird ignoriert, Header en gilt", nil, "fr", "en", En},
		{"Cookie fr ohne Header -> de", nil, "fr", "", De},
		{"Cookie EN (Grossschreibung) ungueltig", nil, "EN", "en", En},
		// oeffentlich
		{"oeffentlich Cookie en", nil, "en", "", En},
		{"oeffentlich Cookie de vor Header en", nil, "de", "en", De},
		{"ohne alles -> de", nil, "", "", De},
		{"Nutzer mit ungueltiger Sprache faellt durch", strp("fr"), "", "en", En},
		// Accept-Language
		{"en-US mit q-Werten", nil, "", "en-US,en;q=0.9,de;q=0.8", En},
		{"de hoeher gewichtet als en", nil, "", "en;q=0.5,de;q=0.9", De},
		{"Standard-q=1 schlaegt q=0.9", nil, "", "de-AT;q=0.9,en-GB", En},
		{"q=0 wird ignoriert", nil, "", "en;q=0,de;q=0.1", De},
		{"nur q=0 -> de", nil, "", "en;q=0", De},
		{"unbekannte Sprachen werden uebersprungen", nil, "", "fr-FR,it;q=0.9,en;q=0.2", En},
		{"nur unbekannte -> de", nil, "", "fr,es", De},
		{"Grossschreibung im Header", nil, "", "EN-us", En},
		{"Leerzeichen und Stern", nil, "", " * , en ; q=0.4 ", En},
		{"kaputter q-Wert wird uebersprungen", nil, "", "en;q=abc,de;q=0.1", De},
	}
	for _, tc := range cases {
		var u *model.User
		if tc.userLang != nil {
			u = &model.User{ID: "nutzer-a", Language: *tc.userLang}
		}
		if got := FromRequest(anfrage(tc.cookie, tc.accept), u); got != tc.want {
			t.Errorf("%s: FromRequest = %q, erwartet %q", tc.name, got, tc.want)
		}
	}
}

func strp(s string) *string { return &s }

func TestFromContextUndWithLang(t *testing.T) {
	if got := FromContext(context.Background()); got != De {
		t.Errorf("FromContext ohne Sprache = %q, erwartet de", got)
	}
	ctx := WithLang(context.Background(), En)
	if got := FromContext(ctx); got != En {
		t.Errorf("FromContext nach WithLang(En) = %q", got)
	}
	// Kontexte sind unabhaengig: kein globaler Sprachzustand.
	ctxDe := WithLang(context.Background(), De)
	if FromContext(ctx) != En || FromContext(ctxDe) != De {
		t.Errorf("zwei Kontexte beeinflussen sich gegenseitig")
	}
	if got := FromContext(WithLang(context.Background(), Lang("fr"))); got != De {
		t.Errorf("WithLang(fr) = %q, erwartet de", got)
	}
}
