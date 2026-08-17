// SSR-Renderharness fuer TripNewEditor.svelte (Issue #1738).
//
// Rendert die ECHTE Anlege-Komponente serverseitig (svelte/server `render`) —
// keine Mocks, keine Quelltext-Greps. Vorbild:
// shared/versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts.
//
// TEST-SEAM (RED-Infrastruktur, Muster `profileOverride` aus #1510):
// TripNewEditor haelt Tab-Auswahl, Wetter-Kanaele, Etappen und die
// Viewport-Erkennung ausschliesslich in internem `$state`; `isMobileViewport`
// entsteht sogar erst in `onMount`, das `svelte/server` nicht ausfuehrt. Ohne
// Vorbelegung ist der Zeitplan-Tab im Test nicht erreichbar und AC-5
// ("schmale UND breite Ansicht") gar nicht messbar. Diese Tests verlangen
// deshalb eine optionale Prop `stateOverride` (Form s. TripNewStateOverride
// unten); ohne Uebergabe bleibt das Verhalten unveraendert.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.

import { register } from 'node:module';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> trip-new -> components -> lib -> src -> frontend
export const FRONTEND = path.resolve(HERE, '../../../../..');

// Reihenfolge: erst der Runen-/$app-Hook (bits-ui liefert unkompilierte
// `*.svelte.js`-Runenmodule aus, `$app/*` existiert ausserhalb von Vite nicht),
// danach der `.svelte`-Compiler-Hook.
register(pathToFileURL(path.join(HERE, 'ssrRunesHook.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

export interface TripNewStateOverride {
	/** Offener Tab beim Rendern (Default 'route'). */
	activeTab?: string;
	/** Ersetzt die matchMedia-Erkennung, die sonst erst in onMount entsteht. */
	isMobileViewport?: boolean;
	/** Wetter-Kanaele aus dem Metriken-Tab (display_config.channels). */
	channels?: { email: boolean; telegram: boolean; sms: boolean };
	reportConfig?: Record<string, unknown>;
	name?: string;
	startDate?: string;
	stageNames?: string[];
}

const { render } = await import('svelte/server');
const TripNewEditor = (
	await import(
		pathToFileURL(path.join(FRONTEND, 'src/lib/components/trip-new/TripNewEditor.svelte')).href
	)
).default;

/** Rendert /trips/new serverseitig mit vorbelegtem Anlege-Zustand. */
export function renderTripNew(stateOverride: TripNewStateOverride): string {
	return render(TripNewEditor, { props: { stateOverride } }).body;
}

/** Positivkontrolle: die Vorbelegung hat gegriffen, der gewuenschte Tab ist
 *  wirklich offen. Ohne sie waere kein Befund unten von "der Harness kommt gar
 *  nicht am Zeitplan-Tab an" zu unterscheiden. */
export function assertTabOffen(html: string, tab: string): void {
	for (const marker of ['trip-new-name-input-desktop', 'trip-new-name-input-mobile']) {
		assert.ok(
			!html.includes(`data-testid="${marker}"`),
			`Vorbelegung stateOverride.activeTab="${tab}" wurde nicht beachtet — es rendert weiter ` +
				`der Route-Tab (${marker} im Dokument). Ohne diese Prop ist der Zeitplan-Tab im ` +
				'SSR-Test nicht erreichbar (s. TEST-SEAM im Kopf von tripNewSsr.ts).'
		);
	}
}

export function countTestid(html: string, testid: string): number {
	return html.split(`data-testid="${testid}"`).length - 1;
}

/** `<input …>`-Tag direkt hinter dem gegebenen Testid. */
export function checkboxInputTag(html: string, testid: string): string {
	const mi = html.indexOf(`data-testid="${testid}"`);
	assert.notEqual(mi, -1, `Testid "${testid}" fehlt im gerenderten Zeitplan-Tab.`);
	const start = html.indexOf('<input', mi);
	assert.notEqual(start, -1, `Kein <input> hinter Testid "${testid}".`);
	return html.slice(start, html.indexOf('>', start) + 1);
}

/** true nur, wenn das boolsche Attribut im Tag gesetzt ist (Svelte-SSR rendert
 *  es als `x=""` oder laesst es bei `false` ganz weg). */
export function hatAttribut(inputTag: string, name: string): boolean {
	return new RegExp(`\\b${name}(=""|(?=[\\s/>]))`).test(inputTag);
}

/** Sichtbarer Text (Tags + Svelte-Kommentaranker raus). */
export function visibleText(html: string): string {
	return html
		.replace(/<!--[\s\S]*?-->/g, ' ')
		.replace(/<[^>]*>/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
}

/** Aeusseres HTML des Elements mit dem gegebenen Testid (Tag-Nesting zaehlend). */
export function outerHtml(html: string, testid: string): string {
	const mi = html.indexOf(`data-testid="${testid}"`);
	assert.notEqual(mi, -1, `Testid "${testid}" fehlt im gerenderten Dokument.`);
	const start = html.lastIndexOf('<', mi);
	const tag = /^<([a-zA-Z0-9-]+)/.exec(html.slice(start, start + 40))?.[1];
	assert.ok(tag, `Kein Tag-Name vor Testid "${testid}".`);
	const re = new RegExp(`<${tag}\\b[^>]*>|</${tag}>`, 'g');
	re.lastIndex = start;
	let depth = 0;
	let m: RegExpExecArray | null;
	while ((m = re.exec(html))) {
		if (m[0].startsWith('</')) {
			depth--;
			if (depth === 0) return html.slice(start, m.index + m[0].length);
		} else if (m[0].endsWith('/>')) {
			if (m.index === start) return m[0];
		} else {
			depth++;
		}
	}
	assert.fail(`Element zu Testid "${testid}" nicht geschlossen.`);
}

/** In welchem der beiden per CSS umgeschalteten Markup-Baeume steht das Testid?
 *  Der Mobil-Inhaltsbaum ist der LETZTE `.tn-mobile`-Block des Dokuments
 *  (TripNewEditor.svelte:834), alles davor gehoert zum Desktop-Baum. */
export function bereichVon(html: string, testid: string): 'desktop' | 'mobil' {
	const mi = html.indexOf(`data-testid="${testid}"`);
	assert.notEqual(mi, -1, `Testid "${testid}" fehlt im gerenderten Dokument.`);
	const mobileStart = html.lastIndexOf('class="tn-mobile');
	assert.notEqual(mobileStart, -1, 'Mobil-Inhaltsbaum (.tn-mobile) nicht gefunden.');
	return mi < mobileStart ? 'desktop' : 'mobil';
}
