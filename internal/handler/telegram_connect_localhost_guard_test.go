package handler

// Sicherheitsfix (Team-Lead-Befund, 2026-08-10): PostTelegramConnectHandler
// hatte dieselbe wirkungslose localhost-Sperre wie
// PostPremiumSmsLearnHandler -- r.RemoteAddr ist bei jeder ueber nginx
// hereingeholten Anfrage "127.0.0.1:<port>", egal welche externe IP den
// Request abgeschickt hat. Diese Tests pruefen die WIRKUNG des Fixes
// (requireLocalOnly, internal/handler/localhost_guard.go) an diesem
// Endpoint: eine Anfrage mit Proxy-Header wird abgelehnt und veraendert
// keinen Nutzerdatensatz; ein echter lokaler Aufruf (kein Proxy-Header)
// funktioniert weiter wie zuvor.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func telegramConnectTestStore(t *testing.T) *store.Store {
	t.Helper()
	return store.New(t.TempDir(), "default")
}

func newTelegramConnectRequest(remoteAddr string, headers map[string]string, body map[string]any) *http.Request {
	b, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPost, "/api/internal/telegram-connect", bytes.NewReader(b))
	req.RemoteAddr = remoteAddr
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	return req
}

// Anfrage traegt X-Forwarded-For, RemoteAddr taeuscht Loopback vor (wie es
// eine ueber nginx durchgeleitete Anfrage tut) -> 403, kein Schreibzugriff.
func TestTelegramConnectRejectsRequestWithForwardedForHeader(t *testing.T) {
	s := telegramConnectTestStore(t)
	ts := NewTelegramTokenStore(t.TempDir())
	mustSaveUser(t, s, model.User{ID: "victim-user"})
	token := ts.CreateToken("victim-user")

	h := PostTelegramConnectHandler(s, ts)
	req := newTelegramConnectRequest(
		"127.0.0.1:54321",
		map[string]string{"X-Forwarded-For": "203.0.113.5"},
		map[string]any{"token": token, "chat_id": "attacker-chat-id"},
	)
	rr := httptest.NewRecorder()
	h(rr, req)

	if rr.Code != http.StatusForbidden {
		t.Fatalf("erwartet 403 bei X-Forwarded-For, bekam %d, body=%s", rr.Code, rr.Body.String())
	}

	victim := mustLoadUser(t, s, "victim-user")
	if victim.TelegramChatID != "" {
		t.Errorf("proxierte Anfrage darf TelegramChatID NICHT setzen, hat aber %q", victim.TelegramChatID)
	}
}

// Anfrage ohne Proxy-Header von echtem Loopback -> funktioniert weiter wie
// vor dem Fix.
func TestTelegramConnectWorksForGenuineLocalCallWithoutProxyHeaders(t *testing.T) {
	s := telegramConnectTestStore(t)
	ts := NewTelegramTokenStore(t.TempDir())
	mustSaveUser(t, s, model.User{ID: "victim-user"})
	token := ts.CreateToken("victim-user")

	h := PostTelegramConnectHandler(s, ts)
	req := newTelegramConnectRequest(
		"127.0.0.1:54321",
		nil,
		map[string]any{"token": token, "chat_id": "real-chat-id"},
	)
	rr := httptest.NewRecorder()
	h(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("erwartet 200 fuer echten lokalen Aufruf, bekam %d, body=%s", rr.Code, rr.Body.String())
	}

	victim := mustLoadUser(t, s, "victim-user")
	if victim.TelegramChatID != "real-chat-id" {
		t.Errorf("erwartet TelegramChatID=%q, bekam %q", "real-chat-id", victim.TelegramChatID)
	}
}
