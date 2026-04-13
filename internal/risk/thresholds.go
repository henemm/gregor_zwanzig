package risk

// Normal thresholds: value >= medium -> MODERATE, value >= high -> HIGH
const (
	windModerate   = 50.0 // km/h
	windHigh       = 70.0
	gustModerate   = 50.0
	gustHigh       = 70.0
	precipModerate = 20.0 // mm (no HIGH level)
	popModerate    = 80   // % (no HIGH level)
	capeModerate   = 1000.0 // J/kg
	capeHigh       = 2000.0
)

// Inverted thresholds: value < threshold -> HIGH
const (
	windChillHighLt = -20.0 // °C
	visHighLt       = 100.0 // m
)

// Wind exposition thresholds (lower than normal, exposed terrain)
const (
	windExpoModerate = 30.0 // km/h
	windExpoHigh     = 50.0
	gustExpoModerate = 40.0
	gustExpoHigh     = 60.0
)
