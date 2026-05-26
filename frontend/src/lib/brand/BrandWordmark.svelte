<script lang="ts">
	// BrandWordmark — kanonisches Lockup-Logo: Berg+Blitz-Glyph + Mono-Typo + Caption.
	// 1:1 portiert aus brand-kit.jsx. Drei Groessen (sm/md/lg); `icon`-Prop steuert die Komposition.
	import BrandIcon from './BrandIcon.svelte';

	interface Props {
		size?: 'sm' | 'md' | 'lg';
		dark?: boolean;
		caption?: string | null;
		icon?: 'left' | 'only' | 'none';
	}

	let {
		size = 'md',
		dark = false,
		caption = 'V0.20 · Wetter-Briefing',
		icon = 'left'
	}: Props = $props();

	type SizeSpec = { row: number; sub: number; gap: number; iconGap: number; iconPx: number };
	// iconPx exakt nach brand-kit.jsx (Claude-Design-Grundgesetz, 1:1): sm 20 / md 26 / lg 34.
	const SIZES: Record<string, SizeSpec> = {
		sm: { row: 14, sub: 8, gap: 2, iconGap: 8, iconPx: 20 },
		md: { row: 18, sub: 9, gap: 3, iconGap: 10, iconPx: 26 },
		lg: { row: 24, sub: 10, gap: 4, iconGap: 14, iconPx: 34 }
	};
	// Fallback auf md bei unbekanntem size.
	const s = $derived(SIZES[size] ?? SIZES.md);
	// Fallback auf left bei unbekanntem icon.
	const mode = $derived(icon === 'only' || icon === 'none' ? icon : 'left');

	const inkPrimary = $derived(dark ? 'var(--g-paper)' : 'var(--g-ink)');
	const inkDot = $derived(dark ? 'rgba(246,244,238,0.45)' : 'var(--g-ink-4)'); // audit:exempt — Wordmark/Logo-Glyph, kein Lesetext (WCAG §1.4.3)
	const inkCaption = $derived(dark ? 'rgba(246,244,238,0.55)' : 'var(--g-ink-muted)');

	const hasCaption = $derived(caption != null && caption !== '');
	// Caption als UPPERCASE-Textknoten (nicht nur via CSS text-transform), damit
	// der DOM-Text der visuellen Mono-Caps-Darstellung entspricht (Spec §9, AC-10).
	const captionText = $derived(hasCaption ? (caption as string).toUpperCase() : '');
	// Caption unter dem Schriftzug einruecken (um Icon-Breite + iconGap), damit sie
	// linksbuendig zum Schriftzug startet, nicht unter dem Symbol (icon="left").
	const captionIndent = $derived(s.iconPx + s.iconGap);
</script>

{#if mode === 'only'}
	<span data-testid="brand-wordmark" style="display:inline-flex;line-height:1">
		<BrandIcon size={s.iconPx * 1.6} color={inkPrimary} />
	</span>
{:else if mode === 'none'}
	<span data-testid="brand-wordmark" style="display:inline-block;line-height:1">
		<span class="typo-block" style="display:inline-block;line-height:1">
			<span
				class="typo-row"
				style="font-family:var(--g-font-mono);font-size:{s.row}px;font-weight:500;letter-spacing:0.04em;color:{inkPrimary};display:flex;align-items:baseline;line-height:1"
			>
				<span>gregor</span><span style:color={inkDot}>.</span><!-- audit:exempt: Markenname/Logo --><span style:color="var(--g-accent)">zwanzig</span>
			</span>
			{#if hasCaption}
				<span
					class="caption"
					style="display:block;font-family:var(--g-font-mono);font-size:{s.sub}px;font-weight:500;letter-spacing:0.18em;text-transform:uppercase;color:{inkCaption};margin-top:{s.gap}px"
				>{captionText}</span>
			{/if}
		</span>
	</span>
{:else}
	<span data-testid="brand-wordmark" style="display:inline-flex;flex-direction:column;line-height:1">
		<!-- Erste Reihe: Symbol + Schriftzug-Zeile auf einer Achse (Symbol-Mitte ≈ Schriftzug-Mitte) -->
		<span style="display:inline-flex;align-items:center;gap:{s.iconGap}px;line-height:1">
			<BrandIcon size={s.iconPx} color={inkPrimary} />
			<span
				class="typo-row"
				style="font-family:var(--g-font-mono);font-size:{s.row}px;font-weight:500;letter-spacing:0.04em;color:{inkPrimary};display:flex;align-items:baseline;line-height:1"
			>
				<span>gregor</span><span style:color={inkDot}>.</span><!-- audit:exempt: Markenname/Logo --><span style:color="var(--g-accent)">zwanzig</span>
			</span>
		</span>
		{#if hasCaption}
			<!-- Caption unter dem Schriftzug, eingerueckt um Symbol-Breite + iconGap -->
			<span
				class="caption"
				style="display:block;font-family:var(--g-font-mono);font-size:{s.sub}px;font-weight:500;letter-spacing:0.18em;text-transform:uppercase;color:{inkCaption};margin-top:{s.gap}px;margin-left:{captionIndent}px"
			>{captionText}</span>
		{/if}
	</span>
{/if}
