package handler

// Issue #2155 S3 (Kontosperre), Adversary-Nacharbeit F002/F003/F005.
// Spec: docs/specs/modules/admin_rolle_s3_admin_api.md (AC-2, AC-10).
//
//   - F002: Ladefehler an der Sperrpruefung ist fail-closed (keine Sitzung).
//   - F003: last_trip_report_run im Admin-DTO traegt einen vorhandenen
//     Laufzustand (time/status/error), nicht nur null.
//   - F005: struktureller Guard — AddSession darf ausserhalb von
//     issueSessionWithoutVerificationGate nirgends aufgerufen werden.
//
// Kein Mock-Theater: echter Store auf Tempverzeichnis, echter Scheduler mit
// vorgeschriebener Zustandsdatei, echter Quelltext per go/parser.

import (
	"encoding/json"
	"go/ast"
	"go/parser"
	"go/token"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

func TestIssueSession_UnreadableProfileIsFailClosed(t *testing.T) {
	s := newTestStore(t)
	const uid = "alice"
	if err := s.SaveUser(model.User{ID: uid, CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	// Kaputtes Profil: LoadUser liefert einen Fehler (kein nil, nil).
	if err := os.WriteFile(filepath.Join(s.UserDir(uid), "user.json"), []byte("{kaputt"), 0644); err != nil {
		t.Fatalf("user.json beschaedigen: %v", err)
	}

	req := httptest.NewRequest(http.MethodPost, "/api/auth/login", nil)
	w := httptest.NewRecorder()
	if issueSessionWithoutVerificationGate(w, req, s, uid, issuanceSecret) {
		t.Fatalf("Ladefehler: Ausgabe muss scheitern (fail-closed), lieferte true")
	}
	if w.Code < 400 {
		t.Errorf("Ladefehler: Status >= 400 erwartet, bekommen %d", w.Code)
	}
	if c := sessionCookieOderNil(w); c != nil {
		t.Errorf("Ladefehler: kein Sitzungscookie erwartet, bekommen %v", c)
	}
	sessions, _ := s.LoadSessions(uid)
	if len(sessions) != 0 {
		t.Errorf("Ladefehler: keine Sitzung in der Gaesteliste erwartet, bekommen %d", len(sessions))
	}
}

func TestAdminList_CarriesRecordedTripReportRun(t *testing.T) {
	dir := t.TempDir()
	s := store.New(dir, "alice")
	for _, id := range []string{"alice", "bob"} {
		if err := s.SaveUser(model.User{ID: id, CreatedAt: time.Now()}); err != nil {
			t.Fatalf("SaveUser %s: %v", id, err)
		}
	}
	lauf := time.Date(2026, 9, 29, 5, 0, 0, 0, time.UTC)
	zustand := map[string]map[string]map[string]any{
		"trip_reports_hourly": {"alice": {"last_run": lauf, "last_status": "partial", "last_error": "boom"}},
	}
	raw, _ := json.Marshal(zustand)
	if err := os.WriteFile(filepath.Join(dir, "scheduler_user_state.json"), raw, 0644); err != nil {
		t.Fatalf("Zustandsdatei schreiben: %v", err)
	}
	sched, err := scheduler.New(&config.Config{PythonCoreURL: "http://127.0.0.1:1", SchedulerTimezone: "Europe/Vienna"}, s)
	if err != nil {
		t.Fatalf("scheduler.New: %v", err)
	}
	t.Cleanup(sched.Stop)

	w := httptest.NewRecorder()
	AdminListUsersHandler(s, sched)(w, httptest.NewRequest(http.MethodGet, "/api/admin/users", nil))
	var resp struct {
		Users []map[string]json.RawMessage `json:"users"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("Antwort parsen: %v", err)
	}
	for _, u := range resp.Users {
		var id string
		json.Unmarshal(u["id"], &id)
		got := string(u["last_trip_report_run"])
		switch id {
		case "alice":
			var lr map[string]string
			if err := json.Unmarshal(u["last_trip_report_run"], &lr); err != nil {
				t.Fatalf("alice: last_trip_report_run kein Objekt: %s", got)
			}
			if lr["time"] != "2026-09-29T05:00:00Z" || lr["status"] != "partial" || lr["error"] != "boom" {
				t.Errorf("alice: time/status/error erwartet, bekommen %v", lr)
			}
		case "bob":
			if got != "null" {
				t.Errorf("bob: ohne Lauf muss last_trip_report_run null sein, ist %s", got)
			}
		}
	}
	if len(resp.Users) != 2 {
		t.Fatalf("2 Nutzer erwartet, bekommen %d", len(resp.Users))
	}
}

// TestAddSession_OnlyCalledFromSanctionedIssuer ist der strukturelle Guard zu
// AC-10: jede Stelle in internal/ und cmd/, die AddSession referenziert, muss
// in issueSessionWithoutVerificationGate stehen — dort sitzt die Sperrpruefung.
// Der Pfad wird relativ zu DIESER Datei aufgeloest (Worktree-sicher).
func TestAddSession_OnlyCalledFromSanctionedIssuer(t *testing.T) {
	_, thisFile, _, _ := runtime.Caller(0)
	root := filepath.Join(filepath.Dir(thisFile), "..", "..")
	const erlaubt = "issueSessionWithoutVerificationGate"

	fset := token.NewFileSet()
	var verstoesse []string
	erlaubteFunde := 0
	for _, sub := range []string{"internal", "cmd"} {
		filepath.WalkDir(filepath.Join(root, sub), func(p string, d os.DirEntry, err error) error {
			if err != nil || d.IsDir() || !strings.HasSuffix(p, ".go") || strings.HasSuffix(p, "_test.go") {
				return nil
			}
			f, perr := parser.ParseFile(fset, p, nil, 0)
			if perr != nil {
				t.Fatalf("parse %s: %v", p, perr)
			}
			for _, decl := range f.Decls {
				fn, ok := decl.(*ast.FuncDecl)
				if !ok || fn.Body == nil {
					continue
				}
				ast.Inspect(fn.Body, func(n ast.Node) bool {
					sel, ok := n.(*ast.SelectorExpr)
					if !ok || sel.Sel.Name != "AddSession" {
						return true
					}
					if fn.Name.Name == erlaubt {
						erlaubteFunde++
					} else {
						verstoesse = append(verstoesse, fset.Position(sel.Pos()).String()+" in "+fn.Name.Name)
					}
					return true
				})
			}
			return nil
		})
	}
	if erlaubteFunde == 0 {
		t.Fatalf("Guard vakuum: kein AddSession in %s gefunden (Umbenennung?)", erlaubt)
	}
	if len(verstoesse) > 0 {
		t.Errorf("AddSession ausserhalb von %s (umgeht die Sperrpruefung): %v", erlaubt, verstoesse)
	}
}
