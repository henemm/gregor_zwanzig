// Issue #1461 Scheibe S3b-2a — AC-10: der Nutzer sieht je Kanal die
// eingestellte Dringlichkeits-Schwelle und kann sie aendern; die Aenderung
// loest die konsolidierte Speicherung aus (route-Speicherweg).
//
// Reine Logik-Tests (kein DOM-Rendering, keine Mocks, kein Playwright).
// Svelte-5-Komponenten sind ohne @testing-library/svelte (nicht in
// package.json) in diesem Test-Setup nicht mountbar — ADR-0020 zieht daraus
// bewusst die Konsequenz: Unit-Tests bleiben auf reine Funktionen/Helpers
// beschraenkt, UI-Rendering-/Klick-Verhalten gehoert in Playwright-E2E.
//
// Adversary-Befund F003 (Runde 2): eine fruehere Fassung dieser Datei prüfte
// „Teil C" per Quelltext-String-Suche (`src.includes(...)`) auf
// AlertChannelPicker.svelte/AlarmeTab.svelte — genau das von CLAUDE.md
// verbotene Dateiinhalt-Matching als Verhaltensnachweis. Fix: die
// eigentliche Aenderungs-Logik hinter einem Klick (Zusammenfuehren von
// Zustand + Kanal + neuer Stufe) lebt jetzt als reine, exportierte Funktion
// `applyThresholdChange()` in `alertChannelState.ts` — AlarmeTab.svelte ruft
// sie auf, statt die Logik nur inline zu duplizieren. Damit ist "kann diese
// Einstellung aendern" (AC-10) an ECHTEN Ein-/Ausgabewerten geprueft. Die
// verbleibenden Teile von Teil C (Rendering, Klick-Verdrahtung im Markup,
// Kontext-Gating) sind ohne Mount-Faehigkeit nicht als Verhalten pruefbar
// und wurden ENTFERNT statt als Quelltext-Suche stehen zu bleiben (lieber
// weniger Tests als scheinbare) — die Wirkung dort ist Sache der
// Staging-/Playwright-E2E-Verifikation nach dem Deploy.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/alarme-tab/alertChannelThresholds.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
	applyThresholdChange,
	resolveAlertChannelThresholds,
	CHANNEL_THRESHOLD_LEVELS,
	CHANNEL_THRESHOLD_LABELS
} from './alertChannelState.ts';
import { buildAlarmeDeliveryPayload } from './alarmeDeliveryPayload.ts';

// ─────────────────────────────────────────────────────────────────────────
// Nachweisbarer Teil A: Zustand — "erkennt er, ab welcher Dringlichkeit
// dieser ihn erreicht" (Startwert 'gering', Bestand wird angezeigt).
// ─────────────────────────────────────────────────────────────────────────
describe('AC-10: resolveAlertChannelThresholds() zeigt den aktuellen Wert je Kanal', () => {
	test('ohne Bestand: alle drei Kanaele zeigen den Startwert LOW (gering)', () => {
		const state = resolveAlertChannelThresholds(null);
		assert.deepEqual(state, { telegram: 'LOW', sms: 'LOW', email: 'LOW' });
	});

	test('mit Bestand: der eingestellte Wert eines Kanals erscheint unveraendert, die anderen bleiben LOW', () => {
		const state = resolveAlertChannelThresholds({ telegram: 'HIGH' });
		assert.equal(state.telegram, 'HIGH', 'telegram muss den Bestandswert HIGH zeigen');
		assert.equal(state.sms, 'LOW', 'sms ohne Bestand bleibt beim Startwert LOW');
		assert.equal(state.email, 'LOW', 'email ohne Bestand bleibt beim Startwert LOW');
	});

	test('drei Stufen sind gering/mittel/hoch beschriftet', () => {
		assert.deepEqual(CHANNEL_THRESHOLD_LEVELS, ['LOW', 'MODERATE', 'HIGH']);
		assert.equal(CHANNEL_THRESHOLD_LABELS.LOW, 'gering');
		assert.equal(CHANNEL_THRESHOLD_LABELS.MODERATE, 'mittel');
		assert.equal(CHANNEL_THRESHOLD_LABELS.HIGH, 'hoch');
	});
});

