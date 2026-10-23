import type { Role } from '../api/types';
export interface NavItem { label: string; path: string; }
const menus: Record<Role, NavItem[]> = {
  Operator: [{ label: 'Log Reading', path: '/log-reading' }],
  Engineer: [{ label: 'Alert Queue', path: '/alerts' }, { label: 'Work Orders', path: '/work-orders' }, { label: 'Machines', path: '/machines' }, { label: 'Log Reading', path: '/log-reading' }, { label: 'Dashboard', path: '/dashboard' }],
  Manager: [{ label: 'Dashboard', path: '/dashboard' }, { label: 'Alerts', path: '/alerts' }, { label: 'Work Orders', path: '/work-orders' }, { label: 'Machines', path: '/machines' }],
};
const landings: Record<Role, string> = { Operator: '/log-reading', Engineer: '/alerts', Manager: '/dashboard' };
export const SCREEN_ROLES = {
  logReading: ['Operator', 'Engineer'], alerts: ['Engineer', 'Manager'], workOrders: ['Engineer', 'Manager'],
  machines: ['Engineer', 'Manager'], machineEdit: ['Engineer'], dashboard: ['Engineer', 'Manager'],
} as const satisfies Record<string, readonly Role[]>;
// PUBLIC_INTERFACE
export const menuFor = (role: Role) => menus[role];
// PUBLIC_INTERFACE
export const landingFor = (role: Role) => landings[role];
// PUBLIC_INTERFACE
export const canManage = (role: Role | undefined) => role === 'Engineer';
