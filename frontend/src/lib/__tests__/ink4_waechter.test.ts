// doc-compliance-test
// TDD RED — Issue #2371 (Epic #2508 Strang B, ADR-0008 „Kontrast vor Optik").
// Spec: docs/specs/modules/ink4_kontrast_2371.md — AC-4, AC-6.
//
// Ratschen-Wächter: `color: var(--g-ink-4)` (2,7:1) darf nur Placeholder und deaktivierte
// Eingaben färben. Quellcode ist hier GEGENSTAND der Regel (Ausnahme der Test-Politik, wie die
// i18n-Ratschen); das Browser-Verhalten belegt die Staging-Messung e2e/ink4-kontrast.staging.spec.ts.
//
// Regeln:
//  - je Datei zählt die Anzahl der Treffer; AUSNAHMEN[datei] ist die erlaubte Obergrenze
//  - nicht gelistete Datei = 0; Scope-Dateien stehen NICHT in der Liste
//  - Treffer über dem Zähler → rot; Zähler über dem Ist → rot („Zähler senken", Ratsche)
//  - nicht gezählt: ::placeholder, :disabled, Zeile/Vorzeile mit `audit:exempt`
//
// Pfadregel #1409: Pfade relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/ink4_waechter.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_SRC = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..');

/**
 * Nur Textfarbe — nicht `background-color`/`border-color`/`text-decoration-color`/`stroke`.
 * Drei Schreibweisen: CSS `color: var(--g-ink-4)`, Interpolation im style-Attribut
 * `color:{… 'var(--g-ink-4)' …}` und Svelte-Direktive `style:color="var(--g-ink-4)"`
 * bzw. `style:color={… 'var(--g-ink-4)' …}` (Ternär).
 */
