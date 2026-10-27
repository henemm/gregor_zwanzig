package handler

// Konto-Endpoint fuer den Premium-SMS-Verknuepfungs-Code — Issue #2154
// Scheibe A (Spec D1/D2/D3).
//
//	POST /api/auth/premium-sms-link-code -> erzeugt/erneuert den Code und gibt
//	     ihn GENAU EINMAL im Klartext zurueck. Erneuern ersetzt die Datei und
//	     entwertet damit den alten Code.
//	GET  /api/auth/premium-sms-link-code -> {"exists": true|false}, niemals der
//	     Code und niemals der Hash.
//
// Beide anmeldepflichtig ueber die globale AuthMiddleware; die Kennung kommt
// aus dem Auth-Kontext, NIE aus s.UserID (Vorgabe-Kennung "default" waere ein
// Cross-User-Datenleck). Vorbild telegram_connect.go::GetTelegramLinkHandler.
//
// bcryptCost als Parameter nach dem Vorbild RegisterHandler/ForgotPasswordHandler
// (auth.go:31,231) — der Router reicht bcrypt.DefaultCost ein, Tests MinCost.

import (
	"crypto/rand"
	"encoding/json"
	"math/big"
	"net/http"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// Gestalt des Codes (Issue #2323): fester Praefix "XX" + 3 Buchstaben + 3
// Ziffern, jeweils ohne die verwechselbaren I/L/O/0/1. Der Code wird per
// Satellit abgetippt — eine Verwechslung kostet einen Rateversuch und eine
// bezahlte SMS. Der feste Praefix macht ihn im Befehlstext eindeutig von einem
// Steuerbefehl unterscheidbar (Python-Pendant:
// src/services/inbound_sms_reader.py::_LINK_CODE_PATTERN).
const premiumSmsLinkCodePrefix = "XX"
const premiumSmsLinkCodeLetterAlphabet = "ABCDEFGHJKMNPQRSTUVWXYZ"
const premiumSmsLinkCodeDigitAlphabet = "23456789"
const premiumSmsLinkCodeLetterCount = 3
const premiumSmsLinkCodeDigitCount = 3

// generatePremiumSmsLinkCode zieht Buchstaben- und Ziffernblock getrennt aus
// crypto/rand — ein gemeinsames Alphabet liesse Ziffern an Buchstabenposition
// landen und umgekehrt.
func generatePremiumSmsLinkCode() (string, error) {
	letters, err := randomStringFromAlphabet(premiumSmsLinkCodeLetterAlphabet, premiumSmsLinkCodeLetterCount)
	if err != nil {
		return "", err
	}
	digits, err := randomStringFromAlphabet(premiumSmsLinkCodeDigitAlphabet, premiumSmsLinkCodeDigitCount)
	if err != nil {
		return "", err
	}
	return premiumSmsLinkCodePrefix + letters + digits, nil
}

// randomStringFromAlphabet: rand.Int statt "Zufallsbyte modulo n" — 256 ist
// kein Vielfaches der Alphabetlaengen, ein Modulo verzerrte die vorderen
// Zeichen des Alphabets und naehme dem Geheimnis Entropie.
func randomStringFromAlphabet(alphabet string, length int) (string, error) {
	limit := big.NewInt(int64(len(alphabet)))
	out := make([]byte, length)
	for i := range out {
		n, err := rand.Int(rand.Reader, limit)
		if err != nil {
			return "", err
		}
		out[i] = alphabet[n.Int64()]
	}
	return string(out), nil
}

// PostPremiumSmsLinkCodeHandler erzeugt bzw. erneuert den Code.
func PostPremiumSmsLinkCodeHandler(s *store.Store, bcryptCost int) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		if userID == "" {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}

		code, err := generatePremiumSmsLinkCode()
		if err != nil {
			http.Error(w, "internal error", http.StatusInternalServerError)
			return
		}
		hash, err := bcrypt.GenerateFromPassword([]byte(code), bcryptCost)
		if err != nil {
			http.Error(w, "internal error", http.StatusInternalServerError)
			return
		}
		if err := s.SaveLinkCode(userID, model.PremiumSmsLinkCode{
			CodeHash:  string(hash),
			CreatedAt: time.Now().UTC(),
		}); err != nil {
			http.Error(w, "save failed", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"code": code})
	}
}

// GetPremiumSmsLinkCodeHandler meldet nur, OB ein Code vorliegt.
func GetPremiumSmsLinkCodeHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		if userID == "" {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		stored, err := s.LoadLinkCode(userID)
		if err != nil {
			http.Error(w, "load failed", http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]bool{"exists": stored != nil})
	}
}
