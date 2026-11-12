package handler

// Zugangsregeln der Staging-Hilfsendpunkte (Issue #2961, Spec
// security_haertung_2026_11_go_schnittstellen.md AC-18 bis AC-20).
//
// Die Endpunkte sind nur bei GZ_ENV=staging registriert und anmeldepflichtig.
// Zusaetzlich gilt jetzt:
//   - Aufrufer muss Admin, das Betreiber-/Seed-Konto des Stacks
//     (GZ_AUTH_USER, auf Staging das Konto der E2E-Anmeldung) oder ein
//     Testkonto (Profilfeld is_test_user, ADR-0072) sein.
//   - Ausnahme nur fuer den SMS-Code des EIGENEN Kontos: ein Wegwerfkonto der
//     laufenden Pruefung (angelegt vor hoechstens stagingWegwerfFenster) darf
//     seinen eigenen Code abholen — die Live-Specs melden sich als frisch
//     registriertes Konto an (feat-2406-sms-verify.spec.ts).
//   - Das E-Mail-Token gibt es nur fuer das eigene Konto, Testkonten und
//     frisch registrierte, noch unbestaetigte Konten (E2E-Zweitnutzer sind
//     bewusst KEINE Testkonten, frontend/e2e/helpers.ts). Jedes andere oder
//     unbekannte Konto bekommt dieselbe 404-Antwort — die Existenz fremder
//     Konten bleibt verborgen.

import (
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// stagingWegwerfFenster: so lange gilt ein frisch registriertes Konto als
// Wegwerfkonto der laufenden Pruefung.
const stagingWegwerfFenster = time.Hour

// StagingZugang traegt, wer die Staging-Hilfsendpunkte nutzen darf.
type StagingZugang struct {
	// Admins: GZ_ADMIN_USER_IDS.
	Admins map[string]struct{}
	// Betreiber: GZ_AUTH_USER (Seed-/E2E-Konto des Stacks), leer = keins.
	Betreiber string
}

// berechtigt: Admin, Betreiber-Konto oder Testkonto.
func (z StagingZugang) berechtigt(u *model.User) bool {
	if u == nil || u.ID == "" {
		return false
	}
	if _, ok := z.Admins[u.ID]; ok {
		return true
	}
	return (z.Betreiber != "" && u.ID == z.Betreiber) || model.IsTestAccount(u)
}

// frischRegistriert: Konto wurde vor hoechstens stagingWegwerfFenster angelegt.
func frischRegistriert(u *model.User, jetzt time.Time) bool {
	return u != nil && !u.CreatedAt.IsZero() && jetzt.Sub(u.CreatedAt) <= stagingWegwerfFenster
}

// tokenZielZulaessig: fuer wen das E-Mail-Token herausgegeben werden darf.
func tokenZielZulaessig(aufrufer string, ziel *model.User, jetzt time.Time) bool {
	if ziel == nil {
		return false
	}
	if ziel.ID == aufrufer || model.IsTestAccount(ziel) {
		return true
	}
	return ziel.EmailVerifiedAt == nil && frischRegistriert(ziel, jetzt)
}
