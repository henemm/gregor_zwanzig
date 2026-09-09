package store

import (
	"archive/zip"
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"strings"

	"github.com/henemm/gregor-api/internal/model"
)

// ListUserIDs returns the IDs of all registered users.
// A valid user directory must contain a user.json file.
// Returns an empty slice if the users directory does not exist.
func (s *Store) ListUserIDs() ([]string, error) {
	usersDir := filepath.Join(s.DataDir, "users")
	entries, err := os.ReadDir(usersDir)
	if err != nil {
		if os.IsNotExist(err) {
			return []string{}, nil
		}
		return nil, fmt.Errorf("read users dir: %w", err)
	}

	var ids []string
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		userJSON := filepath.Join(usersDir, e.Name(), "user.json")
		if _, err := os.Stat(userJSON); err == nil {
			ids = append(ids, e.Name())
		}
	}
	if ids == nil {
		ids = []string{}
	}
	return ids, nil
}

// UserDir returns the directory for a specific user.
// Uses explicit id parameter, NOT s.UserID — user records are global.
func (s *Store) UserDir(id string) string {
	return filepath.Join(s.DataDir, "users", id)
}

func (s *Store) LoadUser(id string) (*model.User, error) {
	if !ValidUserID(id) {
		return nil, ErrInvalidUserID
	}
	path := filepath.Join(s.UserDir(id), "user.json")

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	var user model.User
	if err := json.Unmarshal(data, &user); err != nil {
		return nil, err
	}

	return &user, nil
}

func (s *Store) SaveUser(user model.User) error {
	if !ValidUserID(user.ID) {
		return ErrInvalidUserID
	}
	dir := s.UserDir(user.ID)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	data, err := json.MarshalIndent(user, "", "  ")
	if err != nil {
		return err
	}

	return writeFileLogged(filepath.Join(dir, "user.json"), data)
}

// ProvisionUserDirs creates the standard subdirectories for a new user.
func (s *Store) ProvisionUserDirs(id string) error {
	if !ValidUserID(id) {
		return ErrInvalidUserID
	}
	base := s.UserDir(id)
	for _, sub := range []string{"locations", "gpx", "weather_snapshots"} {
		if err := os.MkdirAll(filepath.Join(base, sub), 0755); err != nil {
			return err
		}
	}
	return nil
}

func (s *Store) SaveResetToken(userId string, token model.PasswordResetToken) error {
	if !ValidUserID(userId) {
		return ErrInvalidUserID
	}
	dir := s.UserDir(userId)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(token, "", "  ")
	if err != nil {
		return err
	}
	return writeFileLogged(filepath.Join(dir, "password_reset.json"), data)
}

func (s *Store) LoadResetToken(userId string) (*model.PasswordResetToken, error) {
	if !ValidUserID(userId) {
		return nil, ErrInvalidUserID
	}
	path := filepath.Join(s.UserDir(userId), "password_reset.json")
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	var token model.PasswordResetToken
	if err := json.Unmarshal(data, &token); err != nil {
		return nil, err
	}
	return &token, nil
}

func (s *Store) DeleteResetToken(userId string) error {
	if !ValidUserID(userId) {
		return ErrInvalidUserID
	}
	path := filepath.Join(s.UserDir(userId), "password_reset.json")
	err := os.Remove(path)
	if os.IsNotExist(err) {
		return nil
	}
	return err
}

// SaveVerificationToken persists an EmailVerificationToken (Issue #1219
// Scheibe 2a-i) under data/users/<id>/email_verification.json. Mirrors
// SaveResetToken. Overwrites an existing file without warning — a second
// address change intentionally invalidates the first token (AC-7).
func (s *Store) SaveVerificationToken(userId string, token model.EmailVerificationToken) error {
	if !ValidUserID(userId) {
		return ErrInvalidUserID
	}
	dir := s.UserDir(userId)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(token, "", "  ")
	if err != nil {
		return err
	}
	return writeFileLogged(filepath.Join(dir, "email_verification.json"), data)
}

func (s *Store) LoadVerificationToken(userId string) (*model.EmailVerificationToken, error) {
	if !ValidUserID(userId) {
		return nil, ErrInvalidUserID
	}
	path := filepath.Join(s.UserDir(userId), "email_verification.json")
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	var token model.EmailVerificationToken
	if err := json.Unmarshal(data, &token); err != nil {
		return nil, err
	}
	return &token, nil
}

func (s *Store) DeleteVerificationToken(userId string) error {
	if !ValidUserID(userId) {
		return ErrInvalidUserID
	}
	path := filepath.Join(s.UserDir(userId), "email_verification.json")
	err := os.Remove(path)
	if os.IsNotExist(err) {
		return nil
	}
	return err
}

