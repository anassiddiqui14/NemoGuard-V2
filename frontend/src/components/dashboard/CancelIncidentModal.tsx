import { useState } from 'react';
import { motion } from 'framer-motion';
import { XCircle, X } from 'lucide-react';
import { modalBackdrop, modalPanel } from './shared';

/**
 * In-app confirmation modal for cancelling an AWAITING_APPROVAL incident.
 * Replaces a previous window.prompt()-based flow, which is a blocking
 * native browser dialog that doesn't match the app's visual language, is
 * inaccessible to any automated UI testing/tooling, and offers no way to
 * distinguish "cancel with no reason" from the user backing out entirely
 * (both produced an empty string from window.prompt).
 */
export function CancelIncidentModal({
    incidentId,
    submitting,
    onClose,
    onConfirm,
}: {
    incidentId: string;
    submitting: boolean;
    onClose: () => void;
    onConfirm: (reason: string) => void;
}) {
    const [reason, setReason] = useState('');

    return (
        <motion.div {...modalBackdrop} className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
            <motion.div {...modalPanel} className="glass-panel rounded-2xl shadow-2xl w-full max-w-md overflow-hidden ring-1 ring-white/[0.08]">
                <div className="px-6 py-4 border-b border-white/[0.06] flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-critical/15 flex items-center justify-center">
                            <XCircle className="w-4 h-4 text-critical" />
                        </div>
                        <h2 className="text-[15px] font-semibold text-text-primary">Cancel Incident</h2>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/[0.06] rounded-full transition-colors">
                        <X className="w-4 h-4 text-text-muted hover:text-text-primary" />
                    </button>
                </div>

                <div className="p-6 space-y-4">
                    <p className="text-[12.5px] text-text-secondary leading-relaxed">
                        This will stand <span className="font-mono text-[11.5px]">{incidentId}</span> down without
                        executing its recovery plan. This action cannot be undone.
                    </p>
                    <div>
                        <label className="text-[11px] font-semibold text-text-muted uppercase tracking-wide mb-1.5 block">
                            Reason (optional)
                        </label>
                        <input
                            type="text"
                            autoFocus
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            placeholder="e.g. Duplicate of INC-XYZ, false positive…"
                            className="w-full rounded-xl px-4 py-2.5 text-[13px] bg-white/[0.03] ring-1 ring-white/[0.06] focus:outline-none focus:ring-critical/50 transition-all"
                            onKeyDown={(e) => e.key === 'Enter' && onConfirm(reason)}
                        />
                    </div>
                </div>

                <div className="border-t border-white/[0.06] p-5 flex justify-end gap-3">
                    <motion.button
                        whileTap={{ scale: 0.96 }}
                        onClick={onClose}
                        disabled={submitting}
                        className="px-5 py-2.5 rounded-xl ring-1 ring-white/[0.08] hover:bg-white/[0.04] text-text-primary text-[13px] font-medium transition-all disabled:opacity-40"
                    >
                        Back
                    </motion.button>
                    <motion.button
                        whileTap={{ scale: 0.96 }}
                        onClick={() => onConfirm(reason)}
                        disabled={submitting}
                        className="px-6 py-2.5 rounded-xl bg-critical text-white text-[13px] font-semibold hover:brightness-110 transition-all disabled:opacity-50 flex items-center gap-2"
                    >
                        <XCircle className="w-3.5 h-3.5" /> {submitting ? 'Cancelling…' : 'Confirm Cancellation'}
                    </motion.button>
                </div>
            </motion.div>
        </motion.div>
    );
}
