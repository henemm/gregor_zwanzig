<script lang="ts">
	// Issue #2346 S3 (AC-11) — EIN Startseiten-Hero fuer Trip und Ortsvergleich
	// (ersetzt die beiden Inline-Heros aus +page.svelte). Gemeinsamer Rahmen mit
	// fester Felderfolge Pills -> Titel -> Untertitel -> Naechster Versand -> Kanaele,
	// darunter die Schnellaktionen. Kind-eigene Inhalte (Trip: Etappen-Fortschritt;
	// Vergleich: Zeitplan) kommen als Snippets — keine zweite Struktur je kind.
	// Kanaele kommen fertig vom Aufrufer (homeHeroChannels: Flags, nie empfaenger, #1452).

	import type { Snippet } from 'svelte';
	import { Card, Dot, Eyebrow } from '$lib/components/atoms';
	import type { SubscriptionKind } from '$lib/components/shared/subscriptionTabs.js';
	import { t } from '$lib/i18n/index.js';

	interface Props {
		kind: SubscriptionKind;
		id: string;
		name: string;
		href: string;
		subtitle?: string;
		channels: string[];
		nextSend?: string | null;
		pills?: Snippet;
		details?: Snippet;
		actions?: Snippet;
		/** Rechte Spalte (Versand heute + Alerts), kind-eigen. */
		aside?: Snippet;
	}

	let { kind, id, name, href, subtitle = '', channels, nextSend = null, pills, details, actions, aside }: Props =
		$props();

	// #2652 (i18n F3): $derived, damit der Link auf einen Sprachwechsel reagiert.
	const OEFFNEN: Record<SubscriptionKind, string> = $derived({
		trip: $t('home.hero.oeffnen.trip'),
		vergleich: $t('home.hero.oeffnen.vergleich')
	});
</script>

<!-- 2-Spalten-Grid: links Hero-Karte + Schnellaktionen, rechts kind-eigene Spalte (aside) -->
<div data-testid="home-hero-{id}" data-kind={kind} class="cockpit-hero" style:margin-bottom="36px">
<div style:display="flex" style:flex-direction="column" style:gap="20px">
	<Card padding={0} style="overflow: hidden; border-left: 3px solid var(--g-accent)">
		<div style:padding="22px 26px">
			<div
				data-field="pills"
				style:display="flex"
				style:align-items="center"
				style:gap="10px"
				style:margin-bottom="12px"
				style:flex-wrap="wrap"
			>
				{@render pills?.()}
			</div>

			<a
				data-field="title"
				{href}
				class="g-link-tap"
				style:display="block"
				style:font-size="34px"
				style:font-weight="600"
				style:letter-spacing="-0.02em"
				style:line-height="1.05"
				style:margin-bottom="6px"
				style:color="var(--g-ink)"
				style:text-decoration="none"
			>{name}</a>

			<div data-field="subtitle" style:font-size="15px" style:color="var(--g-ink-2)" style:margin-bottom="20px">
				{subtitle}
			</div>

			<!-- Kind-eigene Inhalte (details) und Naechster Versand teilen sich ein Raster;
			     ein Inhalt ueber die volle Breite setzt selbst grid-column: 1 / -1. -->
			<div style:display="grid" style:grid-template-columns="1fr 1fr" style:gap="14px">
				{@render details?.()}
				<div
					data-field="next-send"
					style:padding="12px 14px"
					style:border="1px solid var(--g-rule-soft)"
					style:border-radius="var(--g-r-2)"
					style:background="var(--g-paper-deep)"
				>
					<div
						style:font-family="var(--g-font-mono)"
						style:font-size="11px"
						style:color="var(--g-ink-3)"
						style:text-transform="uppercase"
						style:letter-spacing="0.1em"
						style:margin-bottom="5px"
					>{$t('home.hero.naechster_versand')}</div>
					<div style:font-size="15px" style:font-weight="600">{nextSend ?? '—'}</div>
				</div>
			</div>
		</div>

		<div
			data-field="channels"
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
				<Eyebrow>{$t('home.hero.kanaele')}</Eyebrow>
				<div style:display="flex" style:gap="14px">
					{#each channels as ch (ch)}
						<span
							data-channel={ch}
							style:display="inline-flex"
							style:align-items="center"
							style:gap="6px"
							style:font-size="12px"
							style:color="var(--g-ink-2)"
						>
							<Dot tone="good" size={7} />
							<span style:font-family="var(--g-font-mono)">{ch}</span>
						</span>
					{:else}
						<span style:font-size="12px" style:color="var(--g-ink-2)">—</span>
					{/each}
				</div>
			</div>
			<a
				{href}
				class="g-link-tap"
				style:font-size="12px"
				style:color="var(--g-ink-3)"
				style:text-decoration="none"
				style:font-family="var(--g-font-mono)"
			>{OEFFNEN[kind]}</a>
		</div>
	</Card>

	{#if actions}
		<div>
			<div style:margin-bottom="12px">
				<Eyebrow style="margin-bottom: 4px">{$t('home.hero.schnell_eingreifen')}</Eyebrow>
				<div style:font-size="17px" style:font-weight="600">{$t('home.hero.schnellaktionen')}</div>
			</div>
			<div style:display="flex" style:flex-direction="column" style:gap="10px">
				{@render actions()}
			</div>
		</div>
	{/if}
</div>
{@render aside?.()}
</div>

<style>
	.cockpit-hero {
		display: grid;
		grid-template-columns: 1.4fr 1fr;
		gap: 24px;
		align-items: start;
	}
	/* Grid-Items dürfen unter ihre Min-Content-Breite schrumpfen — sonst
	   sprengen nowrap-Zeilen (Datum, Compare-Rows) den Viewport auf Mobile. */
	.cockpit-hero > :global(*) {
		min-width: 0;
	}
	@media (max-width: 899px) {
		.cockpit-hero {
			grid-template-columns: 1fr;
		}
	}
</style>
