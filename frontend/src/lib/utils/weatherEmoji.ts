const WMO_PRECIP: Record<number, string> = {
	45: '🌫️', 48: '🌫️',
	51: '🌦️', 53: '🌦️', 55: '🌧️', 56: '🌧️', 57: '🌧️',
	61: '🌧️', 63: '🌧️', 65: '🌧️', 66: '🌨️', 67: '🌨️',
	71: '❄️', 73: '❄️', 75: '❄️', 77: '❄️',
	80: '🌦️', 81: '🌧️', 82: '🌧️', 85: '🌨️', 86: '🌨️',
	95: '⛈️', 96: '⛈️', 99: '⛈️'
};

export function weatherEmoji(
	wmoCode?: number | null,
	isDay?: number | null,
	dniWm2?: number | null,
	cloudPct?: number | null
): string {
	// Priority 1: WMO precipitation codes
	if (wmoCode != null && WMO_PRECIP[wmoCode]) return WMO_PRECIP[wmoCode];

	// Priority 2: Night
	if (isDay === 0) {
		return (cloudPct ?? 0) > 50 ? '☁️' : '🌙';
	}

	// Priority 3: DNI-based (daytime solar)
	if (dniWm2 != null) {
		if (dniWm2 > 500) return '☀️';
		if (dniWm2 > 200) return '🌤️';
		if (dniWm2 > 50) return '⛅';
		return '☁️';
	}

	// Priority 4: Cloud percentage fallback
	const cloud = cloudPct ?? 0;
	if (cloud < 20) return '☀️';
	if (cloud < 50) return '🌤️';
	if (cloud < 80) return '⛅';
	return '☁️';
}

const CARDINALS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'] as const;

export function degToCardinal(deg?: number | null): string {
	if (deg == null) return '—';
	const idx = Math.round(((deg % 360) + 360) % 360 / 45) % 8;
	return CARDINALS[idx];
}
