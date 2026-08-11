package handler

// Issue #1461 Scheibe S3b-2b (AC-9/AC-10) — AlertChannelThresholds-Pointer-
// Feld auf ComparePreset: ZWEI Ebenen Datenverlustschutz auf ZWEI Schreib-
// wegen, alle vier Kombinationen Pflicht (nicht Kann):
//
//   Ebene 1 (AC-9): Top-Level-nil-Erbe — ein PUT ohne das Feld darf einen
//   zuvor gesetzten Wert nicht loeschen.
//   Ebene 2 (AC-10): Feld-Level-Merge INNERHALB des Unterobjekts — ein PUT,
//   das nur EINEN Kanal mitschickt, darf den anderen nicht loeschen.
//
//   Weg 1: PUT /api/compare/presets/{id} (compare_preset.go, Handarbeit,
//   volles model.ComparePreset als Decode-Ziel — UMGEKEHRTE Polaritaet zum
//   Trip: „if updated.X == nil { updated.X = original.X }“, nicht
//   „if req.X != nil { … }“ wie beim Trip-Pointer-DTO).
//   Weg 2: PUT /api/briefings/{id}?kind=vergleich (briefing_subscription.go,
//   mergeBriefingPatch — generischer JSON-Merge, der ein neues Feld
//   VORAUSSICHTLICH automatisch traegt; die Spec verlangt das zu BELEGEN,
//   nicht anzunehmen).
//
// Vorlage Ebene 1/Weg 1: compare_preset_official_warnings_test.go (Issue
// #1258) — derselbe Praezedenzfall, dort fuer OfficialWarningsConfig.
// Vorlage Weg 2: briefing_subscription_vergleich_etag_test.go (Issue #1395
// S6) fuer den Router-Aufbau (briefingVergleichEtagRouter, doReq, mustETag —
// alle im selben Paket, hier wiederverwendet statt dupliziert).
//
// RED-Grund heute: `model.ComparePreset` hat KEIN `AlertChannelThresholds`-
// Feld — dieser Testfile kompiliert nicht (Compile-Error, dieselbe
// RED-Bauform wie ein fehlendes Python-Modul/ImportError, s. z.B.
// tests/tdd/test_compare_radar_alert.py Modul-Docstring). Nach dem Anlegen
// des Feldes (analog trip.go:202, selbes Package, kein neuer Typ) kompiliert
// die Datei, faellt aber ohne den Preserve-Block in TestUpdateComparePreset_
// AlertChannelThresholds* rot durch — genau der in der Spec beschriebene
// Datenverlust.
//
// Spec: docs/specs/modules/feat_1461_s3b2b_compare_kanal_schwelle.md AC-9/AC-10.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
)

func alertThresholdStrPtr(s string) *string { return &s }

// ═══════════════════════════ Weg 1: PUT /api/compare/presets/{id} ═════════

