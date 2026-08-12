import { motion } from 'framer-motion';

const steps = [
  ['DETECTED', 'Detected'], ['CORRELATING', 'Correlating'], ['INVESTIGATING', 'Investigating'], ['PLAN_READY', 'Plan ready'],
  ['AWAITING_APPROVAL', 'Approval'], ['EXECUTING', 'Executing'], ['VERIFYING', 'Verifying'], ['RESOLVED', 'Resolved'],
] as const;

export function ConnectedProcessFlow({ status }: { status: string }) {
  const value = status?.toUpperCase() || '';
  const located = steps.findIndex(([key]) => key === value);
  const current = located >= 0 ? located : value === 'TRIAGING' ? 2 : value === 'NEEDS_REVIEW' ? 3 : 0;
  return <div>
    <div className="text-[10px] uppercase tracking-[0.14em] font-bold text-text-muted mb-2.5">Incident response flow</div>
    <div className="grid grid-cols-2 sm:grid-cols-4 2xl:grid-cols-8 gap-2">
      {steps.map(([key, label], index) => {
        const done = index < current;
        const active = index === current;
        const card = done ? 'bg-healthy/[0.08] ring-healthy/25' : active ? 'bg-gradient-to-br from-primary/15 to-agent-active/10 ring-primary/35 shadow-md shadow-primary/10' : 'bg-white/[0.02] ring-white/[0.06]';
        const connector = done ? 'bg-healthy/60' : active ? 'bg-gradient-to-r from-primary to-agent-active' : 'bg-border-color';
        return <motion.div key={key} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.04 }} aria-current={active ? 'step' : undefined} className={`relative min-w-0 rounded-xl p-3 ring-1 ${card}`}>
          <div className="flex items-center gap-2">
            <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 text-[9px] font-bold ${done ? 'bg-healthy text-app-bg' : active ? 'bg-gradient-to-br from-primary to-agent-active text-white' : 'bg-white/[0.04] text-text-muted ring-1 ring-white/[0.06]'}`}>{done ? '✓' : index + 1}</div>
            <div className="min-w-0"><span className={`block text-[10.5px] truncate ${active ? 'text-text-primary font-semibold' : done ? 'text-text-secondary font-medium' : 'text-text-muted'}`}>{label}</span><span className={`hidden 2xl:block text-[8.5px] uppercase tracking-wide mt-0.5 ${active ? 'text-agent-active' : done ? 'text-healthy' : 'text-text-muted'}`}>{active ? 'In progress' : done ? 'Complete' : 'Upcoming'}</span></div>
          </div>
          {index < steps.length - 1 && <motion.div initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ delay: 0.16 + index * 0.04, duration: 0.3 }} className={`hidden 2xl:block origin-left absolute top-1/2 -right-2 w-2 h-[2px] z-10 ${connector}`} />}
          {active && <motion.div layoutId="connected-active-step" className="absolute -bottom-px left-3 right-3 h-[2px] rounded-full bg-gradient-to-r from-primary to-agent-active" />}
        </motion.div>;
      })}
    </div>
  </div>;
}
