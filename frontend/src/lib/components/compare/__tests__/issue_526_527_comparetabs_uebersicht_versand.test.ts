// TDD RED — Issues #526 + #527: CompareTabs Übersicht- und Versand-Tab
//
// Spec: docs/specs/modules/issue_526_527_comparetabs_uebersicht_versand.md
//
// Source-Inspection-Tests: prüfen Soll-Zustand nach Implementation.
//
// RED-Erwartung (vor Implementation):
//   AC-1: FAIL — kein summary-grid / 4 SummaryCards im Übersicht-Tab
//   AC-2: FAIL — kein handleValueChange('orte'/'idealwerte'/'layout'/'versand') im Übersicht-Tab
//   AC-3: FAIL — monitoring-strip statt Card; Card-Import fehlt
//   AC-4: FAIL — kein accent={true} Card + kein 'Vorschau prüfen'-Button im Übersicht-Tab
//   AC-5: FAIL — kein versand-grid im Versand-Tab
//   AC-6: FAIL — kein Switch-Import; keine Email/Signal/Telegram/SMS-Kanal-Zeilen mit Switch
//   AC-7: FAIL — kein 'Pausieren'-Button im Versand-Tab
//   AC-8: FAIL — kein 'Aktivieren'-Button bei Draft-Status
//   AC-9: FAIL — kein 'Aktivieren'-Button bei Paused-Status (= AC-8)
//   AC-10: FAIL — kein 'Test-Briefing'-Button im Versand-Tab (nur in Vorschau-Tab)
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_526_527_comparetabs_uebersicht_versand.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const COMPARE_DIR = join(dirname(fileURLToPath(import.meta.url)), '..');
const TABS_FILE = join(COMPARE_DIR, 'CompareTabs.svelte');

function src(): string {
	assert.ok(existsSync(TABS_FILE), 'CompareTabs.svelte existiert nicht');
	return readFileSync(TABS_FILE, 'utf-8');
}

// ── Imports ──────────────────────────────────────────────────────────────────

describe('Imports: Card, Switch, DetailRow', () => {
	test('Card ist aus atoms importiert', () => {
		assert.match(
			src(),
			/\bCard\b.*from.*atoms|from.*atoms.*\bCard\b/,
			'Card-Atom fehlt in den Imports von CompareTabs.svelte'
		);
	});

	test('Switch ist aus atoms importiert', () => {
		assert.match(
			src(),
			/\bSwitch\b.*from.*atoms|from.*atoms.*\bSwitch\b/,
			'Switch-Atom fehlt in den Imports von CompareTabs.svelte'
		);
	});

	test('DetailRow ist importiert', () => {
		assert.match(
			src(),
			/DetailRow/,
			'DetailRow-Molecule fehlt in den Imports von CompareTabs.svelte'
		);
	});
});

// ── AC-1: 2×2 SummaryCard-Grid im Übersicht-Tab ──────────────────────────────

describe('AC-1: 2×2 SummaryCard-Grid im Übersicht-Tab', () => {
	test('summary-grid CSS-Klasse oder äquivalente Grid-Struktur vorhanden', () => {
		assert.match(
			src(),
			/summary-grid|summary_grid/,
			'Kein summary-grid im Übersicht-Tab gefunden — 2×2 SummaryCard-Grid fehlt'
		);
	});

	test('Übersicht-Tab enthält 4 Cards (Orte / Idealwerte / Layout / Versand)', () => {
		const content = src();
		// Im uebersicht-Tab-Block müssen mindestens 4 <Card-Tags vorkommen
		const uebersichtBlock = content.slice(
			content.indexOf("activeTab === 'uebersicht'"),
			content.indexOf("activeTab === 'orte'")
		);
		const cardMatches = uebersichtBlock.match(/<Card\b/g) ?? [];
		assert.ok(
			cardMatches.length >= 4,
			`Im Übersicht-Tab wurden nur ${cardMatches.length} <Card>-Elemente gefunden, erwartet ≥4`
		);
	});
});

// ── AC-2: Bearbeiten-Buttons wechseln Tab ────────────────────────────────────

