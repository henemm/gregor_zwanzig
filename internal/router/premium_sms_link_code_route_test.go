package router

// Verdrahtungs- und Anmelde-Nachweis fuer /api/auth/premium-sms-link-code
// (Issue #2154 Scheibe A, Adversary-Befund F001).
//
// Warum zusaetzlich zu internal/handler/premium_sms_link_code_test.go: die
// AC-Tests dort rufen die beiden Handler DIREKT auf. Sie bleiben restlos gruen,
// wenn die Routen-Zeilen in router.go fehlten oder der Pfad in die
// Public-Allowlist der AuthMiddleware geriete (internal/middleware/auth.go:50-68)
// — der Verknuepfungs-Code eines fremden Kontos haenge dann an einem Endpunkt
// ohne Anmeldepflicht. Gebaut wird deshalb der ECHTE Produktions-Router
// (newBriefingTestRouter, dieselbe Deps-Verdrahtung wie cmd/server/main.go)
// inklusive AuthMiddleware, angesprochen ueber den echten Pfad.
//
// Der eigentliche Waechter ist die POSITIV-Kontrolle, nicht der anonyme Aufruf:
// der Allowlist-Zweig der Middleware ruft next.ServeHTTP OHNE context.WithValue
// (auth.go:69) — auf einem freigegebenen Pfad bekaeme der Handler also auch mit
// gueltigem Anmelde-Merkmal keine Nutzerkennung und antwortete seinerseits 401.
// Ein anonymer Aufruf allein saehe in beiden Welten gleich aus. Er wird deshalb
// zusaetzlich an der ANTWORTFORM unterschieden: die Middleware meldet
// {"error":"unauthorized"}, der Handler selbst nur "unauthorized".

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

const linkCodeRoutePath = "/api/auth/premium-sms-link-code"

func TestPremiumSmsLinkCodeRouteIstVerdrahtetUndAnmeldepflichtig(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)

	const uid = "linkcodealice"
	if err := s.SaveUser(model.User{ID: uid, Tier: "premium", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	// --- 1. Angemeldet: die Route existiert UND der Handler sieht die
	//        Nutzerkennung aus dem geprueften Merkmal.
	rrPost := doBriefingRequest(t, r, http.MethodPost, linkCodeRoutePath, nil, sessionCookieFor(uid, secret))
	// 405 zaehlt wie 404: chi meldet "Methode nicht erlaubt", wenn der Pfad nur
	// noch fuer das andere Verb registriert ist — auch das ist ein unerreichbarer
	// Endpunkt.
	if rrPost.Code == http.StatusNotFound || rrPost.Code == http.StatusMethodNotAllowed {
		t.Fatalf("VERDRAHTUNG FEHLT: POST %s antwortet %d — die Route ist im Produktions-Router "+
			"nicht registriert, der Endpunkt ist unerreichbar", linkCodeRoutePath, rrPost.Code)
	}
	if rrPost.Code != http.StatusOK {
		t.Fatalf("F001: angemeldet erwartet 200, bekam %d, body=%s — ein 401 hier hiesse, dass die "+
			"AuthMiddleware den Pfad durchgewunken hat, ohne die Nutzerkennung in den Kontext zu legen "+
			"(Public-Allowlist, auth.go:50-68)", rrPost.Code, rrPost.Body.String())
	}
	var created map[string]string
	if err := json.Unmarshal(rrPost.Body.Bytes(), &created); err != nil {
		t.Fatalf("Antwort nicht JSON-dekodierbar: %v (%s)", err, rrPost.Body.String())
	}
	if len(created["code"]) != 7 {
		t.Errorf("angemeldet erwartet einen 7-stelligen Klartext-Code, bekam %q", created["code"])
	}

	rrGet := doBriefingRequest(t, r, http.MethodGet, linkCodeRoutePath, nil, sessionCookieFor(uid, secret))
	if rrGet.Code != http.StatusOK {
		t.Fatalf("F001: angemeldeter Statusaufruf erwartet 200, bekam %d, body=%s", rrGet.Code, rrGet.Body.String())
	}
	var status map[string]bool
	if err := json.Unmarshal(rrGet.Body.Bytes(), &status); err != nil {
		t.Fatalf("Statusantwort nicht JSON-dekodierbar: %v (%s)", err, rrGet.Body.String())
	}
	if !status["exists"] {
		t.Errorf("angemeldet muss der eben erzeugte Code als exists=true gemeldet werden, body=%s", rrGet.Body.String())
	}

}

// Zweite Haelfte von F001, bewusst als EIGENER Test: die Positiv-Kontrolle oben
// bricht bei Fehlschlag ab (ohne erzeugten Code ist der Rest gegenstandslos) —
// stuende der anonyme Nachweis in demselben Rumpf, verschwaende er hinter genau
// dem Abbruch, den die Allowlist-Mutation ausloest.
func TestPremiumSmsLinkCodeRouteWeistAnonymeAufrufeInDerMiddlewareAb(t *testing.T) {
	r, s, _ := newBriefingTestRouter(t)

	// --- BEIDE Verben werden von der AuthMiddleware abgewiesen, nicht erst vom
	//     Handler.
	for _, method := range []string{http.MethodPost, http.MethodGet} {
		req := httptest.NewRequest(method, linkCodeRoutePath, nil)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusUnauthorized {
			t.Errorf("F001: anonymes %s %s erwartet 401, bekam %d, body=%s",
				method, linkCodeRoutePath, w.Code, w.Body.String())
		}
		if got := strings.TrimSpace(w.Body.String()); got != `{"error":"unauthorized"}` {
			t.Errorf("F001: anonymes %s %s wurde NICHT von der AuthMiddleware abgewiesen, sondern erst "+
				"vom Handler (Antwort %q) — der Pfad steht in der Public-Allowlist (auth.go:50-68)",
				method, linkCodeRoutePath, got)
		}
	}

	// --- Der anonyme Aufruf darf nichts angelegt haben — weder unter der
	//     Vorgabe-Kennung noch unter der leeren.
	for _, id := range []string{"default", ""} {
		path := filepath.Join(s.DataDir, "users", id, "premium_sms_link.json")
		if _, err := os.Stat(path); err == nil {
			t.Errorf("F001: der anonyme Aufruf hat %s geschrieben — Rueckfall auf eine Kennung "+
				"statt Abweisung", path)
		}
	}
}
