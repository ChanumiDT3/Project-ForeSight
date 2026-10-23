import { describe, expect, it } from 'vitest';
import { canManage, landingFor, menuFor } from './roles';

describe('role navigation (Q7b)', () => {
  it('gives Operators only Log Reading', () => {
    expect(menuFor('Operator').map((item) => item.label)).toEqual(['Log Reading']);
    expect(landingFor('Operator')).toBe('/log-reading');
  });

  it('gives Engineers the full working menu, landing on the alert queue', () => {
    expect(menuFor('Engineer').map((item) => item.label)).toEqual([
      'Alert Queue',
      'Work Orders',
      'Machines',
      'Log Reading',
      'Dashboard',
    ]);
    expect(landingFor('Engineer')).toBe('/alerts');
  });

  it('gives Managers read-only screens, landing on the dashboard', () => {
    expect(menuFor('Manager').map((item) => item.label)).toEqual(['Dashboard', 'Alerts', 'Work Orders', 'Machines']);
    expect(landingFor('Manager')).toBe('/dashboard');
    expect(canManage('Manager')).toBe(false);
    expect(canManage('Engineer')).toBe(true);
  });
});
