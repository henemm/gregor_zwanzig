<script lang="ts">
	// Issue #2837 S1 (Epic #2345, ADR-0110) — geteilter Hub-Kopf für Trip (`context="route"`)
	// und Ortsvergleich (`context="vergleich"`). Spec: docs/specs/modules/rework_2837_s1_hub_kopf.md
	//
	// EIN Markup, keine Verzweigung nach `context`: es wählt nur Datenmarke (`data-kind`) und
	// den Text, den die Seite hineinreicht (Breadcrumb-Elternteil, Kind). Die Leiste trägt
	// Zurück-Pfeil (mobil), Breadcrumb, „Senden" (bzw. im Vergleich-Entwurf „Setup abschließen"
	// auf demselben Platz), Kebab und Meldungen; darunter der geteilte `SubscriptionHeader`.
	// Fachlich Verschiedenes kommt nur über Snippets (Whitelist, Spec Entscheidung 8).
	// Der Baustein ruft keine API: „Senden" öffnet über `onSend` nur den Dialog der Seite (#2278).
	import type { Snippet } from 'svelte';
	import { Btn, BackLink } from '$lib/components/atoms';
	import SubscriptionKebab from '$lib/components/molecules/SubscriptionKebab.svelte';
	import SubscriptionHeader from '$lib/components/shared/subscription-header/SubscriptionHeader.svelte';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import { t } from '$lib/i18n';

	type Field = 'name' | 'region' | 'profile';

	interface Props {
		context: 'route' | 'vergleich';
		/** Elternteil des Breadcrumbs (Katalogtext + Listen-Adresse); Ziel auch des Zurück-Pfeils. */
		parent: { label: string; href: string };
		/** Kind des Breadcrumbs (Trip: Kürzel ?? Name, Vergleich: Name) — kein Link. */
		crumb: string;
		sendLabel: string;
		onSend?: () => void;
		sendDisabled?: boolean;
		/** 'setup' nur im Vergleich-Entwurf: „Setup abschließen" (onSetup) auf dem Platz von „Senden". */
		sendMode?: 'senden' | 'setup';
		onSetup?: () => void;
		actions?: Array<{ id: string; label: string; danger?: boolean }>;
		onSelect?: (id: string) => void;
		mobil?: boolean;
		onSheetOpen?: () => void;
		/** Stabile Alt-testid um die Leiste (Trip: `trip-detail-breadcrumb-bar`). */
		leisteTestid?: string;
		name: string;
		region: string | undefined;
		profile: string | undefined;
		profileOptions: ReadonlyArray<{ value: string; label: string }>;
		profileLabel?: string;
		regionMaxLength?: number;
		testidPrefix: string;
		titleTestid?: string;
		titleSize?: 30 | 38;
		saveController?: SaveStatus;
		onSaveField: (field: Field, value: string, schliessen: () => void) => Promise<void>;
		status?: Snippet;
		eyebrow?: Snippet;
		namePrefix?: Snippet;
		meta?: Snippet;
		meldungen?: Snippet;
		/** Fachliches unter dem Titelblock (Whitelist: Trip-km/Hm und Mobil-Kacheln), über der Unterkante. */
		unten?: Snippet;
	}

	let {
		context, parent, crumb, sendLabel, onSend, sendDisabled = false, sendMode = 'senden', onSetup,
		actions = [], onSelect, mobil = false, onSheetOpen, leisteTestid,
		name, region, profile, profileOptions, profileLabel = '', regionMaxLength = 60, testidPrefix,
		titleTestid, titleSize = 38, saveController, onSaveField,
		status, eyebrow, namePrefix, meta, meldungen, unten
	}: Props = $props();

	// SubscriptionHeader kennt die Arten als 'trip' | 'vergleich' — reine Datenmarke (Tabelle,
	// keine HERKUNFT-Verzweigung im Sinne von context_herkunft_zweige_eingefroren.test.ts).
	const KIND = { route: 'trip', vergleich: 'vergleich' } as const;
</script>

