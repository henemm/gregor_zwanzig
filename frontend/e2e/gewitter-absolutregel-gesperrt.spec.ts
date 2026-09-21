// E2E — #1895 Schritt 1: der Alarmregel-Editor kennt keinen Absolut-Modus mehr.
//
// Spec: docs/specs/modules/fix_1895_alarm_modus_rueckbau.md (AC-1, AC-2, AC-3, AC-5, AC-7)
//
// Diese Datei war bis #1895 der Sperr-Waechter aus #1488 Scheibe A („fuer Gewitter
// ist der Absolut-Modus gesperrt"). Sie wird hier IN PLACE zum Abwesenheits-
// Waechter umgeschrieben und behaelt ihren Dateinamen: sie steht in der
// E2E-Ratsche `ci_e2e_specs.txt` (Zeile 213) und laeuft im `e2e`-Check der
// CI-Ampel. Ein neuer Dateiname haette den Ratschen-Eintrag entwertet — „Ratsche
// leeren macht den abhaengigen Test vakuum-gruen".
//
// Gemessener Befund (docs/context/fix-1895-alarm-absolut-modus.md): der Editor
// bietet drei Modus-Karten und ein Absolut-Schwellenfeld an. Seit dem Umbau #946
// loest eine Absolut-Schwelle nie mehr einen Alarm aus, und der Go-Store schreibt
// jede Absolut-Regel bei jedem Laden und Speichern still zu kind='delta' um
// (SyncAlertRules). Die Bedienflaeche verspricht etwas, das es nicht gibt.
//
// Gemessen wird hier die `.svelte`-Verdrahtung im echten Browser. Der SSR-Harness
// (node --test) erreicht den Bearbeiten-Zustand nicht und kann darum weder das
// Verschwinden der Modus-Karten noch das Ueberleben der Kanal-Chips belegen.

import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import * as path from 'node:path';

const MOBILE = { width: 390, height: 844 };

// Modus-Karten-Locator. ModeCard.svelte:58-60 wechselte die testid je nach Auswahl
// (`mode-card-absolute` <-> `mode-card-absolute-selected`) — ein exakter Vergleich
// wuerde die ausgewaehlte Karte uebersehen und faelschlich „nicht vorhanden"
// melden. Nach dem Rueckbau darf KEINE der beiden Varianten mehr auftauchen.
function modeCard(scope: ReturnType<Page['locator']>, mode: 'absolute' | 'delta' | 'both') {
	return scope.locator(`[data-testid="mode-card-${mode}"], [data-testid="mode-card-${mode}-selected"]`);
}

// Alle Modus-Karten zusammen — faengt auch eine vierte, neu erfundene Karte.
function alleModusKarten(scope: ReturnType<Page['locator']>) {
	return scope.locator('[data-testid^="mode-card-"]');
}

