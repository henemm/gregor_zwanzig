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

/**
 * Die 24 vollen Stunden als Auswahl-Eintraege ("00:00" … "23:00").
 *
 * Issue #1379: Die Versandzeit (Morgen-/Abend-Briefing) wird ausschliesslich
 * als volle Stunde gewaehlt — der Scheduler versendet ohnehin nur stuendlich
 * (#1280). Diese Liste ist die EINE Quelle der waehlbaren Uhrzeiten.
 */
export const HOUR_OPTIONS: string[] = Array.from(
	{ length: 24 },
	(_, h) => `${String(h).padStart(2, '0')}:00`
);

/**
 * Bildet einen gespeicherten Zeitwert ("HH:MM" / "HH:MM:SS") auf den passenden
 * Eintrag aus HOUR_OPTIONS ab — Minuten werden gekappt, nicht gerundet (gleiche
 * Regel wie serverseitig, store.TruncateTimeStringToHour).
 *
 * Reine Anzeige-Ableitung: es wird nichts zurueckgeschrieben, solange der
 * Nutzer nicht selbst waehlt (Issue #1379, AC-5). Nicht interpretierbare Werte
 * (leer, kaputt, Stunde ausserhalb 0-23) liefern den uebergebenen
 * Vorgabe-Eintrag, damit die Auswahl nie leer erscheint.
 */
export function toHourOption(time: string | null | undefined, fallback = '07:00'): string {
	const match = /^(\d{1,2}):\d{1,2}/.exec(time ?? '');
	if (!match) return fallback;
	const hour = Number(match[1]);
	if (!Number.isInteger(hour) || hour < 0 || hour > 23) return fallback;
	return HOUR_OPTIONS[hour];
}
