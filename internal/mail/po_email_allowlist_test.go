package mail

// TDD RED — Issue #2147 Scheibe B2, AC-16: die konfigurierte Betreiber-Adresse
// (GZ_PO_EMAIL / cfg.PoEmail, Empfaenger der Tier-Antraege) wird vom
// Resend-Guard NICHT blockiert — unabhaengig davon, welches Profil welche
// Felder traegt. Spec: docs/specs/modules/adresswechsel_nach_bestaetigung.md
// §5 (Entscheidung 8), AC-16.
//
// Vertrag fuer /50 (nur beobachtbares Verhalten, keine neue Signatur): der
// Guard kennt die Betreiber-Adresse ueber die Prozess-Umgebung GZ_PO_EMAIL —
// dieselbe Naht, ueber die er schon heute die Datenwurzel findet
// (resendAllowlistDataDir -> GZ_DATA_DIR) und aus der internal/config den
// Wert cfg.PoEmail laedt (envconfig-Praefix GZ). Der Handler-Pendant-Test
// (internal/handler/tier_change_po_email_allowlist_test.go) prueft denselben
// Vertrag ueber den echten Tier-Antrag-Pfad.
//
// Zwei-Nutzer-Pflicht: die Datenwurzel traegt zwei bestaetigte Konten, deren
// Adressen die PO-Adresse NICHT enthalten.

import "testing"

const poAllowlistResendHost = "smtp.resend-fixture.test"

func TestAC16_BetreiberAdresseOhneProfilWirdVomResendGuardNichtBlockiert(t *testing.T) {
	dataDir := t.TempDir()
	writeRawUserJSON(t, dataDir, "wanderer-a", map[string]any{
		"mail_to":           "wanderer-a-kontakt@gmail.com",
		"email_verified_at": "2026-01-01T00:00:00Z",
	})
	writeRawUserJSON(t, dataDir, "wanderer-b", map[string]any{
		"email":             "wanderer-b-login@gmail.com",
		"mail_to":           "wanderer-b-kontakt@gmail.com",
		"email_verified_at": "2026-01-01T00:00:00Z",
	})
	t.Setenv("GZ_DATA_DIR", dataDir)
	t.Setenv("GZ_PO_EMAIL", "betreiber-antraege@gmail.com")

	if err := recipientBlocked(poAllowlistResendHost, "betreiber-antraege@gmail.com"); err != nil {
		t.Errorf("AC-16: konfigurierte Betreiber-Adresse (GZ_PO_EMAIL), die in keinem Profil steht, "+
			"wurde vom Resend-Guard blockiert — Tier-Antraege waeren unzustellbar: %v", err)
	}
}

// AC-16 Gegenprobe: die Freigabe gilt NUR fuer die konfigurierte Adresse —
// eine andere profillose Adresse bleibt blockiert (faengt "Guard aus" bzw.
// "alles erlauben, sobald GZ_PO_EMAIL gesetzt ist"). Heute gruen.
func TestAC16_FreigabeGiltNurFuerDieKonfigurierteBetreiberAdresse(t *testing.T) {
	dataDir := t.TempDir()
	writeRawUserJSON(t, dataDir, "wanderer-a", map[string]any{
		"mail_to":           "wanderer-a-kontakt@gmail.com",
		"email_verified_at": "2026-01-01T00:00:00Z",
	})
	writeRawUserJSON(t, dataDir, "wanderer-b", map[string]any{
		"mail_to":           "wanderer-b-kontakt@gmail.com",
		"email_verified_at": "2026-01-01T00:00:00Z",
	})
	t.Setenv("GZ_DATA_DIR", dataDir)
	t.Setenv("GZ_PO_EMAIL", "betreiber-antraege@gmail.com")

	if err := recipientBlocked(poAllowlistResendHost, "fremd-ohne-profil@gmail.com"); err == nil {
		t.Errorf("AC-16 Gegenprobe: fremde profillose Adresse wurde durchgelassen, obwohl nur die Betreiber-Adresse freigegeben ist")
	}
	// Mehrempfaenger: Betreiber-Adresse + Fremdadresse im selben to — die
	// Fremdadresse darf nicht huckepack mit durchrutschen.
	if err := recipientBlocked(poAllowlistResendHost, "betreiber-antraege@gmail.com, fremd-ohne-profil@gmail.com"); err == nil {
		t.Errorf("AC-16 Gegenprobe: Fremdadresse rutschte zusammen mit der Betreiber-Adresse durch")
	}
}
