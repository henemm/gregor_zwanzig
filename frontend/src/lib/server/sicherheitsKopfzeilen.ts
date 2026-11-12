// Issue #2961 (FE6) — Sicherheits-Kopfzeilen fuer jede Antwort des
// Frontend-Servers (Seiten, Daten, Durchreicher). Die Content-Security-Policy
// selbst setzt SvelteKit fuer Seitenantworten (`kit.csp` in svelte.config.js).

/**
 * Geolocation nutzt die App nicht (Orte kommen aus Karte, Suche und GPX);
 * deshalb ist sie wie die uebrigen Geraete-Schnittstellen ganz abgeschaltet.
 * Passkeys (WebAuthn) bleiben bei ihrer Voreinstellung (eigener Ursprung).
 */
export const SICHERHEITS_KOPFZEILEN: Readonly<Record<string, string>> = {
	'x-content-type-options': 'nosniff',
	'referrer-policy': 'strict-origin-when-cross-origin',
	'x-frame-options': 'DENY',
	'permissions-policy': 'camera=(), microphone=(), geolocation=(), payment=(), usb=()'
};

/** Setzt die Kopfzeilen auf der Antwort (fehlt eine Schreibbarkeit, bleibt sie, wie sie ist). */
export function sicherheitsKopfzeilenSetzen(antwort: Response): Response {
	try {
		for (const [name, wert] of Object.entries(SICHERHEITS_KOPFZEILEN)) {
			antwort.headers.set(name, wert);
		}
		return antwort;
	} catch {
		// Unveraenderliche Kopfzeilen (z. B. Response.redirect): als Kopie neu stellen.
		const kopie = new Response(antwort.body, antwort);
		for (const [name, wert] of Object.entries(SICHERHEITS_KOPFZEILEN)) kopie.headers.set(name, wert);
		return kopie;
	}
}
