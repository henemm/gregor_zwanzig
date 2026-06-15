package model

// TDD RED — Issue #817: Alerts-Tab auf Δ-Schwellen umstellen.
//
// Diese Tests sind in der RED-Phase geschrieben und schlagen FEHL, weil:
//   - AC-1: SyncAlertRules erzeugt heute kind="absolute" (nicht "delta")
//   - AC-2: SyncAlertRules migriert absolute→delta noch nicht
//   - AC-3: SyncAlertRules löscht heute Delta-Regeln aktiv (Z. 177) → würde neue absolute erzeugen
//   - AC-8: Roundtrip liefert kind="absolute" statt "delta"
//
// AC-7 ist ein Regression-Guard (schlägt heute NICHT fehl — Isolation existiert bereits).

import (
	"encoding/json"
	"os"
	"testing"
)

// --- AC-1: Neue Regel ist kind="delta" mit Delta-Default-Threshold ---
//
// RED-Treiber: SyncAlertRules gibt heute kind="absolute" mit Threshold=50 zurück.
// GRÜN nach Implementierung: DefaultDeltaThreshold["wind_gust"].Threshold = 20.
func TestSyncAlertRules_817_NewRuleIsDelta(t *testing.T) {
	result := SyncAlertRules(nil, []string{"wind_gust"})
	if len(result) != 1 {
		t.Fatalf("AC-1: want 1 rule, got %d", len(result))
	}
	r := result[0]
	if r.Kind != AlertRuleKindDelta {
		t.Errorf("AC-1: want kind=%q, got %q", AlertRuleKindDelta, r.Kind)
	}
	// DefaultDeltaThreshold["wind_gust"].Threshold == 20.0 (Cross-Lang-Kontrakt #817)
	if r.Threshold != 20.0 {
		t.Errorf("AC-1: want threshold=20.0 (DefaultDeltaThreshold[wind_gust]), got %f", r.Threshold)
	}
	if r.Metric != AlertMetricWindGust {
		t.Errorf("AC-1: want metric=wind_gust, got %s", r.Metric)
	}
}

// --- AC-2: Migration absolute→delta: Enabled/Severity bleiben erhalten ---
//
// RED-Treiber: SyncAlertRules behält heute absolute Regel 1:1 als "absolute" zurück.
// GRÜN nach Implementierung: migriert auf kind="delta", setzt Threshold=20 (Default),
// erhält Enabled+Severity aus Ursprungsregel.
func TestSyncAlertRules_817_MigratesAbsoluteToDelta(t *testing.T) {
	existing := []AlertRule{
		{
			ID:        "legacy-rule",
			Kind:      AlertRuleKindAbsolute,
			Metric:    AlertMetricWindGust,
			Threshold: 50,
			Unit:      "km/h",
			Enabled:   true,
			Severity:  AlertSeverityWarning,
		},
	}
	result := SyncAlertRules(existing, []string{"wind_gust"})
	if len(result) != 1 {
		t.Fatalf("AC-2: want 1 rule, got %d", len(result))
	}
	r := result[0]
	if r.Kind != AlertRuleKindDelta {
		t.Errorf("AC-2: want kind=%q after migration, got %q", AlertRuleKindDelta, r.Kind)
	}
	// Der absolute Threshold (50) war nie alert-wirksam → wird auf Delta-Default (20) gesetzt.
	if r.Threshold != 20.0 {
		t.Errorf("AC-2: want threshold=20.0 (DefaultDeltaThreshold[wind_gust]), got %f", r.Threshold)
	}
	// Nutzer-Einstellungen müssen erhalten bleiben (read-modify-write):
	if !r.Enabled {
		t.Error("AC-2: want Enabled=true (preserved from original rule)")
	}
	if r.Severity != AlertSeverityWarning {
		t.Errorf("AC-2: want Severity=%q (preserved from original rule), got %q", AlertSeverityWarning, r.Severity)
	}
	if r.ID != "legacy-rule" {
		t.Errorf("AC-2: want ID=%q (preserved from original rule), got %q", "legacy-rule", r.ID)
	}
}

