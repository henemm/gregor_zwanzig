// TDD RED — Issue #1256 S8b (Rest-Inventur R1): Hub-Vorschau-Kanal-Umschalter.
//
// Spec: docs/specs/modules/fix_1256_s8b_preview_channel_switch.md
// Soll: screen-compare-detail.jsx:351 (channels aus Preset-Konfiguration),
//       :365-369 („Kanal nicht konfiguriert"-Hinweis)
//
// IST-BEFUND (Audit 2026-07-14): CompareTabs.svelte:943 übergibt `onchange`
// (klein) — CompareChannelSwitch (molecules) erwartet `onChange`; Svelte-5-
// Props sind case-sensitiv, der Klick-Handler kommt nie an → Umschalter ist
// ein No-Op. Kanal-Liste zudem hart ['email','sms'] (Telegram fehlt immer),
// kein Hinweis-Zustand für unkonfigurierte Kanäle.
//
// Source-Inspection (Projekt-Idiom, kein jsdom-Mount); der eigentliche
// Klick-Beweis läuft als Playwright-Wächter gegen Staging (AC-1), weil die
// No-Op-Klasse „falsch benannter Handler-Prop" nur im echten DOM sicher
// auffällt.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const TABS = resolve(HERE, '../CompareTabs.svelte');

function previewBlock(): string {
	const src = readFileSync(TABS, 'utf-8');
	const start = src.indexOf('<CompareChannelSwitch');
	assert.ok(start > -1, 'CompareChannelSwitch wird im Vorschau-Tab nicht gerendert');
	return src.slice(start, start + 600);
}

describe('AC-1 — Umschalter-Handler ist verdrahtet (onChange, case-sensitiv)', () => {
	test('CompareChannelSwitch erhält onChange (nicht onchange)', () => {
		const block = previewBlock();
		assert.match(
			block,
			/\bonChange=\{/,
			'CompareChannelSwitch bekommt kein onChange-Prop — Svelte-5-Props sind ' +
				'case-sensitiv, `onchange` kommt nie an und der Kanal-Klick ist ein No-Op ' +
				'(CompareChannelSwitch.svelte: interface Props { onChange?: ... })'
		);
		assert.doesNotMatch(
			block,
			/\bonchange=\{/,
			'CompareChannelSwitch bekommt noch das wirkungslose kleingeschriebene onchange-Prop'
		);
	});
});

describe('AC-2 — Kanal-Liste kommt aus der Preset-Konfiguration', () => {
	test('kein hartes Kanal-Literal am Umschalter, Telegram möglich', () => {
		const block = previewBlock();
		assert.doesNotMatch(
			block,
			/channels=\{\[\s*'email'\s*,\s*'sms'\s*\]\}/,
			'Kanal-Liste ist hart [email, sms] — Telegram-Nutzer sehen ihren Kanal nie ' +
				'(Soll: konfigurierte Kanäle des Presets, screen-compare-detail.jsx:351)'
		);
	});

	test('previewChannel-Typ umfasst telegram', () => {
		const src = readFileSync(TABS, 'utf-8');
		const decl = src.match(/let previewChannel = \$state<([^>]+)>/);
		assert.ok(decl, 'previewChannel-State-Deklaration nicht gefunden');
		assert.ok(
			decl[1].includes('telegram'),
			`previewChannel-Typ ist <${decl[1]}> — Telegram kann nie gewählt werden`
		);
	});
});

describe('AC-3 — Hinweis-Zustand für unkonfigurierten Kanal', () => {
	test('Render-Fläche kennt „Kanal nicht konfiguriert"', () => {
		const src = readFileSync(TABS, 'utf-8');
		assert.match(
			src,
			/nicht konfiguriert/i,
			'Es gibt keinen „Kanal nicht konfiguriert"-Hinweis — die Wahl eines ' +
				'unkonfigurierten Kanals zeigt leere/stale Vorschau ' +
				'(Soll: screen-compare-detail.jsx:365-369)'
		);
	});
});
