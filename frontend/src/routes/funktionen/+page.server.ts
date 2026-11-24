// Issue #3319 / #3320 (AC-4) — oeffentliche Funktionsuebersicht. Der Loader
// liefert NUR die Kennung `oeffentlich` und die aufgeloeste Sprache: keine
// Nutzerdaten, kein userId, kein Aufruf der Go-API — auch fuer Angemeldete.
// Sprache wie auf der Startseite: Cookie gz_lang > Accept-Language > de
// (hooks.server.ts setzt locals.lang).
import type { PageServerLoad } from './$types.js';

export const load: PageServerLoad = async ({ locals }) => ({
	oeffentlich: true as const,
	lang: locals.lang ?? 'de'
});
