import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';

export function CtaBand() {
    const navigate = useNavigate();
    const hasToken = !!localStorage.getItem('nemoguard_token');

    const handlePrimary = () => {
        navigate(hasToken ? '/app' : '/login');
    };

    return (
        <section className="py-24 px-6">
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-10% 0px' }}
                className="max-w-2xl mx-auto text-center glass-panel rounded-3xl p-10 sm:p-14 ring-1 ring-white/[0.08] relative overflow-hidden"
            >
                <div
                    className="absolute inset-0 opacity-30"
                    style={{ backgroundImage: 'radial-gradient(ellipse 60% 60% at 50% 0%, rgba(99,102,241,0.3), transparent)' }}
                />
                <div className="relative z-10">
                    <h2 className="text-2xl sm:text-3xl font-semibold text-text-primary tracking-tight mb-4">
                        See it work end to end
                    </h2>
                    <p className="text-[14px] text-text-muted mb-8 max-w-md mx-auto">
                        Step into the Command Center and watch agents investigate, decide, and recover — with you
                        holding the approval.
                    </p>
                    <button
                        onClick={handlePrimary}
                        className="press-scale inline-flex items-center gap-2 text-[14px] px-6 py-3 rounded-xl bg-gradient-to-r from-primary to-agent-active text-white hover:brightness-110 transition font-semibold shadow-lg shadow-primary/30"
                    >
                        {hasToken ? 'Enter Command Center' : 'Sign in to enter'}
                        <ArrowRight className="w-4 h-4" />
                    </button>
                </div>
            </motion.div>
        </section>
    );
}
