"use client";

/**
 * Custom fullscreen shader. React Three Fiber is intentionally not used:
 * one quad keeps the hero off the Three.js bundle.
 */

import { useEffect, useRef, useState } from "react";
import { heroPointer } from "@/components/hero-pointer";

const VERT = `
attribute vec2 a;
void main() {
  gl_Position = vec4(a, 0.0, 1.0);
}
`;

const FRAG = `
precision mediump float;
uniform vec2 u_res;
uniform float u_time;
uniform vec2 u_mouse;
uniform float u_theme;
uniform float u_gain;

float hair(float coord, float gap) {
  float dist = abs(fract(coord / gap) - 0.5) * gap;
  return 1.0 - smoothstep(0.45, 1.35, dist);
}

float filament(vec2 uv, float base, float freq, float speed, float phase, float amp) {
  float y = base + amp * sin(uv.x * freq + u_time * speed + phase);
  float pull = exp(-abs(uv.x - u_mouse.x) * 2.2) * (u_mouse.y - y) * 0.22;
  y += pull;
  float d = abs(uv.y - y);
  return exp(-d * d * 14000.0) + exp(-d * 90.0) * 0.28;
}

float filamentSoft(vec2 uv, float base, float freq, float speed, float phase, float amp) {
  float y = base + amp * sin(uv.x * freq + u_time * speed + phase);
  float pull = exp(-abs(uv.x - u_mouse.x) * 1.25) * (u_mouse.y - y) * 0.065;
  y += pull;
  float d = abs(uv.y - y);
  return exp(-d * d * 1800.0) + exp(-d * 18.0) * 0.7;
}

void main() {
  vec2 uv = gl_FragCoord.xy / u_res.xy;
  float aspect = u_res.x / max(u_res.y, 1.0);
  vec3 sky = vec3(0.494, 0.714, 1.0);       /* #7eb6ff */
  vec3 royal = vec3(0.298, 0.553, 1.0);     /* #4c8dff */
  vec3 violet = vec3(0.318, 0.337, 0.902);  /* #5156e6 */
  vec3 navy = vec3(0.008, 0.039, 0.118);    /* #020a1e */

  if (u_theme > 0.5) {
    float t = u_time;
    vec2 p = vec2(uv.x * aspect, uv.y);
    vec3 top = vec3(0.930, 0.962, 1.0);
    vec3 mid = vec3(0.816, 0.902, 0.988);
    vec3 low = vec3(0.690, 0.824, 0.973);
    vec2 c1 = vec2(0.22 * aspect + 0.18 * sin(t * 0.042), 0.74 + 0.08 * cos(t * 0.034));
    vec2 c2 = vec2(0.86 * aspect + 0.14 * cos(t * 0.028 + 0.7), 0.32 + 0.10 * sin(t * 0.025));
    vec2 c3 = vec2(0.52 * aspect + 0.12 * sin(t * 0.022 + 1.6), 0.56 + 0.07 * cos(t * 0.031));
    vec2 c4 = vec2(0.08 * aspect + 0.09 * cos(t * 0.019), 0.16 + 0.06 * sin(t * 0.024));
    float b1 = exp(-dot(p - c1, p - c1) * 0.85);
    float b2 = exp(-dot(p - c2, p - c2) * 0.62);
    float b3 = exp(-dot(p - c3, p - c3) * 1.05);
    float b4 = exp(-dot(p - c4, p - c4) * 0.7);
    float f1 = filamentSoft(uv, 0.28, 1.45, 0.030, 0.3, 0.058);
    float f2 = filamentSoft(uv, 0.46, 1.9, 0.022, 1.6, 0.050);
    float f3 = filamentSoft(uv, 0.64, 1.2, 0.036, 2.3, 0.042);
    float f4 = filamentSoft(uv, 0.82, 1.65, 0.018, 0.8, 0.036);
    vec2 delta = vec2((uv.x - u_mouse.x) * aspect, uv.y - u_mouse.y);
    float lamp = exp(-dot(delta, delta) * 1.65);
    float vignette = smoothstep(1.4, 0.15, length((uv - vec2(0.5)) * vec2(aspect, 1.0)));
    vec3 color = mix(low, top, smoothstep(0.0, 0.95, uv.y));
    color = mix(color, sky, b1 * 0.46);
    color = mix(color, royal, b2 * 0.36);
    color = mix(color, violet, b3 * 0.18);
    color = mix(color, mix(sky, mid, 0.35), b4 * 0.24);
    color = mix(color, sky, clamp(f1, 0.0, 1.0) * 0.62 * u_gain);
    color = mix(color, royal, clamp(f2, 0.0, 1.0) * 0.5 * u_gain);
    color = mix(color, mix(sky, royal, 0.35), clamp(f3, 0.0, 1.0) * 0.4 * u_gain);
    color = mix(color, violet, clamp(f4, 0.0, 1.0) * 0.3 * u_gain);
    color = mix(color, sky, lamp * 0.16 * u_gain);
    color = mix(mix(top, low, 0.45), color, mix(0.78, 1.0, vignette));
    gl_FragColor = vec4(clamp(color, 0.0, 1.0), 1.0);
  } else {
    vec3 bg = mix(navy, vec3(0.027, 0.071, 0.165), smoothstep(0.0, 1.0, uv.y) * 0.65);
    float rules = hair(gl_FragCoord.y + u_time * 1.6, 28.0);
    float major = hair(gl_FragCoord.y + u_time * 1.6, 140.0);
    float columns = hair(gl_FragCoord.x, 168.0);
    float flow = 0.0;
    vec2 delta = vec2((uv.x - u_mouse.x) * aspect, uv.y - u_mouse.y);
    float lamp = exp(-dot(delta, delta) * 3.4);
    float vignette = smoothstep(1.2, 0.25, length((uv - vec2(0.5)) * vec2(aspect, 1.0)));
    vec3 color = bg;
    flow += filament(uv, 0.30, 2.2, 0.18, 0.4, 0.040);
    flow += filament(uv, 0.48, 3.0, 0.13, 1.8, 0.046);
    flow += filament(uv, 0.66, 1.7, 0.22, 2.5, 0.034);
    flow += filament(uv, 0.80, 2.6, 0.11, 0.6, 0.030);
    color += royal * (rules * 0.05 + major * 0.045);
    color += violet * columns * 0.038;
    color += mix(sky, violet, 0.42) * flow * 0.88 * u_gain;
    color += mix(sky, royal, 0.3) * lamp * 0.18 * u_gain;
    color = mix(navy, color, mix(0.55, 1.0, vignette));
    gl_FragColor = vec4(color, 1.0);
  }
}
`;

