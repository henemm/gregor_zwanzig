// doc-compliance-test
// TDD RED — Issue #2400 (Epic #2508): vollständiger Dark Mode — Ratsche gegen harte Farben.
// Spec: docs/specs/modules/fix_2400_dark_mode_vollstaendig.md — AC-11.
//
// Harte Farben folgen dem Dark-Block nicht und erzeugen im Dunkelmodus weiße Karten oder
// unlesbare Statusboxen. Quellcode ist hier GEGENSTAND der Regel (Ausnahme der Test-Politik, wie
// ink4_waechter.test.ts); das Browser-Verhalten belegt e2e/dark-mode-alle-routen.staging.spec.ts.
//
// Regeln:
//  - Treffer: `background(-color): #fff/#ffffff`, `bg-white`, Tailwind-Palettenfarben
//    `bg-|text-|border-<farbe>-NN(N)`, `rgba(26,26,24,…)` (heller Ink-Schatten/-Tint)
//  - Scope-Dateien der Spec (Abschnitt Scope Nr. 7) haben 0 Treffer UND keine Hex-Farbe in einer
//    Farb-Eigenschaft (auch nicht als var()-Fallback) — sie gehen vollständig auf Tokens
//  - übrige Dateien: AUSNAHMEN[datei] ist die Obergrenze (Stand dieser Spec), darf nur sinken;
//    nicht gelistete Datei = 0; Zähler über dem Ist → rot („Zähler senken")
//  - nicht gezählt: app.css (Token-Definitionen), Tests, Zeile/Vorzeile mit `audit:exempt`
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/harte_farben_waechter.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_SRC = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..');

const FARBEN =
	'slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose';
