// Issue #322 — WIcon-Komponente: WMO→WIconKind-Mapping + degToCardinal.
//
// Spec: docs/specs/modules/issue_322_wicon_komponente.md
//
// Ersetzt das bisherige Emoji-Mapping aus weatherEmoji.ts (das unberührt
// bleibt). Konsumenten verwenden den zurückgegebenen WIconKind in
// <WIcon kind={...} />, um ein Lucide-SVG zu rendern.

export type WIconKind =
	| 'sun'
	| 'cloud'
	| 'rain'
	| 'thunder'
	| 'snow'
	| 'wind'
	| 'moon'
	| 'headlamp';

/**
 * Mappt einen WMO-Wettercode + optionale Tageszeit-/Strahlungs-/Bewölkungs-Parameter
 * auf einen WIconKind-Wert. Gibt 'cloud' als sicheren Fallback zurück.
 *
 * @param wmo      WMO-Wettercode (oder null wenn nicht vorhanden)
 * @param isDay    1 = Tag, 0 = Nacht (oder null)
 * @param dni      Direct Normal Irradiance in W/m² (oder null)
 * @param cloudPct Bewölkungsgrad 0–100 (oder null)
 */
export function wmoToWIconKind(
	wmo?: number | null,
	isDay?: number | null,
	dni?: number | null,
	cloudPct?: number | null
): WIconKind {
	// WMO-codierte Phänomene haben Vorrang
	if (wmo != null) {
		if (wmo === 45 || wmo === 48) return 'cloud'; // Nebel
		if (wmo >= 51 && wmo <= 55) return 'rain'; // Nieselregen
		if (wmo >= 56 && wmo <= 67) return 'rain'; // Regen / gefrierender Regen
		if (wmo >= 71 && wmo <= 77) return 'snow'; // Schnee / Schneegestöber
		if (wmo >= 80 && wmo <= 82) return 'rain'; // Regenschauer
		if (wmo === 85 || wmo === 86) return 'snow'; // Schneeschauer
		if (wmo >= 95 && wmo <= 99) return 'thunder'; // Gewitter
	}

	// Tageszeit- und Strahlungsbasierte Entscheidung
	if (isDay === 0) {
		// Nacht
		return cloudPct != null && cloudPct > 50 ? 'cloud' : 'moon';
	}

	// Tag (isDay === 1 oder unbekannt)
	if (dni != null && dni > 500) return 'sun';

	return 'cloud'; // sicherer Fallback
}

/**
 * Konvertiert einen Windrichtungs-Grad-Wert (0–360) in eine 8-Punkte-Himmelsrichtung.
 * Identische Logik wie der bisherige Export aus weatherEmoji.ts.
 */
export function degToCardinal(deg?: number | null): string {
	if (deg == null) return '—';
	const idx = Math.round((((deg % 360) + 360) % 360) / 45) % 8;
	return ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][idx];
}
