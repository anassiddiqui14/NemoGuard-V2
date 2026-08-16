import { useState } from 'react';
import { motion } from 'framer-motion';
import { CheckSquare, FileText, AlertTriangle, ShieldCheck, Send, X, CheckCircle, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import { modalBackdrop, modalPanel } from './dashboard/shared';
import { authFetch } from '../contexts/AuthGateContext';

const RISK_STYLES: Record<string, string> = {
  LOW: 'border-l-healthy',
  MEDIUM: 'border-l-warning',
  HIGH: 'border-l-critical',
};

export function PlanApprovalModal({ incidentId, plan, onClose, onRefreshPlan }: { incidentId: string, plan: any, onClose: () => void, onRefreshPlan: () => void }) {
  const [feedback, setFeedback] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!plan) return null;

  // Once the plan has already been executed/approved, this modal should be
  // read-only — previously the Approve/Revise controls stayed active even
  // for a plan whose incident had already resolved.
  const isFinalized = plan.status === 'EXECUTED' || plan.status === 'APPROVED';

  const approvePlan = async () => {
    setSubmitting(true);
    try {
      const res = await authFetch(`/api/v2/incidents/${incidentId}/plans/${plan.action_plan_id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: 'approve', plan_hash: plan.plan_hash }),
      });
      // Previously the response was never checked — a failed approval (401
      // unauthorized, 409 stale plan_hash, or any backend 500) was silently
      // swallowed and the modal closed as if it succeeded, leaving the
      // incident stuck un-executed with no visible error to the operator.
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try {
          const body = await res.json();
          detail = body?.detail || detail;
        } catch {
          // response wasn't JSON; fall back to the status code above
        }
        toast.error(`Failed to approve plan: ${detail}`);
        return;
      }
      toast.success('Plan approved — executing recovery actions.');
      onRefreshPlan();
      onClose();
    } catch (e) {
      toast.error(`Failed to approve plan: ${e instanceof Error ? e.message : 'network error'}`);
    } finally {
      setSubmitting(false);
    }
  };

  const rejectPlan = async () => {
    if (!feedback) return alert('Please provide feedback for the agent');
    setSubmitting(true);
    try {
      const res = await authFetch(`/api/v2/incidents/${incidentId}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback }),
      });
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try {
          const body = await res.json();
          detail = body?.detail || detail;
        } catch {
          // response wasn't JSON; fall back to the status code above
        }
        toast.error(`Failed to submit feedback: ${detail}`);
        return;
      }
      toast.success('Feedback submitted — plan is being revised.');
      onRefreshPlan();
      onClose();
    } catch (e) {
      toast.error(`Failed to submit feedback: ${e instanceof Error ? e.message : 'network error'}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <motion.div {...modalBackdrop} className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <motion.div {...modalPanel} className="glass-panel rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden ring-1 ring-white/[0.08]">
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
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.2, delay: idx * 0.04 }}
                  className={`flex rounded-xl bg-white/[0.02] ring-1 ring-white/[0.05] p-3.5 border-l-[3px] ${RISK_STYLES[step.risk_level] || 'border-l-white/10'}`}
                >
                  <div className="w-7 h-7 rounded-lg bg-white/[0.05] text-text-secondary text-[11px] flex items-center justify-center mr-3 font-semibold flex-shrink-0">
                    {idx + 1}
                  </div>
                  <div>
                    <div className="font-medium text-[13px] text-text-primary">{step.action_type}</div>
                    <div className="text-[10.5px] text-text-muted mt-1 font-mono bg-black/20 px-2 py-0.5 rounded inline-block ring-1 ring-white/[0.05]">
                      {step.tool_name} · {step.risk_level} risk
                    </div>
                  </div>
                </motion.div>
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
            <motion.button
              whileTap={{ scale: 0.96 }}
              onClick={rejectPlan}
              disabled={submitting || !feedback || isFinalized}
              className="px-5 py-2.5 rounded-xl ring-1 ring-white/[0.08] hover:bg-white/[0.04] text-text-primary text-[13px] font-medium transition-all disabled:opacity-40 flex items-center gap-2"
            >
              <Send className="w-3.5 h-3.5" /> Revise
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.96 }}
              onClick={approvePlan}
              disabled={submitting || isFinalized}
              className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-primary to-agent-active hover:brightness-110 text-white text-[13px] font-semibold transition-all disabled:opacity-50 flex items-center gap-2 shadow-lg shadow-primary/20"
            >
              <ShieldCheck className="w-4 h-4" /> {isFinalized ? 'Already Executed' : 'Approve & Execute'}
            </motion.button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
