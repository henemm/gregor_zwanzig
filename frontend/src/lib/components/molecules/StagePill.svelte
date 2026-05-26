<script lang="ts">
	// Issue #372 — StagePill-Molecule (kanonisch aus molecules.jsx, Svelte 5).
	//
	// Etappen-Kachel fuer Etappen-Streifen / Trip-Verlauf. State-getriebenes
	// Prop-Modell (D7): state active|done|future|muted, exponiert als data-state.
	// Backward-compatible mit den boolschen Original-Props (active/done/muted).
	// Risk-Farbe token-basiert.
	//
	// Spec: docs/specs/modules/issue_372_molecules.md (AC-4)

	type StageState = 'active' | 'done' | 'future' | 'muted';

	interface Stage {
		code: string;
		risk?: 'high' | 'med' | 'low' | string;
	}

	interface Props {
		stage: Stage;
		state?: StageState;
		active?: boolean;
		done?: boolean;
		muted?: boolean;
		class?: string;
	}

	let { stage, state, active, done, muted, class: className = '' }: Props = $props();

	// Boolean-Props auf state mappen, falls state nicht gesetzt; unbekannte
	// state-Werte fallen auf 'future' zurueck (kein Crash).
	const known: StageState[] = ['active', 'done', 'future', 'muted'];
	const s = $derived<StageState>(
		state && known.includes(state)
			? state
			: active
				? 'active'
				: done
					? 'done'
					: muted
						? 'muted'
						: 'future'
	);

	const isActive = $derived(s === 'active');
	const isMuted = $derived(s === 'muted');

	const riskTone = $derived(
		stage.risk === 'high'
			? 'var(--g-bad)'
			: stage.risk === 'med'
				? 'var(--g-warn)'
				: 'var(--g-good)'
	);

	const background = $derived(
		isActive ? 'var(--g-accent-tint)' : isMuted ? 'var(--g-paper-deep)' : 'var(--g-card-alt)'
	);
</script>

<div
	class={className}
	data-state={s}
	style:flex="1"
	style:min-width="0"
	style:padding="8px 10px"
	style:background={background}
	style:border={isActive ? '1px solid var(--g-accent)' : '1px solid var(--g-rule-soft)'}
	style:border-radius="var(--g-r-2)"
	style:opacity={isMuted ? 0.55 : 1}
>
	<div
		style:font-family="var(--g-font-mono)"
		style:font-size="10px"
		style:color={isActive ? 'var(--g-accent-deep)' : 'var(--g-ink-3)'}
		style:text-transform="uppercase"
		style:letter-spacing="0.06em"
		style:font-weight="500"
		style:white-space="nowrap"
		style:overflow="hidden"
		style:text-overflow="ellipsis"
	>{stage.code}</div>
	{#if !isMuted && stage.risk}
		<div style:margin-top="6px" style:height="3px" style:background={riskTone} style:border-radius="2px"></div>
	{/if}
</div>
