package handler

// Issue #2961 Nachbesserung (Gegenpruefung F1/F3) — Testkonto-Schalter:
// keine privilegierten Kennungen ohne Admin-Sitzung, gefaelschte/widerrufene
// Admin-Sitzungen oeffnen nichts.

import (
	"net/http"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
)

// AC-10 (Nachbesserung): im Staging/Fixture-Modus belegt eine Registrierung
// ohne Admin-Sitzung keine privilegierte Kennung (Admin- oder Ausnahmeliste,
// ohne Gross-/Kleinschreibung); reservierte Kennungen ebenso nicht. Mit
// Admin-Sitzung ist eine privilegierte Kennung erlaubt.
func TestTestkontoSchalter_PrivilegierteKennungNurMitAdminSitzung(t *testing.T) {
	s := newTestStore(t)
	for _, cfg := range []config.Config{
		{SessionSecret: schalterSecret2961, Env: "staging", AdminUserIDs: "chef,Boss", QuotaExemptUserIDs: "Validator"},
		{SessionSecret: schalterSecret2961, TestFixtureDir: t.TempDir(), AdminUserIDs: "chef,Boss", QuotaExemptUserIDs: "Validator"},
	} {
		for _, id := range []string{"boss", "BOSS", "validator", "VALIDATOR", "Default", "ROOT"} {
			w := registriere2961(t, s, cfg, testkontoRumpf2961(id), nil)
			if w.Code != http.StatusBadRequest || antwortCode2961(w) != "validation_failed" {
				t.Fatalf("%q (Env=%q): erwartet 400 validation_failed, bekommen %d: %s", id, cfg.Env, w.Code, w.Body.String())
			}
			if s.UserExists(id) {
				t.Fatalf("%q: es darf kein Kontoordner entstehen", id)
			}
		}
	}
	cfg := config.Config{SessionSecret: schalterSecret2961, Env: "staging", AdminUserIDs: "chef,Boss", QuotaExemptUserIDs: "Validator"}
	c := sitzungFuer2961(t, s, "chef")
	if w := registriere2961(t, s, cfg, testkontoRumpf2961("validator"), c); w.Code != http.StatusCreated {
		t.Fatalf("Admin-Sitzung: privilegierte Kennung erwartet 201, bekommen %d: %s", w.Code, w.Body.String())
	}
	// Gegenprobe: gewoehnliche Kennung im Staging ohne Sitzung bleibt erlaubt.
	if w := registriere2961(t, s, cfg, testkontoRumpf2961("normaltest"), nil); w.Code != http.StatusCreated {
		t.Fatalf("gewoehnliche Testkennung im Staging: erwartet 201, bekommen %d: %s", w.Code, w.Body.String())
	}
}

// F3: ein Admin-Cookie mit falscher Signatur bzw. ein widerrufener
// Admin-Cookie oeffnet den Schalter in Produktion nicht.
func TestTestkontoSchalter_GefaelschteOderWiderrufeneAdminSitzung(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{SessionSecret: schalterSecret2961, AdminUserIDs: "chef"}
	c := sitzungFuer2961(t, s, "chef")

	letztes := c.Value[len(c.Value)-1]
	ersatz := byte('0')
	if letztes == '0' {
		ersatz = '1'
	}
	gefaelscht := &http.Cookie{Name: "gz_session", Value: c.Value[:len(c.Value)-1] + string(ersatz)}
	if w := registriere2961(t, s, cfg, testkontoRumpf2961("faelschung"), gefaelscht); w.Code != http.StatusBadRequest {
		t.Fatalf("falsche Signatur: erwartet 400, bekommen %d: %s", w.Code, w.Body.String())
	}
	fremdSecret := &http.Cookie{Name: "gz_session", Value: middleware.SignSessionWithID("chef", "x", "anderes-secret-32-zeichen-lang!!")}
	if w := registriere2961(t, s, cfg, testkontoRumpf2961("faelschung"), fremdSecret); w.Code != http.StatusBadRequest {
		t.Fatalf("fremdes Secret: erwartet 400, bekommen %d: %s", w.Code, w.Body.String())
	}
	// Positivkontrolle, dann Widerruf.
	if w := registriere2961(t, s, cfg, testkontoRumpf2961("vorwiderruf"), c); w.Code != http.StatusCreated {
		t.Fatalf("gueltige Admin-Sitzung: erwartet 201, bekommen %d: %s", w.Code, w.Body.String())
	}
	if err := s.ClearSessions("chef"); err != nil {
		t.Fatal(err)
	}
	if w := registriere2961(t, s, cfg, testkontoRumpf2961("nachwiderruf"), c); w.Code != http.StatusBadRequest {
		t.Fatalf("widerrufene Sitzung: erwartet 400, bekommen %d: %s", w.Code, w.Body.String())
	}
}
