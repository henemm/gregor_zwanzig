<script lang="ts">
	// Issue #345 (Wetter-Editor-Konsolidierung) — read-only Wetter-Profil-Karte
	// in der Trip-Bearbeiten-Maske (AC-1, AC-5).
	// Design: docs/design-requests/issue_345_assets/screen-weather-consolidation.jsx
	//         (Funktion WEKEditFormDrop).
	//
	// Zeigt Profilname + Mono-Zähler (Spalten · Detail · aktiv) und verlinkt in
	// den einzigen Bearbeitungs-Ort: Trip-Detail → Tab „Wetter-Briefing"
	// (/trips/{id}?tab=wetter-metriken, #2287). KEINE bearbeitbaren Toggles (AP-013).
	import { goto } from '$app/navigation';
	import { Btn, Eyebrow } from '$lib/components/atoms';
	import { summarizeTripWeather, type DisplayConfigLike } from './weatherSummary.js';
	import { t } from '$lib/i18n';

	interface Props {
		displayConfig: DisplayConfigLike | undefined | null;
		tripId: string;
	}
	let { displayConfig, tripId }: Props = $props();

	const summary = $derived(summarizeTripWeather(displayConfig));
	const profileLabel = $derived(
		summary.presetName ?? (summary.aktiv > 0 ? $t('trip.wetter.eigene_auswahl') : '—'),
	);

	// Factory Pattern für den Navigations-Handler (Safari-Closure-Schutz, CLAUDE.md).
	function makeOpenWeatherTab() {
		return function openWeatherTab() {
			goto(`/trips/${tripId}?tab=wetter-metriken`);
		};
	}
	const onOpenWeatherTab = makeOpenWeatherTab();
</script>

<div data-testid="weather-summary-card" class="ws-card">
	<div class="ws-head">
		<div class="ws-info">
			<Eyebrow>{$t('trip.wetter.profil')}</Eyebrow>
			<div class="ws-title-row">
				<span class="ws-profile">{profileLabel}</span>
				<span class="mono ws-counts" data-testid="weather-summary-counts">
					{$t('trip.wetter.zaehler', { spalten: summary.spalten, detail: summary.detail, aktiv: summary.aktiv })}
				</span>
			</div>
		</div>
		<Btn variant="ghost" onclick={onOpenWeatherTab} data-testid="weather-edit-link">
			{$t('trip.wetter.bearbeiten')}
		</Btn>
	</div>
	<div class="ws-note">
		<strong>{$t('trip.wetter.nur_lesen')}</strong>
		{$t('trip.wetter.hinweis')}
	</div>
</div>

<style>
	.ws-card {
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-sm);
		overflow: hidden;
	}
	.ws-head {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: var(--g-s-4);
		align-items: center;
		padding: var(--g-s-4) var(--g-s-5);
	}
	.ws-info {
		min-width: 0;
	}
	.ws-title-row {
		display: flex;
		align-items: baseline;
		flex-wrap: wrap;
		gap: var(--g-s-3);
		margin-top: var(--g-s-1);
	}
	.ws-profile {
		font-size: var(--g-text-lg);
		font-weight: 600;
		color: var(--g-ink);
	}
	.ws-counts {
		font-size: var(--g-text-xs);
		color: var(--g-ink-3);
		letter-spacing: 0.04em;
	}
	.ws-note {
		padding: var(--g-s-2) var(--g-s-5);
		border-top: 1px solid var(--g-ink-faint);
		background: var(--g-surface-2);
		font-size: var(--g-text-sm);
		color: var(--g-ink-3);
		line-height: 1.5;
	}
	.ws-note strong {
		color: var(--g-ink-2);
	}
	@media (max-width: 640px) {
		.ws-head {
			grid-template-columns: 1fr;
			gap: var(--g-s-3);
		}
	}
</style>
