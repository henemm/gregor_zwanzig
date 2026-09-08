package config

import (
	"log"
	"net/url"
	"strings"

	"github.com/go-webauthn/webauthn/protocol"
	"github.com/go-webauthn/webauthn/webauthn"
)

// Issue #2130 — Passkey-RP-Konfiguration aus PublicHost ableiten.
//
// Produktion sendete dem Browser drei Monate lang rpId "localhost", weil
// GZ_WEBAUTHN_RP_ID nirgends gesetzt war und der Default hier auf "localhost"
// steht. RP-ID und Origins werden deshalb aus der ohnehin gepflegten
// PublicHost-Konfiguration abgeleitet; die expliziten Variablen bleiben als
// Override fuer die lokale Entwicklung erhalten.

// Bisherige Defaults aus dem Config-Struct. Traegt ein Feld noch seinen
// Default, gilt es als "nicht gesetzt" und wird abgeleitet.
const (
	defaultWebAuthnRPID     = "localhost"
	defaultWebAuthnRPOrigin = "http://localhost:5173"
)

// NewWebAuthn baut die WebAuthn-Instanz so, wie der laufende Server sie
// braucht: RP-ID und Origins aus PublicHost abgeleitet, ResidentKey global auf
// "preferred". Ist PublicHost unbrauchbar, greift der konfigurierte Ersatzwert
// und der Fehlgriff wird sichtbar protokolliert — eine falsch eingetragene
// oeffentliche Adresse darf den Dienst nie am Start hindern (AC-5).
func NewWebAuthn(cfg *Config) (*webauthn.WebAuthn, error) {
	rpID, origins := resolveWebAuthnRP(cfg)

	return webauthn.New(&webauthn.Config{
		RPID:          rpID,
		RPDisplayName: cfg.WebAuthnRPDisplayName,
		RPOrigins:     origins,
		AuthenticatorSelection: protocol.AuthenticatorSelection{
			ResidentKey: protocol.ResidentKeyRequirementPreferred,
		},
	})
}

// resolveWebAuthnRP liefert die effektive RP-ID und die effektiven Origins.
func resolveWebAuthnRP(cfg *Config) (string, []string) {
	derivedID, derivedOrigin, ok := deriveFromPublicHost(cfg.PublicHost)
	if !ok {
		log.Printf("[webauthn] GZ_PUBLIC_HOST %q ist unbrauchbar — Passkey-RP-ID/Origins "+
			"koennen daraus nicht abgeleitet werden, es gelten die konfigurierten "+
			"Ersatzwerte. Passkey-Anmeldung funktioniert erst, wenn GZ_PUBLIC_HOST "+
			"die oeffentliche Adresse traegt.", cfg.PublicHost)
	}

	rpID := strings.TrimSpace(cfg.WebAuthnRPID)
	if ok && (rpID == "" || rpID == defaultWebAuthnRPID) {
		rpID = derivedID
	}
	if rpID == "" {
		rpID = defaultWebAuthnRPID
	}

	configured := splitOrigins(cfg.WebAuthnRPOrigins)
	origins := configured
	explicit := len(configured) > 0 &&
		!(len(configured) == 1 && configured[0] == defaultWebAuthnRPOrigin)
	if ok && !explicit {
		origins = []string{derivedOrigin}
	}
	if len(origins) == 0 {
		origins = []string{defaultWebAuthnRPOrigin}
	}

	return rpID, origins
}

// deriveFromPublicHost zerlegt PublicHost in RP-ID (Hostanteil ohne Port) und
// RP-Origin (Schema + Host inklusive Port — go-webauthn prueft Origins exakt
// mit Port). ok ist false, wenn sich daraus nichts Brauchbares ergibt.
func deriveFromPublicHost(publicHost string) (string, string, bool) {
	raw := strings.TrimSpace(publicHost)
	if raw == "" {
		return "", "", false
	}
	u, err := url.Parse(raw)
	if err != nil {
		return "", "", false
	}
	scheme := strings.ToLower(u.Scheme)
	if scheme != "http" && scheme != "https" {
		return "", "", false
	}
	if u.Host == "" || u.Hostname() == "" {
		return "", "", false
	}
	return u.Hostname(), scheme + "://" + u.Host, true
}

func splitOrigins(raw string) []string {
	var out []string
	for _, o := range strings.Split(raw, ",") {
		if trimmed := strings.TrimSpace(o); trimmed != "" {
			out = append(out, trimmed)
		}
	}
	return out
}
