package handler

// Zusicherung: eine codelose Nachricht verbraucht KEIN Budget der Ratebremse.
// Issue #2154 Scheibe A, Adversary-Befund F002 (premium_sms_connect.go:161).
//
// Warum das eine eigene Zusicherung ist und nicht bloss eine Eigenheit der
// Reihenfolge: die Bremse ist global und von allen Premium-Nutzern GETEILT
// (premium_sms_ratelimit.go), und codelose Garmin-Nachrichten sind vor der
// ersten Verknuepfung der Normalfall. Fiele der Fruehausstieg weg, liefe jede
// gewoehnliche Nachricht in den bcrypt-Vergleich, faende nichts und verbuchte
// einen Fehlversuch — ein Schwall normalen Verkehrs sperrte dann ALLE
// Premium-Nutzer gemeinsam aus. Selbst-DoS auf den eigenen Schutzmechanismus.
//
// Gemessen wird an beiden Stellen, an denen die Zusicherung wirkt: am Zaehler
// (bleibt 0) und an der Folge (der legitime Code kommt danach noch durch). Die
// Reihenfolge im Rumpf ist Teil der Messung — der erfolgreiche Aufruf steht
// ZULETZT. Andersherum setzte er PremiumSmsReplyTo, und die folgenden codelosen
// Nachrichten entschieden bereits in Schritt 4 (frischer gespeicherter Treffer,
// premium_sms_connect.go:154); die Bremse wuerde nie gefragt und der Test waere
// auch verfaelscht still gruen.

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func TestLearnWithoutCodeNeverConsumesRateLimitBudget(t *testing.T) {
	// Kleines Budget, damit die codelosen Nachrichten es unter der Mutation
	// sicher ueberschreiten — mit dem Produktionsbudget kostete das je Versuch
	// bcrypt-Rechenzeit.
	const budget = 2

	s := learnTestStore(t)
	mustSaveUser(t, s, model.User{ID: "premium-anna", Tier: "premium"})
	mustSaveUser(t, s, model.User{ID: "premium-bert", Tier: "premium"})
	mustSaveLinkCode(t, s, "premium-anna", linkCodeAnna)

	rl := NewPremiumSmsRateLimiter(budget)
	h := PostPremiumSmsLearnHandler(s, rl)

	// Mehr codelose Nachrichten, als das Budget hergibt.
	for i := 1; i <= budget+1; i++ {
		rr := httptest.NewRecorder()
		h(rr, newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromA}))
		if rr.Code == http.StatusOK {
			t.Fatalf("F002: eine codelose Nachricht darf nie verknuepfen (Versuch %d), bekam 200, body=%s",
				i, rr.Body.String())
		}
		// Nicht abbrechend: so bleibt bei einer Regression auch die
		// Wirkungs-Haelfte unten sichtbar, statt hinter dem ersten Abbruch zu
		// verschwinden.
		if got := rl.FailedAttempts(); got != 0 {
			t.Errorf("F002: die codelose Nachricht %d hat Budget der GETEILTEN Ratebremse verbraucht — "+
				"erwartet FailedAttempts()=0, bekam %d (Antwort %d, body=%s)",
				i, got, rr.Code, rr.Body.String())
		}
	}

	// Wirkungs-Haelfte: der legitime Verknuepfungsversuch muss danach noch
	// moeglich sein. Ohne sie belegte der Test nur einen Zaehlerstand, nicht
	// die Aussperrung, um die es geht.
	rr := httptest.NewRecorder()
	h(rr, newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromCoded, "code": linkCodeAnna}))
	if rr.Code != http.StatusOK {
		t.Fatalf("F002: nach %d codelosen Nachrichten muss der gueltige Code weiterhin verknuepfen — "+
			"bekam %d, body=%s (gewoehnlicher Verkehr hat die geteilte Bremse erschoepft)",
			budget+1, rr.Code, rr.Body.String())
	}
	if got := mustLoadUser(t, s, "premium-anna").PremiumSmsReplyTo; got != garminFromCoded {
		t.Errorf("F002: erwartet Rueckadresse %q nach dem gueltigen Code, bekam %q", garminFromCoded, got)
	}
}
