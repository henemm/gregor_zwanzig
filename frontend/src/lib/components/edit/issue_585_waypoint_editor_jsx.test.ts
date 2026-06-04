// TDD RED — Issue #585: Waypoint-Editor Design-Fidelity 1:1 nach screen-waypoint-editor.jsx
//
// Spec: docs/specs/modules/issue_585_waypoint_editor_design.md
//
// Source-Inspection-Tests: prüfen, dass NEUE Muster vorhanden und
// ALTE Muster entfernt sind. VOR der Implementierung SCHEITERN sie (RED).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/edit/issue_585_waypoint_editor_jsx.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const WAYPOINTS_DIR = join(HERE, '..', 'trip-detail', 'waypoints');
const TYPES_FILE = join(HERE, '..', '..', '..', 'lib', 'types.ts');

function read(file: string): string {
	return readFileSync(file, 'utf-8');
}

const ETAPPEN_STRIP = join(WAYPOINTS_DIR, 'EtappenStrip.svelte');
const STAGE_CARD    = join(WAYPOINTS_DIR, 'StageCard.svelte');
const WAYPOINT_CARD = join(WAYPOINTS_DIR, 'WaypointCard.svelte');
const EDIT_PANEL    = join(HERE, 'EditStagesPanelNew.svelte');

// ── AC-1: EtappenStrip — Eyebrow-Header + GPX/Pause-Zähler ──────────────────

describe('AC-1: EtappenStrip — Eyebrow-Header + Zähler', () => {
	test('AC-1a: EtappenStrip enthält den Eyebrow-Text "DRAG ZUM SORTIEREN"', () => {
		const src = read(ETAPPEN_STRIP);
		assert.ok(
			src.includes('DRAG ZUM SORTIEREN') || src.includes('Drag zum Sortieren'),
			'EtappenStrip.svelte muss den Eyebrow-Text "DRAG ZUM SORTIEREN" enthalten (JSX: "ETAPPEN · DRAG ZUM SORTIEREN · + PAUSE ZWISCHEN")'
		);
	});

	test('AC-1b: EtappenStrip enthält den "+ PAUSE ZWISCHEN"-Hinweis im Header', () => {
		const src = read(ETAPPEN_STRIP);
		assert.ok(
			src.includes('PAUSE ZWISCHEN') || src.includes('Pause zwischen'),
			'EtappenStrip.svelte muss "+ PAUSE ZWISCHEN" im Strip-Header zeigen'
		);
	});

	test('AC-1c: EtappenStrip zeigt GPX- und Pause-Zähler nebeneinander', () => {
		const src = read(ETAPPEN_STRIP);
		assert.ok(
			src.includes('GPX') && (src.includes('Pause') || src.includes('pause')),
			'EtappenStrip.svelte muss "N GPX · N Pause"-Zähler im Header rechts anzeigen'
		);
	});
});

// ── AC-2: EtappenStrip — PauseInsertGap zwischen Karten ──────────────────────

describe('AC-2: EtappenStrip — PauseInsertGap', () => {
	test('AC-2a: PauseInsertGap-Pattern zwischen Etappenkarten vorhanden', () => {
		const src = read(ETAPPEN_STRIP);
		// Erwartet: Hover-Logic die Breite zwischen Karten von 8px auf 56px expandiert
		assert.ok(
			src.includes('56') && (src.includes('hoverGap') || src.includes('hover')),
			'EtappenStrip.svelte muss PauseInsertGap-Element mit Hover-Expand (56px) zwischen Etappenkarten haben'
		);
	});

	test('AC-2b: PauseInsertGap zeigt "+ Pause"-Badge bei Hover', () => {
		const src = read(ETAPPEN_STRIP);
		assert.ok(
			src.includes('+ Pause') || src.includes('+Pause'),
			'EtappenStrip.svelte muss "+ Pause"-Badge im PauseInsertGap-Element zeigen'
		);
	});
});

// ── AC-3: EtappenStrip — "+ Etappe"-Button am Ende ───────────────────────────

describe('AC-3: EtappenStrip — "+ Etappe"-Button', () => {
	test('AC-3a: "+ Etappe"-Button am Strip-Ende vorhanden', () => {
		const src = read(ETAPPEN_STRIP);
		assert.ok(
			src.includes('+ Etappe'),
			'EtappenStrip.svelte muss "+ Etappe"-Button am rechten Ende des Strips haben'
		);
	});

	test('AC-3b: "+ Etappe"-Button hat dashed border-style', () => {
		const src = read(ETAPPEN_STRIP);
		assert.ok(
			src.includes('dashed'),
			'EtappenStrip.svelte "+ Etappe"-Button muss border-style: dashed haben'
		);
	});
});

