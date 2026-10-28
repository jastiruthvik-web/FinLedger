"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { Component, useEffect, useRef, useState, type ReactNode } from "react";
import * as THREE from "three";
import { heroPointer } from "@/components/hero-pointer";

type Flow = {
  line: THREE.Line;
  packet: THREE.Line;
  positions: THREE.BufferAttribute;
  packetPositions: THREE.BufferAttribute;
  index: number;
};

type Tick = { line: THREE.Line; z: number; x: number; y: number };

const DARK = ["#9cf0de", "#e7d0aa", "#9eb6ff"];
const LIGHT = ["#0c6558", "#6e4a16", "#1d4e9a"];

function makeLine(color: string, count: number, opacity: number) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(count * 3), 3));
  const material = new THREE.LineBasicMaterial({
    color,
    transparent: true,
    opacity,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  return {
    line: new THREE.Line(geometry, material),
    positions: geometry.getAttribute("position") as THREE.BufferAttribute,
  };
}

function sample(index: number, along: number, time: number, px: number, py: number) {
  const yBase = (index - 7.5) * 0.4;
  const zBase = 1.6 - (index % 6) * 1.45;
  const phase = index * 0.57;
  const x = -9.4 + along * 18.8;
  const y =
    yBase +
    Math.sin(x * 0.4 + time * (0.26 + (index % 4) * 0.05) + phase) * (0.15 + (index % 3) * 0.045) +
    Math.sin(x * 0.14 - time * 0.16 + phase) * 0.07 +
    py * 0.2 * (0.3 + along);
  const z =
    zBase +
    (along - 0.42) * (1.7 + (index % 3) * 0.65) +
    Math.cos(along * 2.2 + time * 0.08 + phase) * 0.32 +
    px * (0.4 + along * 1.5);
  return { x, y, z };
}

function Field({ lines, ticks }: { lines: number; ticks: number }) {
  const group = useRef<THREE.Group>(null);
  const flows = useRef<Flow[]>([]);
  const marks = useRef<Tick[]>([]);
  const theme = useRef<"dark" | "light">("dark");
  const [epoch, setEpoch] = useState(0);

  useEffect(() => {
    const nextFlows = Array.from({ length: lines }, (_, index) => {
      const color = DARK[index % DARK.length];
      const main = makeLine(color, 84, index % 3 === 0 ? 0.88 : 0.46);
      const packet = makeLine(index % 2 === 0 ? "#f3dcc0" : color, 12, 1);
      return {
        line: main.line,
        packet: packet.line,
        positions: main.positions,
        packetPositions: packet.positions,
        index,
      };
    });
    const nextMarks = Array.from({ length: ticks }, (_, index) => {
      const built = makeLine(DARK[index % DARK.length], 2, 0.4);
      return {
        line: built.line,
        z: -11 + (index / Math.max(ticks, 1)) * 13,
        x: -6.5 + ((index * 1.65) % 13),
        y: -2 + (index % 8) * 0.52,
      };
    });
    flows.current = nextFlows;
    marks.current = nextMarks;
    setEpoch((value) => value + 1);
    return () => {
      nextFlows.forEach((flow) => {
        flow.line.geometry.dispose();
        flow.packet.geometry.dispose();
        (flow.line.material as THREE.Material).dispose();
        (flow.packet.material as THREE.Material).dispose();
      });
      nextMarks.forEach((mark) => {
        mark.line.geometry.dispose();
        (mark.line.material as THREE.Material).dispose();
      });
    };
  }, [lines, ticks]);

  useFrame((state) => {
    if (!flows.current.length) return;
    const time = state.clock.elapsedTime;
    const dark = document.documentElement.dataset.theme !== "light";
    const mode = dark ? "dark" : "light";
    if (theme.current !== mode) {
      theme.current = mode;
      const palette = dark ? DARK : LIGHT;
      const blending = dark ? THREE.AdditiveBlending : THREE.NormalBlending;
      const fog = state.scene.fog as THREE.Fog | null;
      if (fog) fog.color.set(dark ? 0x07080c : 0xefece4);
      flows.current.forEach((flow, index) => {
        const color = palette[index % palette.length];
        for (const line of [flow.line, flow.packet]) {
          const material = line.material as THREE.LineBasicMaterial;
          material.color.set(line === flow.packet && index % 2 === 0 ? (dark ? "#f3dcc0" : "#6e4a16") : color);
          material.blending = blending;
          material.needsUpdate = true;
        }
      });
      marks.current.forEach((mark, index) => {
        const material = mark.line.material as THREE.LineBasicMaterial;
        material.color.set(palette[index % palette.length]);
        material.blending = blending;
        material.needsUpdate = true;
      });
    }

    heroPointer.tx += (heroPointer.x - heroPointer.tx) * 0.055;
    heroPointer.ty += (heroPointer.y - heroPointer.ty) * 0.055;
    const px = heroPointer.tx;
    const py = heroPointer.ty;

    flows.current.forEach((flow) => {
      for (let i = 0; i < 84; i += 1) {
        const point = sample(flow.index, i / 83, time, px, py);
        flow.positions.setXYZ(i, point.x, point.y, point.z);
      }
      flow.positions.needsUpdate = true;
      const head = (time * (0.05 + flow.index * 0.0035) + flow.index * 0.09) % 1;
      for (let i = 0; i < 12; i += 1) {
        const along = (head - i * 0.01 + 1) % 1;
        const point = sample(flow.index, along, time, px, py);
        flow.packetPositions.setXYZ(i, point.x, point.y, point.z);
      }
      flow.packetPositions.needsUpdate = true;
    });

    marks.current.forEach((mark, index) => {
      mark.z += 0.012 * (0.6 + (index % 3) * 0.28);
      if (mark.z > 3.5) mark.z = -12;
      const position = mark.line.geometry.getAttribute("position") as THREE.BufferAttribute;
      const x = mark.x + px * 0.7;
      const y = mark.y + Math.sin(time * 0.22 + index) * 0.04;
      position.setXYZ(0, x, y - 0.12, mark.z);
      position.setXYZ(1, x, y + 0.12, mark.z);
      position.needsUpdate = true;
      const material = mark.line.material as THREE.LineBasicMaterial;
      material.opacity = THREE.MathUtils.clamp(0.55 - Math.abs(mark.z) / 16, 0.05, dark ? 0.45 : 0.6);
    });

    if (group.current) {
      group.current.rotation.y = time * 0.012 + px * 0.16;
      group.current.rotation.x = py * -0.08;
    }
    const camera = state.camera;
    camera.position.x += (0.15 + px * 0.55 - camera.position.x) * 0.045;
    camera.position.y += (0.05 + py * 0.3 - camera.position.y) * 0.045;
    camera.lookAt(0.7, 0, -1);
  });

  void epoch;
  return (
    <group ref={group} position={[0.85, -0.05, 0]}>
      {flows.current.flatMap((flow) => [
        <primitive key={`line-${flow.index}-${epoch}`} object={flow.line} />,
        <primitive key={`packet-${flow.index}-${epoch}`} object={flow.packet} />,
      ])}
      {marks.current.map((mark, index) => (
        <primitive key={`tick-${index}-${epoch}`} object={mark.line} />
      ))}
    </group>
  );
}

class SceneBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed) return <div className="hero-fallback" />;
    return this.props.children;
  }
}

