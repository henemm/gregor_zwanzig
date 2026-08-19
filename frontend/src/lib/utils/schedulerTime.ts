// Issue #1727 S5e — Anzeige des naechsten Scheduler-Laufs auf der Konto-Seite.
// Ausgelagert aus `routes/account/+page.svelte` (:264-281), damit die Funktion
// ueberhaupt pruefbar ist (Spec `fix_1727_s5e_sperrcache_anzeige.md`, B.5).
//
// Ohne `timeZone`-Option formatiert `Intl` in der Zone der ausfuehrenden
// Umgebung — also im Browser des Nutzers (Muster aller uebrigen Zeitanzeigen im
// Frontend). Frueher stand hier fest `Europe/Vienna`. Damit die Zahl eindeutig
// bleibt, traegt die Ausgabe in beiden Faellen ein Zonenkuerzel.

// Vor dieser Grenze ist ein Zeitstempel kein Termin, sondern ein Nullwert:
// die Go-API liefert fuer nie gelaufene Jobs `0001-01-01T00:00:00Z` (#1329).
// Die Grenze liegt am Jahr, nicht bei `getTime() <= 0` — sonst rutschten
// Zeitpunkte zwischen 1970 und heute durch, die ebenso wenig ein Termin sind.
const PLAUSIBLES_MINDESTJAHR = 2000;

export function formatNextRun(iso: string | null | undefined): string {
	if (!iso) return '—';
	try {
		const date = new Date(iso);
		if (date.getFullYear() < PLAUSIBLES_MINDESTJAHR) return '—';
		const now = new Date();
		const time = date.toLocaleString('de-AT', { hour: '2-digit', minute: '2-digit', timeZoneName: 'short' });

		// Der Tagesvergleich liest `now`/`date` direkt aus. Frueher lief er ueber
		// `new Date(x.toLocaleString('en-US'))` — mit fester Wiener Zone eine echte
		// Umrechnung, ohne sie ein Hin-und-Zurueck in derselben Zone und damit
		// wirkungslos. Das Rueck-Einlesen ist zudem heikel: manche ICU-/V8-Kombina-
		// tionen setzen ein schmales geschuetztes Leerzeichen vor AM/PM, das der
		// Parser als `Invalid Date` zurueckweist — der "heute/morgen"-Zweig fiele
		// dann unbemerkt auf den fernen Zweig zurueck.
		const todayDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
		const targetDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
		const diffDays = Math.round((targetDate.getTime() - todayDate.getTime()) / 86400000);

		if (diffDays === 0) return `heute um ${time}`;
		if (diffDays === 1) return `morgen um ${time}`;
		return date.toLocaleString('de-AT', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' });
	} catch { return iso; }
}
