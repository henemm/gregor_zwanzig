// #1592 Scheibe C3, Adversary-Runde 2 Finding F001 (HIGH): das `title`-
// Attribut der CAPE-Schwellenzelle (`AlertMetricLevelRow.svelte`) wurde von
// KEINEM Test bewacht — `thresholdTitle()` war nur an der FUNKTION geprüft,
// nicht an der Stelle, wo sie tatsächlich wirkt (Prüfort ≠ Wirkort). Dieser
// Test rendert die echte Svelte-Komponente serverseitig (svelte/server
// `render()`, Hooks: frontend/test-svelte-ssr-hooks.mjs — Vorbild:
// shared/versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts) und
// prüft am erzeugten HTML.
//
// Spec: docs/specs/modules/fix_1592_c3_cape_delta_alarme.md (AC-9)
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/alerts-tab/__tests__/alertMetricLevelRowTitleRender.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> alerts-tab -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const AlertMetricLevelRow = (
	await import(
		pathToFileURL(path.join(FRONTEND, 'src/lib/components/alerts-tab/AlertMetricLevelRow.svelte')).href
	)
).default;

function renderRow(metric: string, label: string, level: string): string {
	return render(AlertMetricLevelRow, {
		props: { metric, label, level, onChange: () => {} }
	}).body;
}

/** Öffnendes `<td ...>`-Tag UND sichtbarer Zellentext der Schwellenzelle
 * dieser Metrik — robust gegen Attributreihenfolge/umgebendes Markup. */
function thresholdCell(html: string, metric: string): { openTag: string; text: string } {
	const marker = `data-testid="alert-threshold-${metric}"`;
	const markerIdx = html.indexOf(marker);
	assert.notEqual(markerIdx, -1, `Testid "alert-threshold-${metric}" nicht im gerenderten HTML gefunden.`);
	const tagStart = html.lastIndexOf('<td', markerIdx);
	assert.notEqual(tagStart, -1, `Kein <td> vor dem Testid "alert-threshold-${metric}" gefunden.`);
	const tagEnd = html.indexOf('>', markerIdx);
	const openTag = html.slice(tagStart, tagEnd + 1);
	const cellEnd = html.indexOf('</td>', tagEnd);
	assert.notEqual(cellEnd, -1, `Kein schliessendes </td> fuer "alert-threshold-${metric}" gefunden.`);
	const text = html
		.slice(tagEnd + 1, cellEnd)
		.replace(/<!--[\s\S]*?-->/g, '')
		.trim();
	return { openTag, text };
}

// ─────────────────────────────────────────────────────────────────────────
// F001: CAPE-Zeile trägt das `title`-Attribut mit der Umrechnungs-Erklärung,
// UND der Zellentext behält das führende "Δ ≥" (das war der Fehler der
// vorigen Fassung, s. capeRichtwertAnzeige.test.ts).
// ─────────────────────────────────────────────────────────────────────────

test('CAPE-Schwellenzelle traegt title="Richtwert — wird je Wettermodell und Gebiet umgerechnet" (F001)', () => {
	const html = renderRow('cape', 'CAPE', 'standard');
	const { openTag, text } = thresholdCell(html, 'cape');

	assert.match(
		openTag,
		/title="Richtwert — wird je Wettermodell und Gebiet umgerechnet"/,
		`CAPE-Zelle muss das erklärende title-Attribut tragen — gerendertes Tag: ${openTag}`
	);
	assert.equal(
		text,
		'Δ ≥ ~600 J/kg',
		'CAPE-Zellentext muss weiterhin mit "Δ ≥" beginnen (Änderungsschwelle, kein absoluter Grenzwert).'
	);
});

// ─────────────────────────────────────────────────────────────────────────
// Gegenprobe: eine andere Metrik bekommt KEIN title-Attribut — auch kein
// leeres title="".
// ─────────────────────────────────────────────────────────────────────────

test('wind_gust-Schwellenzelle traegt KEIN title-Attribut (Gegenprobe F001)', () => {
	const html = renderRow('wind_gust', 'Windböen', 'standard');
	const { openTag, text } = thresholdCell(html, 'wind_gust');

	assert.doesNotMatch(
		openTag,
		/\btitle=/,
		`wind_gust-Zelle darf kein title-Attribut tragen (auch kein title="") — gerendertes Tag: ${openTag}`
	);
	assert.equal(text, 'Δ ≥ 20 km/h', 'wind_gust-Zellentext muss unverändert bleiben.');
});
