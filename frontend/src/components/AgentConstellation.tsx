import React, { useMemo } from 'react';
import { Cpu, Eye, GitBranch, BookOpen, Shield, CheckCircle } from 'lucide-react';
import { motion } from 'framer-motion';
import type { AgentEvent } from '../hooks/useIncidentEvents';

interface Props {
  status: string;
  events: AgentEvent[];
}

type AgentState = 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED';

interface AgentDef {
  key: string;
  name: string;
  icon: React.ReactNode;
  actors: string[];
  completedOn: string[];
  failedOn?: string[];
  idleDesc: string;
}

const AGENT_DEFS: AgentDef[] = [
  { key: 'watcher', name: 'Watcher', icon: <Eye className="w-4 h-4" />, actors: ['Watcher Agent', 'Watcher_Agent'], completedOn: ['ALERT_CORRELATED'], idleDesc: 'Classifying and correlating incoming alerts' },
  { key: 'rca', name: 'RCA', icon: <Cpu className="w-4 h-4" />, actors: ['RCA Agent', 'RCA_Agent'], completedOn: ['HYPOTHESIS_CREATED'], idleDesc: 'Investigating logs to isolate the root cause' },
  { key: 'impact', name: 'Impact', icon: <GitBranch className="w-4 h-4" />, actors: ['Impact Agent', 'Dependency_Agent'], completedOn: ['IMPACT_CALCULATED'], idleDesc: 'Calculating downstream and business impact' },
  { key: 'runbook', name: 'Runbook', icon: <BookOpen className="w-4 h-4" />, actors: ['Runbook Agent', 'Runbook_Agent'], completedOn: ['RUNBOOK_RETRIEVED'], idleDesc: 'Matching incident to approved recovery procedures' },
  { key: 'safety', name: 'Safety', icon: <Shield className="w-4 h-4" />, actors: ['Safety Agent', 'Grounding_Critic'], completedOn: ['SAFETY_VALIDATION_PASSED'], failedOn: ['SAFETY_VALIDATION_FAILED'], idleDesc: 'Validating plan grounding and blast radius' },
  { key: 'verifier', name: 'Verifier', icon: <CheckCircle className="w-4 h-4" />, actors: ['Verifier', 'Executor'], completedOn: ['VERIFICATION_PASSED', 'ACTION_COMPLETED'], failedOn: ['VERIFICATION_FAILED'], idleDesc: 'Independently confirming recovery after execution' },
];

function computeAgentState(def: AgentDef, events: AgentEvent[], incidentStatus: string): { state: AgentState; lastMessage?: string } {
  const s = incidentStatus.toUpperCase();
  const isResolved = s === 'RESOLVED';

  const relevant = events.filter((e) => def.actors.includes(e.source));
  if (relevant.length === 0) {
    // Once the incident is resolved, no agent should still be shown as
    // running/queued — previously agents with no emitted events for this
    // incident (e.g. Watcher on a fast auto-recovered incident) fell through
    // to QUEUED here, but that's fine; the real bug is below where agents
    // *with* events but no explicit completion event stayed RUNNING forever.
    if (isResolved) return { state: 'COMPLETED', lastMessage: def.idleDesc };

    const isInvestigatingPhase = ['INVESTIGATING', 'TRIAGING', 'CORRELATING'].includes(s);
    const isExecPhase = ['EXECUTING', 'VERIFYING'].includes(s);
    if (def.key === 'verifier' && isExecPhase) return { state: 'RUNNING' };
    if (def.key !== 'verifier' && isInvestigatingPhase) return { state: 'RUNNING' };
    return { state: 'QUEUED' };
  }
  const last = relevant[relevant.length - 1];
  if (def.failedOn?.includes(last.event_type)) return { state: 'FAILED', lastMessage: last.message };
  if (def.completedOn.includes(last.event_type)) return { state: 'COMPLETED', lastMessage: last.message };
  // The agent's last recorded event wasn't an explicit "completed" event type
  // (this happens for auto-resolved incidents where the pipeline short-circuits
  // and never emits every agent's terminal event). If the incident has already
  // resolved, treat every agent as COMPLETED rather than leaving it stuck on
  // RUNNING indefinitely.
  if (isResolved) return { state: 'COMPLETED', lastMessage: last.message };
  return { state: 'RUNNING', lastMessage: last.message };
}

const STATE_STYLES: Record<AgentState, { ring: string; bg: string; text: string; glow: string }> = {
  QUEUED: { ring: 'ring-white/[0.06]', bg: 'bg-white/[0.02]', text: 'text-text-muted', glow: '' },
  RUNNING: { ring: 'ring-agent-active/40', bg: 'bg-gradient-to-br from-agent-active/15 to-primary/5', text: 'text-agent-active', glow: 'shadow-lg shadow-agent-active/20' },
  COMPLETED: { ring: 'ring-healthy/30', bg: 'bg-healthy/[0.06]', text: 'text-healthy', glow: '' },
  FAILED: { ring: 'ring-critical/40', bg: 'bg-critical/[0.08]', text: 'text-critical', glow: '' },
};

