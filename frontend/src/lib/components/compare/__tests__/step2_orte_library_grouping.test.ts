// TDD GREEN (war RED, Phase 6 implementiert) — Issue #1256 Scheibe 5:
// Editor-Tab "Orte" (Step2Orte.svelte), Fidelity-Verifikation gegen
// screen-compare-editor.jsx:200-311.
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 5 (AC-12, AC-13)
// Soll (JSX): claude-code-handoff/current/jsx/screen-compare-editor.jsx:206-207
//   const groups = locations.filter(l => l.group !== "Test").reduce((acc, l) => {
//     (acc[l.group] = acc[l.group] || []).push(l); return acc;
//   }, {});
//
// IST-BEFUND aus der RED-Phase (Spec-Phase-Annahme "nur CSS/Grid-Feinschliff,
// kein Verhaltenswechsel erwartet" war stale): Step2Orte.svelte gruppierte
// die Bibliothek bis Phase 6 nach `loc.region` ("loc.region || 'Weitere'").
// `region` ist jedoch NICHT das App-Äquivalent von JSX `l.group`:
//   - `Location.region` (types.ts:7, internal/model/location.go:11) ist die
//     Lawinenwarnregion (LocationForm.svelte:124 Placeholder "z.B. AT-07-23-02")
//     bzw. wird vom Smart-Import-Resolver NIE befüllt (internal/resolver/resolver.go:18
//     deklariert `Region`, aber kein einziger Resolve-Pfad setzt sie — verifiziert
//     per grep, 0 Treffer für "\.Region\s*=" außerhalb trip.go). In der Praxis
//     landet daher (fast) jeder Ort in der "Weitere"-Sammelgruppe.
//   - `Location.group` (types.ts:10) ist explizit als "Legacy-Freitext — bleibt
//     erhalten, wird nicht mehr gelesen" dokumentiert — ebenfalls kein Ziel.
//   - Das App-eigene Äquivalent zu JSX `l.group` (handkuratierte Namen wie
//     "Zillertal"/"Hochkönig"/"Tirol West"/"Mallorca"/"Dolomiten",
//     mock-locations.jsx:4-22) ist die Group-Entity aus Issue #301:
//     `Location.group_id` (types.ts:11, "Source of Truth") + `GET /api/groups`,
//     bereits gekapselt im getesteten, wiederverwendbaren Helper
//     `groupLocations()` (locationHelpers.ts:94-111,
//     locationHelpers.groups.test.ts — grün, Issue #301).
//
// GREEN (Phase 6): Step2Orte.svelte gruppiert jetzt über groupLocations()
// nach group_id, akzeptiert eine `groups: Group[]`-Prop; CompareEditor.svelte
// lädt die Gruppen lazy beim ersten Orte-Tab-Besuch (Muster ltLoadCatalog,
// Scheibe-4-Fix-Loop-F001-Lehre: kein unbedingter Mount-Fetch) und reicht sie
// an Step2Orte + den mobilen Bibliotheks-Sheet durch (dort dieselbe
// groupLocations()-Quelle statt der vorherigen Duplikat-Logik).
//
// Mini-Fix-Loop 1 (Adversary AMBIGUOUS, F001 MEDIUM): das ceGroups-Lazy-Gate
// in CompareEditor.svelte hatte keinen eigenen Regressions-Test, obwohl es
// exakt dieselbe Fehlerklasse abwehrt wie das S4-Pendant
// (compare_editor_layout_tab_wiring.test.ts:343-352). Nachgezogen als eigener
// describe-Block unten (Quelltext-Beleg, kein Produktiv-Code geändert).
//
// Source-Inspection-Tests (KEIN Mock, KEIN jsdom-Mount — Projekt-Idiom, siehe
// corridorEditorMobile.test.ts / issue_683_wizard_remove.test.ts /
// compare_editor_layout_tab_wiring.test.ts): Svelte-5-Komponenten sind ohne
// @testing-library/svelte (nicht in package.json) in diesem Test-Setup nicht
// mountbar — echtes DOM-Verhalten wird ergänzend über Playwright
// (compare-flow-navigation.spec.ts, Scheibe 5) gegen Staging abgesichert.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/step2_orte_library_grouping.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
// __tests__ -> compare -> steps
const STEP2_FILE = join(here, '..', 'steps', 'Step2Orte.svelte');
// __tests__ -> compare
const COMPARE_TABS_FILE = join(here, '..', 'CompareTabs.svelte');

