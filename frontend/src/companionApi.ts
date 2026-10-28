import type { DomainRecord } from './api';

export interface ModelStatus {
  state: string; mode: string; version: string | null; message: string;
  hosted_provider: boolean; generative_model_used: boolean;
}
export type TypedRecord<T> = Omit<DomainRecord, 'data'> & { data: T };
export type CompanionConversation = TypedRecord<{
  owner_actor_id: string; workspace: string; context_record_versions: Record<string, number>;
  active_message_id: string | null; next_turn: number;
  progress?: { phase: string; message: string; since: string };
  last_model_status?: ModelStatus;
}>;
export type CompanionMessage = TypedRecord<{
  role: string; text: string; reply_kind?: string; facts?: unknown[]; next_steps?: Array<string | {id?: string; text: string}>;
  missing_inputs?: string[]; source_refs?: unknown[]; model?: Record<string, unknown>;
  reply_to_message_id?: string; action_ids?: string[];
  request?: { jurisdiction?: string | null; operation_date?: string | null };
}>;
export type ActionPreview = TypedRecord<{
  kind: 'task_draft' | 'workflow_draft' | 'case_draft'; label: string;
  preview: Record<string, unknown>; owner_actor_id: string; status?: string;
  expires_at?: string;
}>;
export type CompanionTask = TypedRecord<{
  owner_actor_id: string; conversation_id: string; source_message_id: string;
  description: string; due_at: string | null; completed_at: string | null;
  created_from_action_id: string; workflow_id?: string;
}>;
export interface CompanionJob {
  id: string; kind: string; state: string; version: number;
  payload: { conversation_id: string; message_id: string };
  result?: unknown; error?: string | null;
}
export interface WorkflowJob {
  id: string; kind: 'agent_orchestration'; state: string; version: number;
  payload: { workflow_id: string; workflow_version: number };
  result?: unknown; error?: string | null;
}
export interface CompanionDetail {
  conversation: CompanionConversation; messages: CompanionMessage[];
  action_previews: ActionPreview[]; tasks: CompanionTask[]; active_job: CompanionJob | null;
  model_status: ModelStatus;
}
export interface CompanionCatalog {
  workspaces: unknown; action_kinds: unknown; model_status: ModelStatus; contracts?: unknown;
}
export interface SendResponse {
  conversation: CompanionConversation; user_message: CompanionMessage;
  job: CompanionJob; reply: null; action_previews: ActionPreview[]; model_status: ModelStatus;
}
export interface ConfirmResponse {
  conversation: CompanionConversation; action: ActionPreview;
  task?: CompanionTask; workflow?: DomainRecord; job?: CompanionJob | WorkflowJob;
  case?: DomainRecord;
}
export const companionWorkspaces: Record<string, string> = {
  operations: 'operations', scheduling: 'scheduling', airspace: 'airspace',
  authorisations: 'authorisations', safety: 'safety_evidence', library: 'regulatory',
  incidents: 'incidents', fleet: 'fleet', commercial: 'deployment',
  administration: 'administration', agents: 'agents', crossborder: 'coordination',
};
