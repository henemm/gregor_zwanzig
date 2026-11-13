package handler

// Issue #2961 Nachbesserung (Gegenpruefung F2) — Fehlversuchsbremse als
// gleitendes Fenster: hoechstens max Versuche in JEDEM Intervall der
// Fensterlaenge, kein Ruecksetzen an einem festen Fensterrand. Uhr injiziert.

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
)

type testUhr2961 struct{ t time.Time }

func (u *testUhr2961) jetzt() time.Time       { return u.t }
func (u *testUhr2961) weiter(d time.Duration) { u.t = u.t.Add(d) }
func neueTestUhr2961() *testUhr2961 {
	return &testUhr2961{t: time.Date(2026, 11, 13, 8, 0, 0, 0, time.UTC)}
}
func guardMitUhr2961(u *testUhr2961) *attemptGuard {
	g := newAttemptGuard(5, 15*time.Minute, 15*time.Minute)
	g.setNow(u.jetzt)
	return g
}

// 4 Versuche bei t0, weitere bei t0+15min−ε: der 5. ist noch im gleitenden
// Fenster und loest die Sperre aus, ab dem 6. ist gesperrt.
func TestAttemptGuard_GleitendesFensterUeberDenFensterrand(t *testing.T) {
	u := neueTestUhr2961()
	g := guardMitUhr2961(u)
	for i := 1; i <= 4; i++ {
		if !g.Reserve("k") {
			t.Fatalf("Versuch %d bei t0: erwartet erlaubt", i)
		}
	}
	u.weiter(15*time.Minute - time.Second)
	if !g.Reserve("k") {
		t.Fatal("5. Versuch bei t0+15min−ε: erwartet erlaubt")
	}
	if g.Reserve("k") {
		t.Fatal("6. Versuch im gleitenden Fenster: erwartet gesperrt")
	}
}

// Ein fester Fensterrand darf das Kontingent nicht auffrischen: 1 Versuch bei
// t0, 3 bei t0+14min; bei t0+15min+ε faellt nur der erste aus dem Fenster —
// es bleiben ZWEI freie Versuche, nicht fuenf.
func TestAttemptGuard_KeinRuecksetzenAmFestenFensterrand(t *testing.T) {
	u := neueTestUhr2961()
	g := guardMitUhr2961(u)
	g.Reserve("k")
	u.weiter(14 * time.Minute)
	for i := 0; i < 3; i++ {
		g.Reserve("k")
	}
	u.weiter(time.Minute + time.Second) // t0+15min+1s
	for i := 1; i <= 2; i++ {
		if !g.Reserve("k") {
			t.Fatalf("freier Versuch %d: erwartet erlaubt (3 im Fenster)", i)
		}
	}
	if g.Reserve("k") {
		t.Fatal("danach 5 Versuche im gleitenden Fenster: erwartet gesperrt")
	}
}

// Die Sperre dauert 15 Minuten ab dem 5. Versuch — unabhaengig davon, wann
// die ersten Versuche lagen.
func TestAttemptGuard_SperrdauerAbDemFuenftenVersuch(t *testing.T) {
	u := neueTestUhr2961()
	g := guardMitUhr2961(u)
	for i := 0; i < 5; i++ {
		g.Reserve("k")
		u.weiter(time.Minute) // Versuche bei t0 … t0+4min
	}
	// 5. Versuch lag bei t0+4min; jetzt ist t0+5min.
	u.weiter(14*time.Minute - time.Second) // t0+19min−1s
	if g.Reserve("k") {
		t.Fatal("vor Ablauf von 15 min nach dem 5. Versuch: erwartet gesperrt")
	}
	u.weiter(2 * time.Second) // t0+19min+1s
	if !g.Reserve("k") {
		t.Fatal("nach Ablauf der Sperre: erwartet erlaubt")
	}
	if g.Reserve("x") == false {
		t.Fatal("anderer Schluessel: erwartet erlaubt")
	}
}

