import { apiRequest } from './client';
import type {
  Addendum, Alert, AlertDetail, Breach, ChecklistItem, ClosurePayload, ClosureResult, CurrentUser,
  Dashboard, DirectoryUser, LogReadingResult, MachineDetail, MachineListItem, MachinePayload,
  MachineRecord, Page, Parameter, ParameterPayload, Reading, ReadingTarget, Result, UserChoice,
  WorkOrder, WorkOrderEditPayload, WorkOrderRecord, WorkOrderStatus,
} from './types';

const MAX_PAGE = 100;

// PUBLIC_INTERFACE
export async function fetchAllPages<T>(loader: (offset: number, limit: number) => Promise<Page<T>>): Promise<T[]> {
  /** Read a complete bounded collection in backend-supported pages. */
  const rows: T[] = [];
  for (let offset = 0;;) {
    const page = await loader(offset, MAX_PAGE);
    rows.push(...page.data);
    offset += page.data.length;
    if (!page.data.length || offset >= page.total) return rows;
  }
}

// PUBLIC_INTERFACE
export const listActiveUsers = () => fetchAllPages((offset, limit) => apiRequest<Page<UserChoice>>('/v1/users', { isPublic: true, query: { offset, limit } }));
// PUBLIC_INTERFACE
export const getMe = async (userId?: string) => (await apiRequest<Result<CurrentUser>>('/v1/me', { userId })).data;
// PUBLIC_INTERFACE
export const listDirectory = () => fetchAllPages((offset, limit) => apiRequest<Page<DirectoryUser>>('/v1/users/directory', { query: { offset, limit } }));

// PUBLIC_INTERFACE
export const listMachines = (offset: number, limit: number, signal?: AbortSignal) => apiRequest<Page<MachineListItem>>('/v1/machines', { query: { offset, limit }, signal });
// PUBLIC_INTERFACE
export const getMachine = async (id: string, signal?: AbortSignal) => (await apiRequest<Result<MachineDetail>>(`/v1/machines/${encodeURIComponent(id)}`, { signal })).data;
// PUBLIC_INTERFACE
export const getMachineStatus = async (id: string, signal?: AbortSignal) => (await apiRequest<Result<any>>(`/v1/machines/${encodeURIComponent(id)}/status`, { signal })).data;
// PUBLIC_INTERFACE
export const registerMachine = async (body: MachinePayload) => (await apiRequest<Result<MachineRecord>>('/v1/machines', { method: 'POST', body })).data;
// PUBLIC_INTERFACE
export const editMachineDetails = async (id: string, body: any) => (await apiRequest<Result<MachineRecord>>(`/v1/machines/${encodeURIComponent(id)}`, { method: 'PATCH', body })).data;
// PUBLIC_INTERFACE
export const editCriticality = async (id: string, criticality: number) => (await apiRequest<Result<MachineRecord>>(`/v1/machines/${encodeURIComponent(id)}/criticality`, { method: 'PATCH', body: { criticality } })).data;
// PUBLIC_INTERFACE
export const addParameter = async (id: string, body: ParameterPayload) => (await apiRequest<Result<Parameter>>(`/v1/machines/${encodeURIComponent(id)}/parameters`, { method: 'POST', body })).data;
// PUBLIC_INTERFACE
export const editThreshold = async (id: string, threshold: string) => (await apiRequest<Result<Parameter>>(`/v1/parameters/${encodeURIComponent(id)}/threshold`, { method: 'PATCH', body: { threshold } })).data;
// PUBLIC_INTERFACE
export const editSuggestedAction = async (id: string, suggested_action: string) => (await apiRequest<Result<Parameter>>(`/v1/parameters/${encodeURIComponent(id)}/suggested-action`, { method: 'PATCH', body: { suggested_action } })).data;
// PUBLIC_INTERFACE
export const editCumulative = async (id: string, cumulative: boolean) => (await apiRequest<Result<Parameter>>(`/v1/parameters/${encodeURIComponent(id)}/cumulative`, { method: 'PATCH', body: { cumulative } })).data;

