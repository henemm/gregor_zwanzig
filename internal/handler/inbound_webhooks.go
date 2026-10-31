package handler

// Push-Eingang fuer Befehle (Issue #2439, ADR-0088): "Webhook = Weckruf".
//
// Oeffentliche, secret-geschuetzte Endpunkte
//
//	POST /api/webhooks/sms/{secret}   (seven.io sms_mo, HMAC-signiert)
//	POST /api/webhooks/mail/{secret}  (Stalwart-Mail-Eingang, Bearer)
//
// Der Handler verarbeitet die Nachricht NICHT und parst den Body nicht (bei SMS
// nur fuer die Signatur gehasht). Nach bestandener Pruefung stoesst er den
// bestehenden Poll-Job des Kanals an (Scheduler.Kick, asynchron) und antwortet
// sofort 200. Vorlage: telegram_webhook.go (503 fail-closed, konstantzeitiger
// Vergleich).
//
// Spec: docs/specs/modules/feat_2439_befehle_push_eingang.md

import (
	"crypto/hmac"
	"crypto/md5" // #nosec G501 -- vom seven.io-Signaturverfahren vorgegeben, kein Sicherheitsanker
	"crypto/sha256"
	"encoding/hex"
	"io"
	"log"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/scheduler"
)

const (
	// sevenTimestampWindow: erlaubte Abweichung von X-Timestamp zur Uhr.
	sevenTimestampWindow = 30 * time.Second
	// sevenMaxBody: Obergrenze fuer den gehashten Body.
	sevenMaxBody = 1 << 20
)

// sevenSignature berechnet die seven.io-Webhook-Signatur: HMAC-SHA256 (Hex) mit dem
// Signing-Key ueber Timestamp, Nonce, Methode, volle Ziel-URL und MD5-Hex des
// Bodys, getrennt durch "\n", ohne abschliessenden Zeilenumbruch. Verfahren gegen
// die echte seven.io-Gegenseite belegt:
// docs/artifacts/feat-2439-befehle-push-eingang/seven-signatur-nachweis.md
func sevenSignature(signingKey, timestamp, nonce, method, fullURL string, body []byte) string {
	sum := md5.Sum(body) // #nosec G401
	msg := strings.Join([]string{timestamp, nonce, method, fullURL, hex.EncodeToString(sum[:])}, "\n")
	mac := hmac.New(sha256.New, []byte(signingKey))
	mac.Write([]byte(msg))
	return hex.EncodeToString(mac.Sum(nil))
}

// nonceCache merkt gesehene Nonces fuer die Dauer des Timestamp-Fensters.
type nonceCache struct {
	mu   sync.Mutex
	seen map[string]time.Time
}

// firstUse meldet true, wenn die Nonce noch nicht gesehen wurde, und merkt sie.
func (c *nonceCache) firstUse(nonce string, now time.Time) bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.seen == nil {
		c.seen = make(map[string]time.Time)
	}
	for n, t := range c.seen {
		if now.Sub(t) > 2*sevenTimestampWindow {
			delete(c.seen, n)
		}
	}
	if _, dup := c.seen[nonce]; dup {
		return false
	}
	c.seen[nonce] = now
	return true
}

// webhookReject antwortet 403 und verbucht die Abweisung (kein Kick).
func webhookReject(w http.ResponseWriter, r *http.Request, sched *scheduler.Scheduler, jobID, kanal string) {
	sched.RecordPushRejected(jobID)
	log.Printf("[%s-webhook] 403 rejected (remote=%s)", kanal, r.RemoteAddr)
	http.Error(w, "forbidden", http.StatusForbidden)
}

// webhookAccept verbucht den Eingang, weckt den Poll-Job und antwortet sofort 200.
func webhookAccept(w http.ResponseWriter, sched *scheduler.Scheduler, jobID string) {
	sched.RecordPushReceived(jobID)
	sched.Kick(jobID)
	w.WriteHeader(http.StatusOK)
}

// InboundSMSWebhook ist der seven.io-sms_mo-Weckruf. publicHost bildet die
// signierte URL (publicHost + Pfad), nie r.URL/Host-Header; now ist die Uhr.
// pathSecret/signingKey kommen aus config.Config (Issue #2163, leer = 503).
func InboundSMSWebhook(sched *scheduler.Scheduler, publicHost, pathSecret, signingKey string, now func() time.Time) http.HandlerFunc {
	nonces := &nonceCache{}
	return func(w http.ResponseWriter, r *http.Request) {
		if pathSecret == "" || signingKey == "" {
			http.Error(w, "webhook not configured", http.StatusServiceUnavailable)
			return
		}
		job := scheduler.JobPremiumSMSPoll
		if !secretEqual(chi.URLParam(r, "secret"), pathSecret) {
			webhookReject(w, r, sched, job, "sms")
			return
		}
		body, err := io.ReadAll(io.LimitReader(r.Body, sevenMaxBody))
		if err != nil {
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}
		if !sevenRequestValid(r, body, signingKey, strings.TrimRight(publicHost, "/")+
			"/api/webhooks/sms/"+pathSecret, now(), nonces) {
			webhookReject(w, r, sched, job, "sms")
			return
		}
		webhookAccept(w, sched, job)
	}
}

// sevenRequestValid prueft Timestamp-Fenster, Signatur und Nonce (Replay).
func sevenRequestValid(r *http.Request, body []byte, key, fullURL string, now time.Time, nonces *nonceCache) bool {
	ts, nonce, sig := r.Header.Get("X-Timestamp"), r.Header.Get("X-Nonce"), r.Header.Get("X-Signature")
	sec, err := strconv.ParseInt(ts, 10, 64)
	if err != nil || nonce == "" || sig == "" {
		return false
	}
	if d := now.Sub(time.Unix(sec, 0)); d > sevenTimestampWindow || d < -sevenTimestampWindow {
		return false
	}
	want := sevenSignature(key, ts, nonce, r.Method, fullURL, body)
	if !secretEqual(strings.ToLower(sig), want) {
		return false
	}
	// Nonce erst NACH gueltiger Signatur merken: Fremde fuellen den Cache nicht.
	return nonces.firstUse(nonce, now)
}

// InboundMailWebhook ist der Stalwart-Mail-Eingangs-Weckruf: Pfad-Secret plus
// "Authorization: Bearer <STALWART_WEBHOOK_SECRET>".
// pathSecret/bearer kommen aus config.Config (Issue #2163, leer = 503).
func InboundMailWebhook(sched *scheduler.Scheduler, pathSecret, bearer string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if pathSecret == "" || bearer == "" {
			http.Error(w, "webhook not configured", http.StatusServiceUnavailable)
			return
		}
		job := scheduler.JobInboundCommandPoll
		got, hasBearer := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
		okPath := secretEqual(chi.URLParam(r, "secret"), pathSecret)
		okBearer := secretEqual(got, bearer)
		if !okPath || !hasBearer || !okBearer {
			webhookReject(w, r, sched, job, "mail")
			return
		}
		webhookAccept(w, sched, job)
	}
}