export default function HeroScene({ variant = "hero" }: { variant?: "hero" | "ribbon" }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const ribbon = variant === "ribbon";
  const [alive, setAlive] = useState(true);

  useEffect(() => {
    const node = rootRef.current;
    if (!node) return;
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    let seen = true;
    let visible = document.visibilityState === "visible";
    const sync = () => setAlive(!query.matches && seen && visible);
    sync();
    const observer = new IntersectionObserver(([entry]) => {
      seen = entry.isIntersecting;
      sync();
    }, { threshold: 0.04 });
    observer.observe(node);
    const onVisibility = () => {
      visible = document.visibilityState === "visible";
      sync();
    };
    document.addEventListener("visibilitychange", onVisibility);
    query.addEventListener("change", sync);
    return () => {
      observer.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      query.removeEventListener("change", sync);
    };
  }, []);

  return (
    <div ref={rootRef} className={ribbon ? "ribbon-scene" : "hero-scene"} aria-hidden="true">
      <div className="hero-fallback" />
      <SceneBoundary>
        <Canvas
          dpr={[1, 1.35]}
          frameloop={alive ? "always" : "demand"}
          camera={{ position: [0.1, 0.04, ribbon ? 8.4 : 6.05], fov: ribbon ? 38 : 32, near: 0.1, far: 48 }}
          gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
          onCreated={({ gl, invalidate, scene }) => {
            gl.setClearColor(0x000000, 0);
            scene.fog = new THREE.Fog(0x07080c, 7, 20);
            invalidate();
          }}
        >
          <Field lines={ribbon ? 8 : 16} ticks={ribbon ? 0 : 18} />
        </Canvas>
      </SceneBoundary>
    </div>
  );
}
