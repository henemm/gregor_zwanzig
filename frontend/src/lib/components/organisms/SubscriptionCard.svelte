<script lang="ts">
	// Issue #2278 (AC-14/AC-15) — EINE Karte fuer Trip und Ortsvergleich (verallgemeinert CompareTile).
	//
	// - Aktionen: Prop `actions` (Startseiten-Kachel: nur "Bearbeiten"), sonst
	//   subscriptionActions(kind, Lebenszyklus, 'list').
	// - dense + onAction: Menue-Knopf (oeffnet im Elternteil das Aktionsblatt); nicht-dense: Kebab.
	// - Wurzel data-testid="subscription-card-{id}", data-kind, data-status (Lebenszyklus).
	// - Issue #2346 S2: Felder data-field="status|channels|next-send|last-sent" kind-neutral (auch compact).

	import type { ComparePreset, Trip } from '$lib/types.js';
	import {
		presetLocationsLabel,
		presetProfileLabel,
		presetTileScheduleLabel,
		relativeLastSent,
		presetChannels
	} from '$lib/components/compare/subscriptionHelpers.js';
	import { subscriptionActions, subscriptionLifecycle } from '$lib/components/shared/subscriptionActions.js';
	import type { SubscriptionKind } from '$lib/components/shared/subscriptionTabs.js';
	import { tripStatus } from '$lib/utils/tripStatus.js';
	import SubscriptionKebab from '$lib/components/molecules/SubscriptionKebab.svelte';
	import EllipsisVerticalIcon from '@lucide/svelte/icons/ellipsis-vertical';
	import { t } from '$lib/i18n';

	interface Props {
		kind: SubscriptionKind;
		sub: Trip | ComparePreset;
		now?: Date;
		dense?: boolean;
		compact?: boolean;
		accent?: boolean;
		onclick?: () => void;
		onAction?: (id: string) => void;
		actions?: Array<{ id: string; label: string; danger?: boolean }>;
		class?: string;
		// Issue #2346 S2: kind-neutrale Felder, vom Aufrufer geliefert (Startseiten-Kachel).
		// Nicht gesetzt (undefined) => bisheriges Verhalten (Listen); null => ehrlicher Leerzustand "—".
		channels?: string[];
		nextSend?: string | null;
		lastSent?: string | null;
		href?: string;
	}

	let {
		kind,
		sub,
		now = new Date(),
		dense = false,
		compact = false,
		accent = false,
		onclick,
		onAction,
		actions: actionsProp,
		class: className = '',
		channels: channelsProp,
		nextSend,
		lastSent,
		href
	}: Props = $props();

	const status = $derived(subscriptionLifecycle(kind, sub, now));
	const active = $derived(status === 'active');
	const draft = $derived(status === 'draft');
	const actions = $derived(actionsProp ?? subscriptionActions(kind, status, 'list'));

	const preset = $derived(sub as ComparePreset);
	const trip = $derived(sub as Trip);

	// Anzeige-Status: Trip zeigt die feinere Datumsphase (geplant/fertig) wie bisher im Cockpit.
	const statusText = $derived(
		kind === 'trip'
			? status === 'active' || status === 'paused' || status === 'draft'
				? tripStatus(trip, now)
				: 'archiviert'
			: ({ active: 'aktiv', paused: 'pausiert', draft: 'draft', archived: 'archiviert' } as const)[status]
	);
	const region = $derived(
		kind === 'trip'
			? (trip.region ?? '')
			: (((preset.display_config as Record<string, unknown> | undefined)?.region as string | undefined) ?? '')
	);
	const metaText = $derived.by(() => {
		if (kind === 'trip') {
			const dates = (trip.stages ?? []).map((s) => s.date).filter(Boolean).sort();
			const range = dates.length === 0 ? '-' : dates.length === 1 ? dates[0] : `${dates[0]} — ${dates[dates.length - 1]}`;
			return $t('bausteine.abo.etappen', { anzahl: trip.stages?.length ?? 0, zeitraum: range });
		}
		const profil = presetProfileLabel(preset.profil);
		return presetLocationsLabel(preset) + (profil ? ` · ${profil}` : '');
	});
	// Issue #2346 S2: Felder erscheinen, wenn ihre Daten vorliegen — nicht nach kind. Geliefert vom
	// Aufrufer (Kachel, beide kinds, auch compact) oder aus der eingebauten Quelle des Vergleichs
	// (presetChannels, letzter_versand, Zeitplan) wie bisher in den Listen.
	const channels = $derived(
		channelsProp ?? (kind === 'vergleich' && !compact ? presetChannels(preset) : null)
	);
	const versandGeliefert = $derived(nextSend !== undefined || lastSent !== undefined);
	const zeigeFusszeile = $derived(versandGeliefert || kind === 'vergleich');
	const scheduleText = $derived(kind === 'vergleich' ? presetTileScheduleLabel(preset) : '');
	const lastSentText = $derived(
		lastSent !== undefined
			? lastSent
			: kind === 'vergleich'
				? relativeLastSent(preset.letzter_versand) || null
				: null
	);

	let hover = $state(false);

	function handleKey(e: KeyboardEvent) {
		if (!onclick) return;
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			onclick();
		}
	}
	const dotColor = (good: boolean): string => (good ? 'var(--g-accent-good, #22c55e)' : 'var(--g-ink-4)');