// `/trips/new` bis zum Alerts-Tab durchklicken. Uebernommen aus dem bereits
// funktionierenden `issue-776-metrics-toggle.spec.ts::openNewTripZeitplan()`
// (mobiler Pfad, Progressive-Tab-Unlock) — einziger zusaetzlicher Schritt ist der
// Klick auf „Alerts". Kein Trip wird angelegt: der GPX-Upload loest nur den
// zustandslosen `POST /api/gpx/parse` aus.
async function openNewTripAlerts(page: Page) {
	await page.setViewportSize(MOBILE);
	await page.goto('/trips/new');
	await page.getByTestId('trip-new-name-input-mobile').fill('#1895 Alarmregel-Modus');
	await page.getByTestId('trip-new-date-input').fill(new Date().toISOString().slice(0, 10));

	const tabbar = page.getByTestId('tn-mobile-tabbar');
	await tabbar.getByRole('tab', { name: /Etappen/ }).click({ force: true });

	const gpx = path.resolve('./e2e/fixtures/test-trip.gpx');
	// IMMER den ersten verbleibenden offenen Datei-Input frisch aufloesen: eine
	// Etappe mit gesetztem GPX verliert ihren Input komplett aus dem DOM
	// (TripNewEditor.svelte `{#if s.gpx}`), ein fixierter Index zeigt danach ins Leere.
	const stageCount = await page.locator('.tn-mobile input[type="file"][accept=".gpx"]').count();
	for (let i = 0; i < stageCount; i++) {
		const input = page.locator('.tn-mobile input[type="file"][accept=".gpx"]').first();
		await Promise.all([
			page.waitForResponse((r) => r.url().includes('/api/gpx/parse'), { timeout: 30_000 }).catch(() => null),
			input.setInputFiles(gpx)
		]);
		await page.waitForTimeout(600);
	}

	await tabbar.getByRole('tab', { name: /Wetter/ }).click({ force: true });
	await tabbar.getByRole('tab', { name: /Zeitplan/ }).click({ force: true });
	await tabbar.getByRole('tab', { name: /Alerts/ }).click({ force: true });

	// Harter Surface-Check: ohne ihn waere jedes spaetere `toHaveCount(0)`
	// bedeutungslos (leerer DOM zaehlt auch 0). AlertRulesEditor wird sowohl im
	// .tn-desktop- als auch im .tn-mobile-Baum gemountet — daher scopen.
	const editor = page.locator('.tn-mobile').getByTestId('alert-rules-editor');
	await expect(editor).toBeVisible({ timeout: 15_000 });
	return editor;
}

// Legt eine Default-Regel an und oeffnet ihren Edit-Modus.
async function openFirstRuleEditor(page: Page, editor: ReturnType<Page['locator']>) {
	await editor.getByTestId('alert-rules-editor-add').click();
	await editor.getByTestId('alert-rule-kebab-trigger').first().click();
	await editor.getByTestId('alert-rule-edit-btn').first().click();
	const edit = editor.getByTestId('alert-rule-edit').first();
	await expect(edit).toBeVisible();
	return edit;
}

// Oeffnet den Edit-Modus einer bereits sichtbaren Regel (ohne eine neue anzulegen).
async function reopenRuleEditor(editor: ReturnType<Page['locator']>) {
	await editor.getByTestId('alert-rule-kebab-trigger').first().click();
	await editor.getByTestId('alert-rule-edit-btn').first().click();
	const edit = editor.getByTestId('alert-rule-edit').first();
	await expect(edit).toBeVisible();
	return edit;
}

