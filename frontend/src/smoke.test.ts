import { describe, expect, it } from 'vitest';

describe('dashboard runtime', () => {
  it('formats a backend-style numeric total safely', () => {
    expect(new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(-12.5)).toBe('-13');
  });
});
