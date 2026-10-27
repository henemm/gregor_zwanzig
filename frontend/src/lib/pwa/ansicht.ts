// Issue #2131/#2520 — reine Positivlisten-Logik des Service Workers, ausgelagert
// damit sie ohne Worker-Umgebung testbar ist (AC-9: `/` nie darunter).

/** Genau eine Trip- oder Vergleichs-Ansicht -- keine Liste, kein Anlegen. */
const ANSICHT = /^\/(?:trips|compare)\/[^/]+$/;
export const DATEN_ENDUNG = '/__data.json';

/**
 * Zu welcher vorgehaltenen Ansicht gehoert dieser Pfad? `null` = keine.
 *
 * SvelteKit navigiert clientseitig NICHT per Seitenaufruf, sondern per
 * `fetch()` auf `<pfad>/__data.json`. Beide Anfrageklassen gehoeren derselben
 * Ansicht -- wer nur die Seite ablegt, kann offline eine Ansicht oeffnen, aber
 * nicht von ihr weg- und wieder zu ihr zurueck (Spec, Befund B1).
 */
export function ansichtVon(pathname: string): string | null {
	const kandidat = pathname.endsWith(DATEN_ENDUNG)
		? pathname.slice(0, -DATEN_ENDUNG.length)
		: pathname;
	if (!ANSICHT.test(kandidat)) return null;
	// `/trips/new` und `/compare/new` sind Anlege-Flaechen, keine Ansichten.
	if (kandidat.endsWith('/new')) return null;
	return kandidat;
}
