import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
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
            <div className="w-full rounded-xl bg-white/[0.02] p-1 ring-1 ring-white/[0.05]">
                <div className="flex flex-wrap gap-1">
                    {TABS.map((tab) => (
                        <button
                            key={tab.key}
                            onClick={() => setActive(tab.key)}
                            className={`relative flex-1 min-w-[92px] flex items-center justify-center gap-1.5 px-2.5 py-2 rounded-lg text-[12px] font-medium transition-colors ${active === tab.key
                                ? 'text-text-primary'
                                : 'text-text-muted hover:text-text-secondary'
                                }`}
                        >
                            {active === tab.key && (
                                <motion.div
                                    layoutId="workspace-tab-pill"
                                    className="absolute inset-0 rounded-lg bg-white/[0.06] ring-1 ring-white/[0.08]"
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

            <AnimatePresence mode="wait">
                <motion.div
                    key={active}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.18 }}
                >
                    {content[active]}
                </motion.div>
            </AnimatePresence>
        </div>
    );
}
