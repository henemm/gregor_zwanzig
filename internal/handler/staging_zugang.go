package handler

// Zielregel des Staging-Testwegs fuer E-Mail-Bestaetigungstoken (Issue #2961,
// Spec security_haertung_2026_11_go_schnittstellen.md AC-18/AC-19).
//
// Die Staging-Hilfsendpunkte sind nur bei GZ_ENV=staging registriert und
// anmeldepflichtig; eine gueltige Sitzung genuegt. Tragend ist die Zielregel:
// das Token gibt es nur fuer das eigene Konto, fuer Testkonten (Profilfeld
// is_test_user, ADR-0072) und fuer frisch registrierte, noch unbestaetigte
// Konten (E2E-Zweitnutzer sind bewusst KEINE Testkonten, frontend/e2e/
// helpers.ts). Jedes andere oder unbekannte Konto bekommt dieselbe
// 404-Antwort — die Existenz fremder Konten bleibt verborgen. SMS-Code und
// Seed wirken ohnehin nur auf das eigene Konto (Sitzungskennung).

import (
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// stagingWegwerfFenster: so lange gilt ein frisch registriertes Konto als
// Wegwerfkonto der laufenden Pruefung.
const stagingWegwerfFenster = time.Hour

// frischRegistriert: Konto wurde vor hoechstens stagingWegwerfFenster angelegt.
func frischRegistriert(u *model.User, jetzt time.Time) bool {
	return u != nil && !u.CreatedAt.IsZero() && jetzt.Sub(u.CreatedAt) <= stagingWegwerfFenster
}

// tokenZielZulaessig: fuer wen das E-Mail-Token herausgegeben werden darf.
func tokenZielZulaessig(aufrufer string, ziel *model.User, jetzt time.Time) bool {
	if ziel == nil {
		return false
	}
	if (aufrufer != "" && ziel.ID == aufrufer) || model.IsTestAccount(ziel) {
		return true
	}
	return ziel.EmailVerifiedAt == nil && frischRegistriert(ziel, jetzt)
}
