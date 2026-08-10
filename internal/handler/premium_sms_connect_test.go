package handler

// TDD RED: Issue #1676 Scheibe S1 — Premium-SMS Rueckkanal, Go-Endpoint.
// Spec: docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md v1.1
//
// Muss FEHLSCHLAGEN bis PostPremiumSmsLearnHandler + model.User-Felder
// PremiumSmsReplyTo/PremiumSmsReplyAt existieren (Compile-Fehler).
// Ausführung (Overlay, siehe RED-Artefakt): go test -overlay=... -run TestLearn ./internal/handler/...
//
// Erfundene Rufnummern (Repo ist öffentlich): 4917000000001/...002/...099.
// Echter Store gegen temporäres Testverzeichnis (kein Mock), zwei Nutzer wie
// von CLAUDE.md für datenbewegende Endpoints gefordert.
//
// Zustaendigkeitsschnitt (Team-Lead-Korrektur #1676 S1, 2026-08-10):
// AC-1 und AC-3 sind JEWEILS auf zwei Tests aufgeteilt, weil die Behauptung
// zwei Haelften hat: "der Reader ruft korrekt auf" (Python,
// tests/unit/test_inbound_sms_reply_learning.py) und "der Aufruf persistiert
// tatsaechlich/ueberschreibt tatsaechlich" (hier, gegen einen echten Store).
// Ein frueherer Python-Fake bildete die Persistenzlogik selbst nach UND
// schrieb selbst -- die Pruefung war damit tautologisch. Hier, gegen den
// echten (noch zu implementierenden) Handler und einen echten Store, ist sie
// es nicht: TestLearnSetsReplyAddressForSoleUnambiguousPremiumUser deckt die
// Persistenz-Haelfte von AC-1 ab, TestLearnOverwritesReplyAddressAcrossCalls
// die Persistenz-Haelfte von AC-3.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	garminFromA = "4917000000001"
	garminFromB = "4917000000002"
)

func learnTestStore(t *testing.T) *store.Store {
	t.Helper()
	tmpDir := t.TempDir()
	return store.New(tmpDir, "default")
}

func mustSaveUser(t *testing.T, s *store.Store, u model.User) {
	t.Helper()
	if err := s.SaveUser(u); err != nil {
		t.Fatalf("SaveUser(%s) error: %v", u.ID, err)
	}
}

func mustLoadUser(t *testing.T, s *store.Store, id string) *model.User {
	t.Helper()
	u, err := s.LoadUser(id)
	if err != nil {
		t.Fatalf("LoadUser(%s) error: %v", id, err)
	}
	if u == nil {
		t.Fatalf("LoadUser(%s): user not found", id)
	}
	return u
}

func newLearnRequest(remoteAddr string, body map[string]any) *http.Request {
	b, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPost, "/api/internal/premium-sms-learn", bytes.NewReader(b))
	req.RemoteAddr = remoteAddr
	return req
}

func newLearnRequestWithHeader(remoteAddr, headerName, headerValue string, body map[string]any) *http.Request {
	req := newLearnRequest(remoteAddr, body)
	req.Header.Set(headerName, headerValue)
	return req
}

// ---------------------------------------------------------------------------
// AC-4 UND AC-1 (Persistenz-Haelfte): genau ein Premium-Kandidat ohne
// gespeicherten Treffer -> lernt tatsaechlich am persistierten user.json.
// Die Reader-Haelfte von AC-1 (korrekter Aufruf) prueft
// tests/unit/test_inbound_sms_reply_learning.py::test_garmin_marker_message_learns_reply_address.
// ---------------------------------------------------------------------------

func TestLearnSetsReplyAddressForSoleUnambiguousPremiumUser(t *testing.T) {
	s := learnTestStore(t)
	mustSaveUser(t, s, model.User{ID: "free-user", Tier: "free"})
	mustSaveUser(t, s, model.User{ID: "premium-user", Tier: "premium"})

	h := PostPremiumSmsLearnHandler(s)
	req := newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromA})
	rr := httptest.NewRecorder()
	h(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("AC-4: erwartet 200, bekam %d, body=%s", rr.Code, rr.Body.String())
	}

	premium := mustLoadUser(t, s, "premium-user")
	if premium.PremiumSmsReplyTo != garminFromA {
		t.Errorf("AC-4: erwartet PremiumSmsReplyTo=%q, bekam %q", garminFromA, premium.PremiumSmsReplyTo)
	}
	if premium.PremiumSmsReplyAt == nil {
		t.Error("AC-4: PremiumSmsReplyAt sollte gesetzt sein, ist nil")
	}

	free := mustLoadUser(t, s, "free-user")
	if free.PremiumSmsReplyTo != "" {
		t.Errorf("AC-4: free-user darf NICHT veraendert werden, hat aber PremiumSmsReplyTo=%q", free.PremiumSmsReplyTo)
	}
}

