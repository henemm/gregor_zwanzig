<script lang="ts">
	// Issue #374 — Showcase-Route /_design-system (Epic #368).
	//
	// Rendert ALLE Brand-, Atom-, Molecule- und Mobile-Bausteine in allen
	// Varianten. Zweck: visuelle Gesamt-Abnahme des Atomic-Pakets (#370–#373)
	// + Regressions-Referenz. Dass diese Route die echten Komponenten importiert
	// und fehlerfrei kompiliert, ist der Integrationsbeweis.
	//
	// Vorlage: docs/design-requests/issue_15_atomic_design/spec/screen-design-system.jsx
	// Spec:    docs/specs/modules/issue_374_showcase.md
	//
	// Organisms/Templates bewusst NICHT enthalten (Out of Scope, #364/Epic #368).
	// Demo-Helfer (Section/Swatch/PhoneFrame/MobileStatusBar) sind LOKAL —
	// Showcase-spezifisch, NICHT Bibliothek.
	//
	// Kontrast (#377): Mono-Demo-Labels nutzen --g-ink-3 (AA) statt des Vorlagen-
	// Werts --g-ink-4 (FAIL als Textfarbe). Demo-CSS durchgaengig var(--g-*).

	import type { Snippet } from 'svelte';

	// Schicht 1 — Brand (#370)
	import { BrandWordmark, BrandIcon, BrandIconSquare } from '$lib/brand';

	// Schicht 2 — Atoms (#371)
	import {
		Pill,
		Btn,
		Input,
		Switch,
		WIcon,
		Dot,
		Eyebrow,
		SectionH,
		AvatarStack,
		TopoBg
	} from '$lib/components/atoms';

	// Schicht 3 — Molecules (#372)
	import {
		Field,
		DetailRow,
		StagePill,
		ChannelRow,
		ChannelChip,
		Stat,
		AlertRow,
		BriefingTimelineRow,
		BriefingScheduleRow,
		ThresholdRow
	} from '$lib/components/molecules';

	// Schicht 4 — Mobile (#373)
	import { MBtn, MSwitch, MTab, Sheet, Toast, MobileShell } from '$lib/components/mobile';
	import type { MTabItem } from '$lib/components/mobile';

	// ── Type-Scale (Vorlage §02) ──────────────────────────────────────────────
	const TYPE_SCALE = [
		{ l: 'Display 5xl · 60', s: 60, w: 600, t: 'Karnischer Höhenweg' },
		{ l: 'Display 4xl · 44', s: 44, w: 600, t: 'Heute geht ein Report raus.' },
		{ l: 'Title 3xl · 32', s: 32, w: 600, t: 'KHW_00a · Toblach → Helmhotel' },
		{ l: 'Title 2xl · 24', s: 24, w: 600, t: 'Etappen-Übersicht' },
		{ l: 'Heading xl · 20', s: 20, w: 600, t: 'Wegpunkt-Editor' },
		{ l: 'Body lg · 17', s: 17, w: 400, t: 'Vor dem Trip aktualisierst du am Desktop, unterwegs liest du SMS.' },
		{ l: 'Body md · 15', s: 15, w: 400, t: '8–12°C, trocken, Regen ab 11:00, schwacher Wind NE 12 km/h.' },
		{ l: 'Caption sm · 13', s: 13, w: 500, t: 'Letzter Sync: 06:01 UTC · openmeteo (icon_d2)' },
		{ l: 'Eyebrow xs · 11', s: 11, w: 500, t: 'MORNING REPORT · 06.05.2026', caps: true, mono: true }
	] as const;

	// ── Farben-Swatches (Vorlage §03) ─────────────────────────────────────────
	const SURFACE_COLORS = [
		{ v: 'var(--g-paper)', n: 'paper', hex: '#f6f4ee' },
		{ v: 'var(--g-paper-deep)', n: 'paper-deep', hex: '#ecead9' },
		{ v: 'var(--g-card)', n: 'card', hex: '#ffffff' },
		{ v: 'var(--g-card-alt)', n: 'card-alt', hex: '#faf8f1' },
		{ v: 'var(--g-rule)', n: 'rule', hex: '#d8d3c2' }
	];
	// audit:exempt — Swatch-Daten: v ist Hintergrund-Fuellung der Farbprobe (§1.4.11),
	// niemals Textfarbe. --g-ink-4 / --g-accent erscheinen hier als FLAECHE, nicht Text.
	const INK_COLORS = [
		{ v: 'var(--g-ink)', n: 'ink', hex: '#1a1a18' },
		{ v: 'var(--g-ink-2)', n: 'ink-2', hex: '#45433d' },
		{ v: 'var(--g-ink-3)', n: 'ink-3', hex: '#6b675c' },
		{ v: 'var(--g-ink-4)', n: 'ink-4', hex: '#9a958a' } // audit:exempt — Swatch-Flaeche
	];
	// audit:exempt — Swatch-Daten: v ist Hintergrund-Fuellung der Farbprobe (§1.4.11).
	const ACCENT_COLORS = [
		{ v: 'var(--g-accent-deep)', n: 'accent-deep', hex: '#8c3e1a' },
		{ v: 'var(--g-accent)', n: 'accent', hex: '#c45a2a' }, // audit:exempt — Swatch-Flaeche
		{ v: 'var(--g-accent-soft)', n: 'accent-soft', hex: '#f3d9c8' }
	];
	const SEMANTIC_COLORS = [
		{ v: 'var(--g-success)', n: 'good', hex: '#3d6b3a' },
		{ v: 'var(--g-warning)', n: 'warn', hex: '#c08a1a' },
		{ v: 'var(--g-danger)', n: 'bad', hex: '#a83232' },
		{ v: 'var(--g-info)', n: 'info', hex: '#2c5a8c' }
	];
	const WEATHER_COLORS = [
		{ v: 'var(--g-wx-rain)', n: 'rain', hex: '#4a7fb5' },
		{ v: 'var(--g-wx-snow)', n: 'snow', hex: '#a8c8e8' },
		{ v: 'var(--g-wx-thunder)', n: 'thunder', hex: '#c43a2a' },
		{ v: 'var(--g-wx-sun)', n: 'sun', hex: '#e8a820' },
		{ v: 'var(--g-wx-fog)', n: 'fog', hex: '#9a9a8a' }
	];

	const WICON_KINDS = ['sun', 'cloud', 'rain', 'thunder', 'snow', 'wind', 'moon', 'headlamp'] as const;

	const DEMO_USERS = [
		{ name: 'Henning Emmrich', initials: 'HE' },
		{ name: 'Gregor Zwanzig', initials: 'GZ' },
		{ name: 'Test User', initials: 'TU' }
	];

	const REPORT_TIMELINE = [
		{ when: '06:00', kind: 'morning', etappe: 'KHW_03 · Obstanser See', channels: ['email'], status: 'sent' },
		{ when: '18:00', kind: 'evening', etappe: 'KHW_04 · Filmoor', channels: ['email'], status: 'planned' }
	];

	// ── Atom-Demo: Switch-State (Vorlage SwitchRow) ───────────────────────────
	let swGood = $state(true);
	let swAccent = $state(true);
	let swInfo = $state(true);
	let swA = $state(true);
	let swB = $state(true);
	let swC = $state(true);

	// ── Mobile-Demo State (PhoneFrame mit MobileShell — F001-Toggle live) ──────
	let mobileMenuOpen = $state(false);
	let sheetOpen = $state(false);
	let mSwitch = $state(true);
	let mActiveTab = $state('heute');
	const MOBILE_TABS: MTabItem[] = [
		{ id: 'heute', label: 'Heute' },
		{ id: 'etappen', label: 'Etappen', badge: 9 },
		{ id: 'alerts', label: 'Alerts', badge: 2, accent: true },
		{ id: 'config', label: 'Konfiguration' }
	];

	function toggleMobileMenu() {
		mobileMenuOpen = !mobileMenuOpen;
	}
