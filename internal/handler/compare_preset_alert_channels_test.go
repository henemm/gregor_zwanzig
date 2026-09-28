package handler

// Issue #2293 Scheibe S2 (Epic #1374/#2345) — `alert_channels` als eigenes
// Go-Feld auf model.ComparePreset (analog Trip, internal/model/trip.go:214-
// 219), deterministische Materialisierung beim Laden/Schreiben/Anlegen, und
// die Altbestand-Bereinigung fuer ungewollte Premium-SMS-Briefings.
//
// Spec: docs/specs/modules/feat_2293_s2_compare_alarm_kanaele.md AC-1, AC-2,
// AC-4, AC-5, AC-6, AC-7, AC-15 (Go-Teil), AC-16, AC-17.
//
// RED-Grund heute: `model.ComparePreset` hat KEIN `AlertChannels`-Feld —
// diese Datei kompiliert nicht (Compile-Error, dieselbe RED-Bauform wie
// compare_preset_alert_channel_thresholds_test.go Modul-Kommentar, Issue
// #1461). Nach dem Anlegen des Feldes (Implementation Details Abschnitt 1)
// kompiliert die Datei, faellt aber ohne `materializeAlertChannels`
// (Implementation Details Abschnitt 7) rot durch: AC-1/AC-6/AC-7 sehen kein
// materialisiertes `alert_channels`, AC-15/AC-17 behalten `send_premium_sms=
// true` auf einem Altbestand ohne `alert_channels`.
//
// Vorlage: compare_preset_alert_channel_thresholds_test.go (beide PUT-Wege,
// Mandanten-Test Zeile 613) — briefingVergleichEtagRouter/doReq/
// loadPresetOrFail/seedComparePreset/boolPtr sind package-intern bereits
// definiert (briefing_subscription_vergleich_etag_test.go,
// trip_etag_ifmatch_test.go, compare_preset_etag_ifmatch_test.go,
// compare_preset_detail_test.go, trip_alert_channels_test.go) und werden
// hier wiederverwendet, nicht dupliziert.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// writeRawComparePresetFixture schreibt rohes JSON DIREKT auf die Platte
// (briefings/<id>.json), OHNE SaveComparePreset/SaveComparePresets zu
// durchlaufen. Das ist Pflicht fuer echte Legacy-Fixtures: nach dem GREEN-
// Stand materialisiert jeder Store-Schreibweg alert_channels automatisch —
// ein ueber SaveComparePresets angelegter "Altbestand" waere ab dann kein
// Altbestand mehr, sondern ein bereits materialisiertes Preset (vakuum-
// gruener Test, der die Bereinigungslogik nie triggert). Pfadlayout
// identisch zu store.briefingsDir() (internal/store/briefing_subscription.go).
func writeRawComparePresetFixture(t *testing.T, s *store.Store, userID, id, rawJSON string) {
	t.Helper()
	dir := filepath.Join(s.DataDir, "users", userID, "briefings")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("MkdirAll: %v", err)
	}
	path := filepath.Join(dir, id+".json")
	if err := os.WriteFile(path, []byte(rawJSON), 0644); err != nil {
		t.Fatalf("WriteFile: %v", err)
	}
}

// readRawComparePresetFixture liest die Rohdatei zurueck — fuer den
// Byte-Vergleich in AC-7 (kein Write-Back durch ein reines GET).
func readRawComparePresetFixture(t *testing.T, s *store.Store, userID, id string) []byte {
	t.Helper()
	path := filepath.Join(s.DataDir, "users", userID, "briefings", id+".json")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("ReadFile: %v", err)
	}
	return data
}

// ═══════════════════════════ AC-1: Alarme-Reiter persistiert alert_channels ═══

