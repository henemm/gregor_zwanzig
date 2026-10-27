package handler_test

// TDD RED — Issue #2406: Mengenbremse fuer SMS-Bestaetigungscodes.
// Spec: docs/specs/modules/sms_nummer_verifikation.md — AC-5, AC-6 (§2, §7).
//
// Umgebung und Versand-Gegenstelle: sms_verification_test.go (smsUmgebung2406).
// Gemessen wird ueber den ECHTEN Router — damit ist die Verdrahtung der
// eigenstaendigen smsFloodLimiter-Instanz (router.go) mitgeprueft, nicht nur
// ein von Hand durchgereichter Limiter (Lehre aus #2404 F001).

import (
	"fmt"
	"net/http"
	"testing"
)

// AC-5: Profil-Speichern mit UNVERAENDERTEM sms_to (das Frontend schickt es bei
// jedem Speichern mit) versendet keinen Code und verbraucht kein Kontingent.
// Gegenprobe im selben Test: danach sind alle 3 Versuche fuer echte Wechsel
// noch frei — sonst waere „kein Versand" heute trivial gruen.
func TestSmsProfilSpeichernOhneNummernwechselVersendetKeinenCode(t *testing.T) {
	e := neueSmsUmgebung2406(t, false)
	const uid = "smsnurname"
	e.konto(t, uid, "standard", bestaetigtA2406())
	c := e.cookie(t, uid)

	for i := 1; i <= 5; i++ {
		w := e.profilPut(t, c, fmt.Sprintf(`{"display_name":"Name %d","sms_to":%q}`, i, nummerA2406))
		if w.Code != http.StatusOK {
			t.Fatalf("AC-5: Speichern %d (nur display_name) erwartet 200, bekommen %d: %s", i, w.Code, w.Body.String())
		}
	}
	e.erwarteKeinenVersand(t, "AC-5 fuenfmal nur display_name")

	// Echter Wechsel → Code an B.
	if w := e.profilPut(t, c, fmt.Sprintf(`{"display_name":"Name 6","sms_to":%q}`, nummerB2406)); w.Code != http.StatusOK {
		t.Fatalf("AC-5: echter Wechsel auf B erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	e.erwarteVersand(t, uid, nummerB2406, "AC-5 erster echter Wechsel")

	// Erneutes Absenden des bereits ausstehenden Werts ist ein No-op (§2).
	if w := e.profilPut(t, c, fmt.Sprintf(`{"display_name":"Name 7","sms_to":%q}`, nummerB2406)); w.Code != http.StatusOK {
		t.Fatalf("AC-5: erneutes Absenden von B erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	e.erwarteKeinenVersand(t, "AC-5 ausstehender Wert erneut gesendet")

	// Zweiter und dritter echter Wechsel — kein vorzeitiges 429.
	for i, n := range []string{nummerC2406, "+491514000004"} {
		w := e.profilPut(t, c, fmt.Sprintf(`{"sms_to":%q}`, n))
		if w.Code != http.StatusOK {
			t.Fatalf("AC-5: echter Wechsel %d auf %s erwartet 200 (Kontingent darf nicht verbraucht sein), bekommen %d: %s",
				i+2, n, w.Code, w.Body.String())
		}
		e.erwarteVersand(t, uid, n, fmt.Sprintf("AC-5 echter Wechsel %d", i+2))
	}
}

// AC-6: nach 3 Codes in der Stunde lehnt der Endpoint den vierten mit 429 und
// Retry-After: 1200 ab — ohne jeden Teilzustand, auch nicht fuer display_name.
func TestSmsCodeKontingentErschoepftBlocktOhneTeilzustand(t *testing.T) {
	e := neueSmsUmgebung2406(t, false)
	const uid = "smsflut"
	e.konto(t, uid, "standard", nil)
	c := e.cookie(t, uid)

	for i, n := range []string{"+491515000001", "+491515000002", "+491515000003"} {
		if w := e.profilPut(t, c, fmt.Sprintf(`{"sms_to":%q}`, n)); w.Code != http.StatusOK {
			t.Fatalf("AC-6: Wechsel %d erwartet 200, bekommen %d: %s", i+1, w.Code, w.Body.String())
		}
		e.erwarteVersand(t, uid, n, fmt.Sprintf("AC-6 Wechsel %d", i+1))
	}

	vorher := e.userBytes(t, uid)
	w := e.profilPut(t, c, `{"sms_to":"+491515000004","display_name":"Harmlos geaendert"}`)
	if w.Code != http.StatusTooManyRequests {
		t.Fatalf("AC-6: vierter Code in der Stunde erwartet 429, bekommen %d: %s", w.Code, w.Body.String())
	}
	if ra := w.Header().Get("Retry-After"); ra != "1200" {
		t.Errorf("AC-6: Retry-After erwartet \"1200\" (3/h), bekommen %q", ra)
	}
	if nachher := e.userBytes(t, uid); string(nachher) != string(vorher) {
		t.Errorf("AC-6: bei 429 darf NICHTS gespeichert werden (auch display_name nicht).\nvorher:  %s\nnachher: %s", vorher, nachher)
	}
	e.erwarteKeinenVersand(t, "AC-6 abgelehnter vierter Wechsel")
}

// AC-6 Zusatz: SMS- und Mail-Kontingent sind getrennt — in BEIDE Richtungen.
func TestSmsCodeKontingentIstGetrenntVomMailKontingent(t *testing.T) {
	t.Run("sms_erschoepft_mail_bleibt_frei", func(t *testing.T) {
		e := neueSmsUmgebung2406(t, false)
		const uid = "smsvollmail"
		e.konto(t, uid, "standard", nil)
		c := e.cookie(t, uid)

		for i, n := range []string{"+491516000001", "+491516000002", "+491516000003"} {
			if w := e.profilPut(t, c, fmt.Sprintf(`{"sms_to":%q}`, n)); w.Code != http.StatusOK {
				t.Fatalf("Wechsel %d erwartet 200, bekommen %d: %s", i+1, w.Code, w.Body.String())
			}
			e.erwarteVersand(t, uid, n, fmt.Sprintf("SMS-Wechsel %d", i+1))
		}
		if w := e.profilPut(t, c, `{"sms_to":"+491516000004"}`); w.Code != http.StatusTooManyRequests {
			t.Fatalf("AC-6: SMS-Kontingent muss nach 3 Codes erschoepft sein (429), bekommen %d: %s", w.Code, w.Body.String())
		}
		w := e.profilPut(t, c, `{"mail_to":"smsvollmail-neu@beispiel.de"}`)
		if w.Code != http.StatusOK {
			t.Errorf("AC-6: Mail-Kontingent darf durch SMS-Codes nicht verbraucht sein — Mail-Wechsel erwartet 200, bekommen %d: %s",
				w.Code, w.Body.String())
		}
	})

	t.Run("mail_erschoepft_sms_bleibt_frei", func(t *testing.T) {
		e := neueSmsUmgebung2406(t, false)
		const uid = "mailvollsms"
		e.konto(t, uid, "standard", nil)
		c := e.cookie(t, uid)

		// 10 Mail-Wechsel schoepfen den Nutzer-Bucket des Mail-Limiters (10/h) aus.
		for i := 1; i <= 10; i++ {
			if w := e.profilPut(t, c, fmt.Sprintf(`{"mail_to":"mailvollsms-%d@beispiel.de"}`, i)); w.Code != http.StatusOK {
				t.Fatalf("Mail-Wechsel %d erwartet 200, bekommen %d: %s", i, w.Code, w.Body.String())
			}
		}
		if w := e.profilPut(t, c, `{"mail_to":"mailvollsms-11@beispiel.de"}`); w.Code != http.StatusTooManyRequests {
			t.Fatalf("Messaufbau: Mail-Kontingent muss erschoepft sein (429), bekommen %d: %s", w.Code, w.Body.String())
		}
		w := e.profilPut(t, c, fmt.Sprintf(`{"sms_to":%q}`, nummerA2406))
		if w.Code != http.StatusOK {
			t.Fatalf("AC-6: SMS-Wechsel trotz erschoepftem Mail-Kontingent erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
		}
		e.erwarteVersand(t, uid, nummerA2406, "AC-6 SMS-Code trotz vollem Mail-Kontingent")
	})
}
