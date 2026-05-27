<script lang="ts">
	// Issue #372 — AlertRow-Molecule (kanonisch aus molecules.jsx, Svelte 5).
	//
	// Eine Alert-/Warn-Meldung in einer Liste. Drei Varianten:
	//   variant="icon"  — WIcon links (Wetter-Symbol je nach alert.kind).
	//   variant="dot"   — kleiner Accent-Dot-Marker, kein Wetter-Icon.
	//   variant="plain" — nur when + msg, kein Marker.
	//
	// alert: { kind, when, msg, channel? }
	// last: unterdrueckt den Bottom-Divider. divider: dashed|solid|none.
	//
	// Kontrast: when nutzt --g-ink-3 statt Vorlagen-Wert --g-ink-3 (bereits AA).
	//
	// Spec: docs/specs/modules/issue_372_molecules.md (AC-4)

	import { WIcon } from '$lib/components/atoms';
	import type { WIconKind } from '$lib/utils/weatherUtils.js';

	type Variant = 'icon' | 'dot' | 'plain';
	type Divider = 'dashed' | 'solid' | 'none';

	interface Alert {
		kind: string;
		when?: string;
		msg?: string;
		channel?: string;
	}

	interface Props {
		alert: Alert;
		variant?: Variant;
		last?: boolean;
		divider?: Divider;
		class?: string;
	}

	let {
		alert,
		variant = 'icon',
		last = false,
		divider = 'dashed',
		class: className = ''
	}: Props = $props();

	// Unbekannte variant/divider -> Default-Fallback (kein Crash).
	const resolvedVariant = $derived<Variant>(
		variant === 'icon' || variant === 'dot' || variant === 'plain' ? variant : 'icon'
	);
	const resolvedDivider = $derived<Divider>(
		divider === 'dashed' || divider === 'solid' || divider === 'none' ? divider : 'dashed'
	);

	const TONE_MAP: Record<string, 'bad' | 'warn'> = {
		'thunder': 'bad',
		'thunder_level': 'bad',
	};
	const tone = $derived<'bad' | 'warn'>(TONE_MAP[alert.kind] ?? 'warn');
	const toneColor = $derived(tone === 'bad' ? 'var(--g-bad)' : 'var(--g-warn)');

	const KIND_MAP: Record<string, WIconKind> = {
		'thunder': 'thunder',
		'thunder_level': 'thunder',
		'wind': 'wind',
		'wind_gust': 'wind',
		'wind_change': 'wind',
		'rain': 'rain',
		'precipitation_sum': 'rain',
		'precipitation_change': 'rain',
		'snow': 'snow',
		'snow_line': 'snow',
		'sun': 'sun',
		'temperature': 'sun',
		'temperature_min': 'sun',
		'temperature_max': 'sun',
		'temperature_change': 'sun',
	};
	const iconKind = $derived<WIconKind>(KIND_MAP[alert.kind] ?? 'wind');
	const borderBottom = $derived(
		last || resolvedDivider === 'none' ? 'none' : `1px ${resolvedDivider} var(--g-rule-soft)`
	);
</script>

<div
	class={className}
	style:display="flex"
	style:gap="10px"
	style:padding="10px 0"
	style:border-bottom={borderBottom}
>
	{#if resolvedVariant === 'icon'}
		<div style:margin-top="2px" style:flex-shrink="0">
			<WIcon kind={iconKind} size={18} color={toneColor} />
		</div>
	{:else if resolvedVariant === 'dot'}
		<div style:padding-top="6px" style:flex-shrink="0">
			<span
				style:display="inline-block"
				style:width="6px"
				style:height="6px"
				style:border-radius="50%"
				style:background="var(--g-accent)"
			></span>
		</div>
	{/if}
	<div style:flex="1" style:min-width="0">
		<div
			style:font-family="var(--g-font-mono)"
			style:font-size="11px"
			style:color="var(--g-ink-3)"
			style:margin-bottom="2px"
		>
			{alert.when}{#if alert.channel}<span> · {alert.channel}</span>{/if}
		</div>
		<div style:font-size="13px" style:color="var(--g-ink)" style:line-height="1.4">{alert.msg}</div>
	</div>
</div>