</script>

<div
	class={'subscription-card' + (className ? ' ' + className : '')}
	data-testid="subscription-card-{sub.id}"
	data-kind={kind}
	data-status={status}
	role={onclick ? 'button' : undefined}
	tabindex={onclick ? 0 : undefined}
	onclick={onclick ? () => onclick?.() : undefined}
	onkeydown={onclick ? handleKey : undefined}
	onmouseenter={() => (hover = true)}
	onmouseleave={() => (hover = false)}
	style:cursor={onclick ? 'pointer' : 'default'}
	style:text-align="left"
	style:width="100%"
	style:background="var(--g-card)"
	style:border-top="1px solid var(--g-rule)"
	style:border-right="1px solid var(--g-rule)"
	style:border-bottom="1px solid var(--g-rule)"
	style:border-color={hover && !dense ? 'var(--g-ink-3)' : 'var(--g-rule)'}
	style:border-left={active && accent ? '3px solid var(--g-accent)' : '1px solid var(--g-rule)'}
	style:border-radius="var(--g-r-3)"
	style:box-shadow={dense ? 'none' : hover ? 'var(--g-shadow-2, 0 6px 20px rgba(0,0,0,0.10))' : 'var(--g-shadow-1)'}
	style:transition="box-shadow 120ms, border-color 120ms"
	style:padding={dense ? '14px 14px' : '16px 18px'}
	style:min-height="44px"
	style:display="flex"
	style:flex-direction="column"
	style:gap={dense ? '10px' : '12px'}
	style:opacity={draft && !dense ? '0.94' : '1'}
