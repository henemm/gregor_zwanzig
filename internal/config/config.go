package config

import "github.com/kelseyhightower/envconfig"

type Config struct {
	Host              string `envconfig:"HOST" default:"127.0.0.1"`
	Port              string `envconfig:"PORT" default:"8090"`
	PythonCoreURL     string `envconfig:"PYTHON_CORE_URL" default:"http://localhost:8000"`
	DataDir           string `envconfig:"DATA_DIR" default:"data"`
	UserID            string `envconfig:"USER_ID" default:"default"`
	OpenMeteoBaseURL  string `envconfig:"OPENMETEO_BASE_URL" default:"https://api.open-meteo.com"`
	OpenMeteoAQURL    string `envconfig:"OPENMETEO_AQ_URL" default:"https://air-quality-api.open-meteo.com"`
	OpenMeteoTimeout  int    `envconfig:"OPENMETEO_TIMEOUT" default:"30"`
	OpenMeteoRetries  int    `envconfig:"OPENMETEO_RETRIES" default:"5"`
	CacheDir          string `envconfig:"CACHE_DIR" default:"data/cache"`
	SessionSecret     string `envconfig:"SESSION_SECRET" default:"dev-secret-change-me"`
	AuthUser          string `envconfig:"AUTH_USER" default:"admin"`
	AuthPass          string `envconfig:"AUTH_PASS" default:""`
	HeartbeatComparePresets string `envconfig:"HEARTBEAT_COMPARE_PRESETS" default:""`
	SchedulerTimezone string `envconfig:"SCHEDULER_TIMEZONE" default:"Europe/Vienna"`
	SMTPHost          string `envconfig:"SMTP_HOST" default:""`
	SMTPPort          int    `envconfig:"SMTP_PORT" default:"587"`
	SMTPUser          string `envconfig:"SMTP_USER" default:""`
	SMTPPass          string `envconfig:"SMTP_PASS" default:""`
	SMTPFrom          string `envconfig:"SMTP_FROM" default:"gregor_zwanzig@henemm.com"`
	GoogleSMTPHost    string `envconfig:"GOOGLE_SMTP_HOST" default:""`
	GoogleSMTPPort    int    `envconfig:"GOOGLE_SMTP_PORT" default:"587"`
	GoogleSMTPUser    string `envconfig:"GOOGLE_SMTP_USER" default:""`
	GoogleSMTPPass    string `envconfig:"GOOGLE_SMTP_PASS" default:""`
	GoogleClientID     string `envconfig:"GOOGLE_CLIENT_ID" default:""`
	GoogleClientSecret string `envconfig:"GOOGLE_CLIENT_SECRET" default:""`
	GoogleRedirectURL  string `envconfig:"GOOGLE_REDIRECT_URL" default:""`
	PublicHost        string `envconfig:"PUBLIC_HOST" default:"https://gregor20.henemm.com"`
	TestFixtureDir    string `envconfig:"TEST_FIXTURE_DIR" default:""`
	// Issue #450 — Passkey/WebAuthn V1 Add-on
	WebAuthnRPID          string `envconfig:"WEBAUTHN_RP_ID" default:"localhost"`
	WebAuthnRPDisplayName string `envconfig:"WEBAUTHN_RP_DISPLAY_NAME" default:"Gregor Zwanzig"`
	WebAuthnRPOrigins     string `envconfig:"WEBAUTHN_RP_ORIGINS" default:"http://localhost:5173"`
}

func Load() (*Config, error) {
	var cfg Config
	err := envconfig.Process("GZ", &cfg)
	return &cfg, err
}