// --- AC-3: Idempotenz — nutzerkonfigurierter Δ-Threshold wird NICHT resettet ---
//
// RED-Treiber: SyncAlertRules löscht heute Delta-Regeln aktiv (Z. 177 trip.go)
// → erzeugt neue absolute Regel mit Threshold=50. Nach Implementierung muss
// die vorhandene Delta-Regel mit Threshold=35 erhalten bleiben.
func TestSyncAlertRules_817_IdempotentDeltaPreservesCustomThreshold(t *testing.T) {
	existing := []AlertRule{
		{
			ID:        "user-delta",
			Kind:      AlertRuleKindDelta,
			Metric:    AlertMetricWindGust,
			Threshold: 35, // nutzerkonfiguriert (abweichend vom Default 20)
			Unit:      "km/h",
			Enabled:   true,
			Severity:  AlertSeverityWarning,
		},
	}
	result := SyncAlertRules(existing, []string{"wind_gust"})
	if len(result) != 1 {
		t.Fatalf("AC-3: want exactly 1 rule (no duplication), got %d", len(result))
	}
	r := result[0]
	if r.Kind != AlertRuleKindDelta {
		t.Errorf("AC-3: want kind=%q (unchanged), got %q", AlertRuleKindDelta, r.Kind)
	}
	// Nutzerkonfigurierter Threshold DARF NICHT auf Default 20 resettet werden.
	if r.Threshold != 35 {
		t.Errorf("AC-3: want threshold=35 (user-configured, must not reset to default 20), got %f", r.Threshold)
	}
}

// --- AC-7: Mandantentrennung (Regression-Guard, heute GRÜN) ---
//
// Dieser Test ist ein Regression-Guard. Er schlägt heute NICHT fehl —
// die Store-Isolation existiert bereits (#809). Er verhindert Regression
// durch zukünftige Änderungen an SyncAlertRules.
//
// Beweis: Zwei separate Store-Instanzen in t.TempDir() mit verschiedenen UserIDs.
// SaveTrip(user_a) verändert user_b-alert_rules nicht.
//
// HINWEIS: Der eigentliche Store-Roundtrip-Test (AC-7 mit TempDir-Stores) ist in
// internal/store/store_817_test.go, da er das store-Package benötigt.
// Dieser model-seitige Test prüft SyncAlertRules direkt auf Isolation:
// Zwei unabhängige SyncAlertRules-Aufrufe mit verschiedenen activeMetricIDs
// beeinflussen sich nicht gegenseitig.
func TestSyncAlertRules_817_Idempotent_NoGlobalState(t *testing.T) {
	// Regression-Guard: SyncAlertRules hat keinen globalen State.
	// Zwei Aufrufe mit verschiedenen Metriken geben verschiedene Ergebnisse.
	resultA := SyncAlertRules(nil, []string{"wind_gust"})
	resultB := SyncAlertRules(nil, []string{"temperature_min"})

	if len(resultA) != 1 {
		t.Fatalf("AC-7/guard: call A: want 1 rule, got %d", len(resultA))
	}
	if len(resultB) != 1 {
		t.Fatalf("AC-7/guard: call B: want 1 rule, got %d", len(resultB))
	}
	if resultA[0].Metric == resultB[0].Metric {
		t.Error("AC-7/guard: independent calls returned same metric — global state leak?")
	}
}

// --- DefaultDeltaThreshold Map-Existenz-Test ---
//
// RED-Treiber: DefaultDeltaThreshold existiert noch nicht in trip.go.
// Compile-Fehler ist ein gültiges RED-Signal — dieser Test referenziert das Symbol.
// GRÜN nach Implementierung wenn die Map mit korrekten Werten existiert.
func TestDefaultDeltaThreshold_817_MapExists(t *testing.T) {
	// Kern-Metriken müssen alle im DefaultDeltaThreshold-Map stehen.
	cases := []struct {
		metric    AlertMetric
		threshold float64
		unit      string
	}{
		{AlertMetricWindGust, 20.0, "km/h"},
		{AlertMetricPrecipitationSum, 10.0, "mm"},
		{AlertMetricTemperatureMin, 5.0, "°C"},
		{AlertMetricTemperatureMax, 5.0, "°C"},
		{AlertMetricThunderLevel, 1.0, ""},
		{AlertMetricSnowLine, 200.0, "m"},
	}
	for _, tc := range cases {
		entry, ok := DefaultDeltaThreshold[tc.metric]
		if !ok {
			t.Errorf("DefaultDeltaThreshold: missing entry for metric %s", tc.metric)
			continue
		}
		if entry.Threshold != tc.threshold {
			t.Errorf("DefaultDeltaThreshold[%s].Threshold: want %f, got %f",
				tc.metric, tc.threshold, entry.Threshold)
		}
		if entry.Unit != tc.unit {
			t.Errorf("DefaultDeltaThreshold[%s].Unit: want %q, got %q",
				tc.metric, tc.unit, entry.Unit)
		}
	}
}

