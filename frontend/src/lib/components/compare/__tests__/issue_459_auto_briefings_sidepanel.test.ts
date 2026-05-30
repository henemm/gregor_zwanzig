// TDD RED — Issue #459: Auto-Briefings Sidepanel Frontend
//
// Spec: docs/specs/modules/issue_459_auto_briefings_sidepanel.md
//
// Source-Inspection-Tests (node:test, kein DOM-Rendering).
// Prüft: ComparePreset-Typ, Helper-Funktionen, Komponenten-Props,
//        SavePresetDialog, Send-Button, Leerzustand, Page-Integration.
//
// RED-Erwartung (vor Implementation):
//   - types.ts hat kein ComparePreset-Interface
//   - subscriptionHelpers.ts hat kein presetScheduleLabel
//   - AutoReportsOverview.svelte hat noch subscriptions-Prop
//   - AutoReportCard.svelte hat noch subscription-Prop, keinen Send-Button
//   - SavePresetDialog.svelte existiert nicht
//   - +page.server.ts lädt keine presets
//   - +page.svelte übergibt noch data.subscriptions
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_459_auto_briefings_sidepanel.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

const TYPES        = resolve('src/lib/types.ts');
const HELPERS      = resolve('src/lib/components/compare/subscriptionHelpers.ts');
const OVERVIEW     = resolve('src/lib/components/compare/AutoReportsOverview.svelte');
const CARD         = resolve('src/lib/components/compare/AutoReportCard.svelte');
const SAVE_DIALOG  = resolve('src/lib/components/compare/SavePresetDialog.svelte');
const PAGE_SERVER  = resolve('src/routes/compare/+page.server.ts');
const PAGE         = resolve('src/routes/compare/+page.svelte');

// ── §1 ComparePreset-Interface in types.ts ───────────────────────────────────

test('AC-1: ComparePreset-Interface existiert in types.ts', () => {
	const src = readFileSync(TYPES, 'utf-8');
	assert.match(src, /interface ComparePreset/, 'types.ts muss ein ComparePreset-Interface enthalten');
});

test('AC-1: ComparePreset hat Pflichtfeld schedule (daily|weekly|manual)', () => {
	const src = readFileSync(TYPES, 'utf-8');
	assert.match(
		src,
		/schedule:\s*['"]daily['"]\s*\|\s*['"]weekly['"]\s*\|\s*['"]manual['"]/,
		"ComparePreset.schedule muss 'daily' | 'weekly' | 'manual' typisiert sein"
	);
});

test('AC-1: ComparePreset hat Felder letzter_versand und top_ort_letzter_versand', () => {
	const src = readFileSync(TYPES, 'utf-8');
	assert.match(src, /letzter_versand/, 'ComparePreset muss letzter_versand enthalten');
	assert.match(src, /top_ort_letzter_versand/, 'ComparePreset muss top_ort_letzter_versand enthalten');
});

test('AC-1: ComparePreset hat Feld empfaenger', () => {
	const src = readFileSync(TYPES, 'utf-8');
	assert.match(src, /empfaenger/, 'ComparePreset muss empfaenger enthalten');
});

// ── §2 subscriptionHelpers.ts — neue Helfer ───────────────────────────────────

test('AC-1: presetScheduleLabel wird aus subscriptionHelpers exportiert', () => {
	const src = readFileSync(HELPERS, 'utf-8');
	assert.match(
		src,
		/export\s+function\s+presetScheduleLabel/,
		'subscriptionHelpers.ts muss presetScheduleLabel exportieren'
	);
});

test('AC-1: presetScheduleLabel behandelt schedule=daily mit hour_from/hour_to', () => {
	const src = readFileSync(HELPERS, 'utf-8');
	assert.match(src, /hour_from/, 'presetScheduleLabel muss hour_from verwenden');
	assert.match(src, /hour_to/, 'presetScheduleLabel muss hour_to verwenden');
});