// DeleteUser ist die schaerfste Stelle des Pfadbaus (os.RemoveAll): ohne die
// Kennungspruefung wuerde eine Traversal-Kennung hier ein FREMDES Verzeichnis
// loeschen.
func (s *Store) DeleteUser(id string) error {
	if !ValidUserID(id) {
		return ErrInvalidUserID
	}
	dir := s.UserDir(id)
	return os.RemoveAll(dir)
}

// --- Datenexport nach DSGVO Art. 20 (Issue #2270) ---------------------------
//
// Die Erlaubnisliste steht bewusst HIER im Produktivcode und wird vom Test
// NICHT importiert (internal/handler/data_export_test.go fuehrt eine eigene
// Erwartungsliste). Teilten sich beide eine Konstante, spiegelte der Test nur
// die Annahme des Codes zurueck und ein entfernter Eintrag bliebe gruen.
//
// Erlaubnisliste statt Sperrliste: ein durchgelassenes Geheimnis ist der
// teurere Fehler als eine vergessene Datenart. Die Gegenrichtung (eine neue
// Datenart faellt still aus dem Export) bewacht der Drift-Test.

// exportErlaubteDateienExakt — Vergleich auf Gleichheit, kein Praefix.
var exportErlaubteDateienExakt = []string{
	"user.json", // wird gefiltert ausgeliefert, s. exportFilterUserJSON
	"groups.json",
	"metric_presets.json",
	"alert_log.json",
	"briefing_log.json",
	"pending_briefings.json",
	"briefing_slots.json",
	"briefing_anchor.json",
	"throttle_state.json",
	// Altbestand aus src/services/throttle_store.py:31-33: Vorgaenger-Dateien,
	// die bei Nutzern aus aelteren Staenden noch im Ordner liegen.
	"alert_throttle.json",
	"compare_alert_throttle.json",
	"radar_alert_throttle.json",
}

// exportErlaubteOrdner — Vergleich auf Praefix, der Inhalt wandert vollstaendig
// mit. briefings/ traegt Trips, Compare-Presets und Subscriptions in EINEM
// Ordner; der Briefing-Fingerabdruck wird daraus berechnet und hat keine
// eigene Datei.
var exportErlaubteOrdner = []string{
	"locations/",
	"gpx/",
	"weather_snapshots/",
	"compare_weather_snapshots/",
	"briefings/",
	"alert_state/",
}

// exportGeheimnisFelder fliegen aus der ausgelieferten user.json. Die uebrigen
// Profilfelder bleiben unangetastet — deshalb Feld-Entfernung auf der
// generischen Map statt einer handgepflegten Positivliste, die bei jedem neuen
// Profilfeld still veralten wuerde.
var exportGeheimnisFelder = []string{"password_hash", "passkey_credentials"}

// ExportUser schreibt die exportfaehigen Daten des Nutzers als ZIP-Archiv
// direkt in w. Durchgereicht statt gepuffert: der Speicherbedarf bleibt
// unabhaengig von der Datenmenge des Nutzers.
//
// Bewusst hingenommen (Spec Known Limitations b): Bricht das Packen mitten
// drin ab, ist der Erfolgs-Statuscode bereits gesendet und die Uebertragung
// endet mit einem unvollstaendigen Archiv. Das ist dem stillen Teilexport mit
// vorgetaeuschter Vollstaendigkeit vorgezogen.
//
// id ist die Kennung aus dem Auth-Kontext, nicht s.UserID: der Aufrufer haelt
// den Wurzel-Store (Voreinstellung "default"), UserDir(id) ist die eine
// Pfad-Engstelle.
func (s *Store) ExportUser(id string, w io.Writer) error {
	if !ValidUserID(id) {
		return ErrInvalidUserID
	}
	zw := zip.NewWriter(w)
	if err := exportWalkUserDir(s.UserDir(id), zw); err != nil {
		zw.Close()
		return err
	}
	// Close schreibt das zentrale Verzeichnis — ohne diesen Aufruf ist das
	// Archiv nicht lesbar.
	return zw.Close()
}

func exportWalkUserDir(base string, zw *zip.Writer) error {
	err := filepath.WalkDir(base, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		// Nur echte Dateien wandern mit. filepath.WalkDir FOLGT Verweisen
		// nicht, meldet sie aber als Nicht-Ordner — os.Open/os.ReadFile beim
		// Packen folgen ihnen sehr wohl. Ein Verweis im Nutzerordner zoege
		// damit unter unauffaelligem, erlaubtem Namen fremde Nutzerdaten oder
		// Dateien ausserhalb des Datenbaums ins Archiv. d.Type() stammt aus
		// dem readdir-Eintrag und hat lstat-Semantik: es misst den Verweis
		// selbst, niemals sein Ziel. Nachweis:
		// internal/handler/data_export_test.go,
		// TestExportFolgtKeinemVerweisAusDemNutzerordner.
		if !d.Type().IsRegular() {
			return nil
		}
		rel, rerr := filepath.Rel(base, p)
		if rerr != nil {
			return rerr
		}
		name := filepath.ToSlash(rel)
		if !exportNameIstSicher(name) || !exportIstErlaubt(name) {
			return nil
		}
		return exportSchreibeEintrag(zw, name, p)
	})
	// Ein Nutzer ohne angelegtes Verzeichnis liefert ein leeres, aber gueltiges
	// Archiv statt eines Fehlers.
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	return nil
}