const TREFFER =
	/(?<![-\w])color\s*:\s*(?:var\(--g-ink-4\)|\{[^}]*['"]var\(--g-ink-4\)['"])|(?<![-\w])style:color=(?:"var\(--g-ink-4\)"|\{[^}]*['"]var\(--g-ink-4\)['"])/;

/** Scope aus der Spec: hier muss der Zähler 0 sein. */
const SCOPE = [
	'lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte',
	'lib/components/shared/anlege-rahmen/AnlegeFortschritt.svelte',
	'lib/components/trip-new/TripNewEditor.svelte',
	'lib/components/compare-new/CompareNewEditor.svelte',
	'routes/archiv/+page.svelte',
	'lib/components/compare/steps/Step2Orte.svelte',
	// Hinweistext unter Feldern in /compare/new (CompareNewEditor rendert <Field hint=…>)
	'lib/components/molecules/Field.svelte'
];

/** Bestand außerhalb des Scopes: Obergrenze je Datei, darf nur sinken. */
const AUSNAHMEN: Record<string, number> = {
	// #2879: Lesetext der Listen, Uebersicht und Etappen auf --g-ink-3 — Rest sind Chevron-Icons.
	'lib/components/organisms/ListTableRow.svelte': 1,
	'lib/components/compare/LocationNewModal.svelte': 7,
	'lib/components/shared/AlertChannelPicker.svelte': 1,
	'lib/components/shared/layout-tab/LTCapNote.svelte': 1,
	'lib/components/shared/layout-tab/LTChannelPicker.svelte': 1,
	'lib/components/shared/layout-tab/LayoutTab.svelte': 1,
	'lib/components/shared/dnd/DragHandle.svelte': 1,
	'lib/components/shared/versand-tab/VTSchedulePlan.svelte': 1,
	'lib/components/shared/hub-uebersicht/HubUebersicht.svelte': 1,
	'lib/components/shared/weather-metrics-tab/WeatherV2Grundauswahl.svelte': 1,
	'lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte': 4,
	'lib/components/mobile/StageCardM.svelte': 1,
	'lib/components/trip-detail/WeatherV2Kanaele.svelte': 2,
	'lib/components/mobile/DrawerGroup.svelte': 1,
	'lib/components/mobile/Sheet.svelte': 1,
	'lib/components/molecules/BriefingTimelineRow.svelte': 1,
	'lib/components/organisms/MetricOffShelf.svelte': 2,
	'lib/components/organisms/PresetRail.svelte': 1
};

/** Zählt gemeldete Zeilen eines Quelltexts (reine Funktion, auch für die Gegenproben). */
export function zaehleVerstoesse(text: string): number {
	const zeilen = text.split('\n');
	let n = 0;
	for (let i = 0; i < zeilen.length; i++) {
		const z = zeilen[i];
		if (!TREFFER.test(z)) continue;
		if (/audit:exempt/.test(z) || (i > 0 && /audit:exempt/.test(zeilen[i - 1]))) continue;
		// Selektor-Kontext: Regel in einem ::placeholder- oder :disabled-Block (bis 3 Zeilen davor)
		const kontext = zeilen.slice(Math.max(0, i - 3), i + 1).join('\n');
		if (/::placeholder|:disabled/.test(kontext)) continue;
		n++;
	}
	return n;
}

function alleSvelte(dir: string, out: string[] = []): string[] {
	for (const name of readdirSync(dir)) {
		if (name === 'node_modules' || name === '__tests__') continue;
		const p = join(dir, name);
		if (statSync(p).isDirectory()) alleSvelte(p, out);
		else if (name.endsWith('.svelte')) out.push(p);
	}
	return out;
}

function istStand(): Record<string, number> {
	const ergebnis: Record<string, number> = {};
	for (const datei of alleSvelte(FRONTEND_SRC)) {
		const n = zaehleVerstoesse(readFileSync(datei, 'utf8'));
		if (n > 0) ergebnis[relative(FRONTEND_SRC, datei)] = n;
	}
	return ergebnis;
}

test('AC-4: Scanner meldet Fließtext, lässt Platzhalter-Regeln, disabled und audit:exempt durch', () => {
	assert.equal(zaehleVerstoesse('<span style="font-size: 11px; color: var(--g-ink-4);">x</span>'), 1);
	assert.equal(zaehleVerstoesse('<span style="color:var(--g-ink-4)">x</span>'), 1);
	assert.equal(zaehleVerstoesse('input::placeholder { color: var(--g-ink-4); }'), 0);
	assert.equal(zaehleVerstoesse('input:disabled {\n\tcolor: var(--g-ink-4);\n}'), 0);
	assert.equal(zaehleVerstoesse('<svg style="color: var(--g-ink-4)"/> <!-- audit:exempt: Symbol -->'), 0);
	assert.equal(zaehleVerstoesse('<!-- audit:exempt: Symbol -->\n<svg style="color: var(--g-ink-4)"/>'), 0);
	assert.equal(zaehleVerstoesse('<div style="background-color: var(--g-ink-4)"></div>'), 0);
});

test('AC-4: Scanner meldet auch die Svelte-Direktive style:color, aber nicht background/border/stroke', () => {
	assert.equal(zaehleVerstoesse('<div\n\tstyle:font-size="12px"\n\tstyle:color="var(--g-ink-4)"\n>x</div>'), 1);
	assert.equal(zaehleVerstoesse(`<span style:color={on ? 'var(--g-ink)' : 'var(--g-ink-4)'}>x</span>`), 1);
	assert.equal(zaehleVerstoesse('<span style:color="var(--g-ink-4)"></span> <!-- audit:exempt: Symbol -->'), 0);
	assert.equal(zaehleVerstoesse('<!-- audit:exempt: Symbol -->\n<svg style:color="var(--g-ink-4)"/>'), 0);
	assert.equal(zaehleVerstoesse('<div style:background-color="var(--g-ink-4)"></div>'), 0);
	assert.equal(zaehleVerstoesse('<div style:border-color="var(--g-ink-4)"></div>'), 0);
	assert.equal(zaehleVerstoesse('<path style:stroke="var(--g-ink-4)"/>'), 0);
	assert.equal(zaehleVerstoesse('<span style:color="var(--g-ink-3)">x</span>'), 0);
});

test('AC-4: Scanner meldet Interpolation color:{…} im style-Attribut, nicht background/border', () => {
	assert.equal(zaehleVerstoesse(`<span style="font-size:9px; color:{active ? 'var(--g-accent-deep)' : 'var(--g-ink-4)'};">x</span>`), 1);
	assert.equal(zaehleVerstoesse(`<span style="color: {on ? "var(--g-ink-4)" : 'var(--g-ink)'}">x</span>`), 1);
	assert.equal(zaehleVerstoesse(`<span style="background:{on ? 'var(--g-ink)' : 'var(--g-ink-4)'}">x</span>`), 0);
	assert.equal(zaehleVerstoesse(`<span style="border-color:{on ? 'var(--g-ink)' : 'var(--g-ink-4)'}">x</span>`), 0);
	assert.equal(zaehleVerstoesse(`<span style="color:{on ? 'var(--g-ink)' : 'var(--g-ink-3)'}">x</span>`), 0);
	assert.equal(zaehleVerstoesse(`<!-- audit:exempt: Symbol -->\n<svg style="color:{on ? 'a' : 'var(--g-ink-4)'}"/>`), 0);
});

test('AC-6: Scope-Dateien (Anlege-Editoren, Rahmen, Archiv, Organismen) haben 0 Treffer', () => {
	const ist = istStand();
	const verstoesse = SCOPE.filter((d) => (ist[d] ?? 0) > 0).map((d) => `${d}: ${ist[d]}`);
	assert.deepEqual(verstoesse, [], `Scope-Dateien mit color: var(--g-ink-4) (muss --g-ink-3 sein):\n${verstoesse.join('\n')}`);
});

test('AC-6: kein Treffer über dem Zähler, keine nicht gelistete Datei mit Treffern', () => {
	const ist = istStand();
	const zuViel = Object.entries(ist)
		.filter(([d, n]) => n > (AUSNAHMEN[d] ?? 0))
		.map(([d, n]) => `${d}: ${n} > erlaubt ${AUSNAHMEN[d] ?? 0}`);
	assert.deepEqual(zuViel, []);
});

test('AC-6: Zähler größer als Ist → rot („Zähler senken", Ratsche darf nur sinken)', () => {
	const ist = istStand();
	const zuHoch = Object.entries(AUSNAHMEN)
		.filter(([d, n]) => (ist[d] ?? 0) < n)
		.map(([d, n]) => `${d}: Zähler ${n}, Ist ${ist[d] ?? 0} — Zähler senken`);
	assert.deepEqual(zuHoch, []);
});

test('AC-6: Scope-Dateien stehen nicht in der Ausnahmeliste', () => {
	const drin = SCOPE.filter((d) => d in AUSNAHMEN);
	assert.deepEqual(drin, []);
});