const TREFFER: RegExp[] = [
	/background(?:-color)?\s*:\s*#fff(?:fff)?\b/gi,
	/\bbg-white\b/g,
	new RegExp(`\\b(?:bg|text|border)-(?:${FARBEN})-\\d{2,3}\\b`, 'g'),
	/rgba\(\s*26\s*,\s*26\s*,\s*24\b/g,
	// Fix-Loop 1 (F002): weisse Flaeche als rgba und weisse Schrift — beide folgen dem Dunklen nicht.
	/background(?:-color)?\s*:\s*rgba\(\s*255\s*,\s*255\s*,\s*255\b/gi,
	/(?<![-\w])color\s*:\s*(?:#fff(?:fff)?|white)\b/gi,
	/style:(?:color|background)=["'](?:#fff(?:fff)?|white)["']/gi,
	/\bfg\s*:\s*['"](?:#fff(?:fff)?|white)['"]/gi
];
/** Hex-Farbe in einer Farb-Eigenschaft (auch `var(--g-x, #abc)`-Fallback) — nur für Scope-Dateien. */
const HEX_IN_FARBE = /(?:^|[\s;"'{])(?:color|background(?:-color)?|border(?:-[a-z]+)*|outline(?:-color)?|fill|stroke)\s*:\s*[^;"]*#[0-9a-fA-F]{3,8}\b/g;

/** Scope der Spec (Nr. 7): hier muss alles auf Tokens stehen. */
const SCOPE = [
	'lib/components/shared/corridor-editor/CorridorEditor.svelte',
	'lib/components/shared/corridor-editor/CorridorEditorMobile.svelte',
	'lib/components/trip-detail/waypoints/ProfileEditor.svelte',
	'lib/components/shared/OfflineSperre.svelte',
	'lib/components/ui/SaveIndicator.svelte',
	'lib/components/account/PremiumSmsLinkCard.svelte',
	'routes/account/+page.svelte',
	'routes/login/+page.svelte',
	'routes/register/+page.svelte',
	'routes/verify-email/+page.svelte',
	'routes/magic-link/+page.svelte',
	'routes/reset-password/+page.svelte',
	'routes/forgot-password/+page.svelte',
	'routes/gpx-upload/+page.svelte'
];

/** Bestand außerhalb des Scopes (Stand Spec 2026-11-09): Obergrenze je Datei, darf nur sinken. */
const AUSNAHMEN: Record<string, { n: number; grund: string }> = {
	'lib/components/mobile/Drawer.svelte': { n: 1, grund: 'Scrim (gewollt fix, Spec Out of Scope)' },
	'lib/components/mobile/Sheet.svelte': { n: 2, grund: 'Scrim + Schatten (gewollt fix)' },
	'lib/components/compare/LocationNewModal.svelte': { n: 1, grund: 'Scrim (gewollt fix)' },
	'lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte': { n: 2, grund: 'Scrim + Schatten (gewollt fix)' },
	'lib/brand/BrandSidebar.svelte': { n: 1, grund: 'Tint 5 % hinter Kürzel-Chip' },
	'routes/+layout.svelte': { n: 3, grund: 'Schatten-Fallback in var(--g-elev-3, …)' },
	'routes/email-preview-dev/+page.svelte': { n: 3, grund: 'Entwickler-Vorschau, nicht ausgeliefert' },
	// Fix-Loop 1 (F002): weisser Schalter-Knopf — gewollte Festfarbe laut Spec (Out of Scope „Switch-Knöpfe").
	'lib/components/atoms/Switch.svelte': { n: 1, grund: 'Switch-Knopf weiss (gewollt fix, Spec Out of Scope)' },
	'lib/components/mobile/MSwitch.svelte': { n: 1, grund: 'Switch-Knopf weiss (gewollt fix, Spec Out of Scope)' }
};

function ohneAusgenommen(text: string): string[] {
	const zeilen = text.split('\n');
	return zeilen.filter((z, i) => !/audit:exempt/.test(z) && !(i > 0 && /audit:exempt/.test(zeilen[i - 1])));
}

/** Zählt Treffer der allgemeinen Regel (reine Funktion, auch für die Gegenproben). */
export function zaehleHarteFarben(text: string): number {
	let n = 0;
	for (const z of ohneAusgenommen(text)) for (const r of TREFFER) n += z.match(r)?.length ?? 0;
	return n;
}
/** Zählt Hex-Farben in Farb-Eigenschaften (Scope-Regel). */
export function zaehleHexFarben(text: string): number {
	let n = 0;
	for (const z of ohneAusgenommen(text)) n += z.match(HEX_IN_FARBE)?.length ?? 0;
	return n;
}

function quellDateien(dir: string, out: string[] = []): string[] {
	for (const name of readdirSync(dir)) {
		const p = join(dir, name);
		if (statSync(p).isDirectory()) {
			if (name === '__tests__' || name === 'node_modules') continue;
			quellDateien(p, out);
		} else if (/\.(svelte|css|ts)$/.test(name) && !/\.(test|spec)\.ts$/.test(name) && !/\.d\.ts$/.test(name)) {
			out.push(p);
		}
	}
	return out;
}

const IST: Record<string, number> = {};
for (const f of quellDateien(FRONTEND_SRC)) {
	const rel = relative(FRONTEND_SRC, f).split('\\').join('/');
	if (rel === 'app.css') continue;
	const n = zaehleHarteFarben(readFileSync(f, 'utf-8'));
	if (n) IST[rel] = n;
}

describe('AC-11: Scope-Dateien stehen vollständig auf Tokens', () => {
	for (const rel of SCOPE) {
		test(`${rel}: keine harten Farben`, () => {
			const text = readFileSync(join(FRONTEND_SRC, rel), 'utf-8');
			assert.equal(zaehleHarteFarben(text), 0, `${rel}: ${zaehleHarteFarben(text)} harte Farbe(n) (bg-white, bg-/text-<farbe>-NN, #fff, rgba(26,26,24))`);
			assert.equal(zaehleHexFarben(text), 0, `${rel}: ${zaehleHexFarben(text)} Hex-Farbe(n) in Farb-Eigenschaften — auf --g-* ohne Fallback umstellen`);
		});
	}
});

describe('AC-11: Ratsche — keine neuen harten Farben, Ausnahmeliste darf nur sinken', () => {
	test('keine Datei über ihrer Obergrenze', () => {
		const zuViel = Object.entries(IST)
			.filter(([rel, n]) => !SCOPE.includes(rel) && n > (AUSNAHMEN[rel]?.n ?? 0))
			.map(([rel, n]) => `${rel}: ${n} > ${AUSNAHMEN[rel]?.n ?? 0}`);
		assert.deepEqual(zuViel, [], 'neue harte Farben — auf Tokens umstellen');
	});
	test('keine Obergrenze über dem Ist (Zähler senken)', () => {
		const zuHoch = Object.entries(AUSNAHMEN)
			.filter(([rel, a]) => (IST[rel] ?? 0) < a.n)
			.map(([rel, a]) => `${rel}: Obergrenze ${a.n}, Ist ${IST[rel] ?? 0}`);
		assert.deepEqual(zuHoch, [], 'Ausnahmeliste senken');
	});
	test('Scope-Dateien stehen nicht in der Ausnahmeliste', () => {
		assert.deepEqual(SCOPE.filter((s) => s in AUSNAHMEN), []);
	});
});

describe('Gegenproben der Zählregel', () => {
	test('bg-white in einer Komponente wird gezählt', () => {
		assert.equal(zaehleHarteFarben('<div class="rounded bg-white p-2">'), 1);
	});
	test('Tailwind-Statusbox wird gezählt (bg-green-50 + text-green-800)', () => {
		assert.equal(zaehleHarteFarben('<p class="bg-green-50 text-green-800">ok</p>'), 2);
	});
	test('background:#fff und rgba(26,26,24,…) werden gezählt', () => {
		assert.equal(zaehleHarteFarben('style="background:#fff; box-shadow:0 1px 2px rgba(26, 26, 24, 0.1)"'), 2);
	});
	test('F002: weisse rgba-Flaeche und weisse Schrift werden gezählt', () => {
		assert.equal(zaehleHarteFarben('style="background: rgba(255,255,255,0.4)"'), 1);
		assert.equal(zaehleHarteFarben('.x { color: #fff; } .y { color: white; }'), 2);
		assert.equal(zaehleHarteFarben('<span style:color="#fff" style:background="white">'), 2);
		assert.equal(zaehleHarteFarben("success: { bg: 'var(--g-success)', fg: '#fff' }"), 1);
	});
	test('F002: border-color/background-color weiss als Schrift nicht doppelt, Token-Schrift zählt nicht', () => {
		assert.equal(zaehleHarteFarben('border-color: white; color: var(--g-on-accent);'), 0);
	});
	test('Token-Nutzung zählt nicht', () => {
		assert.equal(zaehleHarteFarben('style="background: var(--g-card); color: var(--g-ink)"'), 0);
	});
	test('Hex-Fallback in Farb-Eigenschaft wird in Scope-Dateien gezählt, Issue-Nummern nicht', () => {
		assert.equal(zaehleHexFarben('  color: var(--g-good, #2e7d32);'), 1);
		assert.equal(zaehleHexFarben('  /* Issue #880: fixes Overlay */'), 0);
	});
	test('audit:exempt in der Vorzeile nimmt die Zeile aus', () => {
		assert.equal(zaehleHarteFarben('<!-- audit:exempt -->\n<div class="bg-white">'), 0);
	});
});
