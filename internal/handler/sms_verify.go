package handler

// SMS-Nummer-Verifikation — Issue #2406 (S3 aus #2153, Epic #2138).
// Spec: docs/specs/modules/sms_nummer_verifikation.md §3/§4.
//
// Go erzeugt und prueft den Code; versendet wird er ausschliesslich ueber den
// internen Python-Endpunkt (ADR-0062/ADR-0076) — einen zweiten seven.io-Client
// in Go gibt es bewusst nicht. Die eigentliche Sperre gegen Versand an eine
// unbewiesene Nummer sitzt NICHT hier, sondern an der Wirkstelle
// `src/app/config.py::with_user_profile` (AC-1).

import (
	"bytes"
	"crypto/rand"
	"encoding/json"
	"fmt"
	"log"
	"math/big"
	"net/http"
	"strings"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	smsCodeLaenge      = 6
	smsCodeGueltigkeit = 10 * time.Minute
	smsCodeMaxVersuche = 5
)

// smsVerifiziert meldet, ob die WIRKSAME Nummer des Kontos bewiesen ist —
// dieselbe Frage, die `with_user_profile` auf der Python-Seite stellt. Beide
// Seiten getrimmt (AC-12), damit ein ungetrimmter Backfill-Bestand hier nicht
// anders beurteilt wird als dort.
func smsVerifiziert(u *model.User) bool {
	bewiesen := strings.TrimSpace(u.SmsVerifiedNumber)
	return bewiesen != "" && bewiesen == strings.TrimSpace(u.SmsTo)
}

// smsZielnummer liefert die Nummer, die gerade zu beweisen ist: die
// ausstehende, sonst die eingetragene (Muster dispatchVerificationMail).
func smsZielnummer(u *model.User) string {
	if u.PendingSmsTo != "" {
		return u.PendingSmsTo
	}
	return u.SmsTo
}

// generateSmsCode zieht sechs Ziffern aus crypto/rand (Muster
// randomStringFromAlphabet, premium_sms_link_code.go).
func generateSmsCode() (string, error) {
	limit := big.NewInt(10)
	out := make([]byte, smsCodeLaenge)
	for i := range out {
		n, err := rand.Int(rand.Reader, limit)
		if err != nil {
			return "", err
		}
		out[i] = byte('0' + n.Int64())
	}
	return string(out), nil
}

// issueSmsVerificationCode erzeugt den Code, persistiert NUR seinen Hash und
// gibt den Klartext zurueck. Die Datei entsteht VOR dem Sendeversuch — der
// Code muss auch ohne funktionierenden Versand gelten (Staging-Testweg §5).
func issueSmsVerificationCode(s *store.Store, userId, number string) (string, error) {
	code, err := generateSmsCode()
	if err != nil {
		return "", fmt.Errorf("sms code generation failed: %w", err)
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(code), bcrypt.DefaultCost)
	if err != nil {
		return "", fmt.Errorf("sms code hash failed: %w", err)
	}
	if err := s.SaveSmsVerification(userId, model.SmsVerificationCode{
		CodeHash:  string(hash),
		ExpiresAt: time.Now().Add(smsCodeGueltigkeit),
		Number:    number,
	}); err != nil {
		return "", fmt.Errorf("SaveSmsVerification failed: %w", err)
	}
	return code, nil
}

// sendSmsCodeFn ist der Test-Seam (Muster sendVerificationMailFn): Default ist
// der echte Aufruf des internen Python-Endpunkts.
var sendSmsCodeFn = postSmsVerificationCode

func postSmsVerificationCode(cfg config.Config, userId, number, code string) error {
	rumpf, err := json.Marshal(map[string]string{"user_id": userId, "to": number, "code": code})
	if err != nil {
		return err
	}
	// Kein eigener Header-Code: coreauth.Install haengt X-GZ-Core-Auth an jeden
	// http.DefaultTransport-Aufruf gegen den Core (Muster forecast.go).
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Post(cfg.PythonCoreURL+"/api/_internal/sms/verification-code",
		"application/json", bytes.NewReader(rumpf))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		return fmt.Errorf("python core answered %d", resp.StatusCode)
	}
	return nil
}

