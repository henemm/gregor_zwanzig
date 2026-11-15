// doc-compliance-test
// Fix #2944 (Ortsvergleich: „Nicht im Briefing" zeigt nur Metriken des Vergleichs-Katalogs), Adversary-Finding F001.
// Spec: docs/specs/modules/fix_2944_orts_nicht_im_briefing.md
//
// Warum ein Quelltext-Verdrahtungstest statt Server-Render:
//   Die Filterung selbst ist als reine Funktion `briefingAngebot` in
//   src/lib/components/shared/wetter-tab/__tests__/nicht_im_briefing_kontextkatalog.test.ts verhaltensgeprüft.
//   Im Organismus WetterTabInhalt wirkt sie erst nach `laden()`, das nur in `onMount` läuft. Ein Server-Render
//   (svelte/server) führt onMount nie aus und zeigt nur die Ladeanzeige; die Chips „Nicht im Briefing" sind
//   ohne Produktionsumbau oder Mock-Theater nicht erreichbar. Deshalb sichert dieser Test die Verdrahtung
//   im <script> von WetterTabInhalt.svelte:
//     (1) `nichtIm` entsteht über `briefingAngebot(context, …, katalogIds)` — erstes Argument genau `context`
//         (kein fest verdrahtetes 'route'/'vergleich'), letztes genau `katalogIds`;
//     (2) `laden()` weist `katalogIds` aus dem geladenen Vergleichs-Katalog (`katalog`, `metric_id`) zu;
//     (3) keine zweite/alte Ableitung von `nichtIm` über `Object.keys(daten.eig)` minus Auswahl;
//     (4) NichtImBriefing bekommt genau `nichtIm`.
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/fix2944_nicht_im_briefing_verdrahtung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DATEI = path.resolve(HERE, '..', 'wetter-tab', 'WetterTabInhalt.svelte');
const QUELLE = readFileSync(DATEI, 'utf8');

/** Instanz-<script> ohne Kommentare und mit normalisiertem Leerraum. */
function skript(): string {
	const ast: any = parse(QUELLE, { modern: true });
	assert.ok(ast.instance, 'WetterTabInhalt.svelte hat kein <script>');
	const roh = QUELLE.slice(ast.instance.content.start, ast.instance.content.end);
	return roh
		.replace(/\/\*[\s\S]*?\*\//g, ' ')
		.replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1 ')
		.replace(/\s+/g, ' ');
}
const S = skript();

/** Rumpf der Deklaration `const nichtIm = $derived( … );` (Klammerzählung). */
function nichtImRumpf(): string {
	const start = S.indexOf('const nichtIm = $derived(');
	assert.ok(start >= 0, '`const nichtIm = $derived(` fehlt in WetterTabInhalt.svelte');
	let i = start + 'const nichtIm = $derived('.length;
	let tiefe = 1;
	for (; i < S.length && tiefe > 0; i++) {
		if (S[i] === '(') tiefe++;
		else if (S[i] === ')') tiefe--;
	}
	return S.slice(start, i);
}

/** Rumpf von `async function laden()` bis zum folgenden `onMount(`. */
function ladenRumpf(): string {
	const start = S.indexOf('async function laden()');
	assert.ok(start >= 0, '`async function laden()` fehlt');
	const ende = S.indexOf('onMount(', start);
	assert.ok(ende > start, 'onMount nach laden() fehlt');
	return S.slice(start, ende);
}

describe('Fix #2944 F001: WetterTabInhalt verdrahtet briefingAngebot mit Kontext und Katalog', () => {
	test('(1) nichtIm entsteht über briefingAngebot(context, …, katalogIds)', () => {
		const r = nichtImRumpf();
		const m = r.match(/briefingAngebot\(\s*([^,()]+?)\s*,([^()]*(?:\([^()]*\)[^()]*)*)\)/);
		assert.ok(m, `nichtIm ruft briefingAngebot nicht auf: ${r}`);
		assert.equal(m![1], 'context', `erstes Argument von briefingAngebot muss genau \`context\` sein, ist \`${m![1]}\``);
		const args = m![2].split(',').map((a) => a.trim());
		assert.equal(args[args.length - 1], 'katalogIds', `letztes Argument muss \`katalogIds\` sein, ist \`${args[args.length - 1]}\``);
	});

	test('(2) laden() weist katalogIds aus dem Vergleichs-Katalog (metric_id) zu', () => {
		const r = ladenRumpf();
		assert.match(r, /VERGLEICHS_KATALOG\[\s*context\s*\]\(\)/, 'laden() lädt den Vergleichs-Katalog nicht kontextabhängig');
		const m = r.match(/katalogIds\s*=\s*([^;]+);/);
		assert.ok(m, 'laden() setzt katalogIds nicht');
		assert.match(m![1], /\bkatalog\b/, `katalogIds wird nicht aus \`katalog\` gebildet: ${m![1]}`);
		assert.match(m![1], /metric_id/, `katalogIds nutzt nicht metric_id: ${m![1]}`);
	});

	test('(3) keine alte Ableitung von nichtIm über Object.keys(daten.eig)', () => {
		const r = nichtImRumpf();
		assert.doesNotMatch(r, /Object\.keys\(\s*daten\.eig\s*\)/, 'nichtIm leitet wieder alle Eigenschaften ab statt briefingAngebot');
		assert.equal(S.split('const nichtIm').length - 1, 1, 'nichtIm darf nur einmal deklariert sein');
	});

	test('(4) NichtImBriefing bekommt genau nichtIm', () => {
		assert.match(QUELLE, /<NichtImBriefing\s[^>]*metriken=\{nichtIm\}/, 'NichtImBriefing erhält nicht metriken={nichtIm}');
	});
});
