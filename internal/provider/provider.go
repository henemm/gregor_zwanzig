package provider

import (
	"fmt"

	"github.com/henemm/gregor-api/internal/model"
)

type WeatherProvider interface {
	FetchForecast(lat, lon float64, hours int) (*model.Timeseries, error)
}

type ProviderError struct {
	Msg string
}

func (e *ProviderError) Error() string {
	return fmt.Sprintf("provider error: %s", e.Msg)
}

type ProviderRequestError struct {
	StatusCode int
	Msg        string
}

func (e *ProviderRequestError) Error() string {
	return fmt.Sprintf("HTTP %d: %s", e.StatusCode, e.Msg)
}