// Erfolg setzt den Zaehler zurueck: danach sind wieder volle 5 Versuche frei.
func TestAttemptGuard_ErfolgSetztZurueck(t *testing.T) {
	u := neueTestUhr2961()
	g := guardMitUhr2961(u)
	for i := 0; i < 4; i++ {
		g.Reserve("k")
	}
	g.Success("k")
	for i := 1; i <= 5; i++ {
		if !g.Reserve("k") {
			t.Fatalf("nach Erfolg Versuch %d: erwartet erlaubt", i)
		}
	}
	if g.Reserve("k") {
		t.Fatal("6. Versuch nach Erfolg: erwartet gesperrt")
	}
}

// M04: Code-Anmeldung — eine erfolgreiche Anmeldung setzt den Adresszaehler
// zurueck (4 Fehlversuche, Erfolg, danach wieder 4 Fehlversuche ohne Sperre).
func TestAnmeldeCode_ErfolgSetztAdresszaehlerZurueck(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	ResetOTPStoreForTest()
	s := newTestStore(t)
	if err := s.SaveUser(model.User{ID: "reset1", Email: "reset@beispiel.de", CreatedAt: time.Now(), EmailVerifiedAt: jetztBestaetigt()}); err != nil {
		t.Fatal(err)
	}
	cfg := &config.Config{SessionSecret: "test-secret-32-chars-minimum-ok!"}
	h := MagicLinkRequestHandler(s, cfg)
	const adresse = "reset@beispiel.de"
	runde := func() string {
		codeAnfordern2961(t, h, adresse)
		richtig := otpCodeFor(t, adresse)
		falsch := "00000000"
		if falsch == richtig {
			falsch = "11111111"
		}
		for i := 0; i < 2; i++ {
			einloesen(s, cfg, adresse, falsch)
		}
		return richtig
	}
	// 4 Fehlversuche ueber zwei Codes, dann Erfolg.
	runde()
	otpStore.Delete(adresse)
	richtig := runde()
	if w := einloesen(s, cfg, adresse, richtig); w.Code != http.StatusOK {
		t.Fatalf("Erfolg nach 4 Fehlversuchen erwartet, bekommen %d: %s", w.Code, w.Body.String())
	}
	if n := magicFailGuard.count(adresse); n != 0 {
		t.Fatalf("nach Erfolg muss der Adresszaehler 0 sein, ist %d", n)
	}
	// Wieder 4 Fehlversuche, dann gelingt der richtige Code (ohne Reset waeren
	// es 8 und die Adresse gesperrt).
	runde()
	otpStore.Delete(adresse)
	richtig = runde()
	if w := einloesen(s, cfg, adresse, richtig); w.Code != http.StatusOK {
		t.Fatalf("nach Reset: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
}

// M67: Passwortwechsel — ein gelungener Wechsel setzt den Zaehler zurueck.
func TestPasswortwechsel_ErfolgSetztZaehlerZurueck(t *testing.T) {
	s := newTestStore(t)
	if err := s.SaveUser(pwKonto2961(t, "pwreset", "alt-passwort-1")); err != nil {
		t.Fatal(err)
	}
	h := ChangePasswordHandler(s, bcrypt.MinCost, bremsenSecret2961, "")
	wechsel := func(alt, neu string) int {
		body := `{"old_password":"` + alt + `","new_password":"` + neu + `"}`
		req := alsNutzer2961(httptest.NewRequest(http.MethodPut, "/api/auth/password", strings.NewReader(body)), "pwreset")
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		return w.Code
	}
	for i := 0; i < 4; i++ {
		wechsel("falsch", "egal-egal-1")
	}
	if c := wechsel("alt-passwort-1", "neu-passwort-2"); c != http.StatusOK {
		t.Fatalf("Wechsel nach 4 Fehlversuchen: erwartet 200, bekommen %d", c)
	}
	for i := 1; i <= 4; i++ {
		if c := wechsel("falsch", "egal-egal-1"); c != http.StatusForbidden {
			t.Fatalf("Fehlversuch %d nach Reset: erwartet 403, bekommen %d", i, c)
		}
	}
	if c := wechsel("neu-passwort-2", "neu-passwort-3"); c != http.StatusOK {
		t.Fatalf("nach Reset und 4 Fehlversuchen: erwartet 200, bekommen %d", c)
	}
}