// PUBLIC_INTERFACE
export const listReadingTargets = () => fetchAllPages((offset, limit) => apiRequest<Page<ReadingTarget>>('/v1/readings/targets', { query: { offset, limit } }));
// PUBLIC_INTERFACE
export const logReading = async (parameter_id: string, value: string) => (await apiRequest<Result<LogReadingResult>>('/v1/readings', { method: 'POST', body: { parameter_id, value } })).data;
// PUBLIC_INTERFACE
export const listParameterReadings = (id: string, offset: number, limit: number, signal?: AbortSignal) => apiRequest<Page<Reading>>(`/v1/parameters/${encodeURIComponent(id)}/readings`, { query: { offset, limit }, signal });

// PUBLIC_INTERFACE
export const listAlerts = (offset: number, limit: number, signal?: AbortSignal) => apiRequest<Page<Alert>>('/v1/alerts', { query: { offset, limit }, signal });
// PUBLIC_INTERFACE
export const getAlert = async (id: string, signal?: AbortSignal) => (await apiRequest<Result<AlertDetail>>(`/v1/alerts/${encodeURIComponent(id)}`, { signal })).data;
// PUBLIC_INTERFACE
export const listBreaches = (id: string, offset: number, limit: number, signal?: AbortSignal) => apiRequest<Page<Breach>>(`/v1/alerts/${encodeURIComponent(id)}/breaches`, { query: { offset, limit }, signal });
// PUBLIC_INTERFACE
export const dismissAlert = async (id: string, reason: string, version: number) => (await apiRequest<Result<Alert>>(`/v1/alerts/${encodeURIComponent(id)}/dismissal`, { method: 'POST', body: { reason }, version })).data;
// PUBLIC_INTERFACE
export const createWorkOrder = async (id: string) => (await apiRequest<Result<WorkOrder>>(`/v1/alerts/${encodeURIComponent(id)}/work-orders`, { method: 'POST' })).data;

// PUBLIC_INTERFACE
export const listWorkOrders = (params: { offset: number; limit: number; status?: WorkOrderStatus | ''; assignee?: string }, signal?: AbortSignal) => apiRequest<Page<WorkOrderRecord>>('/v1/work-orders', { query: params, signal });
// PUBLIC_INTERFACE
export const getWorkOrder = async (id: string, signal?: AbortSignal) => (await apiRequest<Result<WorkOrder>>(`/v1/work-orders/${encodeURIComponent(id)}`, { signal })).data;
// PUBLIC_INTERFACE
export const editWorkOrder = async (id: string, body: WorkOrderEditPayload, version: number) => (await apiRequest<Result<WorkOrder>>(`/v1/work-orders/${encodeURIComponent(id)}`, { method: 'PATCH', body, version })).data;
// PUBLIC_INTERFACE
export const startWorkOrder = async (id: string, version: number) => (await apiRequest<Result<WorkOrder>>(`/v1/work-orders/${encodeURIComponent(id)}/start`, { method: 'POST', version })).data;
// PUBLIC_INTERFACE
export const cancelWorkOrder = async (id: string, reason: string, version: number) => (await apiRequest<Result<WorkOrder>>(`/v1/work-orders/${encodeURIComponent(id)}/cancellation`, { method: 'POST', body: { reason }, version })).data;
// PUBLIC_INTERFACE
export const replaceChecklist = async (id: string, items: ChecklistItem[], version: number) => (await apiRequest<Result<WorkOrder>>(`/v1/work-orders/${encodeURIComponent(id)}/parts-checklist`, { method: 'PUT', body: { items }, version })).data;
// PUBLIC_INTERFACE
export const closeWorkOrder = async (id: string, body: ClosurePayload, version: number) => (await apiRequest<Result<ClosureResult>>(`/v1/work-orders/${encodeURIComponent(id)}/closure`, { method: 'POST', body, version })).data;
// PUBLIC_INTERFACE
export const addAddendum = async (id: string, note: string) => (await apiRequest<Result<Addendum>>(`/v1/work-orders/${encodeURIComponent(id)}/addenda`, { method: 'POST', body: { note } })).data;
// PUBLIC_INTERFACE
export const getDashboard = async (filters: any, signal?: AbortSignal) => (await apiRequest<Result<Dashboard>>('/v1/dashboard', { query: filters, signal })).data;
