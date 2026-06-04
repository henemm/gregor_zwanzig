<script lang="ts">
	// Issue #578 — HomeHeroCompare-Organism.
	// Kanonische Quelle: screen-home.jsx::HomeHeroCompare
	//
	// Hero-Karte für einen aktiven Orts-Vergleich (Startseite-Cockpit).

	import { Card, Pill, Dot, Eyebrow } from '$lib/components/atoms';

	interface ComparePreset {
		id?: string;
		name: string;
		location_ids?: string[];
		display_config?: Record<string, unknown>;
		empfaenger?: string[];
		schedule?: string;
		nextSend?: string;
		profileLabel?: string;
		region?: string;
		horizon?: string;
		channels?: string[];
	}

	interface Props {
		preset: ComparePreset;
		class?: string;
	}

	let { preset, class: className = '' }: Props = $props();

	const locationCount = $derived((preset.location_ids ?? []).length);
	const schedule = $derived(preset.schedule ?? '—');
	const nextSend = $derived(preset.nextSend ?? '—');
	const channels = $derived(preset.channels ?? preset.empfaenger ?? []);
	const profileLabel = $derived(preset.profileLabel ?? '');
	const region = $derived((preset.display_config?.region as string) ?? preset.region ?? '');
</script>

<Card padding={0} style="overflow: hidden; border-left: 3px solid var(--g-accent);" class={className}>
	<div style:padding="22px 26px">
		<!-- Pills -->
		<div style:display="flex" style:align-items="center" style:gap="10px" style:margin-bottom="12px" style:flex-wrap="wrap">
			<Pill tone="accent"><Dot tone="good" size={6} /> Aktiv · läuft automatisch</Pill>
			{#if profileLabel}
				<Pill tone="ghost">{profileLabel}</Pill>
			{/if}
		</div>

		<!-- Titel -->
		<div style:font-size="34px" style:font-weight="600" style:letter-spacing="-0.02em" style:line-height="1.05" style:margin-bottom="6px">
			{preset.name}
		</div>

		<!-- Subtitel -->
		<div style:font-size="15px" style:color="var(--g-ink-2)" style:margin-bottom="20px">
			{region}{region ? ' · ' : ''}{locationCount} Orte verglichen
		</div>

		<!-- 2-Spalten-Grid: Zeitplan + Nächster Versand -->
		<div style:display="grid" style:grid-template-columns="1fr 1fr" style:gap="14px">
			<div style:padding="12px 14px" style:border="1px solid var(--g-rule-soft)" style:border-radius="var(--g-r-2)" style:background="var(--g-paper-deep)">
				<div style:font-family="var(--g-font-mono)" style:font-size="10px" style:color="var(--g-ink-3)" style:text-transform="uppercase" style:letter-spacing="0.1em" style:margin-bottom="5px">Zeitplan</div>
				<div style:font-size="15px" style:font-weight="600">{schedule}</div>
			</div>
			<div style:padding="12px 14px" style:border="1px solid var(--g-rule-soft)" style:border-radius="var(--g-r-2)" style:background="var(--g-paper-deep)">
				<div style:font-family="var(--g-font-mono)" style:font-size="10px" style:color="var(--g-ink-3)" style:text-transform="uppercase" style:letter-spacing="0.1em" style:margin-bottom="5px">Nächster Versand</div>
				<div style:font-size="15px" style:font-weight="600">{nextSend}</div>
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
				{#each channels as ch (ch)}
					<span style:display="inline-flex" style:align-items="center" style:gap="6px" style:font-size="12px" style:color="var(--g-ink-2)">
						<Dot tone="good" size={7} />
						<span style:font-family="var(--g-font-mono)" style:text-transform="capitalize">{ch}</span>
					</span>
				{/each}
			</div>
		</div>
		<a href="#" style:font-size="12px" style:color="var(--g-ink-3)" style:text-decoration="none" style:font-family="var(--g-font-mono)">Vergleich öffnen →</a>
	</div>
</Card>
