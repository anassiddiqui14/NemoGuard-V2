import { useEffect, useRef, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { AgentConstellation3D } from './AgentConstellation3D';

/** Subtly drifts the camera based on pointer position for a parallax "presence" effect. */
function CameraRig({ reduceMotion }: { reduceMotion: boolean }) {
    const { camera } = useThree();
    const target = useRef({ x: 0, y: 0 });

    useEffect(() => {
        if (reduceMotion) return;
        const handler = (e: PointerEvent) => {
            target.current.x = (e.clientX / window.innerWidth - 0.5) * 2;
            target.current.y = (e.clientY / window.innerHeight - 0.5) * 2;
        };
        window.addEventListener('pointermove', handler);
        return () => window.removeEventListener('pointermove', handler);
    }, [reduceMotion]);

    useFrame(() => {
        if (reduceMotion) return;
        camera.position.x += (target.current.x * 0.8 - camera.position.x) * 0.03;
        camera.position.y += (-target.current.y * 0.5 - camera.position.y) * 0.03;
        camera.lookAt(0, 0, 0);
    });

    return null;
}

export function HeroScene() {
    const containerRef = useRef<HTMLDivElement>(null);
    const [inView, setInView] = useState(true);
    const [reduceMotion, setReduceMotion] = useState(false);

    useEffect(() => {
        const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
        setReduceMotion(mq.matches);
        const handler = () => setReduceMotion(mq.matches);
        mq.addEventListener?.('change', handler);
        return () => mq.removeEventListener?.('change', handler);
    }, []);

    useEffect(() => {
        if (!containerRef.current) return;
        const observer = new IntersectionObserver(
            ([entry]) => setInView(entry.isIntersecting),
            { threshold: 0.1 },
        );
        observer.observe(containerRef.current);
        return () => observer.disconnect();
    }, []);

    return (
        <div ref={containerRef} className="absolute inset-0">
            <Canvas
                dpr={[1, Math.min(window.devicePixelRatio || 1, 2)]}
                camera={{ position: [0, 0, 7], fov: 50 }}
                frameloop={inView ? 'always' : 'never'}
                gl={{ antialias: true, alpha: true }}
            >
                <CameraRig reduceMotion={reduceMotion} />
                <AgentConstellation3D reduceMotion={reduceMotion} />
            </Canvas>
        </div>
    );
}
