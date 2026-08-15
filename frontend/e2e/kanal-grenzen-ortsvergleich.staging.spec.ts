// E2E (Staging) — Issue #1719 Scheibe 3, AC-6: der Ortsvergleich nennt in
// drei geteilten Bausteinen ebenfalls die echte Zeichengrenze, keine
// Wertung — Versand-Reiter (VTBriefingChannels), Alarme-Reiter
// (AlertChannelPicker), SMS-Vorschau (CompareSmsPreview).
//
// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md AC-6.
//   Zuordnungstabelle: Commit 3da43cad (Bündel `kanal-grenzen-ortsvergleich`).
// Kontext: docs/context/fix-1719-s3-aus-ist-ein-zustand.md Abschnitt 10.2/10.3
//   ("LTCapNote erreicht den Ortsvergleich nicht mehr" — seit #1360 ist der
//   Layout-Reiter des Ortsvergleichs aufgelöst; die drei hier geprüften
//   Bausteine sind die EINZIGE verbliebene Verbindung).
//
// 🔴 Spec-Korrektur 2 (Commit 6403c57a, 2026-08-11): es gibt DREI
// SMS-Zeichengrenzen, nicht zwei — je Ausgabeweg eine eigene, alle drei
// gemessen, keine davon pauschal falsch:
//   Trip-Briefing:       160  (trip_report.py:446)                — anderes Bündel
//   Vergleichs-Briefing: 153  (channel_layout.py:48, GSM-7/UDH)   — VTBriefingChannels(vergleich)/CompareSmsPreview
//   Alarm:               140  (alert/render.py:621, Vorgabewert;
//                               notification_service.py:1318 überschreibt ihn NICHT) — AlertChannelPicker
//
// Gemessene, heute LEBENDIGE Fundstellen:
//   - VTBriefingChannels.svelte:120 (SUB.sms = "Layout · flach, ≤ 140 Z.")
//     UND :113/:114 (CTX_LEAD "SMS läuft flach"/"SMS wird flach" — Wertung).
//     "140" ist HIER falsch (Vergleichs-Briefing rechnet 153).
//   - CompareSmsPreview.svelte:15 (COMPARE_SMS_MAX = 140, literal im
//     Zeichenzähler-Text "{count}/{COMPARE_SMS_MAX} Zeichen" sichtbar).
//     "140" ist auch HIER falsch (derselbe Vergleichs-Briefing-Pfad, 153).
//   - AlertChannelPicker.svelte:51 (CHANNEL_SUB.sms = "sofort · ≤ 140 Z.") —
//     "140" ist HIER KORREKT (Alarm-Pfad, alert/render.py:621) und darf NICHT
//     geändert werden. In der aktuell verdrahteten AlarmeTab-Instanz ist der
//     Text-Zweig durch `thresholds` (immer gesetzt) verdeckt — der Test prüft
//     deshalb, dass 140 IRGENDWO in der SMS-Zeile auftaucht, nicht die tote
//     CHANNEL_SUB-Fundstelle selbst. Zu prüfen ist allein, dass keine Wertung
//     dazukommt — NICHT, dass die Zahl wechselt.
//
// SCHREIBT NUR — wird in dieser RED-Phase NICHT ausgeführt (Testauflage PO,
// "Das ist KRITISCH!!!!!" — der Lauf gehört in die GREEN-/Verifikationsphase).
//
// Vorbild: compare-outlook-metric-selection.staging.spec.ts (Testaufbau
// Preset/Location, compare-detail-tab-*-Konvention).
//
// Ausführen (gegen Staging, aus frontend/, NACH GREEN):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=e2e/playwright.kanal-grenzen-ortsvergleich.staging.config.ts

import { test, expect, type Page } from '@playwright/test';
import { createTestLocation } from './helpers';

let createdPresetIds: string[] = [];
let createdLocationIds: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of createdPresetIds) {
		await page.request.delete(`/api/compare/presets/${id}`).catch(() => {});
	}
	createdPresetIds = [];
	for (const id of createdLocationIds) {
		await page.request.delete(`/api/locations/${id}`).catch(() => {});
	}
	createdLocationIds = [];
});