// dispatchSmsVerificationCode stellt den Code aus (synchron, damit er nach der
// Rueckkehr garantiert auf Platte liegt) und schickt ihn asynchron los. Ein
// gescheiterter Versand laesst den Code gueltig — der Nutzer kann „erneut
// senden" druecken.
func dispatchSmsVerificationCode(s *store.Store, cfg config.Config, userId, number string) {
	code, err := issueSmsVerificationCode(s, userId, number)
	if err != nil {
		log.Printf("sms verification: code issuance failed for %s: %v", userId, err)
		return
	}
	go func() {
		if err := sendSmsCodeFn(cfg, userId, number, code); err != nil {
			log.Printf("sms verification: code dispatch failed for %s: %v", userId, err)
		}
	}()
}

func smsFehler(w http.ResponseWriter, status int, code string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	fmt.Fprintf(w, `{"error":%q}`, code)
}

// PostSmsVerifyHandler loest den Bestaetigungscode ein. Die Kennung kommt
// AUSSCHLIESSLICH aus der Sitzung — nie aus dem Rumpf (der Endpunkt ist
// anmeldepflichtig, anders als ResendVerificationHandler).
func PostSmsVerifyHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userId := middleware.UserIDFromContext(r.Context())
		var req struct {
			Code string `json:"code"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			smsFehler(w, 400, "invalid request")
			return
		}
		user, err := s.LoadUser(userId)
		if err != nil || user == nil {
			smsFehler(w, 404, "not_found")
			return
		}
		rec, err := s.LoadSmsVerification(userId)
		if err != nil || rec == nil ||
			time.Now().After(rec.ExpiresAt) || rec.FailedAttempts >= smsCodeMaxVersuche {
			smsFehler(w, 400, "code_expired")
			return
		}
		// Nummernbindung (AC-4c): der Code beweist GENAU die Nummer, fuer die
		// er ausgestellt wurde. Ohne diese Pruefung bestaetigte ein Code, der
		// auf eine fremde Nummer zeigt, die Nummer des Kontos.
		if rec.Number == "" || rec.Number != smsZielnummer(user) {
			smsFehler(w, 400, "invalid_code")
			return
		}
		if bcrypt.CompareHashAndPassword([]byte(rec.CodeHash), []byte(req.Code)) != nil {
			rec.FailedAttempts++
			if rec.FailedAttempts >= smsCodeMaxVersuche {
				// Sofort verbrennen: ein sechster Versuch ist nicht noetig,
				// um den Code wertlos zu machen.
				if err := s.DeleteSmsVerification(userId); err != nil {
					log.Printf("sms verification: delete after lockout failed for %s: %v", userId, err)
				}
			} else if err := s.SaveSmsVerification(userId, *rec); err != nil {
				log.Printf("sms verification: attempt counter not persisted for %s: %v", userId, err)
			}
			smsFehler(w, 400, "invalid_code")
			return
		}

		// Read-Modify-Write: das geladene Objekt wird geaendert, nicht ersetzt.
		if user.PendingSmsTo != "" {
			user.SmsTo = user.PendingSmsTo
			user.PendingSmsTo = ""
		}
		now := time.Now().UTC()
		user.SmsVerifiedNumber = user.SmsTo
		user.SmsVerifiedAt = &now
		if err := s.SaveUser(*user); err != nil {
			smsFehler(w, 500, "store_error")
			return
		}
		if err := s.DeleteSmsVerification(userId); err != nil {
			log.Printf("sms verification: delete after success failed for %s: %v", userId, err)
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(toProfileResponse(user))
	}
}

// PostSmsResendHandler stellt einen frischen Code aus und verschickt ihn an die
// gerade zu beweisende Nummer. Tier-Gate und Mengenbremse gelten hier genauso
// wie im Profil-Update (AC-7): ein zweiter Eintrittspunkt darf nicht der
// billigere sein.
func PostSmsResendHandler(s *store.Store, cfg config.Config, limiter *MailFloodLimiter) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userId := middleware.UserIDFromContext(r.Context())
		user, err := s.LoadUser(userId)
		if err != nil || user == nil {
			smsFehler(w, 404, "not_found")
			return
		}
		ziel := smsZielnummer(user)
		if ziel == "" {
			smsFehler(w, 400, "no_number")
			return
		}
		if !model.SmsAllowed(model.EffectiveTier(user.Tier)) {
			smsFehler(w, 400, "sms_not_allowed")
			return
		}
		if !limiter.Allow(userId, ziel) {
			w.Header().Set("Retry-After", limiter.RetryAfterHeader())
			smsFehler(w, 429, "rate_limit_exceeded")
			return
		}
		dispatchSmsVerificationCode(s, cfg, userId, ziel)
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"sent"}`))
	}
}
