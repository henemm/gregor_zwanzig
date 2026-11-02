// Pruefstand fuer die Tests zur Begriff-Erklaerung (ⓘ) und Infobox.
//
// Rendert ECHTE Komponenten serverseitig (svelte/server) — kein Mock. Die
// noch nicht existierenden Bausteine werden NIE auf Modulebene importiert,
// sondern erst im Test (`lade(...)`): sonst bricht die ganze Datei mit EINEM
// Importfehler ab und rot/gruen-Zaehlungen waeren bedeutungslos.
//
// Issue #2727 (Epic #2345, DoD-1, Spec feat_2727_compare_wizardstate_abloesen.md AC-10):
// das geteilte Zustandsmodul des Ortsvergleichs ist abgeloest. Frueher lud dieser Helfer die
// Zustandsklasse VOR den SSR-Hooks (eigener `$state`-Shim, Reihenfolge-Zwang) und reichte eine
// Instanz per Context an `CompareNewEditor`. Beides entfaellt: der Anlege-Editor haelt seinen
// Zustand selbst, Startwerte reisen ueber `stateOverride` (Muster TripNewEditor). Daten-Feldsaetze
// fuer Organismus-Props liefert `compareFeldsatzPruefstand.neuerFeldsatz()`. Die SSR-Hooks werden
// direkt registriert — es gibt kein Modul mehr, das vorher ausserhalb des Compilers laden muss.
//
// Pfadregel #1409: alles relativ zu DIESER Datei.

import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> shared -> components -> lib -> src -> frontend
export const FRONTEND = path.resolve(HERE, '../../../../..');
export const COMPONENTS = path.resolve(HERE, '../..');

register(
	pathToFileURL(path.join(COMPONENTS, 'trip-new/__tests__/ssrRunesHook.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');

/** Laedt ein Modul relativ zu `src/lib/components/` erst beim Aufruf. */
export async function lade(rel: string): Promise<any> {
	return (await import(pathToFileURL(path.join(COMPONENTS, rel)).href)).default;
}

export function renderKomponente(
	Komponente: unknown,
	props: Record<string, unknown>,
	context?: Map<string, unknown>
): string {
	return render(Komponente as never, { props: props as never, ...(context ? { context } : {}) }).body;
}

export async function renderTrip(stateOverride: Record<string, unknown>): Promise<string> {
	const Editor = await lade('trip-new/TripNewEditor.svelte');
	return renderKomponente(Editor, { stateOverride });
}

/** `/compare/new` ohne Context: Name + zwei Orte ueber `stateOverride`, damit die Reiter frei sind. */
export async function renderVergleichNeu(stateOverride: Record<string, unknown>): Promise<string> {
	const Editor = await lade('compare-new/CompareNewEditor.svelte');
	return renderKomponente(Editor, {
		stateOverride: { name: 'Infobox-Test', pickedIds: ['loc-a', 'loc-b'], ...stateOverride }
	});
}

// ── HTML-Leser ───────────────────────────────────────────────────────────────

export function entschluesselt(s: string): string {
	return s
		.replace(/&quot;/g, '"')
		.replace(/&#39;/g, "'")
		.replace(/&lt;/g, '<')
		.replace(/&gt;/g, '>')
		.replace(/&amp;/g, '&');
}

/** Sichtbarer Text: Tags, Kommentare und Attribute raus, Entitaeten aufgeloest. */
export function sichtbarerText(html: string): string {
	return entschluesselt(
		html
			.replace(/<!--[\s\S]*?-->/g, ' ')
			.replace(/<[^>]*>/g, ' ')
			.replace(/\s+/g, ' ')
			.trim()
	);
}

/** Alle data-testid-Werte, die mit `praefix` beginnen (in Dokumentreihenfolge). */
export function testids(html: string, praefix: string): string[] {
	const re = /data-testid="([^"]*)"/g;
	const treffer: string[] = [];
	let m: RegExpExecArray | null;
	while ((m = re.exec(html))) if (m[1].startsWith(praefix)) treffer.push(m[1]);
	return treffer;
}

/** Oeffnende Tags aller Elemente, deren data-testid mit `praefix` beginnt. */
export function tagsMitTestid(html: string, praefix: string): string[] {
	const re = new RegExp(`<[a-zA-Z0-9-]+\\b[^>]*data-testid="${praefix}[^"]*"[^>]*>`, 'g');
	return html.match(re) ?? [];
}

export function attribut(tag: string, name: string): string | null {
	const m = new RegExp(`\\s${name}="([^"]*)"`).exec(tag);
	return m ? entschluesselt(m[1]) : null;
}

/** Inneres HTML des ersten Elements mit exakt diesem Testid (Tag-Nesting zaehlend). */
export function innen(html: string, testid: string, nr = 0): string {
	let von = -1;
	for (let i = 0; i <= nr; i++) {
		von = html.indexOf(`data-testid="${testid}"`, von + 1);
		if (von === -1) throw new Error(`Testid "${testid}" (Nr. ${nr}) fehlt im gerenderten Dokument.`);
	}
	const start = html.lastIndexOf('<', von);
	const tag = /^<([a-zA-Z0-9-]+)/.exec(html.slice(start, start + 40))![1];
	const re = new RegExp(`<${tag}\\b[^>]*>|</${tag}>`, 'g');
	re.lastIndex = start;
	let tiefe = 0;
	let m: RegExpExecArray | null;
	let ende = html.length;
	while ((m = re.exec(html))) {
		if (m[0].startsWith('</')) tiefe--;
		else if (!m[0].endsWith('/>')) tiefe++;
		if (tiefe === 0) {
			ende = m.index + m[0].length;
			break;
		}
	}
	return html.slice(start, ende);
}