// AC-1: E-Mail aus, Telegram an im Alarme-Reiter (immer alle vier Booleans)
// persistiert exakt dieses alert_channels-Objekt ueber PUT, andere Felder
// bleiben unberuehrt.
func TestUpdateComparePreset_AlertChannelsPersistedViaAlarmeReiter(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-2293-ac1", "AC1-Test", []string{"loc-a"})

	body := map[string]interface{}{
		"alert_channels": map[string]interface{}{
			"email": false, "telegram": true, "sms": false, "premium_sms": false,
		},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-2293-ac1", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded := loadPresetOrFail(t, s, "cp-2293-ac1")
	ac := loaded.AlertChannels
	if ac == nil || ac.Email == nil || *ac.Email != false || ac.Telegram == nil || *ac.Telegram != true ||
		ac.Sms == nil || *ac.Sms != false || ac.PremiumSms == nil || *ac.PremiumSms != false {
		t.Errorf("expected alert_channels={email:false,telegram:true,sms:false,premium_sms:false}, got %+v", ac)
	}
	if loaded.Name != "AC1-Test" {
		t.Errorf("expected name unberuehrt, got %q", loaded.Name)
	}
}

// ═══════════════════════════ AC-2: Erhalt bei PUT ohne alert_channels ═══════

// AC-2 Weg 1: ein PUT ohne alert_channels im Body (z.B. der Versand-Reiter)
// laesst ein zuvor gesetztes alert_channels unveraendert.
func TestUpdateComparePreset_AlertChannelsPreservedWhenPutOmitsIt(t *testing.T) {
	s := newTestStore(t)
	original := model.ComparePreset{
		ID: "cp-2293-ac2-weg1", Name: "AC2-Weg1", UserID: "test",
		LocationIDs: []string{"loc-a"}, Schedule: "manual", Profil: "SUMMER_TREKKING",
		HourFrom: 8, HourTo: 17, Empfaenger: []string{"a@example.com"},
		AlertChannels: &model.AlertChannelsConfig{
			Email: boolPtr(false), Telegram: boolPtr(true), Sms: boolPtr(false), PremiumSms: boolPtr(false),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	// Versand-Reiter-typischer PUT: nur send_telegram, kein alert_channels.
	body := map[string]interface{}{"send_telegram": false}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-2293-ac2-weg1", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded := loadPresetOrFail(t, s, "cp-2293-ac2-weg1")
	ac := loaded.AlertChannels
	if ac == nil || ac.Email == nil || *ac.Email != false || ac.Telegram == nil || *ac.Telegram != true ||
		ac.Sms == nil || *ac.Sms != false || ac.PremiumSms == nil || *ac.PremiumSms != false {
		t.Errorf("alert_channels erased by PUT without field, expected unveraendert, got %+v", ac)
	}
}

// AC-2 Weg 2: derselbe Erhalt ueber PUT /api/briefings/{id}?kind=vergleich.
func TestUpdateBriefingHandler_Vergleich_AlertChannelsPreservedWhenPatchOmitsIt(t *testing.T) {
	s := newTestStore(t)
	original := model.ComparePreset{
		ID: "cp-2293-ac2-weg2", Name: "AC2-Weg2", UserID: "test",
		LocationIDs: []string{"loc-a"}, Schedule: "manual", Profil: "SUMMER_TREKKING",
		HourFrom: 8, HourTo: 17, Empfaenger: []string{"a@example.com"},
		AlertChannels: &model.AlertChannelsConfig{
			Email: boolPtr(false), Telegram: boolPtr(true), Sms: boolPtr(false), PremiumSms: boolPtr(false),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	r := briefingVergleichEtagRouter(s)
	w := doReq(r, http.MethodPut, "/api/briefings/cp-2293-ac2-weg2?kind=vergleich",
		`{"send_telegram":false}`, "", "test")

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded := loadPresetOrFail(t, s, "cp-2293-ac2-weg2")
	ac := loaded.AlertChannels
	if ac == nil || ac.Email == nil || *ac.Email != false || ac.Telegram == nil || *ac.Telegram != true ||
		ac.Sms == nil || *ac.Sms != false || ac.PremiumSms == nil || *ac.PremiumSms != false {
		t.Errorf("Weg 2: alert_channels erased by patch without field, expected unveraendert, got %+v", ac)
	}
}

// ═══════════════════ AC-4: Trennung Alarm- vs. Briefing-Kanaele ════════════

// AC-4 Weg 1, Richtung "Versand-Reiter": ein PUT, das nur send_telegram
// aendert, laesst alert_channels exakt wie zuvor gesetzt.
func TestUpdateComparePreset_SendTelegramChangeLeavesAlertChannelsUnchanged(t *testing.T) {
	s := newTestStore(t)
	original := model.ComparePreset{
		ID: "cp-2293-ac4-versand", Name: "AC4-Versand", UserID: "test",
		LocationIDs: []string{"loc-a"}, Schedule: "manual", Profil: "SUMMER_TREKKING",
		HourFrom: 8, HourTo: 17, Empfaenger: []string{"a@example.com"},
		SendTelegram: boolPtr(true),
		AlertChannels: &model.AlertChannelsConfig{
			Email: boolPtr(true), Telegram: boolPtr(false), Sms: boolPtr(false), PremiumSms: boolPtr(false),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	buf, _ := json.Marshal(map[string]interface{}{"send_telegram": false})
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-2293-ac4-versand", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded := loadPresetOrFail(t, s, "cp-2293-ac4-versand")
	if loaded.SendTelegram == nil || *loaded.SendTelegram != false {
		t.Errorf("expected send_telegram=false, got %+v", loaded.SendTelegram)
	}
	ac := loaded.AlertChannels
	if ac == nil || ac.Email == nil || *ac.Email != true || ac.Telegram == nil || *ac.Telegram != false {
		t.Errorf("AC-4: alert_channels changed by a Versand-Reiter PUT, expected unveraendert, got %+v", ac)
	}
}

// AC-4 Weg 1, umgekehrte Richtung "Alarme-Reiter": ein PUT, das nur
// alert_channels aendert, laesst send_telegram/send_sms/send_premium_sms
// unveraendert.
func TestUpdateComparePreset_AlertChannelsChangeLeavesSendFlagsUnchanged(t *testing.T) {
	s := newTestStore(t)
	original := model.ComparePreset{
		ID: "cp-2293-ac4-alarm", Name: "AC4-Alarm", UserID: "test",
		LocationIDs: []string{"loc-a"}, Schedule: "manual", Profil: "SUMMER_TREKKING",
		HourFrom: 8, HourTo: 17, Empfaenger: []string{"a@example.com"},
		SendTelegram: boolPtr(true), SendSms: boolPtr(false), SendPremiumSms: boolPtr(false),
		AlertChannels: &model.AlertChannelsConfig{
			Email: boolPtr(true), Telegram: boolPtr(false), Sms: boolPtr(false), PremiumSms: boolPtr(false),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	buf, _ := json.Marshal(map[string]interface{}{
		"alert_channels": map[string]interface{}{
			"email": true, "telegram": true, "sms": false, "premium_sms": false,
		},
	})
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-2293-ac4-alarm", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded := loadPresetOrFail(t, s, "cp-2293-ac4-alarm")
	if loaded.AlertChannels == nil || loaded.AlertChannels.Telegram == nil || *loaded.AlertChannels.Telegram != true {
		t.Fatalf("expected alert_channels.telegram=true applied, got %+v", loaded.AlertChannels)
	}
	if loaded.SendTelegram == nil || *loaded.SendTelegram != true {
		t.Errorf("AC-4: send_telegram changed by an Alarme-Reiter PUT, expected unveraendert true, got %+v", loaded.SendTelegram)
	}
	if loaded.SendSms == nil || *loaded.SendSms != false {
		t.Errorf("AC-4: send_sms changed by an Alarme-Reiter PUT, expected unveraendert false, got %+v", loaded.SendSms)
	}
	if loaded.SendPremiumSms == nil || *loaded.SendPremiumSms != false {
		t.Errorf("AC-4: send_premium_sms changed by an Alarme-Reiter PUT, expected unveraendert false, got %+v", loaded.SendPremiumSms)
	}
}

// AC-4 Weg 2, beide Richtungen — analog Weg 1, ueber den Briefing-PUT.
func TestUpdateBriefingHandler_Vergleich_SendTelegramChangeLeavesAlertChannelsUnchanged(t *testing.T) {
	s := newTestStore(t)
	original := model.ComparePreset{
		ID: "cp-2293-ac4-weg2-versand", Name: "AC4-Weg2-Versand", UserID: "test",
		LocationIDs: []string{"loc-a"}, Schedule: "manual", Profil: "SUMMER_TREKKING",
		HourFrom: 8, HourTo: 17, Empfaenger: []string{"a@example.com"},
		SendTelegram: boolPtr(true),
		AlertChannels: &model.AlertChannelsConfig{
			Email: boolPtr(true), Telegram: boolPtr(false), Sms: boolPtr(false), PremiumSms: boolPtr(false),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	r := briefingVergleichEtagRouter(s)
	w := doReq(r, http.MethodPut, "/api/briefings/cp-2293-ac4-weg2-versand?kind=vergleich",
		`{"send_telegram":false}`, "", "test")
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded := loadPresetOrFail(t, s, "cp-2293-ac4-weg2-versand")
	if loaded.SendTelegram == nil || *loaded.SendTelegram != false {
		t.Errorf("expected send_telegram=false, got %+v", loaded.SendTelegram)
	}
	ac := loaded.AlertChannels
	if ac == nil || ac.Email == nil || *ac.Email != true || ac.Telegram == nil || *ac.Telegram != false {
		t.Errorf("AC-4 Weg 2: alert_channels changed by a Versand-Reiter Patch, expected unveraendert, got %+v", ac)
	}
}

func TestUpdateBriefingHandler_Vergleich_AlertChannelsChangeLeavesSendFlagsUnchanged(t *testing.T) {
	s := newTestStore(t)
	original := model.ComparePreset{
		ID: "cp-2293-ac4-weg2-alarm", Name: "AC4-Weg2-Alarm", UserID: "test",
		LocationIDs: []string{"loc-a"}, Schedule: "manual", Profil: "SUMMER_TREKKING",
		HourFrom: 8, HourTo: 17, Empfaenger: []string{"a@example.com"},
		SendTelegram: boolPtr(true), SendSms: boolPtr(false), SendPremiumSms: boolPtr(false),
		AlertChannels: &model.AlertChannelsConfig{
			Email: boolPtr(true), Telegram: boolPtr(false), Sms: boolPtr(false), PremiumSms: boolPtr(false),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	r := briefingVergleichEtagRouter(s)
	w := doReq(r, http.MethodPut, "/api/briefings/cp-2293-ac4-weg2-alarm?kind=vergleich",
		`{"alert_channels":{"email":true,"telegram":true,"sms":false,"premium_sms":false}}`, "", "test")
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded := loadPresetOrFail(t, s, "cp-2293-ac4-weg2-alarm")
	if loaded.AlertChannels == nil || loaded.AlertChannels.Telegram == nil || *loaded.AlertChannels.Telegram != true {
		t.Fatalf("expected alert_channels.telegram=true applied via Weg 2, got %+v", loaded.AlertChannels)
	}
	if loaded.SendTelegram == nil || *loaded.SendTelegram != true {
		t.Errorf("AC-4 Weg 2: send_telegram changed by an Alarme-Reiter Patch, expected unveraendert true, got %+v", loaded.SendTelegram)
	}
	if loaded.SendSms == nil || *loaded.SendSms != false {
		t.Errorf("AC-4 Weg 2: send_sms changed, expected unveraendert false, got %+v", loaded.SendSms)
	}
	if loaded.SendPremiumSms == nil || *loaded.SendPremiumSms != false {
		t.Errorf("AC-4 Weg 2: send_premium_sms changed, expected unveraendert false, got %+v", loaded.SendPremiumSms)
	}
}

// ═══════════════════════════ AC-5: Mandanten-Isolation ═════════════════════

// AC-5: zwei Nutzer setzen je die Alarm-Kanaele an einem gleichnamigen
// Preset — keiner sieht die Werte des anderen (eigenes Verzeichnis, eigener
// Store). Vorbild: compare_preset_alert_channel_thresholds_test.go Zeile 613.
func TestUpdateComparePreset_AlertChannelsCrossUserIsolation(t *testing.T) {
	s := newTestStore(t)

	presetA := model.ComparePreset{
		ID: "cp-2293-usera", Name: "Nutzer A", UserID: "usera",
		LocationIDs: []string{"loc-a"}, Schedule: "manual", Profil: "SUMMER_TREKKING",
		HourFrom: 8, HourTo: 17, Empfaenger: []string{"a@example.com"},
		AlertChannels: &model.AlertChannelsConfig{
			Email: boolPtr(true), Telegram: boolPtr(false), Sms: boolPtr(false), PremiumSms: boolPtr(false),
		},
		CreatedAt: time.Now().UTC(),
	}
	presetB := model.ComparePreset{
		ID: "cp-2293-userb", Name: "Nutzer B", UserID: "userb",
		LocationIDs: []string{"loc-b"}, Schedule: "manual", Profil: "SUMMER_TREKKING",
		HourFrom: 9, HourTo: 16, Empfaenger: []string{"b@example.com"},
		AlertChannels: &model.AlertChannelsConfig{
			Email: boolPtr(true), Telegram: boolPtr(false), Sms: boolPtr(false), PremiumSms: boolPtr(false),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.WithUser("usera").SaveComparePresets([]model.ComparePreset{presetA}); err != nil {
		t.Fatalf("SaveComparePresets usera: %v", err)
	}
	if err := s.WithUser("userb").SaveComparePresets([]model.ComparePreset{presetB}); err != nil {
		t.Fatalf("SaveComparePresets userb: %v", err)
	}

	// Nutzer A schaltet Telegram an.
	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	buf, _ := json.Marshal(map[string]interface{}{
		"alert_channels": map[string]interface{}{
			"email": true, "telegram": true, "sms": false, "premium_sms": false,
		},
	})
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-2293-usera", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "usera")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loadedA, err := s.WithUser("usera").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets usera: %v", err)
	}
	if loadedA[0].AlertChannels == nil || loadedA[0].AlertChannels.Telegram == nil || *loadedA[0].AlertChannels.Telegram != true {
		t.Errorf("expected usera telegram=true after PUT, got %+v", loadedA[0].AlertChannels)
	}

	loadedB, err := s.WithUser("userb").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets userb: %v", err)
	}
	if loadedB[0].Name != "Nutzer B" {
		t.Errorf("cross-user leak: userb's preset name changed to %q", loadedB[0].Name)
	}
	if loadedB[0].AlertChannels == nil || loadedB[0].AlertChannels.Telegram == nil || *loadedB[0].AlertChannels.Telegram != false {
		t.Errorf(
			"cross-user leak: userb's alert_channels changed by usera's PUT, expected unveraendert telegram=false, got %+v",
			loadedB[0].AlertChannels,
		)
	}
}

// ═══════════════════════════ AC-6: Neuanlage materialisiert ═══════════════

// AC-6: die Server-Antwort einer Neuanlage traegt sofort ein materialisiertes
// alert_channels-Objekt (Standard-Neuanlage ohne Opt-ins).
func TestCreateComparePresetHandler_AlertChannelsMaterializedInResponse(t *testing.T) {
	s := newTestStore(t)

	body := map[string]interface{}{
		"name": "Neuanlage-2293", "schedule": "manual", "profil": "SUMMER_TREKKING",
		"hour_from": 8, "hour_to": 17, "location_ids": []string{"loc-a"},
		"empfaenger": []string{"a@example.com"},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPost, "/api/compare/presets", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var resp model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	ac := resp.AlertChannels
	if ac == nil || ac.Email == nil || *ac.Email != true || ac.Telegram == nil || *ac.Telegram != false ||
		ac.Sms == nil || *ac.Sms != false || ac.PremiumSms == nil || *ac.PremiumSms != false {
		t.Fatalf(
			"AC-6: expected alert_channels={email:true,telegram:false,sms:false,premium_sms:false} in der Create-Response, got %+v",
			ac,
		)
	}

	loaded, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	if len(loaded) != 1 || loaded[0].AlertChannels == nil {
		t.Fatalf("expected 1 persisted preset with materialized alert_channels, got %+v", loaded)
	}
}

// AC-6 Adversary-Nachtrag (F002): eine Neuanlage MIT send_premium_sms=true
// und OHNE mitgeschicktes alert_channels behaelt send_premium_sms=true —
// sowohl in der Server-Antwort als auch in der persistierten Datei — und
// materialisiert zusaetzlich alert_channels.premium_sms=true. Die
// Altbestand-Bereinigung (send_premium_sms -> false) darf HIER NICHT greifen:
// sie ist ausschliesslich dem Lade-Pfad einer Bestandsdatei vorbehalten
// (normalizeLoadedComparePreset -> materializeAlertChannels(p, true)), nicht
// dem Create-Pfad (NormalizeComparePreset -> materializeAlertChannels(p,
// false)). Verfaelscht man dieses `false` zu `true`, faengt das kein anderer
// Test in dieser Datei: AC-6 selbst schickt kein send_premium_sms mit, AC-15/
// 16/17 pruefen ausschliesslich den Lade+PUT-Pfad einer bereits auf der
// Platte liegenden Datei, nie den frischen Create-Pfad.
func TestCreateComparePresetHandler_SendPremiumSmsWithoutAlertChannelsSurvivesCreate(t *testing.T) {
	s := newTestStore(t)

	body := map[string]interface{}{
		"name": "Neuanlage-2293-PremiumSms", "schedule": "manual", "profil": "SUMMER_TREKKING",
		"hour_from": 8, "hour_to": 17, "location_ids": []string{"loc-a"},
		"empfaenger": []string{"a@example.com"}, "send_premium_sms": true,
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPost, "/api/compare/presets", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var resp model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.SendPremiumSms == nil || *resp.SendPremiumSms != true {
		t.Errorf(
			"F002: expected send_premium_sms=true to survive Create ohne alert_channels im Body, got %+v",
			resp.SendPremiumSms,
		)
	}
	if resp.AlertChannels == nil || resp.AlertChannels.PremiumSms == nil || *resp.AlertChannels.PremiumSms != true {
		t.Errorf("F002: expected alert_channels.premium_sms=true in der Create-Response, got %+v", resp.AlertChannels)
	}

	loaded := loadPresetOrFail(t, s, resp.ID)
	if loaded.SendPremiumSms == nil || *loaded.SendPremiumSms != true {
		t.Errorf(
			"F002: expected persisted send_premium_sms=true (Create-Pfad darf NIE bereinigen), got %+v",
			loaded.SendPremiumSms,
		)
	}
	if loaded.AlertChannels == nil || loaded.AlertChannels.PremiumSms == nil || *loaded.AlertChannels.PremiumSms != true {
		t.Errorf("F002: expected persisted alert_channels.premium_sms=true, got %+v", loaded.AlertChannels)
	}
}

// ═══════════════════ AC-7: Legacy-GET materialisiert ohne Write-Back ══════

// AC-7: eine Legacy-Preset-Datei ohne alert_channels-Schluessel liefert per
// GET ein materialisiertes alert_channels-Objekt, aber die Datei auf der
// Festplatte bleibt byte-identisch (kein Write-Back durch reines Lesen).
func TestGetComparePresetHandler_LegacyPresetMaterializesAlertChannelsWithoutWriteBack(t *testing.T) {
	s := newTestStore(t)
	rawJSON := `{
		"id": "cp-2293-ac7",
		"name": "Legacy-AC7",
		"user_id": "test",
		"location_ids": ["loc-a"],
		"schedule": "manual",
		"profil": "SUMMER_TREKKING",
		"hour_from": 8,
		"hour_to": 17,
		"forecast_hours": 48,
		"empfaenger": ["a@example.com"],
		"created_at": "2026-01-01T00:00:00Z",
		"corridors": [],
		"kind": "vergleich",
		"morning_time": "06:00:00",
		"evening_time": "18:00:00",
		"morning_enabled": true,
		"evening_enabled": false,
		"send_telegram": true,
		"send_sms": false,
		"send_premium_sms": false
	}`
	writeRawComparePresetFixture(t, s, "test", "cp-2293-ac7", rawJSON)
	before := readRawComparePresetFixture(t, s, "test", "cp-2293-ac7")

	r := chi.NewRouter()
	r.Get("/api/compare/presets/{id}", GetComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodGet, "/api/compare/presets/cp-2293-ac7", nil)
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	ac := resp.AlertChannels
	if ac == nil || ac.Email == nil || *ac.Email != true || ac.Telegram == nil || *ac.Telegram != true ||
		ac.Sms == nil || *ac.Sms != false || ac.PremiumSms == nil || *ac.PremiumSms != false {
		t.Fatalf(
			"AC-7: expected materialized alert_channels={email:true,telegram:true,sms:false,premium_sms:false} in GET-response, got %+v",
			ac,
		)
	}

	after := readRawComparePresetFixture(t, s, "test", "cp-2293-ac7")
	if !bytes.Equal(before, after) {
		t.Errorf(
			"AC-7: GET schrieb die Legacy-Datei zurueck (Write-Back), Bestand vorher/nachher unterscheidet sich:\nvorher:  %s\nnachher: %s",
			before, after,
		)
	}
}

// ═══════════════ AC-3 (Go-Teil): 8-Kombinationen-Materialisierungstabelle ═

// AC-3 (Go-Teil): fuer alle 8 Kombinationen der flachen Kanal-Felder
// materialisiert ein Legacy-GET exakt {email:true, telegram:<flach>,
// sms:<flach>, premium_sms:<flach>} — die Materialisierung veraendert kein
// beobachtbares Alarmverhalten gegenueber der vorherigen, rein flachen
// Auflösung (resolve_alert_channels, Python-Seite, unveraendert).
func TestGetComparePresetHandler_LegacyFlatChannelsMaterializeToAlertChannelsAllCombinations(t *testing.T) {
	combos := []struct {
		telegram, sms, premiumSms bool
	}{
		{false, false, false},
		{true, false, false},
		{false, true, false},
		{false, false, true},
		{true, true, false},
		{true, false, true},
		{false, true, true},
		{true, true, true},
	}

	for i, c := range combos {
		s := newTestStore(t)
		id := "cp-2293-ac3-combo"
		rawJSON := `{
			"id": "` + id + `",
			"name": "Combo",
			"user_id": "test",
			"location_ids": ["loc-a"],
			"schedule": "manual",
			"profil": "SUMMER_TREKKING",
			"hour_from": 8,
			"hour_to": 17,
			"forecast_hours": 48,
			"empfaenger": ["a@example.com"],
			"created_at": "2026-01-01T00:00:00Z",
			"corridors": [],
			"kind": "vergleich",
			"morning_time": "06:00:00",
			"evening_time": "18:00:00",
			"morning_enabled": true,
			"evening_enabled": false,
			"send_telegram": ` + boolJSON(c.telegram) + `,
			"send_sms": ` + boolJSON(c.sms) + `,
			"send_premium_sms": ` + boolJSON(c.premiumSms) + `
		}`
		writeRawComparePresetFixture(t, s, "test", id, rawJSON)

		r := chi.NewRouter()
		r.Get("/api/compare/presets/{id}", GetComparePresetHandler(s))
		req := httptest.NewRequest(http.MethodGet, "/api/compare/presets/"+id, nil)
		req = addUserToContext(req, "test")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("combo %d: expected 200, got %d: %s", i, w.Code, w.Body.String())
		}
		var resp model.ComparePreset
		if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
			t.Fatalf("combo %d: decode response: %v", i, err)
		}
		ac := resp.AlertChannels
		if ac == nil || ac.Email == nil || *ac.Email != true ||
			ac.Telegram == nil || *ac.Telegram != c.telegram ||
			ac.Sms == nil || *ac.Sms != c.sms ||
			ac.PremiumSms == nil || *ac.PremiumSms != c.premiumSms {
			t.Errorf(
				"combo %d (telegram=%v,sms=%v,premium_sms=%v): expected alert_channels={email:true,telegram:%v,sms:%v,premium_sms:%v}, got %+v",
				i, c.telegram, c.sms, c.premiumSms, c.telegram, c.sms, c.premiumSms, ac,
			)
		}
	}
}

func boolJSON(b bool) string {
	if b {
		return "true"
	}
	return "false"
}

// ═════════════ AC-15/16/17 (Nachtrag): Altbestand-Bereinigung Premium-SMS ═

// AC-15 (Go-Teil): ein Altbestand ohne alert_channels mit
// send_premium_sms=true verliert diesen Briefing-Kanal, sobald das Preset
// ueber Go geladen und per PUT gespeichert wird — bleibt aber als Alarm-Kanal
// (alert_channels.premium_sms=true) erhalten.
func TestUpdateComparePresetHandler_LegacyPremiumSmsWithoutAlertChannelsClearedOnSave(t *testing.T) {
	s := newTestStore(t)
	id := "cp-2293-ac15"
	rawJSON := `{
		"id": "` + id + `",
		"name": "Legacy-AC15",
		"user_id": "test",
		"location_ids": ["loc-a"],
		"schedule": "manual",
		"profil": "SUMMER_TREKKING",
		"hour_from": 8,
		"hour_to": 17,
		"forecast_hours": 48,
		"empfaenger": ["a@example.com"],
		"created_at": "2026-01-01T00:00:00Z",
		"corridors": [],
		"kind": "vergleich",
		"morning_time": "06:00:00",
		"evening_time": "18:00:00",
		"morning_enabled": true,
		"evening_enabled": false,
		"send_telegram": false,
		"send_sms": false,
		"send_premium_sms": true
	}`
	writeRawComparePresetFixture(t, s, "test", id, rawJSON)

	// PUT aendert nur den Namen — loest Load(materialisiert+bereinigt)+Save aus.
	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	buf, _ := json.Marshal(map[string]interface{}{"name": "Legacy-AC15 (umbenannt)"})
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/"+id, bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded := loadPresetOrFail(t, s, id)
	if loaded.SendPremiumSms == nil || *loaded.SendPremiumSms != false {
		t.Errorf("AC-15: expected send_premium_sms=false after Go-Load+PUT (Bereinigung), got %+v", loaded.SendPremiumSms)
	}
	if loaded.AlertChannels == nil || loaded.AlertChannels.PremiumSms == nil || *loaded.AlertChannels.PremiumSms != true {
		t.Errorf("AC-15: expected alert_channels.premium_sms=true (Alarm-Kanal unveraendert), got %+v", loaded.AlertChannels)
	}
}

// AC-16 (Gegenprobe): ein Preset MIT bereits gesetztem alert_channels und
// send_premium_sms=true (vom neuen Versand-Schalter gesetzt) behaelt
// send_premium_sms=true — die Bereinigung greift ausschliesslich bei
// fehlendem alert_channels.
func TestUpdateComparePresetHandler_PremiumSmsWithAlertChannelsSurvivesSave(t *testing.T) {
	s := newTestStore(t)
	id := "cp-2293-ac16"
	rawJSON := `{
		"id": "` + id + `",
		"name": "AC16-Test",
		"user_id": "test",
		"location_ids": ["loc-a"],
		"schedule": "manual",
		"profil": "SUMMER_TREKKING",
		"hour_from": 8,
		"hour_to": 17,
		"forecast_hours": 48,
		"empfaenger": ["a@example.com"],
		"created_at": "2026-01-01T00:00:00Z",
		"corridors": [],
		"kind": "vergleich",
		"morning_time": "06:00:00",
		"evening_time": "18:00:00",
		"morning_enabled": true,
		"evening_enabled": false,
		"send_premium_sms": true,
		"alert_channels": {"email": true, "telegram": false, "sms": false, "premium_sms": true}
	}`
	writeRawComparePresetFixture(t, s, "test", id, rawJSON)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	buf, _ := json.Marshal(map[string]interface{}{"name": "AC16-Test (umbenannt)"})
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/"+id, bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded := loadPresetOrFail(t, s, id)
	if loaded.SendPremiumSms == nil || *loaded.SendPremiumSms != true {
		t.Errorf("AC-16: expected send_premium_sms=true to survive (alert_channels was already set), got %+v", loaded.SendPremiumSms)
	}
	if loaded.AlertChannels == nil || loaded.AlertChannels.PremiumSms == nil || *loaded.AlertChannels.PremiumSms != true {
		t.Errorf("AC-16: expected alert_channels.premium_sms=true unveraendert, got %+v", loaded.AlertChannels)
	}
}

// AC-17 (Mandanten-Test): zwei Nutzer mit je einem Altbestand ohne
// alert_channels und send_premium_sms=true — jeder wird bei Load+Save nur
// fuer sein EIGENES Preset bereinigt, keine Vermischung zwischen den
// Nutzerverzeichnissen.
func TestUpdateComparePresetHandler_LegacyPremiumSmsCleanupIsolatedPerUser(t *testing.T) {
	s := newTestStore(t)
	rawJSONFor := func(id, user string) string {
		return `{
			"id": "` + id + `",
			"name": "AC17-` + user + `",
			"user_id": "` + user + `",
			"location_ids": ["loc-a"],
			"schedule": "manual",
			"profil": "SUMMER_TREKKING",
			"hour_from": 8,
			"hour_to": 17,
			"forecast_hours": 48,
			"empfaenger": ["a@example.com"],
			"created_at": "2026-01-01T00:00:00Z",
			"corridors": [],
			"kind": "vergleich",
			"morning_time": "06:00:00",
			"evening_time": "18:00:00",
			"morning_enabled": true,
			"evening_enabled": false,
			"send_premium_sms": true
		}`
	}
	writeRawComparePresetFixture(t, s, "usera17", "cp-2293-ac17-a", rawJSONFor("cp-2293-ac17-a", "usera17"))
	writeRawComparePresetFixture(t, s, "userb17", "cp-2293-ac17-b", rawJSONFor("cp-2293-ac17-b", "userb17"))

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))

	putRename := func(id, user, newName string) {
		buf, _ := json.Marshal(map[string]interface{}{"name": newName})
		req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/"+id, bytes.NewReader(buf))
		req.Header.Set("Content-Type", "application/json")
		req = addUserToContext(req, user)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != http.StatusOK {
			t.Fatalf("PUT %s (%s): expected 200, got %d: %s", id, user, w.Code, w.Body.String())
		}
	}
	putRename("cp-2293-ac17-a", "usera17", "AC17-usera17 (umbenannt)")
	putRename("cp-2293-ac17-b", "userb17", "AC17-userb17 (umbenannt)")

	loadedA := loadPresetOrFail(t, s.WithUser("usera17"), "cp-2293-ac17-a")
	if loadedA.SendPremiumSms == nil || *loadedA.SendPremiumSms != false {
		t.Errorf("AC-17: usera17 not cleaned up, expected send_premium_sms=false, got %+v", loadedA.SendPremiumSms)
	}
	if loadedA.AlertChannels == nil || loadedA.AlertChannels.PremiumSms == nil || *loadedA.AlertChannels.PremiumSms != true {
		t.Errorf("AC-17: usera17 alert_channels.premium_sms should be true, got %+v", loadedA.AlertChannels)
	}

	loadedB := loadPresetOrFail(t, s.WithUser("userb17"), "cp-2293-ac17-b")
	if loadedB.SendPremiumSms == nil || *loadedB.SendPremiumSms != false {
		t.Errorf("AC-17: userb17 not cleaned up, expected send_premium_sms=false, got %+v", loadedB.SendPremiumSms)
	}
	if loadedB.AlertChannels == nil || loadedB.AlertChannels.PremiumSms == nil || *loadedB.AlertChannels.PremiumSms != true {
		t.Errorf("AC-17: userb17 alert_channels.premium_sms should be true, got %+v", loadedB.AlertChannels)
	}
	if loadedB.Name != "AC17-userb17 (umbenannt)" {
		t.Errorf("cross-user leak: userb17 name unexpected: %q", loadedB.Name)
	}
}
