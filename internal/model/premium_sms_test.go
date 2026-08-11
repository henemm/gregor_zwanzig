package model

// TDD RED — Issue #1717 (Scheibe S3): Premium-SMS in der Oberflaeche.
// Spec: docs/specs/modules/feat_1717_s3_premium_sms_ui.md — AC-6 (Tarif-Gate)
// und die Frist-Ableitung, die `GET /api/auth/profile` fuer die Anzeige
// braucht (AC-3/AC-5 lesen den fertig abgeleiteten Zustand).
//
// Herkunft: in der RED-Phase lag diese Datei ausserhalb von internal/ und wurde
// per `go test -overlay` eingespielt (der edit_gate laesst in phase5_tdd_red nur
// Test-Verzeichnisse zu). Seit Phase 6 liegt sie an ihrem Zielort neben dem
// Code — Assertions unveraendert.
//
// RED war: `internal/model/premium_sms.go` existierte nicht — weder
// `PremiumSmsAllowed`, noch `PremiumSmsReplyTTL`, noch
// `DerivePremiumSmsReplyState`. Das Paket uebersetzte deshalb nicht.
//
// Keine Mocks: echte Funktionsaufrufe, echte time.Time-Werte.

import (
	"testing"
	"time"
)

// Vom Geraet gelernte Garmin-Rueckadresse (S1 schreibt sie). Garmin inReach hat
// KEINE feste Nummer — der Wert ist beispielhaft, nie eine Konfiguration.
const testReplyTo = "15551234567"

// AC-6: Das Premium-SMS-Tarif-Gate ist eigenstaendig und laesst ausschliesslich
// `premium` durch. Es darf NICHT an SmsAllowed delegieren — das laesst
// `standard` mit durch (tier.go:3-10), und ein standard-Nutzer koennte dann
// einen Kanal einschalten, den der Sendepfad (S2a AC-8) ohnehin blockt.
func TestPremiumSmsAllowedExcludesStandardTier(t *testing.T) {
	// Vorbedingung, damit dieser Test nicht still bedeutungslos wird: das
	// bestehende SMS-Gate laesst `standard` tatsaechlich durch.
	if !SmsAllowed("standard") {
		t.Fatalf("Vorbedingung verletzt: SmsAllowed(\"standard\") = false — dann ist die " +
			"Unterscheidung, die dieser Test bewacht, gegenstandslos geworden.")
	}

	faelle := []struct {
		tier string
		want bool
	}{
		{"premium", true},
		{"standard", false}, // der Kern von AC-6
		{"free", false},
		{"", false},
		{"Premium", false}, // nur exakt "premium" (EffectiveTier normalisiert vorher)
	}
	for _, f := range faelle {
		if got := PremiumSmsAllowed(f.tier); got != f.want {
			t.Errorf("PremiumSmsAllowed(%q) = %v, want %v", f.tier, got, f.want)
		}
	}
}

// Die drei Zustandswerte sind ein Vertrag mit dem Frontend
// (`premium_sms_reply_state`, verarbeitet in premiumSmsChannelState.ts). Wer
// sie umbenennt, bricht die Anzeige ohne dass ein Renderer-Test rot wird.
func TestPremiumSmsStateConstantsMatchWireContract(t *testing.T) {
	faelle := []struct {
		got  string
		want string
	}{
		{PremiumSmsStateNone, "none"},
		{PremiumSmsStateStale, "stale"},
		{PremiumSmsStateFresh, "fresh"},
	}
	for _, f := range faelle {
		if f.got != f.want {
			t.Errorf("Zustands-Konstante = %q, want %q (Vertrag mit dem Frontend)", f.got, f.want)
		}
	}
}

// Ohne gelernte Rueckadresse ODER ohne Zeitstempel ist der Zustand "none" —
// genau die Bedingung des Sendepfads (`not reply_to or reply_at is None`,
// src/output/channels/premium_sms.py:73). Ein Zeitstempel ohne Adresse und eine
// Adresse ohne Zeitstempel sind beides "noch nie gemeldet", nicht "veraltet":
// als "stale" gemeldet, wuerde die Oberflaeche ein Verfallsdatum behaupten, das
// es nie gab.
func TestDerivePremiumSmsReplyStateNoneWithoutLearnedAddress(t *testing.T) {
	now := time.Now().UTC()

	faelle := []struct {
		name    string
		replyTo string
		replyAt *time.Time
	}{
		{"nichts gelernt", "", nil},
		{"Zeitstempel ohne Adresse", "", &now},
		{"Adresse ohne Zeitstempel", testReplyTo, nil},
	}
	for _, f := range faelle {
		if got := DerivePremiumSmsReplyState(f.replyTo, f.replyAt); got != PremiumSmsStateNone {
			t.Errorf("%s: DerivePremiumSmsReplyState = %q, want %q",
				f.name, got, PremiumSmsStateNone)
		}
	}
}

// Grenzwert der Frist, relativ zur Konstante gemessen (keine zweite 30 im Test —
// die Deckungsgleichheit der ZAHL bewacht tests/test_premium_sms_ttl_drift.py,
// AC-11). Semantik wie im Sendepfad: `age > TTL` ist veraltet, `age == TTL` ist
// noch frisch (premium_sms.py:81).
func TestDerivePremiumSmsReplyStateFreshInsideTTL(t *testing.T) {
	now := time.Now().UTC()

	faelle := []struct {
		name string
		age  time.Duration
	}{
		{"gerade gemeldet", 0},
		{"eine Sekunde vor der Frist", PremiumSmsReplyTTL - time.Second},
		{"genau auf der Frist", PremiumSmsReplyTTL},
	}
	for _, f := range faelle {
		at := now.Add(-f.age)
		if got := DerivePremiumSmsReplyState(testReplyTo, &at); got != PremiumSmsStateFresh {
			t.Errorf("%s (Alter %v): DerivePremiumSmsReplyState = %q, want %q",
				f.name, f.age, got, PremiumSmsStateFresh)
		}
	}
}

func TestDerivePremiumSmsReplyStateStaleOneSecondOutsideTTL(t *testing.T) {
	now := time.Now().UTC()

	faelle := []struct {
		name string
		age  time.Duration
	}{
		{"eine Sekunde nach der Frist", PremiumSmsReplyTTL + time.Second},
		{"deutlich nach der Frist", PremiumSmsReplyTTL + 400*24*time.Hour},
	}
	for _, f := range faelle {
		at := now.Add(-f.age)
		if got := DerivePremiumSmsReplyState(testReplyTo, &at); got != PremiumSmsStateStale {
			t.Errorf("%s (Alter %v): DerivePremiumSmsReplyState = %q, want %q",
				f.name, f.age, got, PremiumSmsStateStale)
		}
	}
}