// AC-9 (Ebene 1, Weg 1): PUT ohne alert_channel_thresholds im Body laesst
// eine zuvor gesetzte Schwelle unveraendert.
func TestUpdateComparePreset_AlertChannelThresholdsPreservedWhenBodyOmitsIt(t *testing.T) {
	s := newTestStore(t)

	original := model.ComparePreset{
		ID:          "cp-1461-ac9",
		Name:        "AC9-Test",
		UserID:      "user1",
		LocationIDs: []string{"loc-a"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{
			Telegram: alertThresholdStrPtr("HIGH"),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	// PUT-Body OHNE alert_channel_thresholds — nur "name" geaendert (Muster
	// compare_preset_official_warnings_test.go: der Preset-PUT ist ein
	// Voll-Ersetzen, Pflichtfelder muessen im Body erneut stehen).
	body := map[string]interface{}{
		"name":         "AC9-Test (umbenannt)",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    8,
		"hour_to":      17,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-1461-ac9", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	p := loaded[0]
	if p.AlertChannelThresholds == nil || p.AlertChannelThresholds.Telegram == nil ||
		*p.AlertChannelThresholds.Telegram != "HIGH" {
		t.Errorf(
			"alert_channel_thresholds erased by PUT without field: expected telegram=HIGH, got %+v",
			p.AlertChannelThresholds,
		)
	}
	if p.Name != "AC9-Test (umbenannt)" {
		t.Errorf("expected name updated, got %q", p.Name)
	}
}

// AC-10 (Ebene 2, Weg 1): PUT, das nur EINEN der zwei zuvor gesetzten Kanaele
// mitschickt, darf den anderen, nicht angefassten Kanal nicht loeschen.
func TestUpdateComparePreset_AlertChannelThresholdsFieldLevelMergePreservesUntouchedChannel(t *testing.T) {
	s := newTestStore(t)

	original := model.ComparePreset{
		ID:          "cp-1461-ac10",
		Name:        "AC10-Test",
		UserID:      "user1",
		LocationIDs: []string{"loc-a"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{
			Email:    alertThresholdStrPtr("MODERATE"),
			Telegram: alertThresholdStrPtr("HIGH"),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	// PUT aendert NUR telegram, email fehlt im Unterobjekt komplett.
	body := map[string]interface{}{
		"name":         "AC10-Test",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    8,
		"hour_to":      17,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
		"alert_channel_thresholds": map[string]interface{}{
			"telegram": "LOW",
		},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-1461-ac10", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	p := loaded[0]
	if p.AlertChannelThresholds == nil || p.AlertChannelThresholds.Telegram == nil ||
		*p.AlertChannelThresholds.Telegram != "LOW" {
		t.Fatalf("expected telegram=LOW applied, got %+v", p.AlertChannelThresholds)
	}
	if p.AlertChannelThresholds.Email == nil || *p.AlertChannelThresholds.Email != "MODERATE" {
		t.Errorf(
			"AC-10: email erased by telegram-only PUT, expected MODERATE (unangetastet), got %+v",
			p.AlertChannelThresholds.Email,
		)
	}
}

// Issue #1701 (S2b, D6): vierter Schwellenwert-Fall fuer den Ortsvergleich
// -- identisches Feld-Level-Merge-Muster wie oben, jetzt fuer PremiumSms.
func TestUpdateComparePreset_AlertChannelThresholdsPremiumSmsFieldLevelMerge(t *testing.T) {
	s := newTestStore(t)

	original := model.ComparePreset{
		ID:          "cp-1701-thr-premium",
		Name:        "PremiumSms-Threshold-Test",
		UserID:      "user1",
		LocationIDs: []string{"loc-a"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{
			Email:      alertThresholdStrPtr("MODERATE"),
			PremiumSms: alertThresholdStrPtr("HIGH"),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	// PUT aendert NUR email, premium_sms fehlt im Unterobjekt komplett.
	body := map[string]interface{}{
		"name":         "PremiumSms-Threshold-Test",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    8,
		"hour_to":      17,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
		"alert_channel_thresholds": map[string]interface{}{
			"email": "LOW",
		},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-1701-thr-premium", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	p := loaded[0]
	if p.AlertChannelThresholds == nil || p.AlertChannelThresholds.Email == nil ||
		*p.AlertChannelThresholds.Email != "LOW" {
		t.Fatalf("expected email=LOW applied, got %+v", p.AlertChannelThresholds)
	}
	if p.AlertChannelThresholds.PremiumSms == nil || *p.AlertChannelThresholds.PremiumSms != "HIGH" {
		t.Errorf(
			"premium_sms erased by email-only PUT, expected HIGH (unangetastet), got %+v",
			p.AlertChannelThresholds.PremiumSms,
		)
	}
}

// F002 (Adversary HIGH, Fix-Loop 1): der bestehende AC-10-Test oben deckt nur
// eine Merge-Richtung ab (Body traegt telegram, prueft dass email erhalten
// bleibt) — Email und Sms als Preserve-Zeilen (compare_preset.go:425-430)
// waren dadurch UNBEWACHT: eine entfernte Telegram- oder Sms-Preserve-Zeile
// faerbte KEINEN Test rot. Die beiden folgenden Tests pruefen die jeweils
// ANDERE Merge-Richtung (Body traegt email bzw. sms, die beiden NICHT
// gesendeten Kanaele muessen erhalten bleiben) — analog fuer Weg 2 unten.

// AC-10 (Ebene 2, Weg 1, F002-Ergaenzung): PUT traegt NUR email — telegram
// UND sms (beide zuvor gesetzt) muessen erhalten bleiben.
func TestUpdateComparePreset_AlertChannelThresholdsFieldLevelMergePreservesTelegramAndSmsWhenOnlyEmailSet(t *testing.T) {
	s := newTestStore(t)

	original := model.ComparePreset{
		ID:          "cp-1461-f002-email",
		Name:        "F002-Email-Test",
		UserID:      "user1",
		LocationIDs: []string{"loc-a"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{
			Email:    alertThresholdStrPtr("LOW"),
			Telegram: alertThresholdStrPtr("HIGH"),
			Sms:      alertThresholdStrPtr("MODERATE"),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	// PUT aendert NUR email, telegram und sms fehlen im Unterobjekt komplett.
	body := map[string]interface{}{
		"name":         "F002-Email-Test",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    8,
		"hour_to":      17,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
		"alert_channel_thresholds": map[string]interface{}{
			"email": "HIGH",
		},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-1461-f002-email", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	p := loaded[0]
	if p.AlertChannelThresholds == nil || p.AlertChannelThresholds.Email == nil ||
		*p.AlertChannelThresholds.Email != "HIGH" {
		t.Fatalf("expected email=HIGH applied, got %+v", p.AlertChannelThresholds)
	}
	if p.AlertChannelThresholds.Telegram == nil || *p.AlertChannelThresholds.Telegram != "HIGH" {
		t.Errorf(
			"F002: telegram erased by email-only PUT, expected HIGH (unangetastet), got %+v",
			p.AlertChannelThresholds.Telegram,
		)
	}
	if p.AlertChannelThresholds.Sms == nil || *p.AlertChannelThresholds.Sms != "MODERATE" {
		t.Errorf(
			"F002: sms erased by email-only PUT, expected MODERATE (unangetastet), got %+v",
			p.AlertChannelThresholds.Sms,
		)
	}
}

// AC-10 (Ebene 2, Weg 1, F002-Ergaenzung): PUT traegt NUR sms — email UND
// telegram (beide zuvor gesetzt) muessen erhalten bleiben.
func TestUpdateComparePreset_AlertChannelThresholdsFieldLevelMergePreservesEmailAndTelegramWhenOnlySmsSet(t *testing.T) {
	s := newTestStore(t)

	original := model.ComparePreset{
		ID:          "cp-1461-f002-sms",
		Name:        "F002-Sms-Test",
		UserID:      "user1",
		LocationIDs: []string{"loc-a"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{
			Email:    alertThresholdStrPtr("LOW"),
			Telegram: alertThresholdStrPtr("HIGH"),
			Sms:      alertThresholdStrPtr("MODERATE"),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	// PUT aendert NUR sms, email und telegram fehlen im Unterobjekt komplett.
	body := map[string]interface{}{
		"name":         "F002-Sms-Test",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    8,
		"hour_to":      17,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
		"alert_channel_thresholds": map[string]interface{}{
			"sms": "HIGH",
		},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-1461-f002-sms", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	p := loaded[0]
	if p.AlertChannelThresholds == nil || p.AlertChannelThresholds.Sms == nil ||
		*p.AlertChannelThresholds.Sms != "HIGH" {
		t.Fatalf("expected sms=HIGH applied, got %+v", p.AlertChannelThresholds)
	}
	if p.AlertChannelThresholds.Email == nil || *p.AlertChannelThresholds.Email != "LOW" {
		t.Errorf(
			"F002: email erased by sms-only PUT, expected LOW (unangetastet), got %+v",
			p.AlertChannelThresholds.Email,
		)
	}
	if p.AlertChannelThresholds.Telegram == nil || *p.AlertChannelThresholds.Telegram != "HIGH" {
		t.Errorf(
			"F002: telegram erased by sms-only PUT, expected HIGH (unangetastet), got %+v",
			p.AlertChannelThresholds.Telegram,
		)
	}
}

// F005 (Adversary HIGH, Fix-Loop 2): der HAEUFIGSTE Alltagspfad war
// unbewacht — ein frisches Preset OHNE `alert_channel_thresholds`
// (`original.AlertChannelThresholds == nil`), dessen Nutzer zum ersten Mal
// EINEN Kanal einstellt. Alle bisherigen Tests legten `original` bereits mit
// vollstaendig gesetzten Schwellen an; der aeussere Guard
// `original.AlertChannelThresholds != nil` (compare_preset.go:421), der die
// drei Feld-Preserve-Zeilen umschliesst, wurde dadurch von KEINEM Test
// durchlaufen. Ohne ihn: nil-pointer-Panic (SIGSEGV) beim Zugriff auf
// `original.AlertChannelThresholds.Email` — ein 500er fuer den
// wahrscheinlichsten Fall im echten Betrieb.
func TestUpdateComparePreset_AlertChannelThresholdsFirstTimeSetOnFreshPresetNoPanic(t *testing.T) {
	s := newTestStore(t)

	// original traegt bewusst KEIN AlertChannelThresholds-Feld (nil) —
	// der Alltagsfall "noch nie eine Schwelle gesetzt".
	original := model.ComparePreset{
		ID:          "cp-1461-f005",
		Name:        "F005-Test",
		UserID:      "user1",
		LocationIDs: []string{"loc-a"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		CreatedAt:   time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	// PUT setzt zum ERSTEN Mal EINEN Kanal (telegram).
	body := map[string]interface{}{
		"name":         "F005-Test",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    8,
		"hour_to":      17,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
		"alert_channel_thresholds": map[string]interface{}{
			"telegram": "HIGH",
		},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-1461-f005", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 (KEIN Panic), got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	p := loaded[0]
	if p.AlertChannelThresholds == nil || p.AlertChannelThresholds.Telegram == nil ||
		*p.AlertChannelThresholds.Telegram != "HIGH" {
		t.Fatalf("expected telegram=HIGH applied, got %+v", p.AlertChannelThresholds)
	}
	if p.AlertChannelThresholds.Email != nil {
		t.Errorf("F005: email darf beim ersten Setzen nicht miterfunden werden, got %+v", p.AlertChannelThresholds.Email)
	}
	if p.AlertChannelThresholds.Sms != nil {
		t.Errorf("F005: sms darf beim ersten Setzen nicht miterfunden werden, got %+v", p.AlertChannelThresholds.Sms)
	}
}

// Gegenprobe: ein neu angelegter Ortsvergleich ohne alert_channel_thresholds
// bleibt nil (Startwert "LOW" je Kanal wird von Python code-seitig
// angenommen, nicht hier persistiert — Muster
// TestCreateTripHandler_AlertChannelThresholdsDefaultsNil).
func TestCreateComparePresetHandler_AlertChannelThresholdsDefaultsNil(t *testing.T) {
	s := newTestStore(t)

	body := map[string]interface{}{
		"name":         "Neuanlage",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    8,
		"hour_to":      17,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPost, "/api/compare/presets", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var resp model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.AlertChannelThresholds != nil {
		t.Errorf("expected nil alert_channel_thresholds in response, got %+v", resp.AlertChannelThresholds)
	}

	loaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	if len(loaded) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(loaded))
	}
	if loaded[0].AlertChannelThresholds != nil {
		t.Errorf("expected nil alert_channel_thresholds on a fresh preset, got %+v", loaded[0].AlertChannelThresholds)
	}
}

// AC-14 (Vollstaendigkeitspruefung Fix-Loop 3, Punkt 2): die Gegenprobe oben
// belegt nur "ohne Feld bleibt nil" — es fehlte ein Test dafuer, dass ein
// POST MIT gesetzten Schwellen sie auch tatsaechlich speichert (genau die
// AC, die der PO frisch entschieden hat: Stufe beim Anlegen setzbar). Der
// Weg ist strukturell da (CreateComparePresetHandler dekodiert das ganze
// Struct, compare_preset.go:198-201), aber bis hierhin unbewacht.
func TestCreateComparePresetHandler_AlertChannelThresholdsPersistedWhenSet(t *testing.T) {
	s := newTestStore(t)

	body := map[string]interface{}{
		"name":         "Neuanlage-Mit-Schwelle",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    8,
		"hour_to":      17,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
		"alert_channel_thresholds": map[string]interface{}{
			"telegram": "HIGH",
		},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPost, "/api/compare/presets", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var resp model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.AlertChannelThresholds == nil || resp.AlertChannelThresholds.Telegram == nil ||
		*resp.AlertChannelThresholds.Telegram != "HIGH" {
		t.Fatalf(
			"AC-14: expected telegram=HIGH in der Create-Response, got %+v",
			resp.AlertChannelThresholds,
		)
	}

	loaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	if len(loaded) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(loaded))
	}
	if loaded[0].AlertChannelThresholds == nil || loaded[0].AlertChannelThresholds.Telegram == nil ||
		*loaded[0].AlertChannelThresholds.Telegram != "HIGH" {
		t.Errorf(
			"AC-14: expected telegram=HIGH on the PERSISTED preset, got %+v",
			loaded[0].AlertChannelThresholds,
		)
	}
}

// Mandantentrennung (CLAUDE.md-Pflicht, F004-Muster): Nutzer A aendert die
// Schwelle SEINES Presets — der gleichnamige Preset von Nutzer B (eigenes
// Verzeichnis, eigener Store) bleibt unangetastet.
func TestUpdateComparePreset_AlertChannelThresholdsCrossUserIsolation(t *testing.T) {
	s := newTestStore(t)

	presetA := model.ComparePreset{
		ID:          "cp-1461-usera",
		Name:        "Nutzer A",
		UserID:      "usera",
		LocationIDs: []string{"loc-a"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{
			Telegram: alertThresholdStrPtr("LOW"),
		},
		CreatedAt: time.Now().UTC(),
	}
	presetB := model.ComparePreset{
		ID:          "cp-1461-userb",
		Name:        "Nutzer B",
		UserID:      "userb",
		LocationIDs: []string{"loc-b"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    9,
		HourTo:      16,
		Empfaenger:  []string{"b@example.com"},
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{
			Telegram: alertThresholdStrPtr("MODERATE"),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.WithUser("usera").SaveComparePresets([]model.ComparePreset{presetA}); err != nil {
		t.Fatalf("SaveComparePresets usera: %v", err)
	}
	if err := s.WithUser("userb").SaveComparePresets([]model.ComparePreset{presetB}); err != nil {
		t.Fatalf("SaveComparePresets userb: %v", err)
	}

	// Nutzer A setzt telegram auf HIGH ueber PUT.
	body := map[string]interface{}{
		"name":         "Nutzer A",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    8,
		"hour_to":      17,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
		"alert_channel_thresholds": map[string]interface{}{
			"telegram": "HIGH",
		},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-1461-usera", bytes.NewReader(buf))
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
	if loadedA[0].AlertChannelThresholds == nil || loadedA[0].AlertChannelThresholds.Telegram == nil ||
		*loadedA[0].AlertChannelThresholds.Telegram != "HIGH" {
		t.Errorf("expected usera telegram=HIGH after PUT, got %+v", loadedA[0].AlertChannelThresholds)
	}

	// Nutzer B's gleichnamiger Preset darf weder Name noch Schwelle verlieren.
	loadedB, err := s.WithUser("userb").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets userb: %v", err)
	}
	if loadedB[0].Name != "Nutzer B" {
		t.Errorf("cross-user leak: userb's preset name changed to %q", loadedB[0].Name)
	}
	if loadedB[0].AlertChannelThresholds == nil || loadedB[0].AlertChannelThresholds.Telegram == nil ||
		*loadedB[0].AlertChannelThresholds.Telegram != "MODERATE" {
		t.Errorf(
			"cross-user leak: userb's alert_channel_thresholds changed by usera's PUT, "+
				"expected unveraendert telegram=MODERATE (Nutzer B's eigener Ursprungswert, "+
				"NICHT usera's neuer Wert HIGH), got %+v",
			loadedB[0].AlertChannelThresholds,
		)
	}
}

// ═══════════════════ Weg 2: PUT /api/briefings/{id}?kind=vergleich ════════
//
// AC-9 verlangt ausdruecklich BEIDE Schreibwege — waere nur Weg 1
// abgesichert, bliebe Weg 2 eine Umgehung (Muster briefing_subscription_
// vergleich_etag_test.go Modul-Kommentar: „Waere nur einer der beiden Wege
// abgesichert, bliebe der andere eine Umgehung“).
//
// briefingVergleichEtagRouter/doReq/mustETag sind package-intern und bereits
// definiert (briefing_subscription_vergleich_etag_test.go) — dasselbe Paket,
// keine zweite Fassung.

// AC-9 (Ebene 1, Weg 2): ein Patch, der alert_channel_thresholds GAR NICHT
// mitschickt, darf eine zuvor gesetzte Schwelle nicht loeschen — der
// generische mergeBriefingPatch-Merge muss das TRAGEN, nicht nur zufaellig
// treffen (Spec: „voraussichtlich automatisch — trotzdem mit Test zu
// belegen, nicht anzunehmen“).
func TestUpdateBriefingHandler_Vergleich_AlertChannelThresholdsPreservedWhenPatchOmitsIt(t *testing.T) {
	s := newTestStore(t)

	original := model.ComparePreset{
		ID:          "cp-1461-brief-ac9",
		Name:        "Brief-AC9-Test",
		UserID:      "test",
		LocationIDs: []string{"loc-a"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{
			Telegram: alertThresholdStrPtr("HIGH"),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	r := briefingVergleichEtagRouter(s)
	// Patch: NUR "name" geaendert, alert_channel_thresholds fehlt komplett
	// (kein Voll-Ersetzen wie Weg 1 — mergeBriefingPatch ist ein echter
	// Patch, andere Felder duerfen deshalb im Body fehlen).
	w := doReq(r, http.MethodPut, "/api/briefings/cp-1461-brief-ac9?kind=vergleich",
		`{"name":"Brief-AC9-Test (umbenannt)"}`, "", "test")

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded := loadPresetOrFail(t, s, "cp-1461-brief-ac9")
	if loaded.AlertChannelThresholds == nil || loaded.AlertChannelThresholds.Telegram == nil ||
		*loaded.AlertChannelThresholds.Telegram != "HIGH" {
		t.Errorf(
			"Weg 2: alert_channel_thresholds erased by patch without field: expected telegram=HIGH, got %+v",
			loaded.AlertChannelThresholds,
		)
	}
	if loaded.Name != "Brief-AC9-Test (umbenannt)" {
		t.Errorf("expected name updated, got %q", loaded.Name)
	}
}

// AC-10 (Ebene 2, Weg 2): ein Patch, der NUR einen Kanal mitschickt, darf den
// anderen, nicht angefassten Kanal ueber diesen Schreibweg ebenfalls nicht
// loeschen. Wird ueber mergeConfigMap (config_merge.go) generisch erwartet —
// dieser Test belegt es, statt es aus Weg 1 anzunehmen.
func TestUpdateBriefingHandler_Vergleich_AlertChannelThresholdsFieldLevelMergePreservesUntouchedChannel(t *testing.T) {
	s := newTestStore(t)

	original := model.ComparePreset{
		ID:          "cp-1461-brief-ac10",
		Name:        "Brief-AC10-Test",
		UserID:      "test",
		LocationIDs: []string{"loc-a"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{
			Email:    alertThresholdStrPtr("MODERATE"),
			Telegram: alertThresholdStrPtr("HIGH"),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	r := briefingVergleichEtagRouter(s)
	w := doReq(r, http.MethodPut, "/api/briefings/cp-1461-brief-ac10?kind=vergleich",
		`{"alert_channel_thresholds":{"telegram":"LOW"}}`, "", "test")

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded := loadPresetOrFail(t, s, "cp-1461-brief-ac10")
	if loaded.AlertChannelThresholds == nil || loaded.AlertChannelThresholds.Telegram == nil ||
		*loaded.AlertChannelThresholds.Telegram != "LOW" {
		t.Fatalf("expected telegram=LOW applied via Weg 2, got %+v", loaded.AlertChannelThresholds)
	}
	if loaded.AlertChannelThresholds.Email == nil || *loaded.AlertChannelThresholds.Email != "MODERATE" {
		t.Errorf(
			"Weg 2: email erased by telegram-only patch, expected MODERATE (unangetastet), got %+v",
			loaded.AlertChannelThresholds.Email,
		)
	}
}

// F002 (Adversary HIGH, Fix-Loop 1), Weg 2: dieselbe Luecke wie bei Weg 1 —
// der bestehende AC-10-Test fuer Weg 2 prueft nur, dass ein telegram-only
// Patch die Email-Preserve-Zeile nicht bricht. Die beiden folgenden Tests
// pruefen die andere Merge-Richtung ueber `mergeConfigMap` (config_merge.go),
// die generisch fuer ALLE drei Kanaele gelten muss — nicht aus Weg 1
// annehmen, sondern hier eigenstaendig belegen (Muster des bestehenden
// Weg-2-Tests).

// AC-10 (Ebene 2, Weg 2, F002-Ergaenzung): ein Patch, der NUR email
// mitschickt, darf telegram UND sms ueber diesen Schreibweg nicht loeschen.
func TestUpdateBriefingHandler_Vergleich_AlertChannelThresholdsFieldLevelMergePreservesTelegramAndSmsWhenOnlyEmailSet(t *testing.T) {
	s := newTestStore(t)

	original := model.ComparePreset{
		ID:          "cp-1461-brief-f002-email",
		Name:        "Brief-F002-Email-Test",
		UserID:      "test",
		LocationIDs: []string{"loc-a"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{
			Email:    alertThresholdStrPtr("LOW"),
			Telegram: alertThresholdStrPtr("HIGH"),
			Sms:      alertThresholdStrPtr("MODERATE"),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	r := briefingVergleichEtagRouter(s)
	w := doReq(r, http.MethodPut, "/api/briefings/cp-1461-brief-f002-email?kind=vergleich",
		`{"alert_channel_thresholds":{"email":"HIGH"}}`, "", "test")

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded := loadPresetOrFail(t, s, "cp-1461-brief-f002-email")
	if loaded.AlertChannelThresholds == nil || loaded.AlertChannelThresholds.Email == nil ||
		*loaded.AlertChannelThresholds.Email != "HIGH" {
		t.Fatalf("expected email=HIGH applied via Weg 2, got %+v", loaded.AlertChannelThresholds)
	}
	if loaded.AlertChannelThresholds.Telegram == nil || *loaded.AlertChannelThresholds.Telegram != "HIGH" {
		t.Errorf(
			"F002 Weg 2: telegram erased by email-only patch, expected HIGH (unangetastet), got %+v",
			loaded.AlertChannelThresholds.Telegram,
		)
	}
	if loaded.AlertChannelThresholds.Sms == nil || *loaded.AlertChannelThresholds.Sms != "MODERATE" {
		t.Errorf(
			"F002 Weg 2: sms erased by email-only patch, expected MODERATE (unangetastet), got %+v",
			loaded.AlertChannelThresholds.Sms,
		)
	}
}

// AC-10 (Ebene 2, Weg 2, F002-Ergaenzung): ein Patch, der NUR sms mitschickt,
// darf email UND telegram ueber diesen Schreibweg nicht loeschen.
func TestUpdateBriefingHandler_Vergleich_AlertChannelThresholdsFieldLevelMergePreservesEmailAndTelegramWhenOnlySmsSet(t *testing.T) {
	s := newTestStore(t)

	original := model.ComparePreset{
		ID:          "cp-1461-brief-f002-sms",
		Name:        "Brief-F002-Sms-Test",
		UserID:      "test",
		LocationIDs: []string{"loc-a"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{
			Email:    alertThresholdStrPtr("LOW"),
			Telegram: alertThresholdStrPtr("HIGH"),
			Sms:      alertThresholdStrPtr("MODERATE"),
		},
		CreatedAt: time.Now().UTC(),
	}
	if err := s.SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	r := briefingVergleichEtagRouter(s)
	w := doReq(r, http.MethodPut, "/api/briefings/cp-1461-brief-f002-sms?kind=vergleich",
		`{"alert_channel_thresholds":{"sms":"HIGH"}}`, "", "test")

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded := loadPresetOrFail(t, s, "cp-1461-brief-f002-sms")
	if loaded.AlertChannelThresholds == nil || loaded.AlertChannelThresholds.Sms == nil ||
		*loaded.AlertChannelThresholds.Sms != "HIGH" {
		t.Fatalf("expected sms=HIGH applied via Weg 2, got %+v", loaded.AlertChannelThresholds)
	}
	if loaded.AlertChannelThresholds.Email == nil || *loaded.AlertChannelThresholds.Email != "LOW" {
		t.Errorf(
			"F002 Weg 2: email erased by sms-only patch, expected LOW (unangetastet), got %+v",
			loaded.AlertChannelThresholds.Email,
		)
	}
	if loaded.AlertChannelThresholds.Telegram == nil || *loaded.AlertChannelThresholds.Telegram != "HIGH" {
		t.Errorf(
			"F002 Weg 2: telegram erased by sms-only patch, expected HIGH (unangetastet), got %+v",
			loaded.AlertChannelThresholds.Telegram,
		)
	}
}

// F005 (Adversary HIGH, Fix-Loop 2), Weg 2: derselbe Alltagsfall wie bei
// Weg 1 — ein frisches Preset OHNE `alert_channel_thresholds`, dessen Nutzer
// zum ersten Mal EINEN Kanal einstellt. Weg 2 durchlaeuft strukturell NICHT
// den Go-Preserve-Block aus UpdateComparePresetHandler, sondern den
// generischen `mergeBriefingPatch`/`mergeConfigMap`-Weg (kein Pointer-Zugriff
// auf ein nil-Unterobjekt, deshalb hier kein Panic-Risiko wie bei Weg 1) —
// trotzdem eigenstaendig belegt statt aus Weg 1 angenommen (Muster der
// uebrigen Weg-2-Tests in dieser Datei).
func TestUpdateBriefingHandler_Vergleich_AlertChannelThresholdsFirstTimeSetOnFreshPresetNoPanic(t *testing.T) {
	s := newTestStore(t)

	original := model.ComparePreset{
		ID:          "cp-1461-brief-f005",
		Name:        "Brief-F005-Test",
		UserID:      "test",
		LocationIDs: []string{"loc-a"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		CreatedAt:   time.Now().UTC(),
	}
	if err := s.SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	r := briefingVergleichEtagRouter(s)
	w := doReq(r, http.MethodPut, "/api/briefings/cp-1461-brief-f005?kind=vergleich",
		`{"alert_channel_thresholds":{"telegram":"HIGH"}}`, "", "test")

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 (KEIN Panic), got %d: %s", w.Code, w.Body.String())
	}

	loaded := loadPresetOrFail(t, s, "cp-1461-brief-f005")
	if loaded.AlertChannelThresholds == nil || loaded.AlertChannelThresholds.Telegram == nil ||
		*loaded.AlertChannelThresholds.Telegram != "HIGH" {
		t.Fatalf("expected telegram=HIGH applied via Weg 2, got %+v", loaded.AlertChannelThresholds)
	}
	if loaded.AlertChannelThresholds.Email != nil {
		t.Errorf("F005 Weg 2: email darf beim ersten Setzen nicht miterfunden werden, got %+v", loaded.AlertChannelThresholds.Email)
	}
	if loaded.AlertChannelThresholds.Sms != nil {
		t.Errorf("F005 Weg 2: sms darf beim ersten Setzen nicht miterfunden werden, got %+v", loaded.AlertChannelThresholds.Sms)
	}
}
