package store

// Issue #2194 (Epic #2138, ADR-0105): E-Mail-Adresse als Login-Identifier.
// Spec: docs/specs/modules/email_login_identifier.md
//
// Das Konto bleibt an eine stabile, undurchsichtige Kennung gebunden
// (Ordnername = ID); der Login sucht das Konto ueber die E-Mail-Adresse.

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"os"

	"github.com/henemm/gregor-api/internal/model"
)

// opaqueIDRandFn ist die Zufallsquelle fuer NewOpaqueUserID (Test-Seam fuer
// den Kollisionsnachweis). Vertrag: genau ein Aufruf pro Versuch mit einem
// 4-Byte-Puffer.
var opaqueIDRandFn = rand.Read

// opaqueIDMaxAttempts begrenzt die Wiederholungen bei Kollision: 4 Byte
// Zufall ergeben ~4 Mrd. IDs, eine Dauerkollision deutet auf eine kaputte
// Zufallsquelle hin und endet mit Fehler statt Endlosschleife.
const opaqueIDMaxAttempts = 16

// ErrOpaqueIDExhausted meldet, dass keine freie ID gefunden wurde.
var ErrOpaqueIDExhausted = errors.New("opaque user id: no free id after max attempts")

// FindUsersByLoginEmail liefert alle Nicht-Testkonten, deren Feld email
// (und NUR email, nie mail_to) normalisiert gleich der normalisierten
// Eingabe ist. Leere Adresse => keine Treffer. Fail-closed: eine unlesbare
// user.json irgendeines Kontos bricht mit Fehler ab (sonst koennte aus zwei
// Treffern scheinbar einer werden).
// gz-store-scope-exempt: sucht kontouebergreifend, die Kennung ist erst das Ergebnis des Lookups
func (s *Store) FindUsersByLoginEmail(addr string) ([]*model.User, error) {
	x := NormalizeEmailAddress(addr)
	if x == "" {
		return nil, nil
	}
	ids, err := s.ListUserIDs()
	if err != nil {
		return nil, err
	}
	var treffer []*model.User
	for _, id := range ids {
		u, err := s.LoadUser(id)
		if err != nil {
			return nil, err
		}
		if u == nil || model.IsTestAccount(u) {
			continue
		}
		if NormalizeEmailAddress(u.Email) != x {
			continue
		}
		// Der Ordnername ist die Kennung (Sitzung, Pfade); ein abweichendes
		// oder fehlendes "id"-Feld in user.json darf sie nicht verschieben.
		u.ID = id
		treffer = append(treffer, u)
	}
	return treffer, nil
}

// NewOpaqueUserID erzeugt eine neue Konto-ID "<prefix>-<8 hex>" aus
// crypto/rand. Eine bereits belegte ID (Eintrag unter users/ existiert)
// fuehrt zu einem neuen Versuch; ein bestehendes Konto wird nie
// zurueckgegeben und damit nie ueberschrieben. Nach opaqueIDMaxAttempts
// Kollisionen kommt ein Fehler.
// gz-store-scope-exempt: erzeugt eine kontouebergreifend freie Kennung, es gibt noch kein Konto
func (s *Store) NewOpaqueUserID(prefix string) (string, error) {
	for i := 0; i < opaqueIDMaxAttempts; i++ {
		b := make([]byte, 4)
		if _, err := opaqueIDRandFn(b); err != nil {
			return "", fmt.Errorf("opaque user id: random source failed: %w", err)
		}
		id := prefix + "-" + hex.EncodeToString(b)
		if !ValidUserID(id) {
			return "", fmt.Errorf("opaque user id: invalid prefix %q", prefix)
		}
		if _, err := os.Lstat(s.UserDir(id)); err == nil {
			continue
		} else if !os.IsNotExist(err) {
			return "", fmt.Errorf("opaque user id: collision check failed: %w", err)
		}
		return id, nil
	}
	return "", ErrOpaqueIDExhausted
}
