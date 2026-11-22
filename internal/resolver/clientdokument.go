package resolver

// Client-ID-Metadaten-Dokument (CIMD) fuer den MCP-Konnektor „Gregor Wetter“
// (Issue #3281, Scheibe 2; ADR-0128). Die client_id der Claude-App ist eine
// https-Adresse; ihr Dokument wird ueber den abgeschotteten Client (ADR-0114)
// geholt: nur von freigegebenen Hosts (claude.ai), nur Standard-Port, keine
// Weiterleitungen, hoechstens 64 KB, eigene Kennung (claude.ai weist die
// Standardkennung von HTTP-Bibliotheken ab).

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const (
	clientDokumentMaxBytes = 64 << 10
	clientDokumentTimeout  = 5 * time.Second
	clientDokumentKennung  = "gregor-zwanzig/1.0 (OAuth client metadata)"
)

// clientDokumentHostErlaubt: Hosts, deren Client-Dokumente abgerufen werden;
// nur export_test.go ersetzt die Pruefung.
var clientDokumentHostErlaubt = func(host string) bool { return strings.EqualFold(host, "claude.ai") }

// ClientDokumentHolen ruft das Client-Dokument unter adresse ab.
func ClientDokumentHolen(ctx context.Context, adresse string) ([]byte, error) {
	u, err := url.Parse(adresse)
	if err != nil || !linkSchemes[strings.ToLower(u.Scheme)] || u.User != nil ||
		!clientDokumentHostErlaubt(u.Hostname()) || !linkPortErlaubt(u.Port()) {
		return nil, fmt.Errorf("%w: client-dokument", errZielGesperrt)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", clientDokumentKennung)
	client := newLinkClient(clientDokumentTimeout)
	client.CheckRedirect = func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("client-dokument: status %d", resp.StatusCode)
	}
	roh, err := io.ReadAll(io.LimitReader(resp.Body, clientDokumentMaxBytes+1))
	if err != nil {
		return nil, err
	}
	if len(roh) > clientDokumentMaxBytes {
		return nil, fmt.Errorf("client-dokument: groesser als %d bytes", clientDokumentMaxBytes)
	}
	return roh, nil
}
