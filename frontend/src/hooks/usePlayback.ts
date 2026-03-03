"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Trajectories, PlaybackSpeed } from "@/types/simulation";

const PLAYBACK_FPS = 10; // simulation Hz
const BASE_INTERVAL = 1000 / PLAYBACK_FPS; // 100ms per frame at 1x

interface UsePlaybackOptions {
  trajectories: Trajectories | null;
}

interface UsePlaybackReturn {
  isPlaying: boolean;
  currentFrame: number;
  totalFrames: number;
  speed: PlaybackSpeed;
  frameRef: React.MutableRefObject<number>;
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  reset: () => void;
  setSpeed: (speed: PlaybackSpeed) => void;
  cycleSpeed: () => void;
  scrubTo: (frame: number) => void;
  setPlaying: (playing: boolean) => void;
}

export function usePlayback({
  trajectories,
}: UsePlaybackOptions): UsePlaybackReturn {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [speed, setSpeed] = useState<PlaybackSpeed>(1);
  const frameRef = useRef(0);
  const lastTimestampRef = useRef<number | null>(null);
  const accumulatorRef = useRef(0);
  const rafIdRef = useRef(0);

  const totalFrames = useMemo(
    () => (trajectories ? Object.keys(trajectories).length : 0),
    [trajectories],
  );

  // rAF-based playback loop with time accumulator
  useEffect(() => {
    if (!isPlaying || !trajectories || totalFrames === 0) {
      lastTimestampRef.current = null;
      return;
    }

    const tick = (timestamp: number) => {
      if (lastTimestampRef.current === null) {
        lastTimestampRef.current = timestamp;
      }

      // Clamp elapsed to 200ms to handle tab backgrounding
      const elapsed = Math.min(timestamp - lastTimestampRef.current, 200);
      lastTimestampRef.current = timestamp;

      accumulatorRef.current += elapsed;
      const frameInterval = BASE_INTERVAL / speed;

      while (accumulatorRef.current >= frameInterval) {
        accumulatorRef.current -= frameInterval;
        frameRef.current += 1;
        if (frameRef.current >= totalFrames) {
          frameRef.current = 0;
        }
      }

      setCurrentFrame(frameRef.current);
      rafIdRef.current = requestAnimationFrame(tick);
    };

    rafIdRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafIdRef.current);
  }, [isPlaying, trajectories, totalFrames, speed]);

  const play = useCallback(() => setIsPlaying(true), []);

  const pause = useCallback(() => {
    setIsPlaying(false);
    lastTimestampRef.current = null;
    accumulatorRef.current = 0;
  }, []);

  const togglePlay = useCallback(() => setIsPlaying((p) => !p), []);

  const reset = useCallback(() => {
    setIsPlaying(false);
    frameRef.current = 0;
    setCurrentFrame(0);
    lastTimestampRef.current = null;
    accumulatorRef.current = 0;
  }, []);

  const scrubTo = useCallback((f: number) => {
    frameRef.current = f;
    setCurrentFrame(f);
  }, []);

  const cycleSpeed = useCallback(() => {
    setSpeed((prev) => (prev === 1 ? 2 : prev === 2 ? 4 : 1));
  }, []);

  return {
    isPlaying,
    currentFrame,
    totalFrames,
    speed,
    frameRef,
    play,
    pause,
    togglePlay,
    reset,
    setSpeed,
    cycleSpeed,
    scrubTo,
    setPlaying: setIsPlaying,
  };
}
