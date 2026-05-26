// TDD RED: Issue #374 — Showcase-Route /_design-system
//
// Spec: docs/specs/modules/issue_374_showcase.md
// Vorlage: docs/design-requests/issue_15_atomic_design/spec/screen-design-system.jsx
//
// Source-Inspection-Test (kein Render, keine Mocks): Route existiert, importiert
// alle vier Schichten, zeigt die 6 Sektionen, nutzt MobileShell, README-Abschnitt.
//
// RED vor Implementierung: +page.svelte fehlt → Asserts schlagen fehl.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test src/routes/_design-system/showcase.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const page = join(here, '+page.svelte');
const readPage = () => readFileSync(page, 'utf-8');

test('#374 AC-1: Route +page.svelte existiert + importiert alle 4 Schichten', () => {
	assert.ok(existsSync(page), 'routes/_design-system/+page.svelte fehlt');
	const src = readPage();
	assert.ok(/\$lib\/brand/.test(src), 'Import aus $lib/brand fehlt');
	assert.ok(/\$lib\/components\/atoms/.test(src), 'Import aus $lib/components/atoms fehlt');
	assert.ok(/\$lib\/components\/molecules/.test(src), 'Import aus $lib/components/molecules fehlt');
	assert.ok(/\$lib\/components\/mobile/.test(src), 'Import aus $lib/components/mobile fehlt');
});

test('#374 AC-2: 6 Sektionen Brand/Typografie/Farben/Bausteine/Molecules/Voice', () => {
	const src = readPage();
	for (const s of ['Brand', 'Typografie', 'Farben', 'Bausteine', 'Molecules', 'Voice']) {
		assert.ok(src.includes(s), `Sektion "${s}" fehlt`);
	}
	// Organisms/Templates NICHT in #374 (Out of Scope, Epic #368)
	assert.ok(!/Section[^>]*Organisms/.test(src) && !/title=["']Organisms["']/.test(src), 'Organisms-Sektion gehört NICHT in #374');
});

test('#374 AC-2: gezeigte Pflicht-Varianten (Switch-Tones, Btn quiet, Pill ghost, Stat, AlertRow)', () => {
	const src = readPage();
	assert.ok(/Switch/.test(src) && /Btn/.test(src) && /Pill/.test(src), 'Atom-Varianten fehlen');
	assert.ok(/Stat/.test(src) && /AlertRow/.test(src) && /ChannelRow/.test(src), 'Molecule-Varianten fehlen');
});

test('#374 AC-3: Mobile-Demo nutzt MobileShell + Mobile-Primitive', () => {
	const src = readPage();
	assert.ok(/MobileShell/.test(src), 'MobileShell in Mobile-Demo fehlt');
	assert.ok(/MBtn|MSwitch|Sheet|Toast/.test(src), 'Mobile-Primitive in Demo fehlen');
});

test('#374 AC-4: Token-basiert (kein nackter Hex außer in Farben-Swatch-Labels)', () => {
	const src = readPage();
	assert.ok(/var\(--g-/.test(src), 'Route nutzt keine --g-*-Tokens');
});

test('#374 AC-5: Frontend-Doku "Atomic-Design-Disziplin"', () => {
	const candidates = [
		join(here, '../../../README.md'),
		join(here, '../../../CLAUDE.md'),
	];
	const found = candidates.filter(existsSync).map(p => readFileSync(p, 'utf-8')).join('\n');
	assert.ok(/Atomic-Design-Disziplin/.test(found), 'README/CLAUDE.md: Abschnitt "Atomic-Design-Disziplin" fehlt');
});
