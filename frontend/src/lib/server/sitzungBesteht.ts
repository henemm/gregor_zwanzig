// Issue #2961 (FE2e) — besteht fuer diese Anfrage noch eine gueltige Sitzung?
//
// Die Anmeldeseite raeumt den Offline-Speicher nach `/login?abgemeldet=1`. Ein
// solcher Verweis kann auch von aussen kommen; geraeumt werden darf deshalb
// nur, wenn tatsaechlich keine Sitzung mehr besteht. Die Antwort gibt die
// Go-API, die allein die Gaesteliste der Sitzungen kennt.

import { apiBase as API } from '$lib/server/apiBase.js';

type KeksLeser = { get(name: string): string | undefined };

/**
 * `false` nur, wenn kein Sitzungs-Cookie vorliegt oder die Go-API es mit 401
 * ablehnt. Jede andere Lage (200, Stoerung, keine Verbindung) gilt als
 * bestehende Sitzung — im Zweifel wird nicht geraeumt.
 */
export async function sitzungBesteht(cookies: KeksLeser): Promise<boolean> {
	const sitzung = cookies.get('gz_session');
	if (!sitzung) return false;
	try {
		const res = await fetch(`${API()}/api/auth/profile`, {
			headers: { Cookie: `gz_session=${sitzung}` },
			signal: AbortSignal.timeout(3000)
		});
		return res.status !== 401;
	} catch {
		return true;
	}
}
