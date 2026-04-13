package config

import "github.com/kelseyhightower/envconfig"

type Config struct {
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
}

func Load() (*Config, error) {
	var cfg Config
	err := envconfig.Process("GZ", &cfg)
	return &cfg, err
}