function compile(gl: WebGLRenderingContext, type: number, source: string) {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

export default function HeroScene({ variant = "hero" }: { variant?: "hero" | "ribbon" }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [failed, setFailed] = useState(false);
  const ribbon = variant === "ribbon";

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let dead = false;
    const gl = canvas.getContext("webgl", {
      alpha: true,
      antialias: false,
      depth: false,
      stencil: false,
      powerPreference: "low-power",
    });
    if (!gl) {
      setFailed(true);
      return;
    }
    const vertex = compile(gl, gl.VERTEX_SHADER, VERT);
    const fragment = compile(gl, gl.FRAGMENT_SHADER, FRAG);
    if (!vertex || !fragment) {
      setFailed(true);
      return;
    }
    const program = gl.createProgram();
    if (!program) {
      setFailed(true);
      return;
    }
    gl.attachShader(program, vertex);
    gl.attachShader(program, fragment);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      setFailed(true);
      return;
    }
    gl.useProgram(program);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
    const attribute = gl.getAttribLocation(program, "a");
    gl.enableVertexAttribArray(attribute);
    gl.vertexAttribPointer(attribute, 2, gl.FLOAT, false, 0, 0);

    const uRes = gl.getUniformLocation(program, "u_res");
    const uTime = gl.getUniformLocation(program, "u_time");
    const uMouse = gl.getUniformLocation(program, "u_mouse");
    const uTheme = gl.getUniformLocation(program, "u_theme");
    const uGain = gl.getUniformLocation(program, "u_gain");
    const pointer = { x: 0.68, y: 0.42, tx: 0.68, ty: 0.42 };
    let raf = 0;
    let last = 0;
    let seen = true;
    let visible = document.visibilityState === "visible";
    const reduceQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    let reduce = reduceQuery.matches;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      const width = Math.max(1, Math.floor(rect.width * dpr));
      const height = Math.max(1, Math.floor(rect.height * dpr));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      gl.viewport(0, 0, canvas.width, canvas.height);
    };

    const draw = (time: number) => {
      resize();
      if (!ribbon) {
        pointer.tx = 0.66 + heroPointer.tx * 0.22;
        pointer.ty = 0.46 + heroPointer.ty * 0.18;
      }
      pointer.x += (pointer.tx - pointer.x) * 0.16;
      pointer.y += (pointer.ty - pointer.y) * 0.16;
      gl.uniform2f(uRes, canvas.width, canvas.height);
      gl.uniform1f(uTime, time);
      gl.uniform2f(uMouse, pointer.x, 1 - pointer.y);
      gl.uniform1f(uTheme, document.documentElement.dataset.theme === "light" ? 1 : 0);
      gl.uniform1f(uGain, ribbon ? 0.72 : 1);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      canvas.dataset.ready = "1";
    };

    const stop = () => {
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
    };
    const loop = (now: number) => {
      if (dead || reduce || !seen || !visible) {
        raf = 0;
        return;
      }
      raf = requestAnimationFrame(loop);
      if (now - last < 33) return;
      last = now;
      heroPointer.tx += (heroPointer.x - heroPointer.tx) * 0.08;
      heroPointer.ty += (heroPointer.y - heroPointer.ty) * 0.08;
      draw((now % 100000) / 1000);
    };
    const start = () => {
      if (raf || reduce) return;
      last = 0;
      raf = requestAnimationFrame(loop);
    };
    const sync = () => {
      reduce = reduceQuery.matches;
      if (reduce || !seen || !visible) {
        stop();
        draw(4.2);
      } else start();
    };

    draw(4.2);
    sync();

    const host = ribbon ? canvas.parentElement?.parentElement : canvas.parentElement?.parentElement;
    const onPointer = (event: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      pointer.tx = (event.clientX - rect.left) / Math.max(rect.width, 1);
      pointer.ty = (event.clientY - rect.top) / Math.max(rect.height, 1);
    };
    if (ribbon) host?.addEventListener("pointermove", onPointer, { passive: true });

    const observer = new IntersectionObserver(
      ([entry]) => {
        seen = entry.isIntersecting;
        sync();
      },
      { threshold: 0.02 },
    );
    observer.observe(canvas.parentElement ?? canvas);
    const onVisibility = () => {
      visible = document.visibilityState === "visible";
      sync();
    };
    document.addEventListener("visibilitychange", onVisibility);
    reduceQuery.addEventListener("change", sync);
    window.addEventListener("resize", sync);
    const themeObserver = new MutationObserver(() => draw(reduce ? 4.2 : (performance.now() % 100000) / 1000));
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const onLost = (event: Event) => {
      event.preventDefault();
      stop();
      if (!dead) setFailed(true);
    };
    canvas.addEventListener("webglcontextlost", onLost);

    return () => {
      dead = true;
      stop();
      observer.disconnect();
      themeObserver.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      reduceQuery.removeEventListener("change", sync);
      window.removeEventListener("resize", sync);
      host?.removeEventListener("pointermove", onPointer);
      canvas.removeEventListener("webglcontextlost", onLost);
      gl.deleteProgram(program);
      gl.deleteShader(vertex);
      gl.deleteShader(fragment);
      gl.deleteBuffer(buffer);
    };
  }, [ribbon]);

  return (
    <div className={ribbon ? "ribbon-scene" : "hero-scene"} aria-hidden="true">
      <div className="hero-fallback" />
      {failed ? null : <canvas ref={canvasRef} />}
    </div>
  );
}
