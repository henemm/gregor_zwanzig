<script lang="ts">
	// Issue #2837 S1 (Epic #2345, ADR-0110) — geteilter Hub-Kopf für Trip (`context="route"`)
	// und Ortsvergleich (`context="vergleich"`). Spec: docs/specs/modules/rework_2837_s1_hub_kopf.md
	//
	// EIN Markup, keine Verzweigung nach `context`: es wählt nur Datenmarke (`data-kind`) und
	// den Text, den die Seite hineinreicht (Breadcrumb-Elternteil, Kind). Die Leiste trägt
	// Breadcrumb (seit #2980 ohne Zurück-Pfeil), „Senden" (bzw. im Vergleich-Entwurf „Setup abschließen"
	// auf demselben Platz), Kebab und Meldungen; darunter der geteilte `SubscriptionHeader`.
	// Fachlich Verschiedenes kommt nur über Snippets (Whitelist, Spec Entscheidung 8).
	// Der Baustein ruft keine API: „Senden" öffnet über `onSend` nur den Dialog der Seite (#2278).
	//
	// #2913 Scheibe c2 (Spec docs/specs/modules/feat_2913_c2_seitenkopf.md): Kopf nach Mockup —
	// Eyebrow („Trip · Region" / „Orte · Region") und Meta-Zeile kommen als reiner Text über
	// `eyebrowText`/`metaTeile` (genau ein Eyebrow, genau eine Meta-Zeile, für beide Arten gleich);
	// im Entwurf steht „Aktivieren" als Link (`aktivierenHref`, Ziel wählt die Seite) neben der Status-Pill.
	import type { Snippet } from 'svelte';
	import { Btn, Eyebrow } from '$lib/components/atoms';
	import SubscriptionKebab from '$lib/components/molecules/SubscriptionKebab.svelte';
	import SubscriptionHeader from '$lib/components/shared/subscription-header/SubscriptionHeader.svelte';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import { t } from '$lib/i18n';

	type Field = 'name' | 'region' | 'profile';

	interface Props {
		context: 'route' | 'vergleich';
		/** Elternteil des Breadcrumbs (Katalogtext + Listen-Adresse); einziger Weg zur Liste (#2980 AC-24). */
		parent: { label: string; href: string };
		/** Kind des Breadcrumbs: voller Name (#2980 AC-24, kein Kürzel) — kein Link. */
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
		/** #2913 c2: Eyebrow über dem Titel als reiner Text (Trip „Trip · Region", Vergleich „Orte · Region"). */
		eyebrowText?: string;
		/** #2913 c2: Meta-Zeile unter dem Titel, Teile mit „ · " verbunden. */
		metaTeile?: string[];
		/** #2913 c2: nur im Entwurf übergeben — „Aktivieren" als Link neben der Status-Pill (Ziel im Markup prüfbar). */
		aktivierenHref?: string;
		meldungen?: Snippet;
		/** Fachliches unter dem Titelblock (Whitelist: Trip-km/Hm und Mobil-Kacheln), über der Unterkante. */
		unten?: Snippet;
	}

	let {
		context, parent, crumb, sendLabel, onSend, sendDisabled = false, sendMode = 'senden', onSetup,
		actions = [], onSelect, mobil = false, onSheetOpen, leisteTestid,
		name, region, profile, profileOptions, profileLabel = '', regionMaxLength = 60, testidPrefix,
		titleTestid, titleSize = 38, saveController, onSaveField,
		status, eyebrow, namePrefix, meta, eyebrowText, metaTeile, aktivierenHref, meldungen, unten
	}: Props = $props();

	// SubscriptionHeader kennt die Arten als 'trip' | 'vergleich' — reine Datenmarke (Tabelle,
	// keine HERKUNFT-Verzweigung im Sinne von context_herkunft_zweige_eingefroren.test.ts).
	const KIND = { route: 'trip', vergleich: 'vergleich' } as const;
</script>

