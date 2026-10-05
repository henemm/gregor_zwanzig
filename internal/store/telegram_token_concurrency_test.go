package store_test

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
	"testing"

	"github.com/henemm/gregor-api/internal/handler"
)

// AC-15 (#2158): Regressionswaechter. Ein Nebenlaeufigkeitstest fuer
// telegram_tokens.json existierte bisher nicht (geprueft per Suche in
// internal/handler: nur Einzelpfad-Tests aus #2160). Der TelegramTokenStore
// lebt im Paket handler; dieser Test liegt im externen Testpaket store_test,
// damit kein Importzyklus entsteht. Erwartet GRUEN: #2160 AC-14 hat Sperre und
// atomares Schreiben schon geliefert, Produktivcode bleibt unveraendert.
func TestTelegramTokenConcurrency_ParalleleSchreiberVerlierenKeinenToken(t *testing.T) {
	dir := t.TempDir()
	ts := handler.NewTelegramTokenStore(dir)

	const n = 60
	tokens := make([]string, n)
	var wg sync.WaitGroup
	start := make(chan struct{})
	for i := 0; i < n; i++ {
		i := i
		wg.Add(1)
		go func() {
			defer wg.Done()
			<-start
			tok, err := ts.IssueToken("user-" + string(rune('a'+i%26)))
			if err != nil {
				t.Errorf("IssueToken %d: %v", i, err)
				return
			}
			tokens[i] = tok
		}()
	}
	close(start)
	wg.Wait()

	data, err := os.ReadFile(filepath.Join(dir, "telegram_tokens.json"))
	if err != nil {
		t.Fatalf("Datei nicht lesbar: %v", err)
	}
	var onDisk map[string]json.RawMessage
	if err := json.Unmarshal(data, &onDisk); err != nil {
		t.Fatalf("Datei ist kein gueltiges JSON (halb geschrieben?): %v", err)
	}
	for i, tok := range tokens {
		if _, ok := onDisk[tok]; !ok {
			t.Errorf("Token %d fehlt in telegram_tokens.json", i)
		}
	}
	if len(onDisk) != n {
		t.Errorf("erwartet %d Tokens auf Platte, gefunden %d", n, len(onDisk))
	}
	entries, _ := os.ReadDir(dir)
	for _, e := range entries {
		if e.Name() != "telegram_tokens.json" {
			t.Errorf("Temp-Datei liegen geblieben: %s", e.Name())
		}
	}
}
