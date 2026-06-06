<script lang="ts">
	import { SectionH, Card, Btn, Eyebrow } from '$lib/components/atoms';
	import FullProfile from './FullProfile.svelte';
	import TripStageRow from './TripStageRow.svelte';
	import MetricsPreview from './MetricsPreview.svelte';
	import ReportLine from './ReportLine.svelte';
	import ChannelDot from './ChannelDot.svelte';
	import type { Trip } from '$lib/types';

	interface Props {
		trip: Trip;
		onJump?: (tab: string) => void;
	}
	let { trip, onJump }: Props = $props();

	let selectedStageId = $state<string | null>(trip.stages?.[0]?.id ?? null);

	function makeJumpHandler(tab: string) {
		return function doJump() {
			onJump?.(tab);
		};
	}

	function makeStageSelectHandler(id: string) {
		return function doSelect() {
			selectedStageId = id;
		};
	}
</script>

<div
	data-testid="hub-overview"
	style="
		position: relative;
		padding: 32px 40px 60px;
		display: grid;
		grid-template-columns: 1fr 380px;
		gap: 32px;
		max-width: 1480px;
	"
>
	<!-- Left column -->
	<div>
		<SectionH eyebrow="Etappen" title="Reihenfolge & Profil">
			{#snippet right()}
				<Btn variant="ghost" size="sm" onclick={makeJumpHandler('etappen')}>Im Editor öffnen →</Btn>
			{/snippet}
		</SectionH>

		<Card padding={20}>
			<FullProfile {trip} {selectedStageId} onSelectStage={(id) => (selectedStageId = id)} />
		</Card>

		{#each trip.stages ?? [] as stage, i}
			<TripStageRow
				{stage}
				index={i}
				active={stage.id === selectedStageId}
				onclick={makeStageSelectHandler(stage.id)}
			/>
		{/each}

		<div style="margin-top: 32px;">
			<SectionH eyebrow="Wetter-Metriken" title="Aktive Metriken">
				{#snippet right()}
					<Btn variant="ghost" size="sm" onclick={makeJumpHandler('weather')}>Bearbeiten →</Btn>
				{/snippet}
			</SectionH>

			<MetricsPreview {trip} />
		</div>
	</div>

	<!-- Right column -->
	<div style="display: flex; flex-direction: column; gap: 20px;">
		<Card padding={18}>
			<Eyebrow style="margin-bottom: 10px;">Briefings laufen</Eyebrow>
			<ReportLine kind="morning" time="06:00" channels={['email', 'telegram']} active />
			<ReportLine kind="evening" time="18:00" channels={['email']} active />
			<ReportLine kind="alert" time="bei Δ" channels={['telegram']} active alert />
			<div style="margin-top: 12px;">
				<Btn variant="ghost" size="sm" onclick={makeJumpHandler('briefings')}>Zeitplan bearbeiten →</Btn>
			</div>
		</Card>

		<Card padding={18}>
			<Eyebrow style="margin-bottom: 10px;">Alerts (letzte 7 Tage)</Eyebrow>
			<p style="font-size: 13px; color: var(--g-ink-2); margin: 0 0 12px;">Keine aktuellen Alerts.</p>
			<Btn variant="ghost" size="sm" onclick={makeJumpHandler('alerts')}>Alle Alerts →</Btn>
		</Card>

		<Card padding={18} style="background: var(--g-card-alt);">
			<Eyebrow style="margin-bottom: 10px;">Vorschau</Eyebrow>
			<p style="font-size: 13px; color: var(--g-ink-2); margin: 0 0 12px;">Wie sieht das nächste Briefing aus?</p>
			<Btn variant="primary" size="sm" onclick={makeJumpHandler('preview')}>Vorschau öffnen</Btn>
		</Card>
	</div>
</div>
