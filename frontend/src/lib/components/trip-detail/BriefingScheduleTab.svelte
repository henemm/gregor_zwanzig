<script lang="ts">
	import { api } from '$lib/api.js';
	import { Btn } from '$lib/components/atoms';
	import EditReportConfigSection from '$lib/components/edit/EditReportConfigSection.svelte';
	import type { Trip, ReportConfig } from '$lib/types';
	import type { ChannelConfig } from './briefingChannelGating.ts';

	interface Props {
		trip: Trip;
		onTripUpdate?: (updated: Trip) => void;
	}
	let { trip, onTripUpdate }: Props = $props();

	let reportConfig = $state<ReportConfig>(
		trip.report_config ? JSON.parse(JSON.stringify(trip.report_config)) : {}
	);

	// Issue #617: Wetter-Kanäle aus display_config.channels durchreichen.
	// Cast über unknown wie in WeatherMetricsTab (#587). Default: Email+Telegram aktiv, SMS aus.
	const weatherChannels: ChannelConfig = (
		(trip.display_config as unknown as Record<string, unknown>)?.channels as ChannelConfig | undefined
	) ?? { email: true, telegram: true, sms: false };
	let saving = $state(false);
	let statusMsg = $state('');

	function makeSaveHandler() {
		return async function doSave() {
			saving = true;
			statusMsg = '';
			try {
				await api.put<Trip>(`/api/trips/${trip.id}`, { report_config: reportConfig });
				statusMsg = 'Gespeichert.';
				onTripUpdate?.({ ...trip, report_config: reportConfig });
			} catch (e: unknown) {
				const err = e as { error?: string; detail?: string };
				statusMsg = err.detail ?? err.error ?? 'Fehler beim Speichern';
			} finally {
				saving = false;
			}
		};
	}
</script>

<div class="briefing-schedule-tab" style="padding: 32px 40px 60px; max-width: 720px;">
	<EditReportConfigSection bind:reportConfig mode="edit" {weatherChannels} />

	<div style="margin-top: 24px; display: flex; align-items: center; gap: 12px;">
		<Btn
			variant="primary"
			data-testid="briefings-save"
			disabled={saving}
			onclick={makeSaveHandler()}
		>
			{saving ? 'Speichern …' : 'Briefing-Zeitplan speichern'}
		</Btn>
		{#if statusMsg}
			<span style="font-size: 13px; color: var(--g-ink-muted);">{statusMsg}</span>
		{/if}
	</div>
</div>
