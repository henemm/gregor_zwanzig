package config

// TDD RED — Issue #2163 Scheibe 1, Punkt-7-Block (abtrennbar), AC-15/AC-16.
// Spec: docs/specs/modules/auth_haertung_go_2163.md
//
// Festgelegte Felder in config.Config (alle `default:""`, envconfig-Tag =
// unpraefixierter Name; envconfig v1.4.0 liest erst GZ_<NAME>, dann <NAME>):
//
//	TelegramWebhookSecret     string `envconfig:"TELEGRAM_WEBHOOK_SECRET" default:""`
//	TelegramBotUsername       string `envconfig:"TELEGRAM_BOT_USERNAME" default:""`
//	SevenWebhookPathSecret    string `envconfig:"SEVEN_WEBHOOK_PATH_SECRET" default:""`
//	SevenWebhookSigningKey    string `envconfig:"SEVEN_WEBHOOK_SIGNING_KEY" default:""`
//	StalwartWebhookPathSecret string `envconfig:"STALWART_WEBHOOK_PATH_SECRET" default:""`
//	StalwartWebhookSecret     string `envconfig:"STALWART_WEBHOOK_SECRET" default:""`
//
// Hier wird bewusst ueber die Umgebung gesetzt (t.Setenv): geprueft wird das
// envconfig-Tag dort, wo es WIRKT — eine Direktzuweisung liesse einen falschen
// Tag-Namen gruen.
//
// RED-Beleg: Build-Fehler "cfg.TelegramWebhookSecret undefined" usw.

import (
	"os"
	"testing"
)

type webhookSecretFeld struct {
	env string
	get func(*Config) string
}

func webhookSecretFelder() []webhookSecretFeld {
	return []webhookSecretFeld{
		{"TELEGRAM_WEBHOOK_SECRET", func(c *Config) string { return c.TelegramWebhookSecret }},
		{"TELEGRAM_BOT_USERNAME", func(c *Config) string { return c.TelegramBotUsername }},
		{"SEVEN_WEBHOOK_PATH_SECRET", func(c *Config) string { return c.SevenWebhookPathSecret }},
		{"SEVEN_WEBHOOK_SIGNING_KEY", func(c *Config) string { return c.SevenWebhookSigningKey }},
		{"STALWART_WEBHOOK_PATH_SECRET", func(c *Config) string { return c.StalwartWebhookPathSecret }},
		{"STALWART_WEBHOOK_SECRET", func(c *Config) string { return c.StalwartWebhookSecret }},
	}
}

// unsetWebhookEnv entfernt beide Schreibweisen (GZ_ und unpraefixiert) aller
// sechs Variablen wirklich (nicht nur leer gesetzt); t.Setenv stellt den
// Ausgangszustand der Host-Umgebung nach dem Test wieder her.
func unsetWebhookEnv(t *testing.T) {
	t.Helper()
	for _, f := range webhookSecretFelder() {
		for _, k := range []string{f.env, "GZ_" + f.env} {
			t.Setenv(k, "")
			os.Unsetenv(k)
		}
	}
}

// AC-15: unpraefixierte Namen (wie in den Prod-/Staging-Env-Dateien) landen in
// den sechs Feldern.
func TestLoad_WebhookSecrets_UnpraefixiertGelesen_AC15(t *testing.T) {
	unsetWebhookEnv(t)
	for _, f := range webhookSecretFelder() {
		t.Setenv(f.env, "plain-"+f.env)
	}
	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	for _, f := range webhookSecretFelder() {
		if got := f.get(cfg); got != "plain-"+f.env {
			t.Errorf("AC-15: %s unpraefixiert gesetzt, Feld erwartet %q, bekommen %q", f.env, "plain-"+f.env, got)
		}
	}
}

// AC-15: ein GZ_-praefixierter Wert hat Vorrang vor dem unpraefixierten.
func TestLoad_WebhookSecrets_GZPraefixHatVorrang_AC15(t *testing.T) {
	unsetWebhookEnv(t)
	for _, f := range webhookSecretFelder() {
		t.Setenv(f.env, "plain-"+f.env)
		t.Setenv("GZ_"+f.env, "gz-"+f.env)
	}
	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	for _, f := range webhookSecretFelder() {
		if got := f.get(cfg); got != "gz-"+f.env {
			t.Errorf("AC-15: GZ_%s und %s gesetzt, Feld erwartet GZ_-Wert %q, bekommen %q", f.env, f.env, "gz-"+f.env, got)
		}
	}
}

// AC-15: nur GZ_ gesetzt wird ebenfalls gelesen.
func TestLoad_WebhookSecrets_NurGZPraefix_AC15(t *testing.T) {
	unsetWebhookEnv(t)
	for _, f := range webhookSecretFelder() {
		t.Setenv("GZ_"+f.env, "gz-"+f.env)
	}
	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	for _, f := range webhookSecretFelder() {
		if got := f.get(cfg); got != "gz-"+f.env {
			t.Errorf("AC-15: nur GZ_%s gesetzt, Feld erwartet %q, bekommen %q", f.env, "gz-"+f.env, got)
		}
	}
}

// AC-16: keine der sechs Variablen gesetzt (Telegram bewusst nicht
// konfiguriert) -> kein Fehler, alle Felder leer.
func TestLoad_WebhookSecrets_OhneVariablen_KeinFehlerLeereFelder_AC16(t *testing.T) {
	unsetWebhookEnv(t)
	cfg, err := Load()
	if err != nil {
		t.Fatalf("AC-16: Load ohne Webhook-Variablen darf nicht scheitern: %v", err)
	}
	for _, f := range webhookSecretFelder() {
		if got := f.get(cfg); got != "" {
			t.Errorf("AC-16: %s nicht gesetzt, Feld erwartet leer, bekommen %q", f.env, got)
		}
	}
}
