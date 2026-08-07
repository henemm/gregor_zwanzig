package mail

import (
	"strings"
	"testing"
)

// TDD RED: Issue #1555 AC-9 — die Freigabe-Mail muss BEIDE noetigen Schritte
// nennen. Der bisherige Text nennt nur "das tier-Feld ... setzen"; genau
// deshalb blieb requested_tier in der Praxis stehen und ein laengst erledigter
// Antrag zaehlte weiter als offen.
//
// KEINE Mocks: echter Aufruf von BuildTierChangeRequestMail, echte Bodies.
func TestTierChangeRequestMailNennsBeideFreigabeSchritte(t *testing.T) {
	m := BuildTierChangeRequestMail("gz1555-nutzer", "free", "premium")

	teile := []struct {
		name string
		body string
	}{
		{"PlainBody", m.PlainBody},
		{"HTMLBody", m.HTMLBody},
	}

	for _, teil := range teile {
		if teil.body == "" {
			t.Fatalf("%s ist leer", teil.name)
		}
		lower := strings.ToLower(teil.body)

		// Schritt 1: tier setzen (im Bestand bereits vorhanden).
		if !strings.Contains(lower, "tier") || !strings.Contains(lower, "setzen") {
			t.Errorf("%s: Schritt 1 fehlt — Text muss das Setzen des tier-Feldes nennen. Text: %q",
				teil.name, teil.body)
		}

		// Schritt 2: requested_tier entfernen (neu, AC-9).
		if !strings.Contains(lower, "requested_tier") {
			t.Errorf("%s: Schritt 2 fehlt — Text nennt das Feld requested_tier nicht. Text: %q",
				teil.name, teil.body)
		}
		if !strings.Contains(lower, "entfern") && !strings.Contains(lower, "loesch") &&
			!strings.Contains(lower, "lösch") {
			t.Errorf("%s: Schritt 2 unvollstaendig — Text macht das Entfernen/Loeschen nicht explizit. Text: %q",
				teil.name, teil.body)
		}
	}
}
