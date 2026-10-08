package router

// TDD RED — Issue #2218 Scheibe C, Eintrag C5-02a (AC-23, AC-24).
//
// Spec: docs/specs/modules/fix_2218_scheibe_c_observability.md
//
// Der Go-Cron ruft fuenf Python-Alarm-Endpunkte; nur alert-checks hat heute
// einen Admin-Proxy. Gefordert: die vier uebrigen als requireAdmin-Proxys
// (POST /api/scheduler/{radar-alert-checks, compare-alert-checks,
// compare-radar-alert-checks, compare-official-alert-checks}).
//
// Echter Produktions-Router (adminTestRouter, Helfer aus
// admin_trigger_test.go), echte gz_session-Cookies; das Python-Ziel ist ein
// httptest-Server, der Aufrufe je Pfad zaehlt. Kein Prod-Trigger noetig: der
// Nachweis laeuft ausschliesslich hier (ein Admin-Trigger auf Prod liefe ueber
// alle Nutzer = verbotener Sammel-Versand).
//
// Hinweis fuer die Umsetzung: dieser Test ersetzt NICHT die Erweiterung von
// triggerPfade in admin_trigger_test.go — er deckt die vier neuen Pfade
// stand-alone ab.

import (
	"net/http"
	"strings"
	"testing"
)

var alarmTriggerPfade = []string{
	"/api/scheduler/radar-alert-checks",
	"/api/scheduler/compare-alert-checks",
	"/api/scheduler/compare-radar-alert-checks",
	"/api/scheduler/compare-official-alert-checks",
}

// AC-23: Admin erreicht auf jeder der vier Routen genau einmal den passenden
// Python-Pfad, die Python-Antwort wird durchgereicht.
func TestAdminAlarmTrigger_Admin_ReachesProxy_OnAllFourRoutes(t *testing.T) {
	r, _, secret, ziel := adminTestRouter(t, "alice")

	for _, pfad := range alarmTriggerPfade {
		w := trigger(t, r, secret, http.MethodPost, pfad, "alice")
		if w.Code != http.StatusOK {
			t.Errorf("Admin %s: erwartet 200, bekommen %d: %s", pfad, w.Code, w.Body.String())
		}
		if !strings.Contains(w.Body.String(), "python-core") {
			t.Errorf("Admin %s: Antwort muss die des Python-Ziels sein, bekommen %q", pfad, w.Body.String())
		}
		if got := ziel.n(pfad); got != 1 {
			t.Errorf("Admin %s: Python-Ziel muss genau 1x erreicht werden, wurde %dx", pfad, got)
		}
	}
}

// AC-24: Nicht-Admin (bob) bekommt auf ALLEN vier Routen 403 mit exaktem Body,
// ohne Sitzung 401; das Python-Ziel bleibt unberuehrt. alice im selben Lauf
// erreicht den Proxy (Zwei-Nutzer-Test; zugleich Positivkontrolle).
func TestAdminAlarmTrigger_NormalUserForbidden_NoCookie401_TargetUntouched(t *testing.T) {
	r, _, secret, ziel := adminTestRouter(t, "alice")

	for _, pfad := range alarmTriggerPfade {
		w := trigger(t, r, secret, http.MethodPost, pfad, "bob")
		if w.Code != http.StatusForbidden {
			t.Errorf("bob %s: erwartet 403, bekommen %d: %s", pfad, w.Code, w.Body.String())
		}
		if got := strings.TrimSpace(w.Body.String()); got != `{"error":"forbidden"}` {
			t.Errorf("bob %s: Body erwartet %q, bekommen %q", pfad, `{"error":"forbidden"}`, got)
		}
		if w := trigger(t, r, secret, http.MethodPost, pfad, ""); w.Code != http.StatusUnauthorized {
			t.Errorf("ohne Cookie %s: erwartet 401, bekommen %d", pfad, w.Code)
		}
	}
	if got := ziel.gesamt(); got != 0 {
		t.Fatalf("Nicht-Admin/ohne Sitzung darf das Python-Ziel NICHT erreichen, Zaehler=%d", got)
	}

	for _, pfad := range alarmTriggerPfade {
		if w := trigger(t, r, secret, http.MethodPost, pfad, "alice"); w.Code != http.StatusOK {
			t.Errorf("alice %s: erwartet 200, bekommen %d", pfad, w.Code)
		}
	}
	if got := ziel.gesamt(); got != len(alarmTriggerPfade) {
		t.Errorf("nach den alice-Anfragen: erwartet %d Aufrufe, Zaehler=%d", len(alarmTriggerPfade), got)
	}
}
