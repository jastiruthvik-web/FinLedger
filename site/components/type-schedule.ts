export type TypeSegmentId = "mark" | "sign" | "voucher" | "guess";

type Phrase = {
  id: TypeSegmentId;
  text: string;
  /** Quiet beat after the phrase, before the next one starts. */
  pauseAfter: number;
};

/** FinLedger, then "Sign the voucher." (two designed lines), then "Not the guess." */
const PHRASES: Phrase[] = [
  { id: "mark", text: "FinLedger", pauseAfter: 380 },
  { id: "sign", text: "Sign the", pauseAfter: 160 },
  { id: "voucher", text: "voucher.", pauseAfter: 400 },
  { id: "guess", text: "Not the guess.", pauseAfter: 0 },
];

const CHAR_MIN = 40;
const CHAR_MAX = 70;
const LEAD_MS = 48;
const END_CARET_MS = 240;

/** Steady hand with a slight swell. Stays inside 40–70ms per character. */
export function charGap(char: string, index: number) {
  const wave = 54 + Math.sin(index * 1.35) * 12;
  let gap = wave;
  if (char === " ") gap += 8;
  if (char === "." || char === ",") gap += 10;
  return Math.round(Math.min(CHAR_MAX, Math.max(CHAR_MIN, gap)));
}

export type TypeScheduleEntry = {
  id: TypeSegmentId;
  text: string;
  at: number[];
  caretUntil: number;
};

function buildSchedule() {
  let t = LEAD_MS;
  let globalIndex = 0;
  const entries = {} as Record<TypeSegmentId, TypeScheduleEntry>;
  for (const phrase of PHRASES) {
    const at: number[] = [];
    for (let i = 0; i < phrase.text.length; i++) {
      at.push(Math.round(t));
      t += charGap(phrase.text[i]!, globalIndex);
      globalIndex += 1;
    }
    const nextStart = t + phrase.pauseAfter;
    const caretUntil = phrase.pauseAfter > 0 ? nextStart : t + END_CARET_MS;
    entries[phrase.id] = {
      id: phrase.id,
      text: phrase.text,
      at,
      caretUntil: Math.round(caretUntil),
    };
    t = nextStart;
  }
  return entries;
}

export const TYPE_SCHEDULE = buildSchedule();

export const TYPE_HORIZON_MS = Math.max(...Object.values(TYPE_SCHEDULE).map((entry) => entry.caretUntil)) + 32;

export function typeSegment(id: TypeSegmentId) {
  return TYPE_SCHEDULE[id];
}

export function visibleCount(at: readonly number[], elapsed: number) {
  let count = 0;
  for (const time of at) {
    if (time <= elapsed) count += 1;
    else break;
  }
  return count;
}

type ClockListener = (elapsed: number) => void;

const listeners = new Set<ClockListener>();
const EVENTS = (() => {
  const times = new Set<number>([0]);
  for (const entry of Object.values(TYPE_SCHEDULE)) {
    for (const at of entry.at) times.add(at);
    times.add(entry.caretUntil);
  }
  return [...times].sort((a, b) => a - b);
})();

let cursor = 0;
let timer = 0;
let running = false;

function emit() {
  const presented = EVENTS[cursor] ?? 0;
  listeners.forEach((listener) => listener(presented));
}

function tick() {
  timer = 0;
  if (cursor < EVENTS.length - 1) cursor += 1;
  emit();
  queueNext();
}

function queueNext() {
  if (!running || listeners.size === 0 || cursor >= EVENTS.length - 1) return;
  const gap = Math.max(16, EVENTS[cursor + 1]! - EVENTS[cursor]!);
  timer = window.setTimeout(tick, gap);
}

function stopClock() {
  if (timer) window.clearTimeout(timer);
  timer = 0;
  running = false;
  cursor = 0;
}

/**
 * One shared sequence for the wordmark and the headline.
 * Each tick reveals a single character, even if the previous gap ran late.
 */
export function subscribeTypeClock(listener: ClockListener) {
  listeners.add(listener);
  if (!running) {
    running = true;
    cursor = 0;
    emit();
    queueNext();
  } else listener(EVENTS[cursor] ?? 0);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) stopClock();
  };
}
