package handler

// TDD RED: Issue #2141 — Eindeutigkeit der Telegram-Chat-ID im Token-Flow.
// Spec: docs/specs/modules/telegram_chat_id_ownership.md, AC-4..AC-6.
//
// PostTelegramConnectHandler (telegram_connect.go:192-201) laedt den Nutzer
// zum Token und schreibt die Chat-ID ohne jede Kollisionspruefung. Gehoert die
// ID bereits einem anderen ECHTEN Konto, muss der Endpunkt mit 409
// {"error":"chat_id_already_linked"} antworten und darf nichts speichern.
//
// Test-Nutzer (model.IsTestUserID) sind bewusst ausgenommen: Issue #1013 haelt
// fest, dass der echte Nutzer gegen die Fixture gewinnt — sonst koennte sich
// der PO auf Staging nicht mehr verbinden, sobald tg-live-e2e seine Chat-ID
// traegt.
//
// Nachweisform: echter store.Store gegen ein temporaeres Verzeichnis (ein
// gestubbter Store wuerde eine fehlende Iteration ueber alle Nutzer nicht
// auffallen lassen), zwei persistierte Nutzer, beide user.json nach dem
// Request frisch von der Platte gelesen. Aufrufe kommen von echtem Loopback
// ohne Proxy-Header, passieren requireLocalOnly also wie der lokale
// Python-Core.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// connectErrorCode liest das error-Feld aus einer Connect-Antwort.
func connectErrorCode(t *testing.T, raw []byte) string {
	t.Helper()
	var resp map[string]interface{}
	if err := json.Unmarshal(raw, &resp); err != nil {
		t.Fatalf("Connect-Antwort ist kein gueltiges JSON: %v (body=%s)", err, string(raw))
	}
	v, ok := resp["error"]
	if !ok || v == nil {
		return ""
	}
	s, ok := v.(string)
	if !ok {
		t.Fatalf("error ist kein String: %#v", v)
	}
	return s
}

// AC-4: Nutzer anna haelt 55501. bertram loest einen gueltigen Einmal-Token
// aus und verbindet damit dieselbe Chat-ID. Erwartet 409
// chat_id_already_linked; bertram bleibt ohne Verknuepfung, anna behaelt ihre.
func TestTelegramConnectRejectsChatIDOwnedByAnotherUser(t *testing.T) {
	s := telegramConnectTestStore(t)
	ts := NewTelegramTokenStore(t.TempDir())
	mustSaveUser(t, s, model.User{ID: "anna", TelegramChatID: victimChatID})
	mustSaveUser(t, s, model.User{ID: "bertram"})
	token := ts.CreateToken("bertram")

	h := PostTelegramConnectHandler(s, ts)
	req := newTelegramConnectRequest("127.0.0.1:54321", nil,
		map[string]any{"token": token, "chat_id": victimChatID})
	rr := httptest.NewRecorder()
	h(rr, req)

	if rr.Code != http.StatusConflict {
		t.Errorf("erwartet 409 fuer fremde chat id, bekam %d, body=%s", rr.Code, rr.Body.String())
	}
	if got := connectErrorCode(t, rr.Body.Bytes()); got != "chat_id_already_linked" {
		t.Errorf("erwartet error=%q, bekam %q (body=%s)",
			"chat_id_already_linked", got, rr.Body.String())
	}

	attacker := mustLoadUser(t, s, "bertram")
	if attacker.TelegramChatID != "" {
		t.Errorf("chat id von anna wurde uebernommen: bertram traegt %q, erwartet %q",
			attacker.TelegramChatID, "")
	}
	victim := mustLoadUser(t, s, "anna")
	if victim.TelegramChatID != victimChatID {
		t.Errorf("anna's Verknuepfung wurde veraendert: %q, erwartet %q",
			victim.TelegramChatID, victimChatID)
	}
}

// AC-5: Derselbe Nutzer verbindet dieselbe Chat-ID erneut — kein Konflikt.
// Verhindert, dass die Eindeutigkeitspruefung den legitimen Re-Connect
// blockiert (z. B. nach einem Bot-Wechsel oder erneutem /start).
func TestTelegramConnectAllowsReconnectOfSameUser(t *testing.T) {
	s := telegramConnectTestStore(t)
	ts := NewTelegramTokenStore(t.TempDir())
	mustSaveUser(t, s, model.User{ID: "bertram", TelegramChatID: ownChatID})
	token := ts.CreateToken("bertram")

	h := PostTelegramConnectHandler(s, ts)
	req := newTelegramConnectRequest("127.0.0.1:54321", nil,
		map[string]any{"token": token, "chat_id": ownChatID})
	rr := httptest.NewRecorder()
	h(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("erwartet 200 fuer Re-Connect desselben Nutzers, bekam %d, body=%s",
			rr.Code, rr.Body.String())
	}
	user := mustLoadUser(t, s, "bertram")
	if user.TelegramChatID != ownChatID {
		t.Errorf("Re-Connect hat die eigene chat id veraendert: %q, erwartet %q",
			user.TelegramChatID, ownChatID)
	}
}

// AC-6: Der Test-Nutzer tg-live-e2e traegt 55501. Ein echter Nutzer verbindet
// dieselbe Chat-ID — Test-Nutzer duerfen echte Nutzer nicht blockieren
// (Issue #1013, Vorrang des echten Kontos).
func TestTelegramConnectIgnoresTestUserHoldingSameChatID(t *testing.T) {
	const fixtureUserID = "tg-live-e2e"
	if !model.IsTestUserID(fixtureUserID) {
		t.Fatalf("Testvoraussetzung verletzt: %q gilt nicht als Test-Nutzer", fixtureUserID)
	}

	s := telegramConnectTestStore(t)
	ts := NewTelegramTokenStore(t.TempDir())
	mustSaveUser(t, s, model.User{ID: fixtureUserID, TelegramChatID: victimChatID})
	mustSaveUser(t, s, model.User{ID: "anna"})
	token := ts.CreateToken("anna")

	h := PostTelegramConnectHandler(s, ts)
	req := newTelegramConnectRequest("127.0.0.1:54321", nil,
		map[string]any{"token": token, "chat_id": victimChatID})
	rr := httptest.NewRecorder()
	h(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("Test-Nutzer %q blockiert den echten Nutzer: erwartet 200, bekam %d, body=%s",
			fixtureUserID, rr.Code, rr.Body.String())
	}
	real := mustLoadUser(t, s, "anna")
	if real.TelegramChatID != victimChatID {
		t.Errorf("anna's chat id nicht gesetzt: %q, erwartet %q", real.TelegramChatID, victimChatID)
	}
	fixture := mustLoadUser(t, s, fixtureUserID)
	if fixture.TelegramChatID != victimChatID {
		t.Errorf("Fixture-Konto wurde nebenbei veraendert: %q, erwartet %q",
			fixture.TelegramChatID, victimChatID)
	}
}