test('AC-1: formatLastSent wird aus subscriptionHelpers exportiert', () => {
	const src = readFileSync(HELPERS, 'utf-8');
	assert.match(
		src,
		/export\s+function\s+formatLastSent/,
		'subscriptionHelpers.ts muss formatLastSent exportieren'
	);
});

// ── §3 +page.server.ts — Presets laden ────────────────────────────────────────

test('AC-1: +page.server.ts lädt /api/compare/presets', () => {
	const src = readFileSync(PAGE_SERVER, 'utf-8');
	assert.match(
		src,
		/\/api\/compare\/presets/,
		'+page.server.ts muss /api/compare/presets fetchen'
	);
});

test('AC-1: +page.server.ts gibt presets im Return-Objekt zurück', () => {
	const src = readFileSync(PAGE_SERVER, 'utf-8');
	assert.match(src, /presets/, '+page.server.ts muss presets im return zurückgeben');
});

// ── §4 AutoReportsOverview.svelte — Props-Umbau ───────────────────────────────

test('AC-1: AutoReportsOverview nutzt presets-Prop (nicht subscriptions)', () => {
	const src = readFileSync(OVERVIEW, 'utf-8');
	assert.match(src, /presets/, 'AutoReportsOverview.svelte muss presets-Prop nutzen');
	assert.doesNotMatch(
		src,
		/subscriptions:\s*Subscription/,
		'AutoReportsOverview.svelte darf keinen subscriptions: Subscription-Prop mehr haben'
	);
});

test('AC-4: AutoReportsOverview enthält data-testid="auto-reports-empty" für Leerzustand', () => {
	const src = readFileSync(OVERVIEW, 'utf-8');
	assert.match(
		src,
		/auto-reports-empty/,
		'AutoReportsOverview.svelte muss data-testid="auto-reports-empty" für den Leerzustand enthalten'
	);
});

test('AC-4: Leerzustand prüft presets.length === 0', () => {
	const src = readFileSync(OVERVIEW, 'utf-8');
	assert.match(
		src,
		/presets\.length/,
		'AutoReportsOverview.svelte muss presets.length für den Leerzustand prüfen'
	);
});

test('AC-2: AutoReportsOverview importiert SavePresetDialog', () => {
	const src = readFileSync(OVERVIEW, 'utf-8');
	assert.match(
		src,
		/import\s+SavePresetDialog/,
		'AutoReportsOverview.svelte muss SavePresetDialog importieren'
	);
});

test('AC-2: AutoReportsOverview enthält SavePresetDialog-Instanz mit bind:open', () => {
	const src = readFileSync(OVERVIEW, 'utf-8');
	assert.match(
		src,
		/SavePresetDialog/,
		'AutoReportsOverview.svelte muss SavePresetDialog einbinden'
	);
	assert.match(
		src,
		/bind:open/,
		'AutoReportsOverview.svelte muss bind:open für SavePresetDialog nutzen'
	);
});

// ── §5 SavePresetDialog.svelte — neue Datei ───────────────────────────────────

test('AC-2: SavePresetDialog.svelte existiert', () => {
	assert.ok(existsSync(SAVE_DIALOG), 'SavePresetDialog.svelte muss existieren');
});

test('AC-2: SavePresetDialog enthält data-testid="save-preset-dialog"', () => {
	const src = readFileSync(SAVE_DIALOG, 'utf-8');
	assert.match(src, /save-preset-dialog/, 'SavePresetDialog.svelte muss data-testid="save-preset-dialog" enthalten');
});

test('AC-2: SavePresetDialog hat Input für Preset-Name', () => {
	const src = readFileSync(SAVE_DIALOG, 'utf-8');
	assert.match(src, /save-preset-name/, 'SavePresetDialog.svelte muss data-testid="save-preset-name" enthalten');
});

