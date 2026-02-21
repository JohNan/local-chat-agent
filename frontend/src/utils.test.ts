import { describe, it, expect, vi, afterEach } from 'vitest';
import { generateId } from './utils';

describe('generateId', () => {
  const originalCrypto = global.crypto;

  afterEach(() => {
    // Restore global.crypto and mocks after each test
    Object.defineProperty(global, 'crypto', {
      value: originalCrypto,
      writable: true
    });
    vi.restoreAllMocks();
  });

  it('should use crypto.randomUUID when available', () => {
    const mockUUID = '12345678-1234-1234-1234-1234567890ab';

    // Mock crypto.randomUUID
    const mockCrypto = {
      randomUUID: vi.fn().mockReturnValue(mockUUID)
    };

    Object.defineProperty(global, 'crypto', {
      value: mockCrypto,
      writable: true
    });

    const id = generateId();

    expect(mockCrypto.randomUUID).toHaveBeenCalled();
    expect(id).toBe(mockUUID);
  });

  it('should fall back to Math.random when crypto is undefined', () => {
    // Mock crypto as undefined
    Object.defineProperty(global, 'crypto', {
      value: undefined,
      writable: true
    });

    const randomSpy = vi.spyOn(Math, 'random');

    const id = generateId();

    expect(randomSpy).toHaveBeenCalled();
    expect(typeof id).toBe('string');
    expect(id.length).toBeGreaterThan(0);
    // Check if it's alphanumeric (base36)
    expect(id).toMatch(/^[a-z0-9]+$/);
  });

  it('should fall back to Math.random when crypto.randomUUID is undefined', () => {
    // Mock crypto but without randomUUID
    Object.defineProperty(global, 'crypto', {
      value: {},
      writable: true
    });

    const randomSpy = vi.spyOn(Math, 'random');

    const id = generateId();

    expect(randomSpy).toHaveBeenCalled();
    expect(typeof id).toBe('string');
    expect(id.length).toBeGreaterThan(0);
    expect(id).toMatch(/^[a-z0-9]+$/);
  });
});
