// TDD RED — Issue #503: Wegpunkt-Editor vollständiger Fix (Navigation + Design)
//
// Spec: docs/specs/modules/issue_503_wegpunkt_editor_fix.md
//
// Source-Inspection-Tests (kein DOM-Rendering, keine Mocks, kein Playwright).
// Methodik: node:test + readFileSync — prüft Datei-Invarianten gegen das
// Claude-Design-Spec (`screen-waypoint-editor.jsx`, `screen-waypoint-editor-mobile.jsx`).
//
// RED-Erwartung (vor Implementation):
//   - TripOverview.svelte: actionHref="#stages" statt "/trips/{id}/edit" → FAIL
//   - TripTabs.svelte: rendert noch WaypointsPanel im #stages-Tab → FAIL
//   - WaypointEditorPage.svelte: keine Breadcrumb-Header, kein Eyebrow auf Cards → FAIL
//   - MapCanvas.svelte: width:400px;height:300px → FAIL
//   - EtappenStrip.svelte: kein semi-transparenter Hintergrund → FAIL
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/waypoints/issue_503_wp_editor_fix.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));

// Pfade zu den betroffenen Dateien (siehe Spec → Betroffene Dateien)
//   here = .../trip-detail/waypoints/
const TRIP_OVERVIEW = join(here, '..', 'TripOverview.svelte');
const TRIP_TABS     = join(here, '..', 'TripTabs.svelte');
const MAP_CANVAS    = join(here, 'MapCanvas.svelte');
const ETAPPEN_STRIP = join(here, 'EtappenStrip.svelte');
const WP_EDITOR     = join(here, '..', '..', 'edit', 'WaypointEditorPage.svelte');

// ────────────────────────────────────────────────────────────────────────────
// Navigation-Fix (AC-1, AC-2)
// ────────────────────────────────────────────────────────────────────────────