<div class="hub-kopf" data-kind={context}>
	<div data-testid={leisteTestid}>
		<div class="hub-kopf-leiste" data-testid="hub-kopf-leiste">
			<div class="back-mobil"><BackLink href={parent.href} label="" ariaLabel={$t('aktionen.zurueck_uebersicht')} /></div>
			<div class="breadcrumb-path" data-testid="hub-kopf-breadcrumb">
				<a href={parent.href} class="breadcrumb-link g-link-tap">{parent.label}</a>
				<span class="trenner">/</span>
				<span class="kind">{crumb}</span>
			</div>
			<div class="hub-actions">
				{#if sendMode === 'setup'}
					<Btn variant="primary" size="sm" onclick={() => onSetup?.()}>{sendLabel}</Btn>
				{:else}
					<!-- „Senden" öffnet nur den Sende-Dialog der Seite (#2278 AC-12). -->
					<Btn variant="primary" size="sm" data-testid="subscription-hub-send" onclick={() => onSend?.()} disabled={sendDisabled}>{sendLabel}</Btn>
				{/if}
				<SubscriptionKebab data-testid="subscription-kebab" {actions} {onSelect} {mobil} {onSheetOpen} />
				{#if meldungen}{@render meldungen()}{/if}
			</div>
		</div>
	</div>
	<div class="hub-kopf-titel">
		<SubscriptionHeader
			kind={KIND[context]}
			{name}
			{region}
			{profile}
			{profileOptions}
			{profileLabel}
			{regionMaxLength}
			{testidPrefix}
			{titleTestid}
			{titleSize}
			{saveController}
			{onSaveField}
			{eyebrow}
			{namePrefix}
			{meta}
		>
			{#snippet badges()}
				<span class="hub-kopf-status" data-testid="hub-kopf-status">{#if status}{@render status()}{/if}</span>
			{/snippet}
		</SubscriptionHeader>
		{#if unten}{@render unten()}{/if}
	</div>
</div>

<style>
	.hub-kopf-leiste {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 12px 40px;
		border-bottom: 1px solid var(--g-rule-soft);
		gap: 16px;
	}
	.breadcrumb-path {
		font-family: var(--g-font-mono);
		font-size: 11px;
		letter-spacing: 0.06em;
		color: var(--g-ink-3);
		flex: 1 1 0;
		min-width: 0;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.breadcrumb-link {
		color: inherit;
		text-decoration: none;
	}
	.breadcrumb-link:hover {
		text-decoration: underline;
	}
	.trenner {
		margin: 0 8px;
	}
	.kind {
		color: var(--g-ink);
	}
	.hub-actions {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		flex-wrap: wrap;
		gap: 8px;
		/* schrumpfbar: eine Meldung bricht IN den Aktionen um statt die Leiste zu sprengen (AC-8). */
		min-width: 0;
	}
	.back-mobil {
		display: none;
	}
	/* #2837 S1 (Adversary F001): Unterkante des Kopfs für beide Arten hier, nie in der Seite —
	   Abstand unter dem Titelblock und (Desktop) die Trennlinie aus der Design-Fidelity #582. */
	.hub-kopf-titel {
		padding: 24px 40px 16px;
	}
	@media (min-width: 900px) {
		.hub-kopf {
			border-bottom: 1px solid var(--g-rule);
		}
	}
	.hub-kopf-status {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		flex-shrink: 0;
	}
	/* Mobil (≤899 px): Zurück-Pfeil statt Pfad-Anfang, 44-px-Tippflächen ohne Zeilenhöhe
	   (negativer Block-Rand, #2284 S2 AC-13); der Pfad kürzt mit Ellipsis, damit „Senden"
	   und Kebab nie in eine zweite Zeile rutschen (#2278 AC-13, AC-5). */
	@media (max-width: 899px) {
		.hub-kopf-leiste {
			padding: 12px 16px;
		}
		.back-mobil {
			display: flex;
			flex-shrink: 0;
			margin-block: -8px;
			margin-right: -12px;
		}
		.hub-actions > :global([data-slot='btn']),
		.hub-actions > :global([data-testid='subscription-kebab']) {
			min-height: 44px;
			min-width: 44px;
			margin-block: -8px;
		}
		.hub-kopf-titel {
			padding: 16px;
		}
	}
</style>