// ---------------------------------------------------------------------------
// AC-5: zwei Premium-Nutzer, kein gespeicherter Treffer -> ablehnen, kein Leck
// ---------------------------------------------------------------------------

func TestLearnRejectsWhenTwoPremiumUsersAndNoStoredMatch(t *testing.T) {
	s := learnTestStore(t)
	mustSaveUser(t, s, model.User{ID: "premium-a", Tier: "premium"})
	mustSaveUser(t, s, model.User{ID: "premium-b", Tier: "premium"})

	h := PostPremiumSmsLearnHandler(s)
	req := newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromA})
	rr := httptest.NewRecorder()
	h(rr, req)

	if rr.Code == http.StatusOK {
		t.Fatalf("AC-5: erwartet Fehlerstatus (kein 200) bei Mehrdeutigkeit, bekam %d, body=%s",
			rr.Code, rr.Body.String())
	}

	a := mustLoadUser(t, s, "premium-a")
	b := mustLoadUser(t, s, "premium-b")
	if a.PremiumSmsReplyTo != "" || b.PremiumSmsReplyTo != "" {
		t.Fatalf("AC-5: bei Mehrdeutigkeit darf KEIN Nutzer veraendert werden (kein Fallback auf Default), "+
			"a=%q b=%q", a.PremiumSmsReplyTo, b.PremiumSmsReplyTo)
	}
}

// ---------------------------------------------------------------------------
// AC-6: gespeicherter Treffer schlaegt die "genau ein Kandidat"-Regel
// ---------------------------------------------------------------------------

func TestLearnPrefersStoredMatchOverSoleCandidateRule(t *testing.T) {
	s := learnTestStore(t)
	oldAt := time.Now().Add(-1 * time.Hour).UTC()
	mustSaveUser(t, s, model.User{
		ID: "premium-with-history", Tier: "premium",
		PremiumSmsReplyTo: garminFromA, PremiumSmsReplyAt: &oldAt,
	})
	mustSaveUser(t, s, model.User{ID: "premium-no-history", Tier: "premium"})

	h := PostPremiumSmsLearnHandler(s)
	req := newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromA})
	rr := httptest.NewRecorder()
	h(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("AC-6: erwartet 200, bekam %d, body=%s", rr.Code, rr.Body.String())
	}

	withHistory := mustLoadUser(t, s, "premium-with-history")
	if withHistory.PremiumSmsReplyTo != garminFromA {
		t.Errorf("AC-6: erwartet unveraendertes PremiumSmsReplyTo=%q, bekam %q", garminFromA, withHistory.PremiumSmsReplyTo)
	}
	if withHistory.PremiumSmsReplyAt == nil || !withHistory.PremiumSmsReplyAt.After(oldAt) {
		t.Errorf("AC-6: PremiumSmsReplyAt haette aktualisiert werden muessen (alt=%v, neu=%v)",
			oldAt, withHistory.PremiumSmsReplyAt)
	}

	noHistory := mustLoadUser(t, s, "premium-no-history")
	if noHistory.PremiumSmsReplyTo != "" {
		t.Errorf("AC-6: der zweite Premium-Nutzer darf NICHT veraendert werden, hat aber PremiumSmsReplyTo=%q",
			noHistory.PremiumSmsReplyTo)
	}
}

// ---------------------------------------------------------------------------
// AC-3 (Persistenz-Haelfte): ein zweiter realer Lernaufruf mit einer ANDEREN
// Nummer ueberschreibt den zuvor gespeicherten Wert VOLLSTAENDIG, inklusive
// aktualisiertem Zeitstempel. Die Reader-Haelfte (dass der Reader ueberhaupt
// einen zweiten Aufruf mit der neuen Nummer absetzt, ohne den ersten zu
// wiederholen) prueft
// tests/unit/test_inbound_sms_reply_learning.py::test_newest_garmin_message_triggers_second_learn_call_with_new_sender.
// Spec Implementation Details: "R2 braucht keine eigene Vergleichslogik im
// Python-Reader" -- die Ueberschreib-Semantik ist reine Go-Verantwortung.
// ---------------------------------------------------------------------------