>
	<div style:display="flex" style:align-items="flex-start" style:gap="10px">
		<span style:margin-top={dense ? '5px' : '6px'} style:flex-shrink="0">
			<svg width="7" height="7" viewBox="0 0 7 7" style:display="block">
				<circle cx="3.5" cy="3.5" r="3.5" fill={dotColor(active)} />
			</svg>
		</span>

		<div style:flex="1" style:min-width="0">
			<div
				style:font-size={dense ? '15px' : '15.5px'}
				style:font-weight="600"
				style:letter-spacing="-0.01em"
				style:line-height="1.25"
				style:white-space="nowrap"
				style:overflow="hidden"
				style:text-overflow="ellipsis"
			>
				{#if href}
					<!-- #2346 AC-17: echter Link (Mittel-/Rechtsklick); Karten-Klick bleibt goto. -->
					<a
						{href}
						onclick={(e) => e.stopPropagation()}
						style:color="inherit"
						style:text-decoration="none">{sub.name || '(ohne Namen)'}</a
					>
				{:else}
					{sub.name || '(ohne Namen)'}
				{/if}
			</div>

			<div style:display="flex" style:align-items="center" style:gap="7px" style:margin-top="3px">
				<span
					data-field="status"
					style:font-family="var(--g-font-mono)"
					style:font-size="11px"
					style:color="var(--g-ink-4)"
					style:text-transform="uppercase"
					style:letter-spacing="0.14em"
				>{statusText}</span>
				{#if region}
					<span
						style:font-size="12px"
						style:color="var(--g-ink-3)"
						style:white-space="nowrap"
						style:overflow="hidden"
						style:text-overflow="ellipsis"
					>· {region}</span>
				{/if}
			</div>
		</div>

		{#if onAction}
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<div style:flex-shrink="0" style:margin-top="2px" onclick={(e) => e.stopPropagation()}>
				{#if dense}
					<button
						type="button"
						data-testid="subscription-card-menu-{sub.id}"
						aria-label={$t('aktionen.weitere')}
						title={$t('aktionen.weitere')}
						onclick={(e: MouseEvent) => {
							e.stopPropagation();
							onAction?.('menu');
						}}
						style:display="inline-flex"
						style:align-items="center"
						style:justify-content="center"
						style:width="44px"
						style:height="44px"
						style:margin="-8px -8px 0 0"
						style:background="transparent"
						style:border="none"
						style:color="var(--g-ink-2)"
						style:cursor="pointer"
					>
						<EllipsisVerticalIcon size={18} />
					</button>
				{:else}
					<SubscriptionKebab {actions} onSelect={(id) => onAction?.(id)} />
				{/if}
			</div>
		{/if}
	</div>

	<div
		style:font-family="var(--g-font-mono)"
		style:font-size={dense ? '11px' : '11.5px'}
		style:color="var(--g-ink-2)"
		style:letter-spacing="0.02em"
		style:padding-left="17px"
	>{metaText}</div>

	{#if channels}
		<div
			data-field="channels"
			style:display="flex"
			style:flex-wrap="wrap"
			style:gap={dense ? '4px' : '5px'}
			style:padding-left="17px"
			style:min-height={dense ? '18px' : '20px'}
		>
			{#if channels.length === 0}
				<span style:font-family="var(--g-font-mono)" style:font-size={dense ? '10px' : '11px'} style:color="var(--g-ink-4)"
					>{$t('bausteine.abo.keine_kanaele')}</span
				>
			{:else}
				{#each channels as ch (ch)}
					<span
						data-channel={ch}
						style:font-family="var(--g-font-mono)"
						style:padding="2px 7px"
						style:font-size="11px"
						style:letter-spacing="0.04em"
						style:border="1px solid var(--g-rule)"
						style:border-radius="var(--g-r-pill)"
						style:background="var(--g-card-alt)"
						style:color="var(--g-ink-2)">{ch}</span
					>
				{/each}
			{/if}
		</div>
	{/if}

	{#if zeigeFusszeile}
		<div
			style:display="flex"
			style:align-items="center"
			style:justify-content="space-between"
			style:flex-wrap="wrap"
			style:gap="8px"
			style:padding-left="17px"
			style:padding-top="11px"
			style:border-top="1px dashed var(--g-rule-soft)"
		>
			{#if draft || scheduleText}
				<span style:font-family="var(--g-font-mono)" style:font-size="11px" style:color="var(--g-ink-3)" style:letter-spacing="0.02em"
					>{draft ? $t('bausteine.abo.setup_unvollstaendig') : scheduleText}</span
				>
			{/if}
			{#if nextSend !== undefined}
				<span
					data-field="next-send"
					style:font-size="11px"
					style:color="var(--g-ink-2)"
					style:flex-shrink="0">{$t('bausteine.abo.naechster', { zeit: nextSend ?? '—' })}</span
				>
			{/if}
			{#if !draft || versandGeliefert}
				<span
					data-field="last-sent"
					style:display="inline-flex"
					style:align-items="center"
					style:gap="6px"
					style:font-size="11px"
					style:color="var(--g-ink-3)"
					style:flex-shrink="0"
				>
					<svg width="6" height="6" viewBox="0 0 6 6" style:display="block">
						<circle cx="3" cy="3" r="3" fill={dotColor(active)} />
					</svg>
					{$t('bausteine.abo.zuletzt', { zeit: lastSentText || '—' })}
				</span>
			{/if}
		</div>
	{/if}
</div>