{#snippet kopfEyebrow()}
	<div class="hub-kopf-eyebrow"><Eyebrow data-testid="hub-kopf-eyebrow">{eyebrowText}</Eyebrow></div>
{/snippet}
{#snippet kopfMeta()}
	<p class="hub-kopf-meta" data-testid="hub-kopf-meta">{(metaTeile ?? []).join(' · ')}</p>
{/snippet}

<div class="hub-kopf" data-kind={context} data-seite="hub" data-abschnitt="kopf">
	<div data-testid={leisteTestid}>
		<div class="hub-kopf-leiste" data-testid="hub-kopf-leiste">
			<!-- #2980 AC-24 (ADR-0118, Mockup Z. 229–240): kein Zurück-Pfeil mehr, auch am Handy —
			     der Elternteil des Breadcrumbs ist der Weg zur Liste. -->
			<div class="breadcrumb-path" data-testid="hub-kopf-breadcrumb">
				<a href={parent.href} class="breadcrumb-link g-link-tap">{parent.label}</a>
				<span class="trenner">/</span>
				<span class="kind">{crumb}</span>
			</div>
			<div class="hub-actions">
				<!-- #2913 c2: Reihenfolge wie im Mockup (mockup-hub-fassung3.html Z. 233–237): erst Kebab, dann „Test schicken ▾“. -->
				<SubscriptionKebab data-testid="subscription-kebab" {actions} {onSelect} {mobil} {onSheetOpen} />
				{#if sendMode === 'setup'}
					<Btn variant="primary" size="sm" onclick={() => onSetup?.()}>{sendLabel}</Btn>
				{:else}
					<!-- „Senden" öffnet nur den Sende-Dialog der Seite (#2278 AC-12).
					     #2980 AC-16 (ADR-0118): Akzent-Hauptaktion, Fläche --g-accent-deep (WCAG-AA statt Mockup-Orange). -->
					<Btn variant="accent" size="sm" data-testid="subscription-hub-send" onclick={() => onSend?.()} disabled={sendDisabled}>{sendLabel}</Btn>
				{/if}
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
			eyebrow={eyebrowText !== undefined ? kopfEyebrow : eyebrow}
			unterTitel={metaTeile !== undefined ? kopfMeta : undefined}
			{namePrefix}
			{meta}
		>
			{#snippet badges()}
				<span class="hub-kopf-status" data-testid="hub-kopf-status">
					{#if status}{@render status()}{/if}
					{#if aktivierenHref}<Btn variant="primary" size="sm" data-testid="hub-kopf-aktivieren" href={aktivierenHref}>{$t('aktionen.kopf.aktivieren')}</Btn>{/if}
				</span>
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
		/* #2980 AC-23 (Mockup .crumbs): Großschreibung nur per CSS, der DOM-Text bleibt unverändert. */
		text-transform: uppercase;
		flex: 1 1 0;
		/* #2980 AC-24: langer Name bricht um statt mit Auslassungspunkten gekürzt zu werden
		   (kein overflow:hidden mehr, daher beschneidet nichts die 44-px-Trefferfläche des Links). */
		min-width: 0;
		overflow-wrap: anywhere;
		/* #2601 Runde 2 (AC-10): Raum für die 44-px-Trefferfläche des .g-link-tap-Links (±13 px)
		   im Bereich selbst, sonst ragt sie über den Bereich hinaus (scrollHeight > clientHeight).
		   Der negative Block-Rand hebt das Polster für das Layout wieder auf (Zeilenhöhe unverändert). */
		padding-block: 13px;
		margin-block: -13px;
	}
	.breadcrumb-link {
		color: inherit;
		text-decoration: none;
		/* #2980 AC-10/AC-24: bricht der Name um, liegt seine zweite Zeile im unteren Polster der
		   Link-Trefferfläche — der Link liegt darüber, damit die volle Trefferhöhe antippbar bleibt. */
		position: relative;
		z-index: 1;
	}
	.breadcrumb-link:hover {
		text-decoration: underline;
	}
	.trenner {
		margin: 0 8px;
	}
	/* #2980 AC-23 (Mockup .crumbs .path b): Name in --g-ink, Gewicht 500. */
	.kind {
		color: var(--g-ink);
		font-weight: 500;
		overflow-wrap: anywhere;
	}
	.hub-actions {
		/* #2980 HP-3: Lage der Aktionen unabhängig von der Zeilenzahl der Brotkrumen — bricht ein
		   langer Name um, bleibt „Senden"/„Setup abschließen" oben statt mittig tiefer zu rutschen.
		   Einzeilig sind die Aktionen das höchste Element der Leiste, oben = mittig (unverändert). */
		align-self: flex-start;
		display: flex;
		align-items: center;
		justify-content: flex-end;
		flex-wrap: wrap;
		gap: 8px;
		/* schrumpfbar: eine Meldung bricht IN den Aktionen um statt die Leiste zu sprengen (AC-8). */
		min-width: 0;
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
	.hub-kopf-eyebrow {
		margin-bottom: var(--g-s-2);
	}
	/* #2980 AC-20 (Mockup .meta): Mono 13 px in --g-ink-3. */
	.hub-kopf-meta {
		margin: var(--g-s-2) 0 0;
		font-family: var(--g-font-mono);
		font-size: var(--g-text-sm);
		color: var(--g-ink-3);
		font-variant-numeric: tabular-nums;
	}
	/* #2980 AC-25 (Mockup .btn.ghost): Kebab als Ghost-Knopf mit Rahmen --g-rule auf transparentem
	   Grund, Desktop und Handy. !important nötig, weil SubscriptionKebab Rahmen und Grund als
	   Inline-Stil setzt (Desktop --g-rule-soft, Handy ohne Rahmen) und auch in der Listen-Karte
	   (SubscriptionCard) dient, deren Optik hier unverändert bleibt. */
	.hub-actions > :global([data-testid='subscription-kebab']) {
		border: 1px solid var(--g-rule) !important;
		background: transparent !important;
	}
	.hub-kopf-status {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		flex-shrink: 0;
	}
	/* Mobil (≤899 px): 44-px-Tippflächen ohne Zeilenhöhe (negativer Block-Rand, #2284 S2 AC-13).
	   #2980 AC-24: kein Zurück-Pfeil mehr; der Pfad bricht um (min-width:0 oben), damit
	   „Test schicken" und Kebab ihren Platz in der Leiste behalten. */
	@media (max-width: 899px) {
		.hub-kopf-leiste {
			padding: 12px 16px;
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
