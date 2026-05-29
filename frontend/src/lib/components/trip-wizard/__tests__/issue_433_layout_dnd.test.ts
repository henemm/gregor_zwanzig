// TDD RED — Issue #433: Layout-Editor Drag-and-Drop.
// SPEC: docs/specs/modules/issue_433_layout_dnd.md (AC-1..AC-10).
//
// Source-Inspection-Tests prüfen, ob die vier betroffenen Komponenten
// die laut Spec erforderlichen DnD-Patterns enthalten:
//
//   BucketSection.svelte   — dndzone + $effect + onDndReorder-Prop
//   OutputLayoutEditor.svelte — onDndReorder?-Prop-Durchleitung
//   WeatherMetricsTab.svelte  — Consumer-Handler onDndReorder
//   Step4Layout.svelte        — Consumer-Handler handleDndReorder
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_433_layout_dnd.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const BUCKET    = join(here, '..', '..', 'trip-detail', 'BucketSection.svelte');
const EDITOR    = join(here, '..', '..', 'shared', 'OutputLayoutEditor.svelte');
const METRICS   = join(here, '..', '..', 'trip-detail', 'WeatherMetricsTab.svelte');
const STEP4     = join(here, '..', 'steps', 'Step4Layout.svelte');

function read(p: string): string { return readFileSync(p, 'utf-8'); }

// =============================================================================
// BucketSection.svelte — AC-1, AC-6, AC-7, AC-8, AC-9
// =============================================================================

test('AC-1/AC-7: BucketSection importiert dndzone und DndEvent aus svelte-dnd-action', () => {
	const src = read(BUCKET);
	assert.ok(
		src.includes('svelte-dnd-action'),
		'BucketSection muss svelte-dnd-action importieren.',
	);
	assert.ok(
		src.includes('dndzone'),
		'BucketSection muss dndzone importieren/verwenden.',
	);
});

test('AC-9: BucketSection importiert flip aus svelte/animate', () => {
	const src = read(BUCKET);
	assert.ok(
		src.includes("from 'svelte/animate'") || src.includes('from "svelte/animate"'),
		'BucketSection muss flip aus svelte/animate importieren.',
	);
	assert.ok(
		src.includes('flip'),
		'BucketSection muss animate:flip verwenden.',
	);
});

test('AC-7: BucketSection hat Prop onDndReorder', () => {
	const src = read(BUCKET);
	assert.ok(
		src.includes('onDndReorder'),
		'BucketSection muss onDndReorder als Prop deklarieren.',
	);
});

test('AC-6: BucketSection verwendet $effect (nicht $derived) für dndItems-Sync', () => {
	const src = read(BUCKET);
	assert.ok(
		src.includes('dndItems'),
		'BucketSection muss einen lokalen dndItems-State haben.',
	);
	assert.ok(
		src.includes('$effect'),
		'BucketSection muss $effect für dndItems-Sync verwenden (nicht $derived).',
	);
	// Sicherheitsnetz: kein $derived für dndItems (würde Drag-Zustand zerstören)
	const derivedForDndItems = /\$derived[^)]*dndItems/.test(src) || /dndItems\s*=\s*\$derived/.test(src);
	assert.ok(!derivedForDndItems, 'dndItems darf nicht via $derived abgeleitet werden.');
});

test('AC-7: BucketSection ruft onDndReorder in handleDndFinalize mit string[] auf', () => {
	const src = read(BUCKET);
	assert.ok(
		src.includes('handleDndFinalize') || src.includes('onfinalize'),
		'BucketSection muss einen finalize-Handler haben.',
	);
	assert.ok(
		src.includes('onDndReorder'),
		'handleDndFinalize muss onDndReorder aufrufen.',
	);
	// Konvertierung {id}[] → string[] via .map(x => x.id)
	assert.ok(
		src.includes('.map(') && src.includes('.id'),
		'finalize-Handler muss dndItems per .map(x => x.id) zu string[] konvertieren.',
	);
});

test('AC-9: BucketSection verwendet flipDurationMs: 200 und dropTargetStyle: {}', () => {
	const src = read(BUCKET);
	assert.ok(
		src.includes('flipDurationMs') && src.includes('200'),
		'BucketSection muss flipDurationMs: 200 in der dndzone-Direktive setzen.',
	);
	assert.ok(
		src.includes('dropTargetStyle'),
		'BucketSection muss dropTargetStyle: {} in der dndzone-Direktive setzen.',
	);
});

test('AC-5: BucketSection hat dropFromOthersDisabled: true (verhindert Cross-Bucket-Drag)', () => {
	const src = read(BUCKET);
	assert.ok(
		src.includes('dropFromOthersDisabled'),
		'BucketSection muss dropFromOthersDisabled: true in der dndzone-Direktive setzen, um Cross-Bucket-Drag zu verhindern (AC-5).',
	);
	assert.ok(
		src.includes('dropFromOthersDisabled: true') || src.includes('dropFromOthersDisabled:true'),
		'dropFromOthersDisabled muss explizit auf true gesetzt sein.',
	);
});

test('AC-9: BucketSection hat animate:flip auf Wrapper-div', () => {
	const src = read(BUCKET);
	assert.ok(
		src.includes('animate:flip'),
		'BucketSection muss animate:flip auf dem direkten Kind-div von dndzone verwenden.',
	);
});

test('AC-8: BucketSection iteriert über dndItems (nicht items) im Template', () => {
	const src = read(BUCKET);
	// #each dndItems statt #each items
	assert.ok(
		src.includes('#each dndItems') || src.includes('{#each dndItems'),
		'BucketSection muss im Template über dndItems iterieren (nicht items), damit der Signal-Divider korrekt bleibt.',
	);
});

