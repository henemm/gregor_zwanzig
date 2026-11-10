// Issue #2794 S3a, Teil-PR 3, Fix-Loop 3 (Befund C1): tiefe Kopie reiner Daten, die auch
// Svelte-5-`$state`-Proxys verkraftet. `structuredClone` wirft auf einem Proxy DataCloneError
// (Stand des Reiters und Abo-Props sind im Browser Proxys); eine JSON-Rundreise wuerde `NaN`
// (ungueltige Eingabe in „Grenzen ändern") zu `null` verfaelschen. Darum: rekursiv ueber
// Arrays und Objekte, Werte unveraendert.
// Kein Browser-/SvelteKit-Import, lauffaehig unter node --experimental-strip-types.

export function klon<T>(x: T): T {
	if (Array.isArray(x)) return x.map((e) => klon(e)) as T;
	if (x !== null && typeof x === 'object') {
		const aus: Record<string, unknown> = {};
		for (const [k, v] of Object.entries(x as Record<string, unknown>)) aus[k] = klon(v);
		return aus as T;
	}
	return x;
}
