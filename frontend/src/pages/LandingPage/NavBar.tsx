import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, useScroll } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { BrandLockup } from './Brand';

const LINKS = [
    { label: 'How it works', href: '#lifecycle' },
    { label: 'Evidence', href: '#evidence' },
    { label: 'Metrics', href: '#metrics' },
    { label: 'Platform', href: '#features' },
];

export function NavBar() {
    const navigate = useNavigate();
    const { scrollYProgress } = useScroll();
    const [scrolled, setScrolled] = useState(false);
    const hasToken = !!localStorage.getItem('nemoguard_token');

    useEffect(() => {
        const onScroll = () => setScrolled(window.scrollY > 24);
        onScroll();
        window.addEventListener('scroll', onScroll, { passive: true });
        return () => window.removeEventListener('scroll', onScroll);
    }, []);

    const scrollTo = (href: string) => {
        const el = document.querySelector(href);
        el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    return (
        <header
            className={`fixed top-0 left-0 right-0 z-50 transition-colors duration-300 ${scrolled ? 'bg-app-bg/80 backdrop-blur-xl border-b border-white/[0.06]' : 'bg-transparent'
                }`}
        >
            <nav className="max-w-6xl mx-auto flex items-center justify-between px-6 h-16">
                <button onClick={() => scrollTo('#top')} className="flex items-center">
                    <BrandLockup iconClassName="w-5.5 h-5.5" textClassName="text-[14.5px]" />
                </button>

                <div className="hidden md:flex items-center gap-7">
                    {LINKS.map((link) => (
                        <button
                            key={link.href}
                            onClick={() => scrollTo(link.href)}
                            className="text-[13px] text-text-secondary hover:text-text-primary transition-colors"
                        >
                            {link.label}
                        </button>
                    ))}
                </div>

                <button
                    onClick={() => navigate(hasToken ? '/app' : '/login')}
                    className="press-scale inline-flex items-center gap-1.5 text-[13px] font-semibold px-4 py-2 rounded-lg bg-white/[0.05] ring-1 ring-white/[0.1] text-text-primary hover:bg-white/[0.08] transition-colors"
                >
                    {hasToken ? 'Command Center' : 'Sign in'}
                    <ArrowRight className="w-3.5 h-3.5" />
                </button>
            </nav>
            <motion.div
                style={{ scaleX: scrollYProgress }}
                className="h-[2px] w-full bg-gradient-to-r from-primary via-agent-active to-healthy origin-left"
            />
        </header>
    );
}
