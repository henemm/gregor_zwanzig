package openmeteo

import "github.com/henemm/gregor-api/internal/model"

type RegionalModel struct {
	ID        string
	Name      string
	Endpoint  string
	MinLat    float64
	MaxLat    float64
	MinLon    float64
	MaxLon    float64
	GridResKm float64
	Priority  int
}

var RegionalModels = []RegionalModel{
	{
		ID: "meteofrance_arome", Name: "AROME France & Balearics (1.3km)",
		Endpoint: "/v1/meteofrance",
		MinLat: 38, MaxLat: 53, MinLon: -8, MaxLon: 10,
		GridResKm: 1.3, Priority: 1,
	},
	{
		ID: "icon_d2", Name: "ICON-D2 Germany & Alps (2km)",
		Endpoint: "/v1/dwd-icon",
		MinLat: 43, MaxLat: 56, MinLon: 2, MaxLon: 18,
		GridResKm: 2.0, Priority: 2,
	},
	{
		ID: "metno_nordic", Name: "MetNo Nordic (1km)",
		Endpoint: "/v1/metno",
		MinLat: 53, MaxLat: 72, MinLon: 3, MaxLon: 35,
		GridResKm: 1.0, Priority: 3,
	},
	{
		ID: "icon_eu", Name: "ICON-EU Europe (7km)",
		Endpoint: "/v1/dwd-icon",
		MinLat: 29, MaxLat: 71, MinLon: -24, MaxLon: 45,
		GridResKm: 7.0, Priority: 4,
	},
	{
		ID: "ecmwf_ifs04", Name: "ECMWF IFS Global (40km)",
		Endpoint: "/v1/ecmwf",
		MinLat: -90, MaxLat: 90, MinLon: -180, MaxLon: 180,
		GridResKm: 40.0, Priority: 5,
	},
}

// ThunderCodes: WMO-Codes die ThunderHigh ausloesen
var ThunderCodes = map[int]bool{95: true, 96: true, 99: true}

func parseThunderLevel(wmoCode int) model.ThunderLevel {
	if ThunderCodes[wmoCode] {
		return model.ThunderHigh
	}
	return model.ThunderNone
}

// HourlyParams: OpenMeteo API parameter names
var HourlyParams = []string{
	"temperature_2m",
	"apparent_temperature",
	"relative_humidity_2m",
	"dewpoint_2m",
	"pressure_msl",
	"cloud_cover",
	"cloud_cover_low",
	"cloud_cover_mid",
	"cloud_cover_high",
	"wind_speed_10m",
	"wind_direction_10m",
	"wind_gusts_10m",
	"precipitation",
	"weather_code",
	"visibility",
	"precipitation_probability",
	"cape",
	"freezing_level_height",
	"is_day",
	"direct_normal_irradiance",
}
