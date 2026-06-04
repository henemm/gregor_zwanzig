// Issue #503 — Wegpunkt-Editor im Tab „Etappen & Wegpunkte" (Option B).
//
// Quelle: docs/design-requests/issue-503/RESPONSE-FROM-CLAUDE-DESIGN
// Referenz-Mockups: /tmp/design-komp/gregor-zwanzig/project/screen-trip-edit-tabs.jsx,
//                   screen-waypoint-editor.jsx
//
// Source-Inspection-Tests (kein DOM-Rendering, keine Mocks, kein Playwright).
// Methodik: node:test + readFileSync — prüft Datei-Invarianten.
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/edit/issue_503_etappen_waypoints.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));

// Pfade
const TRIP_EDIT_VIEW = join(here, 'TripEditView.svelte');
const EDIT_STAGES_PANEL = join(here, 'EditStagesPanelNew.svelte');
const WAYPOINT_EDITOR_PAGE = join(here, 'WaypointEditorPage.svelte');
const AI_SUGGESTION_BAR = join(here, 'AISuggestionBar.svelte');
const STAGE_NAV_DROPDOWN = join(here, 'StageNavDropdown.svelte');

// Issue #522 — Wegpunkt-Karte Visual-Redesign
const WAYPOINT_CARD = join(here, '..', 'trip-detail', 'waypoints', 'WaypointCard.svelte');
const WAYPOINT_PIN = join(here, '..', 'trip-detail', 'waypoints', 'WaypointPin.svelte');

// ────────────────────────────────────────────────────────────────────────────
// Tab-Umbenennung (TripEditView)
// ────────────────────────────────────────────────────────────────────────────