function readStep2(): string {
	return readFileSync(STEP2_FILE, 'utf-8');
}

function readCompareTabs(): string {
	return readFileSync(COMPARE_TABS_FILE, 'utf-8');
}

/**
 * Extrahiert den Body eines `const <name> = $derived.by(() => { ... });`-Blocks
 * per Klammer-Zählung (robuster als ein non-greedy Regex, da der Block selbst
 * verschachtelte `{}` enthält — analog resolveRenderedContent-Idiom in
 * compare_editor_layout_tab_wiring.test.ts, hier für $derived.by statt Snippets).
 */
function extractDerivedByBody(src: string, name: string): string {
	const marker = `const ${name} = $derived.by(() => {`;
	const start = src.indexOf(marker);
	assert.ok(start >= 0, `Marker nicht gefunden: "${marker}" in Step2Orte.svelte`);
	let i = start + marker.length;
	let depth = 1; // die öffnende '{' der marker-Zeile ist bereits gezählt
	const bodyStart = i;
	while (depth > 0 && i < src.length) {
		if (src[i] === '{') depth++;
		else if (src[i] === '}') depth--;
		i++;
	}
	assert.ok(depth === 0, `Keine schließende Klammer für "${name}"-Block gefunden`);
	return src.slice(bodyStart, i - 1);
}

// =============================================================================
// AC-12 (Regressionsanker): Smart-Import/min-2-Validierung/nummerierte Auswahl
// bleiben unverändert funktionsfähig — bereits vor Scheibe 5 1:1 zum Soll.
// Diese Tests sind HEUTE bereits grün (Regressionsschutz, kein RED-Befund).
// =============================================================================