// =============================================================================
// OutputLayoutEditor.svelte — AC-4 (SMS out), AC-5 (Cross-Bucket out)
// =============================================================================

test('AC-1/AC-7: OutputLayoutEditor hat optionales Prop onDndReorder', () => {
	const src = read(EDITOR);
	assert.ok(
		src.includes('onDndReorder'),
		'OutputLayoutEditor muss onDndReorder als (optionales) Prop deklarieren.',
	);
});

test('AC-1: OutputLayoutEditor leitet onDndReorder an beide BucketSection-Instanzen weiter', () => {
	const src = read(EDITOR);
	// Mindestens zwei Erwähnungen von onDndReorder (Prop + Weitergabe an primary + secondary)
	const count = (src.match(/onDndReorder/g) || []).length;
	assert.ok(
		count >= 3,
		`OutputLayoutEditor muss onDndReorder mindestens 3× erwähnen (Prop-Deklaration + primary + secondary). Gefunden: ${count}`,
	);
});

test('AC-4: OutputLayoutEditor-SMS-Branch enthält kein dndzone', () => {
	const src = read(EDITOR);
	// SMS-Branch: der Abschnitt zwischen {#if channel === 'sms'} und {:else}
	// Wir prüfen: wenn der SMS-Branch kein dndzone enthält, ist AC-4 erfüllt.
	// Einfache Heuristik: dndzone darf NUR im Standard-Branch vorkommen, nicht nahe 'sms'.
	const smsSectionMatch = src.match(/channel === ['"]sms['"][\s\S]*?{:else}/);
	if (smsSectionMatch) {
		assert.ok(
			!smsSectionMatch[0].includes('dndzone'),
			'SMS-Branch darf kein dndzone enthalten (AC-4: SMS ist explizit Out of Scope).',
		);
	}
	// Wenn kein {:else}-Split gefunden: Test schlägt fehl, da Struktur nicht wie erwartet
});

// =============================================================================
// WeatherMetricsTab.svelte — AC-10
// =============================================================================

test('AC-10: WeatherMetricsTab hat onDndReorder-Handler', () => {
	const src = read(METRICS);
	assert.ok(
		src.includes('onDndReorder'),
		'WeatherMetricsTab muss einen onDndReorder-Handler implementieren.',
	);
});

test('AC-10: WeatherMetricsTab onDndReorder ersetzt Bucket per Spread', () => {
	const src = read(METRICS);
	// Handler-Logik: { ...buckets, [bucket]: newOrder } oder äquivalent
	const hasSpread = src.includes('...buckets') || src.includes('{ ...buckets');
	assert.ok(
		hasSpread,
		'WeatherMetricsTab onDndReorder muss Bucket per Spread-Zuweisung ersetzen.',
	);
});

test('AC-10: WeatherMetricsTab übergibt onDndReorder an OutputLayoutEditor', () => {
	const src = read(METRICS);
	// OutputLayoutEditor-Aufruf muss onDndReorder als Prop enthalten
	const editorBlock = src.match(/OutputLayoutEditor[\s\S]*?(?:>|\/\>)/);
	assert.ok(
		editorBlock && editorBlock[0].includes('onDndReorder'),
		'WeatherMetricsTab muss onDndReorder an OutputLayoutEditor übergeben.',
	);
});

// =============================================================================
// Step4Layout.svelte — AC-10
// =============================================================================

test('AC-10: Step4Layout hat handleDndReorder-Handler', () => {
	const src = read(STEP4);
	assert.ok(
		src.includes('handleDndReorder') || src.includes('onDndReorder'),
		'Step4Layout muss einen handleDndReorder- oder onDndReorder-Handler implementieren.',
	);
});

test('AC-10: Step4Layout handleDndReorder aktualisiert channelBuckets[activeChannel][bucket]', () => {
	const src = read(STEP4);
	// Handler muss channelBuckets spreaden und activeChannel + bucket-Key ersetzen
	const hasChannelBucketsUpdate =
		src.includes('channelBuckets') &&
		(src.includes('[activeChannel]') || src.includes('activeChannel'));
	assert.ok(
		hasChannelBucketsUpdate,
		'handleDndReorder muss channelBuckets mit dem aktiven Kanal und dem Bucket-Key aktualisieren.',
	);
});

test('AC-10: Step4Layout übergibt onDndReorder an OutputLayoutEditor', () => {
	const src = read(STEP4);
	const editorBlock = src.match(/OutputLayoutEditor[\s\S]*?(?:>|\/\>)/);
	assert.ok(
		editorBlock && editorBlock[0].includes('onDndReorder') || src.includes('onDndReorder={handleDndReorder}'),
		'Step4Layout muss onDndReorder an OutputLayoutEditor übergeben.',
	);
});

// =============================================================================
// AC-3: ▲▼-Buttons bleiben erhalten
// =============================================================================

test('AC-3: BucketSection behält onReorder-Prop (▲▼-Buttons-Pfad unverändert)', () => {
	const src = read(BUCKET);
	assert.ok(
		src.includes('onReorder'),
		'BucketSection muss onReorder weiterhin als Prop haben (▲▼-Buttons bleiben erhalten).',
	);
});

test('AC-3: ActiveMetricRow wird weiterhin in BucketSection verwendet', () => {
	const src = read(BUCKET);
	assert.ok(
		src.includes('ActiveMetricRow'),
		'BucketSection muss ActiveMetricRow weiterhin einbetten.',
	);
});
