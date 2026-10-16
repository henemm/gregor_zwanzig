package handler

// TDD RED — Onboarding S2: echte Testmail, Zeitstempel `test_mail_sent_at`.
// Spec: docs/specs/modules/onboarding_willkommen_checkliste.md — AC-11, AC-9
// (Go-Seite).
//
// Festgelegte Signatur (ersetzt ProxyPostHandler an router.go POST /api/notify/test):
//
//	func NotifyTestHandler(s *store.Store, pythonURL string) http.HandlerFunc
//
// Verhalten, das hier bewacht wird:
//   - ohne user_id im Auth-Kontext: 401, KEIN Aufruf am Python-Core, nichts geschrieben;
//   - leitet POST an <pythonURL>/api/notify/test weiter, mit dem UNVERAENDERTEN
//     Body ({"channel": ...}) und `user_id` aus dem Auth-Kontext als Query
//     (ein vom Client mitgeschicktes ?user_id= wird ersetzt, Muster appendUserID);
//   - gibt Statuscode und Body des Python-Core unveraendert zurueck;
//   - setzt `test_mail_sent_at` (RFC3339) im Profil des AUFRUFERS per
//     Merge-Setter NUR bei Kanal "email" UND Antwort {"status":"ok"} —
//     nicht bei HTTP 200 mit {"error": ...}, nicht bei Kanal "telegram".
//
// Python-Gegenstueck ist ein echter httptest-Server (kein Mock-Objekt), der
// aufzeichnet, was ankommt. Gemessen wird roh auf der Platte.

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

type onbCoreCall struct {
	path   string
	userID []string
	body   string
}

// onbPythonStub antwortet immer mit HTTP 200 und dem gegebenen Body und
// zeichnet jeden Aufruf auf.
func onbPythonStub(t *testing.T, antwort string) (*httptest.Server, func() []onbCoreCall) {
	t.Helper()
	var mu sync.Mutex
	var calls []onbCoreCall
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		mu.Lock()
		calls = append(calls, onbCoreCall{path: r.URL.Path, userID: r.URL.Query()["user_id"], body: string(b)})
		mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(antwort))
	}))
	t.Cleanup(srv.Close)
	return srv, func() []onbCoreCall {
		mu.Lock()
		defer mu.Unlock()
		return append([]onbCoreCall(nil), calls...)
	}
}

func onbNotifyTest(t *testing.T, s *store.Store, pythonURL, uid, query, body string) *httptest.ResponseRecorder {
	t.Helper()
	target := "/api/notify/test"
	if query != "" {
		target += "?" + query
	}
	req := httptest.NewRequest(http.MethodPost, target, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	if uid != "" {
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), uid))
	}
	w := httptest.NewRecorder()
	NotifyTestHandler(s, pythonURL).ServeHTTP(w, req)
	return w
}

// onbPruefeCoreCall: genau ein Aufruf, richtiger Pfad, user_id des
// Auth-Kontexts (genau einmal), Body unveraendert angekommen.
func onbPruefeCoreCall(t *testing.T, calls []onbCoreCall, uid, body string) {
	t.Helper()
	if len(calls) != 1 {
		t.Fatalf("Python-Core: genau ein Aufruf erwartet, bekommen %d (%+v)", len(calls), calls)
	}
	c := calls[0]
	if c.path != "/api/notify/test" {
		t.Errorf("Python-Core: Pfad %q, erwartet /api/notify/test", c.path)
	}
	if len(c.userID) != 1 || c.userID[0] != uid {
		t.Errorf("AC-9: beim Python-Core kam user_id=%v an, erwartet genau [%q] aus dem Auth-Kontext", c.userID, uid)
	}
	if !onbJSONEqual(json.RawMessage(c.body), json.RawMessage(body)) {
		t.Errorf("Python-Core: Body kam nicht unveraendert an: %q, erwartet %q "+
			"(Handler liest den Body fuer die Kanal-Erkennung und reicht ihn leer weiter?)", c.body, body)
	}
}

func onbTestMailSentAt(t *testing.T, s *store.Store, uid string) (time.Time, bool) {
	t.Helper()
	v, ok := onbReadRawUser(t, s, uid)["test_mail_sent_at"]
	if !ok {
		return time.Time{}, false
	}
	var str string
	if err := json.Unmarshal(v, &str); err != nil {
		t.Fatalf("test_mail_sent_at ist kein String: %s", v)
	}
	ts, err := time.Parse(time.RFC3339Nano, str)
	if err != nil {
		t.Fatalf("test_mail_sent_at nicht RFC3339: %q", str)
	}
	return ts, true
}

