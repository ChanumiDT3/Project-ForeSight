/** Types mirroring the ForeSight REST API. Decimal values are strings. */
export type Role = 'Operator' | 'Engineer' | 'Manager';
export type ParameterKind = 'temperature' | 'vibration' | 'cycle_count' | 'runtime_hours' | 'custom';
export type WorkOrderStatus = 'Open' | 'In Progress' | 'Closed' | 'Cancelled';
export type AlertStatus = 'Open' | 'In Progress' | 'Resolved' | 'Dismissed';
export type PriorityLabel = 'Critical' | 'High' | 'Medium';
export type Availability = 'yes' | 'no' | 'ordered';

export interface Page<T> {
  data: T[];
  total: number;
  offset: number;
  limit: number;
}

export interface Result<T> {
  data: T;
}

export interface UserChoice {
  id: string;
  name: string;
  role: Role;
}

export interface CurrentUser extends UserChoice {
  plant_id: string;
}

export interface DirectoryUser extends UserChoice {
  active: boolean;
}

export interface ParameterPayload {
  kind: ParameterKind;
  name: string;
  threshold: string;
  suggested_action: string;
  unit?: string;
  minimum?: string;
  maximum?: string;
  precision?: number;
  cumulative?: boolean;
  baseline?: string;
  current_meter?: string;
}

export interface MachinePayload {
  equipment_id: string;
  name: string;
  location: string;
  equipment_type: string;
  criticality: number;
  parameters: ParameterPayload[];
  baseline?: string;
  current_meter?: string;
}

export interface WorkOrderEditPayload {
  assignee?: string | null;
  due_at?: string;
  scheduled_service?: boolean;
}

export interface ChecklistItem {
  part_name: string;
  part_number?: string | null;
  quantity: number;
  availability: Availability;
  notes?: string | null;
}

export interface PartUsed {
  part_name: string;
  part_number?: string | null;
  quantity: number;
  notes?: string | null;
}

export interface ClosurePayload {
  resolution_note: string;
  parts_used: PartUsed[];
  no_parts_used: boolean;
  hour_meter_value?: string;
}

export interface Parameter {
  id: string;
  machine_id: string;
  kind: ParameterKind;
  name: string;
  unit: string;
  minimum: string;
  maximum: string;
  precision: number;
  cumulative: boolean | null;
  threshold: string;
  threshold_type: 'max';
  suggested_action: string;
  created_by: string;
  created_at: string;
  updated_by: string;
  updated_at: string;
  latest_value?: string | null;
  latest_reading_at?: string | null;
}

export interface MachineRecord {
  id: string;
  equipment_id: string;
  name: string;
  location: string;
  equipment_type: string;
  criticality: number;
  baseline: string | null;
  registration_meter: string | null;
  last_service_at: string | null;
  created_by: string;
  created_at: string;
  updated_by: string;
  updated_at: string;
  parameters: Parameter[];
  monitoring_state: 'Monitored' | 'Not monitored';
}

export interface MachineListItem {
  id: string;
  equipment_id: string;
  name: string;
  location: string;
  equipment_type: string;
  status: 'Healthy' | 'At Risk';
  monitoring_state: 'Monitored' | 'Not monitored';
  parameter_count: number;
  active_alert_count: number;
}

export interface BaselineHistory {
  id: string;
  work_order_id: string;
  old_baseline: string;
  new_baseline: string;
  created_by: string;
  created_at: string;
}

export interface MachineDetail extends Omit<MachineRecord, 'parameters'> {
  parameters: Parameter[];
  runtime_applicable: boolean;
  runtime_state?: 'Ready' | 'Baseline missing' | 'Data error';
  hours_since_service?: string | null;
  active_alert_count: number;
  status: 'Healthy' | 'At Risk';
  baseline_history: BaselineHistory[];
}

export interface ReadingTarget {
  id: string;
  equipment_id: string;
  name: string;
  location: string;
  baseline: string | null;
  parameters: Parameter[];
}

export interface Reading {
  id: string;
  parameter_id: string;
  value: string;
  source: 'manual' | 'closure';
  work_order_id: string | null;
  created_by: string;
  created_at: string;
}

export interface LogReadingResult {
  reading: Reading;
  alert_id?: string | null;
}

export interface Alert {
  id: string;
  status: AlertStatus;
  priority_label: PriorityLabel;
  machine?: { equipment_id: string };
  parameter?: { name: string };
}

export interface AlertDetail extends Alert {
  latest_value: string;
  latest_breach_at: string;
  breach_count: number;
  priority_score: number;
  breakdown?: { priority_score?: number } | null;
  work_order_ids: string[];
}

export interface Breach {
  id: string;
  created_at: string;
}

export interface WorkOrderSnapshot {
  equipment_id: string;
  machine_name: string;
  machine_location: string;
  equipment_type: string;
  parameter_name: string;
  parameter_kind: ParameterKind;
  unit: string;
  fault_description: string;
  suggested_action: string;
  priority_score: number;
}

export interface WorkOrderRecord {
  id: string;
  status: WorkOrderStatus;
  snapshot: WorkOrderSnapshot;
  assignee: string | null;
  due_at: string | null;
  priority: PriorityLabel | null;
}

export interface Addendum {
  id: string;
  note: string;
  created_by: string;
  created_at: string;
}

export interface WorkOrder extends WorkOrderRecord {
  alert_id: string;
  machine_id: string;
  version: number;
  raised_from_runtime_alert: boolean;
  scheduled_service: boolean;
  parts_checklist: ChecklistItem[] | null;
  reset_applies: boolean;
  runtime_applicable: boolean;
  addenda: Addendum[];
}

export interface ClosureResult extends WorkOrder {
  machine_status: 'Healthy' | 'At Risk';
  new_baseline: string | null;
  last_service_at: string;
}

export interface Dashboard {
  filters: {
    location: string | null;
    equipment_type: string | null;
    locations: string[];
    equipment_types: string[];
  };
  open_alerts_by_priority: Record<PriorityLabel, number>;
  at_risk_machines: {
    total: number;
    items: Array<{
      id: string;
      equipment_id: string;
      name: string;
      location: string;
      equipment_type: string;
      active_alert_count: number;
    }>;
  };
  open_work_orders: {
    total: number;
    items: Array<{
      id: string;
      machine_id: string;
      equipment_id: string;
      machine_name: string;
      priority: PriorityLabel | null;
      status: WorkOrderStatus;
      assignee: string | null;
      due_at: string | null;
      alert_id: string;
    }>;
  };
}