describe('#503 Tab-Umbenennung', () => {
	test('TripEditView Tab-Label heißt „Etappen & Wegpunkte"', () => {
		const src = readFileSync(TRIP_EDIT_VIEW, 'utf-8');
		assert.ok(
			src.includes('Etappen & Wegpunkte'),
			'TripEditView.svelte muss den Tab-Label "Etappen & Wegpunkte" enthalten'
		);
	});

	test('TripEditView Tab heißt nicht mehr nur „Etappen <N>"', () => {
		const src = readFileSync(TRIP_EDIT_VIEW, 'utf-8');
		// Der reine "Etappen ${stats.stages}"-Label ist Vergangenheit.
		assert.ok(
			!/label:\s*`Etappen\s+\$\{stats\.stages\}`/.test(src),
			'TripEditView.svelte darf nicht mehr `Etappen ${stats.stages}` als Label haben'
		);
	});

	test('TripEditView bindet den Editor-Tab an EtappenStrip (Issue #581 AC-7)', () => {
		const src = readFileSync(TRIP_EDIT_VIEW, 'utf-8');
		assert.ok(
			src.includes('EtappenStrip'),
			'TripEditView.svelte muss EtappenStrip als Tab-Inhalt rendern (EditStagesPanelNew durch #581 abgelöst)'
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// EditStagesPanelNew: Karte + Grid + keine KI/Suggested-Branches
// ────────────────────────────────────────────────────────────────────────────

describe('#503 EditStagesPanelNew Layout', () => {
	test('importiert MapCanvas', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		assert.ok(
			/import\s+MapCanvas\s+from\s+['"][^'"]*MapCanvas\.svelte['"]/.test(src),
			'EditStagesPanelNew.svelte muss MapCanvas importieren'
		);
	});

	test('rendert MapCanvas-Element', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		assert.ok(
			/<MapCanvas[\s>]/.test(src),
			'EditStagesPanelNew.svelte muss <MapCanvas .../> im Markup rendern'
		);
	});

	test('Grid-Layout mit grid-template-columns: 1fr 360px', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		// Whitespace-tolerant: erlaubt Mehrfach-Leerzeichen
		const hasGrid = /grid-template-columns:\s*1fr\s+360px/.test(src);
		assert.ok(
			hasGrid,
			'EditStagesPanelNew.svelte muss grid-template-columns: 1fr 360px haben'
		);
	});

	test('Karten-Card hat Eyebrow "Karte · OpenTopoMap (OSM + SRTM)"', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		assert.ok(
			src.includes('Karte · OpenTopoMap (OSM + SRTM)'),
			'EditStagesPanelNew.svelte muss den Eyebrow-Text "Karte · OpenTopoMap (OSM + SRTM)" enthalten'
		);
	});

	test('Karten-Card hat Pill "Topo"', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		// Pill als Atom mit Kind-Text "Topo" — toleriere beliebiges Pill-Markup
		const hasTopoPill = />\s*Topo\s*</.test(src);
		assert.ok(
			hasTopoPill,
			'EditStagesPanelNew.svelte muss eine Pill mit dem Text "Topo" enthalten'
		);
	});

	test('Profil-Card hat Eyebrow "Höhenprofil · synchron mit Karte"', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		assert.ok(
			src.includes('Höhenprofil · synchron mit Karte'),
			'EditStagesPanelNew.svelte muss den Eyebrow-Text "Höhenprofil · synchron mit Karte" enthalten'
		);
	});

	test('Sidebar-Card hat Eyebrow "Wegpunkte"', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		// "Wegpunkte" als sichtbarer Eyebrow-Kind-Text
		assert.ok(
			/<Eyebrow>\s*Wegpunkte\s*<\/Eyebrow>/.test(src),
			'EditStagesPanelNew.svelte muss eine Sidebar-Card mit <Eyebrow>Wegpunkte</Eyebrow> haben'
		);
	});

	test('Sidebar hat „+ auf Route"-Button', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		assert.ok(
			src.includes('+ auf Route'),
			'EditStagesPanelNew.svelte muss einen Button mit Text "+ auf Route" haben'
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// KI/Auto/Manuell-Unterscheidung entfernt
// ────────────────────────────────────────────────────────────────────────────

describe('#503 Keine KI/Auto/Manuell-Unterscheidung', () => {
	test('EditStagesPanelNew setzt KEIN waypoint.suggested mehr beim Profil-Add', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		// Konkrete Anti-Pattern: neuer Waypoint mit suggested: true.
		assert.ok(
			!/suggested:\s*true/.test(src),
			'EditStagesPanelNew.svelte darf "suggested: true" beim Neuanlegen nicht mehr setzen'
		);
	});

	test('EditStagesPanelNew enthält keinen KI-Hinweis-Footer', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		// KI-Vorschläge & "gestrichelt" gehören in den alten Hinweis-Footer.
		assert.ok(
			!src.includes('KI-Vorschläge'),
			'EditStagesPanelNew.svelte darf keinen "KI-Vorschläge"-Hinweis-Footer mehr haben'
		);
		assert.ok(
			!src.includes('gestrichelt'),
			'EditStagesPanelNew.svelte darf keinen "gestrichelt"-Hinweis-Footer mehr haben'
		);
	});

	test('EditStagesPanelNew rendert keine Confirm-/Reject-Buttons', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		// "Bestätigen"/"Verwerfen" oder waypoint-confirm-/-reject-testids
		assert.ok(
			!src.includes('Bestätigen'),
			'EditStagesPanelNew.svelte darf keinen "Bestätigen"-Button mehr enthalten'
		);
		assert.ok(
			!src.includes('Verwerfen'),
			'EditStagesPanelNew.svelte darf keinen "Verwerfen"-Button mehr enthalten'
		);
	});

	test('EditStagesPanelNew nutzt KEIN bedingtes Rendering auf waypoint.suggested', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		// Whitespace-toleranter Match.
		const hasSuggestedBranch =
			/\{#if\s+[^}]*\.suggested\b/.test(src) ||
			/\bwaypoint\.suggested\b/.test(src);
		assert.ok(
			!hasSuggestedBranch,
			'EditStagesPanelNew.svelte darf kein bedingtes Rendering auf waypoint.suggested haben'
		);
	});

	test('ProfileEditor.svelte enthält keine isSuggested-Conditional mehr', () => {
		const src = readFileSync(
			new URL('../trip-detail/waypoints/ProfileEditor.svelte', import.meta.url).pathname,
			'utf-8'
		);
		assert.ok(!src.includes('isSuggested'), 'ProfileEditor darf kein isSuggested enthalten');
		assert.ok(!src.includes('suggested === true'), 'ProfileEditor darf kein suggested===true enthalten');
	});
});

// ────────────────────────────────────────────────────────────────────────────
// WaypointEditorPage existiert nicht mehr (toter Code)
// ────────────────────────────────────────────────────────────────────────────

