package handler

// TDD RED — Onboarding S2: Willkommens-Hinweis und Startklar-Checkliste.
// Spec: docs/specs/modules/onboarding_willkommen_checkliste.md — AC-4, AC-5,
// AC-6, AC-7, AC-12 (Go-Seite).
//
// Zusicherungen:
//   - PUT /api/auth/profile mit NUR `onboarding_dismissed` bzw. NUR
//     `checklist_dismissed` setzt genau dieses Flag ueber den Merge-Setter
//     (mergeUserJSON) — ein unbekanntes Fremdfeld und alle Nachbarfelder der
//     Altdatei bleiben erhalten (kein SaveUser, BUG-DATALOSS-GR221).
//   - GET /api/auth/profile liefert `onboarding_pending`, `onboarding_dismissed`,
//     `checklist_dismissed` IMMER (auch als false), `test_mail_sent_at` nur
//     wenn gesetzt, `first_briefing_at` aus data/users/<id>/first_briefing.json
//     (fehlend oder kaputt = Feld fehlt, nie 500).
//   - Vom Client mitgeschickte `onboarding_pending`, `test_mail_sent_at`,
//     `first_briefing_at` bleiben wirkungslos; nur das Profil des Aufrufers
//     aendert sich.
//
// Gemessen wird auf der PLATTE (rohe user.json als Map), nicht ueber das
// typisierte Struct: so kompiliert die Datei ohne die neuen Modellfelder und
// wird per Assertion rot, und ein Fremdfeld ist ueberhaupt nur roh sichtbar.
// Fixtures werden roh per os.WriteFile geschrieben, weil SaveUser das
// Fremdfeld bereits beim Anlegen verwerfen wuerde.
//
// Keine Mocks: echte Handler ueber echte HTTP-Requests, echter Store auf
// t.TempDir().

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

// onbAltdatei liefert eine Bestands-user.json OHNE die neuen S2-Felder, mit
// durchweg belegten Nachbarfeldern und einem unbekannten Fremdfeld.
// tier bewusst "standard": ein geleertes tier liest sich als "free" zurueck.
func onbAltdatei(id string) map[string]interface{} {
	return map[string]interface{}{
		"id":                       id,
		"email":                    id + "@example.com",
		"password_hash":            "$2a$04$abcdefghijklmnopqrstuv",
		"created_at":               "2026-06-01T12:00:00Z",
		"mail_to":                  id + "@example.com",
		"telegram_chat_id":         "777000" + id,
		"tier":                     "standard",
		"passkey_prompt_dismissed": true,
		"email_verified_at":        "2026-07-01T08:30:00Z",
		"zukunftsfeld":             map[string]interface{}{"x": 1, "liste": []interface{}{"a", "b"}},
	}
}

// onbNachbarfelder sind die Schluessel, die ein Dismiss-PUT nie veraendern darf.
var onbNachbarfelder = []string{
	"id", "email", "password_hash", "created_at", "mail_to", "telegram_chat_id",
	"tier", "passkey_prompt_dismissed", "email_verified_at", "zukunftsfeld",
}

func onbWriteRawUser(t *testing.T, s *store.Store, id string, m map[string]interface{}) {
	t.Helper()
	dir := s.UserDir(id)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "user.json"), data, 0o644); err != nil {
		t.Fatal(err)
	}
}

func onbReadRawUserBytes(t *testing.T, s *store.Store, id string) []byte {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(s.UserDir(id), "user.json"))
	if err != nil {
		t.Fatalf("user.json von %q nicht lesbar: %v", id, err)
	}
	return data
}

func onbReadRawUser(t *testing.T, s *store.Store, id string) map[string]json.RawMessage {
	t.Helper()
	var m map[string]json.RawMessage
	data := onbReadRawUserBytes(t, s, id)
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("user.json von %q ist kein JSON: %v (%s)", id, err, data)
	}
	return m
}

// onbJSONEqual vergleicht inhaltlich (nicht byteweise): mergeUserJSON schreibt
// mit MarshalIndent und rueckt verschachtelte Werte neu ein.
func onbJSONEqual(a, b json.RawMessage) bool {
	var va, vb interface{}
	if json.Unmarshal(a, &va) != nil || json.Unmarshal(b, &vb) != nil {
		return false
	}
	return reflect.DeepEqual(va, vb)
}

