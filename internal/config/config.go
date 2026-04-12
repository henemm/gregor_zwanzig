package config

import "github.com/kelseyhightower/envconfig"

type Config struct {
	Port          string `envconfig:"PORT" default:"8090"`
	PythonCoreURL string `envconfig:"PYTHON_CORE_URL" default:"http://localhost:8000"`
	DataDir       string `envconfig:"DATA_DIR" default:"data"`
	UserID        string `envconfig:"USER_ID" default:"default"`
}

func Load() (*Config, error) {
	var cfg Config
	err := envconfig.Process("GZ", &cfg)
	return &cfg, err
}
