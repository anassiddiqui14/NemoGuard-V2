import { useEffect, useRef, useState } from 'react';
import { motion, useInView } from 'framer-motion';

interface Metric {
    label: string;
    value: number;
    suffix: string;
    decimals?: number;
}

const METRICS: Metric[] = [
    { label: 'Alerts consolidated per incident (demo env)', value: 7, suffix: '→1' },
    { label: 'Mean time to recovery (demo env)', value: 3.7, suffix: 'm', decimals: 1 },
    { label: 'Actions gated by human approval', value: 100, suffix: '%' },
    { label: 'Verification checks per plan (demo env)', value: 6, suffix: '' },
];

function useCountUp(target: number, active: boolean, decimals = 0) {
    const [value, setValue] = useState(0);
    useEffect(() => {
        if (!active) return;
        const duration = 1200;
        const start = performance.now();
        let raf: number;
        const tick = (now: number) => {
            const progress = Math.min((now - start) / duration, 1);
            setValue(target * progress);
            if (progress < 1) raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(raf);
    }, [active, target]);
    return value.toFixed(decimals);
}

function MetricCounter({ metric, active }: { metric: Metric; active: boolean }) {
    const display = useCountUp(metric.value, active, metric.decimals);
    return (
        <div className="text-center">
            <div className="text-3xl sm:text-4xl font-bold text-text-primary tabular-nums">
                {display}
                <span className="text-lg text-agent-active">{metric.suffix}</span>
            </div>
            <div className="text-[11.5px] text-text-muted mt-2 max-w-[180px] mx-auto leading-snug">{metric.label}</div>
        </div>
    );
}

export function MetricsStrip() {
    const ref = useRef(null);
    const inView = useInView(ref, { once: true, margin: '-10% 0px' });

    return (
        <section ref={ref} className="py-20 px-6">
            <div className="max-w-5xl mx-auto">
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={inView ? { opacity: 1 } : {}}
                    className="text-center mb-3"
                >
                    <span className="text-[10.5px] font-semibold uppercase tracking-wider text-text-muted">Demo environment metrics</span>
                </motion.div>
                <div className="glass-panel rounded-2xl p-8 ring-1 ring-white/[0.08] grid grid-cols-2 sm:grid-cols-4 gap-8">
                    {METRICS.map((m, idx) => (
                        <motion.div
                            key={m.label}
                            initial={{ opacity: 0, y: 12 }}
                            animate={inView ? { opacity: 1, y: 0 } : {}}
                            transition={{ delay: idx * 0.08 }}
                        >
                            <MetricCounter metric={m} active={inView} />
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