test('AC-2: SavePresetDialog hat Schedule-Select', () => {
	const src = readFileSync(SAVE_DIALOG, 'utf-8');
	assert.match(src, /save-preset-schedule/, 'SavePresetDialog.svelte muss data-testid="save-preset-schedule" enthalten');
});

test('AC-2: SavePresetDialog sendet POST /api/compare/presets', () => {
	const src = readFileSync(SAVE_DIALOG, 'utf-8');
	assert.match(
		src,
		/\/api\/compare\/presets/,
		'SavePresetDialog.svelte muss POST /api/compare/presets aufrufen'
	);
});

test('AC-2: SavePresetDialog nutzt Dialog.Root und bind:open', () => {
	const src = readFileSync(SAVE_DIALOG, 'utf-8');
	assert.match(src, /Dialog\.Root/, 'SavePresetDialog.svelte muss Dialog.Root nutzen');
	assert.match(src, /bind:open/, 'SavePresetDialog.svelte muss bind:open nutzen');
});

test('AC-2: SavePresetDialog hat Fehlerfeld data-testid="save-preset-error"', () => {
	const src = readFileSync(SAVE_DIALOG, 'utf-8');
	assert.match(src, /save-preset-error/, 'SavePresetDialog.svelte muss data-testid="save-preset-error" für Fehleranzeige enthalten');
});

// ── §6 AutoReportCard.svelte — Send-Button ────────────────────────────────────

test('AC-3: AutoReportCard nutzt preset-Prop (nicht subscription)', () => {
	const src = readFileSync(CARD, 'utf-8');
	assert.match(src, /preset/, 'AutoReportCard.svelte muss preset-Prop nutzen');
	assert.doesNotMatch(
		src,
		/subscription:\s*Subscription/,
		'AutoReportCard.svelte darf keinen subscription: Subscription-Prop mehr haben'
	);
});

test('AC-3: AutoReportCard enthält Send-Button mit korrektem data-testid', () => {
	const src = readFileSync(CARD, 'utf-8');
	assert.match(
		src,
		/auto-report-send/,
		'AutoReportCard.svelte muss data-testid="auto-report-send-{id}" für den Send-Button enthalten'
	);
});

test('AC-3: AutoReportCard ruft /api/compare/presets/{id}/send auf', () => {
	const src = readFileSync(CARD, 'utf-8');
	assert.match(
		src,
		/\/api\/compare\/presets\/.*\/send|\/api\/compare\/presets.*send/,
		'AutoReportCard.svelte muss /api/compare/presets/{id}/send aufrufen'
	);
});

test('AC-3: AutoReportCard importiert Send-Icon', () => {
	const src = readFileSync(CARD, 'utf-8');
	assert.match(
		src,
		/[Ss]end[Ii]con|icons\/send/,
		'AutoReportCard.svelte muss ein Send-Icon importieren'
	);
});

test('AC-3: AutoReportCard hat sending-State (Button deaktiviert während API-Call)', () => {
	const src = readFileSync(CARD, 'utf-8');
	assert.match(src, /sending/, 'AutoReportCard.svelte muss sending-State für den Send-Button enthalten');
});

// ── §7 +page.svelte — Anpassung ───────────────────────────────────────────────

test('AC-1: +page.svelte übergibt data.presets an AutoReportsOverview', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/presets={data\.presets}/,
		'+page.svelte muss presets={data.presets} an AutoReportsOverview übergeben'
	);
});

test('AC-1: +page.svelte übergibt NICHT subscriptions-Prop an AutoReportsOverview', () => {
	const src = readFileSync(PAGE, 'utf-8');
	// Der subscriptions-Prop darf in AutoReportsOverview nicht mehr vorkommen.
	// Prüft ob irgendein subscriptions=... Binding in der AutoReportsOverview-Sektion existiert.
	assert.doesNotMatch(
		src,
		/AutoReportsOverview[\s\S]{0,300}subscriptions=/,
		'+page.svelte darf keinen subscriptions-Prop mehr an AutoReportsOverview übergeben'
	);
});