describe('AC-2: Bearbeiten-Buttons im Übersicht-Tab rufen handleValueChange auf', () => {
	test("handleValueChange('orte') im Übersicht-Tab vorhanden", () => {
		const content = src();
		const uebersichtBlock = content.slice(
			content.indexOf("activeTab === 'uebersicht'"),
			content.indexOf("activeTab === 'orte'")
		);
		assert.match(
			uebersichtBlock,
			/handleValueChange\s*\(\s*['"]orte['"]\s*\)/,
			"handleValueChange('orte') fehlt im Übersicht-Tab — Orte-Kachel hat keinen Bearbeiten-Button"
		);
	});

	test("handleValueChange('idealwerte') im Übersicht-Tab vorhanden", () => {
		const content = src();
		const uebersichtBlock = content.slice(
			content.indexOf("activeTab === 'uebersicht'"),
			content.indexOf("activeTab === 'orte'")
		);
		assert.match(
			uebersichtBlock,
			/handleValueChange\s*\(\s*['"]idealwerte['"]\s*\)/,
			"handleValueChange('idealwerte') fehlt im Übersicht-Tab"
		);
	});

	test("handleValueChange('layout') im Übersicht-Tab vorhanden", () => {
		const content = src();
		const uebersichtBlock = content.slice(
			content.indexOf("activeTab === 'uebersicht'"),
			content.indexOf("activeTab === 'orte'")
		);
		assert.match(
			uebersichtBlock,
			/handleValueChange\s*\(\s*['"]layout['"]\s*\)/,
			"handleValueChange('layout') fehlt im Übersicht-Tab"
		);
	});

	test("handleValueChange('versand') im Übersicht-Tab vorhanden", () => {
		const content = src();
		const uebersichtBlock = content.slice(
			content.indexOf("activeTab === 'uebersicht'"),
			content.indexOf("activeTab === 'orte'")
		);
		assert.match(
			uebersichtBlock,
			/handleValueChange\s*\(\s*['"]versand['"]\s*\)/,
			"handleValueChange('versand') fehlt im Übersicht-Tab"
		);
	});
});

// ── AC-3: Monitoring-Info in weißer Card ─────────────────────────────────────

describe('AC-3: Monitoring-Info in weißer Card statt off-white monitoring-strip', () => {
	test('monitoring-strip mit g-paper-Hintergrund ist entfernt', () => {
		const content = src();
		// Der alte Strip hatte background: var(--g-paper) — das soll weg
		assert.ok(
			!content.includes('class="monitoring-strip"'),
			'.monitoring-strip-Div noch vorhanden — muss durch Card-Atom ersetzt werden'
		);
	});

	test('Monitoring-Block im Übersicht-Tab nutzt <Card', () => {
		const content = src();
		const uebersichtBlock = content.slice(
			content.indexOf("activeTab === 'uebersicht'"),
			content.indexOf("activeTab === 'orte'")
		);
		assert.match(
			uebersichtBlock,
			/<Card\b/,
			'Kein <Card-Element im Übersicht-Tab gefunden — Monitoring muss in Card sein'
		);
	});
});

// ── AC-4: Hinweis-Box mit accent-Border + Vorschau-Button ────────────────────

describe('AC-4: Hinweis-Box mit accent={true} und "Vorschau prüfen →" Button', () => {
	test('accent={true} Card im Übersicht-Tab vorhanden', () => {
		const content = src();
		const uebersichtBlock = content.slice(
			content.indexOf("activeTab === 'uebersicht'"),
			content.indexOf("activeTab === 'orte'")
		);
		assert.match(
			uebersichtBlock,
			/accent\s*=\s*\{true\}|accent={true}/,
			'Kein <Card accent={true}> im Übersicht-Tab — Hinweis-Box fehlt'
		);
	});

	test('"Gelesen wird das Briefing" Text im Übersicht-Tab vorhanden', () => {
		const content = src();
		const uebersichtBlock = content.slice(
			content.indexOf("activeTab === 'uebersicht'"),
			content.indexOf("activeTab === 'orte'")
		);
		assert.match(
			uebersichtBlock,
			/Gelesen wird das Briefing/,
			'Hinweis-Text "Gelesen wird das Briefing" fehlt im Übersicht-Tab'
		);
	});

	test("handleValueChange('vorschau') in Hinweis-Box vorhanden", () => {
		const content = src();
		const uebersichtBlock = content.slice(
			content.indexOf("activeTab === 'uebersicht'"),
			content.indexOf("activeTab === 'orte'")
		);
		assert.match(
			uebersichtBlock,
			/handleValueChange\s*\(\s*['"]vorschau['"]\s*\)/,
			"handleValueChange('vorschau') fehlt in Hinweis-Box — 'Vorschau prüfen →'-Button fehlt"
		);
	});
});

// ── AC-5: 2-Spalten-Grid im Versand-Tab ──────────────────────────────────────

describe('AC-5: 2-Spalten-Grid im Versand-Tab', () => {
	test('versand-grid CSS-Klasse oder äquivalente Grid-Struktur vorhanden', () => {
		const content = src();
		const versandBlock = content.slice(
			content.indexOf("activeTab === 'versand'"),
			content.indexOf("activeTab === 'vorschau'")
		);
		assert.match(
			versandBlock,
			/versand-grid|versand_grid/,
			'Kein versand-grid im Versand-Tab — 2-Spalten-Layout fehlt'
		);
	});

	test('Versand-Tab enthält linke und rechte Spalte', () => {
		const content = src();
		const versandBlock = content.slice(
			content.indexOf("activeTab === 'versand'"),
			content.indexOf("activeTab === 'vorschau'")
		);
		assert.match(
			versandBlock,
			/versand-left|versand_left/,
			'Kein versand-left-Bereich im Versand-Tab gefunden'
		);
	});
});

// ── AC-6: Kanal-Card mit 4 Kanal-Zeilen + Switch ─────────────────────────────

describe('AC-6: Kanal-Card mit Email/Signal/Telegram/SMS + Switch-Toggle', () => {
	test('<Switch im Versand-Tab vorhanden', () => {
		const content = src();
		const versandBlock = content.slice(
			content.indexOf("activeTab === 'versand'"),
			content.indexOf("activeTab === 'vorschau'")
		);
		assert.match(
			versandBlock,
			/<Switch\b/,
			'<Switch> fehlt im Versand-Tab — Kanal-Toggles nicht implementiert'
		);
	});

	test("'Signal' als Kanalname im Versand-Tab vorhanden", () => {
		const content = src();
		const versandBlock = content.slice(
			content.indexOf("activeTab === 'versand'"),
			content.indexOf("activeTab === 'vorschau'")
		);
		assert.match(
			versandBlock,
			/\bSignal\b/,
			"Kanal 'Signal' fehlt im Versand-Tab Kanal-Card"
		);
	});

	test("'Telegram' als Kanalname im Versand-Tab vorhanden", () => {
		const content = src();
		const versandBlock = content.slice(
			content.indexOf("activeTab === 'versand'"),
			content.indexOf("activeTab === 'vorschau'")
		);
		assert.match(
			versandBlock,
			/\bTelegram\b/,
			"Kanal 'Telegram' fehlt im Versand-Tab Kanal-Card"
		);
	});

	test("'SMS' als Kanalname im Versand-Tab vorhanden", () => {
		const content = src();
		const versandBlock = content.slice(
			content.indexOf("activeTab === 'versand'"),
			content.indexOf("activeTab === 'vorschau'")
		);
		assert.match(
			versandBlock,
			/\bSMS\b/,
			"Kanal 'SMS' fehlt im Versand-Tab Kanal-Card"
		);
	});

	test("'nicht verbunden' Status-Text im Versand-Tab vorhanden", () => {
		const content = src();
		const versandBlock = content.slice(
			content.indexOf("activeTab === 'versand'"),
			content.indexOf("activeTab === 'vorschau'")
		);
		assert.match(
			versandBlock,
			/nicht verbunden/,
			"Status-Text 'nicht verbunden' fehlt in der Kanal-Card"
		);
	});
});

// ── AC-7: Aktivierungs-Card — aktiv → Pausieren-Button ───────────────────────

describe('AC-7: Aktivierungs-Card zeigt Pausieren-Button bei aktivem Preset', () => {
	test("'Pausieren'-Button im Versand-Tab vorhanden", () => {
		const content = src();
		const versandBlock = content.slice(
			content.indexOf("activeTab === 'versand'"),
			content.indexOf("activeTab === 'vorschau'")
		);
		assert.match(
			versandBlock,
			/Pausieren/,
			"'Pausieren'-Button fehlt im Versand-Tab — Aktivierungs-Card nicht implementiert"
		);
	});

	test("localSchedule $state-Variable im Script vorhanden", () => {
		assert.match(
			src(),
			/localSchedule/,
			"'localSchedule' fehlt im Script-Block — Pause/Aktivieren-State nicht implementiert"
		);
	});
});

// ── AC-8+9: Aktivierungs-Card — Draft/Paused → Aktivieren-Button ─────────────

describe('AC-8+9: Aktivierungs-Card zeigt Aktivieren-Button bei Draft/Paused', () => {
	test("'Aktivieren'-Button im Versand-Tab vorhanden", () => {
		const content = src();
		const versandBlock = content.slice(
			content.indexOf("activeTab === 'versand'"),
			content.indexOf("activeTab === 'vorschau'")
		);
		assert.match(
			versandBlock,
			/Aktivieren/,
			"'Aktivieren'-Button fehlt im Versand-Tab — Draft/Paused-State nicht implementiert"
		);
	});

	test("handleToggleActive oder äquivalente Pause/Aktivier-Funktion vorhanden", () => {
		assert.match(
			src(),
			/handleToggleActive|toggleActive|handlePause|handleActivate/,
			'Keine Pause/Aktivieren-Handler-Funktion im Script-Block gefunden'
		);
	});
});

// ── AC-10: Test-Briefing senden im Versand-Tab ────────────────────────────────

describe('AC-10: Test-Briefing senden im Versand-Tab', () => {
	test("'Test-Briefing' Button im Versand-Tab vorhanden (nicht nur in Vorschau)", () => {
		const content = src();
		const versandBlock = content.slice(
			content.indexOf("activeTab === 'versand'"),
			content.indexOf("activeTab === 'vorschau'")
		);
		assert.match(
			versandBlock,
			/Test-Briefing/,
			"'Test-Briefing jetzt senden' fehlt im Versand-Tab — nur im Vorschau-Tab vorhanden"
		);
	});
});