// --- EmitDefaultDeltaThresholdJSON: Cross-Lang-Vertragsbrücke (AC-4, Issue #817) ---
//
// Emittiert DefaultDeltaThreshold als JSON in GZ_DELTA_JSON_OUT (wenn gesetzt).
// Wird vom Python-AC-4-Test via subprocess ausgeführt, um echte Go-Laufzeitwerte
// zu lesen — kein Quelltext-Read (765-konform).
// Format: {"WindGust":20,"PrecipitationSum":10,...} (Const-Suffix → Threshold)
func TestEmitDefaultDeltaThresholdJSON(t *testing.T) {
	outPath := os.Getenv("GZ_DELTA_JSON_OUT")
	if outPath == "" {
		t.Skip("GZ_DELTA_JSON_OUT not set — skipping emit (only runs from Python AC-4 subprocess)")
	}
	out := make(map[string]float64, len(DefaultDeltaThreshold))
	// Const-Suffix-Mapping: AlertMetric-Wert → lesbarer Suffix für Python-Seite
	suffixOf := map[AlertMetric]string{
		AlertMetricWindGust:         "WindGust",
		AlertMetricPrecipitationSum: "PrecipitationSum",
		AlertMetricTemperatureMin:   "TemperatureMin",
		AlertMetricTemperatureMax:   "TemperatureMax",
		AlertMetricThunderLevel:     "ThunderLevel",
		AlertMetricSnowLine:         "SnowLine",
	}
	for metric, entry := range DefaultDeltaThreshold {
		if suffix, ok := suffixOf[metric]; ok {
			out[suffix] = entry.Threshold
		}
	}
	data, err := json.Marshal(out)
	if err != nil {
		t.Fatalf("json.Marshal DefaultDeltaThreshold: %v", err)
	}
	if err := os.WriteFile(outPath, data, 0o644); err != nil {
		t.Fatalf("WriteFile %s: %v", outPath, err)
	}
}

// --- AC-F003: Misch-Regeln — delta-Regel gewinnt gegen absolute bei gleicher Metrik ---
//
// Szenario: stale client state hat fuer DIESELBE Metrik sowohl eine absolute
// (Threshold=50) ALS AUCH eine delta-Regel (Threshold=35, nutzerkonfiguriert).
// Erwartet: SyncAlertRules liefert kind="delta", Threshold=35 (nicht 20).
func TestSyncAlertRules_817_MixedRulesDeltaWins(t *testing.T) {
	existing := []AlertRule{
		{
			ID:        "absolute-rule",
			Kind:      AlertRuleKindAbsolute,
			Metric:    AlertMetricWindGust,
			Threshold: 50,
			Unit:      "km/h",
			Enabled:   true,
			Severity:  AlertSeverityWarning,
		},
		{
			ID:        "delta-rule",
			Kind:      AlertRuleKindDelta,
			Metric:    AlertMetricWindGust,
			Threshold: 35, // nutzerkonfiguriert
			Unit:      "km/h",
			Enabled:   true,
			Severity:  AlertSeverityWarning,
		},
	}
	result := SyncAlertRules(existing, []string{"wind_gust"})
	if len(result) != 1 {
		t.Fatalf("F003: want exactly 1 rule (dedup), got %d", len(result))
	}
	r := result[0]
	if r.Kind != AlertRuleKindDelta {
		t.Errorf("F003: want kind=%q (delta wins), got %q", AlertRuleKindDelta, r.Kind)
	}
	if r.Threshold != 35 {
		t.Errorf("F003: want threshold=35 (user-configured delta wins over absolute 50 and default 20), got %f", r.Threshold)
	}
}

// --- ThunderLevel als alertbare Metrik (Delta-Erweiterung) ---
//
// RED-Treiber: AlertableMetrics enthält heute keinen ThunderLevel-Eintrag
// (laut trip.go Z. 110-116 ist thunder_level explizit ausgeschlossen mit
// Kommentar "no meaningful absolute threshold"). Nach Implementierung soll
// ThunderLevel in AlertableMetrics aufgenommen werden (delta-only).
//
// Hinweis: Diese Metrik hat keinen sinnvollen absoluten Threshold, aber
// einen sinnvollen Δ-Threshold (1 Level). Die Spec fügt sie zu AlertableMetrics
// hinzu, damit SyncAlertRules eine Delta-Regel erzeugen kann.
func TestSyncAlertRules_817_ThunderLevelGetsDeltaRule(t *testing.T) {
	result := SyncAlertRules(nil, []string{"thunder_level"})
	if len(result) != 1 {
		t.Fatalf("AC-1/thunder: want 1 rule for thunder_level, got %d (thunder_level must be added to AlertableMetrics)", len(result))
	}
	r := result[0]
	if r.Kind != AlertRuleKindDelta {
		t.Errorf("AC-1/thunder: want kind=%q, got %q", AlertRuleKindDelta, r.Kind)
	}
	if r.Threshold != 1.0 {
		t.Errorf("AC-1/thunder: want threshold=1.0 (DefaultDeltaThreshold[thunder_level]), got %f", r.Threshold)
	}
}