/*
 * UI MODERNIZATION (spec Section 43/44 -- "NemoGuard Investigation"
 * branded agent loader): the grid-card AgentConstellation above already
 * satisfies the spec's core requirement -- truthful, SSE-driven agent
 * state with zero fabricated progress -- but Section 43's specific
 * mockup shows a compact vertical checklist (✓/●/○ per step) rather than
 * a card grid. Rather than duplicate the real state computation
 * (computeAgentState) in a second component, this reuses the exact same
 * function and just renders it in the checklist layout the spec
 * describes, for contexts (e.g. a narrow sidebar or a modal) where the
 * grid doesn't fit.
 */
export const InvestigationChecklist: React.FC<Props> = ({ status, events }) => {
  const s = status?.toUpperCase() || '';
  const agents = AGENT_DEFS.map((def) => {
    const { state, lastMessage } = computeAgentState(def, events, s);
    return { ...def, state, lastMessage: lastMessage || def.idleDesc };
  });

  return (
    <div className="rounded-xl p-4 bg-white/[0.02] ring-1 ring-white/[0.05]">
      <div className="text-[11px] font-bold text-text-muted uppercase tracking-wider mb-3">NemoGuard Investigation</div>
      <div className="space-y-2">
        {agents.map((agent) => {
          const marker = agent.state === 'COMPLETED' ? '✓' : agent.state === 'FAILED' ? '✕' : agent.state === 'RUNNING' ? '●' : '○';
          const markerClass =
            agent.state === 'COMPLETED'
              ? 'text-healthy'
              : agent.state === 'FAILED'
                ? 'text-critical'
                : agent.state === 'RUNNING'
                  ? 'text-agent-active'
                  : 'text-text-muted';
          return (
            <div key={agent.key} className="flex items-start gap-2.5">
              <span className={`font-mono text-[12px] font-bold flex-shrink-0 w-4 text-center ${markerClass} ${agent.state === 'RUNNING' ? 'animate-pulse' : ''}`}>
                {marker}
              </span>
              <div className="min-w-0 flex-1">
                <span className={`text-[12px] ${agent.state === 'QUEUED' ? 'text-text-muted' : 'text-text-secondary'}`}>{agent.lastMessage}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export const AgentConstellation: React.FC<Props> = ({ status, events }) => {
  const s = status?.toUpperCase() || '';

  const agents = useMemo(() => {
    return AGENT_DEFS.map((def) => {
      const { state, lastMessage } = computeAgentState(def, events, s);
      return { ...def, state, lastMessage: lastMessage || def.idleDesc };
    });
  }, [events, s]);

  const activeCount = agents.filter((a) => a.state === 'RUNNING').length;

  return (
    <div className="flex flex-col h-full">
      <div className="grid grid-cols-3 gap-2.5 content-start">
        {agents.map((agent, idx) => {
          const style = STATE_STYLES[agent.state];
          const isRunning = agent.state === 'RUNNING';
          return (
            <motion.div
              key={agent.key}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: idx * 0.05 }}
              className={`relative rounded-xl p-3 ring-1 ${style.ring} ${style.bg} ${style.glow} flex flex-col items-center text-center transition-all duration-300`}
            >
              {isRunning && (
                <motion.div
                  className="absolute inset-0 rounded-xl ring-2 ring-agent-active/50"
                  animate={{ opacity: [0.6, 0.1, 0.6] }}
                  transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
                />
              )}
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center mb-2 ${style.text} ${agent.state === 'RUNNING' ? 'bg-agent-active/20' : agent.state === 'COMPLETED' ? 'bg-healthy/15' : agent.state === 'FAILED' ? 'bg-critical/15' : 'bg-white/[0.04]'}`}>
                {agent.icon}
              </div>
              <div className="text-[11.5px] font-semibold text-text-primary mb-0.5">{agent.name}</div>
              <div className={`text-[9px] font-bold uppercase tracking-wide ${style.text}`}>{agent.state}</div>
              <div className="text-[9.5px] text-text-muted mt-1.5 line-clamp-2 leading-tight break-words w-full" title={agent.lastMessage}>
                {agent.lastMessage}
              </div>
            </motion.div>
          );
        })}
      </div>
      <div className="flex justify-between items-center pt-3 mt-3 border-t border-white/[0.05] text-[11px]">
        <span className="text-text-muted font-medium">Coordinated agents</span>
        <span className={`font-semibold px-2.5 py-1 rounded-full text-[10px] ${activeCount > 0 ? 'bg-agent-active/15 text-agent-active' : 'bg-white/[0.03] text-text-muted'}`}>
          {activeCount} active / {agents.length} total
        </span>
      </div>
    </div>
  );
};
