<script lang="ts">
	// Issue #578 — HomeHeroTrip-Organism.
	// Kanonische Quelle: screen-home.jsx::HomeHeroTrip
	//
	// Hero-Karte für einen aktiven Trip (Startseite-Cockpit).

	import { Card, Pill, Dot, Eyebrow } from '$lib/components/atoms';

	interface Channel {
		kind: string;
	}

	interface Trip {
		shortName?: string;
		name?: string;
		totalKm?: number;
		channels?: Channel[];
	}

	interface Props {
		trip: Trip;
		dayCurrent: number;
		dayTotal: number;
		channels?: Channel[];
		class?: string;
	}

	let { trip, dayCurrent, dayTotal, channels, class: className = '' }: Props = $props();

	const pct = $derived(dayTotal > 0 ? (dayCurrent / dayTotal) * 100 : 0);
	const tripChannels = $derived(channels ?? trip.channels ?? []);
	const tripName = $derived(trip.shortName ?? trip.name ?? '');
</script>

<Card padding={0} style="overflow: hidden; border-left: 3px solid var(--g-accent);" class={className}>
	<div style:padding="22px 26px">
		<!-- Pills -->
		<div style:display="flex" style:align-items="center" style:gap="10px" style:margin-bottom="12px" style:flex-wrap="wrap">
			<Pill tone="accent"><Dot tone="bad" size={6} /> Live · Tag {dayCurrent} von {dayTotal}</Pill>
			<Pill tone="ghost">Profil</Pill>
		</div>

		<!-- Titel -->
		<div style:font-size="34px" style:font-weight="600" style:letter-spacing="-0.02em" style:line-height="1.05" style:margin-bottom="6px">
			{tripName}
		</div>

		<!-- Subtitel -->
		{#if trip.totalKm != null}
			<div style:font-size="15px" style:color="var(--g-ink-2)" style:margin-bottom="20px">
				{trip.totalKm.toFixed(1)} km
			</div>
		{/if}

		<!-- Fortschrittsbalken -->
		<div>
			<div style:display="flex" style:justify-content="space-between" style:align-items="baseline" style:margin-bottom="8px">
				<span style:font-family="var(--g-font-mono)" style:font-size="11px" style:color="var(--g-ink-2)" style:letter-spacing="0.06em" style:text-transform="uppercase" style:font-weight="600">
					Tag {dayCurrent} / {dayTotal}
				</span>
				<span style:font-family="var(--g-font-mono)" style:font-size="11px" style:color="var(--g-ink-3)">
					{dayCurrent} von {dayTotal} Tagen
				</span>
			</div>
			<div style:height="6px" style:border-radius="999px" style:background="var(--g-paper-deep)" style:overflow="hidden">
				<div style:width="{pct}%" style:height="100%" style:background="var(--g-accent)" style:border-radius="999px"></div>
			</div>
		</div>
	</div>

	<!-- Footer-Leiste -->
	<div
		style:border-top="1px solid var(--g-rule-soft)"
		style:padding="14px 26px"
		style:background="var(--g-card-alt)"
		style:display="flex"
		style:align-items="center"
		style:justify-content="space-between"
		style:gap="16px"
		style:flex-wrap="wrap"
	>
		<div style:display="flex" style:align-items="center" style:gap="16px">
			<Eyebrow>Kanäle</Eyebrow>
			<div style:display="flex" style:gap="14px">
				{#each tripChannels as c (c.kind)}
					<span style:display="inline-flex" style:align-items="center" style:gap="6px" style:font-size="12px" style:color="var(--g-ink-2)">
						<Dot tone="good" size={7} />
						<span style:font-family="var(--g-font-mono)" style:text-transform="capitalize">{c.kind}</span>
					</span>
				{/each}
			</div>
		</div>
		<a href="#" style:font-size="12px" style:color="var(--g-ink-3)" style:text-decoration="none" style:font-family="var(--g-font-mono)">Trip öffnen →</a>
	</div>
</Card>
