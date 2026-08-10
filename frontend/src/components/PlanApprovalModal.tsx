import { useState } from 'react';
import { CheckSquare, FileText, AlertTriangle, ShieldCheck, Send, X, CheckCircle, Sparkles } from 'lucide-react';

const RISK_STYLES: Record<string, string> = {
  LOW: 'border-l-healthy',
  MEDIUM: 'border-l-warning',
  HIGH: 'border-l-critical',
};

export function PlanApprovalModal({ incidentId, plan, onClose, onRefreshPlan }: { incidentId: string, plan: any, onClose: () => void, onRefreshPlan: () => void }) {
  const [feedback, setFeedback] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!plan) return null;

  const approvePlan = async () => {
    setSubmitting(true);
    try {
      const token = localStorage.getItem('nemoguard_token') || '';
      await fetch(`/api/v2/incidents/${incidentId}/plans/${plan.action_plan_id}/approve`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: 'approve', plan_hash: plan.plan_hash }),
      });
      onRefreshPlan();
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  const rejectPlan = async () => {
    if (!feedback) return alert('Please provide feedback for the agent');
    setSubmitting(true);
    try {
      const token = localStorage.getItem('nemoguard_token') || '';
      await fetch(`/api/v2/incidents/${incidentId}/feedback`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback }),
      });
      onRefreshPlan();
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="glass-panel rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden ring-1 ring-white/[0.08]">
        <div className="px-6 py-4 border-b border-white/[0.06] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary/20 to-agent-active/20 flex items-center justify-center">
              <CheckSquare className="w-4 h-4 text-primary" />
            </div>
            <h2 className="text-[15px] font-semibold text-text-primary">Approve Recovery Plan</h2>
            {plan.plan_version > 1 && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-agent-active/15 text-agent-active">v{plan.plan_version}</span>
            )}
          </div>
          <button onClick={onClose} className="p-2 hover:bg-white/[0.06] rounded-full transition-colors">
            <X className="w-4 h-4 text-text-muted hover:text-text-primary" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto space-y-4 flex-1">
          <div className="rounded-xl p-4 flex gap-3 bg-primary/[0.06] ring-1 ring-primary/20">
            <FileText className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-[13px] text-text-primary">Rationale</h4>
              <p className="text-[12.5px] text-text-secondary mt-1 leading-relaxed">{plan?.rationale}</p>
            </div>
          </div>

          <div className="rounded-xl p-4 flex gap-3 bg-healthy/[0.06] ring-1 ring-healthy/20">
            <CheckCircle className="w-5 h-5 text-healthy flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-[13px] text-text-primary">Expected Outcome</h4>
              <p className="text-[12.5px] text-text-secondary mt-1 leading-relaxed">{plan?.expected_outcome}</p>
            </div>
          </div>

          <div className="rounded-xl p-4 flex gap-3 bg-warning/[0.06] ring-1 ring-warning/20">
            <AlertTriangle className="w-5 h-5 text-warning flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-[13px] text-text-primary">Risk Assessment</h4>
              <p className="text-[12.5px] text-text-secondary mt-1 leading-relaxed">{plan?.overall_risk} risk. {plan?.rollback_summary}</p>
            </div>
          </div>

          <div>
            <h4 className="font-semibold text-text-primary mb-3 text-[14px] flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-agent-active" /> Execution Steps
            </h4>
            <div className="space-y-2.5">
              {plan?.steps?.map((step: any, idx: number) => (
                <div key={idx} className={`flex rounded-xl bg-white/[0.02] ring-1 ring-white/[0.05] p-3.5 border-l-[3px] ${RISK_STYLES[step.risk_level] || 'border-l-white/10'}`}>
                  <div className="w-7 h-7 rounded-lg bg-white/[0.05] text-text-secondary text-[11px] flex items-center justify-center mr-3 font-semibold flex-shrink-0">
                    {idx + 1}
                  </div>
                  <div>
                    <div className="font-medium text-[13px] text-text-primary">{step.action_type}</div>
                    <div className="text-[10.5px] text-text-muted mt-1 font-mono bg-black/20 px-2 py-0.5 rounded inline-block ring-1 ring-white/[0.05]">
                      {step.tool_name} · {step.risk_level} risk
                    </div>
                  </div>
                </div>
              ))}
              {(!plan?.steps || plan.steps.length === 0) && (
                <div className="text-[12.5px] text-text-muted italic p-4 text-center rounded-xl ring-1 ring-white/[0.06]">No specific steps returned. Action plan may be generic.</div>
              )}
            </div>
          </div>
        </div>

        <div className="border-t border-white/[0.06] p-5">
          <div className="flex gap-3">
            <input
              type="text"
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="Provide feedback to revise the plan…"
              className="flex-1 rounded-xl px-4 py-2.5 text-[13px] bg-white/[0.03] ring-1 ring-white/[0.06] focus:outline-none focus:ring-primary/50 transition-all"
              onKeyDown={(e) => e.key === 'Enter' && rejectPlan()}
            />
            <button
              onClick={rejectPlan}
              disabled={submitting || !feedback}
              className="px-5 py-2.5 rounded-xl ring-1 ring-white/[0.08] hover:bg-white/[0.04] text-text-primary text-[13px] font-medium transition-all disabled:opacity-40 flex items-center gap-2"
            >
              <Send className="w-3.5 h-3.5" /> Revise
            </button>
            <button
              onClick={approvePlan}
              disabled={submitting}
              className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-primary to-agent-active hover:brightness-110 text-white text-[13px] font-semibold transition-all disabled:opacity-50 flex items-center gap-2 shadow-lg shadow-primary/20"
            >
              <ShieldCheck className="w-4 h-4" /> Approve & Execute
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
