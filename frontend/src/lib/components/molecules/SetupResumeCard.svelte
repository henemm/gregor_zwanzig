<script lang="ts">
	// Issue #568 — SetupResumeCard-Molecule (Startseite-Planungs-Zustand).
	// Spec: docs/specs/modules/issue_568_home_redesign.md
	// Issue #573 — Charter-Compliance-Fix: <Dot> statt ✓/○, <Btn> statt hand-styled <a>,
	//              Token-Fixes (--g-good, --g-paper, letter-spacing).
	//
	// Zeigt einen offenen Wizard mit Schritt-Checkliste + Fortschrittsbalken +
	// CTA-Button („Setup fortsetzen"). tone='accent' = Trip (Akzent-Farbe),
	// tone='default' = Vergleich. CTA-Touch-Target ≥ 44 px (AC-7).

	import { Btn } from '$lib/components/atoms';

	interface Step {
		label: string;
		done: boolean;
	}

	interface Props {
		eyebrow: string;
		title: string;
		subtitle?: string;
		steps: Step[];
		ctaLabel: string;
		ctaHref: string;
		secondary?: { label: string; href: string };
		tone?: 'accent' | 'default';
		class?: string;
	}

	let {
		eyebrow,
		title,
		subtitle,
		steps,
		ctaLabel,
		ctaHref,
		secondary,
		tone = 'default',
		class: className = ''
	}: Props = $props();

	const isAccent = $derived(tone === 'accent');
	const total = $derived(steps?.length ?? 0);
	const doneCount = $derived((steps ?? []).filter((s) => s.done).length);
	const donePct = $derived(total > 0 ? Math.round((doneCount / total) * 100) : 0);

	const barColor = $derived(isAccent ? 'var(--g-accent)' : 'var(--g-ink-2)');
	const nextStep = $derived(steps.find((s) => !s.done));
</script>

<article
	class={className}
	data-tone={tone}
	style:background="var(--g-card)"
	style:border="1px solid var(--g-rule)"
	style:border-left={isAccent ? '3px solid var(--g-accent)' : undefined}
	style:border-radius="var(--g-r-3)"
	style:padding="var(--g-s-5) var(--g-s-6)"
	style:display="flex"
	style:flex-direction="column"
	style:gap="var(--g-s-3)"
	style:box-shadow="var(--g-shadow-1)"
>
	<header style:display="flex" style:flex-direction="column" style:gap="var(--g-s-1)">
		<span
			style:font-family="var(--g-font-mono)"
			style:font-size="var(--g-text-xs)"
			style:text-transform="uppercase"
			style:letter-spacing="var(--g-track-caps)"
			style:color="var(--g-ink-3)"
		>{eyebrow}</span>
		<h3
			style:margin="0"
			style:font-size="var(--g-text-xl)"
			style:font-weight="600"
			style:line-height="1.2"
			style:letter-spacing="var(--g-track-tight)"
			style:color="var(--g-ink)"
		>{title}</h3>
		{#if subtitle}
			<p style:margin="0" style:font-size="var(--g-text-sm)" style:color="var(--g-ink-2)" style:line-height="1.5">
				{subtitle}
			</p>
		{/if}
	</header>

	<!-- Fortschrittsbalken -->
	<div style:display="flex" style:flex-direction="column" style:gap="var(--g-s-1)">
		<div
			style:height="4px"
			style:background="var(--g-rule-soft)"
			style:border-radius="2px"
			style:overflow="hidden"
		>
			<div
				style:height="100%"
				style:background={barColor}
				style:border-radius="2px"
				style:width="{donePct}%"
				style:transition="width 300ms ease"
			></div>
		</div>
		<div
			style:font-family="var(--g-font-mono)"
			style:font-size="var(--g-text-xs)"
			style:color="var(--g-ink-3)"
		>{doneCount} von {total} Schritten</div>
	</div>

	<!-- Schritt-Chips -->
	<div style:display="flex" style:flex-wrap="wrap" style:gap="7px">
		{#each steps as step (step.label)}
			<span
				style:display="inline-flex"
				style:align-items="center"
				style:gap="6px"
				style:padding="5px 11px 5px 8px"
				style:border-radius="var(--g-r-pill)"
				style:font-size="12px"
				style:font-weight="500"
				style:border="1px solid {step.done ? 'var(--g-rule-soft)' : 'var(--g-rule)'}"
				style:background="{step.done ? 'var(--g-card-alt)' : 'var(--g-card)'}"
				style:color="{step.done ? 'var(--g-ink-3)' : 'var(--g-ink)'}"
			>
				{#if step.done}
					<span style:width="15px" style:height="15px" style:border-radius="50%"
						style:background="var(--g-good)" style:display="inline-flex"
						style:align-items="center" style:justify-content="center" style:flex-shrink="0">
						<svg width="9" height="9" viewBox="0 0 12 12" fill="none" stroke="#fff" stroke-width="2.4">
							<path d="M2 6l3 3 5-6"/>
						</svg>
					</span>
				{:else}
					<span style:width="15px" style:height="15px" style:border-radius="50%"
						style:border="1.5px dashed var(--g-ink-4)" style:flex-shrink="0"></span>
				{/if}
				{step.label}
			</span>
		{/each}
	</div>

	<!-- Footer-Leiste -->
	<div
		style:border-top="1px solid var(--g-rule-soft)"
		style:padding="14px 26px"
		style:background="var(--g-card-alt)"
		style:display="flex"
		style:align-items="center"
		style:justify-content="space-between"
		style:gap="12px"
		style:margin="0 calc(-1 * var(--g-s-6)) calc(-1 * var(--g-s-5))"
		style:border-radius="0 0 var(--g-r-3) var(--g-r-3)"
	>
		<span style:font-family="var(--g-font-mono)" style:font-size="11px" style:color="var(--g-ink-3)">
			{#if nextStep}Weiter bei: <span style:color="var(--g-ink-2)" style:font-weight="600">{nextStep.label}</span>
			{:else}Bereit zum Aktivieren{/if}
		</span>
		<div style:display="flex" style:gap="8px">
			{#if secondary}
				<Btn href={secondary.href} variant="ghost" size="sm">{secondary.label}</Btn>
			{/if}
			<Btn href={ctaHref} variant={isAccent ? 'accent' : 'primary'} size="sm">{ctaLabel} →</Btn>
		</div>
	</div>
</article>
