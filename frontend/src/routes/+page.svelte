<script lang="ts">
	// Issue 579 — Home-Screen 1:1 nach JSX (screen-home.jsx + screen-home-planning.jsx).
	// Spec: docs/specs/modules/issue_579_home_screen.md

	import type { Trip, ComparePreset, CockpitStatus } from '$lib/types.js';
	import { Card, Pill, Dot, Eyebrow, Btn, SectionH, PageHeader } from '$lib/components/atoms';
	import {
		BriefingTimelineRow,
		QuickAction,
		SetupResumeCard,
		CompareStatusRow
	} from '$lib/components/molecules';
	import {
		deriveStatusFromPreset,
		formatNextSend
	} from '$lib/components/compare/subscriptionHelpers.js';
	import { tripStatus, activeOrNextTrip, todayStageIndex } from '$lib/utils/tripStatus.js';
	import { plannedBriefings, archivedTrips, homeCompareTimeline } from './_home/cockpitHelpers.js';
	import {
		dayProgress,
		setupStepTrip,
		setupStepCompare,
		nextPlannedTrip,
		firstIncompleteCompare,
		liveTrip,
		deriveNextSend
	} from '$lib/utils/cockpitHelpers568.js';
	import TripKachel from './_home/TripKachel.svelte';
	import CompareKachel from './_home/CompareKachel.svelte';
	import EmptyKachel from './_home/EmptyKachel.svelte';

	let { data } = $props();

	const now = new Date();
	const trips = $derived((data.trips ?? []) as Trip[]);
	const presets = $derived((data.presets ?? []) as ComparePreset[]);
	const activePresets = $derived(
		presets.filter((p) => deriveStatusFromPreset(p) === 'active')
	);
	const cockpitStatus = $derived((data.cockpitStatus ?? null) as CockpitStatus | null);
	const isEmpty = $derived(trips.length === 0 && presets.length === 0);

	const todayPretty = now.toLocaleDateString('de-DE', {
		weekday: 'short',
		day: '2-digit',
		month: 'long',
		year: 'numeric'
	});

	// --- Hero-Modus: trip > compare > planning --------------------------------
	const activeLiveTrip = $derived(liveTrip(trips, now));

	const mode = $derived(
		activeLiveTrip ? 'trip' : (activePresets.length > 0 ? 'compare' : 'planning')
	);

	const compareHero = $derived(mode === 'compare' ? activePresets[0] : null);

	// "Außerdem beobachtet" — nebenher laufende Vergleiche
	const alsoWatched = $derived(
		mode === 'trip' ? activePresets :
		mode === 'compare' ? activePresets.slice(1) : []
	);

	// --- Hero-Tour (aktiv) --------------------------------------------------
	const hero = $derived(mode === 'trip' ? activeLiveTrip : null);
	const heroIsActive = $derived(mode === 'trip');
	const heroStages = $derived(hero?.stages ?? []);
	const todayIdx = $derived(hero ? todayStageIndex(hero, now) : -1);
	const heroStageIdx = $derived(todayIdx >= 0 ? todayIdx : 0);
	const dayX = $derived(heroIsActive ? heroStageIdx + 1 : 1);
	const dayY = $derived(heroStages.length);
	const progressPct = $derived(dayProgress(dayX, dayY));

	// --- Planungs-Kandidaten ------------------------------------------------
	const nextPlanned = $derived(nextPlannedTrip(trips, now));
	const firstIncomplete = $derived(firstIncompleteCompare(presets));
	const setupStepsTrip = $derived(nextPlanned ? setupStepTrip(nextPlanned) : []);
	const setupStepsCompare = $derived(firstIncomplete ? setupStepCompare(firstIncomplete) : []);

	const TRIP_TAB_MAP = ['stages', 'stages', 'weather', 'briefings', 'briefings'];

	function buildTripCtaHref(): string {
		if (!nextPlanned) return '/trips/new';
		const firstOpen = setupStepsTrip.findIndex((s) => !s.done);
		if (firstOpen < 0) return `/trips/${nextPlanned.id}?tab=overview`;
		if (firstOpen === 0) return '/trips/new';
		return `/trips/${nextPlanned.id}?tab=${TRIP_TAB_MAP[firstOpen]}`;
	}

	function buildCompareCtaHref(): string {
		if (!firstIncomplete) return '/compare';
		const firstOpen = setupStepsCompare.findIndex((s) => !s.done);
		const step = firstOpen < 0 ? 1 : firstOpen + 1;
		return `/compare/${firstIncomplete.id}/edit`;
	}

	const tripCtaHref = $derived(buildTripCtaHref());
	const compareCtaHref = $derived(buildCompareCtaHref());

	// --- Rechte Spalte / Archiv ---------------------------------------------
	const briefings = $derived(
		hero ? plannedBriefings(hero.report_config, cockpitStatus?.briefings, hero.id) : []
	);
	const heroAlerts = $derived(
		(cockpitStatus?.alerts ?? []).filter((a) => a.trip_id === hero?.id)
	);
	const archive = $derived(archivedTrips(trips, now, 4));

	// AC-9: fertig-Trips aus otherTrips ausschließen
	const otherTrips = $derived(trips.filter((t) => t.id !== hero?.id && tripStatus(t, now) !== 'fertig'));

	// Aktive Kanäle aus report_config — für die Kanal-Gesundheits-Dots.
	const heroChannels = $derived.by(() => {
		const rc = hero?.report_config;
		if (!rc) return [] as string[];
		const out: string[] = [];
		if (rc.morning_enabled || rc.evening_enabled) {
			if (rc.send_email !== false) out.push('Email');
			if (rc.send_telegram) out.push('Telegram');
			if (rc.send_sms) out.push('SMS');
		}
		return out;
	});

	// Datum-Range für den Fortschrittsbalken
	const heroDateRange = $derived.by(() => {
		if (!hero) return '';
		const dates = (hero.stages ?? [])
			.map((s: { date?: string }) => s.date)
			.filter((d: string | undefined): d is string => !!d)
			.sort();
		if (dates.length === 0) return '';
		const fmt = (iso: string) =>
			new Date(iso).toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' });
		return dates.length === 1 ? fmt(dates[0]) : `${fmt(dates[0])} → ${fmt(dates[dates.length - 1])}`;
	});
