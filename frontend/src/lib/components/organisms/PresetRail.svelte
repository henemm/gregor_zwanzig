<script lang="ts">
	// Issue #578 — PresetRail-Organism.
	// Kanonische Quelle: organisms.jsx::PresetRail
	//
	// Linke Spalte des Metrics-Editors. Listet Wetter-Profile und
	// bietet einen "Eigenes Profil"-Block.

	import { Eyebrow, Btn } from '$lib/components/atoms';

	interface Preset {
		id: string;
		name: string;
		desc?: string;
		builtin?: boolean;
		metrics?: string[];
	}

	interface Props {
		presets?: Preset[];
		value?: string;
		onChange?: (id: string) => void;
		totalActive?: number;
		onSave?: () => void;
		compact?: boolean;
		class?: string;
	}

	let {
		presets = [],
		value = '',
		onChange,
		totalActive = 0,
		onSave,
		compact = false,
		class: className = ''
	}: Props = $props();
</script>

<div style:display="flex" style:flex-direction="column" style:gap="16px" class={className}>
	<div>
		<Eyebrow>Wetter-Profil</Eyebrow>
		<div style:font-size="13px" style:color="var(--g-ink-3)" style:margin-top="4px" style:line-height="1.5">
			Vorlage wählen oder eigenes Profil anlegen.
		</div>
	</div>

	<div style:display="flex" style:flex-direction="column" style:gap="4px">
		{#each presets as p (p.id)}
			<button
				onclick={() => onChange && onChange(p.id)}
				style:text-align="left"
				style:padding={compact ? '8px 11px' : '9px 12px'}
				style:background={p.id === value ? 'var(--g-accent-tint)' : 'transparent'}
				style:border-left={p.id === value ? '3px solid var(--g-accent)' : '3px solid transparent'}
				style:border-top="none"
				style:border-right="none"
				style:border-bottom="none"
				style:border-radius="var(--g-r-2)"
				style:cursor="pointer"
				style:font-family="inherit"
				style:width="100%"
			>
				<div style:display="flex" style:justify-content="space-between" style:align-items="baseline" style:gap="6px">
					<span
						style:font-size="13px"
						style:font-weight={p.id === value ? '600' : '500'}
						style:color={p.id === value ? 'var(--g-accent-deep)' : 'var(--g-ink)'}
					>
						{p.name}
						{#if !p.builtin}
							<!-- audit:exempt --><span
								style:margin-left="6px"
								style:font-size="9px"
								style:color="var(--g-accent)"
								style:letter-spacing="0.08em"
								style:font-family="var(--g-font-mono)"
							>EIGEN</span>
						{/if}
					</span>
					<span
						style:font-family="var(--g-font-mono)"
						style:font-size="10.5px"
						style:color="var(--g-ink-3)"
						style:font-weight="600"
					>{(p.metrics ?? []).length}</span>
				</div>
				{#if p.desc}
					<div style:font-size="11px" style:color="var(--g-ink-3)" style:margin-top="2px">{p.desc}</div>
				{/if}
			</button>
		{/each}
	</div>

	<!-- Eigenes Profil Block -->
	<div
		style:padding="12px"
		style:background="var(--g-card-alt)"
		style:border-radius="var(--g-r-3)"
		style:border="1px dashed var(--g-rule)"
	>
		<!-- audit:exempt: --g-ink-4 für Mono-Eyebrow (dekorativ/Label, JSX canonical) -->
		<div
			style:font-family="var(--g-font-mono)"
			style:font-size="10px"
			style:letter-spacing="0.1em"
			style:text-transform="uppercase"
			style:color="var(--g-ink-4)"
			style:margin-bottom="6px"
		>Eigenes Profil</div>
		<div style:font-size="12px" style:color="var(--g-ink-2)" style:line-height="1.45" style:margin-bottom="8px">
			Aktuelle Auswahl ({totalActive} Metriken) als Profil sichern.
		</div>
		<Btn variant="ghost" size="sm" style="width: 100%" onclick={onSave}>
			+ Als Profil speichern
		</Btn>
	</div>
</div>
