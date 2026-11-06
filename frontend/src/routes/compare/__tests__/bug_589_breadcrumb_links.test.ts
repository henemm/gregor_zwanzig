// Bug #589 — Compare-Detail Breadcrumb anklickbar.
//
// Spec: docs/specs/modules/bug_589_compare_breadcrumb_links.md
//
// AC-2 (Update): Issue #1256 Scheibe S8c (Spec:
// docs/specs/modules/feat_1256_s8c_hub_fidelity.md, AC-10) hat den
// "WORKSPACE"-Krümel auf der Compare-Hub-Seite bewusst entfernt — genau 2 Krümel.
//
// Umgedreht durch #2837 S1 (ADR-0110, Spec docs/specs/modules/rework_2837_s1_hub_kopf.md,
// Entscheidung 4 / AC-4): der Breadcrumb kommt aus dem geteilten HubKopf und lautet wie
// beim Trip „Orts-Vergleiche / <Name des Vergleichs>". Elternteil bleibt Link auf
// /compare (Kern von #589), das Kind ist jetzt der VERGLEICHSNAME statt „Hub" und bleibt
// kein Link; der Krümel „Hub" entfällt. Die Prüfung läuft nicht mehr per Quelltext-Grep,
// sondern am serverseitig gerenderten Markup der echten Seite (Prüfstand f10Pruefstand.ts,
// feste Daten, ohne Netz).
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/routes/compare/__tests__/bug_589_breadcrumb_links.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { baum, alle, einzig, text } from '../../../lib/components/shared/hub-kopf/__tests__/htmlBaum.ts';

const C = await import('../../../lib/components/compare/__tests__/f10Pruefstand.ts');
const SRC = fileURLToPath(new URL('../../..', import.meta.url)); // -> frontend/src/
const HUBKOPF = 'lib/components/shared/hub-kopf/HubKopf.svelte';

const krumen = () => einzig(baum(C.seiteRendern('ruhe', C.vergleichAktiv())), 'hub-kopf-breadcrumb');
const ELTERN = C.trFor('de', 'listen.vergleiche.titel'); // „Orts-Vergleiche"

test('AC-1: „Orts-Vergleiche" ist ein Link auf /compare (Breadcrumb des Hub-Kopfs)', () => {
	const links = alle(krumen(), (n) => n.tag === 'a');
	assert.equal(links.length, 1, `genau ein Link im Breadcrumb erwartet, gefunden ${links.length}`);
	assert.equal(links[0].attrs.href, '/compare');
	assert.equal(text(links[0]), ELTERN);
});

test('AC-2 (Issue #1256 S8c AC-10): genau zwei Krümel, kein "WORKSPACE"-Krümel', () => {
	const k = krumen();
	assert.ok(!/WORKSPACE/i.test(text(k)), 'Regression zu #1256 S8c AC-10: "WORKSPACE"-Krümel im Breadcrumb');
	const teile = text(k).split('/').map((s) => s.trim()).filter(Boolean);
	assert.deepEqual(teile, [ELTERN, 'Skitouren Tirol'], `Krümel: ${JSON.stringify(teile)}`);
});

test('AC-3 (#2837 S1): das Kind ist der Vergleichsname, kein Link; kein Krümel „Hub"', () => {
	const k = krumen();
	const links = alle(k, (n) => n.tag === 'a');
	assert.ok(text(k).includes('Skitouren Tirol'), `Vergleichsname fehlt: „${text(k)}"`);
	assert.ok(!links.some((a) => text(a).includes('Skitouren Tirol')), 'der Vergleichsname darf kein Link sein');
	assert.ok(!/(?<![A-Za-zÄÖÜäöü])Hub(?![A-Za-zÄÖÜäöü])/.test(text(k)), `Krümel „Hub" steht noch: „${text(k)}"`);
	assert.ok(!/DETAIL/i.test(text(k)), '"DETAIL" darf nicht im Breadcrumb stehen');
});

test('AC-4: Breadcrumb-Links haben visuelles Hover-Feedback (im geteilten HubKopf)', () => {
	const link = alle(krumen(), (n) => n.tag === 'a')[0];
	const klasse = link?.attrs.class ?? '';
	const src = readFileSync(join(SRC, HUBKOPF), 'utf8');
	const hasHoverStyle =
		/\bhover:underline\b/.test(klasse) ||
		(/\bbreadcrumb-link\b/.test(klasse) && /\.breadcrumb-link:hover[^}]*text-decoration:\s*underline/.test(src));
	assert.ok(hasHoverStyle, `Breadcrumb-Link ohne Hover-Feedback (class="${klasse}")`);
});
