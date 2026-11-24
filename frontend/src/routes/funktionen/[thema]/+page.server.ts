// Issue #3319 / #3320 (AC-4) — oeffentliche Funktions-Unterseite /funktionen/<slug>.
// Der Loader liefert NUR die Kennung `oeffentlich`, die aufgeloeste Sprache und
// den Slug: keine Nutzerdaten, kein userId, kein Aufruf der Go-API — auch fuer
// Angemeldete. Unbekannter Slug (Gross-/Kleinschreibung zaehlt) => 404; fuer
// Ausgeloggte greift vorher der Auth-Hook (nur exakte Pfade der Seitenliste offen).
import { error } from '@sveltejs/kit';
import { funktionenSeite } from '$lib/funktionen_seiten.js';
import type { PageServerLoad } from './$types.js';

export const load: PageServerLoad = async ({ params, locals }) => {
	const seite = funktionenSeite(params.thema);
	if (!seite) error(404, 'Not found');
	return {
		oeffentlich: true as const,
		lang: locals.lang ?? 'de',
		slug: seite.slug
	};
};