</script>

<!-- ════════════════════════════════════════════════════════════════════════
     Lokale Demo-Helfer (Showcase-spezifisch, NICHT Bibliothek)
     ═══════════════════════════════════════════════════════════════════════ -->
{#snippet Section(eyebrow: string, title: string, kicker: string, body: Snippet)}
	<section style:margin-bottom="56px">
		<div
			style:display="flex"
			style:align-items="baseline"
			style:gap="16px"
			style:margin-bottom="18px"
			style:padding-bottom="12px"
			style:border-bottom="1px solid var(--g-rule)"
		>
			<span
				class="mono"
				style:font-size="12px"
				style:color="var(--g-accent-deep)"
				style:font-weight="500">{eyebrow}</span
			>
			<div style:font-size="22px" style:font-weight="600" style:letter-spacing="-0.01em">{title}</div>
		</div>
		{#if kicker}
			<div style:color="var(--g-ink-3)" style:font-size="14px" style:max-width="700px" style:margin-bottom="18px">
				{kicker}
			</div>
		{/if}
		{@render body()}
	</section>
{/snippet}

{#snippet Panel(label: string, body: Snippet)}
	<div
		style:background="var(--g-card)"
		style:border="1px solid var(--g-rule)"
		style:border-radius="var(--g-r-3)"
		style:padding="24px"
	>
		{#if label}
			<div
				class="mono"
				style:font-size="11px"
				style:color="var(--g-ink-3)"
				style:letter-spacing="var(--g-track-caps)"
				style:text-transform="uppercase"
				style:margin-bottom="14px"
				style:font-weight="500">{label}</div
			>
		{/if}
		{@render body()}
	</div>
{/snippet}

{#snippet Swatch(v: string, n: string, hex: string)}
	<div
		style:border="1px solid var(--g-rule)"
		style:border-radius="var(--g-r-3)"
		style:overflow="hidden"
		style:background="var(--g-card)"
	>
		<div style:height="60px" style:background={v} style:border-bottom="1px solid var(--g-rule-soft)"></div>
		<div style:padding="8px 10px">
			<div class="mono" style:font-size="11px" style:font-weight="500" style:color="var(--g-ink)">{n}</div>
			<div class="mono" style:font-size="10px" style:color="var(--g-ink-3)">{hex}</div>
		</div>
	</div>
{/snippet}

{#snippet ColorRow(label: string, colors: { v: string; n: string; hex: string }[])}
	<div style:margin-bottom="16px">
		<div
			class="mono"
			style:font-size="10px"
			style:color="var(--g-ink-3)"
			style:text-transform="uppercase"
			style:letter-spacing="var(--g-track-caps)"
			style:margin-bottom="6px">{label}</div
		>
		<div style:display="grid" style:grid-template-columns="repeat(5, 1fr)" style:gap="12px">
			{#each colors as c (c.n)}
				{@render Swatch(c.v, c.n, c.hex)}
			{/each}
		</div>
	</div>
{/snippet}

{#snippet MonoTag(text: string)}
	<span
		class="mono"
		style:font-size="10px"
		style:color="var(--g-ink-3)"
		style:letter-spacing="0.1em"
		style:text-transform="uppercase">{text}</span
	>
{/snippet}

<!-- PhoneFrame: lokaler Bezel-Rahmen fuer die Mobile-Demo (Showcase-spezifisch). -->
{#snippet PhoneFrame(body: Snippet)}
	<div
		style:width="360px"
		style:height="640px"
		style:border="10px solid var(--g-ink)"
		style:border-radius="40px"
		style:overflow="hidden"
		style:background="var(--g-paper)"
		style:box-shadow="var(--g-shadow-3)"
		style:position="relative"
		style:flex-shrink="0"
	>
		{@render body()}
	</div>
{/snippet}

<!-- ════════════════════════════════════════════════════════════════════════
     Seite
     ═══════════════════════════════════════════════════════════════════════ -->
<div
	style:padding="56px"
	style:background="var(--g-paper)"
	style:min-height="100%"
	style:position="relative"
	style:overflow="hidden"
>
	<TopoBg opacity={0.18} />
	<div style:position="relative" style:max-width="1320px">
		<!-- Header -->
		<div style:margin-bottom="40px">
			<Eyebrow>System · v2 · Alpine-modern</Eyebrow>
			<div style:font-size="44px" style:font-weight="600" style:letter-spacing="-0.02em" style:margin-top="6px" style:line-height="1.05">
				Gregor 20 Design-System
			</div>
			<div style:font-size="16px" style:color="var(--g-ink-3)" style:max-width="640px" style:margin-top="10px">
				Alpin, präzise, datenehrlich. Inter Tight für UI · JetBrains Mono für alle Zahlen, Koordinaten,
				Zeiten · Topo-Linien als ruhige Hintergrund-Stimmung. Alles als CSS-Variablen.
			</div>
		</div>

		<!-- ═══ 01 · Brand ═══════════════════════════════════════════════════ -->
		{#snippet brandBody()}
			{#snippet lockupSizes()}
				<div style:display="flex" style:flex-direction="column" style:gap="28px" style:align-items="flex-start">
					<BrandWordmark size="sm" />
					<BrandWordmark size="md" />
					<BrandWordmark size="lg" />
				</div>
			{/snippet}
			<div style:margin-bottom="16px">
				{@render Panel('Lockup · drei Größen', lockupSizes)}
			</div>

			<div style:display="grid" style:grid-template-columns="1fr 1fr" style:gap="16px" style:margin-bottom="16px">
				<div
					style:background="var(--g-ink)"
					style:border-radius="var(--g-r-3)"
					style:padding="24px"
				>
					<div
						class="mono"
						style:font-size="11px"
						style:color="var(--g-paper)"
						style:letter-spacing="var(--g-track-caps)"
						style:text-transform="uppercase"
						style:margin-bottom="18px"
						style:opacity="0.75">Auf dunkel</div
					>
					<BrandWordmark size="md" dark />
				</div>

				{#snippet iconSquareBody()}
					<div style:display="flex" style:gap="16px" style:align-items="center">
						<BrandIconSquare size={64} />
						<BrandIconSquare size={48} />
						<BrandIconSquare size={32} />
						<BrandIconSquare size={16} />
						{@render MonoTag('Favicon · Avatar · App-Icon')}
					</div>
				{/snippet}
				{@render Panel('Icon-only · square Kontexte', iconSquareBody)}
			</div>

			{#snippet brandIconBody()}
				<div style:display="flex" style:gap="20px" style:align-items="center">
					<BrandIcon size="sm" />
					<BrandIcon size="md" />
					<BrandIcon size="lg" />
					{@render MonoTag('BrandIcon · Berg+Blitz-Glyph')}
				</div>
			{/snippet}
			<div style:margin-bottom="16px">
				{@render Panel('BrandIcon · Bildmark allein', brandIconBody)}
			</div>

			{#snippet iconPropBody()}
				<div style:display="grid" style:grid-template-columns="180px 1fr" style:gap="14px 20px" style:align-items="center">
					{@render MonoTag('icon="left" (default)')}
					<BrandWordmark size="md" icon="left" />
					{@render MonoTag('icon="only"')}
					<BrandWordmark size="md" icon="only" />
					{@render MonoTag('icon="none"')}
					<BrandWordmark size="md" icon="none" />
				</div>
			{/snippet}
			{@render Panel('Icon-Varianten via icon-Prop', iconPropBody)}
		{/snippet}
		{@render Section('01', 'Brand', 'Berg+Blitz-Glyph + Mono-Lockup. EINE Quelle (brand-kit) — keine zweite Geometrie irgendwo im Projekt.', brandBody)}

		<!-- ═══ 02 · Typografie ══════════════════════════════════════════════ -->
		{#snippet typoBody()}
			<div style:display="grid" style:grid-template-columns="180px 1fr" style:gap="12px" style:align-items="baseline">
				{#each TYPE_SCALE as r (r.l)}
					<div
						class="mono"
						style:font-size="11px"
						style:color="var(--g-ink-3)"
						style:text-transform="uppercase"
						style:letter-spacing="var(--g-track-caps)">{r.l}</div
					>
					<div
						style:font-size="{r.s}px"
						style:font-weight={r.w}
						style:letter-spacing={r.s >= 32 ? 'var(--g-track-tight)' : 'caps' in r && r.caps ? 'var(--g-track-caps)' : '0'}
						style:text-transform={'caps' in r && r.caps ? 'uppercase' : 'none'}
						style:font-family={'mono' in r && r.mono ? 'var(--g-font-mono)' : 'var(--g-font-sans)'}
						style:color="var(--g-ink)"
						style:line-height="1.15"
					>
						{r.t}
					</div>
				{/each}
			</div>
		{/snippet}
		{@render Section('02', 'Typografie', '', typoBody)}

		<!-- ═══ 03 · Farben ══════════════════════════════════════════════════ -->
		{#snippet farbenBody()}
			{@render ColorRow('Surfaces', SURFACE_COLORS)}
			{@render ColorRow('Ink', INK_COLORS)}
			{@render ColorRow('Accent', ACCENT_COLORS)}
			{@render ColorRow('Semantic', SEMANTIC_COLORS)}
			{@render ColorRow('Wetter', WEATHER_COLORS)}
		{/snippet}
		{@render Section('03', 'Farben', 'Paper-Off-White als Bühne, Burnt-Orange als einziger Markenakzent. Wetter-Farben aus dem echten Email-Briefing abgeleitet.', farbenBody)}

		<!-- ═══ 04 · Bausteine (Atoms) ═══════════════════════════════════════ -->
		{#snippet bausteineBody()}
			<div style:display="grid" style:grid-template-columns="1fr 1fr" style:gap="24px">
				<!-- Pills -->
				{#snippet pillsBody()}
					<div style:display="flex" style:flex-wrap="wrap" style:gap="8px">
						<Pill tone="neutral">Neutral</Pill>
						<Pill tone="accent">Accent</Pill>
						<Pill tone="good">Trocken</Pill>
						<Pill tone="warn">Böen 35 km/h</Pill>
						<Pill tone="bad">Gewitter 78%</Pill>
						<Pill tone="ghost">Archiviert</Pill>
					</div>
				{/snippet}
				{@render Panel('Pills', pillsBody)}

				<!-- Buttons -->
				{#snippet buttonsBody()}
					<div style:display="flex" style:flex-wrap="wrap" style:gap="8px" style:align-items="center">
						<Btn variant="primary">Trip starten</Btn>
						<Btn variant="accent">Report jetzt senden</Btn>
						<Btn variant="ghost">Archivieren</Btn>
						<Btn variant="quiet">Abbrechen</Btn>
						<Btn size="xs" variant="ghost">+ Wegpunkt</Btn>
						<Btn size="sm" variant="outline">sm</Btn>
						<Btn size="md" variant="primary">md</Btn>
						<Btn size="lg" variant="primary">lg</Btn>
					</div>
				{/snippet}
				{@render Panel('Buttons · Varianten + 4 Größen', buttonsBody)}

				<!-- Inputs -->
				{#snippet inputsBody()}
					<div style:display="flex" style:flex-direction="column" style:gap="10px">
						<Input size="sm" placeholder="Suche…" />
						<Input size="md" placeholder="Trip-Name" value="Karnischer Höhenweg" />
						<Input size="lg" placeholder="Email" type="email" />
						<Input size="md" placeholder="überzogen" error />
					</div>
				{/snippet}
				{@render Panel('Input · drei Größen', inputsBody)}

				<!-- Switch -->
				{#snippet switchBody()}
					<div style:display="flex" style:flex-direction="column" style:gap="14px">
						<div style:display="flex" style:align-items="center" style:gap="12px">
							<Switch bind:checked={swGood} tone="good" aria-label="good" />
							<span style:font-size="13px" style:color="var(--g-ink-2)">good (default)</span>
						</div>
						<div style:display="flex" style:align-items="center" style:gap="12px">
							<Switch bind:checked={swAccent} tone="accent" aria-label="accent" />
							<span style:font-size="13px" style:color="var(--g-ink-2)">accent</span>
						</div>
						<div style:display="flex" style:align-items="center" style:gap="12px">
							<Switch bind:checked={swInfo} tone="info" aria-label="info" />
							<span style:font-size="13px" style:color="var(--g-ink-2)">info</span>
						</div>
						<div style:display="flex" style:align-items="center" style:gap="12px">
							<Switch checked tone="warn" aria-label="warn" />
							<span style:font-size="13px" style:color="var(--g-ink-2)">warn</span>
						</div>
						<div style:display="flex" style:align-items="center" style:gap="12px">
							<Switch checked tone="bad" aria-label="bad" />
							<span style:font-size="13px" style:color="var(--g-ink-2)">bad</span>
						</div>
						<div
							style:display="flex"
							style:gap="18px"
							style:align-items="center"
							style:padding-top="6px"
							style:border-top="1px dashed var(--g-rule-soft)"
						>
							<Switch bind:checked={swA} size="sm" aria-label="sm" />
							<Switch bind:checked={swB} size="md" aria-label="md" />
							<Switch bind:checked={swC} size="lg" aria-label="lg" />
							{@render MonoTag('sm · md · lg')}
						</div>
					</div>
				{/snippet}
				{@render Panel('Switch · 3 Größen × 5 Tones', switchBody)}

				<!-- Wetter-Icons -->
				{#snippet wiconBody()}
					<div style:display="flex" style:flex-wrap="wrap" style:gap="18px" style:align-items="center">
						{#each WICON_KINDS as k (k)}
							<div style:text-align="center">
								<WIcon kind={k} size={28} color="var(--g-ink-2)" />
								<div
									class="mono"
									style:font-size="10px"
									style:color="var(--g-ink-3)"
									style:margin-top="4px"
									style:text-transform="uppercase"
									style:letter-spacing="0.08em">{k}</div
								>
							</div>
						{/each}
					</div>
				{/snippet}
				{@render Panel('Wetter-Icons (WIcon · alle kinds)', wiconBody)}

				<!-- Dot / Eyebrow / SectionH / AvatarStack -->
				{#snippet miscBody()}
					<div style:display="flex" style:flex-direction="column" style:gap="18px">
						<div style:display="flex" style:align-items="center" style:gap="14px">
							<Dot tone="good" />
							<Dot tone="warn" />
							<Dot tone="bad" />
							<Dot tone="info" />
							<Dot tone="accent" />
							<Dot tone="neutral" />
							{@render MonoTag('Dot · Tones')}
						</div>
						<div>
							<Eyebrow>Eyebrow · Mono-Caps-Label</Eyebrow>
						</div>
						<SectionH eyebrow="Abschnitt" title="SectionH" kicker="Eyebrow + Titel + Kicker." />
						<div style:display="flex" style:align-items="center" style:gap="14px">
							<AvatarStack users={DEMO_USERS} />
							{@render MonoTag('AvatarStack')}
						</div>
					</div>
				{/snippet}
				{@render Panel('Dot · Eyebrow · SectionH · AvatarStack', miscBody)}
			</div>
		{/snippet}
		{@render Section('04', 'Bausteine', '', bausteineBody)}

		<!-- ═══ 05 · Molecules ═══════════════════════════════════════════════ -->
		{#snippet moleculesBody()}
			<div style:display="grid" style:grid-template-columns="1fr 1fr" style:gap="16px" style:margin-bottom="16px">
				<!-- Field -->
				{#snippet fieldBody()}
					<Field label="Trip-Name">
						<Input placeholder="z.B. KHW 403" value="Karnischer Höhenweg 403" />
					</Field>
					<Field label="Email" hint="Wird für Login + Versand verwendet.">
						<Input placeholder="gregor@..." type="email" />
					</Field>
					<Field label="Passwort" error="Mindestens 8 Zeichen">
						<Input type="password" value="x" error />
					</Field>
				{/snippet}
				{@render Panel('Field · unified form-field wrapper', fieldBody)}

				<!-- DetailRow -->
				{#snippet detailRowBody()}
					<DetailRow label="Strecke" value="14.2 km" />
					<DetailRow label="Auf-/Abstieg" value="↑ 980 ↓ 720" />
					<DetailRow label="Max-Höhe" value="2 412 m" sub="Birnlücke" />
					{#snippet riskPill()}
						<Pill tone="good">low</Pill>
					{/snippet}
					<DetailRow label="Risiko" right={riskPill} mono={false} divider="none" />
				{/snippet}
				{@render Panel('DetailRow · KV-Verallgemeinerung', detailRowBody)}
			</div>

			<!-- StagePill -->
			{#snippet stagePillBody()}
				<div style:display="flex" style:gap="4px">
					<StagePill stage={{ code: 'KHW_00', risk: 'low' }} state="done" />
					<StagePill stage={{ code: 'KHW_00a', risk: 'med' }} state="active" />
					<StagePill stage={{ code: 'KHW_01', risk: 'low' }} state="future" />
					<StagePill stage={{ code: 'KHW_02', risk: 'high' }} state="future" />
					<StagePill stage={{ code: 'KHW_03', risk: 'low' }} state="future" />
					<StagePill stage={{ code: 'KHW_04' }} state="muted" />
					<StagePill stage={{ code: 'KHW_05' }} state="muted" />
					<StagePill stage={{ code: 'KHW_06' }} state="muted" />
				</div>
				<div
					class="mono"
					style:font-size="10px"
					style:color="var(--g-ink-3)"
					style:letter-spacing="0.1em"
					style:text-transform="uppercase"
					style:margin-top="10px"
				>
					done · active · future · future-high-risk · future · muted · muted · muted
				</div>
			{/snippet}
			<div style:margin-bottom="16px">
				{@render Panel('StagePill · Etappen-Streifen (4 States)', stagePillBody)}
			</div>

			<div style:display="grid" style:grid-template-columns="1fr 1fr" style:gap="16px" style:margin-bottom="16px">
				<!-- ChannelRow Desktop -->
				{#snippet channelRowBody()}
					<div style:display="flex" style:flex-direction="column" style:gap="8px">
						<ChannelRow kind="Email" target="gregor_zwanzig@henemm.com" active />
						<ChannelRow kind="Telegram" target="@gregor_henemm" />
						<ChannelRow kind="SMS" target="+49 151 ••• 8847" sub="Fallback wenn andere Kanäle ausfallen" />
					</div>
				{/snippet}
				{@render Panel('ChannelRow · Konfigurations-Zeile (Desktop)', channelRowBody)}

				<!-- ChannelChip + ThresholdRow -->
				{#snippet chipThresholdBody()}
					<div style:display="flex" style:flex-wrap="wrap" style:gap="6px" style:margin-bottom="14px">
						<ChannelChip kind="email" />
						<ChannelChip kind="telegram" />
						<ChannelChip kind="sms" active={false} />
					</div>
					<div style:display="flex" style:gap="6px" style:margin-bottom="18px">
						<ChannelChip kind="email" compact />
						<ChannelChip kind="telegram" compact />
						<ChannelChip kind="sms" compact active={false} />
						{@render MonoTag('compact')}
					</div>
					{@render MonoTag('ThresholdRow · default')}
					<ThresholdRow label="Windböen" value="≥ 50 km/h" />
					<ThresholdRow label="Niederschlag" value="≥ 10 mm/h" />
					<ThresholdRow label="Gewitter-Wahrscheinlichkeit" value="≥ 40 %" />
					<ThresholdRow label="Schneefallgrenze" value="200 m unter Trip-Höhe" />
				{/snippet}
				{@render Panel('ChannelChip (default + compact) · ThresholdRow', chipThresholdBody)}
			</div>

			<!-- Stat -->
			{#snippet statBody()}
				<div style:display="grid" style:grid-template-columns="1fr 1fr" style:gap="24px">
					<div>
						{@render MonoTag('layout="stack" (default)')}
						<div style:display="flex" style:gap="32px" style:margin-top="10px">
							<Stat tone="accent" label="Aktive Etappe" value="3/9" size="sm" />
							<Stat tone="accent" label="Nächstes Briefing" value="06:00" size="md" />
							<Stat label="Tage bis Start" value="3" size="lg" />
						</div>
					</div>
					<div>
						{@render MonoTag('layout="inline" (Archiv-Style)')}
						<div style:display="flex" style:gap="32px" style:margin-top="10px">
							<Stat layout="inline" label="Trips" value="12" />
							<Stat layout="inline" label="Briefings" value="486" />
							<Stat layout="inline" label="Treffer Ø" tone="accent" value="87%" />
						</div>
					</div>
				</div>
			{/snippet}
			<div style:margin-bottom="16px">
				{@render Panel('Stat · zwei Layouts × 3 Größen', statBody)}
			</div>

			<!-- AlertRow -->
			{#snippet alertRowBody()}
				<div style:display="grid" style:grid-template-columns="1fr 1fr 1fr" style:gap="24px">
					<div>
						{@render MonoTag('variant="icon"')}
						<AlertRow alert={{ kind: 'thunder', when: 'Heute 14:00', channel: 'email', msg: 'Gewitter-Wahrscheinlichkeit 78% — Briefing-Sonderlauf um 13:00.' }} />
						<AlertRow alert={{ kind: 'wind', when: 'Morgen 17:00', channel: 'email', msg: 'Böen 50 km/h NW — Helmhotel exponiert.' }} last />
					</div>
					<div>
						{@render MonoTag('variant="dot"')}
						<AlertRow variant="dot" alert={{ kind: 'wind', when: '06:42 UTC · 13. Mai', msg: 'Wind-Update: Böen 50 km/h erwartet' }} divider="solid" />
						<AlertRow variant="dot" alert={{ kind: 'rain', when: '21:11 UTC · 12. Mai', msg: 'Schauer ab Mitternacht angekündigt' }} divider="solid" last />
					</div>
					<div>
						{@render MonoTag('variant="plain"')}
						<AlertRow variant="plain" alert={{ kind: 'thunder', when: 'Heute 14:00', msg: 'Gewitterwarnung Salzkammergut' }} />
						<AlertRow variant="plain" alert={{ kind: 'wind', when: 'Morgen 17:00', msg: 'Sturmböen Norddeutschland' }} last />
					</div>
				</div>
			{/snippet}
			<div style:margin-bottom="16px">
				{@render Panel('AlertRow · drei Varianten (icon / dot / plain)', alertRowBody)}
			</div>

			<!-- ChannelRow dense + ThresholdRow solid + BriefingTimelineRow dense -->
			{#snippet denseBody()}
				<div style:font-size="12px" style:color="var(--g-ink-3)" style:margin-bottom="18px" style:line-height="1.5">
					Dieselben Molecules — auf Mobile mit Reihen-Layout statt Card-Style. Eine Bibliothek, zwei Geometrien.
				</div>
				<div style:display="grid" style:grid-template-columns="1fr 1fr" style:gap="24px">
					<div>
						{@render MonoTag('ChannelRow dense')}
						<ChannelRow dense kind="Email" target="gregor_zwanzig@henemm.com" active />
						<ChannelRow dense kind="Telegram" target="@gregor_henemm" />
						<ChannelRow dense kind="SMS" target="+49 151 ••• 8847" sub="Fallback" last />
					</div>
					<div>
						{@render MonoTag('ThresholdRow divider="solid"')}
						<ThresholdRow divider="solid" label="Wind / Böen" value="≥ 50 km/h" />
						<ThresholdRow divider="solid" label="Niederschlag" value="≥ 10 mm/h" />
						<ThresholdRow divider="solid" label="Gewitter-Wahrsch." value="≥ 40 %" />
						<ThresholdRow divider="solid" label="Nullgrad-Grenze" value="−200 m unter Trip" last />
						<div style:margin-top="18px">{@render MonoTag('BriefingTimelineRow dense')}</div>
						{#each REPORT_TIMELINE as r (r.when)}
							<div style:margin-top="6px">
								<BriefingTimelineRow report={r} dense />
							</div>
						{/each}
					</div>
				</div>
			{/snippet}
			<div style:margin-bottom="16px">
				{@render Panel('Mobile · dense / compact / last Props', denseBody)}
			</div>

			<!-- BriefingTimelineRow default + BriefingScheduleRow -->
			{#snippet briefingRowsBody()}
				<div style:display="grid" style:grid-template-columns="1fr 1fr" style:gap="16px">
					<div>
						{@render MonoTag('BriefingTimelineRow · Status-getrieben')}
						<div style:display="flex" style:flex-direction="column" style:gap="8px" style:margin-top="8px">
							{#each REPORT_TIMELINE as r (r.when)}
								<BriefingTimelineRow report={r} />
							{/each}
						</div>
					</div>
					<div>
						{@render MonoTag('BriefingScheduleRow · Toggle-getrieben')}
						<div style:margin-top="8px">
							<BriefingScheduleRow label="Morgen-Briefing" sub="Vor Etappenstart" time="06:00" enabled />
							<BriefingScheduleRow label="Abend-Briefing" sub="Ausblick auf morgen" time="18:00" enabled />
							<BriefingScheduleRow label="Mittags-Update" sub="Nur bei Risiko-Wechsel" time="12:30" last />
						</div>
					</div>
				</div>
			{/snippet}
			{@render Panel('Briefing-Zeilen · zwei Semantiken', briefingRowsBody)}
		{/snippet}
		{@render Section('05', 'Molecules', 'Kompositionen aus Atomen mit eigener Semantik. EINE Quelle: $lib/components/molecules.', moleculesBody)}

		<!-- ═══ 06 · Voice ═══════════════════════════════════════════════════ -->
		{#snippet voiceBody()}
			<div style:display="grid" style:grid-template-columns="1fr 1fr" style:gap="16px">
				<div
					style:background="var(--g-card)"
					style:border="1px solid var(--g-rule)"
					style:border-left="3px solid var(--g-success)"
					style:border-radius="var(--g-r-3)"
					style:padding="20px"
				>
					<div
						class="mono"
						style:font-size="11px"
						style:color="var(--g-success)"
						style:letter-spacing="var(--g-track-caps)"
						style:text-transform="uppercase"
						style:margin-bottom="8px">Tun</div
					>
					<ul style:margin="0" style:padding-left="18px" style:font-size="14px" style:line-height="1.6" style:color="var(--g-ink-2)">
						<li>"Heute 18:00 geht ein Abend-Briefing an Email + Telegram."</li>
						<li>"Böen bis 47 km/h ab 17:00."</li>
						<li>"Ohne Stirnlampe: 05:43 – 21:10."</li>
					</ul>
				</div>
				<div
					style:background="var(--g-card)"
					style:border="1px solid var(--g-rule)"
					style:border-left="3px solid var(--g-danger)"
					style:border-radius="var(--g-r-3)"
					style:padding="20px"
				>
					<div
						class="mono"
						style:font-size="11px"
						style:color="var(--g-danger)"
						style:letter-spacing="var(--g-track-caps)"
						style:text-transform="uppercase"
						style:margin-bottom="8px">Lassen</div
					>
					<ul style:margin="0" style:padding-left="18px" style:font-size="14px" style:line-height="1.6" style:color="var(--g-ink-2)">
						<li><span style:text-decoration="line-through">"Wir kümmern uns um dein Wetter!"</span></li>
						<li><span style:text-decoration="line-through">"Aktiviere jetzt deinen Premium-Schutz"</span></li>
						<li><span style:text-decoration="line-through">"Trip-Erlebnis revolutioniert"</span></li>
					</ul>
				</div>
			</div>
		{/snippet}
		{@render Section('06', 'Voice', 'Dieselbe Sprache wie der Email-Briefing: knapp, datenehrlich, ohne Werbe-Floskeln.', voiceBody)}

		<!-- ═══ Mobile-Demo (PhoneFrame mit MobileShell — F001-Hamburger live) ═ -->
		{#snippet mobileBody()}
			<div style:display="flex" style:gap="32px" style:flex-wrap="wrap" style:align-items="flex-start">
				{#snippet sheetSlot()}
					<Sheet open={sheetOpen} onClose={() => (sheetOpen = false)} title="Aktionen" eyebrow="Etappe 3" snap="half">
						<div style:display="flex" style:flex-direction="column" style:gap="12px">
							<MBtn variant="primary" block onclick={() => (sheetOpen = false)}>Bestätigen</MBtn>
							<MBtn variant="quiet" block onclick={() => (sheetOpen = false)}>Schließen</MBtn>
						</div>
					</Sheet>
				{/snippet}
				{#snippet toastSlot()}
					<Toast kind="success" msg="Briefing gesendet" hint="06:01 UTC" action="OK" />
				{/snippet}
				{#snippet shellInner()}
					<MobileShell
						title="Heute"
						eyebrow="KHW · Etappe 3/9"
						active="heute"
						bind:mobileMenuOpen
						sheet={sheetSlot}
						toast={toastSlot}
					>
						<div style:padding="16px">
							<MTab items={MOBILE_TABS} active={mActiveTab} onChange={(id) => (mActiveTab = id)} />
							<div style:margin-top="16px" style:display="flex" style:flex-direction="column" style:gap="12px">
								<Stat tone="accent" label="Aktive Etappe" value="3/9" size="md" />
								<MSwitch bind:checked={mSwitch} label="Abend-Briefing aktiv" />
								<MBtn variant="primary" block onclick={() => (sheetOpen = true)}>Bottom-Sheet öffnen</MBtn>
								<MBtn variant="accent" size="lg">Report senden</MBtn>
								<MBtn variant="ghost" size="md">Abbrechen</MBtn>
							</div>
						</div>
					</MobileShell>
				{/snippet}

				{@render PhoneFrame(shellInner)}

				<div style:max-width="360px" style:display="flex" style:flex-direction="column" style:gap="14px">
					<div style:font-size="13px" style:color="var(--g-ink-2)" style:line-height="1.6">
						Der Hamburger oben links togglet das Menü (F001-Fix live). MobileShell vereint TopAppBar,
						Scroll-Bereich und BottomNav. Darin: MTab, Stat, MSwitch, MBtn (Varianten + Größen).
					</div>
					<MBtn variant="ghost" onclick={toggleMobileMenu}>
						Menü-Toggle: {mobileMenuOpen ? 'offen' : 'zu'}
					</MBtn>
					{@render MonoTag('MobileShell · MTab · MBtn · MSwitch · Sheet · Toast')}
				</div>
			</div>
		{/snippet}
		{@render Section('07', 'Mobile-Demo', 'Mobile-Primitive im lokalen PhoneFrame. Verifiziert den MobileShell-Hamburger-Toggle live.', mobileBody)}
	</div>
</div>