describe('AC-12 (Regressionsanker): Smart-Import bleibt unverändert', () => {
	test('POST /api/locations/resolve wird weiterhin für Smart-Import aufgerufen', () => {
		assert.match(
			readStep2(),
			/api\.post<ResolveResult>\('\/api\/locations\/resolve'/,
			'Smart-Import muss weiterhin POST /api/locations/resolve aufrufen'
		);
	});

	test('min-2-Validierungs-Copy "min. 2 erforderlich" ist weiterhin vorhanden', () => {
		assert.ok(
			readStep2().includes('min. 2 erforderlich'),
			'Counter-Text "min. 2 erforderlich" muss unterhalb von 2 gewählten Orten erhalten bleiben'
		);
	});

	test('">5"-Empfehlungs-Copy "viel — Empfehlung 3–5" ist weiterhin vorhanden', () => {
		assert.ok(
			readStep2().includes('viel — Empfehlung 3–5'),
			'Counter-Text "viel — Empfehlung 3–5" (>5 Orte) muss erhalten bleiben (Soll: screen-compare-editor.jsx:246)'
		);
	});

	test('Picked-Liste nummeriert weiterhin mit "{i + 1}"', () => {
		assert.match(
			readStep2(),
			/\{i \+ 1\}/,
			'Picked-Liste muss weiterhin 1-basiert nummeriert sein (Soll: screen-compare-editor.jsx:258)'
		);
	});

	test('Entfernen-Button (✕) pro Picked-Item ist weiterhin vorhanden', () => {
		assert.match(
			readStep2(),
			/compare-step2-picked-remove-/,
			'Entfernen-Affordanz pro Picked-Item muss erhalten bleiben'
		);
	});
});

// =============================================================================
// AC-13: Bibliotheks-Grid gruppiert nach der App-eigenen Group-Entity
// (group_id/groupLocations), NICHT mehr nach der funktional toten
// region-Gruppierung.
// =============================================================================

describe('AC-13: Bibliotheks-Grid-Gruppierung — Group-Entity statt Region', () => {
	test('libraryGroups verwendet NICHT mehr "loc.region" als Gruppierungs-Schlüssel', () => {
		const body = extractDerivedByBody(readStep2(), 'libraryGroups');
		assert.ok(
			!/loc\.region/.test(body),
			'Der libraryGroups-Block darf loc.region nicht mehr als Gruppierungs-Schlüssel verwenden — ' +
				'region ist die Lawinenwarnregion (nie vom Smart-Import befüllt), nicht die App-Group-Entity. ' +
				'Gefundener Block:\n' + body
		);
	});

	test('libraryGroups nutzt group_id (Group-Entity, Issue #301) für die Gruppierung', () => {
		const body = extractDerivedByBody(readStep2(), 'libraryGroups');
		assert.ok(
			/group_id/.test(body) || /groupLocations\(/.test(body),
			'Der libraryGroups-Block muss Location.group_id (direkt oder über den bestehenden ' +
				'groupLocations()-Helper aus locationHelpers.ts, Issue #301) für die Gruppierung verwenden.'
		);
	});

	test('Step2Orte.svelte importiert den bestehenden groupLocations-Helper statt eigener Region-Reduce-Logik', () => {
		assert.match(
			readStep2(),
			/from ['"]\.\.\/locationHelpers(\.js|\.ts)?['"]/,
			'Step2Orte.svelte soll den bereits getesteten groupLocations()-Helper (locationHelpers.ts) ' +
				'wiederverwenden statt eine eigene Bibliotheks-Gruppierung zu bauen (DRY, Issue #301 bereits gelöst).'
		);
	});

	test('Step2Orte.svelte hat eine "groups"-Prop (Group[]) für die App-Gruppen-Entity', () => {
		const src = readStep2();
		assert.match(
			src,
			/interface Props \{[\s\S]*?groups[\s\S]*?Group\[\][\s\S]*?\}/,
			'Props-Interface muss "groups: Group[]" enthalten, damit der Aufrufer (CompareEditor.svelte) ' +
				'die via GET /api/groups geladenen Gruppen durchreichen kann.'
		);
	});
});

// =============================================================================
// Nebenbefund (selbe Root Cause wie AC-13), GREEN seit Phase 6: die
// Picked-Item-Meta-Zeile zeigt weiterhin eine Meta-Zeile (Soll:
// "{l.group} · {l.elev} m", screen-compare-editor.jsx:261) — Format bleibt
// "<Bezeichner> · <Höhe> m", der Bezeichner ist jetzt der über group_id
// aufgelöste Gruppenname statt loc.region (Fallback weiterhin "—").
// =============================================================================

describe('Nebenbefund (selbe Root Cause wie AC-13), GREEN: Picked-Item-Meta-Zeile', () => {
	test('Picked-Item-Meta-Zeile löst den Gruppennamen über group_id auf (groupNameById), NICHT mehr loc.region', () => {
		const src = readStep2();
		assert.match(
			src,
			/\{groupNameById\.get\(loc\.group_id \?\? ''\) \?\? '—'\} · \{loc\.elevation_m/,
			'Picked-Item-Meta-Zeile muss den Gruppennamen über groupNameById (group_id-Auflösung) zeigen, ' +
				'mit demselben "—"-Fallback wie zuvor bei loc.region.'
		);
		assert.ok(
			!/\{loc\.region \?\? '—'\} · \{loc\.elevation_m/.test(src),
			'Die alte region-basierte Meta-Zeile darf nicht mehr vorkommen.'
		);
	});
});

// =============================================================================
// Fix-Loop 1 (S4b-Migration, Epic #1273): das Gruppen-/Orte-Lazy-Gate lebte
// ursprünglich als ceGroups-Pattern in CompareEditor.svelte (Adversary
// AMBIGUOUS, F001 MEDIUM — s. Historie oben) und wehrte dieselbe Fehlerklasse
// ab wie Scheibe 4 (unbedingter Fetch bei jedem Mount statt gegated auf
// tatsächliche Nutzung). CompareEditor.svelte ist seit S3 nur noch vom
// Create-Wizard erreichbar und wird in S5 gelöscht; der Hub (CompareTabs.svelte)
// implementiert dasselbe Lazy-Gate-Muster unter anderen Namen: statt eines
// $effect auf activeTab === 'orte' triggert hier der Klick auf "Ort
// hinzufügen" (addPanelOpen-Toggle) den Fetch, mit demselben synchronen
// Start-Guard-Muster (addPanelLoadStarted) VOR dem async-Aufruf.
// Migriert im Rahmen von Epic #1273 Scheibe S4b (Unit-Test-Migration).
// =============================================================================

describe('Fix-Loop 1 (S4b-Migration): Orte-Bibliothek-Fetch ist an das Öffnen des "Ort hinzufügen"-Panels gekoppelt, kein unbedingter Mount-Fetch', () => {
	test('GET /api/locations + GET /api/groups laufen aus einer eigenständigen async-Funktion (toggleAddPanel), nicht direkt in onMount', () => {
		const src = readCompareTabs();
		assert.match(
			src,
			/async function toggleAddPanel\(\)[^{]*\{[\s\S]{0,300}?\/api\/locations['"][\s\S]{0,200}?\/api\/groups/,
			'Der Orte-/Gruppen-Fetch muss in einer benannten async-Funktion (toggleAddPanel) stecken, die gezielt getriggert werden kann'
		);
	});

	test('toggleAddPanel() gated den Fetch auf addPanelOpen (einmalig, mit Start-Guard)', () => {
		const src = readCompareTabs();
		assert.match(
			src,
			/async function toggleAddPanel\(\)[\s\S]{0,30}?\{\s*addPanelOpen = !addPanelOpen;\s*\n\s*if \(!addPanelOpen \|\| addPanelLoadStarted\) return;/,
			'toggleAddPanel() muss den Fetch nur ausführen, wenn das Panel geöffnet wird und noch nicht geladen wurde'
		);
		assert.ok(
			/addPanelLoadStarted/.test(src),
			'Ein Start-Guard (addPanelLoadStarted) muss verhindern, dass der Fetch bei jedem erneuten Öffnen des Panels wiederholt wird'
		);
	});

	test('Start-Guard wird SYNCHRON vor dem Fetch-Aufruf gesetzt (verhindert Doppel-Trigger bei schnellen Klicks)', () => {
		const src = readCompareTabs();
		assert.match(
			src,
			/addPanelLoadStarted = true;\s*\n\s*try \{\s*\n\s*const \[locs, groups\] = await Promise\.all/,
			'addPanelLoadStarted muss synchron VOR dem async-Aufruf true werden — sonst kann ein zweiter ' +
				'Klick vor Abschluss des ersten Fetches erneut triggern (Race, S4-Analogie).'
		);
	});

	// Analog zum ursprünglichen S4/S5-Muster: kein onMount(async …)-Block im
	// Hub ruft toggleAddPanel() unbedingt auf (Fehlerklasse "unbedingter Fetch
	// bei jedem Mount" bleibt abgewehrt).
	test('KEIN onMount(async …)-Block ruft toggleAddPanel() unbedingt auf', () => {
		const src = readCompareTabs();
		const onMountAsyncBlocks = [...src.matchAll(/onMount\(async[\s\S]{0,20}?=>\s*\{([\s\S]*?)\n\t\}\);/g)];
		const offenders = onMountAsyncBlocks.filter((m) => /toggleAddPanel\(\)/.test(m[1]));
		assert.equal(
			offenders.length,
			0,
			'toggleAddPanel() darf nicht aus einem unbedingten onMount(async …)-Block heraus aufgerufen werden — ' +
				'das war exakt die Scheibe-4-F001-Root-Cause (unbedingter Fetch bei JEDEM Mount statt ' +
				'gegated auf die tatsächliche Nutzung).'
		);
	});
});
