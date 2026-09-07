package handler

// TDD RED: Issue #2141 — Telegram-Chat-ID ist eine Identitaetszuordnung, keine
// Einstellung. Spec: docs/specs/modules/telegram_chat_id_ownership.md, AC-1..AC-3.
//
// Diese Datei deckt den PROFIL-Schreibweg (PUT /api/auth/profile) ab. Heute
// uebernimmt UpdateProfileHandler (auth.go:717-719) jeden gesendeten Wert
// ungeprueft — damit kann Nutzer B die Chat-ID von Nutzer A eintragen und den
// localhost-gesperrten Einmal-Token-Flow vollstaendig umgehen.
//
// Nachweisform (Kontext-Dokument, "Nachweisformen, die truegen wuerden"):
// echter store.Store gegen ein temporaeres Verzeichnis, ZWEI persistierte
// Nutzer, und nach jedem Request werden BEIDE user.json frisch von der Platte
// gelesen. Ein Test, der nur den Angreifer prueft, belegt nicht, dass das
// Opfer unangetastet blieb.

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
)

// victimChatID / ownChatID: erfundene Chat-IDs aus der Spec (Repo ist oeffentlich).
const (
	victimChatID = "55501"
	ownChatID    = "77702"
)

// profileChatIDOf liest telegram_chat_id aus einer Profil-Antwort. Das Feld
// traegt omitempty, ein leerer Wert fehlt also ganz — beides gilt als "leer".
func profileChatIDOf(t *testing.T, raw []byte) string {
	t.Helper()
	var resp map[string]interface{}
	if err := json.Unmarshal(raw, &resp); err != nil {
		t.Fatalf("Profil-Antwort ist kein gueltiges JSON: %v (body=%s)", err, string(raw))
	}
	v, ok := resp["telegram_chat_id"]
	if !ok || v == nil {
		return ""
	}
	s, ok := v.(string)
	if !ok {
		t.Fatalf("telegram_chat_id ist kein String: %#v", v)
	}
	return s
}

// AC-1: Nutzer A haelt die Chat-ID 55501. Nutzer B traegt sie ueber sein
// eigenes Profil ein. Danach muss B's Chat-ID leer sein, A's user.json
// unveraendert 55501 tragen, und B darf 55501 auch nicht in der Antwort sehen.
func TestUpdateProfileRejectsForeignTelegramChatID(t *testing.T) {
	s := newTestStore(t)
	mustSaveUser(t, s, model.User{ID: "anna", TelegramChatID: victimChatID})
	mustSaveUser(t, s, model.User{ID: "bertram"})

	h := UpdateProfileHandler(s, config.Config{})

	body := `{"telegram_chat_id":"` + victimChatID + `"}`
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "bertram"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// Angreifer-Seite: nichts uebernommen.
	attacker := mustLoadUser(t, s, "bertram")
	if attacker.TelegramChatID != "" {
		t.Errorf("chat id von anna wurde uebernommen: bertram traegt %q, erwartet %q",
			attacker.TelegramChatID, "")
	}

	// Opfer-Seite: unangetastet.
	victim := mustLoadUser(t, s, "anna")
	if victim.TelegramChatID != victimChatID {
		t.Errorf("anna's user.json wurde veraendert: %q, erwartet %q",
			victim.TelegramChatID, victimChatID)
	}

	// Antwort verraet die fremde Chat-ID nicht zurueck.
	if got := profileChatIDOf(t, w.Body.Bytes()); got == victimChatID {
		t.Errorf("Antwort an bertram zeigt die fremde chat id %q", got)
	}
}

// AC-2: Trennen muss weiter funktionieren — der Leerstring ist der einzige
// Wert, den das Profil uebernimmt. Genau diesen Aufruf setzt
// frontend/src/routes/account/+page.svelte:251 ab.
func TestUpdateProfileClearsOwnTelegramChatID(t *testing.T) {
	s := newTestStore(t)
	mustSaveUser(t, s, model.User{ID: "bertram", TelegramChatID: ownChatID})

	h := UpdateProfileHandler(s, config.Config{})

	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(`{"telegram_chat_id":""}`))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "bertram"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("erwartet 200 beim Trennen, bekam %d: %s", w.Code, w.Body.String())
	}
	user := mustLoadUser(t, s, "bertram")
	if user.TelegramChatID != "" {
		t.Errorf("Trennen wirkungslos: bertram traegt weiter %q", user.TelegramChatID)
	}
	if got := profileChatIDOf(t, w.Body.Bytes()); got != "" {
		t.Errorf("Antwort zeigt nach dem Trennen noch %q, erwartet leer", got)
	}
}

// AC-3: Sendet ein Nutzer seine EIGENE, unveraenderte Chat-ID mit, ist das
// kein Fehler — 200, die Verknuepfung bleibt bestehen, und die uebrigen Felder
// desselben Requests werden normal uebernommen. Regressionsschutz gegen einen
// zu scharfen Fix (400 / stilles Loeschen / Abbruch vor mail_to).
func TestUpdateProfileKeepsOwnTelegramChatIDAndSavesOtherFields(t *testing.T) {
	s := newTestStore(t)
	mustSaveUser(t, s, model.User{ID: "bertram", TelegramChatID: ownChatID})

	h := UpdateProfileHandler(s, config.Config{})

	body := `{"telegram_chat_id":"` + ownChatID + `","mail_to":"bertram@example.com"}`
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "bertram"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("erwartet 200 beim No-Op-Update, bekam %d: %s", w.Code, w.Body.String())
	}
	user := mustLoadUser(t, s, "bertram")
	if user.TelegramChatID != ownChatID {
		t.Errorf("eigene chat id verloren: %q, erwartet %q", user.TelegramChatID, ownChatID)
	}
	if user.MailTo != "bertram@example.com" {
		t.Errorf("mail_to nicht uebernommen: %q, erwartet %q", user.MailTo, "bertram@example.com")
	}
}
