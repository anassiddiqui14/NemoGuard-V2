import { motion } from 'framer-motion';

const steps = [
  { key: 'DETECTED', label: 'Detected' }, { key: 'CORRELATING', label: 'Correlating' },
  { key: 'INVESTIGATING', label: 'Investigating' }, { key: 'PLAN_READY', label: 'Plan ready' },
  { key: 'AWAITING_APPROVAL', label: 'Approval' }, { key: 'EXECUTING', label: 'Executing' },
  { key: 'VERIFYING', label: 'Verifying' }, { key: 'RESOLVED', label: 'Resolved' },
] as const;

export function ProcessFlow({ status }: { status: string }) {
  const current = status?.toUpperCase() || '';
  const found = steps.findIndex((step) => step.key === current);
  const currentIndex = found >= 0 ? found : current === 'TRIAGING' ? 2 : current === 'NEEDS_REVIEW' ? 3 : 0;
  return <div>
    <div className="text-[10px] uppercase tracking-[0.14em] font-bold text-text-muted mb-2.5">Incident response flow</div>
    <div className="grid grid-cols-2 sm:grid-cols-4 2xl:grid-cols-8 gap-2">
      {steps.map((step, index) => {
        const done = index < currentIndex;
        const active = index === currentIndex;
        const tone = done ? 'bg-healthy/[0.08] ring-healthy/25' : active ? 'bg-gradient-to-br from-primary/15 to-agent-active/10 ring-primary/35 shadow-md shadow-primary/10' : 'bg-white/[0.02] ring-white/[0.06]';
        return <motion.div key={step.key} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.04 }} className={`relative min-w-0 rounded-xl p-2.5 ring-1 ${tone}`}>
          <div className="flex items-center gap-2">
            <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 text-[9px] font-bold ${done ? 'bg-healthy text-app-bg' : active ? 'bg-gradient-to-br from-primary to-agent-active text-white' : 'bg-white/[0.04] text-text-muted ring-1 ring-white/[0.06]'}`}>{done ? '✓' : index + 1}</div>
            <span className={`text-[10.5px] truncate ${active ? 'text-text-primary font-semibold' : done ? 'text-text-secondary font-medium' : 'text-text-muted'}`}>{step.label}</span>
          </div>
          {active && <motion.div layoutId="active-process-step" className="absolute -bottom-px left-3 right-3 h-[2px] rounded-full bg-gradient-to-r from-primary to-agent-active" />}
        </motion.div>;
      })}
    </div>
  </div>;
}
