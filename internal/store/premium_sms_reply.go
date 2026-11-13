package store

// Premium-SMS-Rueckadresse: Lernen mit Eindeutigkeit und Trennen — Issue #2961
// Welle 2 (ADR-0116).
//
// Garmin vergibt Absendernummern aus einem rotierenden Pool neu. Eine
// Rueckadresse gehoert deshalb hoechstens EINEM Konto: lernt Konto X die Nummer
// N, verliert jedes andere Konto N (Vorbild: Eindeutigkeit der
// Telegram-chat_id, Issue #2141). Sonst ginge eine Antwort oder ein Alarm des
// frueheren Inhabers an das Geraet eines fremden Nutzers.
//
// Beide Schreibwege sind Read-Modify-Write mit Merge auf Roh-Ebene
// (mergeUserJSON, CLAUDE.md "Daten-Schema-Reworks"): nur die zwei
// Rueckadress-Felder aendern sich, alle uebrigen — auch dem Modell unbekannte —
// Felder bleiben erhalten.

import (
	"encoding/json"
	"errors"
	"strings"
	"sync"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// premiumSmsLernSperre serialisiert alle Schreibwege der Rueckadresse
// (Lernen, Trennen). Ohne sie hinterliessen zwei gleichzeitige Lernvorgaenge
// derselben Nummer fuer zwei Konten die Nummer bei beiden: jeder entfernt sie
// beim anderen, bevor der andere sie setzt. Reihenfolge der Sperren immer
// erst diese, dann je Nutzer (mergeUserJSON) — kein Weg nimmt sie umgekehrt.
var premiumSmsLernSperre sync.Mutex

// ErrEmptyPremiumSmsReplyTo: eine leere Nummer ist keine Rueckadresse.
var ErrEmptyPremiumSmsReplyTo = errors.New("premium-sms: leere Rueckadresse")

// LearnPremiumSmsReplyTo setzt Rueckadresse und Zeitstempel bei id und entfernt
// dieselbe Nummer (in jeder Schreibweise, model.NormalizePremiumSmsNumber)
// vorher bei allen anderen Konten (unabhaengig von Tarif, Frische oder Sperre
// des anderen Kontos). Gespeichert wird die gelieferte Form.
//
// Reihenfolge: erst die anderen Konten bereinigen, dann das Zielkonto setzen.
// Scheitert ein Schritt, gibt es so nie zwei Inhaber derselben Nummer.
// gz-store-scope-exempt: die Kennung kommt als Parameter id herein, nicht aus s.UserID
func (s *Store) LearnPremiumSmsReplyTo(id, from string, at time.Time) error {
	if !ValidUserID(id) {
		return ErrInvalidUserID
	}
	key := model.NormalizePremiumSmsNumber(from)
	if strings.TrimSpace(from) == "" || key == "" {
		return ErrEmptyPremiumSmsReplyTo
	}
	premiumSmsLernSperre.Lock()
	defer premiumSmsLernSperre.Unlock()
	ids, err := s.ListUserIDs()
	if err != nil {
		return err
	}
	for _, other := range ids {
		if other == id {
			continue
		}
		u, err := s.LoadUser(other)
		if err != nil || u == nil || model.NormalizePremiumSmsNumber(u.PremiumSmsReplyTo) != key {
			continue
		}
		if err := s.clearPremiumSmsReplyLocked(other); err != nil {
			return err
		}
	}
	return s.mergeUserJSON(id, func(m map[string]json.RawMessage) {
		m["premium_sms_reply_to"], _ = json.Marshal(from)
		m["premium_sms_reply_at"], _ = json.Marshal(at.UTC())
	})
}

// ClearPremiumSmsReply entfernt Rueckadresse und Zeitstempel ("Verbindung
// trennen"). Der Verknuepfungs-Code (eigene Datei) bleibt unberuehrt.
// gz-store-scope-exempt: die Kennung kommt als Parameter id herein, nicht aus s.UserID
func (s *Store) ClearPremiumSmsReply(id string) error {
	premiumSmsLernSperre.Lock()
	defer premiumSmsLernSperre.Unlock()
	return s.clearPremiumSmsReplyLocked(id)
}

// clearPremiumSmsReplyLocked: Aufrufer haelt premiumSmsLernSperre.
func (s *Store) clearPremiumSmsReplyLocked(id string) error {
	return s.mergeUserJSON(id, func(m map[string]json.RawMessage) {
		delete(m, "premium_sms_reply_to")
		delete(m, "premium_sms_reply_at")
	})
}