async function createComparePreset(page: Page, suffix: number): Promise<string> {
	const loc = await createTestLocation(page.request, {
		name: `1719-s3-ac6-${suffix}`,
		lat: 47.0 + Math.random() * 0.5,
		lon: 11.0 + Math.random() * 0.5
	});
	createdLocationIds.push(loc.id);

	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: `1719-s3-ac6-${suffix}`,
			location_ids: [loc.id],
			schedule: 'manual',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 18,
			empfaenger: ['urlauber@example.com'],
			// Staging-Fund (2026-08-11): `empfaenger` ist seit #1452 inert fuer die
			// Kanal-Anzeige — presetChannels() (subscriptionHelpers.ts:245-251)
			// leitet SMS AUSSCHLIESSLICH aus `send_sms` ab. Ohne dieses Feld zeigt
			// die Vorschau `compare-preview-channel-not-configured` statt
			// `compare-preview-sms`, obwohl das Backend (POST /api/preview/compare/
			// {id}) bereits einen echten, nicht-leeren SMS-Text liefert — verifiziert
			// per direktem API-Aufruf gegen Staging mit genau diesem Preset-Payload.
			send_sms: true
		}
	});
	expect(res.ok(), `Preset-Anlage fehlgeschlagen: ${res.status()}`).toBeTruthy();
	const body = await res.json();
	createdPresetIds.push(body.id);
	return body.id as string;
}

async function openCompareDetail(page: Page, id: string) {
	await page.goto(`/compare/${id}`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 15_000 });
	await page.waitForLoadState('networkidle');
}

