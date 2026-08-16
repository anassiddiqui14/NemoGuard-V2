import { useRef, useState } from 'react';
import { motion, useInView } from 'framer-motion';
import { Radio, ShieldCheck, Search, RotateCcw, Terminal, Lock } from 'lucide-react';

const FEATURES = [
    { icon: <Radio className="w-4.5 h-4.5" />, title: 'Real-time agent visibility', desc: 'Every agent state, tool call, and handoff streams live — nothing happens off-screen.' },
    { icon: <ShieldCheck className="w-4.5 h-4.5" />, title: 'Human-in-the-loop approval', desc: 'Medium- and high-risk actions always wait for an explicit human decision.' },
    { icon: <Search className="w-4.5 h-4.5" />, title: 'Evidence-first RCA', desc: 'Root-cause hypotheses are ranked and linked to structured evidence, never asserted blindly.' },
    { icon: <RotateCcw className="w-4.5 h-4.5" />, title: 'Automated rollback & verification', desc: 'An independent verifier confirms recovery — and rolls back automatically if it fails.' },
    { icon: <Terminal className="w-4.5 h-4.5" />, title: 'SSE-based live console', desc: 'Server-Sent Events stream structured operational events straight from the backend.' },
    { icon: <Lock className="w-4.5 h-4.5" />, title: 'Role-based access', desc: 'JWT-backed RBAC gates who can approve and execute recovery plans.' },
];

function TiltCard({ icon, title, desc, index }: { icon: React.ReactNode; title: string; desc: string; index: number }) {
    const [tilt, setTilt] = useState({ x: 0, y: 0 });

    const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const px = (e.clientX - rect.left) / rect.width - 0.5;
        const py = (e.clientY - rect.top) / rect.height - 0.5;
        setTilt({ x: py * -8, y: px * 8 });
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-10% 0px' }}
            transition={{ delay: index * 0.06 }}
            onMouseMove={handleMouseMove}
            onMouseLeave={() => setTilt({ x: 0, y: 0 })}
            style={{ transformStyle: 'preserve-3d' }}
            animate={{ rotateX: tilt.x, rotateY: tilt.y }}
            className="glass-panel rounded-2xl p-5 ring-1 ring-white/[0.08] cursor-default"
        >
            <div className="w-9 h-9 rounded-lg bg-primary/15 text-primary flex items-center justify-center mb-3.5">
                {icon}
            </div>
            <div className="text-[14px] font-semibold text-text-primary mb-1.5">{title}</div>
            <div className="text-[12px] text-text-muted leading-relaxed">{desc}</div>
        </motion.div>
    );
}

export function FeatureGrid() {
    const ref = useRef(null);
    const inView = useInView(ref, { once: true, margin: '-10% 0px' });

    return (
        <section ref={ref} className="py-24 px-6 max-w-5xl mx-auto">
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={inView ? { opacity: 1, y: 0 } : {}}
                transition={{ duration: 0.5 }}
                className="text-center mb-12"
            >
                <h2 className="text-2xl sm:text-3xl font-semibold text-text-primary tracking-tight mb-3">
                    Built like a real incident-response product
                </h2>
                <p className="text-[14px] text-text-muted max-w-xl mx-auto">
                    Not a chatbot wrapper. A deterministic control plane with agents doing the legwork.
                </p>
            </motion.div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {FEATURES.map((f, idx) => (
                    <TiltCard key={f.title} icon={f.icon} title={f.title} desc={f.desc} index={idx} />
                ))}
            </div>
        </section>
    );
}