test.describe('#1895 Schritt 1: Modus-Auswahl und Absolut-Feld sind zurueckgebaut', () => {
	test('Boeen: keine Modus-Karten, keine Modus-Gruppe, aber Δ-Schwelle und Zeitfenster (AC-1)', async ({ page }) => {
		const editor = await openNewTripAlerts(page);
		const edit = await openFirstRuleEditor(page, editor);

		// Positivkontrolle: die Card ist wirklich die Bearbeiten-Card der Boeen-Regel.
		// Ohne sie hiesse „keine Modus-Karte" bloss „kein DOM".
		await expect(edit.getByTestId('alert-rule-metric')).toHaveValue('wind_gust');

		// Soft, damit ein frueher Bruch die spaeteren Zusicherungen nicht ungemessen
		// laesst — „nicht ausgefuehrt" saehe im RED-Lauf aus wie „erfuellt".
		await expect.soft(alleModusKarten(edit)).toHaveCount(0);
		await expect.soft(modeCard(edit, 'absolute')).toHaveCount(0);
		await expect.soft(modeCard(edit, 'delta')).toHaveCount(0);
		await expect.soft(modeCard(edit, 'both')).toHaveCount(0);
		await expect.soft(edit.locator('[role="radiogroup"][aria-label="Alarm-Modus"]')).toHaveCount(0);
		await expect.soft(edit.getByTestId('alert-rule-delta-only-hint')).toHaveCount(0);
		// Der „Beides"-Zweig trug zwei Schwellenfelder mit eigenen testids; nach dem
		// Kollaps traegt der einzige verbleibende Zweig nur `alert-rule-threshold`.
		await expect.soft(edit.getByTestId('alert-rule-threshold-abs')).toHaveCount(0);
		await expect.soft(edit.getByTestId('alert-rule-threshold-delta')).toHaveCount(0);

		// Der Δ-Zweig BLEIBT sichtbar (Annahme 1 der Spec, vom PO freigegeben).
		await expect.soft(edit.getByTestId('alert-rule-threshold')).toHaveCount(1);
		await expect.soft(edit.getByTestId('alert-rule-threshold')).toBeVisible();
		await expect.soft(edit.getByTestId('alert-rule-delta-window')).toHaveCount(1);
		await expect.soft(edit.getByTestId('alert-rule-delta-window')).toBeVisible();

		// Speichern-Knopf traegt fest „Speichern", nie mehr „Beide Regeln speichern".
		await expect.soft(edit.getByTestId('alert-rule-save')).toHaveText('Speichern');
	});

	test('Metrik-Wechsel: auch Gewitter und Temperatur (Änderung) ohne Modus-Auswahl (AC-1)', async ({ page }) => {
		const editor = await openNewTripAlerts(page);
		const edit = await openFirstRuleEditor(page, editor);

		for (const metric of ['thunder_level', 'temperature_change']) {
			await edit.getByTestId('alert-rule-metric').selectOption(metric);
			// Anti-Vakuum je Durchlauf: die Card steht nach dem Wechsel noch, und der
			// Δ-Zweig ist gerendert. Sonst waere „keine Modus-Karte" nur „nichts da".
			await expect(edit.getByTestId('alert-rule-metric')).toHaveValue(metric);
			await expect(edit.getByTestId('alert-rule-threshold')).toHaveCount(1);

			await expect.soft(alleModusKarten(edit)).toHaveCount(0);
			await expect.soft(edit.locator('[role="radiogroup"][aria-label="Alarm-Modus"]')).toHaveCount(0);
			await expect.soft(edit.getByTestId('alert-rule-threshold-abs')).toHaveCount(0);
			await expect.soft(edit.getByTestId('alert-rule-delta-only-hint')).toHaveCount(0);
			await expect.soft(edit.getByTestId('alert-rule-delta-window')).toHaveCount(1);
		}

		// Die Stufenwoerter aus dem alten Gewitter-Absolut-Select (#1488) bleiben weg.
		await edit.getByTestId('alert-rule-metric').selectOption('thunder_level');
		await expect.soft(edit.locator('option', { hasText: /^MITTEL$/ })).toHaveCount(0);
		await expect.soft(edit.locator('option', { hasText: /^HOCH$/ })).toHaveCount(0);
	});

	test('Absolut-Schwellenfeld existiert fuer KEINE Metrik (AC-5)', async ({ page }) => {
		const editor = await openNewTripAlerts(page);
		const edit = await openFirstRuleEditor(page, editor);

		// Metrik-Werte aus dem DOM lesen, nicht abschreiben: eine abgeschriebene
		// Liste wuerde beim naechsten neuen Select-Eintrag still veralten.
		const werte = await edit
			.getByTestId('alert-rule-metric')
			.locator('option')
			.evaluateAll((opts) => opts.map((o) => (o as HTMLOptionElement).value));
		// Anti-Vakuum: eine leere Optionsliste wuerde die Schleife ueberspringen und
		// den Test gruen lassen, ohne eine einzige Metrik gemessen zu haben.
		expect(werte.length).toBeGreaterThanOrEqual(9);

		for (const wert of werte) {
			await edit.getByTestId('alert-rule-metric').selectOption(wert);
			await expect(edit.getByTestId('alert-rule-metric')).toHaveValue(wert);
			// Positivkontrolle je Metrik: die Card ist gerendert …
			await expect.soft(edit.getByTestId('alert-rule-threshold')).toHaveCount(1);
			// … und traegt trotzdem kein Absolut-Feld.
			await expect.soft(edit.getByTestId('alert-rule-threshold-abs')).toHaveCount(0);
			// Die Modus-Auswahl ist die EINZIGE Tuer zum Absolut-Feld: bis #1895 war
			// `alert-rule-threshold-abs` nur im Modus „Beides" im DOM, im Modus
			// „Absolut" dagegen nie. Ohne diese Zeile waere der ganze Testfall
			// vakuum-gruen — er lief am 2026-09-21 gegen den unveraenderten Stand
			// gruen durch, obwohl jede Metrik noch drei Modus-Karten anbot und der
			// Nutzer das Absolut-Feld mit einem Klick erreicht haette. Solange eine
			// Metrik Modus-Karten zeigt, ist „kein Absolut-Feld" nur eine Aussage
			// ueber den gerade eingestellten Modus, nicht ueber die Metrik.
			await expect.soft(alleModusKarten(edit)).toHaveCount(0);
		}
	});

	test('Neue Regel startet als Aenderungsregel mit Δ 20 / 6h (AC-7)', async ({ page }) => {
		const editor = await openNewTripAlerts(page);
		await editor.getByTestId('alert-rules-editor-add').click();

		const row = editor.getByTestId('alert-rule-row').first();
		await expect(row).toBeVisible();
		await expect.soft(row).toContainText('Δ');
		await expect.soft(row).not.toContainText('Abs');

		const edit = await reopenRuleEditor(editor);
		await expect.soft(edit.getByTestId('alert-rule-threshold')).toHaveValue('20');
		await expect.soft(edit.getByTestId('alert-rule-delta-window')).toHaveValue('6h');
	});

	test('Speichern erhaelt genau eine Regel — keine geht verloren, keine kommt hinzu (AC-2)', async ({ page }) => {
		const editor = await openNewTripAlerts(page);
		const edit = await openFirstRuleEditor(page, editor);

		await edit.getByTestId('alert-rule-metric').selectOption('precipitation_sum');

		// `enabled` wird hier bewusst UMGESCHALTET, nicht nur mitgelesen. An der
		// reinen Funktion expandRules() ist das Durchreichen zwar geprueft, die
		// Zusicherung WIRKT aber in saveEdit() der `.svelte`-Komponente: wer dort
		// `enabled: true` erzwaenge, wuerde von keinem Funktionstest gefangen
		// (Adversary-Mutation M17). Darum laeuft der Nachweis ueber die Bedien-
		// flaeche: abwaehlen -> speichern -> die Ansichtszeile muss inaktiv sein.
		const editAktiv = edit.getByRole('checkbox');
		await expect(editAktiv).toBeChecked();
		await editAktiv.click();
		await expect(editAktiv).not.toBeChecked();

		// F001 — die Regel-`id` wird hier MITGEMESSEN, ohne sie je zu lesen:
		// AlertRulesEditor.svelte:50 schluesselt die Liste mit
		// `{#each rules as rule, i (rule.id)}`. Ein keyed each zerstoert den
		// `<li>`-Block, sobald sich sein Key aendert, und baut einen neuen auf.
		// Der hier VOR dem Speichern gegriffene Knoten bleibt also nur dann mit
		// dem Dokument verbunden, wenn die `id` das Speichern unveraendert
		// ueberlebt. Die Zusicherung steht am Ende dieses Falls.
		const liVorSpeichern = await editor.locator('.rules-list > li').first().elementHandle();

		await edit.getByTestId('alert-rule-save').click();

		// Genau eine Zeile: nicht null (Regel verloren -> das Pruef-Gate
		// has_active_rules koennte kippen) und nicht zwei (das alte „Beides"
		// erzeugte ein Regel-Paar).
		await expect(editor.getByTestId('alert-rule-row')).toHaveCount(1);
		const row = editor.getByTestId('alert-rule-row').first();
		await expect.soft(row).toContainText('Niederschlag');
		await expect.soft(row).toContainText('Δ');
		// HART, nicht soft: das ist die einzige Messung von `enabled` am
		// Speicherweg. Ein erzwungenes `enabled: true` in saveEdit() muss hier
		// unmissverstaendlich rot werden.
		await expect(row.getByRole('checkbox')).not.toBeChecked();
		// Keine Paar-Markierung mehr, weil expandRules() nie mehr zwei Regeln liefert.
		await expect.soft(editor.getByTestId('pair-indicator')).toHaveCount(0);

		// HART und bewusst als LETZTE Zusicherung (alle vorherigen Awaits haben
		// den Re-Render abgewartet): `isConnected === false` heisst, dass der
		// keyed-each-Block neu aufgebaut wurde — und das passiert genau dann,
		// wenn saveEdit() eine NEUE `id` vergibt (Adversary-Mutation M16).
		// `?.` statt `!`: ein fehlender Handle liefert `undefined` und faellt
		// ebenfalls durch, statt still gruen zu bleiben.
		expect(await liVorSpeichern?.evaluate((n) => n.isConnected)).toBe(true);
	});

	// Dieser Fall ist ABSICHTLICH schon vor dem Umbau gruen und muss es danach
	// bleiben: AC-3 sichert nicht eine neue Faehigkeit zu, sondern das Ueberleben
	// einer vorhandenen. Sein Biss wird darum nicht ueber RED gemessen, sondern in
	// der Mutations-Gegenprobe (AC-6): faellt der Chip-Block aus der Edit-Card,
	// muss dieser Fall rot werden. Gemessen am 2026-09-21: gruen gegen den
	// unveraenderten Stand.
	test('Kanal-Chips ueberleben den Rueckbau und schalten weiterhin um (AC-3)', async ({ page }) => {
		const editor = await openNewTripAlerts(page);
		const edit = await openFirstRuleEditor(page, editor);

		// Standardkanaele in `/trips/new` sind E-Mail und Telegram (SMS ist aus).
		const email = edit.getByTestId('alert-rule-channel-email');
		const telegram = edit.getByTestId('alert-rule-channel-telegram');
		await expect(email).toBeVisible();
		await expect(telegram).toBeVisible();
		await expect(edit.getByTestId('alert-rule-channel-sms')).toHaveCount(0);
		await expect(email).toHaveAttribute('aria-pressed', 'true');
		await expect(telegram).toHaveAttribute('aria-pressed', 'true');

		// Umschalten erreicht toggleAlertChannel(): Telegram ab, E-Mail bleibt.
		await telegram.click();
		await expect(telegram).toHaveAttribute('aria-pressed', 'false');
		await expect(email).toHaveAttribute('aria-pressed', 'true');

		await edit.getByTestId('alert-rule-save').click();

		// Roundtrip IM EDITOR (kein API-Aufruf): die Ansichtszeile zeigt nur E-Mail.
		const row = editor.getByTestId('alert-rule-row').first();
		await expect(row).toBeVisible();

		// F005 — Gegenrichtung zur `enabled`-Messung des AC-2-Falls: dort wird der
		// Haken ABGEWAEHLT und danach „nicht gesetzt" erwartet, was nur ein
		// erzwungenes `enabled: true` faengt. Hier bleibt der Haken UNBERUEHRT
		// (geklickt werden nur Kanal-Chips), also muss er das Speichern gesetzt
		// ueberleben. Ein in saveEdit() erzwungenes `enabled: false` wuerde jede
		// Regel still deaktivieren und nur an dieser Stelle rot.
		// (Damit bewacht dieser Fall mehr als der Kopfkommentar oben andeutet.)
		await expect(row.getByRole('checkbox')).toBeChecked();

		await expect.soft(row.locator('.channel-chip')).toHaveText(['E-Mail']);

		// Und erneut geoeffnet steht Telegram weiter auf „aus".
		const wieder = await reopenRuleEditor(editor);
		await expect.soft(wieder.getByTestId('alert-rule-channel-email')).toHaveAttribute('aria-pressed', 'true');
		await expect.soft(wieder.getByTestId('alert-rule-channel-telegram')).toHaveAttribute('aria-pressed', 'false');
	});
});
