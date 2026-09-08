package config

import (
	"os"
	"strings"
	"testing"
)

// TDD RED — Issue #2130: Passkey-RP-Konfiguration wird aus PublicHost abgeleitet.
// Spec: docs/specs/modules/passkey_rp_konfiguration.md (AC-1, AC-5)
//
// Diese Tests kompilieren NICHT gegen den aktuellen Stand: die Funktion
// config.NewWebAuthn(*Config) existiert noch nicht. RED-Zustand: Kompilierfehler
// ("undefined: NewWebAuthn"). Vorbild dieser Form: internal/handler/health_commit_test.go.
//
// Warum diese Naht und nicht der Bestand: die 31 bestehenden Passkey-Tests bauen
// sich ihre webauthn-Instanz per newTestWebAuthn(t, rpID, origin) selbst und
// konnten den Prod-Defekt (rpId "localhost") deshalb drei Monate nicht sehen.
// Geprüft wird hier die reale Kette Load() -> NewWebAuthn().

// withDerivedEnv leert die Prozess-Umgebung, setzt die übergebenen Variablen und
// stellt den Ausgangszustand nach dem Test vollständig wieder her (die übrigen
// Tests dieses Pakets laufen im selben Prozess).
func withDerivedEnv(t *testing.T, vars map[string]string) {
	t.Helper()
	saved := os.Environ()
	t.Cleanup(func() {
		os.Clearenv()
		for _, kv := range saved {
			if i := strings.IndexByte(kv, '='); i > 0 {
				os.Setenv(kv[:i], kv[i+1:])
			}
		}
	})
	os.Clearenv()
	for k, v := range vars {
		os.Setenv(k, v)
	}
}

// AC-1: Ohne explizite WebAuthn-Variablen wird die RP-ID aus PublicHost abgeleitet.
func TestNewWebAuthnAbleitungRPIDAusPublicHost(t *testing.T) {
	// GIVEN: nur GZ_PUBLIC_HOST gesetzt, keine GZ_WEBAUTHN_RP_ID/_RP_ORIGINS
	withDerivedEnv(t, map[string]string{
		"GZ_PUBLIC_HOST": "https://gregor20.henemm.com",
	})

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: unerwarteter Fehler: %v", err)
	}

	// WHEN: die WebAuthn-Instanz aus der Konfiguration gebaut wird
	wa, err := NewWebAuthn(cfg)
	if err != nil {
		t.Fatalf("AC-1: NewWebAuthn darf hier nicht scheitern: %v", err)
	}

	// THEN: RP-ID ist der Hostanteil von PublicHost — nicht "localhost"
	if wa.Config.RPID != "gregor20.henemm.com" {
		t.Errorf("AC-1: erwartet RPID %q, bekommen %q", "gregor20.henemm.com", wa.Config.RPID)
	}

	// THEN: RP-Origin ist Schema+Host von PublicHost
	if !containsOrigin(wa.Config.RPOrigins, "https://gregor20.henemm.com") {
		t.Errorf("AC-1: erwartet Origin %q in %v", "https://gregor20.henemm.com", wa.Config.RPOrigins)
	}
	if containsOrigin(wa.Config.RPOrigins, "http://localhost:5173") {
		t.Errorf("AC-1: alter localhost-Default darf nicht mehr als Origin erscheinen: %v", wa.Config.RPOrigins)
	}
}

// AC-1 (Abgrenzung): Ein anderer PublicHost ergibt eine andere RP-ID — die
// Ableitung liest wirklich den Wert und liefert kein festes Literal.
func TestNewWebAuthnAbleitungFolgtDemPublicHostWert(t *testing.T) {
	withDerivedEnv(t, map[string]string{
		"GZ_PUBLIC_HOST": "https://staging.gregor20.henemm.com",
	})

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: unerwarteter Fehler: %v", err)
	}
	wa, err := NewWebAuthn(cfg)
	if err != nil {
		t.Fatalf("NewWebAuthn: unerwarteter Fehler: %v", err)
	}

	if wa.Config.RPID != "staging.gregor20.henemm.com" {
		t.Errorf("AC-1: erwartet RPID %q, bekommen %q", "staging.gregor20.henemm.com", wa.Config.RPID)
	}
	if !containsOrigin(wa.Config.RPOrigins, "https://staging.gregor20.henemm.com") {
		t.Errorf("AC-1: erwartet Origin %q in %v", "https://staging.gregor20.henemm.com", wa.Config.RPOrigins)
	}
}