describe('#503 Navigation-Fix', () => {
	test('#503 AC-1: TripOverview "Etappen öffnen" navigiert zu /trips/[id]/edit', () => {
		const src = readFileSync(TRIP_OVERVIEW, 'utf-8');
		// SOLL: actionHref baut auf /trips/{trip.id}/edit auf
		const hasEditLink =
			src.includes('/trips/${trip.id}/edit') ||
			src.includes('/trips/{trip.id}/edit') ||
			src.includes("`/trips/${trip.id}/edit`") ||
			/\/trips\/\$\{[a-zA-Z_.]+\}\/edit/.test(src);
		assert.ok(
			hasEditLink,
			'TripOverview.svelte muss in der Stages-Karte auf /trips/{trip.id}/edit verlinken (nicht #stages)'
		);
	});

	test('#503 AC-1: TripOverview Stages-Karte NICHT mehr #stages als actionHref', () => {
		const src = readFileSync(TRIP_OVERVIEW, 'utf-8');
		// Die Stages-Karte (testid="card-stages") darf nicht mehr actionHref="#stages" tragen.
		// Wir prüfen das paarweise: "card-stages" und actionHref="#stages" dürfen nicht
		// im selben DetailCard-Block stehen.
		const stagesCardMatch = src.match(/<DetailCard[\s\S]*?card-stages[\s\S]*?\/>/);
		assert.ok(stagesCardMatch, 'card-stages DetailCard-Block nicht gefunden');
		assert.ok(
			!stagesCardMatch![0].includes('actionHref="#stages"'),
			'Die Stages-Karte (card-stages) darf nicht mehr actionHref="#stages" tragen — sie muss auf /trips/{trip.id}/edit verweisen'
		);
	});

	test('#503 AC-2: TripTabs #stages-Tab rendert kein WaypointsPanel mehr', () => {
		const src = readFileSync(TRIP_TABS, 'utf-8');
		// SOLL: Im stages-Tab darf <WaypointsPanel ... nicht mehr stehen.
		// Wir suchen den stages-Branch im Markup.
		// Aktueller Code: {:else if tab.value === 'stages' && trip}
		//                   <WaypointsPanel {trip} />
		const stagesBranch = src.match(/tab\.value === 'stages'[\s\S]{0,400}/);
		assert.ok(stagesBranch, 'stages-Branch in TripTabs nicht gefunden');
		assert.ok(
			!stagesBranch![0].includes('<WaypointsPanel'),
			'TripTabs.svelte darf im stages-Tab kein WaypointsPanel mehr rendern (Spec AC-2)'
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// Desktop Design (AC-3 bis AC-8)
// ────────────────────────────────────────────────────────────────────────────

describe('#503 Desktop Design', () => {
	test('#503 AC-3: WaypointEditorPage hat Breadcrumb-Header mit "Wegpunkte"', () => {
		const src = readFileSync(WP_EDITOR, 'utf-8');
		// SOLL: Breadcrumb-Header zeigt "Tripname / Etappe-Code / Wegpunkte".
		// Wir prüfen das Vorkommen des Crumb-Texts "Wegpunkte" im Desktop-Layout
		// UND eine erkennbare Breadcrumb-Struktur (CSS-Klasse oder Datenelement).
		assert.ok(
			src.includes('Wegpunkte'),
			'WaypointEditorPage.svelte muss "Wegpunkte" als Breadcrumb-Teil enthalten'
		);
		const hasBreadcrumbStructure =
			src.includes('breadcrumb') ||
			src.includes('Breadcrumb') ||
			src.includes('wp-editor-breadcrumb') ||
			src.includes('wp-editor-header');
		assert.ok(
			hasBreadcrumbStructure,
			'WaypointEditorPage.svelte braucht eine Breadcrumb-Header-Struktur (CSS-Klasse breadcrumb/header)'
		);
	});

	test('#503 AC-4: WaypointEditorPage Karten-Card hat Eyebrow "Karte · OpenTopoMap (OSM + SRTM)"', () => {
		const src = readFileSync(WP_EDITOR, 'utf-8');
		assert.ok(
			src.includes('Karte · OpenTopoMap (OSM + SRTM)'),
			'WaypointEditorPage.svelte muss den Eyebrow-Text "Karte · OpenTopoMap (OSM + SRTM)" enthalten (AC-4)'
		);
	});

	test('#503 AC-4: WaypointEditorPage Karten-Card hat Pill "Topo"', () => {
		const src = readFileSync(WP_EDITOR, 'utf-8');
		// Pill-Label "Topo" — entweder als sichtbarer Text oder als Pill-Atom mit label
		const hasTopoPill =
			/>\s*Topo\s*</.test(src) ||
			/label\s*=\s*["']Topo["']/.test(src) ||
			/text\s*=\s*["']Topo["']/.test(src);
		assert.ok(
			hasTopoPill,
			'WaypointEditorPage.svelte muss eine Pill mit dem Text "Topo" enthalten (AC-4)'
		);
	});

	test('#503 AC-5: MapCanvas hat width:100% (nicht width:400px)', () => {
		const src = readFileSync(MAP_CANVAS, 'utf-8');
		assert.ok(
			!src.includes('width:400px'),
			'MapCanvas.svelte darf NICHT mehr width:400px im inline-style haben (AC-5)'
		);
		assert.ok(
			src.includes('width:100%'),
			'MapCanvas.svelte muss width:100% im inline-style haben (AC-5)'
		);
	});

	test('#503 AC-5: MapCanvas hat height:440px', () => {
		const src = readFileSync(MAP_CANVAS, 'utf-8');
		assert.ok(
			src.includes('height:440px'),
			'MapCanvas.svelte muss height:440px im inline-style haben (AC-5)'
		);
	});

	test('#503 AC-6: WaypointEditorPage Profil-Card hat Eyebrow "Höhenprofil · synchron mit Karte"', () => {
		const src = readFileSync(WP_EDITOR, 'utf-8');
		assert.ok(
			src.includes('Höhenprofil · synchron mit Karte'),
			'WaypointEditorPage.svelte muss den Eyebrow-Text "Höhenprofil · synchron mit Karte" enthalten (AC-6)'
		);
	});

	test('#503 AC-7: WaypointEditorPage Sidebar-Card hat Eyebrow "Wegpunkte"', () => {
		const src = readFileSync(WP_EDITOR, 'utf-8');
		// "Wegpunkte" ist Eyebrow der Sidebar-Card.
		// Wir prüfen das Vorkommen explizit in einer Eyebrow-Struktur (eyebrow="Wegpunkte"
		// oder eyebrow={"Wegpunkte"}) — nicht nur als Plain-Text.
		const hasSidebarEyebrow =
			/eyebrow\s*=\s*["']Wegpunkte["']/.test(src) ||
			/eyebrow\s*=\s*\{?\s*["'`]Wegpunkte["'`]\s*\}?/.test(src) ||
			src.includes('"sidebar-eyebrow"') ||
			src.includes("'sidebar-eyebrow'") ||
			src.includes('wp-editor-sidebar-eyebrow');
		assert.ok(
			hasSidebarEyebrow,
			'WaypointEditorPage.svelte muss eine Sidebar-Card mit Eyebrow "Wegpunkte" haben (AC-7)'
		);
	});

	test('#503 AC-7: Sidebar hat "+ auf Route"-Button', () => {
		const src = readFileSync(WP_EDITOR, 'utf-8');
		assert.ok(
			src.includes('+ auf Route'),
			'WaypointEditorPage.svelte muss einen Button mit Text "+ auf Route" haben (AC-7)'
		);
	});

	test('#503 AC-7: Sidebar hat Hinweis-Footer mit KI-Text ("KI-Vorschläge" und "gestrichelt")', () => {
		const src = readFileSync(WP_EDITOR, 'utf-8');
		assert.ok(
			src.includes('KI-Vorschläge'),
			'WaypointEditorPage.svelte muss im Hinweis-Footer "KI-Vorschläge" erwähnen (AC-7)'
		);
		assert.ok(
			src.includes('gestrichelt'),
			'WaypointEditorPage.svelte muss im Hinweis-Footer "gestrichelt" erwähnen (AC-7)'
		);
	});

	test('#503 AC-8: EtappenStrip hat semi-transparenten Hintergrund (rgba(255,255,255,...) + blur)', () => {
		const src = readFileSync(ETAPPEN_STRIP, 'utf-8');
		// Spec: background rgba(255,255,255,0.4) + backdrop-filter blur
		const hasRgbaWhite =
			src.includes('rgba(255,255,255') ||
			src.includes('rgba(255, 255, 255');
		const hasBlur = src.includes('backdrop-filter') || src.includes('blur(');
		assert.ok(
			hasRgbaWhite,
			'EtappenStrip.svelte muss einen semi-transparenten weißen Hintergrund haben (rgba(255,255,255,0.4)) (AC-8)'
		);
		assert.ok(
			hasBlur,
			'EtappenStrip.svelte muss backdrop-filter:blur enthalten (AC-8)'
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// Mobile Design (AC-9 bis AC-12)
// ────────────────────────────────────────────────────────────────────────────

describe('#503 Mobile Design', () => {
	test('#503 AC-9: Mobile TopAppBar hat eyebrow-Prop mit Trip-Infos', () => {
		const src = readFileSync(WP_EDITOR, 'utf-8');
		// SOLL: TopAppBar nutzt eine eyebrow-Prop (oder mobile-topbar-eyebrow-Klasse).
		// Aktuelle Implementierung: einfacher <header class="mobile-topbar"> ohne eyebrow.
		const hasEyebrowOnTopbar =
			/eyebrow\s*=/.test(src) ||
			src.includes('mobile-topbar-eyebrow') ||
			src.includes('mobile-eyebrow') ||
			src.includes('topbar-eyebrow');
		assert.ok(
			hasEyebrowOnTopbar,
			'WaypointEditorPage.svelte muss eine eyebrow-Prop/Klasse auf der mobilen TopAppBar haben (AC-9)'
		);
	});

	test('#503 AC-10: Mobile hat FAB-Buttons', () => {
		const src = readFileSync(WP_EDITOR, 'utf-8');
		// SOLL: 3 FAB-Buttons (Plus, Map, Search) im Mobile-Layout.
		const hasFab =
			src.includes('data-testid="wp-editor-fab"') ||
			src.includes("data-testid='wp-editor-fab'") ||
			src.includes('wp-editor-fab') ||
			/class\s*=\s*["'][^"']*\bfab\b/.test(src) ||
			src.includes('FAB');
		assert.ok(
			hasFab,
			'WaypointEditorPage.svelte muss FAB-Buttons im Mobile-Layout haben (AC-10)'
		);
	});

	test('#503 AC-10: Mobile hat Profil-Strip auf Karte', () => {
		const src = readFileSync(WP_EDITOR, 'utf-8');
		const hasProfileStrip =
			src.includes('profil-strip') ||
			src.includes('mobile-profile-strip') ||
			src.includes('profile-strip');
		assert.ok(
			hasProfileStrip,
			'WaypointEditorPage.svelte muss einen Profil-Strip auf der mobilen Karte haben (AC-10)'
		);
	});

	test('#503 AC-11: Mobile Bottom-Sheet hat 3 Snap-Positionen (peek/half/full)', () => {
		const src = readFileSync(WP_EDITOR, 'utf-8');
		assert.ok(
			src.includes('peek'),
			'WaypointEditorPage.svelte muss "peek" als Snap-Position des Bottom-Sheets enthalten (AC-11)'
		);
		assert.ok(
			src.includes('half'),
			'WaypointEditorPage.svelte muss "half" als Snap-Position des Bottom-Sheets enthalten (AC-11)'
		);
		assert.ok(
			src.includes('full'),
			'WaypointEditorPage.svelte muss "full" als Snap-Position des Bottom-Sheets enthalten (AC-11)'
		);
	});

	test('#503 AC-12: Mobile Bottom-Sheet hat KI-Aktions-Button "KI-Vorschlag übernehmen"', () => {
		const src = readFileSync(WP_EDITOR, 'utf-8');
		assert.ok(
			src.includes('KI-Vorschlag übernehmen'),
			'WaypointEditorPage.svelte muss einen Button mit Text "KI-Vorschlag übernehmen" im Mobile-Bottom-Sheet haben (AC-12)'
		);
	});
});
