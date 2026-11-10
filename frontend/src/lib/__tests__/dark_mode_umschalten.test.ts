// Issue #2400 Fix-Loop 1 (F004): Laufzeit-Umschalten des Dunklen Designs (applyDarkMode, genutzt
// vom Root-Layout fuer den Umschalter in Sidebar und Konto-Blatt).
//
// Ausgefuehrt gegen ein kleines, regelkonformes Dokument (Attribute als Map, style mit
// colorScheme/removeProperty wie CSSStyleDeclaration, querySelector auf meta[name=…]) — keine
// Spiegelung der erwarteten Antwort. Gemessen wird der ZUSTAND nach jedem Klick; theme-color wird
// gegen --g-paper aus app.css (heller :root bzw. Dark-Block) geprueft, nicht gegen die Konstanten.
//
//   cd frontend && npm test -- src/lib/__tests__/dark_mode_umschalten.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { applyDarkMode } from '../darkMode.ts';

const APP_CSS = readFileSync(join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', 'app.css'), 'utf-8');
function paper(kopf: RegExp): string {
	const m = kopf.exec(APP_CSS);
	assert.ok(m, `Block ${kopf} fehlt`);
	return APP_CSS.slice(m!.index).match(/--g-paper\s*:\s*(#[0-9a-fA-F]{6})\b/)![1].toLowerCase();
}
const PAPER_HELL = paper(/:root\s*\{/);
const PAPER_DUNKEL = paper(/:root\[data-theme=(["'])dark\1\]\s*\{/);

class Knoten {
	attrs = new Map<string, string>();
	private props = new Map<string, string>();
	style = (() => {
		const props = this.props;
		return {
			get colorScheme() {
				return props.get('color-scheme') ?? '';
			},
			set colorScheme(v: string) {
				if (v) props.set('color-scheme', v);
				else props.delete('color-scheme');
			},
			removeProperty(n: string) {
				const alt = props.get(n) ?? '';
				props.delete(n);
				return alt;
			}
		};
	})();
	constructor(attrs: Record<string, string> = {}) {
		for (const [k, v] of Object.entries(attrs)) this.attrs.set(k, v);
	}
	setAttribute(n: string, v: string) {
		this.attrs.set(n, String(v));
	}
	removeAttribute(n: string) {
		this.attrs.delete(n);
	}
	getAttribute(n: string) {
		return this.attrs.get(n) ?? null;
	}
}

/** Dokument wie app.html es ausliefert: helle theme-color im Kopf, kein data-theme. */
function dokument() {
	const html = new Knoten({ lang: 'de' });
	const metas = [new Knoten({ name: 'viewport', content: 'width=device-width' }), new Knoten({ name: 'theme-color', content: PAPER_HELL })];
	const doc = {
		documentElement: html,
		querySelector(sel: string) {
			const m = sel.match(/^meta\[name=["']?([\w-]+)["']?\]$/);
			return (m && metas.find((e) => e.getAttribute('name') === m[1])) || null;
		}
	};
	const zustand = () => ({
		theme: html.getAttribute('data-theme'),
		scheme: html.style.colorScheme,
		themeColor: metas[1].getAttribute('content')
	});
	return { doc, zustand };
}

describe('F004: applyDarkMode schaltet data-theme, color-scheme und theme-color zur Laufzeit', () => {
	test('Messaufbau: helles und dunkles --g-paper aus app.css unterscheiden sich', () => {
		assert.equal(PAPER_HELL, '#f6f4ee');
		assert.notEqual(PAPER_DUNKEL, PAPER_HELL);
	});
	test('einschalten: data-theme="dark", color-scheme dark, theme-color = dunkles --g-paper', () => {
		const { doc, zustand } = dokument();
		applyDarkMode(doc, true);
		assert.deepEqual(zustand(), { theme: 'dark', scheme: 'dark', themeColor: PAPER_DUNKEL });
	});
	test('ausschalten nach einschalten: data-theme entfernt, color-scheme leer, theme-color hell', () => {
		const { doc, zustand } = dokument();
		applyDarkMode(doc, true);
		applyDarkMode(doc, false);
		assert.deepEqual(zustand(), { theme: null, scheme: '', themeColor: PAPER_HELL });
	});
	test('hin und zurueck mehrfach bleibt konsistent', () => {
		const { doc, zustand } = dokument();
		for (const dunkel of [true, false, true, true, false]) {
			applyDarkMode(doc, dunkel);
			assert.equal(zustand().theme, dunkel ? 'dark' : null);
			assert.equal(zustand().scheme, dunkel ? 'dark' : '');
			assert.equal(zustand().themeColor, dunkel ? PAPER_DUNKEL : PAPER_HELL);
		}
	});
	test('ohne theme-color-Meta kein Fehler', () => {
		const { doc } = dokument();
		const ohne = { ...doc, querySelector: () => null };
		assert.doesNotThrow(() => applyDarkMode(ohne, true));
	});
});
