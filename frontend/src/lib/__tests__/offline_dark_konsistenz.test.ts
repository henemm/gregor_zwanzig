// doc-compliance-test
// TDD RED — Issue #2400 (Epic #2508): vollständiger Dark Mode — Offline-Seite.
// Spec: docs/specs/modules/fix_2400_dark_mode_vollstaendig.md — AC-10 (Konsistenz-Teil).
//
// static/offline.html ist bewusst eigenständig (kein app.css, siehe Kommentar dort) und trägt
// darum eine zweite Kopie der Farbwerte. Dieser Test ist eine Konsistenzprüfung ZWEIER Quellen
// der Wahrheit (Spec: „Werte-Gleichheit, damit sie nicht auseinanderlaufen") und ersetzt nicht
// den Browser-Nachweis aus AC-10 (e2e/dark-mode-alle-routen.staging.spec.ts) bzw. die
// Skript-Logik (dark_mechanik.test.ts). Den Kontrast der Offline-Seite im Dark (inkl. der
// Hinweis-Box mit eigenen Farben) misst der Staging-Durchlauf am gerenderten DOM.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/offline_dark_konsistenz.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..');
const APP_CSS = readFileSync(join(FRONTEND, 'src/app.css'), 'utf-8');
const OFFLINE = readFileSync(join(FRONTEND, 'static/offline.html'), 'utf-8');

function blockNach(css: string, kopf: RegExp, was: string): string {
	const m = kopf.exec(css);
	assert.ok(m, `${was}: Block fehlt`);
	const auf = css.indexOf('{', m!.index);
	let tiefe = 0;
	for (let i = auf; i < css.length; i++) {
		if (css[i] === '{') tiefe++;
		else if (css[i] === '}' && --tiefe === 0) return css.slice(auf + 1, i);
	}
	throw new Error(`${was}: Block ohne Ende`);
}
const wert = (block: string, name: string): string | null =>
	block.match(new RegExp(`(?:^|[;{\\s])--${name}\\s*:\\s*([^;]+);`))?.[1].trim().toLowerCase() ?? null;

const appDark = () => blockNach(APP_CSS, /:root\[data-theme=(["'])dark\1\]\s*\{/, 'app.css Dark-Block');
/** Dark-Regel der Offline-Seite: Selektor mit [data-theme="dark"] (auf :root oder html). */
const offlineDark = () => blockNach(OFFLINE, /(?::root|html)\[data-theme=(["'])dark\1\]\s*\{/, 'offline.html Dark-Regel');

/** Wert eines app.css-Dark-Tokens, var() im Dark-Block aufgelöst. */
function appDarkHex(name: string): string {
	const w = wert(appDark(), name);
	assert.ok(w, `app.css Dark-Block ohne --${name}`);
	const v = w!.match(/^var\(--([a-z0-9-]+)\)$/);
	return v ? appDarkHex(v[1]) : w!;
}

/** Offline-Variable → app.css-Token (gleiche Rolle). */
const PAARE: Record<string, string> = {
	paper: 'g-paper',
	card: 'g-card',
	ink: 'g-ink',
	'ink-muted': 'g-ink-muted',
	border: 'g-ink-faint'
};

describe('AC-10: offline.html führt dieselben Dark-Werte wie app.css', () => {
	for (const [offline, app] of Object.entries(PAARE)) {
		test(`--${offline} (offline, dunkel) = --${app} (app.css, dunkel)`, () => {
			const o = wert(offlineDark(), offline);
			assert.ok(o, `offline.html Dark-Regel ohne --${offline}`);
			assert.equal(o, appDarkHex(app));
		});
	}
	test('helle Offline-Werte bleiben unverändert', () => {
		const hell = blockNach(OFFLINE, /:root\s*\{/, 'offline.html :root');
		assert.equal(wert(hell, 'paper'), '#f6f4ee');
		assert.equal(wert(hell, 'card'), '#ffffff');
		assert.equal(wert(hell, 'ink'), '#1a1a18');
		assert.equal(wert(hell, 'ink-muted'), '#5c5a52');
	});
});