// ── AC-4: StageCard — ⋮⋮-Drag-Handle + CODE-Label + ×-Button ────────────────

describe('AC-4: StageCard — Drag-Handle + CODE + ×-Button', () => {
	test('AC-4a: StageCard zeigt ⋮⋮-Drag-Handle', () => {
		const src = read(STAGE_CARD);
		assert.ok(
			src.includes('⋮⋮'),
			'StageCard.svelte muss ⋮⋮-Drag-Handle-Zeichen oben links anzeigen'
		);
	});

	test('AC-4b: StageCard zeigt stage.code neben der Nummer', () => {
		const src = read(STAGE_CARD);
		assert.ok(
			src.includes('stage.code') || src.includes('{stage.code}'),
			'StageCard.svelte muss stage.code (Etappen-Code) neben der Etappennummer anzeigen'
		);
	});

	test('AC-4c: StageCard hat ×-Entfernen-Button', () => {
		const src = read(STAGE_CARD);
		assert.ok(
			src.includes('×') || src.includes('onRemove') || src.includes('remove'),
			'StageCard.svelte muss einen ×-Entfernen-Button haben (onRemove-Prop oder "×"-Zeichen)'
		);
	});

	test('AC-4d: StageCard hat Breite 200px', () => {
		const src = read(STAGE_CARD);
		assert.ok(
			src.includes('200px') || src.includes('width: 200'),
			'StageCard.svelte muss Breite 200px haben (statt aktuell 160px)'
		);
	});
});

// ── AC-5: StageCard — border statt outline für aktiven Zustand ───────────────

describe('AC-5: StageCard — border (nicht outline) für aktiven Zustand', () => {
	test('AC-5a: Aktiver Zustand nutzt border: 2px solid var(--g-accent)', () => {
		const src = read(STAGE_CARD);
		// Nach Migration: border: 2px solid für active, nicht CSS outline
		assert.ok(
			src.includes('2px solid') && !src.includes('outline: 2px solid'),
			'StageCard.svelte aktiver Zustand muss border: 2px solid var(--g-accent) nutzen, kein CSS outline'
		);
	});
});

// ── AC-6: StageCard — inline SVG-Polyline statt ElevSparkline-Atom ───────────

describe('AC-6: StageCard — inline SVG statt ElevSparkline-Atom', () => {
	test('AC-6a: ElevSparkline-Atom ist nicht mehr importiert', () => {
		const src = read(STAGE_CARD);
		assert.ok(
			!src.includes('ElevSparkline'),
			'StageCard.svelte darf ElevSparkline nicht mehr importieren — stattdessen inline SVG-Polyline'
		);
	});

	test('AC-6b: Inline SVG mit <polyline> für Höhenprofil vorhanden', () => {
		const src = read(STAGE_CARD);
		assert.ok(
			src.includes('<polyline') || src.includes('polyline'),
			'StageCard.svelte muss eine inline <svg><polyline></svg> für das Höhenprofil haben'
		);
	});

	test('AC-6c: SVG-Höhe ist 18px', () => {
		const src = read(STAGE_CARD);
		assert.ok(
			src.includes('18') && src.includes('height'),
			'StageCard.svelte MiniSpark-SVG muss height=18 haben'
		);
	});
});

// ── AC-7: StageCard — Pausentag-Design ───────────────────────────────────────

describe('AC-7: StageCard — Pausentag-Design', () => {
	test('AC-7a: Pausentag-Karte zeigt "⌂ Pause"-Zeile', () => {
		const src = read(STAGE_CARD);
		assert.ok(
			src.includes('⌂') || src.includes('Pause ·'),
			'StageCard.svelte muss für Pause-Stages eine "⌂ Pause · Standort"-Zeile anzeigen'
		);
	});

	test('AC-7b: Pausentag-Karte hat card-alt-Hintergrund', () => {
		const src = read(STAGE_CARD);
		assert.ok(
			src.includes('g-card-alt') || src.includes('card-alt'),
			'StageCard.svelte Pause-Stage muss var(--g-card-alt) als Hintergrund haben'
		);
	});
});

