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
	// Issue #736: Mutable state (nicht const) damit Auto-Save-Aktualisierungen sichtbar werden.
	// Cast über unknown wie in WeatherMetricsTab (#587). Default: Email+Telegram aktiv, SMS aus.
	let weatherChannels = $state<ChannelConfig>(
		((trip.display_config as unknown as Record<string, unknown>)?.channels as ChannelConfig | undefined)
		?? { email: true, telegram: true, sms: false }
	);
	let saving = $state(false);
	let statusMsg = $state('');

	// Issue #736: Auto-Save bei Kanal-Toggle — display_config.channels sofort persistieren.
	async function handleChannelChange(channel: 'email' | 'telegram' | 'sms', value: boolean) {
		weatherChannels = { ...weatherChannels, [channel]: value };
		const updatedDisplayConfig = {
			...(trip.display_config as unknown as Record<string, unknown> ?? {}),
			channels: { ...weatherChannels },
		};
		try {
			await api.put(`/api/trips/${trip.id}`, { display_config: updatedDisplayConfig });
			onTripUpdate?.({ ...trip, display_config: updatedDisplayConfig as Trip['display_config'] });
		} catch (e: unknown) {
			console.error(e);
		}
	}

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
	<!-- Issue #736: weatherChannels NICHT übergeben (kein Gating mehr im Versand-Reiter).
	     Alle 3 Kanäle sind immer sichtbar; Initialisierung über reportConfig.send_*. -->
	<EditReportConfigSection bind:reportConfig mode="edit" showMailContent={false} onChannelChange={handleChannelChange} />

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