func TestLearnOverwritesReplyAddressAcrossCalls(t *testing.T) {
	s := learnTestStore(t)
	mustSaveUser(t, s, model.User{ID: "premium-user", Tier: "premium"})

	h := PostPremiumSmsLearnHandler(s)

	// Call 1: Nachricht von garminFromA -- eindeutiger Kandidat (AC-4).
	req1 := newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromA})
	rr1 := httptest.NewRecorder()
	h(rr1, req1)
	if rr1.Code != http.StatusOK {
		t.Fatalf("Call 1: erwartet 200, bekam %d, body=%s", rr1.Code, rr1.Body.String())
	}
	afterCall1 := mustLoadUser(t, s, "premium-user")
	if afterCall1.PremiumSmsReplyTo != garminFromA {
		t.Fatalf("Call 1: erwartet PremiumSmsReplyTo=%q, bekam %q", garminFromA, afterCall1.PremiumSmsReplyTo)
	}
	if afterCall1.PremiumSmsReplyAt == nil {
		t.Fatal("Call 1: PremiumSmsReplyAt sollte gesetzt sein, ist nil")
	}
	firstAt := *afterCall1.PremiumSmsReplyAt

	time.Sleep(2 * time.Millisecond) // sicherstellen, dass sich der Zeitstempel unterscheidet

	// Call 2: neue Nachricht von garminFromB -- muss Call 1 VOLLSTAENDIG ueberschreiben (AC-3).
	req2 := newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromB})
	rr2 := httptest.NewRecorder()
	h(rr2, req2)
	if rr2.Code != http.StatusOK {
		t.Fatalf("Call 2: erwartet 200, bekam %d, body=%s", rr2.Code, rr2.Body.String())
	}

	afterCall2 := mustLoadUser(t, s, "premium-user")
	if afterCall2.PremiumSmsReplyTo != garminFromB {
		t.Fatalf("AC-3: erwartet ueberschriebenes PremiumSmsReplyTo=%q, bekam %q", garminFromB, afterCall2.PremiumSmsReplyTo)
	}
	if afterCall2.PremiumSmsReplyAt == nil || !afterCall2.PremiumSmsReplyAt.After(firstAt) {
		t.Errorf("AC-3: PremiumSmsReplyAt haette aktualisiert werden muessen (call1=%v, call2=%v)",
			firstAt, afterCall2.PremiumSmsReplyAt)
	}
}

// ---------------------------------------------------------------------------
// localhost-Sperre (Vorbild telegram_connect.go)
// ---------------------------------------------------------------------------

func TestLearnRejectsNonLocalhostCaller(t *testing.T) {
	s := learnTestStore(t)
	mustSaveUser(t, s, model.User{ID: "premium-user", Tier: "premium"})

	h := PostPremiumSmsLearnHandler(s)
	req := newLearnRequest("203.0.113.5:54321", map[string]any{"from": garminFromA})
	rr := httptest.NewRecorder()
	h(rr, req)

	if rr.Code != http.StatusForbidden {
		t.Fatalf("erwartet 403 fuer Nicht-Localhost-Aufrufer, bekam %d", rr.Code)
	}

	premium := mustLoadUser(t, s, "premium-user")
	if premium.PremiumSmsReplyTo != "" {
		t.Error("Nicht-Localhost-Aufruf darf NIE etwas persistieren")
	}
}

// ---------------------------------------------------------------------------
// Sicherheitsfix (Team-Lead-Befund, 2026-08-10): RemoteAddr allein reicht
// nicht -- nginx proxyt auf denselben Host, RemoteAddr ist dann IMMER
// 127.0.0.1. Eine Anfrage mit Proxy-Header ist zwangslaeufig durch nginx
// gelaufen und muss abgelehnt werden, auch wenn RemoteAddr Loopback vortaeuscht.
// ---------------------------------------------------------------------------

func TestLearnRejectsRequestWithForwardedForHeaderEvenWithUniqueCandidate(t *testing.T) {
	s := learnTestStore(t)
	mustSaveUser(t, s, model.User{ID: "premium-user", Tier: "premium"})

	h := PostPremiumSmsLearnHandler(s)
	// Genau EIN Premium-Kandidat -- ohne den Proxy-Header waere das ein
	// eindeutiger Treffer (AC-4). Der Header allein muss trotzdem ablehnen:
	// die Mehrdeutigkeitsregel darf nicht die einzige Schutzschicht sein.
	req := newLearnRequestWithHeader("127.0.0.1:54321", "X-Forwarded-For", "203.0.113.5",
		map[string]any{"from": garminFromA})
	rr := httptest.NewRecorder()
	h(rr, req)

	if rr.Code != http.StatusForbidden {
		t.Fatalf("erwartet 403 bei X-Forwarded-For trotz eindeutigem Kandidaten, bekam %d, body=%s",
			rr.Code, rr.Body.String())
	}

	premium := mustLoadUser(t, s, "premium-user")
	if premium.PremiumSmsReplyTo != "" {
		t.Error("proxierte Anfrage darf NIE etwas persistieren, auch nicht bei eindeutigem Kandidaten")
	}
}

