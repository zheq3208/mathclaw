export type ChatAttachmentKind = "image" | "pdf";

export type ChatAttachment = {
  id: string;
  name: string;
  mimeType: string;
  size: number;
  kind: ChatAttachmentKind;
  absolutePath: string;
  relativePath: string;
  downloadUrl: string;
};

export type ChatMessage = {
  role: "user" | "assistant" | "tool";
  content: string;
  /** Thinking/reasoning content (from thinking models) */
  thinking?: string;
  /** Tool calls made in this turn */
  toolCalls?: ToolCallInfo[];
  /** Optional uploaded attachments associated with this message */
  attachments?: ChatAttachment[];
};

export type ToolCallInfo = {
  name: string;
  arguments?: string;
  result?: string;
  status?: "running" | "done" | "error";
};

/** SSE event from /api/agent/chat/stream */
export type StreamEvent = {
  type:
    | "thinking"
    | "content"
    | "content_replace"
    | "tool_call"
    | "tool_result"
    | "done"
    | "error";
  content?: string;
  name?: string;
  arguments?: string;
  result?: string;
  session_id?: string;
};

export type PaperItem = {
  title?: string;
  id?: string;
  published?: string;
  authors?: string[];
  summary?: string;
};

export type CronTaskType = "agent" | "text";

export type CronJobRequest = {
  input: unknown;
  session_id?: string | null;
  user_id?: string | null;
  [key: string]: unknown;
};

export type SessionItem = {
  session_id: string;
  title?: string;
  created_at?: number;
  updated_at?: number;
  message_count?: number;
};

export type CronJobItem = {
  id: string;
  name: string;
  enabled: boolean;
  task_type: CronTaskType;
  cron: string;
  timezone: string;
  channel: string;
  target_user_id: string;
  target_session_id: string;
  mode: "stream" | "final";
  text?: string | null;
  request?: CronJobRequest | null;
  schedule: {
    type: "cron";
    cron: string;
    timezone: string;
  };
  dispatch: {
    type: "channel";
    channel: string;
    target: {
      user_id: string;
      session_id: string;
    };
    mode: "stream" | "final";
    meta: Record<string, unknown>;
  };
  runtime: {
    max_concurrency: number;
    timeout_seconds: number;
    misfire_grace_seconds: number;
  };
  meta: Record<string, unknown>;
};

export type PushMessage = {
  id: string;
  text: string;
};

export type ChannelItem = {
  name: string;
  type: string;
};

export type EnvItem = {
  key: string;
  value: string;
};

export type SkillItem = {
  name?: string;
  path?: string;
  enabled?: boolean;
  description?: string;
  source?: string;
  generated?: boolean;
  deletable?: boolean;
  created_by?: string;
  categories?: string[];
};

export type SkillDraft = {
  slug: string;
  title: string;
  description: string;
  markdown: string;
  categories: string[];
};

export type McpClientItem = {
  key: string;
  name?: string;
  transport?: string;
  enabled?: boolean;
  description?: string;
  command?: string;
  args?: string[];
  url?: string;
  env?: Record<string, string>;
};

export type AgentRunningConfig = {
  max_iters: number;
  max_input_length: number;
};

export type ProviderItem = {
  name: string;
  provider_type: string;
  model_name?: string;
  api_key?: string;
  base_url?: string;
  enabled?: boolean;
  extra?: Record<string, unknown>;
};

export type WorkspaceFileItem = {
  path: string;
  category: string;
  required?: boolean;
  exists: boolean;
  editable: boolean;
  size?: number;
  modified_at?: string | null;
};

export type WorkspaceFileContent = {
  exists: boolean;
  path: string;
  abs_path?: string;
  editable: boolean;
  size?: number;
  modified_at?: string;
  content: string;
};


export type MemoryEntry = {
  name: string;
  status?: string;
  severity?: number;
  risk_score?: number;
  count?: number;
  history_count?: number;
  mastery_streak?: number;
  last_result?: string;
  last_seen_at?: string;
  updated_at?: string;
  mastered_at?: string;
  knowledge_points?: string[];
  prerequisite_gaps?: string[];
  practice_focus?: string[];
  recent_notes?: string[];
  weakness_links?: string[];
  sources?: string[];
};

export type MemoryOverview = {
  memory_path?: string;
  student_id?: string;
  student_ids?: string[];
  active_weaknesses?: MemoryEntry[];
  active_knowledge_points?: MemoryEntry[];
  mastered_weaknesses?: MemoryEntry[];
  mastered_knowledge_points?: MemoryEntry[];
  memory?: {
    recent_events?: Array<Record<string, unknown>>;
    practice_focus?: string[];
  };
  summary?: {
    active_weakness_count?: number;
    active_knowledge_point_count?: number;
    mastered_weakness_count?: number;
    mastered_knowledge_point_count?: number;
    recent_event_count?: number;
  };
  updated_at?: string;
  students?: Record<string, unknown>;
};