</script>

<div class="page-root" style:position="relative" style:max-width="1320px">
	<!-- Topbar — AC-7: kein sub-Text, beide Buttons ghost -->
	<PageHeader
		eyebrow="Übersicht · {todayPretty}"
		title="Deine Touren & Vergleiche"
	>
		{#snippet right()}
			<Btn href="/trips/new" variant="ghost" size="sm">+ Neuer Trip</Btn>
			<Btn href="/compare" variant="ghost" size="sm">+ Neuer Vergleich</Btn>
		{/snippet}
	</PageHeader>

	{#if isEmpty}
		<EmptyKachel />
	{:else}

		<!-- Zustand A: aktiver Trip-Hero + Schnellaktionen in linker Spalte -->
		{#if hero && heroIsActive}
			<!-- AC-1/AC-3: 2-Spalten-Grid, align-items:start -->
			<div class="cockpit-hero" style:margin-bottom="36px">

				<!-- Linke Spalte: Hero-Karte + Schnellaktionen vertikal -->
				<div style:display="flex" style:flex-direction="column" style:gap="20px">

					<!-- AC-2/V2+V3: Hero-Karte — Reihenfolge: Pills → Titel → Region → Progress → Footer -->
					<Card padding={0} style="overflow: hidden; border-left: 3px solid var(--g-accent)">
						<div style:padding="22px 26px">
							<!-- Pills-Zeile -->
							<div
								style:display="flex"
								style:align-items="center"
								style:gap="10px"
								style:margin-bottom="12px"
								style:flex-wrap="wrap"
							>
								<Pill tone="accent"><Dot tone="bad" size={6} /> Live · Tag {dayX} von {dayY}</Pill>
								<Pill tone="ghost">Sommer-Trekking</Pill>
							</div>

							<!-- Titel (34px, fontWeight 600) als Link -->
							<a
								href="/trips/{hero.id}?tab=overview"
								style:display="block"
								style:font-size="34px"
								style:font-weight="600"
								style:letter-spacing="-0.02em"
								style:line-height="1.05"
								style:margin-bottom="6px"
								style:color="var(--g-ink)"
								style:text-decoration="none"
							>{hero.name}</a>

							<!-- Region-Untertitel (15px, ink-2) -->
							{#if hero.region}
								<div
									style:font-size="15px"
									style:color="var(--g-ink-2)"
									style:margin-bottom="20px"
								>{hero.region}</div>
							{:else}
								<div style:margin-bottom="20px"></div>
							{/if}

							<!-- Fortschrittsbalken mit Label "Tag x / y" + Datum-Range -->
							<div>
								<div
									style:display="flex"
									style:justify-content="space-between"
									style:align-items="baseline"
									style:margin-bottom="8px"
								>
									<span
										style:font-family="var(--g-font-mono)"
										style:font-size="11px"
										style:color="var(--g-ink-2)"
										style:letter-spacing="0.06em"
										style:text-transform="uppercase"
										style:font-weight="600"
									>Tag {dayX} / {dayY}</span>
									<span
										style:font-family="var(--g-font-mono)"
										style:font-size="11px"
										style:color="var(--g-ink-3)"
									>{heroDateRange}</span>
								</div>
								<div
									style:height="6px"
									style:border-radius="999px"
									style:background="var(--g-paper-deep)"
									style:overflow="hidden"
								>
									<div
										style:width="{progressPct}%"
										style:height="100%"
										style:background="var(--g-accent)"
										style:border-radius="999px"
									></div>
								</div>
							</div>
						</div>

						<!-- Footer-Leiste: card-alt, borderTop, Eyebrow "Kanäle" + "Trip öffnen →" -->
						<div
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
								<Eyebrow>Kanäle</Eyebrow>
								<div style:display="flex" style:gap="14px">
									{#each heroChannels as ch (ch)}
										<span
											style:display="inline-flex"
											style:align-items="center"
											style:gap="6px"
											style:font-size="12px"
											style:color="var(--g-ink-2)"
										>
											<Dot tone="good" size={7} />
											<span style:font-family="var(--g-font-mono)" style:text-transform="capitalize">{ch}</span>
										</span>
									{/each}
								</div>
							</div>
							<a
								href="/trips/{hero.id}?tab=overview"
								style:font-size="12px"
								style:color="var(--g-ink-3)"
								style:text-decoration="none"
								style:font-family="var(--g-font-mono)"
							>Trip öffnen →</a>
						</div>
					</Card>

					<!-- AC-3/V13: Schnellaktionen vertikal in linker Spalte -->
					<div>
						<div style:margin-bottom="12px">
							<Eyebrow style="margin-bottom: 4px">Schnell eingreifen</Eyebrow>
							<div style:font-size="17px" style:font-weight="600">Schnellaktionen</div>
						</div>
						<div style:display="flex" style:flex-direction="column" style:gap="10px">
							<QuickAction
								glyph="pause"
								label="Pausentag einplanen"
								sub="→ Etappen & Wegpunkte"
								href="/trips/{hero.id}?tab=stages"
							/>
							<QuickAction
								glyph="metrics"
								label="Wetter-Metriken ändern"
								sub="→ Wetter-Metriken"
								href="/trips/{hero.id}?tab=weather"
							/>
							<QuickAction
								glyph="clock"
								label="Briefing-Zeitplan"
								sub="→ Briefing-Zeitplan"
								href="/trips/{hero.id}?tab=briefings"
							/>
							<QuickAction
								glyph="eye"
								label="Vorschau prüfen"
								sub="→ Vorschau"
								href="/trips/{hero.id}?tab=preview"
							/>
							<QuickAction
								glyph="send"
								label="Test-Briefing schicken"
								sub="→ An deine eigenen Kanäle"
								href="/trips/{hero.id}?action=test-send"
							/>
						</div>
					</div>
				</div>

				<!-- Rechte Spalte: Outbox + Alerts -->
				<div style:display="flex" style:flex-direction="column" style:gap="16px">
					<!-- Outbox -->
					<Card padding={20}>
						<div
							style:display="flex"
							style:justify-content="space-between"
							style:align-items="center"
							style:margin-bottom="14px"
							style:gap="12px"
						>
							<div style:min-width="0">
								<Eyebrow style="margin-bottom: 4px">Versand · heute</Eyebrow>
								<div
									style:font-size="17px"
									style:font-weight="600"
									style:white-space="nowrap"
									style:overflow="hidden"
									style:text-overflow="ellipsis"
								>
									Was geht raus · <span style:color="var(--g-ink-2)" style:font-weight="600">{hero?.name ?? ''}</span>
								</div>
							</div>
							<Pill tone="good">Alle Kanäle ok</Pill>
						</div>
						{#if briefings.length > 0}
							<div style:display="flex" style:flex-direction="column" style:gap="8px">
								{#each briefings.slice(0, 3) as r, i (i)}
									<BriefingTimelineRow report={r} />
								{/each}
							</div>
						{:else}
							<div style:font-size="13px" style:color="var(--g-ink-2)">
								Keine Briefings für diesen Trip geplant.
							</div>
						{/if}
					</Card>

					<!-- Alerts -->
					<Card padding={20}>
						<div
							style:display="flex"
							style:justify-content="space-between"
							style:align-items="center"
							style:margin-bottom="12px"
						>
							<div>
								<Eyebrow style="margin-bottom: 4px">Alerts · letzte 24 h</Eyebrow>
								<div style:font-size="17px" style:font-weight="600">
									{heroAlerts.length > 0 ? `${heroAlerts.length} ausgelöst` : 'Keine'}
								</div>
							</div>
							<a
								href="/trips/{hero.id}?tab=alerts"
								style:font-size="12px"
								style:color="var(--g-ink-3)"
								style:text-decoration="none"
								style:font-family="var(--g-font-mono)"
							>Schwellen →</a>
						</div>
						{#if heroAlerts.length > 0}
							<div style:display="flex" style:flex-direction="column" style:gap="6px">
								{#each heroAlerts as alert (alert.sent_at)}
									<div
										style:display="flex"
										style:align-items="center"
										style:gap="8px"
										style:padding="8px 10px"
										style:background="var(--g-card-alt)"
										style:border="1px solid var(--g-rule-soft)"
										style:border-radius="var(--g-r-2)"
										style:font-size="13px"
									>
										<Dot
											tone={alert.severity === 'HIGH'
												? 'bad'
												: alert.severity === 'MODERATE'
													? 'warn'
													: 'neutral'}
										/>
										<span style:color="var(--g-ink-2)"
											>{new Date(alert.sent_at).toLocaleTimeString('de-DE', {
												hour: '2-digit',
												minute: '2-digit'
											})}</span
										>
										<span style:color="var(--g-ink-2)"
											>{alert.changes_count} Änderung{alert.changes_count !== 1
												? 'en'
												: ''}</span
										>
									</div>
								{/each}
							</div>
						{:else}
							<div
								style:font-size="13px"
								style:color="var(--g-ink-2)"
								style:line-height="1.5"
								style:padding-top="2px"
							>
								Keine Schwellen-Überschreitung in den verglichenen Orten. Du wirst sofort benachrichtigt, sobald eine Bedingung kippt.
							</div>
						{/if}
					</Card>
				</div>
			</div>
		{/if}

		<!-- Zustand C: Compare-Hero (kein aktiver Trip, aber aktive Vergleiche) -->
		{#if mode === 'compare' && compareHero}
			<div class="cockpit-hero" style:margin-bottom="36px">
				<!-- Linke Spalte: Compare-Hero + Schnellaktionen vertikal -->
				<div style:display="flex" style:flex-direction="column" style:gap="20px">
					<Card padding={0} style="overflow: hidden; border-left: 3px solid var(--g-accent)">
						<div style:padding="22px 26px">
							<!-- Pills-Zeile -->
							<div
								style:display="flex"
								style:align-items="center"
								style:gap="10px"
								style:margin-bottom="12px"
								style:flex-wrap="wrap"
							>
								<Pill tone="accent"><Dot tone="good" size={6} /> Aktiv · läuft automatisch</Pill>
								{#if (compareHero.display_config as Record<string,unknown> | undefined)?.profile_label}
									<Pill tone="ghost">{(compareHero.display_config as Record<string,unknown>).profile_label as string}</Pill>
								{/if}
							</div>

							<!-- Titel -->
							<div
								style:font-size="34px"
								style:font-weight="600"
								style:letter-spacing="-0.02em"
								style:line-height="1.05"
								style:margin-bottom="6px"
							>{compareHero.name}</div>

							<!-- Region / Orte-Info -->
							<div style:font-size="15px" style:color="var(--g-ink-2)" style:margin-bottom="20px">
								{#if (compareHero.display_config as Record<string,unknown> | undefined)?.region}
									{(compareHero.display_config as Record<string,unknown>).region as string} ·
								{/if}
								{compareHero.location_ids.length} Orte verglichen
							</div>

							<!-- Zeitplan + Nächster Versand -->
							<div style:display="grid" style:grid-template-columns="1fr 1fr" style:gap="14px">
								<div
									style:padding="12px 14px"
									style:border="1px solid var(--g-rule-soft)"
									style:border-radius="var(--g-r-2)"
									style:background="var(--g-paper-deep)"
								>
									<div
										style:font-family="var(--g-font-mono)"
										style:font-size="10px"
										style:color="var(--g-ink-3)"
										style:text-transform="uppercase"
										style:letter-spacing="0.1em"
										style:margin-bottom="5px"
									>Zeitplan</div>
									<div style:font-size="15px" style:font-weight="600">
										{compareHero.schedule === 'daily' ? 'täglich' : compareHero.schedule === 'weekly' ? 'wöchentlich' : 'manuell'}
										{#if compareHero.schedule !== 'manual'} · {String(compareHero.hour_from).padStart(2,'0')}:00{/if}
									</div>
								</div>
								<div
									style:padding="12px 14px"
									style:border="1px solid var(--g-rule-soft)"
									style:border-radius="var(--g-r-2)"
									style:background="var(--g-paper-deep)"
								>
									<div
										style:font-family="var(--g-font-mono)"
										style:font-size="10px"
										style:color="var(--g-ink-3)"
										style:text-transform="uppercase"
										style:letter-spacing="0.1em"
										style:margin-bottom="5px"
									>Nächster Versand</div>
									<div style:font-size="15px" style:font-weight="600">{formatNextSend(deriveNextSend(compareHero, now))}</div>
								</div>
							</div>
						</div>

						<!-- Footer-Leiste: card-alt, borderTop -->
						<div
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
								<Eyebrow>Kanäle</Eyebrow>
								<div style:display="flex" style:gap="14px">
									{#each compareHero.empfaenger as emp (emp)}
										<span
											style:display="inline-flex"
											style:align-items="center"
											style:gap="6px"
											style:font-size="12px"
											style:color="var(--g-ink-2)"
										>
											<Dot tone="good" size={7} />
											<span style:font-family="var(--g-font-mono)" style:text-transform="capitalize">{emp}</span>
										</span>
									{/each}
								</div>
							</div>
							<a
								href="/compare/{compareHero.id}"
								style:font-size="12px"
								style:color="var(--g-ink-3)"
								style:text-decoration="none"
								style:font-family="var(--g-font-mono)"
							>Vergleich öffnen →</a>
						</div>
					</Card>

					<!-- Schnellaktionen vertikal in linker Spalte (Compare-Modus) -->
					<div>
						<div style:margin-bottom="12px">
							<Eyebrow style="margin-bottom: 4px">Schnell eingreifen</Eyebrow>
							<div style:font-size="17px" style:font-weight="600">Schnellaktionen</div>
						</div>
						<div style:display="flex" style:flex-direction="column" style:gap="10px">
							<QuickAction
								glyph="route"
								label="Orte bearbeiten"
								sub="→ Verglichene Orte"
								href="/compare/{compareHero.id}/edit"
							/>
							<QuickAction
								glyph="metrics"
								label="Ideal-Werte ändern"
								sub="→ Ideal-Profil"
								href="/compare/{compareHero.id}/edit#idealwerte"
							/>
							<QuickAction
								glyph="clock"
								label="Briefing-Zeitplan"
								sub="→ Zeitplan & Kanäle"
								href="/compare/{compareHero.id}/edit#schedule"
							/>
							<QuickAction
								glyph="eye"
								label="Vorschau prüfen"
								sub="→ Vorschau"
								href="/compare/{compareHero.id}?tab=preview"
							/>
							<QuickAction
								glyph="send"
								label="Test-Vergleich schicken"
								sub="→ An deine eigenen Kanäle"
								href="/compare/{compareHero.id}?action=test-send"
							/>
						</div>
					</div>
				</div>

				<!-- Rechte Spalte: Outbox + Alerts -->
				<div style:display="flex" style:flex-direction="column" style:gap="16px">
					<Card padding={20}>
						<div
							style:display="flex"
							style:justify-content="space-between"
							style:align-items="center"
							style:margin-bottom="14px"
							style:gap="12px"
						>
							<div style:min-width="0">
								<Eyebrow style="margin-bottom: 4px">Versand · heute</Eyebrow>
								<div
									style:font-size="17px"
									style:font-weight="600"
									style:white-space="nowrap"
									style:overflow="hidden"
									style:text-overflow="ellipsis"
								>
									Was geht raus · <span style:color="var(--g-ink-2)" style:font-weight="600">{compareHero.name}</span>
								</div>
							</div>
							<Pill tone="good">Alle Kanäle ok</Pill>
						</div>
						{#if homeCompareTimeline(compareHero, now).length > 0}
							<div
								style:display="flex"
								style:flex-direction="column"
								style:gap="8px"
								style:margin-top="8px"
							>
								{#each homeCompareTimeline(compareHero, now) as r, i (i)}
									<BriefingTimelineRow report={r} />
								{/each}
							</div>
						{:else}
							<div style:font-size="13px" style:color="var(--g-ink-2)" style:margin-top="8px">
								Versand läuft automatisch gemäß Zeitplan.
							</div>
						{/if}
					</Card>
					<Card padding={20}>
						<div
							style:display="flex"
							style:justify-content="space-between"
							style:align-items="center"
							style:margin-bottom="12px"
						>
							<div>
								<Eyebrow style="margin-bottom: 4px">Alerts · letzte 24 h</Eyebrow>
								<div style:font-size="17px" style:font-weight="600">Keine</div>
							</div>
							<a
								href="/compare/{compareHero.id}"
								style:font-size="12px"
								style:color="var(--g-ink-3)"
								style:text-decoration="none"
								style:font-family="var(--g-font-mono)"
							>Schwellen →</a>
						</div>
						<div style:font-size="13px" style:color="var(--g-ink-2)" style:line-height="1.5" style:padding-top="2px">
							Keine Schwellen-Überschreitung in den verglichenen Orten. Du wirst sofort benachrichtigt, sobald eine Bedingung kippt.
						</div>
					</Card>
				</div>
			</div>
		{/if}

		<!-- Zustand B: Planungs-/Leerzustand (kein aktiver Trip, keine aktiven Vergleiche) -->
		{#if mode === 'planning'}
			<!-- Ehrlicher Hinweis-Banner -->
			<div
				style:display="flex"
				style:align-items="center"
				style:gap="12px"
				style:margin-bottom="28px"
				style:padding="12px 18px"
				style:border-radius="var(--g-r-3)"
				style:background="var(--g-card-alt)"
				style:border="1px solid var(--g-rule-soft)"
			>
				<Dot tone="neutral" size={8} />
				<span style:font-size="14px" style:color="var(--g-ink-2)">
					Aktuell läuft <strong>kein Trip</strong>. Sobald deine nächste Reise startet, schickt <span style:font-family="var(--g-font-mono)" style:font-size="13px">gregor · zwanzig</span> die Briefings automatisch in deine Kanäle.
				</span>
			</div>

			<!-- Weiter einrichten -->
			{#if nextPlanned || firstIncomplete}
				<div style:margin-bottom="36px">
					<SectionH
						eyebrow="Weiter einrichten"
						title="Mach weiter, wo du aufgehört hast"
						kicker="Du nutzt die Webseite vor allem zur Vorbereitung — hier liegen deine offenen Entwürfe"
					/>
					<div class="setup-grid">
						{#if nextPlanned}
							<SetupResumeCard
								tone="accent"
								eyebrow="Nächster Trip"
								title={nextPlanned.name}
								steps={setupStepsTrip}
								ctaLabel="Setup fortsetzen"
								ctaHref={tripCtaHref}
								secondary={{ label: 'Öffnen', href: `/trips/${nextPlanned.id}?tab=overview` }}
							/>
						{/if}
						{#if firstIncomplete}
							<SetupResumeCard
								eyebrow="Orts-Vergleich"
								title={firstIncomplete.name}
								steps={setupStepsCompare}
								ctaLabel="Setup fortsetzen"
								ctaHref={compareCtaHref}
								secondary={{ label: 'Öffnen', href: `/compare/${firstIncomplete.id}` }}
								tone="default"
							/>
						{/if}
					</div>
				</div>
			{/if}

			<!-- Schnell anlegen -->
			<div style:margin-bottom="36px">
				<SectionH eyebrow="Schnell anlegen" title="Neu starten" />
				<div class="quick-create-grid">
					<QuickAction
						glyph="route"
						tone="accent"
						label="Neuer Trip"
						sub="Wizard · 5 Schritte"
						href="/trips/new"
					/>
					<QuickAction
						glyph="metrics"
						label="Neuer Orts-Vergleich"
						sub="Wizard · 5 Schritte"
						href="/compare"
					/>
					<QuickAction
						glyph="eye"
						label="Test-Briefing prüfen"
						sub="Vorschau · alle Kanäle"
						href="/trips"
					/>
				</div>
			</div>

			<!-- Laufende Orts-Vergleiche (falls vorhanden) -->
			{#if activePresets.length > 0}
				<div style:margin-bottom="36px">
					<SectionH
						eyebrow="Läuft automatisch"
						title="Laufende Orts-Vergleiche"
						kicker="Vergleiche laufen unabhängig von Trips weiter — Briefing kommt in die Kanäle"
						right={compareAllLink}
					/>
					<div class="kachel-grid-3">
						{#each activePresets as preset (preset.id)}
							<CompareKachel {preset} />
						{/each}
					</div>
				</div>
			{/if}
		{/if}

		<!-- AC-5/V5: "Außerdem beobachtet" in Card mit Titel + Link -->
		{#if alsoWatched.length > 0}
			<Card padding={20} style="margin-bottom: 36px">
				<div
					style:display="flex"
					style:justify-content="space-between"
					style:align-items="baseline"
					style:margin-bottom="4px"
					style:gap="16px"
				>
					<div>
						<Eyebrow style="margin-bottom: 4px">Außerdem beobachtet</Eyebrow>
						<div style:font-size="15px" style:font-weight="600">
							{#if alsoWatched.length === 1}
								{alsoWatched.length} Orts-Vergleich läuft nebenher
							{:else}
								{alsoWatched.length} Orts-Vergleiche laufen nebenher
							{/if}
						</div>
					</div>
					<a
						href="/compare"
						style:font-size="12px"
						style:color="var(--g-ink-3)"
						style:text-decoration="none"
						style:font-family="var(--g-font-mono)"
					>Alle Vergleiche →</a>
				</div>
				<div>
					{#each alsoWatched as preset (preset.id)}
						<CompareStatusRow {preset} />
					{/each}
				</div>
			</Card>
		{/if}

		<!-- Weitere Trips (nicht hero, nicht fertig) — nur im Trip/Compare-Modus -->
		{#if mode !== 'planning' && otherTrips.length > 0}
			<section style:margin-bottom="32px">
				<div class="kachel-grid">
					{#each otherTrips as trip (trip.id)}
						<TripKachel {trip} />
					{/each}
				</div>
			</section>
		{/if}

		<!-- AC-2 (Trip-Modus): Einrichten / Frühere Trips -->
		{#if mode === 'trip' && archive.length > 0}
			<div style:margin-bottom="40px">
				<SectionH eyebrow="Einrichten" title="Frühere Trips" kicker="{archive.length} abgeschlossene Mehrtages-Trips" right={archiveLink} />
				<div class="archive-grid">
					{#each archive as t (t.id)}
						{@render archiveCard(t)}
					{/each}
				</div>
			</div>
		{/if}

		<!-- AC-1 + AC-3 (Compare-Modus): Einrichten / Kein Trip geplant — Kopf immer sichtbar -->
		{#if mode === 'compare'}
			<div style:margin-bottom="40px">
				<SectionH eyebrow="Einrichten" title="Kein Trip geplant" kicker="Sobald ein Mehrtages-Trip ansteht, übernimmt er das Cockpit" right={newTripLink} />
				{#if archive.length > 0}
					<div class="archive-grid">
						{#each archive as t (t.id)}
							{@render archiveCard(t)}
						{/each}
					</div>
				{/if}
			</div>
		{/if}

		<!-- Planning-Modus: Archiv in Card (1:1 screen-home-planning.jsx Z.133) -->
		{#if mode === 'planning' && archive.length > 0}
			<Card padding={20}>
				<div style:margin-bottom="40px">
					<SectionH eyebrow="Archiv" title="Frühere Trips" kicker="{archive.length} abgeschlossene Trips" right={archiveLink} />
					<div class="archive-grid">
						{#each archive as t (t.id)}
							{@render archiveCard(t)}
						{/each}
					</div>
				</div>
			</Card>
		{/if}
	{/if}
</div>

{#snippet archiveLink()}
	<Btn href="/trips" variant="quiet" size="sm">Alle anzeigen</Btn>
{/snippet}

{#snippet newTripLink()}
	<Btn href="/trips/new" variant="primary" size="sm">Neuer Trip</Btn>
{/snippet}

{#snippet archiveCard(t: { id: string; dates: string; name: string; stages: number })}
	<a
		href="/trips/{t.id}"
		style:padding="14px 16px"
		style:border="1px solid var(--g-rule-soft)"
		style:border-radius="var(--g-r-2)"
		style:background="var(--g-card-alt)"
		style:text-decoration="none"
		style:color="var(--g-ink)"
		style:display="block"
	>
		<div
			style:font-family="var(--g-font-mono)"
			style:font-size="var(--g-text-xs)"
			style:color="var(--g-ink-3)"
			style:text-transform="uppercase"
			style:letter-spacing="var(--g-track-caps)"
			style:margin-bottom="4px"
		>{t.dates}</div>
		<div
			style:font-size="var(--g-text-sm)"
			style:font-weight="600"
			style:line-height="1.3"
			style:margin-bottom="6px"
		>{t.name}</div>
		<div
			style:font-family="var(--g-font-mono)"
			style:font-size="11px"
			style:color="var(--g-ink-3)"
		>{t.stages} {t.stages === 1 ? 'Etappe' : 'Etappen'}</div>
	</a>
{/snippet}

{#snippet compareAllLink()}
	<Btn href="/compare" variant="quiet" size="sm">Alle anzeigen</Btn>
{/snippet}


<style>
	.cockpit-hero {
		display: grid;
		grid-template-columns: 1.4fr 1fr;
		gap: 24px;
		align-items: start;
	}
	.setup-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 20px;
	}
	.quick-create-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 14px;
	}
	.archive-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 12px;
	}
	.kachel-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.75rem;
	}
	.kachel-grid-3 {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 16px;
	}
	@media (max-width: 899px) {
		.cockpit-hero {
			grid-template-columns: 1fr;
		}
		.setup-grid {
			grid-template-columns: 1fr;
		}
		.quick-create-grid {
			grid-template-columns: repeat(2, 1fr);
		}
		.archive-grid {
			grid-template-columns: repeat(2, 1fr);
		}
		.kachel-grid-3 {
			grid-template-columns: 1fr 1fr;
		}
	}
	.page-root {
		padding: 0 0 80px;
	}
	@media (max-width: 640px) {
		.page-root {
			/* F002: Inhalt darf nicht hinter der fixen Mobile-Bottom-Nav verschwinden (64px + Safe Area) */
			padding-bottom: 120px;
		}
		.quick-create-grid {
			grid-template-columns: 1fr;
		}
		.kachel-grid-3 {
			grid-template-columns: 1fr;
		}
	}
	@media (min-width: 640px) {
		.kachel-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}
	@media (min-width: 1024px) {
		.kachel-grid {
			grid-template-columns: repeat(3, 1fr);
		}
	}
</style>
