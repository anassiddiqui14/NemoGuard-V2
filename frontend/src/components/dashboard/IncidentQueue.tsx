import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, RefreshCw, ShieldAlert, Radio } from 'lucide-react';
import { EmptyState, needsAttention, severityPill } from './shared';
import type { IncidentSummary } from './shared';

interface Props {
    openIncidents: IncidentSummary[];
    activeIncidentId: string | null;
    setActiveIncidentId: (id: string) => void;
    refreshQueue: () => void;
}

export function IncidentQueue({ openIncidents, activeIncidentId, setActiveIncidentId, refreshQueue }: Props) {
    return (
        <aside className="w-[300px] flex-shrink-0 border-r border-white/[0.06] bg-black/20 flex flex-col z-10">
            <div className="px-5 py-4 flex items-center justify-between">
                <div>
                    <h2 className="font-semibold text-[13px] text-text-primary tracking-tight">Incident Queue</h2>
                    <p className="text-[11px] text-text-muted mt-0.5">{openIncidents.length} active incident{openIncidents.length !== 1 ? 's' : ''}</p>
                </div>
                <button
                    onClick={refreshQueue}
                    className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-white/[0.05] transition-colors"
                    title="Refresh"
                >
                    <RefreshCw className="w-3.5 h-3.5" />
                </button>
            </div>

            <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-2">
                {openIncidents.length === 0 ? (
                    <EmptyState
                        icon={<AlertTriangle className="w-5 h-5" />}
                        title="No active incidents"
                        subtitle="Trigger a scenario from the Scenario Lab, or wait for a real webhook alert."
                    />
                ) : (
                    <AnimatePresence initial={false}>
                        {openIncidents.map((inc) => {
                            const isActive = inc.incident_id === activeIncidentId;
                            const attn = needsAttention(inc.status);
                            const isLive = ['INVESTIGATING', 'TRIAGING', 'CORRELATING'].includes(inc.status?.toUpperCase());
                            return (
                                <motion.button
                                    layout
                                    initial={{ opacity: 0, y: 8 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, scale: 0.97 }}
                                    key={inc.incident_id}
                                    onClick={() => setActiveIncidentId(inc.incident_id)}
                                    className={`relative w-full text-left rounded-xl p-3.5 transition-all duration-200 group ${isActive
                                            ? 'bg-gradient-to-br from-primary/[0.12] to-agent-active/[0.06] ring-1 ring-primary/30 shadow-lg shadow-primary/5'
                                            : 'bg-white/[0.02] hover:bg-white/[0.04] ring-1 ring-white/[0.04] hover:ring-white/[0.08]'
                                        }`}
                                >
                                    <div className="flex items-center gap-2 mb-2">
                                        {severityPill(inc.severity)}
                                        {attn && <ShieldAlert className="w-3.5 h-3.5 text-warning flex-shrink-0" />}
                                        {isLive && <Radio className="w-3 h-3 text-agent-active animate-pulse flex-shrink-0 ml-auto" />}
                                        <div className={`text-[10px] font-mono truncate ${isLive ? '' : 'ml-auto'} text-text-muted`}>{inc.incident_id}</div>
                                    </div>
                                    <div className={`font-medium text-[13px] leading-snug line-clamp-2 mb-2.5 ${isActive ? 'text-text-primary' : 'text-text-secondary group-hover:text-text-primary'}`}>
                                        {inc.title}
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-[10px] uppercase tracking-wide font-semibold text-text-muted">
                                            {inc.status?.replace(/_/g, ' ')}
                                        </span>
                                    </div>
                                    {isActive && (
                                        <motion.div
                                            layoutId="active-rail"
                                            className="absolute left-0 top-2 bottom-2 w-[3px] rounded-full bg-gradient-to-b from-primary to-agent-active"
                                        />
                                    )}
                                </motion.button>
                            );
                        })}
                    </AnimatePresence>
                )}
            </div>
        </aside>
    );
}
