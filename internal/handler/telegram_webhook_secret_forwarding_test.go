package handler

// Issue #2142, AC-10: Das Telegram-Secret muss beim Weiterreichen an den
// Python-Core MITGESENDET werden — der Core prueft es dort ein zweites Mal
// (Defense in Depth) und antwortet sonst mit 403.
//
// Gemessen wird am Draht: der echte Handler laeuft in einem httptest.Server,
// ein zweiter httptest.Server spielt den Python-Core und prueft den Header, der
// bei IHM ankommt. Ein Test, der nur das Python-Endpoint mit von Hand gesetztem
// Header aufruft, wuerde das Fehlen der Weiterreichung nicht bemerken.
//
// Ausfuehrung: go test ./internal/handler/... -run TestTelegramWebhookForwardsSecret -v

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
)

func TestTelegramWebhookForwardsSecretHeaderToPythonCore(t *testing.T) {
	const secret = "s3cr3t-2142"
	os.Setenv("TELEGRAM_WEBHOOK_SECRET", secret)
	defer os.Unsetenv("TELEGRAM_WEBHOOK_SECRET")

	var coreHits int
	var arrivedSecret string
	core := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		coreHits++
		arrivedSecret = r.Header.Get("X-Telegram-Bot-Api-Secret-Token")
		w.WriteHeader(http.StatusOK)
	}))
	defer core.Close()

	gateway := httptest.NewServer(TelegramWebhookHandler(core.URL))
	defer gateway.Close()

	body := `{"update_id":42,"message":{"chat":{"id":12345},"text":"status"}}`
	req, err := http.NewRequest(http.MethodPost, gateway.URL+"/api/webhooks/telegram/whatever", bytes.NewBufferString(body))
	if err != nil {
		t.Fatalf("Request-Bau fehlgeschlagen: %v", err)
	}
	req.Header.Set("X-Telegram-Bot-Api-Secret-Token", secret)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("Gateway nicht erreichbar: %v", err)
	}
	resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("erwartet 200 vom Gateway, bekam %d", resp.StatusCode)
	}
	// Positivkontrolle: ohne erreichten Core waere die Header-Pruefung wertlos.
	if coreHits != 1 {
		t.Fatalf("Python-Core-Fake wurde nicht genau einmal erreicht (hits=%d)", coreHits)
	}
	if arrivedSecret != secret {
		t.Fatalf("Telegram-Secret kam beim Python-Core nicht an: erwartet %q, angekommen %q — der Core antwortet darauf mit 403 (AC-10)", secret, arrivedSecret)
	}
}
