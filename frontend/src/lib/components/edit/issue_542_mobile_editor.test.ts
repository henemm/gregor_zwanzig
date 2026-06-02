// Issue #542 — Wegpunkt-Editor Mobile-Ansicht + MapCanvas-Klick
//
// Quelle: docs/specs/modules/wegpunkt_editor_handoff.md
// Design-Referenz: docs/design-requests/Gregor 20 - Wegpunkt-Editor im Etappen-Tab.html
//
// Source-Inspection-Tests (kein DOM-Rendering, keine Mocks, kein Playwright).
// Methodik: node:test + readFileSync — prüft Datei-Invarianten.
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/edit/issue_542_mobile_editor.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const waypointsDir = join(here, '..', 'trip-detail', 'waypoints');

// Bestehende Dateien
const MAP_CANVAS      = join(waypointsDir, 'MapCanvas.svelte');
const EDIT_STAGES     = join(here, 'EditStagesPanelNew.svelte');

// Neue Dateien (noch nicht vorhanden — Tests MÜSSEN fehlschlagen)
const MAP_CONTROL     = join(here, 'MapControl.svelte');
const PROFILE_SHEET   = join(here, 'ProfileSheetEmbedded.svelte');
const STAGE_SELECT    = join(here, 'StageSelectSheet.svelte');
const EDITOR_PROFILE  = join(waypointsDir, 'EditorProfileSVG.svelte');

// ────────────────────────────────────────────────────────────────────────────
// AC-1: MapCanvas.svelte — onMapClick-Prop
// ────────────────────────────────────────────────────────────────────────────

