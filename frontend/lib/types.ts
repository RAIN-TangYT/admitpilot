export type AppStatus =
  | "delivered"
  | "partial_delivered"
  | "needs_profile_input"
  | "failed";

export type AgentCode = "aie" | "sae" | "dta" | "cds";

export interface ProgramOption {
  code: string;
  display_name: string;
  slug: string;
}

export interface SchoolOption {
  code: string;
  display_name: string;
  region: string;
  programs: ProgramOption[];
}

export interface CatalogResponse {
  schools: SchoolOption[];
  default_schools: string[];
  default_portfolio: Record<string, string>;
}

export interface MissingProfileField {
  key: string;
  label: string;
  required: boolean;
  help_text: string;
}

export interface UserProfile {
  name: string;
  degree_level: string;
  major_interest: string;
  target_regions: string[];
  academic_metrics: Record<string, unknown>;
  language_scores: Record<string, unknown>;
  experiences: string[];
  target_schools: string[];
  target_programs: string[];
  risk_preference: string;
}

export interface UserArtifact {
  artifact_id: string;
  title: string;
  source_ref: string;
  evidence_type: string;
  date_range: string;
  details: string;
  verified: boolean;
}

export interface AdmitPilotConstraints {
  cycle: string;
  timezone: string;
  timeline_weeks: number;
  target_schools: string[];
  target_program_by_school: Record<string, string>;
  user_artifacts: UserArtifact[];
  [key: string]: unknown;
}

export interface AdmitPilotRequest {
  user_query: string;
  profile: UserProfile;
  constraints: AdmitPilotConstraints;
}

export interface AgentResult {
  agent: AgentCode;
  task: string;
  status: "PENDING" | "READY" | "RUNNING" | "SUCCESS" | "FAILED" | "SKIPPED" | "DEGRADED";
  success: boolean;
  confidence: number;
  evidence_level: string;
  lineage: string[];
  trace: string[];
  blocked_by: string[];
  output: Record<string, unknown>;
}

export interface OrchestrationResponse {
  status: AppStatus;
  summary: string;
  missing_profile_fields: MissingProfileField[];
  results: AgentResult[];
  trace_id: string;
  run_id?: string;
  context?: {
    shared_memory?: Record<string, unknown>;
    decisions?: Record<string, unknown>;
  };
}

export type OrchestrationSocketEvent =
  | {
      event: "workflow_started";
      data: {
        trace_id: string;
        stages: Array<{ agent: AgentCode; task: string }>;
      };
    }
  | {
      event: "stage_started";
      data: {
        trace_id: string;
        agent: AgentCode;
        task: string;
      };
    }
  | {
      event: "stage_completed";
      data: {
        trace_id: string;
        agent: AgentCode;
        task: string;
        status: AgentResult["status"];
        success: boolean;
        result: AgentResult | null;
      };
    }
  | {
      event: "workflow_completed";
      data: {
        trace_id: string;
        response: OrchestrationResponse;
      };
    }
  | {
      event: "workflow_failed";
      data: {
        status: "failed";
        summary: string;
      };
    };

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  demo_credentials?: {
    email: string;
    password: string;
  };
}

export interface LoginResponse {
  token: string;
  user: AuthUser;
}

export interface CurrentUserResponse {
  user: AuthUser;
}

export interface RunHistoryEntry {
  run_id: string;
  trace_id: string;
  status: AppStatus;
  summary: string;
  result_count: number;
  created_at: string;
}

export interface RunHistoryResponse {
  runs: RunHistoryEntry[];
}

export interface RunDetail {
  run_id: string;
  trace_id: string;
  status: AppStatus;
  summary: string;
  result_count: number;
  request: AdmitPilotRequest;
  response: OrchestrationResponse;
  created_at: string;
}

export interface RunDetailResponse {
  run: RunDetail;
}