func TestLearnRejectsRequestWithRealIPOrForwardedProtoHeader(t *testing.T) {
	for _, headerName := range []string{"X-Real-IP", "X-Forwarded-Proto"} {
		t.Run(headerName, func(t *testing.T) {
			s := learnTestStore(t)
			mustSaveUser(t, s, model.User{ID: "premium-user", Tier: "premium"})

			h := PostPremiumSmsLearnHandler(s)
			req := newLearnRequestWithHeader("127.0.0.1:54321", headerName, "https",
				map[string]any{"from": garminFromA})
			rr := httptest.NewRecorder()
			h(rr, req)

			if rr.Code != http.StatusForbidden {
				t.Fatalf("erwartet 403 bei %s, bekam %d, body=%s", headerName, rr.Code, rr.Body.String())
			}
			premium := mustLoadUser(t, s, "premium-user")
			if premium.PremiumSmsReplyTo != "" {
				t.Errorf("proxierte Anfrage (%s) darf NIE etwas persistieren", headerName)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// AC-10: Dry-Run erreicht SaveUser strukturell nie -- beide Zweige
// ---------------------------------------------------------------------------

func TestLearnDryRunNeverCallsSaveUser(t *testing.T) {
	t.Run("eindeutiger Treffer", func(t *testing.T) {
		s := learnTestStore(t)
		mustSaveUser(t, s, model.User{ID: "premium-user", Tier: "premium"})

		h := PostPremiumSmsLearnHandler(s)
		req := newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromA, "dry_run": true})
		rr := httptest.NewRecorder()
		h(rr, req)

		if rr.Code != http.StatusOK {
			t.Fatalf("AC-10 (eindeutig): erwartet 200, bekam %d, body=%s", rr.Code, rr.Body.String())
		}
		var resp map[string]any
		if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
			t.Fatalf("AC-10: Antwort nicht JSON-dekodierbar: %v (%s)", err, rr.Body.String())
		}
		if resp["status"] != "dry_run" || resp["outcome"] != "would_learn" {
			t.Errorf("AC-10 (eindeutig): erwartet status=dry_run/outcome=would_learn, bekam %+v", resp)
		}

		premium := mustLoadUser(t, s, "premium-user")
		if premium.PremiumSmsReplyTo != "" {
			t.Errorf("AC-10 (eindeutig): SaveUser darf im Dry-Run NIE erreicht werden, aber "+
				"PremiumSmsReplyTo=%q wurde persistiert", premium.PremiumSmsReplyTo)
		}
	})

	t.Run("Mehrdeutigkeit", func(t *testing.T) {
		s := learnTestStore(t)
		mustSaveUser(t, s, model.User{ID: "premium-a", Tier: "premium"})
		mustSaveUser(t, s, model.User{ID: "premium-b", Tier: "premium"})

		h := PostPremiumSmsLearnHandler(s)
		req := newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromA, "dry_run": true})
		rr := httptest.NewRecorder()
		h(rr, req)

		if rr.Code != http.StatusOK {
			t.Fatalf("AC-10 (mehrdeutig): erwartet 200 (Dry-Run meldet nie hart ab), bekam %d, body=%s",
				rr.Code, rr.Body.String())
		}
		var resp map[string]any
		if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
			t.Fatalf("AC-10: Antwort nicht JSON-dekodierbar: %v (%s)", err, rr.Body.String())
		}
		if resp["status"] != "dry_run" || resp["outcome"] != "would_skip" {
			t.Errorf("AC-10 (mehrdeutig): erwartet status=dry_run/outcome=would_skip, bekam %+v", resp)
		}

		a := mustLoadUser(t, s, "premium-a")
		b := mustLoadUser(t, s, "premium-b")
		if a.PremiumSmsReplyTo != "" || b.PremiumSmsReplyTo != "" {
			t.Error("AC-10 (mehrdeutig): SaveUser darf im Dry-Run NIE erreicht werden")
		}
	})
}
