package handler

// TDD RED — Issue #2270: Datenexport nach DSGVO Art. 20.
// Spec: docs/specs/modules/user_data_export.md (AC-1 … AC-11; AC-12 ist
// Frontend/E2E und gehoert nicht in diese Datei).
//
// ExportUserDataHandler existiert noch nicht -> das Paket kompiliert nicht ->
// ALLE Tests dieser Datei sind ROT. Die Produktivdateien daneben
// (internal/store/user.go, internal/handler/data_export.go,
// internal/router/router.go) bleiben in Phase 5 bewusst gesperrt
// (openspec.yaml, strict_code_gate) — deshalb keine Stubs.
//
// NICHT in internal/handler/export_test.go schreiben: die existiert bereits
// und traegt das Go-Idiom "Paket-Interna fuer Tests" (ResetOTPStoreForTest).

import (
	"archive/zip"
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// --- Erwartungs- und Ausnahmelisten DES TESTS -------------------------------
//
// Diese Listen sind BEWUSST eigene Konstanten dieser Testdatei und ausdruecklich
// NICHT dieselbe Variable wie die Erlaubnisliste der Umsetzung in
// internal/store/user.go. Teilten sich beide eine Quelle, spiegelte der Test nur
// die Annahme des Codes zurueck und bewachte nichts: ein aus der Erlaubnisliste
// entfernter Eintrag bliebe gruen. Die Trennung ist die Vorbedingung dafuer,
// dass die Mutations-Gegenprobe aus Spec AC-8 ueberhaupt etwas messen kann.
// Beleg der Eintraege: docs/context/feat-2270-datenexport.md, Tabellen
// "Kernbefund" und "Die Erlaubnisliste".

var exportErwarteteDateien = []string{
	"user.json",
	"groups.json",
	"metric_presets.json",
	"alert_log.json",
	"briefing_log.json",
	"pending_briefings.json",
	"briefing_slots.json",
	"briefing_anchor.json",
	"throttle_state.json",
	// Altbestand aus src/services/throttle_store.py:31-33 (Spec AC-9).
	"alert_throttle.json",
	"compare_alert_throttle.json",
	"radar_alert_throttle.json",
}

var exportErwarteteOrdner = []string{
	"locations/",
	"gpx/",
	"weather_snapshots/",
	"compare_weather_snapshots/",
	"briefings/",
	"alert_state/",
}

// Begruendete Ausnahmen: Geheimnisse (exakter Vergleich — ein kuenftiges
// email_verification_v2.json soll die Drift-Klammer melden, nicht still
// durchrutschen) und Betriebsdaten (Praefixvergleich).
var exportAusnahmeDateien = []string{
	"sessions.json",
	"password_reset.json",
	"email_verification.json",
}

var exportAusnahmeOrdner = []string{
	"alert_input/",
	"diagnostics/",
}

// Reste des atomaren Schreibens (src/services/throttle_store.py:154).
var exportAusnahmeMuster = []string{".throttle_state_*.tmp"}

// exportAusnahmeMarkerJePfad koppelt jeden Ausnahme-Pfad des Vollbild-Fixtures
// an seinen Markerwert. Ohne diese Kopplung waere die Abwesenheitspruefung in
// AC-7 selbst-entwertend: aendert jemand einen Marker im Seeder, sucht die
// Pruefung eine Zeichenkette, die niemand mehr schreibt — nicht gefunden, Test
// gruen, Wache still weg. Der Test liest deshalb ZUERST die Fixture-Datei von
// der Platte und belegt, dass der Marker dort wirklich steht.
var exportAusnahmeMarkerJePfad = map[string]string{
	"sessions.json":                      "MARKER-voll-sessions-3a71",
	"password_reset.json":                "MARKER-voll-passwordreset-8c20",
	"email_verification.json":            "MARKER-voll-emailverification-5b93",
	"alert_input/2026-09-01.json":        "MARKER-voll-alertinput-1f04",
	"diagnostics/track_resolution.jsonl": "MARKER-voll-diagnostics-1f04",
	".throttle_state_ab12cd.tmp":         "MARKER-voll-throttletmp-1f04",
}

// --- Hilfsmittel ------------------------------------------------------------

// exportRootStore liefert einen Store, der — wie in Produktion (router.Deps.Store
// traegt cfg.UserID, Voreinstellung "default") — auf "default" wurzelt.
//
// Absicht: eine Umsetzung, die den Auth-Kontext ignoriert und schlicht s.UserID
// verwendet, liefert dann NICHT Alices Daten aus und faellt auf. Ein auf "alice"
// gewurzelter Test-Store wuerde genau diese Verfaelschung durchwinken.
func exportRootStore(t *testing.T) *store.Store {
	t.Helper()
	return store.New(t.TempDir(), "default")
}

// exportRequest stellt die Anfrage an den Handler. userID == "" heisst: kein
// Anmelde-Kontext gesetzt (Spec AC-3).
func exportRequest(t *testing.T, root *store.Store, userID, query string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, "/api/auth/export"+query, nil)
	if userID != "" {
		req = withUserCtx(req, userID)
	}
	w := httptest.NewRecorder()
	ExportUserDataHandler(root).ServeHTTP(w, req)
	return w
}

