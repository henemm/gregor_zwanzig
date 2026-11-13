package router

// Issue #2961 (Spec AC-18, Fix-Runde Gegenpruefung F1): Negativfaelle der
// Zielregel des Staging-Tokens. Jeder Fall muss dieselbe 404 liefern wie ein
// unbekanntes Konto, und es darf kein Token entstehen. Die Faelle fangen die
// Verfaelschungen "Bestaetigt-Pruefung entfernt" und "Fenster stark
// vergroessert".

import (
	"net/http"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

func TestStagingToken_ZielregelNegativfaelle(t *testing.T) {
	t.Setenv("GZ_ENV", "staging")
	e := neueBremsUmgebung(t, nil)
	jetzt := time.Now()
	bestaetigt := jetzt.Add(-time.Minute)
	alt := jetzt.Add(-30 * 24 * time.Hour)

	aufrufer := e.kontoMit(t, model.User{ID: "anna-aufruf", Email: "anna@beispiel.de", CreatedAt: alt, EmailVerifiedAt: &bestaetigt})
	for _, u := range []model.User{
		// frisch registriert, aber bereits bestaetigt
		{ID: "frisch-bestaetigt", Email: "fb@beispiel.de", CreatedAt: jetzt.Add(-5 * time.Minute), EmailVerifiedAt: &bestaetigt},
		// unbestaetigt, 1 h + 1 min alt
		{ID: "knapp-zu-alt", Email: "kza@beispiel.de", CreatedAt: jetzt.Add(-time.Hour - time.Minute)},
		// alt, nie bestaetigt
		{ID: "alt-unbestaetigt", Email: "au@beispiel.de", CreatedAt: alt},
	} {
		if err := e.s.SaveUser(u); err != nil {
			t.Fatal(err)
		}
	}

	ref := e.rufe(t, http.MethodPost, "/api/auth/verify-email/staging-token", []byte(`{"username":"gibt-es-nicht"}`), aufrufer)
	if ref.Code != http.StatusNotFound {
		t.Fatalf("Referenz unbekanntes Konto: %d %s", ref.Code, ref.Body.String())
	}
	for _, ziel := range []string{"frisch-bestaetigt", "knapp-zu-alt", "alt-unbestaetigt"} {
		w := e.rufe(t, http.MethodPost, "/api/auth/verify-email/staging-token", []byte(`{"username":"`+ziel+`"}`), aufrufer)
		if w.Code != http.StatusNotFound || w.Body.String() != ref.Body.String() {
			t.Errorf("%s: erwartet dieselbe 404 wie unbekannt, bekommen %d %s", ziel, w.Code, w.Body.String())
		}
		if tok, _ := e.s.LoadVerificationToken(ziel); tok != nil {
			t.Errorf("%s: Token entstanden", ziel)
		}
	}
}
