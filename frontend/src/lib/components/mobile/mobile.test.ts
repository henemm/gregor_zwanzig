// TDD RED: Issue #373 — Mobile-Touch-Primitives lib/components/mobile/ (Bridge-Ansatz)
//
// Spec: docs/specs/modules/issue_373_mobile.md
// Vorlage: docs/design-requests/issue_15_atomic_design/spec/mobile-shell.jsx
//
// Source-Inspection-Test (kein Render, keine Mocks): Datei-Existenz, index.ts-
// Re-Exporte, Schluessel-Inhalte (Touch-Maße, a11y, SSR-Festigkeit, Token).
//
// RED vor Implementierung: mobile/-Dateien fehlen → Asserts schlagen fehl.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test src/lib/components/mobile/mobile.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const read = (f: string) => readFileSync(join(here, f), 'utf-8');
const has = (f: string) => existsSync(join(here, f));

const ALL_12 = [
	'MBtn', 'MInput', 'MField', 'MSwitch', 'MTab', 'MIcon',
	'TopAppBar', 'BottomNav', 'Drawer', 'Sheet', 'Toast', 'MobileShell',
];

const NEW_10 = ['MBtn', 'MInput', 'MField', 'MSwitch', 'MTab', 'MIcon', 'Drawer', 'Sheet', 'Toast', 'MobileShell'];

test('#373 AC-1: alle 12 Primitive-Dateien existieren in mobile/', () => {
	for (const name of ALL_12) {
		assert.ok(has(`${name}.svelte`), `mobile/${name}.svelte fehlt`);
	}
	assert.ok(has('index.ts'), 'mobile/index.ts fehlt');
});

test('#373 AC-1: index.ts re-exportiert alle 12 Primitive', () => {
	const idx = read('index.ts');
	for (const name of ALL_12) {
		assert.ok(new RegExp(`\\b${name}\\b`).test(idx), `index.ts exportiert ${name} nicht`);
	}
});

test('#373 AC-2: MSwitch role/aria/data-testid + 44px Hit-Area', () => {
	const sw = read('MSwitch.svelte');
	assert.ok(/role=["']switch["']/.test(sw), 'MSwitch role="switch" fehlt');
	assert.ok(/aria-checked/.test(sw), 'MSwitch aria-checked fehlt');
	assert.ok(/data-testid=["']m-switch["']/.test(sw), 'MSwitch data-testid="m-switch" fehlt');
	assert.ok(/44/.test(sw), 'MSwitch 44px Hit-Area fehlt');
});

test('#373 AC-2: MBtn lg/xl mit Touch-Mindestmaß (44px)', () => {
	const btn = read('MBtn.svelte');
	assert.ok(/\bxl\b/.test(btn), 'MBtn size xl fehlt');
	assert.ok(/44|48|52|56/.test(btn), 'MBtn lg/xl Touch-Höhe (>=44px) fehlt');
});

test('#373 AC-3: MInput ≥16px (kein iOS-Zoom) + data-testid', () => {
	const inp = read('MInput.svelte');
	assert.ok(/16px|font-size:\s*16|text-\[16px\]|fontSize:\s*16/.test(inp), 'MInput 16px (iOS-Zoom-Schutz) fehlt');
	assert.ok(/data-testid=["']m-input["']/.test(inp), 'MInput data-testid="m-input" fehlt');
});

test('#373 AC-4: Overlay-Primitive SSR-fest (kein window/document ohne Guard)', () => {
	for (const name of ['Drawer', 'Sheet', 'Toast', ...NEW_10]) {
		if (!has(`${name}.svelte`)) continue;
		const src = read(`${name}.svelte`);
		const hasRaw = /\b(window|document)\./.test(src);
		const hasGuard = /browser|onMount|onDestroy/.test(src);
		assert.ok(!hasRaw || hasGuard, `${name}: ungeschuetzter window/document-Zugriff (nicht SSR-fest)`);
	}
});

test('#373 AC-6: Token-Disziplin + Varianten (Sheet snap, Toast kind)', () => {
	// Neue Primitive nutzen var(--g-*); kein nackter #hex ausser von Vorlage uebernommen.
	for (const name of NEW_10) {
		const src = read(`${name}.svelte`);
		assert.ok(/var\(--g-/.test(src), `${name}: nutzt keine --g-*-Tokens`);
	}
	const sheet = read('Sheet.svelte');
	assert.ok(/full/.test(sheet) && /half/.test(sheet) && /peek/.test(sheet), 'Sheet snap full|half|peek fehlt');
	const toast = read('Toast.svelte');
	for (const k of ['info', 'success', 'warn', 'error']) {
		assert.ok(toast.includes(k), `Toast kind "${k}" fehlt`);
	}
});

test('#373 F001: MobileShell-Hamburger bind-Kette intakt (mobileMenuOpen propagiert)', () => {
	// MobileShell muss mobileMenuOpen via bind: an den TopAppBar-Wrapper geben,
	// und der Wrapper muss es als $bindable weiterreichen — sonst togglet der
	// Hamburger nicht (latenter Defekt vor Showcase #374).
	const shell = read('MobileShell.svelte');
	assert.ok(/bind:mobileMenuOpen/.test(shell), 'MobileShell: bind:mobileMenuOpen fehlt');
	const wrap = read('TopAppBar.svelte');
	assert.ok(/mobileMenuOpen\s*=\s*\$bindable/.test(wrap), 'mobile/TopAppBar: mobileMenuOpen nicht $bindable');
	assert.ok(/bind:mobileMenuOpen/.test(wrap), 'mobile/TopAppBar: bind:mobileMenuOpen an ui/sidebar fehlt');
});
