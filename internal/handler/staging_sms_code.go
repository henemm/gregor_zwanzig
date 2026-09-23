package handler

// Staging-only Testweg fuer den SMS-Bestaetigungscode — Issue #2406, AC-15.
// Spec: docs/specs/modules/sms_nummer_verifikation.md §5.
//
// Auf Staging stellt der seven.io-Sandbox-Zugang (#1336) nie zu; ohne diesen
// Weg waere der Bestaetigungsablauf dort nicht durch den Browser pruefbar.
//
// 🔴 ABWEICHEND vom E-Mail-Vorbild (staging_verify_token.go, das eine beliebige
// `username` aus dem Rumpf nimmt): dieser Handler IGNORIERT den Rumpf
// vollstaendig und arbeitet ausschliesslich auf der Sitzungskennung — ein
// fremdes Konto laesst sich darueber nicht abfragen. Registriert nur bei
// GZ_ENV=staging (router.go) UND anmeldepflichtig: der Pfad liegt unter
// /api/auth/..., nicht unter den von AuthMiddleware pauschal befreiten
// Praefixen, und steht nicht in der Public-Allowlist.
//
// Er MINTET einen frischen Code (nur der bcrypt-Hash liegt auf Platte, der
// Klartext existiert nur im Moment der Erzeugung) und macht KEINEN
// Sendeversuch. Bestaetigen kann weiterhin ausschliesslich
// PostSmsVerifyHandler — der Testweg prueft den echten Pfad mit, statt ihn zu
// umgehen.

import (
	"encoding/json"
	"log"
	"net/http"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

func StagingSmsCodeHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userId := middleware.UserIDFromContext(r.Context())
		user, err := s.LoadUser(userId)
		if err != nil || user == nil {
			smsFehler(w, 404, "not_found")
			return
		}
		ziel := smsZielnummer(user)
		if ziel == "" {
			smsFehler(w, 404, "no_number")
			return
		}
		code, err := issueSmsVerificationCode(s, userId, ziel)
		if err != nil {
			log.Printf("staging sms code: issuance failed for %s: %v", userId, err)
			smsFehler(w, 500, "internal error")
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"code": code})
	}
}
