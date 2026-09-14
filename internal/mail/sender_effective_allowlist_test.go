package mail

// TDD RED — Issue #2147 Scheibe B2: Resend-Allowlist enthaelt nur noch die
// BESTAETIGTE WIRKSAME Kontaktadresse (mail_to, ersatzweise email) je Konto.
// Spec: docs/specs/modules/adresswechsel_nach_bestaetigung.md §5, AC-5, AC-15.
//
// Gemessen wird die beobachtbare Guard-Entscheidung recipientBlocked()
// (block/allow) gegen einen Resend-Host — nicht die interne Datenstruktur
// allein. Fixtures ausschliesslich in t.TempDir(), Datenwurzel ueber
// GZ_DATA_DIR (dieselbe Naht wie recipient_parity_test.go). Profile werden
// als ROHES JSON geschrieben: die Pending-Felder (pending_contact_address/
// pending_contact_field) existieren als Go-Struct-Felder noch nicht, ihr
// JSON-Vertrag ist aber Teil dieser Scheibe.
//
// Zwei-Nutzer-Pflicht (CLAUDE.md): jeder Test legt mindestens zwei Konten an.

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

const effectiveAllowlistResendHost = "smtp.resend-fixture.test"

func writeRawUserJSON(t *testing.T, dataDir, userID string, profile map[string]any) {
	t.Helper()
	userDir := filepath.Join(dataDir, "users", userID)
	if err := os.MkdirAll(userDir, 0755); err != nil {
		t.Fatalf("writeRawUserJSON: %v", err)
	}
	data, err := json.Marshal(profile)
	if err != nil {
		t.Fatalf("writeRawUserJSON: %v", err)
	}
	if err := os.WriteFile(filepath.Join(userDir, "user.json"), data, 0644); err != nil {
		t.Fatalf("writeRawUserJSON: %v", err)
	}
}

// AC-15 (Go): Given ein bestaetigtes Konto A mit email=Login-Adresse und
// davon abweichendem mail_to, plus ein zweites bestaetigtes Konto B / When
// der Resend-Guard die Login-Adresse von A prueft / Then wird sie blockiert —
// nur die wirksame Kontaktadresse (mail_to) von A ist erlaubt.
//
// Heute ROT: loadResendAllowlist nimmt MailTo UND Email auf (sender.go:227).
func TestAC15_AdresseNurImEmailFeldBeiAbweichendemMailToWirdBlockiert(t *testing.T) {
	dataDir := t.TempDir()
	writeRawUserJSON(t, dataDir, "wanderer-a", map[string]any{
		"email":             "wanderer-a-login@gmail.com",
		"mail_to":           "wanderer-a-kontakt@gmail.com",
		"email_verified_at": "2026-01-01T00:00:00Z",
	})
	writeRawUserJSON(t, dataDir, "wanderer-b", map[string]any{
		"mail_to":           "wanderer-b-kontakt@gmail.com",
		"email_verified_at": "2026-01-01T00:00:00Z",
	})
	t.Setenv("GZ_DATA_DIR", dataDir)

	if err := recipientBlocked(effectiveAllowlistResendHost, "wanderer-a-login@gmail.com"); err == nil {
		t.Errorf("AC-15: Adresse nur im email-Feld von wanderer-a (mail_to abweichend) wurde NICHT blockiert — " +
			"nur die bestaetigte wirksame Kontaktadresse darf ueber Resend erreichbar sein")
	}
	if allow := loadResendAllowlist(dataDir); allow["wanderer-a-login@gmail.com"] {
		t.Errorf("AC-15: Allowlist enthaelt die nicht wirksame Login-Adresse von wanderer-a: %v", allow)
	}

	// Gegenprobe: die wirksamen Adressen beider Konten bleiben erreichbar
	// (faengt eine Ueberkorrektur "alles blockieren").
	for _, addr := range []string{"wanderer-a-kontakt@gmail.com", "wanderer-b-kontakt@gmail.com"} {
		if err := recipientBlocked(effectiveAllowlistResendHost, addr); err != nil {
			t.Errorf("AC-15 Gegenprobe: wirksame bestaetigte Adresse %q wurde blockiert: %v", addr, err)
		}
	}
}

// AC-15 Gegenprobe "ersatzweise email": Given ein bestaetigtes Konto OHNE
// mail_to (nur email) neben einem zweiten Konto / When der Guard die
// email-Adresse prueft / Then ist sie erlaubt — sie IST die wirksame Adresse.
// Faengt die Fehlumsetzung "nur noch mail_to aufnehmen". Heute gruen
// (Regressionswaechter).
func TestAC15_EmailOhneMailToBleibtAlsWirksameAdresseErlaubt(t *testing.T) {
	dataDir := t.TempDir()
	writeRawUserJSON(t, dataDir, "wanderer-c", map[string]any{
		"email":             "wanderer-c-login@gmail.com",
		"email_verified_at": "2026-01-01T00:00:00Z",
	})
	writeRawUserJSON(t, dataDir, "wanderer-d", map[string]any{
		"email":             "wanderer-d-login@gmail.com",
		"mail_to":           "wanderer-d-kontakt@gmail.com",
		"email_verified_at": "2026-01-01T00:00:00Z",
	})
	t.Setenv("GZ_DATA_DIR", dataDir)

	if err := recipientBlocked(effectiveAllowlistResendHost, "wanderer-c-login@gmail.com"); err != nil {
		t.Errorf("AC-15 (ersatzweise email): email ohne mail_to ist die wirksame Adresse und muss erlaubt sein: %v", err)
	}
}

// AC-5 (Go-Allowlist-Haelfte) — REGRESSIONSWAECHTER, heute bereits gruen:
// Given ein bestaetigtes Konto mit mail_to=ALT und einer ausstehenden
// Aenderung auf NEU (pending_contact_address/pending_contact_field roh im
// user.json), plus ein zweites Konto / When der Guard NEU und ALT prueft /
// Then ist NEU blockiert und ALT erlaubt. Faengt jede kuenftige Umsetzung,
// die die Pending-Adresse in die Allowlist uebernimmt.
func TestAC5_AusstehendeAdresseNichtInAllowlistAlteBleibtErlaubt(t *testing.T) {
	dataDir := t.TempDir()
	writeRawUserJSON(t, dataDir, "wanderer-alt", map[string]any{
		"email":                   "wanderer-alt@gmail.com",
		"mail_to":                 "wanderer-alt@gmail.com",
		"email_verified_at":       "2026-01-01T00:00:00Z",
		"pending_contact_address": "wanderer-neu@gmail.com",
		"pending_contact_field":   "mail_to",
	})
	writeRawUserJSON(t, dataDir, "wanderer-zweit", map[string]any{
		"mail_to":           "wanderer-zweit@gmail.com",
		"email_verified_at": "2026-01-01T00:00:00Z",
	})
	t.Setenv("GZ_DATA_DIR", dataDir)

	if err := recipientBlocked(effectiveAllowlistResendHost, "wanderer-neu@gmail.com"); err == nil {
		t.Errorf("AC-5: ausstehende, unbestaetigte Adresse wurde vom Resend-Guard durchgelassen")
	}
	allow := loadResendAllowlist(dataDir)
	if allow["wanderer-neu@gmail.com"] {
		t.Errorf("AC-5: Allowlist enthaelt die ausstehende Adresse: %v", allow)
	}
	if err := recipientBlocked(effectiveAllowlistResendHost, "wanderer-alt@gmail.com"); err != nil {
		t.Errorf("AC-5: alte, bestaetigte Adresse muss waehrend der ausstehenden Aenderung erreichbar bleiben: %v", err)
	}
}
