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
const COMPARE_EDITOR_FILE = join(here, '..', 'CompareEditor.svelte');

function readStep2(): string {
	return readFileSync(STEP2_FILE, 'utf-8');
}

function readCompareEditor(): string {
	return readFileSync(COMPARE_EDITOR_FILE, 'utf-8');
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
// Mini-Fix-Loop 1 (Adversary AMBIGUOUS, F001 MEDIUM, reine Testabdeckungs-
// Lücke — Code war bereits korrekt): das ceGroups-Lazy-Gate
// (CompareEditor.svelte:397-403) wehrt exakt dieselbe Fehlerklasse ab wie
// Scheibe 4 (ltCatalogLoadStarted/ltLoadCatalog, s.
// compare_editor_layout_tab_wiring.test.ts:343-352 — "ein $effect gated
// ltLoadCatalog() auf activeTab === 'layout' … mit Start-Guard"), hatte aber
// bislang KEINEN eigenen Regressions-Test. Dieser Block schließt die Lücke
// 1:1 analog zum S4-Muster, diesmal für den Gruppen-Fetch (ceLoadGroups /
// activeTab === 'orte' / ceGroupsLoadStarted).
// =============================================================================

describe('Fix-Loop 1 (S5, Adversary F001 MEDIUM): Gruppen-Fetch ist an den Orte-Tab-Besuch gekoppelt, kein unbedingter Mount-Fetch', () => {
	test('GET /api/groups läuft aus einer eigenständigen async-Funktion (ceLoadGroups), nicht direkt in onMount', () => {
		const src = readCompareEditor();
		assert.match(
			src,
			/async function ceLoadGroups\(\)[^{]*\{[\s\S]{0,300}?\/api\/groups/,
			'Der Gruppen-Fetch muss in einer benannten async-Funktion (ceLoadGroups) stecken, die gezielt getriggert werden kann'
		);
	});

	test('ein $effect gated ceLoadGroups() auf activeTab === \'orte\' (einmalig, mit Start-Guard)', () => {
		const src = readCompareEditor();
		assert.match(
			src,
			/\$effect\(\(\) => \{[\s\S]{0,200}?activeTab === 'orte'[\s\S]{0,200}?ceLoadGroups\(\)/,
			'Es muss einen $effect geben, der ceLoadGroups() nur bei activeTab === \'orte\' aufruft'
		);
		assert.ok(
			/ceGroupsLoadStarted/.test(src),
			'Ein Start-Guard (ceGroupsLoadStarted) muss verhindern, dass der Fetch bei jedem erneuten Tab-Wechsel zurück auf "orte" wiederholt wird'
		);
	});

	test('Start-Guard wird SYNCHRON vor dem Fetch-Aufruf gesetzt (verhindert Doppel-Trigger bei schnellen Tab-Wechseln)', () => {
		const src = readCompareEditor();
		assert.match(
			src,
			/ceGroupsLoadStarted = true;\s*\n\s*void ceLoadGroups\(\)/,
			'ceGroupsLoadStarted muss synchron VOR dem async-Aufruf true werden — sonst kann ein zweiter ' +
				'$effect-Lauf vor Abschluss des ersten Fetches erneut triggern (Race, S4-Analogie).'
		);
	});

	// Monkeypatch-selbstprüfend (S4-Muster, hier auf ceLoadGroups zugeschnitten
	// statt eines pauschalen Datei-weiten "kein onMount(async)"-Verbots — ein
	// Editor mit mehreren unabhängigen Lazy-Fetches darf andere
	// onMount(async …)-Blöcke haben, nur eben nicht FÜR ceLoadGroups): kein
	// onMount(async …)-Block im Quelltext ruft ceLoadGroups() unbedingt auf.
	test('KEIN onMount(async …)-Block ruft ceLoadGroups() unbedingt auf (S4-F001-Fehlerklasse abgewehrt)', () => {
		const src = readCompareEditor();
		const onMountAsyncBlocks = [...src.matchAll(/onMount\(async[\s\S]{0,20}?=>\s*\{([\s\S]*?)\n\t\}\);/g)];
		const offenders = onMountAsyncBlocks.filter((m) => /ceLoadGroups\(\)/.test(m[1]));
		assert.equal(
			offenders.length,
			0,
			'ceLoadGroups() darf nicht aus einem unbedingten onMount(async …)-Block heraus aufgerufen werden — ' +
				'das war exakt die Scheibe-4-F001-Root-Cause (unbedingter Fetch bei JEDEM Editor-Mount statt ' +
				'gegated auf den tatsächlich besuchten Tab).'
		);
	});
});