// AC-1 (Override): Eine explizit gesetzte GZ_WEBAUTHN_RP_ID schlägt die Ableitung.
func TestNewWebAuthnExpliziteRPIDSchlaegtAbleitung(t *testing.T) {
	withDerivedEnv(t, map[string]string{
		"GZ_PUBLIC_HOST":         "https://gregor20.henemm.com",
		"GZ_WEBAUTHN_RP_ID":      "eigene.example",
		"GZ_WEBAUTHN_RP_ORIGINS": "https://eigene.example",
	})

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: unerwarteter Fehler: %v", err)
	}
	wa, err := NewWebAuthn(cfg)
	if err != nil {
		t.Fatalf("NewWebAuthn: unerwarteter Fehler: %v", err)
	}

	if wa.Config.RPID != "eigene.example" {
		t.Errorf("Override: erwartet RPID %q, bekommen %q — die Ableitung hat den expliziten Wert überschrieben",
			"eigene.example", wa.Config.RPID)
	}
	if !containsOrigin(wa.Config.RPOrigins, "https://eigene.example") {
		t.Errorf("Override: erwartet Origin %q in %v", "https://eigene.example", wa.Config.RPOrigins)
	}
}

// AC-1 (Override, nur Origins): Explizite Origins bleiben erhalten, auch wenn die
// RP-ID abgeleitet wird (lokale Entwicklung mit abweichendem Preview-Port).
func TestNewWebAuthnExpliziteOriginsBleibenErhalten(t *testing.T) {
	withDerivedEnv(t, map[string]string{
		"GZ_PUBLIC_HOST":         "http://localhost:4173",
		"GZ_WEBAUTHN_RP_ORIGINS": "http://localhost:4173,http://localhost:5173",
	})

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: unerwarteter Fehler: %v", err)
	}
	wa, err := NewWebAuthn(cfg)
	if err != nil {
		t.Fatalf("NewWebAuthn: unerwarteter Fehler: %v", err)
	}

	if wa.Config.RPID != "localhost" {
		t.Errorf("erwartet abgeleitete RPID %q (Host ohne Port), bekommen %q", "localhost", wa.Config.RPID)
	}
	for _, want := range []string{"http://localhost:4173", "http://localhost:5173"} {
		if !containsOrigin(wa.Config.RPOrigins, want) {
			t.Errorf("expliziter Origin %q fehlt in %v", want, wa.Config.RPOrigins)
		}
	}
}

// AC-5: Unbrauchbare PublicHost-Werte dürfen die Anwendung nicht am Start hindern.
// Die Ableitung liefert nie eine leere RP-ID, und webauthn.New() (in NewWebAuthn
// gekapselt) wirft keinen Fehler — damit kann die bestehende Startprüfung in
// cmd/server/main.go:103 nicht auslösen.
func TestNewWebAuthnKaputterPublicHostStartetTrotzdem(t *testing.T) {
	cases := []struct {
		name       string
		publicHost string
	}{
		{"leer", ""},
		{"ohne Schema", "gregor20.henemm.com"},
		{"kaputtes Schema", "://kaputt"},
		{"Leerzeichen im Schema", "ht tp://x"},
		{"nur Schema", "https://"},
		{"kein URL sondern Satz", "bitte hier die adresse eintragen"},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			withDerivedEnv(t, map[string]string{"GZ_PUBLIC_HOST": tc.publicHost})

			cfg, err := Load()
			if err != nil {
				t.Fatalf("AC-5: Load darf bei kaputtem PublicHost nicht scheitern: %v", err)
			}

			wa, err := NewWebAuthn(cfg)
			if err != nil {
				t.Fatalf("AC-5: NewWebAuthn muss für PublicHost %q ohne Fehler bauen, bekommen: %v",
					tc.publicHost, err)
			}
			if wa == nil {
				t.Fatalf("AC-5: NewWebAuthn lieferte nil-Instanz für PublicHost %q", tc.publicHost)
			}
			if strings.TrimSpace(wa.Config.RPID) == "" {
				t.Errorf("AC-5: leere RP-ID für PublicHost %q — es muss ein Ersatzwert stehen", tc.publicHost)
			}
			if len(wa.Config.RPOrigins) == 0 {
				t.Errorf("AC-5: keine RP-Origins für PublicHost %q", tc.publicHost)
			}
			for _, o := range wa.Config.RPOrigins {
				if strings.TrimSpace(o) == "" {
					t.Errorf("AC-5: leerer Origin-Eintrag für PublicHost %q: %v", tc.publicHost, wa.Config.RPOrigins)
				}
			}
		})
	}
}

func containsOrigin(origins []string, want string) bool {
	for _, o := range origins {
		if strings.TrimSpace(o) == want {
			return true
		}
	}
	return false
}
