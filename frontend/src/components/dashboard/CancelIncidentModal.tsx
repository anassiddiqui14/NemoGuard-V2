import { useState } from 'react';
import { motion } from 'framer-motion';
import { XCircle } from 'lucide-react';
import { Modal } from '../../design-system/components/Modal';
import { Button } from '../../design-system/components/Button';

/**
 * In-app confirmation modal for cancelling an AWAITING_APPROVAL incident.
 * Replaces a previous window.prompt()-based flow, which is a blocking
 * native browser dialog that doesn't match the app's visual language, is
 * inaccessible to any automated UI testing/tooling, and offers no way to
 * distinguish "cancel with no reason" from the user backing out entirely
 * (both produced an empty string from window.prompt).
 *
 * UI MODERNIZATION (Phase 2): migrated to the shared Modal primitive --
 * this is a drop-in visual match for the previous hand-rolled markup, but
 * now gets Escape-to-close, a keyboard focus trap, and body-scroll lock
 * for free, none of which the previous implementation had.
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
        <Modal
            open
            onClose={onClose}
            title="Cancel Incident"
            icon={<XCircle className="w-4 h-4 text-critical" />}
            iconClassName="bg-critical/15"
            maxWidth="max-w-md"
            footer={
                <>
                    <motion.button
                        whileTap={{ scale: 0.96 }}
                        onClick={onClose}
                        disabled={submitting}
                        className="px-5 py-2.5 rounded-xl ring-1 ring-white/[0.08] hover:bg-white/[0.04] text-text-primary text-[13px] font-medium transition-all disabled:opacity-40"
                    >
                        Back
                    </motion.button>
                    <Button
                        variant="danger"
                        className="!bg-critical !text-white !ring-0 px-6 py-2.5 text-[13px]"
                        onClick={() => onConfirm(reason)}
                        disabled={submitting}
                        leadingIcon={<XCircle className="w-3.5 h-3.5" />}
                    >
                        {submitting ? 'Cancelling…' : 'Confirm Cancellation'}
                    </Button>
                </>
            }
        >
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
        </Modal>
    );
}