func onbPutProfile(t *testing.T, s *store.Store, uid, body string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodPut, "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), uid))
	w := httptest.NewRecorder()
	UpdateProfileHandler(s, config.Config{}, weitMailLimiter, weitSmsLimiter).ServeHTTP(w, req)
	return w
}

func onbGetProfile(t *testing.T, s *store.Store, uid string) (int, map[string]json.RawMessage, string) {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, "/api/auth/profile", nil)
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), uid))
	w := httptest.NewRecorder()
	GetProfileHandler(s, nil).ServeHTTP(w, req)
	var m map[string]json.RawMessage
	_ = json.Unmarshal(w.Body.Bytes(), &m)
	return w.Code, m, w.Body.String()
}

// onbPruefeNachbarn: jedes Nachbarfeld der Altdatei steht inhaltlich
// unveraendert auf der Platte.
func onbPruefeNachbarn(t *testing.T, ac string, vorher, nachher map[string]json.RawMessage) {
	t.Helper()
	for _, k := range onbNachbarfelder {
		alt, okAlt := vorher[k]
		if !okAlt {
			t.Fatalf("%s Positivkontrolle: Nachbarfeld %q fehlt schon in der Altdatei", ac, k)
		}
		neu, okNeu := nachher[k]
		if !okNeu {
			t.Errorf("%s: Feld %q ist nach dem PUT aus user.json verschwunden (vorher %s) — "+
				"der Dismiss-PUT hat ersetzt statt gemergt", ac, k, alt)
			continue
		}
		if !onbJSONEqual(alt, neu) {
			t.Errorf("%s: Feld %q veraendert: %s -> %s", ac, k, alt, neu)
		}
	}
}

func onbIstTrue(raw json.RawMessage, ok bool) bool {
	return ok && string(bytes.TrimSpace(raw)) == "true"
}

