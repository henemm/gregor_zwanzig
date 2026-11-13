package handler

// PostPremiumSmsLearnHandler — POST /api/internal/premium-sms-learn
//
// Issue #1676 Scheibe S1: lernt die von Garmin je Gespraech neu vergebene
// Rueckadresse fuer den Premium-SMS-Rueckkanal. Wird ausschliesslich vom
// Python-Core (InboundSmsReader, localhost) aufgerufen — Vorbild
// telegram_connect.go::PostTelegramConnectHandler (localhost-only-Sperre).
//
// Spec: docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md v1.1,
// Implementation Details "Go: neuer Endpoint POST /api/internal/premium-sms-learn".
//
// Aufloesung (Issue #2154 Scheibe A, #2328, seit Issue #2961 Welle 2 /
// ADR-0116 mit Vorrang des Codes; Kandidaten nur Premium-Tier, nicht gesperrt):
//  1. Mit Code -> Budget der Ratebremse pruefen (je Absender, dann global),
//     dann bcrypt-Vergleich gegen den gespeicherten Verknuepfungs-Code jedes
//     Kandidaten; GENAU EIN Treffer -> dieses Konto, auch wenn die Nummer
//     gerade frisch bei einem ANDEREN Konto gespeichert ist (Garmin vergibt
//     Nummern aus einem rotierenden Pool neu). Ein falscher Code zaehlt als
//     Fehlversuch.
//  2. Sonst GENAU EIN frischer Treffer auf gespeicherte PremiumSmsReplyTo
//     (innerhalb model.PremiumSmsReplyTTL) -> dieser Nutzer. So kippt ein
//     Vertipper im Code die bestehende Zuordnung nicht.
//  3. Sonst ohne Code: >=2 frische Treffer -> reasonStoredReplyToAmbiguous,
//     kein Treffer -> reasonLinkCodeRequired; mit Code der Grund aus Schritt 1
//     (ungueltig bzw. Ratebremse). NIE Fallback auf "default".
//
// Beim Lernen entfernt der Store die Nummer bei allen anderen Konten
// (store.LearnPremiumSmsReplyTo): eine Rueckadresse gehoert hoechstens einem
// Konto.
//
// Der Dry-Run-Zweig (AC-10) ist ein eigener Rueckgabepfad VOR SaveUser, kein
// `if` drumherum — SaveUser ist im Dry-Run strukturell unerreichbar.
import (
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// Ablehnungsgruende, wie sie im Antwortkoerper erscheinen.
const (
	reasonLinkCodeRequired       = "link_code_required"
	reasonLinkCodeInvalid        = "link_code_invalid"
	reasonLinkCodeRateLimited    = "link_code_rate_limited"
	reasonStoredReplyToAmbiguous = "stored_reply_to_ambiguous"
)

// PostPremiumSmsLearnHandler baut den Handler mit injiziertem Store und
// injizierter Ratebremse (prozessweit, s. premium_sms_ratelimit.go).
func PostPremiumSmsLearnHandler(s *store.Store, rl *PremiumSmsRateLimiter) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !requireLocalOnly(w, r) {
			return
		}

		var body struct {
			From   string `json:"from"`
			Code   string `json:"code"`
			DryRun bool   `json:"dry_run"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.From == "" {
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}

		userIDs, err := s.ListUserIDs()
		if err != nil {
			http.Error(w, "list users failed", http.StatusInternalServerError)
			return
		}

		var candidates []*model.User
		var storedMatches []*model.User
		for _, id := range userIDs {
			user, err := s.LoadUser(id)
			if err != nil || user == nil {
				continue
			}
			if model.EffectiveTier(user.Tier) != "premium" {
				continue
			}
			// Issue #2155 S3 (ADR-0080): gesperrte Konten sind keine Kandidaten.
			if user.Disabled {
				continue
			}
			candidates = append(candidates, user)
			if user.PremiumSmsReplyTo == body.From {
				storedMatches = append(storedMatches, user)
			}
		}

		w.Header().Set("Content-Type", "application/json")

		if body.DryRun {
			// Strukturell eigener Rueckgabepfad: weder SaveUser noch der
			// prozessweite Fehlversuchszaehler sind von hier aus erreichbar.
			// Der Trockenlauf rechnet gegen eine Wegwerf-Bremse, damit ein
			// falscher Code die echte Bremse nie beruehrt (AC-8).
			target, reason := resolvePremiumSmsTarget(s, candidates, storedMatches, body.From, body.Code, rl.scratch())
			if target == nil {
				json.NewEncoder(w).Encode(map[string]string{
					"status":  "dry_run",
					"outcome": "would_skip",
					"reason":  reason,
				})
				return
			}
			maskedFrom := maskPhoneNumber(body.From)
			json.NewEncoder(w).Encode(map[string]string{
				"status":      "dry_run",
				"outcome":     "would_learn",
				"user_id":     target.ID,
				"masked_from": maskedFrom,
			})
			return
		}

		target, reason := resolvePremiumSmsTarget(s, candidates, storedMatches, body.From, body.Code, rl)
		if reason == reasonLinkCodeRateLimited {
			w.WriteHeader(http.StatusTooManyRequests)
			json.NewEncoder(w).Encode(map[string]string{
				"status": "skipped",
				"reason": reason,
			})
			return
		}
		if target == nil {
			w.WriteHeader(http.StatusConflict)
			json.NewEncoder(w).Encode(map[string]string{
				"status": "skipped",
				"reason": reason,
			})
			return
		}

		if err := s.LearnPremiumSmsReplyTo(target.ID, body.From, time.Now().UTC()); err != nil {
			http.Error(w, "save failed", http.StatusInternalServerError)
			return
		}

		json.NewEncoder(w).Encode(map[string]string{"status": "ok", "user_id": target.ID})
	}
}

// resolvePremiumSmsTarget liefert das Zielkonto oder nil samt Ablehnungsgrund
// (Reihenfolge siehe Kopfkommentar, ADR-0116).
func resolvePremiumSmsTarget(
	s *store.Store, candidates []*model.User, storedMatches []*model.User,
	from, code string, rl *PremiumSmsRateLimiter,
) (*model.User, string) {
	// Dieselbe Frist-Semantik wie im Sendepfad und in der Oberflaeche — eine
	// zweite, eigene Vergleichsformel hier waere ein Drift-Risiko.
	var freshMatches []*model.User
	for _, candidate := range storedMatches {
		if model.DerivePremiumSmsReplyState(candidate.PremiumSmsReplyTo, candidate.PremiumSmsReplyAt) == model.PremiumSmsStateFresh {
			freshMatches = append(freshMatches, candidate)
		}
	}

	codeReason := ""
	if code != "" {
		target, reason := resolveByLinkCode(s, candidates, from, code, rl)
		if target != nil {
			return target, ""
		}
		codeReason = reason
	}
	if len(freshMatches) == 1 {
		return freshMatches[0], ""
	}
	if codeReason != "" {
		return nil, codeReason
	}
	if len(freshMatches) > 1 {
		return nil, reasonStoredReplyToAmbiguous
	}
	return nil, reasonLinkCodeRequired
}

// resolveByLinkCode prueft den mitgeschickten Code. Die Reihenfolge ist die
// Zusicherung: das Budget der Ratebremse wird VOR jedem bcrypt-Vergleich
// gefragt (#2154 AC-7). Stuende die Pruefung dahinter, koennte ein Angreifer
// weiter raten und die Bremse waere Zierde.
func resolveByLinkCode(
	s *store.Store, candidates []*model.User, from, code string, rl *PremiumSmsRateLimiter,
) (*model.User, string) {
	if !rl.AllowFrom(from) {
		return nil, reasonLinkCodeRateLimited
	}
	var matches []*model.User
	for _, c := range candidates {
		stored, err := s.LoadLinkCode(c.ID)
		if err != nil || stored == nil || stored.CodeHash == "" {
			continue
		}
		if bcrypt.CompareHashAndPassword([]byte(stored.CodeHash), []byte(code)) == nil {
			matches = append(matches, c)
		}
	}
	if len(matches) == 1 {
		return matches[0], ""
	}
	rl.RecordFailureFrom(from)
	return nil, reasonLinkCodeInvalid
}

// maskPhoneNumber loggt/meldet Rufnummern nur maskiert (Spec: "Protokolliere
// Rufnummern nur maskiert") — alle bis auf die letzten drei Stellen werden
// verdeckt.
func maskPhoneNumber(number string) string {
	if len(number) <= 3 {
		return strings.Repeat("*", len(number))
	}
	return strings.Repeat("*", len(number)-3) + number[len(number)-3:]
}