// ─────────────────────────────────────────────────────────────────────────
// Nachweisbarer Teil B: "kann diese Einstellung aendern, und die dadurch
// ausgeloeste Speicherung" — die konsolidierte Payload traegt den
// geaenderten Wert.
// ─────────────────────────────────────────────────────────────────────────
describe('AC-10: eine geaenderte Schwelle erscheint in der gespeicherten Payload', () => {
	test('buildAlarmeDeliveryPayload() sendet alert_channel_thresholds mit allen drei Kanaelen', () => {
		const payload = buildAlarmeDeliveryPayload({
			officialWarningsEnabled: true,
			channels: { email: false, telegram: true, sms: true },
			channelThresholds: { email: 'LOW', telegram: 'HIGH', sms: 'MODERATE' }
		}) as { alert_channel_thresholds: Record<string, string> };
		assert.deepEqual(payload.alert_channel_thresholds, {
			email: 'LOW',
			telegram: 'HIGH',
			sms: 'MODERATE'
		});
	});

	test('eine hochgesetzte Telegram-Schwelle steht unveraendert (kein Runden/Clamping) in der Payload', () => {
		const payload = buildAlarmeDeliveryPayload({
			officialWarningsEnabled: false,
			channels: { email: true, telegram: true, sms: false },
			channelThresholds: { email: 'LOW', telegram: 'HIGH', sms: 'LOW' }
		}) as { alert_channel_thresholds: { telegram: string } };
		assert.equal(
			payload.alert_channel_thresholds.telegram,
			'HIGH',
			'die vom Nutzer gewaehlte Stufe muss unveraendert in der Speicher-Payload stehen'
		);
	});
});

// ─────────────────────────────────────────────────────────────────────────
// Teil C (nach Adversary-Fix F003): "kann diese Einstellung aendern" (AC-10)
// direkt an der Logik hinter einem Klick geprueft — echte Ein-/Ausgabewerte,
// kein Quelltext-Matching.
// ─────────────────────────────────────────────────────────────────────────
describe('AC-10: applyThresholdChange() ist die tatsaechliche Klick-Logik', () => {
	test('setzt genau den geklickten Kanal auf die neue Stufe', () => {
		const before = { telegram: 'LOW', sms: 'LOW', email: 'LOW' } as const;
		const after = applyThresholdChange({ ...before }, 'telegram', 'HIGH');
		assert.equal(after.telegram, 'HIGH', 'der geklickte Kanal muss die neue Stufe zeigen');
	});

	test('laesst die beiden nicht geklickten Kanaele unveraendert', () => {
		const before = { telegram: 'MODERATE', sms: 'HIGH', email: 'LOW' } as const;
		const after = applyThresholdChange({ ...before }, 'email', 'HIGH');
		assert.equal(after.telegram, 'MODERATE', 'telegram darf sich nicht mitaendern');
		assert.equal(after.sms, 'HIGH', 'sms darf sich nicht mitaendern');
	});

	test('mutiert den uebergebenen Zustand nicht (reine Funktion)', () => {
		const before = { telegram: 'LOW', sms: 'LOW', email: 'LOW' } as const;
		const snapshot = { ...before };
		applyThresholdChange(before, 'sms', 'MODERATE');
		assert.deepEqual(before, snapshot, 'der Eingabe-Zustand darf durch den Aufruf nicht veraendert werden');
	});

	test('ein erneuter Klick auf denselben Kanal mit derselben Stufe ist ein Vorgang ohne Seiteneffekt auf andere Kanaele', () => {
		const before = { telegram: 'HIGH', sms: 'LOW', email: 'MODERATE' } as const;
		const after = applyThresholdChange({ ...before }, 'telegram', 'HIGH');
		assert.deepEqual(after, before);
	});
});