describe('#503 Toter Code entfernt', () => {
	test('WaypointEditorPage.svelte existiert nicht mehr', () => {
		assert.ok(
			!existsSync(WAYPOINT_EDITOR_PAGE),
			'WaypointEditorPage.svelte muss gelöscht sein (Inhalt ist in EditStagesPanelNew gewandert)'
		);
	});

	test('AISuggestionBar.svelte existiert nicht mehr', () => {
		// Tot, da KI-Bestätigen-Workflow vollständig entfernt wurde.
		assert.ok(
			!existsSync(AI_SUGGESTION_BAR),
			'AISuggestionBar.svelte muss gelöscht sein (KI-Workflow entfernt)'
		);
	});

	test('StageNavDropdown.svelte existiert nicht mehr', () => {
		// Tot, da der Mobile-Editor-Screen entfällt — Tab-Host übernimmt Navigation.
		assert.ok(
			!existsSync(STAGE_NAV_DROPDOWN),
			'StageNavDropdown.svelte muss gelöscht sein (mobile-Editor entfällt)'
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// #522 — WaypointCard Visual-Redesign
// ────────────────────────────────────────────────────────────────────────────

describe('#522 WaypointCard Visual-Redesign', () => {
	test('importiert WaypointPin NICHT mehr', () => {
		const src = readFileSync(WAYPOINT_CARD, 'utf-8');
		assert.ok(
			!/import\s+WaypointPin\s+from/.test(src),
			'WaypointCard.svelte darf WaypointPin NICHT mehr importieren (Kreis-Pin als inline span)'
		);
	});

	test('rendert Kreis-Pin als CSS-Klasse waypoint-pin (kein SVG-Pfad mit stroke-dasharray)', () => {
		const src = readFileSync(WAYPOINT_CARD, 'utf-8');
		assert.ok(
			/class="[^"]*waypoint-pin\b/.test(src),
			'WaypointCard.svelte muss den Kreis-Pin via CSS-Klasse "waypoint-pin" rendern'
		);
		assert.ok(
			!src.includes('stroke-dasharray'),
			'WaypointCard.svelte darf kein stroke-dasharray (gestrichelt) mehr enthalten'
		);
	});

	test('hat Text-Buttons "Umbenennen", "Verschieben", "Löschen" (keine Icons mehr)', () => {
		const src = readFileSync(WAYPOINT_CARD, 'utf-8');
		assert.ok(src.includes('Umbenennen'), 'WaypointCard.svelte muss Text "Umbenennen" enthalten');
		assert.ok(src.includes('Verschieben'), 'WaypointCard.svelte muss Text "Verschieben" enthalten');
		assert.ok(src.includes('Löschen'), 'WaypointCard.svelte muss Text "Löschen" enthalten');
	});

	test('Action-Buttons sind nur bei active sichtbar ({#if active})', () => {
		const src = readFileSync(WAYPOINT_CARD, 'utf-8');
		// Action-Block (mit "Umbenennen") muss in einem {#if active}-Block stehen
		const hasActiveGate = /\{#if\s+active\s*\}[\s\S]*Umbenennen[\s\S]*\{\/if\}/.test(src);
		assert.ok(
			hasActiveGate,
			'WaypointCard.svelte muss die Action-Buttons in einem {#if active}-Block kapseln'
		);
	});

	test('hat data-testid="waypoint-move-{index}" für Verschieben-Button', () => {
		const src = readFileSync(WAYPOINT_CARD, 'utf-8');
		assert.ok(
			/data-testid=["']waypoint-move-\{index\}["']/.test(src),
			'WaypointCard.svelte muss data-testid="waypoint-move-{index}" haben'
		);
	});

	test('behält bestehende data-testids waypoint-card/rename/delete', () => {
		const src = readFileSync(WAYPOINT_CARD, 'utf-8');
		assert.ok(
			/data-testid=["']waypoint-card-\{index\}["']/.test(src),
			'data-testid="waypoint-card-{index}" muss erhalten bleiben'
		);
		assert.ok(
			/data-testid=["']waypoint-rename-\{index\}["']/.test(src),
			'data-testid="waypoint-rename-{index}" muss erhalten bleiben'
		);
		assert.ok(
			/data-testid=["']waypoint-delete-\{index\}["']/.test(src),
			'data-testid="waypoint-delete-{index}" muss erhalten bleiben'
		);
	});

	test('Left-Border-Accent-Indikator: border-left mit var(--g-accent) im aktiven Zustand', () => {
		const src = readFileSync(WAYPOINT_CARD, 'utf-8');
		// CSS muss eine border-left-Regel haben, die im active-State auf --g-accent geht.
		const hasBorderLeft = /border-left[^;]*var\(--g-accent\)/.test(src) ||
			/border-left-color:\s*var\(--g-accent\)/.test(src);
		assert.ok(
			hasBorderLeft,
			'WaypointCard.svelte muss einen Left-Border-Indikator mit var(--g-accent) haben'
		);
	});
});

describe('#522 WaypointPin Cleanup (suggested-Branch raus)', () => {
	test('hat kein suggested Prop mehr', () => {
		const src = readFileSync(WAYPOINT_PIN, 'utf-8');
		assert.ok(
			!/suggested\??:\s*boolean/.test(src),
			'WaypointPin.svelte darf kein "suggested?: boolean" Prop mehr deklarieren'
		);
	});

	test('hat keinen stroke-dasharray-Branch mehr', () => {
		const src = readFileSync(WAYPOINT_PIN, 'utf-8');
		assert.ok(
			!src.includes('stroke-dasharray'),
			'WaypointPin.svelte darf kein stroke-dasharray (gestrichelter suggested-Pin) mehr enthalten'
		);
	});

	test('hat keinen {#if suggested}-Branch mehr', () => {
		const src = readFileSync(WAYPOINT_PIN, 'utf-8');
		assert.ok(
			!/\{#if\s+suggested\b/.test(src),
			'WaypointPin.svelte darf keinen {#if suggested}-Block mehr haben'
		);
	});

	test('aria-label hat keinen suggested-Zweig mehr', () => {
		const src = readFileSync(WAYPOINT_PIN, 'utf-8');
		assert.ok(
			!/Vorgeschlagener\s+Wegpunkt/.test(src),
			'WaypointPin.svelte darf kein "Vorgeschlagener Wegpunkt"-aria-label mehr enthalten'
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// #524 — WaypointSidebar „+ auf Route" Button entsperren
// ────────────────────────────────────────────────────────────────────────────

describe('#524 waypoint-add-on-route-btn entsperren', () => {
	test('AC-1: Button hat KEIN disabled-Attribut', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		const hasDisabled =
			/<Btn[^>]*data-testid=["']waypoint-add-on-route-btn["'][^>]*\bdisabled\b/.test(src) ||
			/\bdisabled\b[^>]*data-testid=["']waypoint-add-on-route-btn["']/.test(src);
		assert.ok(
			!hasDisabled,
			'waypoint-add-on-route-btn darf kein disabled-Attribut haben (Bug #524)'
		);
	});

	test('AC-1: Button setzt addModeHint = true beim Klick', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		assert.ok(
			src.includes('addModeHint = true'),
			'EditStagesPanelNew.svelte muss onclick mit addModeHint = true am waypoint-add-on-route-btn haben'
		);
	});

	test('AC-2: addModeHint als $state(false) deklariert', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		assert.ok(
			/addModeHint\s*=\s*\$state\(false\)/.test(src),
			'EditStagesPanelNew.svelte muss addModeHint = $state(false) enthalten'
		);
	});

	test('AC-2: Info-Strip-Text "Klicke im Höhenprofil" vorhanden', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		assert.ok(
			src.includes('Klicke im Höhenprofil'),
			'EditStagesPanelNew.svelte muss den Info-Strip-Text "Klicke im Höhenprofil" enthalten'
		);
	});

	test('AC-3: data-testid="waypoint-add-on-route-btn" bleibt erhalten', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		assert.ok(
			src.includes('data-testid="waypoint-add-on-route-btn"'),
			'waypoint-add-on-route-btn muss seine data-testid behalten'
		);
	});

	test('AC-4: handleProfileAdd setzt addModeHint = false', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		assert.ok(
			src.includes('addModeHint = false'),
			'handleProfileAdd muss addModeHint = false setzen wenn Wegpunkt eingefügt wurde'
		);
	});
});
