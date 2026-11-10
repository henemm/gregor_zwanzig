// E2E — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter): „−“ und „Nicht im Briefing“ (AC-19), beide Auswahl-Quellen (AC-37),
// Orts-Briefing ohne active_metrics (AC-39).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich), ausser AC-39 (nur vergleich).
//
//   AC-19 — „−“ an Wind: Zeile weg, Picker „1 Abweichung“, Abo ohne Wind in metrics[]/active_metrics;
//           „+ Wind“: Zeile wieder da (hinten angehaengt), Meldung, Picker „unverändert“.
//   AC-37 — nach jedem Speichern: Auswahlliste = aus Vorlage + ampel aufgeloeste aktive Menge
//           (ampel.metrics.<id>.enabled nur bei Abweichung).
//   AC-39 — Orts-Briefing ohne Schluessel active_metrics: Auswahl aus der aufgeloesten Ampel, kein Fehler,
//           keine leere Auswahl; erstes Speichern schreibt active_metrics vollstaendig.
//
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts s3a2794-teil3-nicht-im-briefing

import { test, expect } from '@playwright/test';
import { HUB_KINDS, type HubKind } from './helpers';
import {
	DESKTOP, WT, abweichungen, aktiveDerVorlage, auswahlImStand, metriken, oeffneWetter, seedWetter, stand, vorlagen, warteAufSpeichern, type Json
} from './s3a2794-teil3.helpers';

/** Aktive Menge aus Vorlage + gespeicherter Abweichungsmenge (enabled), wie resolve_ampel. */
function aufgeloesteAuswahl(vorlage: Json, ampel: Json): string[] {
	const an = new Set(aktiveDerVorlage(vorlage));
	for (const [id, e] of Object.entries((ampel?.metrics ?? {}) as Record<string, Json>)) {
		if (e.enabled === true) an.add(id);
		if (e.enabled === false) an.delete(id);
	}
	return [...an].sort();
}

/** Reihenfolge der Auswahl im Abo (Trip: metrics[] enabled, Vergleich: active_metrics, eindeutig). */
function reihenfolge(kind: HubKind, s: Json): string[] {
	const dc = s.display_config ?? {};
	const ids = kind === 'route' ? (dc.metrics as Json[]).filter((m) => m.enabled !== false).map((m) => m.metric_id) : (dc.active_metrics as Json[]).map((m) => m.metric_id);
	return [...new Set(ids)];
}

for (const kind of HUB_KINDS) {
	test(`AC-19/AC-37 (${kind}): „−“ an Wind und „+ Wind“ — Zeilen, Zaehler, Meldung, beide Quellen konsistent`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'alpen-trekking' });
		try {
			const v = (await vorlagen(page.request))['alpen-trekking'];
			const kat = await metriken(page.request);
			const reiter = await oeffneWetter(page, kind, hub.id);

			let speichern = warteAufSpeichern(page, kind, hub.id);
			await reiter.getByTestId(WT.entfernen('wind')).click();
			await expect(reiter.getByTestId(WT.zeile('wind'))).toHaveCount(0);
			expect(await abweichungen(reiter)).toBe(1);
			await expect(reiter.getByTestId(WT.nichtImBriefing)).toContainText('Nicht im Briefing');
			await speichern;
			let s = await stand(page.request, kind, hub.id);
			expect(auswahlImStand(kind, s), 'AC-19: Wind nach „−“ noch in der Auswahl-Quelle').not.toContain('wind');
			expect(s.display_config.ampel.metrics.wind).toEqual({ enabled: false });
			expect(auswahlImStand(kind, s), 'AC-37: Auswahlliste ≠ aufgeloeste Ampel').toEqual(aufgeloesteAuswahl(v.ampel, s.display_config.ampel));

			speichern = warteAufSpeichern(page, kind, hub.id);
			await reiter.getByTestId(WT.plus('wind')).click();
			await expect(reiter.getByTestId(WT.zeile('wind'))).toBeVisible();
			await expect(reiter.getByTestId(WT.hinzuMeldung)).toHaveText(
				`${kat.wind.label} ist jetzt im Briefing und steht in allen Listen unter ‚Inhalt je Kanal und Fläche‘. Dort stellst du Roh oder Einfach ein.`
			);
			await expect(reiter.getByTestId(WT.pickerStatus)).toHaveText('unverändert');
			await speichern;
			s = await stand(page.request, kind, hub.id);
			expect(auswahlImStand(kind, s)).toContain('wind');
			const folge = reihenfolge(kind, s);
			expect(folge[folge.length - 1], 'AC-19: Wind nicht hinten angehaengt').toBe('wind');
			expect(s.display_config.ampel.metrics?.wind, 'AC-37: enabled bleibt als Abweichung stehen').toBeUndefined();
			expect(auswahlImStand(kind, s)).toEqual(aufgeloesteAuswahl(v.ampel, s.display_config.ampel));
		} finally {
			await hub.aufraeumen();
		}
	});
}

test('AC-39 (vergleich): Orts-Briefing ohne active_metrics zeigt die Auswahl der Ampel, erstes Speichern schreibt sie vollstaendig', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	const kind: HubKind = 'vergleich';
	const hub = await seedWetter(page.request, kind, { vorlageId: 'allgemein', ohneActiveMetrics: true });
	try {
		const v = (await vorlagen(page.request)).allgemein;
		const vorher = await stand(page.request, kind, hub.id);
		expect('active_metrics' in (vorher.display_config ?? {}), 'Messaufbau: active_metrics vorhanden').toBe(false);
		const reiter = await oeffneWetter(page, kind, hub.id);
		await expect(reiter.getByTestId(WT.fehler)).toHaveCount(0);
		for (const id of aktiveDerVorlage(v)) await expect(reiter.getByTestId(WT.zeile(id)), `AC-39: ${id} fehlt`).toBeVisible();
		await expect(reiter.getByTestId(WT.pickerStatus)).toHaveText('unverändert');

		const speichern = warteAufSpeichern(page, kind, hub.id);
		await reiter.getByTestId(WT.zeile('gust')).getByTestId(WT.alarmAbStufe('gust', 'red')).click();
		await speichern;
		const s = await stand(page.request, kind, hub.id);
		expect(auswahlImStand(kind, s), 'AC-39: active_metrics nicht vollstaendig geschrieben').toEqual([...aktiveDerVorlage(v)].sort());
	} finally {
		await hub.aufraeumen();
	}
});