// AC-4: PUT mit NUR `onboarding_dismissed` — Flag auf der Platte gesetzt,
// Fremdfeld und alle Nachbarfelder erhalten, Antwort traegt das Flag.
//
// Mutationen, die hier rot werden MUESSEN: Dismiss-Flag ueber SaveUser statt
// Merge-Setter schreiben (Fremdfeld weg); Flag im Decoder nicht uebernehmen.
func TestUpdateProfileOnboardingDismissedPreservesForeignAndNeighbourFields(t *testing.T) {
	s := newTestStore(t)
	const uid = "willi2521"
	onbWriteRawUser(t, s, uid, onbAltdatei(uid))
	vorher := onbReadRawUser(t, s, uid)

	w := onbPutProfile(t, s, uid, `{"onboarding_dismissed":true}`)
	if w.Code != http.StatusOK {
		t.Fatalf("PUT: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}

	nachher := onbReadRawUser(t, s, uid)
	if v, ok := nachher["onboarding_dismissed"]; !onbIstTrue(v, ok) {
		t.Errorf("AC-4: onboarding_dismissed steht nicht als true in user.json (%s, vorhanden=%v) — "+
			"\"Verstanden\" waere auf einem anderen Geraet vergessen", v, ok)
	}
	if _, ok := nachher["checklist_dismissed"]; ok && !onbJSONEqual(nachher["checklist_dismissed"], json.RawMessage("false")) {
		t.Errorf("AC-4: checklist_dismissed wurde mitgesetzt (%s), obwohl nur onboarding_dismissed kam",
			nachher["checklist_dismissed"])
	}
	onbPruefeNachbarn(t, "AC-4", vorher, nachher)

	var resp map[string]json.RawMessage
	_ = json.Unmarshal(w.Body.Bytes(), &resp)
	if v, ok := resp["onboarding_dismissed"]; !onbIstTrue(v, ok) {
		t.Errorf("AC-4: onboarding_dismissed fehlt in der PUT-Antwort oder ist nicht true: %s", w.Body.String())
	}
}

// AC-5: PUT mit NUR `checklist_dismissed` — Flag gesetzt, alles andere bleibt.
func TestUpdateProfileChecklistDismissedPreservesForeignAndNeighbourFields(t *testing.T) {
	s := newTestStore(t)
	const uid = "klara2521"
	onbWriteRawUser(t, s, uid, onbAltdatei(uid))
	vorher := onbReadRawUser(t, s, uid)

	w := onbPutProfile(t, s, uid, `{"checklist_dismissed":true}`)
	if w.Code != http.StatusOK {
		t.Fatalf("PUT: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}

	nachher := onbReadRawUser(t, s, uid)
	if v, ok := nachher["checklist_dismissed"]; !onbIstTrue(v, ok) {
		t.Errorf("AC-5: checklist_dismissed steht nicht als true in user.json (%s, vorhanden=%v)", v, ok)
	}
	if _, ok := nachher["onboarding_dismissed"]; ok && !onbJSONEqual(nachher["onboarding_dismissed"], json.RawMessage("false")) {
		t.Errorf("AC-5: onboarding_dismissed wurde mitgesetzt (%s), obwohl nur checklist_dismissed kam",
			nachher["onboarding_dismissed"])
	}
	onbPruefeNachbarn(t, "AC-5", vorher, nachher)

	var resp map[string]json.RawMessage
	_ = json.Unmarshal(w.Body.Bytes(), &resp)
	if v, ok := resp["checklist_dismissed"]; !onbIstTrue(v, ok) {
		t.Errorf("AC-5: checklist_dismissed fehlt in der PUT-Antwort oder ist nicht true: %s", w.Body.String())
	}
}

// AC-6: zwei Nutzer — A klickt "Verstanden" und "Ausblenden", die Datei von B
// bleibt byte-gleich (sie wird gar nicht angefasst, Bytevergleich zulaessig).
func TestOnboardingDismissTouchesOnlyCallersProfile(t *testing.T) {
	s := newTestStore(t)
	const a, b = "anna2521", "bert2521"
	onbWriteRawUser(t, s, a, onbAltdatei(a))
	onbWriteRawUser(t, s, b, onbAltdatei(b))
	bVorher := onbReadRawUserBytes(t, s, b)

	for _, body := range []string{`{"onboarding_dismissed":true}`, `{"checklist_dismissed":true}`} {
		if w := onbPutProfile(t, s, a, body); w.Code != http.StatusOK {
			t.Fatalf("PUT %s fuer A: erwartet 200, bekommen %d: %s", body, w.Code, w.Body.String())
		}
	}

	aNachher := onbReadRawUser(t, s, a)
	if v, ok := aNachher["onboarding_dismissed"]; !onbIstTrue(v, ok) {
		t.Errorf("AC-6: onboarding_dismissed bei A nicht gesetzt (%s)", v)
	}
	if v, ok := aNachher["checklist_dismissed"]; !onbIstTrue(v, ok) {
		t.Errorf("AC-6: checklist_dismissed bei A nicht gesetzt (%s)", v)
	}
	if bNachher := onbReadRawUserBytes(t, s, b); !bytes.Equal(bVorher, bNachher) {
		t.Errorf("AC-6: user.json von B wurde durch As Klick veraendert:\nvorher:  %s\nnachher: %s", bVorher, bNachher)
	}
	if _, err := os.Stat(filepath.Join(s.UserDir("test"), "user.json")); err == nil {
		t.Errorf("AC-6: Dismiss-PUT hat unter dem Store-Default-Nutzer 'test' eine user.json angelegt")
	}
}

// AC-6: vom Client mitgeschickte Server-Felder bleiben wirkungslos — beide
// Richtungen.
//
// Hinweis: `onboarding_pending: true` steht hier ROH im Fixture, damit die
// Faelschung `false` ueberhaupt etwas zu loeschen haette. Das ist ausdruecklich
// NICHT der AC-1-Nachweis (der laeuft ueber die echten Anlagewege in
// onboarding_account_creation_test.go).
func TestUpdateProfileIgnoresForgedServerOwnedOnboardingFields(t *testing.T) {
	s := newTestStore(t)
	const neu, alt = "nora2521", "otto2521"

	neuDatei := onbAltdatei(neu)
	neuDatei["onboarding_pending"] = true
	onbWriteRawUser(t, s, neu, neuDatei)
	onbWriteRawUser(t, s, alt, onbAltdatei(alt))

	// Richtung 1: neuer Nutzer faelscht pending=false, um sein Merkmal loszuwerden.
	w := onbPutProfile(t, s, neu, `{"onboarding_dismissed":true,"onboarding_pending":false}`)
	if w.Code != http.StatusOK {
		t.Fatalf("PUT (neu): erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if v, ok := onbReadRawUser(t, s, neu)["onboarding_pending"]; !onbIstTrue(v, ok) {
		t.Errorf("AC-6: onboarding_pending ist nach PUT mit gefaelschtem false nicht mehr true (%s, vorhanden=%v) — "+
			"der Client darf das Merkmal nie aendern", v, ok)
	}

	// Richtung 2: Bestandsnutzer faelscht pending=true, Testmail- und
	// Briefing-Zeitstempel.
	w = onbPutProfile(t, s, alt, `{"checklist_dismissed":true,"onboarding_pending":true,`+
		`"test_mail_sent_at":"2026-01-01T00:00:00Z","first_briefing_at":"2026-01-02T00:00:00Z"}`)
	if w.Code != http.StatusOK {
		t.Fatalf("PUT (alt): erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	altNachher := onbReadRawUser(t, s, alt)
	if v, ok := altNachher["onboarding_pending"]; ok && !onbJSONEqual(v, json.RawMessage("false")) {
		t.Errorf("AC-6: gefaelschtes onboarding_pending=true wurde uebernommen (%s)", v)
	}
	if v, ok := altNachher["test_mail_sent_at"]; ok {
		t.Errorf("AC-6: gefaelschtes test_mail_sent_at wurde uebernommen (%s)", v)
	}
	if v, ok := altNachher["first_briefing_at"]; ok {
		t.Errorf("AC-6: gefaelschtes first_briefing_at landete in user.json (%s)", v)
	}
	if _, err := os.Stat(filepath.Join(s.UserDir(alt), "first_briefing.json")); err == nil {
		t.Errorf("AC-6: PUT mit first_briefing_at hat first_briefing.json angelegt — nur der planmaessige Versand darf das")
	}
	// Positivkontrolle: das erlaubte Flag im selben PUT wirkte, sonst haette
	// der Handler den ganzen Body verworfen und alles oben waere trivial gruen.
	if v, ok := altNachher["checklist_dismissed"]; !onbIstTrue(v, ok) {
		t.Errorf("AC-6 Positivkontrolle: checklist_dismissed aus demselben PUT nicht gesetzt (%s)", v)
	}
	_, resp, body := onbGetProfile(t, s, alt)
	if v, ok := resp["first_briefing_at"]; ok {
		t.Errorf("AC-6: GET liefert gefaelschtes first_briefing_at (%s): %s", v, body)
	}
	if v, ok := resp["test_mail_sent_at"]; ok {
		t.Errorf("AC-6: GET liefert gefaelschtes test_mail_sent_at (%s): %s", v, body)
	}
}

// AC-7: GET auf eine Altdatei ohne neue Felder liefert die drei Bools immer
// als false, test_mail_sent_at fehlt; nach einem Dismiss-PUT geht weder
// Fremdfeld noch ein bestehendes Feld verloren.
func TestGetProfileAlwaysReportsOnboardingBoolsAndOmitsUnsetTestMail(t *testing.T) {
	s := newTestStore(t)
	const uid = "lena2521"
	onbWriteRawUser(t, s, uid, onbAltdatei(uid))
	vorher := onbReadRawUser(t, s, uid)

	code, resp, body := onbGetProfile(t, s, uid)
	if code != http.StatusOK {
		t.Fatalf("GET: erwartet 200, bekommen %d: %s", code, body)
	}
	for _, k := range []string{"onboarding_pending", "onboarding_dismissed", "checklist_dismissed"} {
		v, ok := resp[k]
		if !ok {
			t.Errorf("AC-7: %q fehlt in der Profil-Antwort — die Bools muessen IMMER kommen (auch false): %s", k, body)
			continue
		}
		if !onbJSONEqual(v, json.RawMessage("false")) {
			t.Errorf("AC-7: %q ist fuer eine Altdatei ohne das Feld nicht false, sondern %s", k, v)
		}
	}
	if v, ok := resp["test_mail_sent_at"]; ok {
		t.Errorf("AC-7: test_mail_sent_at erscheint, obwohl nie gesetzt (%s) — nur wenn gesetzt", v)
	}
	if v, ok := resp["first_briefing_at"]; ok {
		t.Errorf("AC-7: first_briefing_at erscheint ohne first_briefing.json (%s)", v)
	}

	// Lesen allein schreibt nichts.
	if nachGet := onbReadRawUser(t, s, uid); len(nachGet) != len(vorher) {
		t.Errorf("AC-7: GET hat user.json veraendert (%d -> %d Schluessel)", len(vorher), len(nachGet))
	}

	if w := onbPutProfile(t, s, uid, `{"onboarding_dismissed":true}`); w.Code != http.StatusOK {
		t.Fatalf("PUT: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	onbPruefeNachbarn(t, "AC-7", vorher, onbReadRawUser(t, s, uid))

	_, resp, body = onbGetProfile(t, s, uid)
	if v, ok := resp["onboarding_dismissed"]; !onbIstTrue(v, ok) {
		t.Errorf("AC-7: nach Dismiss liefert GET onboarding_dismissed nicht als true: %s", body)
	}
}

// AC-7: ist test_mail_sent_at gesetzt, liefert GET es als Zeitstempel.
func TestGetProfileReportsTestMailSentAtWhenSet(t *testing.T) {
	s := newTestStore(t)
	const uid = "tom2521"
	datei := onbAltdatei(uid)
	datei["test_mail_sent_at"] = "2026-10-16T08:15:00Z"
	onbWriteRawUser(t, s, uid, datei)

	code, resp, body := onbGetProfile(t, s, uid)
	if code != http.StatusOK {
		t.Fatalf("GET: erwartet 200, bekommen %d: %s", code, body)
	}
	v, ok := resp["test_mail_sent_at"]
	if !ok {
		t.Fatalf("AC-7: test_mail_sent_at fehlt in der Antwort, obwohl gesetzt: %s", body)
	}
	var s2 string
	if err := json.Unmarshal(v, &s2); err != nil {
		t.Fatalf("AC-7: test_mail_sent_at ist kein String: %s", v)
	}
	got, err := time.Parse(time.RFC3339, s2)
	if err != nil || !got.Equal(time.Date(2026, 10, 16, 8, 15, 0, 0, time.UTC)) {
		t.Errorf("AC-7: test_mail_sent_at = %q, erwartet 2026-10-16T08:15:00Z (RFC3339)", s2)
	}
}

func onbWriteFirstBriefing(t *testing.T, s *store.Store, id, inhalt string) {
	t.Helper()
	dir := s.UserDir(id)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "first_briefing.json"), []byte(inhalt), 0o644); err != nil {
		t.Fatal(err)
	}
}

// AC-12: first_briefing_at kommt aus data/users/<id>/first_briefing.json des
// AUFRUFERS. A hat die Datei, B nicht; Koederdateien unter dem Store-Default
// "test" und unter "default" duerfen bei B nie durchschlagen.
func TestGetProfileFirstBriefingAtComesFromCallersOwnFile(t *testing.T) {
	s := newTestStore(t)
	const a, b = "ada2521", "bob2521"
	onbWriteRawUser(t, s, a, onbAltdatei(a))
	onbWriteRawUser(t, s, b, onbAltdatei(b))
	onbWriteFirstBriefing(t, s, a, `{"first_briefing_at":"2026-10-15T05:30:00Z"}`)
	onbWriteFirstBriefing(t, s, "test", `{"first_briefing_at":"2001-01-01T00:00:00Z"}`)
	onbWriteFirstBriefing(t, s, "default", `{"first_briefing_at":"2002-02-02T00:00:00Z"}`)

	code, resp, body := onbGetProfile(t, s, a)
	if code != http.StatusOK {
		t.Fatalf("GET A: erwartet 200, bekommen %d: %s", code, body)
	}
	v, ok := resp["first_briefing_at"]
	if !ok {
		t.Errorf("AC-12: first_briefing_at fehlt bei A, obwohl first_briefing.json existiert: %s", body)
	} else {
		var got string
		_ = json.Unmarshal(v, &got)
		if got != "2026-10-15T05:30:00Z" {
			t.Errorf("AC-12: first_briefing_at bei A = %q, erwartet 2026-10-15T05:30:00Z (aus As eigener Datei)", got)
		}
	}

	code, resp, body = onbGetProfile(t, s, b)
	if code != http.StatusOK {
		t.Fatalf("GET B: erwartet 200, bekommen %d: %s", code, body)
	}
	if v, ok := resp["first_briefing_at"]; ok {
		t.Errorf("AC-12: B ohne eigene Datei bekommt first_briefing_at=%s — Cross-User/Default-Rueckfall", v)
	}
}

// AC-12: kaputte first_briefing.json = Feld fehlt, Profil laedt trotzdem.
func TestGetProfileCorruptFirstBriefingFileOmitsField(t *testing.T) {
	s := newTestStore(t)
	const kaputt, gut = "kai2521", "gus2521"
	onbWriteRawUser(t, s, kaputt, onbAltdatei(kaputt))
	onbWriteRawUser(t, s, gut, onbAltdatei(gut))
	onbWriteFirstBriefing(t, s, kaputt, `{"first_briefing_at": nicht-json`)
	onbWriteFirstBriefing(t, s, gut, `{"first_briefing_at":"2026-10-14T18:00:00Z"}`)

	code, resp, body := onbGetProfile(t, s, kaputt)
	if code != http.StatusOK {
		t.Fatalf("AC-12: kaputte first_briefing.json darf das Profil nicht brechen: %d %s", code, body)
	}
	if v, ok := resp["first_briefing_at"]; ok {
		t.Errorf("AC-12: kaputte Datei liefert trotzdem first_briefing_at=%s", v)
	}
	// Positivkontrolle im selben Test: die gueltige Datei wird gelesen — sonst
	// waere "Feld fehlt" oben trivial wahr.
	_, resp, body = onbGetProfile(t, s, gut)
	if _, ok := resp["first_briefing_at"]; !ok {
		t.Errorf("AC-12 Positivkontrolle: gueltige first_briefing.json wird nicht gelesen: %s", body)
	}
}

// Fix-Loop 1 (F004) — AC-6 auch fuer den GEMISCHTEN PUT: Dismiss-Flag plus ein
// anderes Profilfeld laeuft ueber SaveUser (nicht ueber den Merge-Setter). Auch
// dort bleiben mitgeschickte `onboarding_pending`, `test_mail_sent_at` und
// `first_briefing_at` wirkungslos; das erlaubte Flag UND das andere Feld wirken
// (Positivkontrolle, sonst waere "nichts uebernommen" trivial wahr).
//
// Mutation, die hier rot werden MUSS: im gemischten Zweig `onboarding_pending`
// bzw. `test_mail_sent_at` aus dem Body in das geladene Nutzerobjekt uebernehmen.
func TestUpdateProfileMixedPutIgnoresForgedServerOwnedOnboardingFields(t *testing.T) {
	s := newTestStore(t)
	const uid = "mia2521"
	datei := onbAltdatei(uid)
	datei["onboarding_pending"] = true
	datei["test_mail_sent_at"] = "2026-10-10T10:00:00Z"
	onbWriteRawUser(t, s, uid, datei)

	w := onbPutProfile(t, s, uid, `{"checklist_dismissed":true,"display_name":"Mia Neu",`+
		`"onboarding_pending":false,"test_mail_sent_at":"2001-01-01T00:00:00Z",`+
		`"first_briefing_at":"2002-02-02T00:00:00Z"}`)
	if w.Code != http.StatusOK {
		t.Fatalf("gemischter PUT: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}

	nachher := onbReadRawUser(t, s, uid)
	// Positivkontrolle: Flag UND anderes Feld im selben PUT wirkten.
	if v, ok := nachher["checklist_dismissed"]; !onbIstTrue(v, ok) {
		t.Errorf("AC-6 Positivkontrolle: checklist_dismissed im gemischten PUT nicht gesetzt (%s)", v)
	}
	if v, ok := nachher["display_name"]; !ok || !onbJSONEqual(v, json.RawMessage(`"Mia Neu"`)) {
		t.Errorf("AC-6 Positivkontrolle: display_name im gemischten PUT nicht uebernommen (%s)", v)
	}
	// Wirkungslos: Server-Felder bleiben, wie sie waren.
	if v, ok := nachher["onboarding_pending"]; !onbIstTrue(v, ok) {
		t.Errorf("AC-6: gemischter PUT hat onboarding_pending veraendert (%s, vorhanden=%v)", v, ok)
	}
	if v, ok := nachher["test_mail_sent_at"]; !ok || !onbJSONEqual(v, json.RawMessage(`"2026-10-10T10:00:00Z"`)) {
		t.Errorf("AC-6: gemischter PUT hat test_mail_sent_at veraendert (%s, vorhanden=%v)", v, ok)
	}
	if v, ok := nachher["first_briefing_at"]; ok {
		t.Errorf("AC-6: gefaelschtes first_briefing_at landete in user.json (%s)", v)
	}
	if _, err := os.Stat(filepath.Join(s.UserDir(uid), "first_briefing.json")); err == nil {
		t.Errorf("AC-6: gemischter PUT hat first_briefing.json angelegt")
	}
}

// F021 (AC-6/AC-7): Der Nur-Flags-Zweig (Merge-Setter) darf NUR greifen, wenn
// ausser den Dismiss-Flags KEIN weiteres Profilfeld mitkommt. Fuer jedes
// Nachbarfeld wird derselbe PUT einmal OHNE und einmal MIT Flag gegen zwei
// identische Stores gefahren: das Nachbarfeld muss mit Flag exakt dieselbe
// Wirkung auf der Platte haben wie ohne Flag (nicht still verworfen), und das
// Flag muss zusaetzlich gesetzt sein.
func TestUpdateProfileFlagPlusNeighbourFieldIsNotSilentlyDropped(t *testing.T) {
	const uid = "gemischt2521"
	faelle := []struct{ name, json string }{
		{"email", `"email":"neu-email2521@example.com"`},
		{"mail_to", `"mail_to":"neu-mailto2521@example.com"`},
		{"sms_to", `"sms_to":"+4915112345678"`},
		{"telegram_chat_id", `"telegram_chat_id":""`},
		{"passkey_prompt_dismissed", `"passkey_prompt_dismissed":false`},
	}
	for _, f := range faelle {
		for _, flag := range []string{"onboarding_dismissed", "checklist_dismissed"} {
			f, flag := f, flag
			t.Run(f.name+"+"+flag, func(t *testing.T) {
				sOhne, sMit := newTestStore(t), newTestStore(t)
				onbWriteRawUser(t, sOhne, uid, onbAltdatei(uid))
				onbWriteRawUser(t, sMit, uid, onbAltdatei(uid))

				wOhne := onbPutProfile(t, sOhne, uid, `{`+f.json+`}`)
				wMit := onbPutProfile(t, sMit, uid, `{"`+flag+`":true,`+f.json+`}`)
				if wMit.Code != wOhne.Code {
					t.Fatalf("PUT mit Flag: Status %d, ohne Flag %d: %s", wMit.Code, wOhne.Code, wMit.Body.String())
				}

				ohne := onbReadRawUser(t, sOhne, uid)
				mit := onbReadRawUser(t, sMit, uid)
				if v, ok := mit[flag]; !onbIstTrue(v, ok) {
					t.Errorf("AC-6/7: %s nicht gesetzt im gemischten PUT (%s)", flag, v)
				}
				alt := onbAltdatei(uid)
				geaendert := 0
				schluessel := map[string]bool{}
				for k := range ohne {
					schluessel[k] = true
				}
				for k := range alt {
					schluessel[k] = true
				}
				for k := range schluessel {
					if k == flag {
						continue
					}
					vo, okO := ohne[k]
					vm, okM := mit[k]
					altRaw, _ := json.Marshal(alt[k])
					if okO && onbJSONEqual(vo, altRaw) {
						continue
					}
					geaendert++
					if okO != okM || (okO && !onbJSONEqual(vm, vo)) {
						t.Errorf("AC-6/7: Feld %q mit Flag still verworfen/anders gespeichert (ohne Flag: %s/%v, mit Flag: %s/%v)", k, vo, okO, vm, okM)
					}
				}
				if geaendert == 0 {
					t.Fatalf("Kontrolle: der PUT ohne Flag hat nichts veraendert — Test misst nichts (%s)", f.name)
				}
			})
		}
	}
}