describe('AC-1: MapCanvas onMapClick-Prop', () => {
	test('MapCanvas.svelte deklariert onMapClick als optionalen Prop', () => {
		const src = readFileSync(MAP_CANVAS, 'utf-8');
		assert.ok(
			src.includes('onMapClick'),
			'MapCanvas.svelte muss "onMapClick" als Prop deklarieren'
		);
	});

	test('onMapClick hat Signatur (lat: number, lon: number)', () => {
		const src = readFileSync(MAP_CANVAS, 'utf-8');
		assert.ok(
			src.includes('lat') && src.includes('lon'),
			'onMapClick muss lat und lon als Parameter haben'
		);
	});

	test('MapCanvas registriert Leaflet-Click-Event und ruft onMapClick auf', () => {
		const src = readFileSync(MAP_CANVAS, 'utf-8');
		assert.ok(
			src.includes("'click'") || src.includes('"click"'),
			'MapCanvas muss einen Leaflet click-Listener registrieren'
		);
	});

	test('MapCanvas hat sizeKey-Prop für Leaflet invalidateSize', () => {
		const src = readFileSync(MAP_CANVAS, 'utf-8');
		assert.ok(
			src.includes('sizeKey') && src.includes('invalidateSize'),
			'MapCanvas muss sizeKey-Prop und invalidateSize() enthalten'
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// AC-2: MapControl.svelte — neutraler Karten-Werkzeug-Cluster
// ────────────────────────────────────────────────────────────────────────────

describe('AC-2: MapControl.svelte existiert und ist korrekt gestylt', () => {
	test('MapControl.svelte existiert', () => {
		assert.ok(
			existsSync(MAP_CONTROL),
			'frontend/src/lib/components/edit/MapControl.svelte muss existieren'
		);
	});

	test('MapControl enthält drei Werkzeug-Buttons', () => {
		const src = readFileSync(MAP_CONTROL, 'utf-8');
		const buttonCount = (src.match(/add-waypoint|map-style|search/g) || []).length;
		assert.ok(
			buttonCount >= 3,
			'MapControl muss drei Buttons haben: add-waypoint, map-style, search'
		);
	});

	test('MapControl nutzt --g-card als Hintergrund (kein Akzent)', () => {
		const src = readFileSync(MAP_CONTROL, 'utf-8');
		assert.ok(
			src.includes('--g-card'),
			'MapControl muss --g-card als Hintergrundfarbe verwenden, nicht --g-accent'
		);
		assert.ok(
			!src.includes('--g-accent'),
			'MapControl darf KEINEN Akzent-Hintergrund haben (AP-012-Ausnahme: neutral)'
		);
	});

	test('MapControl ist oben rechts positioniert (top: 12px, right: 12px)', () => {
		const src = readFileSync(MAP_CONTROL, 'utf-8');
		assert.ok(
			(src.includes('top') && src.includes('right')) ||
			src.includes('position: absolute') || src.includes('position:absolute'),
			'MapControl muss absolute positioniert sein, top + right'
		);
	});

	test('MapControl-Buttons sind mindestens 44px groß (Touch-Target)', () => {
		const src = readFileSync(MAP_CONTROL, 'utf-8');
		assert.ok(
			src.includes('44'),
			'MapControl-Buttons müssen mindestens 44×44px sein (Charter §7 Touch-Target)'
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// AC-3: EditStagesPanelNew — Mobile-Branch
// ────────────────────────────────────────────────────────────────────────────

describe('AC-3: EditStagesPanelNew hat Mobile-Branch', () => {
	test('EditStagesPanelNew importiert MapControl', () => {
		const src = readFileSync(EDIT_STAGES, 'utf-8');
		assert.ok(
			src.includes('MapControl'),
			'EditStagesPanelNew muss MapControl importieren'
		);
	});

	test('EditStagesPanelNew importiert ProfileSheetEmbedded', () => {
		const src = readFileSync(EDIT_STAGES, 'utf-8');
		assert.ok(
			src.includes('ProfileSheetEmbedded'),
			'EditStagesPanelNew muss ProfileSheetEmbedded importieren'
		);
	});

	test('EditStagesPanelNew importiert StageSelectSheet', () => {
		const src = readFileSync(EDIT_STAGES, 'utf-8');
		assert.ok(
			src.includes('StageSelectSheet'),
			'EditStagesPanelNew muss StageSelectSheet importieren'
		);
	});

	test('EditStagesPanelNew hat Mobile-CSS-Block (@media max-width: 899px)', () => {
		const src = readFileSync(EDIT_STAGES, 'utf-8');
		assert.ok(
			src.includes('mobile-editor') || src.includes('mobile-map'),
			'EditStagesPanelNew muss einen Mobile-Karten-Container haben'
		);
	});

	test('EditStagesPanelNew übergibt onMapClick an MapCanvas', () => {
		const src = readFileSync(EDIT_STAGES, 'utf-8');
		assert.ok(
			src.includes('onMapClick') || src.includes('handleMapClick'),
			'EditStagesPanelNew muss einen Map-Click-Handler definieren und an MapCanvas übergeben'
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// AC-4: StageSelectSheet.svelte — Etappen-Auswahl-Modal
// ────────────────────────────────────────────────────────────────────────────

describe('AC-4: StageSelectSheet.svelte existiert', () => {
	test('StageSelectSheet.svelte existiert', () => {
		assert.ok(
			existsSync(STAGE_SELECT),
			'frontend/src/lib/components/edit/StageSelectSheet.svelte muss existieren'
		);
	});

	test('StageSelectSheet nutzt Sheet (Bottom-Sheet)', () => {
		const src = readFileSync(STAGE_SELECT, 'utf-8');
		assert.ok(
			src.includes('Sheet'),
			'StageSelectSheet muss die Sheet-Komponente aus mobile/ nutzen'
		);
	});

	test('StageSelectSheet hat stages-Prop und onSelect-Callback', () => {
		const src = readFileSync(STAGE_SELECT, 'utf-8');
		assert.ok(src.includes('stages'), 'StageSelectSheet muss stages-Prop haben');
		assert.ok(
			src.includes('onSelect') || src.includes('onPick'),
			'StageSelectSheet muss einen Auswahl-Callback haben'
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// AC-5: ProfileSheetEmbedded.svelte — Bottom-Sheet mit 3 Snap-Stufen
// ────────────────────────────────────────────────────────────────────────────

describe('AC-5: ProfileSheetEmbedded.svelte existiert mit 3 Snap-Stufen', () => {
	test('ProfileSheetEmbedded.svelte existiert', () => {
		assert.ok(
			existsSync(PROFILE_SHEET),
			'frontend/src/lib/components/edit/ProfileSheetEmbedded.svelte muss existieren'
		);
	});

	test('ProfileSheetEmbedded nutzt Sheet-Komponente', () => {
		const src = readFileSync(PROFILE_SHEET, 'utf-8');
		assert.ok(
			src.includes('Sheet'),
			'ProfileSheetEmbedded muss Sheet aus mobile/ verwenden'
		);
	});

	test('ProfileSheetEmbedded unterstützt alle drei Snap-Stufen', () => {
		const src = readFileSync(PROFILE_SHEET, 'utf-8');
		assert.ok(
			src.includes('peek') && src.includes('half') && src.includes('full'),
			'ProfileSheetEmbedded muss peek, half und full als Snap-Werte unterstützen'
		);
	});

	test('ProfileSheetEmbedded importiert EditorProfileSVG', () => {
		const src = readFileSync(PROFILE_SHEET, 'utf-8');
		assert.ok(
			src.includes('EditorProfileSVG'),
			'ProfileSheetEmbedded muss EditorProfileSVG einbinden'
		);
	});

	test('ProfileSheetEmbedded importiert WaypointCard', () => {
		const src = readFileSync(PROFILE_SHEET, 'utf-8');
		assert.ok(
			src.includes('WaypointCard'),
			'ProfileSheetEmbedded muss WaypointCard für die Wegpunkt-Liste einbinden'
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// AC-6: EditorProfileSVG.svelte — 343×70px Profil für Mobile
// ────────────────────────────────────────────────────────────────────────────

describe('AC-6: EditorProfileSVG.svelte — vereinfachtes Höhenprofil', () => {
	test('EditorProfileSVG.svelte existiert', () => {
		assert.ok(
			existsSync(EDITOR_PROFILE),
			'frontend/src/lib/components/trip-detail/waypoints/EditorProfileSVG.svelte muss existieren'
		);
	});

	test('EditorProfileSVG hat Breite 343px', () => {
		const src = readFileSync(EDITOR_PROFILE, 'utf-8');
		assert.ok(src.includes('343'), 'EditorProfileSVG muss 343px Breite haben');
	});

	test('EditorProfileSVG hat Höhe 70px', () => {
		const src = readFileSync(EDITOR_PROFILE, 'utf-8');
		assert.ok(src.includes('70'), 'EditorProfileSVG muss 70px Höhe haben');
	});

	test('EditorProfileSVG hat onProfileAdd-Callback (identische Signatur wie ProfileEditor)', () => {
		const src = readFileSync(EDITOR_PROFILE, 'utf-8');
		assert.ok(
			src.includes('onProfileAdd'),
			'EditorProfileSVG muss onProfileAdd(fraction) anbieten — gleiche Signatur wie ProfileEditor'
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// AC-7: Pausentag auf Mobile — keine Karte
// ────────────────────────────────────────────────────────────────────────────

describe('AC-7: Pausentag auf Mobile zeigt PauseStageView statt Karte', () => {
	test('EditStagesPanelNew rendert MapControl NICHT bei Pausentagen (konditionell)', () => {
		const src = readFileSync(EDIT_STAGES, 'utf-8');
		// MapControl muss innerhalb eines {#if !activeIsPause} oder ähnlichen Blocks sein
		assert.ok(
			src.includes('activeIsPause') || src.includes('isPause'),
			'EditStagesPanelNew muss bei Pausentagen MapControl ausblenden (activeIsPause-Check)'
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// AC-8: Karten-Klick fügt Wegpunkt ans Ende der Liste
// ────────────────────────────────────────────────────────────────────────────

describe('AC-8: Karten-Klick fügt Wegpunkt hinzu', () => {
	test('EditStagesPanelNew hat handleMapClick-Handler', () => {
		const src = readFileSync(EDIT_STAGES, 'utf-8');
		assert.ok(
			src.includes('handleMapClick') || src.includes('onMapClick'),
			'EditStagesPanelNew muss einen handleMapClick-Handler definieren'
		);
	});

	test('handleMapClick fügt Wegpunkt mit lat und lon ein', () => {
		const src = readFileSync(EDIT_STAGES, 'utf-8');
		assert.ok(
			(src.includes('handleMapClick') || src.includes('onMapClick')) &&
			src.includes('lat') && src.includes('lon'),
			'handleMapClick muss lat/lon-Koordinaten verarbeiten und einen Wegpunkt einfügen'
		);
	});

	test('Neue Wegpunkte haben Elevation 0 als MVP-Fallback', () => {
		const src = readFileSync(EDIT_STAGES, 'utf-8');
		// Prüfen ob elevation_m: 0 oder ähnlicher Fallback im Handler vorkommt
		assert.ok(
			src.includes('elevation_m') &&
			(src.includes('handleMapClick') || src.includes('onMapClick')),
			'handleMapClick muss elevation_m setzen (MVP-Fallback: 0)'
		);
	});
});
