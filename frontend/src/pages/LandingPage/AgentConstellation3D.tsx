import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Line, Html, Sparkles as DreiSparkles, Trail } from '@react-three/drei';
import * as THREE from 'three';

const AGENT_LABELS = ['Watcher', 'RCA', 'Impact', 'Runbook', 'Safety', 'Verifier'];
const AGENT_COLORS = ['#38BDF8', '#818CF8', '#E879F9', '#FBBF24', '#FB7185', '#34D399'];

function computeNodePositions(count: number, radius: number): THREE.Vector3[] {
    const positions: THREE.Vector3[] = [];
    for (let i = 0; i < count; i++) {
        const phi = Math.acos(1 - (2 * (i + 0.5)) / count);
        const theta = Math.PI * (1 + Math.sqrt(5)) * i;
        const x = radius * Math.sin(phi) * Math.cos(theta);
        const y = radius * Math.sin(phi) * Math.sin(theta);
        const z = radius * Math.cos(phi);
        positions.push(new THREE.Vector3(x, y, z));
    }
    return positions;
}

/**
 * A faceted "tech crystal" node (icosahedron, flat-shaded) with an orbiting ring
 * and a soft glow shell — deliberately not a plain smooth sphere, so each agent
 * reads as a distinct engineered object rather than a generic dot.
 */
function Node({ position, color, label, delay }: { position: THREE.Vector3; color: string; label: string; delay: number }) {
    const coreRef = useRef<THREE.Mesh>(null);
    const ringRef = useRef<THREE.Mesh>(null);
    const glowRef = useRef<THREE.Mesh>(null);

    useFrame(({ clock }, delta) => {
        const t = clock.getElapsedTime() + delay;
        if (coreRef.current) {
            const scale = 1 + Math.sin(t * 1.4) * 0.1;
            coreRef.current.scale.setScalar(scale);
            coreRef.current.rotation.x += delta * 0.4;
            coreRef.current.rotation.y += delta * 0.6;
        }
        if (glowRef.current) {
            const glowScale = 2.1 + Math.sin(t * 1.4) * 0.3;
            glowRef.current.scale.setScalar(glowScale);
        }
        if (ringRef.current) {
            ringRef.current.rotation.z += delta * 0.8;
            ringRef.current.rotation.x = Math.PI / 2.4 + Math.sin(t * 0.6) * 0.15;
        }
    });

    return (
        <group position={position}>
            {/* Soft glow shell */}
            <mesh ref={glowRef}>
                <sphereGeometry args={[0.18, 16, 16]} />
                <meshBasicMaterial color={color} transparent opacity={0.18} depthWrite={false} />
            </mesh>

            {/* Faceted crystal core */}
            <mesh ref={coreRef}>
                <icosahedronGeometry args={[0.24, 0]} />
                <meshStandardMaterial
                    color={color}
                    emissive={color}
                    emissiveIntensity={1.4}
                    flatShading
                    roughness={0.35}
                    metalness={0.4}
                />
            </mesh>

            {/* Orbiting accent ring */}
            <mesh ref={ringRef}>
                <torusGeometry args={[0.34, 0.012, 8, 48]} />
                <meshBasicMaterial color={color} transparent opacity={0.7} />
            </mesh>

            <pointLight color={color} intensity={0.7} distance={2.6} />

            <Html distanceFactor={10} position={[0, 0.42, 0]} center>
                <div
                    style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        color: 'rgba(255,255,255,0.75)',
                        whiteSpace: 'nowrap',
                        letterSpacing: '0.04em',
                        textTransform: 'uppercase',
                        textShadow: '0 0 8px rgba(0,0,0,0.8)',
                        pointerEvents: 'none',
                    }}
                >
                    {label}
                </div>
            </Html>
        </group>
    );
}

/** A small glowing packet that travels back and forth along an edge, evoking data/handoffs between agents. */
function PulseAlongEdge({ a, b, color, speed, offset }: { a: THREE.Vector3; b: THREE.Vector3; color: string; speed: number; offset: number }) {
    const ref = useRef<THREE.Mesh>(null);

    useFrame(({ clock }) => {
        if (!ref.current) return;
        const t = (Math.sin(clock.getElapsedTime() * speed + offset) + 1) / 2; // 0..1 ping-pong
        ref.current.position.lerpVectors(a, b, t);
    });

    return (
        <Trail width={3.5} length={6} color={color} attenuation={(t) => t * t}>
            <mesh ref={ref}>
                <sphereGeometry args={[0.05, 8, 8]} />
                <meshBasicMaterial color={color} />
            </mesh>
        </Trail>
    );
}

