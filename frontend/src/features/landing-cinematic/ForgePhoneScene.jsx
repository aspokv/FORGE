import { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { RoundedBox, useTexture } from "@react-three/drei";
import * as THREE from "three";

import { PHONE_SCREENS, chapterFromProgress } from "./sceneConfig";

const clamp = (n, min = 0, max = 1) => Math.max(min, Math.min(max, n));
const range = (n, from, to) => clamp((n - from) / (to - from));

function Phone({ progressRef, profile }) {
  const phone = useRef(null);
  const glass = useRef(null);
  const display = useRef(null);
  const drag = useRef({ active: false, x: 0, rotation: 0 });
  const textures = useTexture(PHONE_SCREENS);

  useEffect(() => {
    textures.forEach((texture) => {
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.anisotropy = 4;
      texture.needsUpdate = true;
    });
  }, [textures]);

  const material = useMemo(
    () => ({
      obsidian: new THREE.MeshPhysicalMaterial({
        color: "#090909",
        metalness: 0.92,
        roughness: 0.2,
        clearcoat: 1,
        clearcoatRoughness: 0.15,
      }),
      copper: new THREE.MeshPhysicalMaterial({
        color: profile === "feminino" ? "#d79b70" : "#b86e3b",
        metalness: 0.88,
        roughness: 0.24,
      }),
    }),
    [profile]
  );

  useEffect(() => () => Object.values(material).forEach((m) => m.dispose()), [material]);

  useFrame((state, delta) => {
    const p = progressRef.current;
    const chapter = chapterFromProgress(p);
    const screenIndex = chapter === 0 && profile === "masculino" ? 1 : chapter;
    const exploded = Math.sin(range(p, 0.49, 0.71) * Math.PI);
    const targetY = p < 0.22 ? -0.14 : p < 0.72 ? 0.03 : -0.08;
    const targetX = state.size.width < 700 ? 0 : p < 0.23 ? 1.55 : p < 0.7 ? -1.45 : 1.35;
    // A camera nunca deixa o produto de perfil justamente quando uma tela precisa ser
    // lida. O giro muda de direcao entre capitulos e mostra espessura sem esconder UI.
    const cinematicRotation = p < 0.23
      ? -0.22 + range(p, 0, 0.23) * 0.42
      : p < 0.46
        ? 0.2 - range(p, 0.23, 0.46) * 0.38
        : p < 0.7
          ? -0.18 + range(p, 0.46, 0.7) * 0.68
          : 0.5 - range(p, 0.7, 1) * 0.62;
    const targetRotation = cinematicRotation + drag.current.rotation;

    phone.current.position.x = THREE.MathUtils.damp(phone.current.position.x, targetX, 4.5, delta);
    phone.current.position.y = THREE.MathUtils.damp(phone.current.position.y, targetY, 4.5, delta);
    phone.current.rotation.y = THREE.MathUtils.damp(phone.current.rotation.y, targetRotation, 4.2, delta);
    phone.current.rotation.x = THREE.MathUtils.damp(phone.current.rotation.x, -0.07 + p * 0.09, 4, delta);
    phone.current.scale.setScalar(THREE.MathUtils.damp(phone.current.scale.x, p > 0.88 ? 0.9 : 1, 4, delta));

    glass.current.position.z = 0.245 + exploded * 0.72;
    display.current.position.z = 0.258 + exploded * 1.42;
    if (display.current.material.map !== textures[screenIndex]) {
      display.current.material.map = textures[screenIndex];
      display.current.material.needsUpdate = true;
    }
  });

  const pointerDown = (event) => {
    event.stopPropagation();
    drag.current.active = true;
    drag.current.x = event.clientX;
    event.target.setPointerCapture?.(event.pointerId);
  };
  const pointerMove = (event) => {
    if (!drag.current.active) return;
    const dx = event.clientX - drag.current.x;
    drag.current.x = event.clientX;
    drag.current.rotation += dx * 0.006;
  };
  const pointerUp = () => {
    drag.current.active = false;
  };

  return (
    <group
      ref={phone}
      onPointerDown={pointerDown}
      onPointerMove={pointerMove}
      onPointerUp={pointerUp}
      onPointerCancel={pointerUp}
    >
      <RoundedBox args={[3.18, 6.72, 0.34]} radius={0.28} smoothness={6} material={material.obsidian} />
      <RoundedBox args={[3.08, 6.62, 0.13]} radius={0.24} smoothness={5} position={[0, 0, 0.16]} material={material.copper} />
      <mesh ref={glass} position={[0, 0, 0.245]}>
        <planeGeometry args={[2.94, 6.39]} />
        <meshPhysicalMaterial color="#090909" roughness={0.07} transmission={0.08} transparent opacity={0.96} />
      </mesh>
      <mesh ref={display} position={[0, 0, 0.258]}>
        <planeGeometry args={[2.88, 6.25]} />
        <meshBasicMaterial map={textures[0]} toneMapped={false} />
      </mesh>
      <RoundedBox args={[0.9, 0.2, 0.08]} radius={0.09} smoothness={4} position={[0, 2.92, 0.31]} material={material.obsidian} />
      <mesh position={[-1.62, 1.5, 0]} material={material.copper}><boxGeometry args={[0.055, 0.65, 0.12]} /></mesh>
      <mesh position={[1.62, 1.1, 0]} material={material.copper}><boxGeometry args={[0.055, 0.92, 0.12]} /></mesh>
    </group>
  );
}

function Lighting() {
  return (
    <>
      <ambientLight intensity={0.35} />
      <spotLight position={[-7, 8, 8]} intensity={22} angle={0.35} penumbra={1} color="#e5a66f" />
      <spotLight position={[8, 2, 5]} intensity={14} angle={0.45} penumbra={1} color="#fff1df" />
      <pointLight position={[0, -5, 4]} intensity={5} color="#a95727" />
    </>
  );
}

export default function ForgePhoneScene({ progressRef, profile, onReady }) {
  return (
    <Canvas
      camera={{ position: [0, 0, 10.3], fov: 39 }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      onCreated={({ gl }) => {
        gl.outputColorSpace = THREE.SRGBColorSpace;
        onReady?.();
      }}
    >
      <Lighting />
      <Phone progressRef={progressRef} profile={profile} />
    </Canvas>
  );
}
