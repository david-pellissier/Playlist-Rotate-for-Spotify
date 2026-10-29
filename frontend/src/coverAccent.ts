import { type CSSProperties, useEffect, useState } from "react";

interface CoverAccent {
  hue: number;
  saturation: number;
}

const SAMPLE_SIZE = 32;
const HUE_BUCKETS = 24;
const MIN_CONTRAST = 4.5;
const LIGHT_SURFACE: Rgb = [1, 1, 1];
const DARK_SURFACE: Rgb = [0x12 / 255, 0x15 / 255, 0x1b / 255];

type Rgb = [number, number, number];

function toRgb(hue: number, saturation: number, lightness: number): Rgb {
  const k = (n: number) => (n + hue / 30) % 12;
  const a = saturation * Math.min(lightness, 1 - lightness);
  return [0, 8, 4].map((n) => lightness - a * Math.max(-1, Math.min(k(n) - 3, 9 - k(n), 1))) as Rgb;
}

function luminance(rgb: Rgb): number {
  const [r, g, b] = rgb.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(first: Rgb, second: Rgb): number {
  const [high, low] = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (high + 0.05) / (low + 0.05);
}

function readableLightness(accent: CoverAccent, surface: Rgb, start: number, step: number): number {
  let lightness = start;
  while (contrast(toRgb(accent.hue, accent.saturation, lightness), surface) < MIN_CONTRAST && lightness > 0.1 && lightness < 0.9) {
    lightness += step;
  }
  return lightness;
}

function toHsl(red: number, green: number, blue: number): [number, number, number] {
  const r = red / 255, g = green / 255, b = blue / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const lightness = (max + min) / 2;
  const delta = max - min;
  if (delta === 0) return [0, 0, lightness];
  const saturation = delta / (1 - Math.abs(2 * lightness - 1));
  const hue = max === r ? ((g - b) / delta + 6) % 6 : max === g ? (b - r) / delta + 2 : (r - g) / delta + 4;
  return [hue * 60, saturation, lightness];
}

function vividAccent(pixels: Uint8ClampedArray): CoverAccent | null {
  const weights = new Array<number>(HUE_BUCKETS).fill(0);
  const hues = new Array<number>(HUE_BUCKETS).fill(0);
  const saturations = new Array<number>(HUE_BUCKETS).fill(0);
  for (let i = 0; i < pixels.length; i += 4) {
    const [hue, saturation, lightness] = toHsl(pixels[i], pixels[i + 1], pixels[i + 2]);
    const weight = saturation * (1 - Math.abs(lightness - 0.5) * 1.6);
    if (saturation < 0.2 || weight <= 0) continue;
    const bucket = Math.floor(hue / (360 / HUE_BUCKETS)) % HUE_BUCKETS;
    weights[bucket] += weight;
    hues[bucket] += hue * weight;
    saturations[bucket] += saturation * weight;
  }
  const best = weights.indexOf(Math.max(...weights));
  if (weights[best] < (pixels.length / 4) * 0.02) return null;
  return {
    hue: Math.round(hues[best] / weights[best]),
    saturation: Math.min(0.85, Math.max(0.45, saturations[best] / weights[best])),
  };
}

export function useCoverAccent(url: string | null): CSSProperties | undefined {
  const [accent, setAccent] = useState<CoverAccent | null>(null);

  useEffect(() => {
    setAccent(null);
    if (!url) return;
    let active = true;
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = SAMPLE_SIZE;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context || !active) return;
      context.drawImage(image, 0, 0, SAMPLE_SIZE, SAMPLE_SIZE);
      setAccent(vividAccent(context.getImageData(0, 0, SAMPLE_SIZE, SAMPLE_SIZE).data));
    };
    image.src = url;
    return () => {
      active = false;
    };
  }, [url]);

  if (!accent) return undefined;
  const percent = (value: number) => `${Math.round(value * 100)}%`;
  return {
    "--cover-h": accent.hue,
    "--cover-s": percent(accent.saturation),
    "--cover-light-l": percent(readableLightness(accent, LIGHT_SURFACE, 0.4, -0.01)),
    "--cover-dark-l": percent(readableLightness(accent, DARK_SURFACE, 0.62, 0.01)),
  } as CSSProperties;
}