// exportNameIstSicher haelt jeden Archiv-Eintragsnamen relativ zum
// Nutzerordner. ValidUserID/pathsafe.go schuetzen nur die Nutzerordner-Ebene;
// Entitaets-Dateinamen innerhalb des Ordners durchlaufen diese Pruefung nicht.
// Der Vergleich laeuft ueber Pfad-SEGMENTE — ein Dateiname wie "..evil.json"
// ist legitim, nur ".." als eigenes Segment ist es nicht.
func exportNameIstSicher(name string) bool {
	if name == "" || name == "." || strings.HasPrefix(name, "/") || filepath.IsAbs(name) {
		return false
	}
	if strings.Contains(name, `\`) {
		return false
	}
	for _, seg := range strings.Split(name, "/") {
		if seg == ".." {
			return false
		}
	}
	return true
}

func exportIstErlaubt(name string) bool {
	for _, f := range exportErlaubteDateienExakt {
		if name == f {
			return true
		}
	}
	for _, d := range exportErlaubteOrdner {
		if strings.HasPrefix(name, d) {
			return true
		}
	}
	return false
}

func exportSchreibeEintrag(zw *zip.Writer, name, path string) error {
	if name == "user.json" {
		raw, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		gefiltert, err := exportFilterUserJSON(raw)
		if err != nil {
			return err
		}
		f, err := zw.Create(name)
		if err != nil {
			return err
		}
		_, err = f.Write(gefiltert)
		return err
	}
	src, err := os.Open(path)
	if err != nil {
		return err
	}
	defer src.Close()
	f, err := zw.Create(name)
	if err != nil {
		return err
	}
	_, err = io.Copy(f, src)
	return err
}

func exportFilterUserJSON(raw []byte) ([]byte, error) {
	var felder map[string]interface{}
	if err := json.Unmarshal(raw, &felder); err != nil {
		return nil, err
	}
	for _, k := range exportGeheimnisFelder {
		delete(felder, k)
	}
	return json.MarshalIndent(felder, "", "  ")
}

func (s *Store) UserExists(id string) bool {
	if !ValidUserID(id) {
		return false
	}
	path := filepath.Join(s.UserDir(id), "user.json")
	_, err := os.Stat(path)
	return err == nil
}

// FindUserByOAuthSub searches for a user matching both OAuthProvider and OAuthSub.
// Returns (nil, nil) when no matching user exists.
func (s *Store) FindUserByOAuthSub(provider, sub string) (*model.User, error) {
	ids, err := s.ListUserIDs()
	if err != nil {
		return nil, err
	}
	for _, id := range ids {
		u, err := s.LoadUser(id)
		if err != nil || u == nil {
			continue
		}
		if u.OAuthProvider == provider && u.OAuthSub == sub {
			return u, nil
		}
	}
	return nil, nil
}

// FindUserByEmail searches all users for one whose Email field matches the given
// address (case-insensitive). Returns (nil, nil) if no match found.
func (s *Store) FindUserByEmail(email string) (*model.User, error) {
	if strings.TrimSpace(email) == "" {
		return nil, nil
	}
	ids, err := s.ListUserIDs()
	if err != nil {
		return nil, err
	}
	for _, id := range ids {
		u, err := s.LoadUser(id)
		if err != nil || u == nil {
			continue
		}
		if strings.EqualFold(u.Email, strings.TrimSpace(email)) {
			return u, nil
		}
	}
	return nil, nil
}

// FindUserByTelegramChatID searches all users for one whose TelegramChatID
// matches exactly (Chat-IDs sind numerisch — kein EqualFold). Returns
// (nil, nil) if no match found or if chatID is empty: ein leeres Feld ist
// keine Verknüpfung. Test-Nutzer (model.IsTestUserID) werden übersprungen —
// Issue #1013 hält fest, dass ein echter Nutzer gegen die Fixture gewinnt,
// sonst könnte sich der PO auf Staging nicht mehr verbinden, sobald
// tg-live-e2e dieselbe Chat-ID trägt. Issue #2141.
func (s *Store) FindUserByTelegramChatID(chatID string) (*model.User, error) {
	if strings.TrimSpace(chatID) == "" {
		return nil, nil
	}
	ids, err := s.ListUserIDs()
	if err != nil {
		return nil, err
	}
	for _, id := range ids {
		if model.IsTestUserID(id) {
			continue
		}
		u, err := s.LoadUser(id)
		if err != nil || u == nil {
			continue
		}
		if u.TelegramChatID == chatID {
			return u, nil
		}
	}
	return nil, nil
}
