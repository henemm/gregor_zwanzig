/**
 * Konvertiert HH:MM auf HH:MM:SS (ISO-konform fuer Python time.fromisoformat).
 * Bereits ISO-konforme Strings (HH:MM:SS) bleiben unveraendert.
 * Leere/undefined/unbekannte Inputs werden unveraendert durchgereicht
 * (defensive, fuer Optional-Felder).
 *
 * Issue #231: report_config.morning_time / evening_time Norm.
 */
export function toHHMMSS(time: string | undefined): string | undefined {
	if (!time) return time;
	if (/^\d{2}:\d{2}$/.test(time)) return `${time}:00`;
	return time;
}