test.describe('Issue #1719 S3 AC-6: Ortsvergleich nennt überall die echte SMS-Zeichengrenze des jeweiligen Ausgabewegs (153 Briefing / 140 Alarm), keine Wertung', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test('Versand-Reiter (VTBriefingChannels): SMS-Zeile nennt 153, nicht 140, keine "läuft/wird flach"-Wertung', async ({
		page
	}) => {
		const id = await createComparePreset(page, Date.now());
		await openCompareDetail(page, id);
		await page.getByTestId('compare-detail-tab-versand').click();
		const panel = page.getByTestId('compare-detail-panel-versand');
		await expect(panel).toBeVisible({ timeout: 10_000 });

		// Der Wrapper-Block der SMS-Zeile (Checkbox + Status + Hinweistext).
		const smsBlock = panel.getByTestId('compare-step5-channel-sms').locator('xpath=..');
		await expect(
			smsBlock,
			'AC-6 FAIL: die SMS-Zeile im Versand-Reiter des Ortsvergleichs muss die echte Zeichengrenze (153) nennen'
		).toContainText('153');
		await expect(
			smsBlock,
			'AC-6 FAIL: "140" ist die falsche Zeichengrenze (das ist der ungenutzte Signal-Wert, ' +
				'der Vergleichspfad rechnet 153 — channel_layout.py:45-54)'
		).not.toContainText('140');

		const fullPanelText = (await panel.innerText()).toLowerCase();
		expect(
			fullPanelText.includes('läuft flach') || fullPanelText.includes('wird flach'),
			'AC-6 FAIL: der Versand-Reiter darf nicht behaupten, SMS "laufe"/"werde flach" (Wertung/Unwahrheit)'
		).toBe(false);
	});

	// AC-6, Alarm-Anteil. Die Spec verlangt hier ausdruecklich NUR, dass die
	// Wertung verschwindet und keine FREMDE Zahl auftaucht — nicht, dass eine
	// Zahl sichtbar ist.
	//
	// 🔴 Staging-Messung 2026-08-12: die gewaehlte Zeile zeigt
	// "SMS — gering mittel hoch", also die Stufen-Auswahl. Der statische Text
	// mit "sofort · ≤ 140 Z." (AlertChannelPicker.svelte:51, CHANNEL_SUB.sms)
	// ist im verdrahteten Zweig TOTES MARKUP: AlarmeTab.svelte:355 uebergibt
	// `thresholds` immer (Typ nicht optional), also wird nie der Textzweig
	// gerendert. Eine Zusicherung auf "140 muss sichtbar sein" wuerde daher
	// neue Oberflaeche erzwingen, die niemand bestellt hat — das gehoert in den
	// Alarm-Umbau (#1701/#1745), nicht in diese Scheibe.
	//
	// Die 140 bleibt in der Konstante trotzdem RICHTIG (alert/render.py:621,
	// von notification_service.py:1318 nicht ueberschrieben) und darf nicht auf
	// den Briefing-Wert 153 gezogen werden — genau das bewacht die zweite
	// Zusicherung unten.
	test('Alarme-Reiter (AlertChannelPicker): SMS-Zeile ohne Wertung und ohne die fremde Briefing-Zahl 153', async ({
		page
	}) => {
		const id = await createComparePreset(page, Date.now() + 1);
		await openCompareDetail(page, id);
		await page.getByTestId('compare-detail-tab-alarme').click();
		const panel = page.getByTestId('compare-detail-panel-alarme');
		await expect(panel).toBeVisible({ timeout: 10_000 });

		const smsRow = panel.getByTestId('alert-channel-row-sms');
		await expect(smsRow).toBeVisible();

		await expect(
			smsRow,
			'AC-6 FAIL: "153" ist die Briefing-Zeichengrenze und im Alarm-Kontext falsch — ' +
				'der Alarm-Pfad hat seine eigene Grenze (140, alert/render.py:621)'
		).not.toContainText('153');

		const rowText = (await smsRow.innerText()).toLowerCase();
		for (const phrase of ['läuft flach', 'wird flach', 'entscheidungskritisch', 'nur das wesentliche']) {
			expect(
				rowText.includes(phrase),
				`AC-6 FAIL: die SMS-Zeile im Alarme-Reiter enthaelt die Wertung "${phrase}"`
			).toBe(false);
		}
	});

	test('SMS-Vorschau (CompareSmsPreview): Zeichenzähler rechnet gegen 153, nicht 140', async ({ page }) => {
		const id = await createComparePreset(page, Date.now() + 2);
		// Staging-Fund (2026-08-11): `getByTestId(...)` ohne `:visible`-Filter +
		// Tab-Wechsel per Klick (ohne vorherige `?tab=vorschau`-Navigation) traf
		// den SMS-Kanal-Umschalter nicht zuverlässig — "compare-preview-sms"
		// blieb unauffindbar, obwohl das Backend (verifiziert per direktem
		// API-Aufruf gegen denselben Preset-Payload) einen echten, nicht-leeren
		// SMS-Text lieferte. Umgestellt auf das bewährte Muster aus
		// compare-mobile-vervollstaendigung.spec.ts (Issue #1256 Scheibe 8b
		// AC-1, exakt dieselbe Kanal-Umschalter-Interaktion, dort stabil grün):
		// Tab per URL-Query vorwählen, zusätzlich per Klick bestätigen,
		// durchgängig `:visible`-gefilterte Locators, SMS-Button-Sichtbarkeit
		// VOR dem Klick abwarten.
		await page.goto(`/compare/${id}?tab=vorschau`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-vorschau"]:visible').click();
		const panel = page.locator('[data-testid="compare-detail-panel-vorschau"]:visible');
		await expect(panel).toBeVisible({ timeout: 10_000 });

		const smsBtn = panel.getByRole('button', { name: 'SMS' });
		await expect(smsBtn).toBeVisible({ timeout: 10_000 });
		await smsBtn.click();
		const smsPreview = panel.locator('[data-testid="compare-preview-sms"]');
		await expect(smsPreview).toBeVisible({ timeout: 15_000 });
		await expect(
			smsPreview,
			'AC-6 FAIL: die SMS-Vorschau muss gegen 153 Zeichen zaehlen (COMPARE_SMS_MAX ist heute ' +
				'faelschlich 140, CompareSmsPreview.svelte:15)'
		).toContainText('153');
		await expect(smsPreview, 'AC-6 FAIL: die SMS-Vorschau darf nicht gegen 140 Zeichen zaehlen').not.toContainText(
			'/140 Zeichen'
		);
	});
});
