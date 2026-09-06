package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

// Gaesteliste gueltiger Anmeldungen je Nutzer (Issue #2129, ADR-0060).
//
// Ablage BEWUSST in einer eigenen Datei data/users/<user_id>/sessions.json,
// nicht in der user.json. Zwei Gruende: (1) die bestehenden SaveUser-Aufrufer
// schreiben das GANZE Nutzerobjekt zurueck -- ein gleichzeitiger
// Profil-Schreiber koennte einen Widerruf sonst schlicht ueberschreiben, und
// ausgerechnet der Widerruf vertraegt diesen Verlust nicht; (2) es bleibt aus
// dem model.User-Schema heraus und loest damit nicht bei jeder Anmeldung den
// Schema-Backup-Hook aus.

// Session ist ein Eintrag der Gaesteliste. Bewusst ein Objekt und kein blanker
// String: eine spaetere Geraeteuebersicht ("angemeldet auf 3 Geraeten seit
// ...") soll ohne Formatbruch hineinwachsen koennen.
type Session struct {
	ID        string    `json:"id"`
	CreatedAt time.Time `json:"created_at"`
}

type sessionFile struct {
	Sessions []Session `json:"sessions"`
	// LegacyRevokedAt schliesst die Abmelde-Luecke des Uebergangs: ein
	// Alt-Merkmal steht auf keiner Gaesteliste, es gaebe beim Abmelden also
	// nichts zu entfernen, und es waere bis zu 24 Stunden weiter gueltig.
	//
	// Das ist KEINE wiederauferstandene Sperrliste: ein einzelner Wert je
	// Nutzer, kein Verzeichnis einzelner Merkmale. Er faellt mit dem
	// Legacy-Zweig ersatzlos weg.
	LegacyRevokedAt *time.Time `json:"legacy_revoked_at,omitempty"`
}

func (s *Store) sessionsPath(userId string) string {
	return filepath.Join(s.UserDir(userId), "sessions.json")
}

// readSessionFile liest die Datei ohne Sperre. Eine FEHLENDE Datei ist der
// leere Stand, kein Fehler -- Bestandsnutzer haben noch keine, und ein Fehler
// wuerde sie mit einem Serverfehler statt mit einer Anmeldeaufforderung
// aussperren.
func (s *Store) readSessionFile(userId string) (sessionFile, error) {
	var f sessionFile
	data, err := os.ReadFile(s.sessionsPath(userId))
	if err != nil {
		if os.IsNotExist(err) {
			return f, nil
		}
		return f, err
	}
	if err := json.Unmarshal(data, &f); err != nil {
		return sessionFile{}, err
	}
	return f, nil
}

func (s *Store) writeSessionFile(userId string, f sessionFile) error {
	dir := s.UserDir(userId)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	if f.Sessions == nil {
		f.Sessions = []Session{}
	}
	data, err := json.MarshalIndent(f, "", "  ")
	if err != nil {
		return err
	}
	return writeFileLogged(s.sessionsPath(userId), data)
}

// LoadSessions liefert die Gaesteliste eines Nutzers (leer, wenn keine da ist).
func (s *Store) LoadSessions(userId string) ([]Session, error) {
	unlock := lockSessions(userId)
	defer unlock()
	f, err := s.readSessionFile(userId)
	return f.Sessions, err
}

// LegacyRevokedAt liefert den Zeitpunkt, ab dem Alt-Merkmale dieses Nutzers
// nicht mehr gelten (nil, wenn nie widerrufen wurde).
func (s *Store) LegacyRevokedAt(userId string) (*time.Time, error) {
	unlock := lockSessions(userId)
	defer unlock()
	f, err := s.readSessionFile(userId)
	return f.LegacyRevokedAt, err
}

// RevokeLegacySessions entwertet alle Alt-Merkmale dieses Nutzers, ohne die
// Gaesteliste anzutasten. Gebraucht beim Abmelden mit einem Alt-Merkmal: dort
// gibt es keinen Eintrag zu entfernen, und ohne diesen Vermerk bliebe die
// Zusage "Abmelden wirkt" im Uebergangsfenster unerfuellt.
func (s *Store) RevokeLegacySessions(userId string) error {
	unlock := lockSessions(userId)
	defer unlock()

	f, err := s.readSessionFile(userId)
	if err != nil {
		return err
	}
	now := time.Now()
	f.LegacyRevokedAt = &now
	return s.writeSessionFile(userId, f)
}

// HasSession beantwortet die Frage, an der die gesamte unbefristete Anmeldung
// haengt: steht diese Anmelde-Kennung noch auf der Gaesteliste?
func (s *Store) HasSession(userId, sessionId string) (bool, error) {
	if userId == "" || sessionId == "" {
		return false, nil
	}
	unlock := lockSessions(userId)
	defer unlock()

	f, err := s.readSessionFile(userId)
	if err != nil {
		return false, err
	}
	for _, sess := range f.Sessions {
		if sess.ID == sessionId {
			return true, nil
		}
	}
	return false, nil
}

// AddSession traegt eine neue Anmeldung ein. Lesen-Aendern-Schreiben laeuft
// unter der Pro-Nutzer-Sperre, damit zwei gleichzeitige Anmeldungen desselben
// Kontos einander nicht verdraengen.
func (s *Store) AddSession(userId, sessionId string) error {
	unlock := lockSessions(userId)
	defer unlock()

	f, err := s.readSessionFile(userId)
	if err != nil {
		return err
	}
	for _, sess := range f.Sessions {
		if sess.ID == sessionId {
			return nil
		}
	}
	f.Sessions = append(f.Sessions, Session{ID: sessionId, CreatedAt: time.Now()})
	return s.writeSessionFile(userId, f)
}

// RemoveSession entfernt genau eine Anmeldung ("dieses Geraet abmelden").
func (s *Store) RemoveSession(userId, sessionId string) error {
	unlock := lockSessions(userId)
	defer unlock()

	f, err := s.readSessionFile(userId)
	if err != nil {
		return err
	}
	kept := make([]Session, 0, len(f.Sessions))
	for _, sess := range f.Sessions {
		if sess.ID != sessionId {
			kept = append(kept, sess)
		}
	}
	if len(kept) == len(f.Sessions) {
		return nil
	}
	f.Sessions = kept
	return s.writeSessionFile(userId, f)
}

// ClearSessions leert die Gaesteliste ("auf allen Geraeten abmelden", ebenso
// Passwortwechsel und Passwort-Zuruecksetzen) UND entwertet die Alt-Merkmale.
// Ohne den zweiten Teil bliebe genau hier dieselbe Luecke offen wie beim
// Abmelden: ein Alt-Merkmal steht auf keiner Liste, ein Leeren traefe es also
// nicht.
func (s *Store) ClearSessions(userId string) error {
	unlock := lockSessions(userId)
	defer unlock()

	now := time.Now()
	return s.writeSessionFile(userId, sessionFile{LegacyRevokedAt: &now})
}
