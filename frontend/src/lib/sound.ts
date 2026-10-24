import { useCallback, useState } from 'react';

const STORAGE_KEY = 'numora:sound-muted';

let audioContext: AudioContext | null = null;

function readMutedPreference(): boolean {
  if (typeof window === 'undefined') return false;

  try {
    return window.localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

function getAudioContext(): AudioContext | null {
  if (typeof window === 'undefined') return null;

  try {
    if (!audioContext) {
      const AudioContextClass = window.AudioContext;
      if (!AudioContextClass) return null;
      audioContext = new AudioContextClass();
    }

    if (audioContext.state === 'suspended') {
      void audioContext.resume().catch(() => {});
    }

    return audioContext;
  } catch {
    return null;
  }
}

function playTone(
  frequency: number,
  duration: number,
  offset = 0,
  volume = 0.025,
  waveform: OscillatorType = 'sine',
  endFrequency?: number,
): void {
  if (readMutedPreference()) return;

  const context = getAudioContext();
  if (!context) return;

  try {
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    const start = context.currentTime + offset;
    const end = start + duration;

    oscillator.type = waveform;
    oscillator.frequency.setValueAtTime(frequency, start);

    if (endFrequency && endFrequency > 0) {
      oscillator.frequency.exponentialRampToValueAtTime(
        endFrequency,
        end,
      );
    }

    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(
      Math.max(0.0001, volume),
      start + 0.01,
    );
    gain.gain.exponentialRampToValueAtTime(0.0001, end);

    oscillator.connect(gain);
    gain.connect(context.destination);

    oscillator.start(start);
    oscillator.stop(end + 0.02);

    oscillator.onended = () => {
      oscillator.disconnect();
      gain.disconnect();
    };
  } catch {
    // Audio must never interrupt the application's normal functionality.
  }
}

export function playTap(): void {
  playTone(620, 0.045, 0, 0.018, 'sine');
}

export function playCoinJingle(): void {
  [880, 1174.66, 1396.91].forEach((frequency, index) => {
    playTone(frequency, 0.13, index * 0.065, 0.028, 'triangle');
  });
}

export function playRollStart(): void {
  playTone(150, 0.28, 0, 0.035, 'sine', 520);
  playTone(310, 0.16, 0.08, 0.012, 'triangle', 720);
}

export function playReelTick(step = 0): void {
  const frequency = 240 + (step % 8) * 28;
  playTone(frequency, 0.035, 0, 0.008, 'triangle');
}

export function playColumnLock(index: number, total: number): void {
  const frequency = 480 + Math.min(index, 10) * 38 + Math.min(total, 10) * 3;

  playTone(frequency, 0.11, 0, 0.025, 'triangle');
  playTone(frequency * 1.5, 0.08, 0.025, 0.009, 'sine');
}

export function playRevealFanfare(rarity: string): void {
  const normalized = rarity.toUpperCase();

  let notes = [440, 554.37, 659.25];

  if (normalized === 'RARE') {
    notes = [523.25, 659.25, 783.99];
  }

  if (normalized === 'EPIC') {
    notes = [523.25, 659.25, 783.99, 1046.5];
  }

  if (
    normalized === 'LEGENDARY' ||
    normalized === 'MYTHIC' ||
    normalized === 'SECRET'
  ) {
    notes = [523.25, 659.25, 783.99, 1046.5, 1318.51];
  }

  notes.forEach((frequency, index) => {
    playTone(
      frequency,
      0.19,
      index * 0.075,
      0.025,
      'triangle',
    );
  });
}

export function useSoundMuted(): [boolean, () => void] {
  const [muted, setMuted] = useState(readMutedPreference);

  const toggleMuted = useCallback(() => {
    setMuted((current) => {
      const next = !current;

      try {
        window.localStorage.setItem(STORAGE_KEY, next ? '1' : '0');
      } catch {
        // Keep the toggle functional even when storage is unavailable.
      }

      return next;
    });
  }, []);

  return [muted, toggleMuted];
}
