import { useEffect, useState } from 'react';
import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';

const STEPS = ['Detected', 'Correlated', 'Investigating', 'Plan Ready', 'Approval', 'Executing', 'Verifying', 'Resolved'];

export function LifecycleShowcase() {
    const ref = useRef(null);
    const inView = useInView(ref, { once: false, margin: '-20% 0px -20% 0px' });
    const [activeStep, setActiveStep] = useState(0);

    useEffect(() => {
        if (!inView) return;
        const t = window.setInterval(() => {
            setActiveStep((s) => (s + 1) % STEPS.length);
        }, 900);
        return () => window.clearInterval(t);
    }, [inView]);

    return (
        <section ref={ref} className="py-24 px-6 max-w-4xl mx-auto">
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={inView ? { opacity: 1, y: 0 } : {}}
                transition={{ duration: 0.5 }}
                className="text-center mb-12"
            >
                <h2 className="text-2xl sm:text-3xl font-semibold text-text-primary tracking-tight mb-3">
                    A real state machine, not a script
                </h2>
                <p className="text-[14px] text-text-muted max-w-xl mx-auto">
                    Every incident moves through the same deterministic lifecycle — no state is skipped,
                    no step is faked.
                </p>
            </motion.div>

            <div className="glass-panel rounded-2xl p-6 sm:p-8 pt-8 ring-1 ring-white/[0.08]">
                <div className="flex items-center justify-between overflow-x-auto overflow-y-visible pb-2">
                    {STEPS.map((step, idx) => {
                        const isDone = idx < activeStep;
                        const isCurrent = idx === activeStep;
                        return (
                            <div key={step} className="flex-1 flex flex-col items-center relative min-w-[64px] pt-1">
                                <div className="flex items-center w-full relative">
                                    <div className={`h-px flex-1 ${idx === 0 ? 'invisible' : isDone || isCurrent ? 'bg-gradient-to-r from-healthy to-primary/60' : 'bg-white/[0.08]'}`} />
                                    <motion.div
                                        animate={{
                                            scale: isCurrent ? [1, 1.15, 1] : 1,
                                        }}
                                        transition={{ duration: 0.6 }}
                                        className={`w-6 h-6 rounded-full ring-2 flex items-center justify-center text-[9px] flex-shrink-0 ${isDone
                                            ? 'bg-healthy ring-healthy/40 text-app-bg'
                                            : isCurrent
                                                ? 'bg-gradient-to-br from-primary to-agent-active ring-primary/40 text-white'
                                                : 'bg-white/[0.03] ring-white/[0.08] text-text-muted'
                                            }`}
                                    >
                                        {isDone ? '✓' : idx + 1}
                                    </motion.div>
                                    <div className={`h-px flex-1 ${idx === STEPS.length - 1 ? 'invisible' : isDone ? 'bg-gradient-to-r from-primary/60 to-healthy' : 'bg-white/[0.08]'}`} />
                                </div>
                                <div className={`mt-2 text-[10px] text-center whitespace-nowrap ${isCurrent ? 'text-text-primary font-semibold' : 'text-text-muted'}`}>
                                    {step}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}
