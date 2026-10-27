package handler

import (
	"net/http"
	"testing"
)

// Issue #2317 Fix-Loop 1 (AC-11) — Ursache des BROKEN-Staging-Verdicts.
//
// Reales Messergebnis (Staging, echter Browser bzw. `Accept-Encoding: gzip`):
// eine gzip-komprimierte Antwort traegt einen SCHWACHEN Validator
// (`ETag: W/"<fp>"`), weil die Kompressions-Schicht (nginx/Proxy) den vom
// Server erzeugten starken Fingerabdruck beim Komprimieren automatisch
// abschwaecht (RFC 7232 §2.1). Jeder echte Client (Browser wie SvelteKit-SSR-
// `fetch`) sendet `Accept-Encoding: gzip` und bekommt diesen schwachen
// Validator zurueck — und reicht ihn beim naechsten Schreibvorgang UNVERAEN-
// DERT als `If-Match` weiter, wie es der Standard verlangt.
//
// `ifMatchAllows` stript bisher nur umschliessende `"`-Zeichen, NICHT das
// vorangestellte `W/` — der Vergleich `W/"<fp>` (nach dem Trim, das "W" bleibt
// stehen, nur die schliessende Anfuehrung faellt weg) gegen den rohen
// Fingerabdruck `<fp>` schlaegt IMMER fehl. Ergebnis: jeder zweite
// Schreibvorgang in einer Sitzung, hinter jedem gzip-faehigen Proxy, wird mit
// einem FALSCHEN 412 abgelehnt — nicht nur im #2317-Nachlade-Pfad, sondern bei
// jeder gewoehnlichen Bearbeitung. Belegt per curl gegen Staging:
//   Accept-Encoding: identity -> ETag: "<fp>"
//   Accept-Encoding: gzip     -> ETag: W/"<fp>"
//
// Betroffen sind alle vier `ifMatchAllows`-Aufrufer (trip.go, weather_config.go,
// compare_preset.go, briefing_subscription.go) — ein Fix an der einen Stelle
// deckt Trip, Ortsvergleich-Preset UND Abo gleichermassen ab.

// Tabellen-Nachweis der eigentlichen Vergleichsfunktion: ein schwacher
// Validator muss wie sein starkes Gegenstueck behandelt werden, ein wirklich
// veralteter schwacher Validator muss weiterhin ablehnen (sonst wuerde der Fix
// zu "alles annehmen" entarten).
func TestIfMatchAllows_WeakValidatorPrefix(t *testing.T) {
	const current = "246d9dc5ce9732cff22031e7c3163379f24ff59eba5ebc8e5353b7b69d07c444"
	cases := []struct {
		name   string
		header string
		want   bool
	}{
		{"starker Validator, passend", `"` + current + `"`, true},
		{"schwacher Validator, passend (gzip-Fall)", `W/"` + current + `"`, true},
		{"ohne Anfuehrungszeichen, passend", current, true},
		{"schwacher Validator mit Leerzeichen vor Komma-Eintrag", `"deadbeef", W/"` + current + `"`, true},
		{"schwacher Validator, veraltet", `W/"0000000000000000000000000000000000000000000000000000000000000000"`, false},
		{"starker Validator, veraltet", `"0000000000000000000000000000000000000000000000000000000000000000"`, false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := ifMatchAllows(c.header, current)
			if got != c.want {
				t.Errorf("ifMatchAllows(%q, %q) = %v, want %v", c.header, current, got, c.want)
			}
		})
	}
}

// HTTP-Boundary-Nachweis (die Stelle, an der die Zusicherung WIRKT): ein PUT
// mit dem exakten, aber schwach-validierten ETag der letzten GET-Antwort darf
// nicht mit 412 abgelehnt werden. Simuliert den echten Ablauf ohne gzip
// nachzubilden (das Handler-Verhalten ist unabhaengig von der Kompression):
// der Client erhaelt einen `W/`-praefigierten Header exakt so, wie ihn ein
// gzip-Proxy ausliefert, und schickt ihn unveraendert zurueck.
func TestUpdateTripHandler_WeakIfMatch_MatchingFingerprint_Accepted(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "etag-weak-1", "Alt")
	r := etagRouter(s)

	et := mustETag(t, doReq(r, http.MethodGet, "/api/trips/etag-weak-1", "", "", ""))
	weak := "W/" + et // genau das, was ein gzip-Proxy aus einem starken ETag macht

	w := doReq(r, http.MethodPut, "/api/trips/etag-weak-1", `{"name":"Neu"}`, weak, "")
	if w.Code != http.StatusOK {
		t.Fatalf("PUT mit schwach-validiertem, aber inhaltlich passendem If-Match: expected 200, got %d: %s",
			w.Code, w.Body.String())
	}
}

// Gegenprobe: ein schwacher, aber tatsaechlich veralteter Validator muss
// weiterhin 412 ausloesen — der Fix darf keine Konflikterkennung wegnehmen.
func TestUpdateTripHandler_WeakIfMatch_StaleFingerprint_Returns412(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "etag-weak-2", "Alt")
	r := etagRouter(s)

	staleWeak := `W/"0000000000000000000000000000000000000000000000000000000000000000"`
	w := doReq(r, http.MethodPut, "/api/trips/etag-weak-2", `{"name":"Neu"}`, staleWeak, "")
	if w.Code != http.StatusPreconditionFailed {
		t.Fatalf("PUT mit veraltetem schwachem If-Match: expected 412, got %d: %s", w.Code, w.Body.String())
	}
}