// exportUnzip entpackt die Antwort in map[Eintragsname]Inhalt.
func exportUnzip(t *testing.T, w *httptest.ResponseRecorder) map[string]string {
	t.Helper()
	if w.Code != http.StatusOK {
		t.Fatalf("erwartet HTTP 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	body := w.Body.Bytes()
	zr, err := zip.NewReader(bytes.NewReader(body), int64(len(body)))
	if err != nil {
		t.Fatalf("Antwort ist kein lesbares ZIP-Archiv (%d Bytes): %v", len(body), err)
	}
	out := map[string]string{}
	for _, f := range zr.File {
		if f.FileInfo().IsDir() {
			continue
		}
		rc, err := f.Open()
		if err != nil {
			t.Fatalf("Archiv-Eintrag %q nicht lesbar: %v", f.Name, err)
		}
		b, err := io.ReadAll(rc)
		rc.Close()
		if err != nil {
			t.Fatalf("Archiv-Eintrag %q nicht lesbar: %v", f.Name, err)
		}
		out[f.Name] = string(b)
	}
	return out
}

// exportInhalt klebt alle Archivinhalte zusammen. Geheimnis- und
// Fremddaten-Nachweise suchen im INHALT, nicht in der Namensliste.
func exportInhalt(entries map[string]string) string {
	var sb strings.Builder
	for _, v := range entries {
		sb.WriteString(v)
		sb.WriteString("\n")
	}
	return sb.String()
}

func exportNamen(entries map[string]string) []string {
	names := make([]string, 0, len(entries))
	for k := range entries {
		names = append(names, k)
	}
	return names
}

// exportSchreibeRoh legt eine Datei direkt an. Verwendet fuer alle Ablagen, fuer
// die es KEINEN Go-Schreiber gibt: die Python-seitigen Dateien
// (briefing_slots.json, briefing_anchor.json, throttle_state.json, alert_state/,
// compare_weather_snapshots/, gpx/, weather_snapshots/, alert_input/,
// diagnostics/, die drei Altbestand-Throttle-Dateien) sowie alert_log.json,
// briefing_log.json und pending_briefings.json — der Go-Store hat dort nur
// Leser (log.go, pending_briefings.go), keinen Schreiber.
func exportSchreibeRoh(t *testing.T, root *store.Store, uid, rel, inhalt string) {
	t.Helper()
	p := filepath.Join(root.UserDir(uid), filepath.FromSlash(rel))
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(p, []byte(inhalt), 0o600); err != nil {
		t.Fatal(err)
	}
}

// exportSeedBasis legt Grunddaten ueber die Produktiv-Schreiber an.
func exportSeedBasis(t *testing.T, root *store.Store, uid, tag string) {
	t.Helper()
	s := root.WithUser(uid)
	if err := s.SaveUser(model.User{
		ID:          uid,
		Email:       uid + "@example.invalid",
		DisplayName: "MARKER-" + tag + "-display",
		CreatedAt:   time.Now().UTC(),
	}); err != nil {
		t.Fatal(err)
	}
	if err := s.ProvisionUserDirs(uid); err != nil {
		t.Fatal(err)
	}
	if err := s.SaveLocation(model.Location{
		ID: uid + "-ort", Name: "MARKER-" + tag + "-ort", Lat: 47.1, Lon: 11.2,
	}); err != nil {
		t.Fatal(err)
	}
	trip := model.Trip{ID: uid + "-tour", Name: "MARKER-" + tag + "-tour"}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatal(err)
	}
}

// exportSeedVollbild legt je ein Exemplar JEDER in der Analyse belegten
// Datenart an (docs/context/feat-2270-datenexport.md).
func exportSeedVollbild(t *testing.T, root *store.Store, uid string) {
	t.Helper()
	s := root.WithUser(uid)
	must := func(err error) {
		t.Helper()
		if err != nil {
			t.Fatal(err)
		}
	}

	// --- Go-Store-Schreiber -------------------------------------------------
	must(s.SaveUser(model.User{
		ID:                 uid,
		Email:              uid + "@example.invalid",
		DisplayName:        "MARKER-voll-display-1f04",
		Tier:               "pro",
		MailTo:             "MARKER-voll-mailto-1f04@example.invalid",
		SmsTo:              "MARKER-voll-smsto-1f04",
		TelegramChatID:     "MARKER-voll-tg-1f04",
		PasswordHash:       "MARKER-voll-pwhash-9d21",
		PasskeyCredentials: []model.WebAuthnCredential{{AttestationType: "MARKER-voll-passkey-4e70"}},
		CreatedAt:          time.Now().UTC(),
	}))
	must(s.ProvisionUserDirs(uid))
	must(s.SaveLocation(model.Location{
		ID: "voll-ort", Name: "MARKER-voll-ort-1f04", Lat: 47.1, Lon: 11.2,
	}))
	must(s.SaveGroup(model.Group{ID: "voll-gruppe", Name: "MARKER-voll-gruppe-1f04"}))
	must(s.SaveMetricPresets([]model.MetricPreset{{
		ID: "voll-preset", Name: "MARKER-voll-metricpreset-1f04", CreatedAt: time.Now().UTC(),
	}}))

	// briefings/ traegt VIER Sorten in EINEM Ordner. Drei davon haben eine
	// eigene Datei; der Fingerabdruck (store.BriefingFingerprint) wird aus den
	// Bytes von briefings/<id>.json BERECHNET und liegt nicht als eigene Datei
	// auf der Platte — er wandert mit der Trip-Datei mit.
	trip := model.Trip{ID: "voll-tour", Name: "MARKER-voll-tour-1f04"}
	must(s.SaveTrip(&trip))
	must(s.SaveComparePreset(model.ComparePreset{
		ID: "voll-vergleich", Name: "MARKER-voll-vergleich-1f04", UserID: uid,
	}))
	var sub model.BriefingSubscription
	must(json.Unmarshal([]byte(`{"id":"voll-abo","kind":"subscription","note":"MARKER-voll-abo-1f04"}`), &sub))
	must(s.SaveBriefing(&sub))

	// Geheimnisse — ueber die Produktiv-Schreiber, damit die Ausnahmeliste
	// gegen den echten Bestand geprueft wird.
	must(s.AddSession(uid, "MARKER-voll-sessions-3a71"))
	must(s.SaveResetToken(uid, model.PasswordResetToken{
		TokenHash: "MARKER-voll-passwordreset-8c20", ExpiresAt: time.Now().Add(time.Hour),
	}))
	must(s.SaveVerificationToken(uid, model.EmailVerificationToken{
		TokenHash: "MARKER-voll-emailverification-5b93", ExpiresAt: time.Now().Add(time.Hour),
	}))

	// --- Ohne Go-Schreiber: direkt auf die Platte ---------------------------
	// Go-Store hat nur Leser (log.go:23,63; pending_briefings.go:30).
	exportSchreibeRoh(t, root, uid, "alert_log.json",
		`{"entries":[{"entity_id":"MARKER-voll-alertlog-1f04","entity_type":"trip","sent_at":"2026-09-01T06:00:00Z","changes_count":1,"severity":"hoch"}]}`)
	exportSchreibeRoh(t, root, uid, "briefing_log.json",
		`{"entries":[{"trip_id":"MARKER-voll-briefinglog-1f04","kind":"morning","sent_at":"2026-09-01T06:00:00Z","channels":["email"]}]}`)
	exportSchreibeRoh(t, root, uid, "pending_briefings.json",
		`{"entries":[{"trip_id":"MARKER-voll-pending-1f04","report_type":"morning","date":"2026-09-01","slot_hour":6,"failed_segment_ids":[],"attempts":1,"created_at":"2026-09-01T06:00:00Z"}]}`)

	// Python-Kern (src/services/*.py) — kein Go-Schreiber.
	exportSchreibeRoh(t, root, uid, "briefing_slots.json", `{"marker":"MARKER-voll-slots-1f04"}`)
	exportSchreibeRoh(t, root, uid, "briefing_anchor.json", `{"marker":"MARKER-voll-anchor-1f04"}`)
	exportSchreibeRoh(t, root, uid, "throttle_state.json", `{"marker":"MARKER-voll-throttle-1f04"}`)
	exportSchreibeRoh(t, root, uid, "alert_throttle.json", `{"marker":"MARKER-voll-throttle-alt-trip-1f04"}`)
	exportSchreibeRoh(t, root, uid, "compare_alert_throttle.json", `{"marker":"MARKER-voll-throttle-alt-compare-1f04"}`)
	exportSchreibeRoh(t, root, uid, "radar_alert_throttle.json", `{"marker":"MARKER-voll-throttle-alt-radar-1f04"}`)
	exportSchreibeRoh(t, root, uid, "alert_state/voll-tour.json", `{"marker":"MARKER-voll-alertstate-1f04"}`)
	exportSchreibeRoh(t, root, uid, "compare_weather_snapshots/voll-vergleich.json", `{"marker":"MARKER-voll-comparesnapshot-1f04"}`)
	exportSchreibeRoh(t, root, uid, "weather_snapshots/voll-tour.json", `{"marker":"MARKER-voll-snapshot-1f04"}`)
	// gpx/ ist XML, nicht JSON — genau der Grund fuer ZIP statt einem
	// JSON-Dokument (api/routers/gpx.py schreibt hier).
	exportSchreibeRoh(t, root, uid, "gpx/voll-track.gpx", `<gpx><name>MARKER-voll-gpx-1f04</name></gpx>`)

	// Betriebsdaten — auf der begruendeten Ausnahmeliste.
	exportSchreibeRoh(t, root, uid, "alert_input/2026-09-01.json", `{"marker":"MARKER-voll-alertinput-1f04"}`)
	exportSchreibeRoh(t, root, uid, "diagnostics/track_resolution.jsonl", `{"marker":"MARKER-voll-diagnostics-1f04"}`)
	// Rest des atomaren Schreibens (throttle_store.py:154).
	exportSchreibeRoh(t, root, uid, ".throttle_state_ab12cd.tmp", `{"marker":"MARKER-voll-throttletmp-1f04"}`)
}

// exportFixturePfade laeuft ueber das angelegte Nutzerverzeichnis und liefert
// alle Dateien relativ zum Nutzerordner (mit "/" als Trenner).
func exportFixturePfade(t *testing.T, root *store.Store, uid string) []string {
	t.Helper()
	base := root.UserDir(uid)
	var rels []string
	err := filepath.WalkDir(base, func(p string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		rel, rerr := filepath.Rel(base, p)
		if rerr != nil {
			return rerr
		}
		rels = append(rels, filepath.ToSlash(rel))
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	return rels
}

// exportIstAusnahme sagt, ob ein Fixture-Pfad auf der begruendeten
// Ausnahmeliste steht.
func exportIstAusnahme(rel string) bool {
	for _, f := range exportAusnahmeDateien {
		if rel == f {
			return true
		}
	}
	for _, d := range exportAusnahmeOrdner {
		if strings.HasPrefix(rel, d) {
			return true
		}
	}
	for _, m := range exportAusnahmeMuster {
		if ok, _ := path.Match(m, path.Base(rel)); ok {
			return true
		}
	}
	return false
}

// --- AC-1 -------------------------------------------------------------------

func TestExportEnthaeltNurEigeneDaten(t *testing.T) {
	root := exportRootStore(t)
	exportSeedBasis(t, root, "alice", "alice-7f3a")
	exportSeedBasis(t, root, "bob", "bob-2c91")

	w := exportRequest(t, root, "alice", "")
	if ct := w.Header().Get("Content-Type"); !strings.Contains(ct, "zip") {
		t.Errorf("Content-Type erwartet application/zip, bekommen %q", ct)
	}
	inhalt := exportInhalt(exportUnzip(t, w))

	for _, m := range []string{"MARKER-alice-7f3a-display", "MARKER-alice-7f3a-ort", "MARKER-alice-7f3a-tour"} {
		if !strings.Contains(inhalt, m) {
			t.Errorf("eigener Marker %q fehlt im entpackten Archiv", m)
		}
	}
	for _, m := range []string{"MARKER-bob-2c91-display", "MARKER-bob-2c91-ort", "MARKER-bob-2c91-tour"} {
		if strings.Contains(inhalt, m) {
			t.Errorf("FREMDDATEN-LECK: Bobs Marker %q steht im ausgelieferten Archiv", m)
		}
	}
}

// --- AC-2 -------------------------------------------------------------------

func TestExportIgnoriertUserIdParameter(t *testing.T) {
	root := exportRootStore(t)
	exportSeedBasis(t, root, "alice", "alice-7f3a")
	exportSeedBasis(t, root, "bob", "bob-2c91")

	// Faengt die Verfaelschung "Kennung wird aus dem Request-Parameter statt
	// aus dem Auth-Kontext gelesen".
	inhalt := exportInhalt(exportUnzip(t, exportRequest(t, root, "alice", "?user_id=bob")))

	if !strings.Contains(inhalt, "MARKER-alice-7f3a-ort") {
		t.Errorf("Archiv enthaelt Alices Daten nicht, obwohl Alice angemeldet ist")
	}
	if strings.Contains(inhalt, "MARKER-bob-2c91-ort") {
		t.Errorf("FREMDDATEN-LECK: der Parameter user_id=bob hat gewirkt")
	}
}

// --- AC-3 -------------------------------------------------------------------

func TestExportOhneAnmeldungLiefertKeinArchiv(t *testing.T) {
	root := exportRootStore(t)
	// Der Sammelordner "default" wird UEBER DEN STORE befuellt — genau der
	// Ordner, auf den eine leere Kennung aufloest: UserIDFromContext liefert
	// "" (middleware/auth.go:151-154), WithUser("") ist ein No-Op
	// (store/store.go:21-24), Voreinstellung ist "default" (config.go:10).
	// Ohne diese Befuellung waere "Marker fehlt" bei jeder beliebigen leeren
	// Antwort erfuellt und der Nachweis gegenstandslos.
	exportSeedBasis(t, root, "default", "default-5b8e")

	w := exportRequest(t, root, "", "")

	if w.Code != http.StatusUnauthorized {
		t.Errorf("erwartet HTTP 401, bekommen %d", w.Code)
	}
	body := w.Body.Bytes()
	if bytes.HasPrefix(body, []byte("PK\x03\x04")) {
		t.Errorf("es wurde ein ZIP-Archiv ausgeliefert, obwohl kein Anmelde-Kontext vorliegt")
	}
	// Leer ODER fehlerfoermig (JSON, Hausstil analog DeleteAccountHandler) —
	// ein blosses "Marker nicht enthalten" genuegt laut Spec nicht.
	if len(body) > 0 && !json.Valid(body) {
		t.Errorf("Antwortkoerper ist weder leer noch als JSON-Fehler geformt: %q", string(body))
	}
	if strings.Contains(string(body), "MARKER-default-5b8e") {
		t.Errorf("FREMDDATEN-LECK: Marker des Sammelordners default steht in der Antwort")
	}
}

// --- AC-4 -------------------------------------------------------------------

func TestExportEnthaeltKeineGeheimnisse(t *testing.T) {
	root := exportRootStore(t)
	s := root.WithUser("alice")
	exportSeedBasis(t, root, "alice", "alice-7f3a")

	if err := s.SaveUser(model.User{
		ID:                 "alice",
		Email:              "alice@example.invalid",
		DisplayName:        "MARKER-alice-7f3a-display",
		PasswordHash:       "MARKER-alice-pwhash-9d21",
		PasskeyCredentials: []model.WebAuthnCredential{{AttestationType: "MARKER-alice-passkey-4e70", Label: "MARKER-alice-passkeylabel-4e70"}},
		CreatedAt:          time.Now().UTC(),
	}); err != nil {
		t.Fatal(err)
	}
	if err := s.SaveResetToken("alice", model.PasswordResetToken{
		TokenHash: "MARKER-alice-reset-1a55", ExpiresAt: time.Now().Add(time.Hour),
	}); err != nil {
		t.Fatal(err)
	}
	if err := s.SaveVerificationToken("alice", model.EmailVerificationToken{
		TokenHash: "MARKER-alice-verify-6b33", ExpiresAt: time.Now().Add(time.Hour),
	}); err != nil {
		t.Fatal(err)
	}
	if err := s.AddSession("alice", "MARKER-alice-session-8c04"); err != nil {
		t.Fatal(err)
	}

	inhalt := exportInhalt(exportUnzip(t, exportRequest(t, root, "alice", "")))

	// Positivkontrolle: das Archiv ist nicht einfach leer.
	if !strings.Contains(inhalt, "MARKER-alice-7f3a-display") {
		t.Fatalf("Positivkontrolle fehlgeschlagen — das Archiv traegt keine Nutzdaten")
	}
	for _, geheim := range []string{
		"MARKER-alice-pwhash-9d21",
		"MARKER-alice-passkey-4e70",
		"MARKER-alice-passkeylabel-4e70",
		"MARKER-alice-reset-1a55",
		"MARKER-alice-verify-6b33",
		"MARKER-alice-session-8c04",
	} {
		if strings.Contains(inhalt, geheim) {
			t.Errorf("GEHEIMNIS-LECK: %q steht im entpackten Archivinhalt", geheim)
		}
	}
}

// --- AC-5 -------------------------------------------------------------------

func TestExportUserJsonEnthaeltProfilfelderOhneGeheimnisse(t *testing.T) {
	root := exportRootStore(t)
	s := root.WithUser("alice")
	if err := s.ProvisionUserDirs("alice"); err != nil {
		t.Fatal(err)
	}
	if err := s.SaveUser(model.User{
		ID:                 "alice",
		Email:              "alice@example.invalid",
		DisplayName:        "Alice Beispiel",
		Tier:               "pro",
		MailTo:             "alice-mail@example.invalid",
		SmsTo:              "+430000000",
		TelegramChatID:     "123456",
		PasswordHash:       "MARKER-alice-pwhash-9d21",
		PasskeyCredentials: []model.WebAuthnCredential{{AttestationType: "MARKER-alice-passkey-4e70"}},
		CreatedAt:          time.Now().UTC(),
	}); err != nil {
		t.Fatal(err)
	}

	archiv := exportUnzip(t, exportRequest(t, root, "alice", ""))
	roh, ok := archiv["user.json"]
	if !ok {
		t.Fatalf("user.json fehlt im Archiv — vorhandene Eintraege: %v", exportNamen(archiv))
	}
	var felder map[string]interface{}
	if err := json.Unmarshal([]byte(roh), &felder); err != nil {
		t.Fatalf("exportierte user.json ist kein gueltiges JSON: %v", err)
	}
	for _, k := range []string{"id", "email", "created_at", "mail_to", "sms_to", "telegram_chat_id", "display_name", "tier"} {
		if _, da := felder[k]; !da {
			t.Errorf("Profilfeld %q fehlt in der exportierten user.json", k)
		}
	}
	for _, k := range []string{"password_hash", "passkey_credentials"} {
		if _, da := felder[k]; da {
			t.Errorf("GEHEIMNIS-LECK: Feld %q steht in der exportierten user.json", k)
		}
	}
}

// --- AC-6 -------------------------------------------------------------------

func TestExportVollbildOhneDrift(t *testing.T) {
	root := exportRootStore(t)
	exportSeedVollbild(t, root, "alice")

	angelegt := exportFixturePfade(t, root, "alice")
	if len(angelegt) < 20 {
		t.Fatalf("Vollbild-Fixture ist zu duenn (%d Eintraege) — der Drift-Nachweis waere gegenstandslos: %v", len(angelegt), angelegt)
	}

	archiv := exportUnzip(t, exportRequest(t, root, "alice", ""))

	for _, rel := range angelegt {
		if _, drin := archiv[rel]; drin {
			continue
		}
		if exportIstAusnahme(rel) {
			continue
		}
		t.Errorf("DRIFT: %q ist weder im ausgelieferten Archiv noch auf der begruendeten Ausnahmeliste", rel)
	}
}

// --- AC-7 -------------------------------------------------------------------

func TestExportAusnahmelisteIstVollstaendigBelegt(t *testing.T) {
	root := exportRootStore(t)
	exportSeedVollbild(t, root, "alice")
	angelegt := exportFixturePfade(t, root, "alice")

	// Teil 1 — kein Totholz: jeder Ausnahme-Eintrag hat ein Gegenstueck im
	// Vollbild-Fixture. Laeuft bei JEDEM Lauf, nicht nur bei einer gedachten
	// Aenderung.
	pruefe := func(bezeichnung string, treffer func(string) bool) {
		t.Helper()
		for _, rel := range angelegt {
			if treffer(rel) {
				return
			}
		}
		t.Errorf("TOTHOLZ: Ausnahme %q hat kein Gegenstueck im Vollbild-Fixture", bezeichnung)
	}
	for _, f := range exportAusnahmeDateien {
		f := f
		pruefe(f, func(rel string) bool { return rel == f })
	}
	for _, d := range exportAusnahmeOrdner {
		d := d
		pruefe(d, func(rel string) bool { return strings.HasPrefix(rel, d) })
	}
	for _, m := range exportAusnahmeMuster {
		m := m
		pruefe(m, func(rel string) bool { ok, _ := path.Match(m, path.Base(rel)); return ok })
	}

	// Teil 2 — die Ausnahmen wirken auch tatsaechlich: kein Markerwert einer
	// Ausnahme-Datei taucht im AUSGELIEFERTEN Archiv auf. Ohne diesen Teil
	// laese der Test nur die Fixture und die eigene Liste, waere vom Export
	// voellig unberuehrt und schon in der RED-Phase gruen.
	inhalt := exportInhalt(exportUnzip(t, exportRequest(t, root, "alice", "")))
	for rel, marker := range exportAusnahmeMarkerJePfad {
		roh, err := os.ReadFile(filepath.Join(root.UserDir("alice"), filepath.FromSlash(rel)))
		if err != nil {
			t.Fatalf("Ausnahme-Fixture %q liegt nicht auf der Platte: %v", rel, err)
		}
		// Positivkontrolle: prueft, ob die Pruefung ueberhaupt misst.
		if !strings.Contains(string(roh), marker) {
			t.Fatalf("Marker %q steht nicht in der Fixture-Datei %q — die Abwesenheitspruefung "+
				"suchte eine Zeichenkette, die niemand schreibt, und bewachte nichts", marker, rel)
		}
		if strings.Contains(inhalt, marker) {
			t.Errorf("Ausnahme wirkt nicht: Marker %q aus %q steht im ausgelieferten Archiv", marker, rel)
		}
	}
}

// --- AC-8 -------------------------------------------------------------------

func TestExportErlaubnislisteWirdUnabhaengigBewacht(t *testing.T) {
	// AC-8 wird in GREEN scharf: erst wenn internal/store/user.go eine eigene
	// Erlaubnisliste traegt, kann die Mutations-Gegenprobe (einen Eintrag
	// daraus entfernen) diesen Test rot faerben. Vorbedingung dafuer ist die
	// Trennung der Listen — exportErwarteteDateien/exportErwarteteOrdner
	// stehen ausschliesslich hier und werden vom Produktivcode nie importiert.
	root := exportRootStore(t)
	exportSeedVollbild(t, root, "alice")
	archiv := exportUnzip(t, exportRequest(t, root, "alice", ""))

	for _, datei := range exportErwarteteDateien {
		if _, drin := archiv[datei]; !drin {
			t.Errorf("Erlaubnislisten-Eintrag %q fehlt im ausgelieferten Archiv (vorhanden: %v)", datei, exportNamen(archiv))
		}
	}
	for _, ordner := range exportErwarteteOrdner {
		gefunden := false
		for name := range archiv {
			if strings.HasPrefix(name, ordner) {
				gefunden = true
				break
			}
		}
		if !gefunden {
			t.Errorf("Erlaubnislisten-Ordner %q ist im ausgelieferten Archiv nicht vertreten", ordner)
		}
	}
}

// --- AC-9 -------------------------------------------------------------------

func TestExportEnthaeltAltbestandDerThrottleDateien(t *testing.T) {
	root := exportRootStore(t)
	exportSeedBasis(t, root, "alice", "alice-7f3a")
	// throttle_store.py:31-33 — Vorgaenger-Dateien, die bei Nutzern aus
	// aelteren Staenden noch im Ordner liegen. Kein Go-Schreiber.
	exportSchreibeRoh(t, root, "alice", "alert_throttle.json", `{"marker":"MARKER-alt-trip-3311"}`)
	exportSchreibeRoh(t, root, "alice", "compare_alert_throttle.json", `{"marker":"MARKER-alt-compare-3312"}`)
	exportSchreibeRoh(t, root, "alice", "radar_alert_throttle.json", `{"marker":"MARKER-alt-radar-3313"}`)

	inhalt := exportInhalt(exportUnzip(t, exportRequest(t, root, "alice", "")))
	for _, m := range []string{"MARKER-alt-trip-3311", "MARKER-alt-compare-3312", "MARKER-alt-radar-3313"} {
		if !strings.Contains(inhalt, m) {
			t.Errorf("Altbestand-Marker %q fehlt im entpackten Archiv", m)
		}
	}
}

// --- AC-10 ------------------------------------------------------------------

func TestExportEnthaeltAlleBriefingSorten(t *testing.T) {
	root := exportRootStore(t)
	s := root.WithUser("alice")
	exportSeedBasis(t, root, "alice", "alice-7f3a")

	trip := model.Trip{ID: "sorte-tour", Name: "MARKER-sorte-tour-a1"}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatal(err)
	}
	if err := s.SaveComparePreset(model.ComparePreset{
		ID: "sorte-vergleich", Name: "MARKER-sorte-vergleich-a2", UserID: "alice",
	}); err != nil {
		t.Fatal(err)
	}
	var sub model.BriefingSubscription
	if err := json.Unmarshal([]byte(`{"id":"sorte-abo","kind":"subscription","note":"MARKER-sorte-abo-a3"}`), &sub); err != nil {
		t.Fatal(err)
	}
	if err := s.SaveBriefing(&sub); err != nil {
		t.Fatal(err)
	}

	archiv := exportUnzip(t, exportRequest(t, root, "alice", ""))

	// Nur der briefings/-Anteil zaehlt — die Sorten liegen alle dort.
	var briefingsInhalt strings.Builder
	for name, inh := range archiv {
		if strings.HasPrefix(name, "briefings/") {
			briefingsInhalt.WriteString(inh)
			briefingsInhalt.WriteString("\n")
		}
	}
	for _, m := range []string{"MARKER-sorte-tour-a1", "MARKER-sorte-vergleich-a2", "MARKER-sorte-abo-a3"} {
		if !strings.Contains(briefingsInhalt.String(), m) {
			t.Errorf("Briefing-Sorte mit Marker %q fehlt im briefings/-Anteil des Archivs", m)
		}
	}
	// Die vierte "Sorte" — der Fingerabdruck — hat KEINE eigene Datei:
	// store.BriefingFingerprint (briefing_fingerprint.go:27) berechnet sha256
	// ueber die Bytes von briefings/<id>.json. Sie wandert mit der Trip-Datei
	// mit; ein eigener Nachweis waere eine erfundene Datei.
	if _, drin := archiv["briefings/sorte-tour.json"]; !drin {
		t.Errorf("briefings/sorte-tour.json fehlt — Grundlage des Fingerabdrucks nicht exportiert")
	}
}

// --- AC-11 ------------------------------------------------------------------

func TestExportArchivnamenBleibenRelativ(t *testing.T) {
	root := exportRootStore(t)
	exportSeedBasis(t, root, "alice", "alice-7f3a")

	// SCHWACHE STELLE, bewusst so belassen: diese Pruefung kann die in AC-11
	// gedachte Bedrohung nicht real herstellen (Adversary-Finding F001). Die
	// herstellbaren Fassungen derselben Bedrohung — ein Eintrag, der AUS dem
	// Nutzerordner HERAUS fuehrt — pruefen weiter unten
	// TestExportFolgtKeinemVerweisAusDemNutzerordner (Symlink) und
	// TestExportLiefertKeinenAusbruchsnamenAn (Backslash-Eintragsname).
	//
	// Konstruierbarkeitsgrenze: ein Dateiname auf Linux kann NICHT "/"
	// enthalten und nicht ".." als eigenes Segment sein. Was geht — und was
	// ValidEntityID (pathsafe.go:41) ablehnt, also nur ueber os.WriteFile
	// entsteht — ist ein fuehrender Doppelpunkt-Punkt-Name. Kein Go-Schreiber
	// legt so etwas an; der Python-Kern und Altbestaende koennen es.
	exportSchreibeRoh(t, root, "alice", "locations/..evil-1d90.json", `{"marker":"MARKER-traversal-1d90"}`)

	archiv := exportUnzip(t, exportRequest(t, root, "alice", ""))
	if len(archiv) == 0 {
		t.Fatalf("Archiv ist leer — die Invariante haette nichts zu pruefen")
	}
	// Invariante ueber ALLE Eintraege, nicht nur den manipulierten.
	for name := range archiv {
		if strings.HasPrefix(name, "/") || filepath.IsAbs(name) {
			t.Errorf("Archiv-Eintrag %q ist ein absoluter Pfad", name)
		}
		if strings.Contains(name, `\`) {
			t.Errorf("Archiv-Eintrag %q enthaelt einen Windows-Pfadtrenner", name)
		}
		for _, seg := range strings.Split(name, "/") {
			if seg == ".." {
				t.Errorf("Archiv-Eintrag %q enthaelt \"..\" als Pfadsegment", name)
			}
		}
	}
}

// TestExportFolgtKeinemVerweisAusDemNutzerordner ist die herstellbare Fassung
// der Bedrohung, die AC-11 meint (Adversary-Finding F001): ein ".." als eigenes
// Pfadsegment laesst sich auf einem echten Dateisystem nicht als Dateiname
// anlegen — ein SYMLINK, der aus dem Nutzerordner herausfuehrt, sehr wohl.
//
// filepath.WalkDir folgt Verweisen nicht, meldet sie aber als Nicht-Ordner:
// der Eintrag traegt einen unauffaelligen, erlaubten Namen und passiert damit
// Namenssicherung und Erlaubnisliste. Erst os.Open/os.ReadFile beim Packen
// folgt dem Verweis — dort entstuende das Leck. Geprueft wird deshalb am
// ENTPACKTEN Archivinhalt, nicht an der Namensliste.
func TestExportFolgtKeinemVerweisAusDemNutzerordner(t *testing.T) {
	root := exportRootStore(t)
	exportSeedBasis(t, root, "alice", "alice-7f3a")
	exportSeedBasis(t, root, "bob", "bob-9c21")

	// Ziel 1: eine Datei IN Bobs Nutzerordner (fremder Nutzer, gleicher Baum).
	exportSchreibeRoh(t, root, "bob", "locations/bob-geheim.json",
		`{"marker":"MARKER-fremdziel-bob-4e17"}`)
	// Ziel 2: eine Datei ausserhalb des Datenbaums. Eigener Marker statt
	// /etc/passwd — der Nachweis darf nicht von Systemzustand abhaengen.
	aussen := filepath.Join(t.TempDir(), "ausserhalb.json")
	if err := os.WriteFile(aussen, []byte(`{"marker":"MARKER-ausserhalb-8b52"}`), 0o600); err != nil {
		t.Fatal(err)
	}

	// Die Verweise liegen an Stellen, die die Erlaubnisliste tatsaechlich
	// einsammelt (locations/ und gpx/) — sonst prueft der Test nichts.
	aliceDir := root.UserDir("alice")
	verweise := []struct{ von, nach string }{
		{filepath.Join(aliceDir, "locations", "verweis-fremd.json"), filepath.Join(root.UserDir("bob"), "locations", "bob-geheim.json")},
		{filepath.Join(aliceDir, "gpx", "verweis-aussen.json"), aussen},
	}
	for _, l := range verweise {
		if err := os.MkdirAll(filepath.Dir(l.von), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.Symlink(l.nach, l.von); err != nil {
			t.Fatal(err)
		}
	}

	archiv := exportUnzip(t, exportRequest(t, root, "alice", ""))
	inhalt := exportInhalt(archiv)

	// Positivkontrolle ZUERST: ein leeres oder ueber Gebuehr leergeraeumtes
	// Archiv wuerde die Abwesenheitspruefung sonst gratis bestehen.
	if !strings.Contains(inhalt, "MARKER-alice-7f3a-ort") {
		t.Fatalf("Alices eigener Ortsmarker fehlt im Archiv — die Abwesenheitspruefung waere wertlos. Eintraege: %v", exportNamen(archiv))
	}
	if !strings.Contains(inhalt, "MARKER-alice-7f3a-tour") {
		t.Fatalf("Alices eigener Tourmarker fehlt im Archiv — die Abwesenheitspruefung waere wertlos. Eintraege: %v", exportNamen(archiv))
	}

	if strings.Contains(inhalt, "MARKER-fremdziel-bob-4e17") {
		t.Errorf("DATENLECK: der Export ist einem Verweis in Bobs Nutzerordner gefolgt — fremder Inhalt liegt im Archiv. Eintraege: %v", exportNamen(archiv))
	}
	if strings.Contains(inhalt, "MARKER-ausserhalb-8b52") {
		t.Errorf("DATENLECK: der Export ist einem Verweis aus dem Datenbaum heraus gefolgt. Eintraege: %v", exportNamen(archiv))
	}
}

// TestExportLiefertKeinenAusbruchsnamenAn trifft exportNameIstSicher DORT, WO
// SIE WIRKT — im Walk, nicht im Direktaufruf (ein Funktionstest wuerde ein
// entferntes Aufruf-Paar nicht bemerken: Naht gebaut != Naht verdrahtet).
//
// Der konstruierbare Fall ist NICHT "..", sondern der Backslash: auf Linux ist
// er ein voellig legaler Dateinamens-Buchstabe, in einem ZIP-Eintragsnamen aber
// ein Pfadtrenner. Ein Entpacker unter Windows schriebe
// "locations\..\..\fremd\user.json" ausserhalb des Zielordners. Der Name
// entsteht real ueber das Dateisystem und passiert die Erlaubnisliste
// (Praefix "locations/") — nur die Namenssicherung haelt ihn auf.
func TestExportLiefertKeinenAusbruchsnamenAn(t *testing.T) {
	root := exportRootStore(t)
	exportSeedBasis(t, root, "alice", "alice-7f3a")
	exportSchreibeRoh(t, root, "alice", `locations/..\..\fremd\user.json`,
		`{"marker":"MARKER-ausbruchsname-3fa9"}`)

	archiv := exportUnzip(t, exportRequest(t, root, "alice", ""))
	// Positivkontrolle: ein leeres Archiv bestuende die Pruefung sonst gratis.
	if !strings.Contains(exportInhalt(archiv), "MARKER-alice-7f3a-ort") {
		t.Fatalf("Alices eigener Ortsmarker fehlt — die Namenspruefung haette nichts zu pruefen. Eintraege: %v", exportNamen(archiv))
	}
	for name := range archiv {
		if strings.Contains(name, `\`) {
			t.Errorf("Archiv-Eintrag %q traegt einen Backslash — beim Entpacken unter Windows ein Pfadtrenner, der aus dem Zielordner herausfuehrt", name)
		}
	}
}