// ── AC-8: EditStagesPanelNew — Wetterscheiden-Text + Etappe-CODE-Eyebrow ─────

describe('AC-8: EditStagesPanelNew — Header mit Wetterscheiden-Text', () => {
	test('AC-8a: Erklärungstext "Wetterscheiden" ist im Stage-Header vorhanden', () => {
		const src = read(EDIT_PANEL);
		assert.ok(
			src.includes('Wetterscheiden'),
			'EditStagesPanelNew.svelte muss den Erklärungstext "Wegpunkte sind Wetterscheiden..." im Stage-Header anzeigen'
		);
	});

	test('AC-8b: Eyebrow zeigt "ETAPPE ·" mit stage.code', () => {
		const src = read(EDIT_PANEL);
		assert.ok(
			(src.includes('Etappe') || src.includes('ETAPPE')) && (src.includes('stage.code') || src.includes('.code')),
			'EditStagesPanelNew.svelte muss Eyebrow "ETAPPE · {stage.code}" im Stage-Header zeigen'
		);
	});

	test('AC-8c: Stage-Name wird in 32px / font-weight 600 gerendert', () => {
		const src = read(EDIT_PANEL);
		assert.ok(
			src.includes('32px') || src.includes('text-3xl') || src.includes('font-size: 32'),
			'EditStagesPanelNew.svelte muss Stage-Name in 32px Schriftgröße anzeigen'
		);
	});
});

// ── AC-9: EditStagesPanelNew — Padding 20/40/60 + maxWidth 1480 ──────────────

describe('AC-9: EditStagesPanelNew — Inhaltsbereich Padding + maxWidth', () => {
	test('AC-9a: padding "20px 40px 60px" im Inhaltsbereich', () => {
		const src = read(EDIT_PANEL);
		assert.ok(
			src.includes('20px 40px 60px') || (src.includes('20px') && src.includes('60px') && src.includes('40px')),
			'EditStagesPanelNew.svelte muss padding: 20px 40px 60px im Stage-Inhaltsbereich haben'
		);
	});

	test('AC-9b: maxWidth 1480px im Inhaltsbereich', () => {
		const src = read(EDIT_PANEL);
		assert.ok(
			src.includes('1480') || src.includes('max-width: 1480'),
			'EditStagesPanelNew.svelte muss maxWidth: 1480px im Stage-Inhaltsbereich haben'
		);
	});
});

// ── AC-10: WaypointCard — Typ-Label (Gipfel/Pass/Hütte/…) ───────────────────

describe('AC-10: WaypointCard — Typ-Label in Meta-Zeile', () => {
	test('AC-10a: Typ-Label-Mapping vorhanden (Gipfel/Pass/Hütte)', () => {
		const src = read(WAYPOINT_CARD);
		assert.ok(
			src.includes('Gipfel') && src.includes('Pass') && src.includes('Hütte'),
			'WaypointCard.svelte muss Typ-Label-Mapping enthalten: Gipfel, Pass, Hütte (aus waypoint.type)'
		);
	});

	test('AC-10b: waypoint.type wird ausgewertet', () => {
		const src = read(WAYPOINT_CARD);
		assert.ok(
			src.includes('waypoint.type') || src.includes('wp.type'),
			'WaypointCard.svelte muss waypoint.type auslesen um das Typ-Label zu rendern'
		);
	});

	test('AC-10c: Typ-Label erscheint in der Meta-Zeile (vor Höhe und Uhrzeit)', () => {
		const src = read(WAYPOINT_CARD);
		// Typ-Label muss im selben Block wie elevation_m und arrival sein
		assert.ok(
			src.includes('typeLabel') || src.includes('type_label') || (src.includes('Gipfel') && src.includes('elevation_m')),
			'WaypointCard.svelte muss Typ-Label in der Meta-Zeile neben elevation_m und Ankunftszeit zeigen'
		);
	});
});

// ── AC-10 Zusatz: types.ts — Waypoint.type Feld ─────────────────────────────

describe('AC-10 Zusatz: types.ts — Waypoint.type', () => {
	test('Waypoint-Interface hat optionales type-Feld', () => {
		const src = read(TYPES_FILE);
		assert.ok(
			src.includes('type?:') || src.includes("type?: 'start'") || (src.includes('Waypoint') && src.includes("type?")),
			'types.ts Waypoint-Interface muss optionales type?-Feld haben (string | undefined)'
		);
	});
});