/** Faceted, slowly-rotating central "Commander" core — an icosahedron inside a wireframe shell. */
function CommanderCore() {
    const coreRef = useRef<THREE.Mesh>(null);
    const wireRef = useRef<THREE.Mesh>(null);

    useFrame((_, delta) => {
        if (coreRef.current) {
            coreRef.current.rotation.y += delta * 0.3;
            coreRef.current.rotation.x += delta * 0.15;
        }
        if (wireRef.current) {
            wireRef.current.rotation.y -= delta * 0.12;
            wireRef.current.rotation.z += delta * 0.08;
        }
    });

    return (
        <group>
            <mesh ref={coreRef}>
                <icosahedronGeometry args={[0.32, 1]} />
                <meshStandardMaterial color="#FFFFFF" emissive="#C7D2FE" emissiveIntensity={1.6} flatShading roughness={0.15} metalness={0.5} />
            </mesh>
            <mesh ref={wireRef}>
                <icosahedronGeometry args={[0.55, 1]} />
                <meshBasicMaterial color="#C7D2FE" wireframe transparent opacity={0.35} />
            </mesh>
            <mesh>
                <sphereGeometry args={[0.85, 24, 24]} />
                <meshBasicMaterial color="#C7D2FE" transparent opacity={0.08} depthWrite={false} />
            </mesh>
            <pointLight color="#C7D2FE" intensity={1.6} distance={4.2} />
        </group>
    );
}

export function AgentConstellation3D({ reduceMotion }: { reduceMotion: boolean }) {
    const groupRef = useRef<THREE.Group>(null);
    const innerRef = useRef<THREE.Group>(null);
    const positions = useMemo(() => computeNodePositions(AGENT_LABELS.length, 3.4), []);

    const edges = useMemo(() => {
        const lines: { a: THREE.Vector3; b: THREE.Vector3; ai: number; bi: number }[] = [];
        for (let i = 0; i < positions.length; i++) {
            for (let j = i + 1; j < positions.length; j++) {
                if (Math.random() > 0.35) lines.push({ a: positions[i], b: positions[j], ai: i, bi: j });
            }
        }
        return lines;
    }, [positions]);

    // A handful of edges get an animated "data pulse" traveling along them.
    const pulseEdges = useMemo(() => edges.slice(0, Math.min(6, edges.length)), [edges]);

    useFrame((_, delta) => {
        if (groupRef.current && !reduceMotion) {
            groupRef.current.rotation.y += delta * 0.14;
        }
        if (innerRef.current && !reduceMotion) {
            innerRef.current.rotation.x = Math.sin(Date.now() * 0.00007) * 0.25;
            innerRef.current.rotation.z = Math.cos(Date.now() * 0.00005) * 0.1;
        }
    });

    return (
        <group ref={groupRef}>
            <ambientLight intensity={0.35} />
            <pointLight position={[6, 6, 6]} intensity={2.4} color="#818CF8" />
            <pointLight position={[-6, -4, -6]} intensity={2} color="#E879F9" />
            <pointLight position={[0, 0, 6]} intensity={1} color="#38BDF8" />

            {/* Ambient particle field for depth and "aliveness" */}
            <DreiSparkles count={160} scale={13} size={3.2} speed={0.3} color="#C7D2FE" opacity={0.7} />
            <DreiSparkles count={70} scale={9} size={2.4} speed={0.18} color="#F0ABFC" opacity={0.5} />
            <DreiSparkles count={30} scale={5} size={2} speed={0.4} color="#67E8F9" opacity={0.6} />

            <group ref={innerRef}>
                {edges.map(({ a, b }, idx) => (
                    <Line key={idx} points={[a, b]} color="#818CF8" transparent opacity={0.35} lineWidth={1.5} />
                ))}

                {!reduceMotion &&
                    pulseEdges.map(({ a, b, ai }, idx) => (
                        <PulseAlongEdge
                            key={idx}
                            a={a}
                            b={b}
                            color={AGENT_COLORS[ai % AGENT_COLORS.length]}
                            speed={0.4 + idx * 0.08}
                            offset={idx * 1.3}
                        />
                    ))}

                {positions.map((pos, idx) => (
                    <Node key={idx} position={pos} color={AGENT_COLORS[idx]} label={AGENT_LABELS[idx]} delay={idx * 0.4} />
                ))}

                <CommanderCore />
            </group>
        </group>
    );
}
