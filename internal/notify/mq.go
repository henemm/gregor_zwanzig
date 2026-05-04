// Package notify provides helpers for inter-instance messaging via the
// local claude-mq service.
//
// SPEC: docs/specs/bugfix/heartbeat_url_rotation.md
package notify

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"
)

type mqMessage struct {
	Sender    string `json:"sender"`
	Recipient string `json:"recipient"`
	Priority  string `json:"priority"`
	Subject   string `json:"subject"`
	Body      string `json:"body"`
}

// SendMQ sends an inter-instance message via the local claude-mq service.
//
// Behaviour:
//   - URL: env CLAUDE_MQ_URL, default http://127.0.0.1:3457/send
//   - Auth: header X-MQ-Secret from env CLAUDE_MQ_SECRET
//   - Fail-soft: returns nil silently when CLAUDE_MQ_SECRET is unset
//     (no POST is made), so dev/test environments do not require config.
//   - On HTTP/transport error: logs a warning and returns the error so the
//     caller may decide to ignore it.
//   - 5s timeout.
func SendMQ(sender, recipient, priority, subject, body string) error {
	secret := os.Getenv("CLAUDE_MQ_SECRET")
	if secret == "" {
		log.Printf("[notify] CLAUDE_MQ_SECRET unset, skipping MQ send (subject=%q)", subject)
		return nil
	}

	url := os.Getenv("CLAUDE_MQ_URL")
	if url == "" {
		url = "http://127.0.0.1:3457/send"
	}

	payload, err := json.Marshal(mqMessage{
		Sender:    sender,
		Recipient: recipient,
		Priority:  priority,
		Subject:   subject,
		Body:      body,
	})
	if err != nil {
		return fmt.Errorf("mq marshal: %w", err)
	}

	req, err := http.NewRequest("POST", url, bytes.NewReader(payload))
	if err != nil {
		return fmt.Errorf("mq request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-MQ-Secret", secret)

	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("[notify] MQ send failed: %v", err)
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		log.Printf("[notify] MQ send HTTP %d (subject=%q)", resp.StatusCode, subject)
		return fmt.Errorf("mq HTTP %d", resp.StatusCode)
	}
	return nil
}
