// One DPR owner: keep text sharp without rendering an unbounded number of pixels.
export function screenDpr(deviceDpr, quality = 1) {
  const native = Number.isFinite(deviceDpr) && deviceDpr > 0 ? deviceDpr : 1;
  const maximum = Math.min(native, 2.5);
  const minimum = Math.min(native, 1.5);
  return minimum + (maximum - minimum) * Math.max(0, Math.min(1, quality));
}

// Recover quality near 60 fps, including on 90/120 Hz displays. Require several
// sustained samples in PerformanceMonitor rather than reacting to one slow frame.
export const performanceBounds = () => [45, 58];