// AC-11 (a) + AC-9: Kanal email, Python antwortet {"status":"ok"} —
// test_mail_sent_at steht im Profil des Aufrufers (und nur dort), Fremdfeld
// bleibt, Antwort geht unveraendert durch, user_id kommt aus dem Auth-Kontext
// (ein gefaelschtes ?user_id=B wird ersetzt).
func TestNotifyTestEmailOkSetsTestMailSentAtOnlyForCaller(t *testing.T) {
	s := newTestStore(t)
	const a, b = "alma2521", "berta2521"
	onbWriteRawUser(t, s, a, onbAltdatei(a))
	onbWriteRawUser(t, s, b, onbAltdatei(b))
	aVorher := onbReadRawUser(t, s, a)
	bVorher := onbReadRawUserBytes(t, s, b)

	const antwort = `{"status":"ok","channel":"email"}`
	srv, calls := onbPythonStub(t, antwort)
	const body = `{"channel":"email"}`

	vor := time.Now().Add(-time.Second)
	w := onbNotifyTest(t, s, srv.URL, a, "user_id="+b, body)
	nach := time.Now().Add(time.Second)

	if w.Code != http.StatusOK {
		t.Fatalf("erwartet 200 (Python-Status durchgereicht), bekommen %d: %s", w.Code, w.Body.String())
	}
	if !onbJSONEqual(w.Body.Bytes(), json.RawMessage(antwort)) {
		t.Errorf("Antwort nicht unveraendert durchgereicht: %s, erwartet %s", w.Body.String(), antwort)
	}
	onbPruefeCoreCall(t, calls(), a, body)

	ts, ok := onbTestMailSentAt(t, s, a)
	if !ok {
		t.Errorf("AC-11: nach erfolgreicher Testmail (status=ok) fehlt test_mail_sent_at in As user.json")
	} else if ts.Before(vor) || ts.After(nach) {
		t.Errorf("AC-11: test_mail_sent_at=%s liegt nicht im Aufrufzeitraum [%s, %s]", ts, vor, nach)
	}
	onbPruefeNachbarn(t, "AC-11", aVorher, onbReadRawUser(t, s, a))

	if bNachher := onbReadRawUserBytes(t, s, b); string(bNachher) != string(bVorher) {
		t.Errorf("AC-11: As Testmail hat Bs user.json veraendert:\nvorher:  %s\nnachher: %s", bVorher, bNachher)
	}
}

// AC-11 (b): HTTP 200 mit {"error": ...} ist ein Fehlschlag (so meldet
// send_test_message Sperren und Versandfehler). Faengt die Mutation
// "HTTP 200 genuegt statt status==\"ok\"".
func TestNotifyTestEmailErrorWithHTTP200DoesNotSetTestMailSentAt(t *testing.T) {
	s := newTestStore(t)
	const uid = "erik2521"
	onbWriteRawUser(t, s, uid, onbAltdatei(uid))

	const antwort = `{"error":"E-Mail-Adresse ist nicht bestaetigt"}`
	srv, calls := onbPythonStub(t, antwort)
	const body = `{"channel":"email"}`
	w := onbNotifyTest(t, s, srv.URL, uid, "", body)

	if w.Code != http.StatusOK || !onbJSONEqual(w.Body.Bytes(), json.RawMessage(antwort)) {
		t.Errorf("Fehlerantwort nicht unveraendert durchgereicht: %d %s", w.Code, w.Body.String())
	}
	// Positivkontrolle: der Python-Core wurde wirklich gefragt — sonst waere
	// "nicht gesetzt" trivial wahr.
	onbPruefeCoreCall(t, calls(), uid, body)
	if ts, ok := onbTestMailSentAt(t, s, uid); ok {
		t.Errorf("AC-11: test_mail_sent_at=%s gesetzt, obwohl Python {\"error\":...} meldete", ts)
	}
}

// AC-11 (c): Kanal telegram mit status=ok setzt den E-Mail-Zeitstempel nicht.
func TestNotifyTestTelegramOkDoesNotSetTestMailSentAt(t *testing.T) {
	s := newTestStore(t)
	const uid = "theo2521"
	onbWriteRawUser(t, s, uid, onbAltdatei(uid))

	const antwort = `{"status":"ok","channel":"telegram"}`
	srv, calls := onbPythonStub(t, antwort)
	const body = `{"channel":"telegram"}`
	w := onbNotifyTest(t, s, srv.URL, uid, "", body)

	if w.Code != http.StatusOK || !onbJSONEqual(w.Body.Bytes(), json.RawMessage(antwort)) {
		t.Errorf("Antwort nicht unveraendert durchgereicht: %d %s", w.Code, w.Body.String())
	}
	onbPruefeCoreCall(t, calls(), uid, body)
	if ts, ok := onbTestMailSentAt(t, s, uid); ok {
		t.Errorf("AC-11: test_mail_sent_at=%s nach Telegram-Test gesetzt — nur der Kanal email zaehlt", ts)
	}
}

// AC-11 (d): ohne Anmeldung 401, kein Aufruf am Python-Core, nichts geschrieben.
func TestNotifyTestWithoutAuthReturns401AndCallsNothing(t *testing.T) {
	s := newTestStore(t)
	const uid = "udo2521"
	onbWriteRawUser(t, s, uid, onbAltdatei(uid))
	vorher := onbReadRawUserBytes(t, s, uid)

	srv, calls := onbPythonStub(t, `{"status":"ok"}`)
	w := onbNotifyTest(t, s, srv.URL, "", "user_id="+uid, `{"channel":"email"}`)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("AC-11: ohne Auth-Kontext erwartet 401, bekommen %d: %s", w.Code, w.Body.String())
	}
	if n := len(calls()); n != 0 {
		t.Errorf("AC-11: ohne Anmeldung wurde der Python-Core %d-mal aufgerufen — er haette nie erreicht werden duerfen", n)
	}
	if nachher := onbReadRawUserBytes(t, s, uid); string(nachher) != string(vorher) {
		t.Errorf("AC-11: ohne Anmeldung (Client-?user_id=%s) wurde dessen user.json veraendert", uid)
	}
}
