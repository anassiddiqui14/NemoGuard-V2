import { useState } from 'react';
import { motion } from 'framer-motion';
import { LayoutGrid, Search as SearchIcon, Activity, BrainCircuit, ShieldCheck } from 'lucide-react';

type TabKey = 'overview' | 'evidence' | 'investigation' | 'activity' | 'recovery';

interface Props {
    alertCount: number;
    overview: React.ReactNode;
    evidence: React.ReactNode;
    investigation: React.ReactNode;
    activity: React.ReactNode;
    recovery: React.ReactNode;
}

// Commander used to be a 6th tab here. Per user feedback, Commander is now
// rendered as its own ALWAYS-VISIBLE panel on the incident page (see
// IncidentWorkspace.tsx), not one of these tabs -- switching between these
// remaining tabs never affects Commander's mount state at all anymore,
// which is a stronger fix than the earlier "keep every tab mounted"
// workaround: Commander no longer needs to survive a tab switch, because
// it's never hidden by one in the first place.
const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
    { key: 'overview', label: 'Overview', icon: <LayoutGrid className="w-3.5 h-3.5" /> },
    { key: 'evidence', label: 'Alerts', icon: <SearchIcon className="w-3.5 h-3.5" /> },
    { key: 'investigation', label: 'Investigation', icon: <BrainCircuit className="w-3.5 h-3.5" /> },
    { key: 'activity', label: 'Activity & impact', icon: <Activity className="w-3.5 h-3.5" /> },
    { key: 'recovery', label: 'Recovery plan', icon: <ShieldCheck className="w-3.5 h-3.5" /> },
];

/**
 * Groups the ENTIRE incident workspace -- situation overview, alerts,
 * agent/hypothesis investigation, activity/impact, AND the recovery plan --
 * into a single tabbed interface. Previously the recovery plan lived in a
 * permanently-visible narrow (300px) right-hand rail alongside everything
 * else, which made the whole dashboard feel cramped even when the operator
 * wasn't looking at recovery status. Now every section (including recovery)
 * gets the full content width when it's the active tab, and the layout only
 * shows exactly one focused section at a time -- addressing direct feedback
 * that the dashboard felt cluttered compared to a tabbed alternative design.
 */
export function WorkspaceTabs({ alertCount, overview, evidence, investigation, activity, recovery }: Props) {
    const [active, setActive] = useState<TabKey>('overview');

    const content: Record<TabKey, React.ReactNode> = {
        overview,
        evidence,
        investigation,
        activity,
        recovery,
    };

    return (
        <div className="flex flex-col gap-3">
            {/* Previously a fixed 5-column grid with a min-w-[640px] wrapped in
                overflow-x-auto -- on narrower viewports (laptop windows, split
                screens, or this app's own browser preview at 900px) the "Recovery
                plan" tab silently scrolled out of view with no visible scrollbar
                affordance, making the Approve & Execute button completely
                unreachable. Tabs now shrink to fit (flex-wrap + min-w-0 + truncate)
                instead of ever requiring horizontal scrolling to reach a tab. */}
            <div className="console-surface w-full rounded-2xl p-1.5">
                <div className="flex flex-wrap gap-1" role="tablist" aria-label="Incident workspace sections">
                    {TABS.map((tab) => (
                        <button
                            key={tab.key}
                            onClick={() => setActive(tab.key)}
                            role="tab"
                            aria-selected={active === tab.key}
                            aria-controls={`workspace-panel-${tab.key}`}
                            className={`focus-ring relative flex-1 min-w-[92px] flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-xl text-[12px] font-semibold transition-colors ${active === tab.key
                                ? 'text-text-primary'
                                : 'text-text-muted hover:text-text-secondary hover:bg-white/[0.03]'
                                }`}
                        >
                            {active === tab.key && (
                                <motion.div
                                    layoutId="workspace-tab-pill"
                                    className="absolute inset-0 rounded-xl bg-gradient-to-br from-white/[0.10] to-white/[0.04] ring-1 ring-primary/25 shadow-lg shadow-primary/5"
                                    transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                                />
                            )}
                            <span className="relative z-10 flex items-center gap-1.5 min-w-0">
                                <span className="flex-shrink-0">{tab.icon}</span>
                                <span className="truncate">{tab.label}</span>
                                {tab.key === 'evidence' && alertCount > 0 && (
                                    <span className="flex-shrink-0 text-[9.5px] font-bold px-1.5 py-0.5 rounded-full bg-primary/20 text-primary">
                                        {alertCount}
                                    </span>
                                )}
                            </span>
                        </button>
                    ))}
                </div>
            </div>

            {/*
              BUG FIX (user-reported): switching away from the Commander tab
              and back made an in-flight "Thinking" indicator disappear and
              never come back, even though the real backend request was
              still running. Root cause: AnimatePresence mode="wait" only
              ever rendered content[active] -- every OTHER tab's panel
              (including CommanderPanel, whose useCommander() hook owns the
              `sending`/optimisticMessages state) was fully UNMOUNTED the
              moment you navigated away, destroying that state entirely.
              Remounting on return started from a clean slate with no
              memory that a request was in flight.

              Fix: render every tab's content simultaneously, all the time,
              and toggle visibility with CSS (hidden vs block) instead of
              conditional rendering. Each tab's own component tree (and any
              hooks/state it owns, e.g. useCommander's sending state) now
              stays mounted for the entire lifetime of this workspace, so an
              in-flight request's UI state survives tab switches exactly
              like a real background task should.
            */}
            {/* IMPORTANT: no `key={active}` on any ancestor of this map --
                that would make AnimatePresence unmount/remount the ENTIRE
                subtree (including every other tab's content) on every tab
                switch, which is exactly the bug being fixed here. Each
                tab's own div keeps a STABLE key (tab.key) for its entire
                lifetime; only its `hidden` attribute changes. The fade-in
                motion is applied to just the currently-visible panel via a
                plain re-keyed inner element that animates without ever
                touching the hidden siblings' mount state. */}
            {TABS.map((tab) => {
                const isActive = tab.key === active;
                return (
                    <div key={tab.key} id={`workspace-panel-${tab.key}`} role="tabpanel" hidden={!isActive}>
                        {isActive ? (
                            <motion.div
                                key={`${tab.key}-fade`}
                                initial={{ opacity: 0, y: 6 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.18 }}
                            >
                                {content[tab.key]}
                            </motion.div>
                        ) : (
                            content[tab.key]
                        )}
                    </div>
                );
            })}
        </div>
    );
}
