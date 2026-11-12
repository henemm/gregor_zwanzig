package handler_test

// Issue #2961 (GA7) — SMS-Bestaetigungscode: Pruefzyklus unter Sperre je
// Nutzer, Zaehler vor dem Vergleich, Mengenbremse je Nutzer.
// Spec: docs/specs/modules/security_haertung_2026_11_go_anmeldung.md (AC-19, AC-20).
//
// Echter Router (smsUmgebung2406), echter Store, echte Code-Datei.

import (
	"fmt"
	"net/http"
	"sync"
	"testing"
)

// AC-19: viele gleichzeitige falsche Codes fuehren zu hoechstens fuenf
// Vergleichen; danach ist auch der richtige Code verbrannt.
func TestSmsVerify_GleichzeitigeFehlversucheHoechstensFuenfVergleiche(t *testing.T) {
	e := neueSmsUmgebung2406(t, false)
	const uid = "smsparallel"
	e.konto(t, uid, "standard", nil)
	c := e.cookie(t, uid)
	if w := e.profilPut(t, c, fmt.Sprintf(`{"sms_to":%q}`, nummerA2406)); w.Code != http.StatusOK {
		t.Fatalf("PUT erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	v := e.erwarteVersand(t, uid, nummerA2406, "Erst-Eintrag")
	falsch := andererCode2406(v.Code)

	const n = 10
	ergebnisse := make([]string, n)
	var wg sync.WaitGroup
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			ergebnisse[i] = fehlerCode2406(e.verify(t, c, falsch))
		}(i)
	}
	wg.Wait()
	verglichen := 0
	for _, r := range ergebnisse {
		if r == "invalid_code" {
			verglichen++
		}
	}
	if verglichen > 5 {
		t.Fatalf("hoechstens 5 Vergleiche erwartet, %d Antworten invalid_code (%v)", verglichen, ergebnisse)
	}
	if w := e.verify(t, c, v.Code); w.Code == http.StatusOK {
		t.Fatalf("nach fuenf Fehlversuchen darf auch der richtige Code nicht mehr gelten")
	}
}

// AC-20: die Route hat eine Mengenbremse je Nutzer (10 je 10 Minuten); ein
// anderer Nutzer ist davon unberuehrt.
func TestSmsVerify_MengenbremseJeNutzer(t *testing.T) {
	e := neueSmsUmgebung2406(t, false)
	e.konto(t, "smsbremse", "standard", nil)
	e.konto(t, "smsandere", "standard", nil)
	c := e.cookie(t, "smsbremse")
	for i := 1; i <= 10; i++ {
		if w := e.verify(t, c, "123456"); w.Code == http.StatusTooManyRequests {
			t.Fatalf("Versuch %d: zu frueh 429", i)
		}
	}
	w := e.verify(t, c, "123456")
	if w.Code != http.StatusTooManyRequests || fehlerCode2406(w) != "rate_limit_exceeded" {
		t.Fatalf("11. Versuch: erwartet 429 rate_limit_exceeded, bekommen %d: %s", w.Code, w.Body.String())
	}
	if w.Header().Get("Retry-After") == "" {
		t.Errorf("429 ohne Retry-After")
	}
	if w := e.verify(t, e.cookie(t, "smsandere"), "123456"); w.Code == http.StatusTooManyRequests {
		t.Fatalf("anderer Nutzer darf nicht mitgebremst werden")
	}
}
