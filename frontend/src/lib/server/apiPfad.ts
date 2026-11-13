// Issue #2961 (FE3) — Adressen und Kopfzeilen fuer Aufrufe an die Go-API.
//
// Kennungen aus der Seitenadresse (Routen-Parameter, `?from=`) und die
// Pfadsegmente des Durchreichers `/api/[...path]` sind Nutzereingaben. Sie
// gehen hier geprueft und je Segment kodiert in den Pfad zur Go-API, damit
// ein Wert immer genau EIN Pfadsegment bleibt und weder Pfad noch Abfrage der
// Ziel-Adresse veraendern kann.

/**
 * Zulassungsmuster fuer Entitaets-Kennungen (Trip, Ort, Vergleich), gleich der
 * kanonischen Go-Quelle `store.ValidEntityIDRe` (internal/store/pathsafe.go):
 * erstes Zeichen kein Punkt; nirgends Trenner (`/`, `\\`), Steuerzeichen
 * (U+0000–U+001F, U+007F–U+009F), Zeilen-/Absatztrenner (U+2028/U+2029) oder
 * `?`, `#`, `%`. Bewusst keine ASCII-Liste — Bestandskennungen tragen Umlaute.
 * Paritaet ueber tests/fixtures/entity_id_pattern_parity/faelle.json.
 */
const ENTITAETS_KENNUNG =
	/^[^./\\\x00-\x1f\x7f-\x9f\u2028\u2029?#%][^/\\\x00-\x1f\x7f-\x9f\u2028\u2029?#%]*$/u;

/**
 * Wie Go `url.PathEscape`: diese Zeichen sind in einem Pfadsegment erlaubt und
 * bleiben unkodiert, damit die Go-Seite dieselbe Adresse sieht wie bisher.
 */
const SEGMENT_ERLAUBT = /%(24|26|2B|2C|3A|3B|3D|40)/giu;

/** Kodiert einen (bereits dekodierten) Wert als genau ein Pfadsegment. */
export function segmentKodieren(wert: string): string {
	return encodeURIComponent(wert).replace(SEGMENT_ERLAUBT, (treffer) =>
		decodeURIComponent(treffer)
	);
}

/**
 * Kennung fuer den Pfad zur Go-API — kodiert, oder `null`, wenn sie dem
 * Zulassungsmuster nicht entspricht (der Aufrufer antwortet dann 404).
 */
export function kennungImPfad(kennung: string | null | undefined): string | null {
	if (typeof kennung !== 'string' || !ENTITAETS_KENNUNG.test(kennung)) return null;
	return segmentKodieren(kennung);
}

/** Ein dekodiertes Segment, das nicht in einen Pfad zur Go-API darf. */
function segmentUnzulaessig(segment: string): boolean {
	return (
		segment === '' ||
		segment === '.' ||
		segment === '..' ||
		segment.includes('/') ||
		segment.includes('\\') ||
		segment.includes('\x00')
	);
}

/**
 * Zielpfad des Durchreichers zur Go-API aus dem (prozentkodierten) Pfad der
 * eingehenden Anfrage, z. B. `/api/trips/abc` → `/api/trips/abc`.
 *
 * `null`, wenn der Pfad nicht unter `/api/` liegt, ein Segment leer, `.`/`..`
 * oder nicht dekodierbar ist oder nach dem Dekodieren einen Trenner enthaelt.
 * Jedes Segment wird einzeln neu kodiert.
 */
export function proxyZielPfad(pfad: string): string | null {
	if (!pfad.startsWith('/api/')) return null;
	const segmente: string[] = [];
	for (const roh of pfad.slice('/api/'.length).split('/')) {
		let segment: string;
		try {
			segment = decodeURIComponent(roh);
		} catch {
			return null;
		}
		if (segmentUnzulaessig(segment)) return null;
		segmente.push(segmentKodieren(segment));
	}
	return `/api/${segmente.join('/')}`;
}

/**
 * Kopfzeilen, die der Durchreicher von der Browser-Anfrage an die Go-API
 * weitergibt — eine feste Positivliste. `If-Match` gehoert dazu, weil jede
 * Speicherung den Stand der geladenen Fassung mitschickt (Konfliktschutz);
 * `X-Real-IP` wie bei den uebrigen Server-Routen (Anmeldung usw.).
 */
export const PROXY_KOPFZEILEN = [
	'content-type',
	'accept',
	'accept-language',
	'if-match',
	'x-real-ip'
] as const;

/**
 * Baut die Kopfzeilen fuer die Anfrage an die Go-API: nur die Positivliste,
 * dazu das Sitzungs-Cookie `gz_session` — kein anderes Cookie des Browsers.
 */
export function proxyAnfrageKopfzeilen(eingang: Headers, sitzung: string | undefined): Headers {
	const aus = new Headers();
	for (const name of PROXY_KOPFZEILEN) {
		const wert = eingang.get(name);
		if (wert !== null) aus.set(name, wert);
	}
	if (sitzung) aus.set('cookie', `gz_session=${sitzung}`);
	return aus;
}
