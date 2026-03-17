import {
  useMemo,
  useRef,
  useEffect,
  useState,
  useCallback,
  useSyncExternalStore,
} from "react";
import type { ChangeEvent, DragEvent, KeyboardEvent } from "react";
import {
  MessageSquare,
  Send,
  Loader2,
  BrainCircuit,
  Wrench,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  XCircle,
  Square,
  PlusCircle,
  RefreshCw,
  Paperclip,
  FileText,
  ImageIcon,
  X,
} from "lucide-react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useSearchParams } from "react-router-dom";
import { getSessionDetail, getSessions, uploadChatAttachments } from "../api";
import type {
  ChatAttachment,
  ChatMessage,
  SessionItem,
  ToolCallInfo,
} from "../types";
import { preprocessMarkdown } from "../utils/markdown";
import {
  getChatRuntimeState,
  replaceChatConversation,
  sendChatMessage,
  startNewConversation,
  stopChatStreaming,
  subscribeChatRuntime,
} from "../chatRuntime";

const MAX_PENDING_FILES = 6;
const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024;

type PendingAttachment = {
  id: string;
  file: File;
  kind: ChatAttachment["kind"];
  previewUrl?: string;
};

function normalizeChatRole(value: unknown): ChatMessage["role"] {
  if (value === "user" || value === "assistant" || value === "tool") {
    return value;
  }
  return "assistant";
}

function normalizeChatAttachments(value: unknown): ChatAttachment[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const items = value
    .map((raw) => {
      if (!raw || typeof raw !== "object") return null;
      const item = raw as Record<string, unknown>;
      const kind = item.kind === "pdf" ? "pdf" : item.kind === "image" ? "image" : null;
      const name = String(item.name ?? "").trim();
      const relativePath = String(item.relativePath ?? item.relative_path ?? "").trim();
      const absolutePath = String(item.absolutePath ?? item.absolute_path ?? "").trim();
      const downloadUrl = String(item.downloadUrl ?? item.download_url ?? "").trim();
      if (!kind || !name || !relativePath || !absolutePath || !downloadUrl) return null;
      return {
        id: String(item.id ?? relativePath),
        name,
        mimeType: String(item.mimeType ?? item.mime_type ?? "application/octet-stream"),
        size: Number(item.size ?? 0) || 0,
        kind,
        absolutePath,
        relativePath,
        downloadUrl,
      } satisfies ChatAttachment;
    })
    .filter((item): item is ChatAttachment => Boolean(item));
  return items.length > 0 ? items : undefined;
}


function formatBytes(size: number): string {
  const units = ["B", "KB", "MB", "GB"];
  let value = size;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 100 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function detectAttachmentKind(file: File): ChatAttachment["kind"] | null {
  const name = file.name.toLowerCase();
  const type = file.type.toLowerCase();
  if (type.startsWith("image/")) return "image";
  if (type === "application/pdf" || name.endsWith(".pdf")) return "pdf";
  return null;
}

function toPendingAttachment(file: File): PendingAttachment | null {
  const kind = detectAttachmentKind(file);
  if (!kind) return null;
  return {
    id: `${file.name}:${file.size}:${file.lastModified}`,
    file,
    kind,
    previewUrl: kind === "image" ? URL.createObjectURL(file) : undefined,
  };
}

function releasePendingAttachment(item: PendingAttachment) {
  if (item.previewUrl) {
    URL.revokeObjectURL(item.previewUrl);
  }
}

function buildPromptWithAttachments(
  text: string,
  attachments: ChatAttachment[],
): string {
  if (attachments.length === 0) return text;

  const imageLines: string[] = [];
  const pdfLines: string[] = [];
  attachments.forEach((item, idx) => {
    const line = `${idx + 1}. ${item.name} (${item.mimeType || item.kind}, ${formatBytes(item.size)})`;
    if (item.kind === "pdf") {
      pdfLines.push(`${line}\n   file_path: ${item.absolutePath}`);
      return;
    }
    imageLines.push(line);
  });

  const prefix = text || "请结合这些附件回答我的问题";
  const sections: string[] = [prefix, "已附加文件"];
  if (imageLines.length > 0) {
    sections.push("图片附件");
    sections.push(...imageLines);
  }
  if (pdfLines.length > 0) {
    sections.push("PDF 附件");
    sections.push(...pdfLines);
  }
  sections.push(
    "如需查看图片或读取文件，请结合附件信息调用合适的工具。",
    "如需读取 PDF，请使用 read_paper(source=<file_path>) 或等效工具。",
  );

  return sections.join("\n\n");
}

export default function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const chatState = useSyncExternalStore(
    subscribeChatRuntime,
    getChatRuntimeState,
    getChatRuntimeState,
  );
  const {
    messages,
    sessionId,
    chatLoading,
    streamContent,
    streamThinking,
    streamToolCalls,
  } = chatState;
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [uploadingFiles, setUploadingFiles] = useState(false);
  const [pendingFiles, setPendingFiles] = useState<PendingAttachment[]>([]);
  const [fileError, setFileError] = useState<string>("");
  const [dragActive, setDragActive] = useState(false);
  const [historyCollapsed, setHistoryCollapsed] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const hydratedSessionRef = useRef<string>("");
  const dragDepthRef = useRef(0);
  const pendingFilesRef = useRef<PendingAttachment[]>([]);

  const canSend = useMemo(
    () => (chatInput.trim().length > 0 || pendingFiles.length > 0) && !chatLoading && !uploadingFiles,
    [chatInput, pendingFiles.length, chatLoading, uploadingFiles],
  );

  const querySessionId = searchParams.get("session_id") || undefined;

  useEffect(() => {
    pendingFilesRef.current = pendingFiles;
  }, [pendingFiles]);

  useEffect(
    () => () => {
      pendingFilesRef.current.forEach((item) => releasePendingAttachment(item));
    },
    [],
  );

  const clearPendingFiles = useCallback(() => {
    setPendingFiles((prev) => {
      prev.forEach((item) => releasePendingAttachment(item));
      return [];
    });
  }, []);

  const appendPendingFiles = useCallback((files: File[]) => {
    if (!files.length) return;

    const errors: string[] = [];

    setPendingFiles((prev) => {
      const existing = new Set(prev.map((item) => item.id));
      const next = [...prev];

      for (const file of files) {
        const id = `${file.name}:${file.size}:${file.lastModified}`;
        if (existing.has(id)) continue;

        if (next.length >= MAX_PENDING_FILES) {
          errors.push(`最多只能添加 ${MAX_PENDING_FILES} 个附件`);
          break;
        }

        const kind = detectAttachmentKind(file);
        if (!kind) {
          errors.push(`${file.name} 仅支持图片或 PDF 文件`);
          continue;
        }

        if (file.size > MAX_FILE_SIZE_BYTES) {
          errors.push(`${file.name} 大小不能超过 ${formatBytes(MAX_FILE_SIZE_BYTES)}`);
          continue;
        }

        const pending = toPendingAttachment(file);
        if (!pending) {
          errors.push(`${file.name} 附件处理失败`);
          continue;
        }

        next.push(pending);
        existing.add(id);
      }

      return next;
    });

    setFileError(errors.join(" "));
  }, []);

  const removePendingFile = useCallback((id: string) => {
    setPendingFiles((prev) => {
      const target = prev.find((item) => item.id === id);
      if (target) releasePendingAttachment(target);
      return prev.filter((item) => item.id !== id);
    });
  }, []);

  const loadSessionList = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const list = await getSessions();
      setSessions(Array.isArray(list) ? list : []);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSessionList();
  }, [loadSessionList]);

  const prevLoadingRef = useRef(chatLoading);
  useEffect(() => {
    if (prevLoadingRef.current && !chatLoading) {
      void loadSessionList();
    }
    prevLoadingRef.current = chatLoading;
  }, [chatLoading, loadSessionList]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamContent, streamThinking, streamToolCalls]);

  useEffect(() => {
    if (!sessionId) return;
    if (querySessionId === sessionId) return;
    syncQuerySession(sessionId);
    // Keep URL and active session aligned while ChatPage is mounted.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, querySessionId]);

  useEffect(() => {
    const targetSessionId = querySessionId || sessionId;
    if (!targetSessionId) return;
    if (querySessionId && querySessionId === sessionId && messages.length > 0) {
      return;
    }
    // Keep in-memory messages while navigating tabs; only hydrate when needed.
    if (!querySessionId && messages.length > 0) return;
    if (targetSessionId === hydratedSessionRef.current) return;
    hydratedSessionRef.current = targetSessionId;

    let cancelled = false;
    void getSessionDetail(targetSessionId)
      .then((detail) => {
        if (cancelled) return;
        const sessionMessages = Array.isArray(detail?.messages)
          ? detail.messages
          : [];
        const restored: ChatMessage[] = sessionMessages.map((m: any) => ({
          role: normalizeChatRole(m?.role),
          content: String(m?.content ?? ""),
          attachments:
            normalizeChatAttachments(m?.attachments)
            ?? normalizeChatAttachments(m?.metadata?.attachments),
        }));
        replaceChatConversation(targetSessionId, restored, {
          stopStreaming: false,
        });
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [messages.length, querySessionId, sessionId]);

  function syncQuerySession(nextSessionId?: string) {
    const next = new URLSearchParams(searchParams);
    if (nextSessionId) {
      next.set("session_id", nextSessionId);
    } else {
      next.delete("session_id");
    }
    setSearchParams(next, { replace: true });
  }

  function handleStop() {
    stopChatStreaming();
  }

  function onNewConversation() {
    startNewConversation();
    setChatInput("");
    setFileError("");
    clearPendingFiles();
    hydratedSessionRef.current = "";
    syncQuerySession(undefined);
  }

  async function onOpenSession(targetSessionId: string) {
    if (!targetSessionId) return;
    if (chatLoading) stopChatStreaming();
    syncQuerySession(targetSessionId);
    if (targetSessionId === sessionId && messages.length > 0) return;
    try {
      const detail = await getSessionDetail(targetSessionId);
      const sessionMessages = Array.isArray(detail?.messages)
        ? detail.messages
        : [];
      const restored: ChatMessage[] = sessionMessages.map((m: any) => ({
        role: normalizeChatRole(m?.role),
        content: String(m?.content ?? ""),
        attachments:
          normalizeChatAttachments(m?.attachments)
          ?? normalizeChatAttachments(m?.metadata?.attachments),
      }));
      hydratedSessionRef.current = targetSessionId;
      replaceChatConversation(targetSessionId, restored);
    } catch {
      // Ignore and keep current UI state.
    }
  }

  async function onSendChat() {
    const text = chatInput.trim();
    if ((!text && pendingFiles.length === 0) || chatLoading || uploadingFiles) {
      return;
    }

    let uploadedAttachments: ChatAttachment[] = [];

    if (pendingFiles.length > 0) {
      setUploadingFiles(true);
      setFileError("");
      try {
        uploadedAttachments = await uploadChatAttachments(
          pendingFiles.map((item) => item.file),
          sessionId,
        );
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "文件上传失败";
        setFileError(message);
        return;
      } finally {
        setUploadingFiles(false);
      }
    }

    const payloadText = buildPromptWithAttachments(text, uploadedAttachments);
    const displayText = text
      || (uploadedAttachments.length > 0
        ? `已附加 ${uploadedAttachments.length} 个文件`
        : payloadText);

    const activeSessionId = sendChatMessage(displayText, {
      preferredSessionId: sessionId,
      payloadMessage: payloadText,
      attachments: uploadedAttachments,
    });
    if (!activeSessionId) return;

    hydratedSessionRef.current = activeSessionId;
    if (searchParams.get("session_id") !== activeSessionId) {
      syncQuerySession(activeSessionId);
    }

    setChatInput("");
    setFileError("");
    clearPendingFiles();
  }

  function onInputKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && canSend) {
      e.preventDefault();
      void onSendChat();
    }
  }

  function onFilePickerChange(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    appendPendingFiles(files);
    e.target.value = "";
  }

  function onPickFiles() {
    fileInputRef.current?.click();
  }

  function onDragEnter(e: DragEvent<HTMLElement>) {
    if (!Array.from(e.dataTransfer.types).includes("Files")) return;
    e.preventDefault();
    e.stopPropagation();
    dragDepthRef.current += 1;
    setDragActive(true);
  }

  function onDragOver(e: DragEvent<HTMLElement>) {
    if (!Array.from(e.dataTransfer.types).includes("Files")) return;
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "copy";
  }

  function onDragLeave(e: DragEvent<HTMLElement>) {
    if (!Array.from(e.dataTransfer.types).includes("Files")) return;
    e.preventDefault();
    e.stopPropagation();
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) {
      setDragActive(false);
    }
  }

  function onDrop(e: DragEvent<HTMLElement>) {
    if (!Array.from(e.dataTransfer.types).includes("Files")) return;
    e.preventDefault();
    e.stopPropagation();
    dragDepthRef.current = 0;
    setDragActive(false);
    appendPendingFiles(Array.from(e.dataTransfer.files ?? []));
  }



  return (
    <div className="chat-page-shell">
      <div className="chat-layout-shell">
        <button
          type="button"
          className={`chat-history-float-toggle${historyCollapsed ? " collapsed" : ""}`}
          aria-label={historyCollapsed ? "展开历史记录" : "收起历史记录"}
          title={historyCollapsed ? "展开历史记录" : "收起历史记录"}
          onClick={() => setHistoryCollapsed((value) => !value)}
        >
          {historyCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>

        <div className={`panel chat-layout${historyCollapsed ? " history-collapsed" : ""}`}>
          <aside className={`chat-history-panel${historyCollapsed ? " collapsed" : ""}`}>
            {!historyCollapsed && (
              <>
                <div className="chat-history-header">
                  <div className="chat-history-actions">
                    <button className="btn-secondary btn-sm" onClick={onNewConversation}>
                      <PlusCircle size={14} />
                      新对话
                    </button>
                    <button
                      className="btn-ghost btn-sm"
                      onClick={() => void loadSessionList()}
                      disabled={sessionsLoading}
                    >
                      <RefreshCw
                        size={14}
                        className={sessionsLoading ? "spin-icon" : undefined}
                      />
                      刷新
                    </button>
                  </div>
                </div>

                <div className="chat-history-list">
                  {sessions.length === 0 && (
                    <div className="chat-history-empty">暂无聊天记录</div>
                  )}
                  {sessions.map((session) => (
                    <button
                      key={session.session_id}
                      className={`chat-history-item${
                        session.session_id === sessionId ? " active" : ""
                      }`}
                      onClick={() => void onOpenSession(session.session_id)}
                    >
                      <div className="chat-history-title">
                        {session.title || session.session_id}
                      </div>
                    </button>
                  ))}
                </div>
              </>
            )}
          </aside>

          <div
            className={`chat-container${dragActive ? " drag-active" : ""}`}
            onDragEnter={onDragEnter}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
          >
            {dragActive && (
              <div className="chat-drop-overlay">
                <ImageIcon size={18} />
                <span>支持 PDF 和图片</span>
              </div>
            )}

            <div className="chat-toolbar">
              <div className="chat-toolbar-session">
                当前会话：{sessionId || "未创建"}
              </div>
              <button className="btn-secondary btn-sm" onClick={onNewConversation}>
                <PlusCircle size={14} />
                新对话
              </button>
            </div>

            <div className="messages">
              {messages.length === 0 && !chatLoading && (
                <div className="chat-empty">
                  <div className="chat-empty-icon">
                    <MessageSquare size={28} />
                  </div>
                  <h3>拖拽文件到此处</h3>
                  <p>
                    上传图片或 PDF，MathClaw 会帮你解析题目并继续解题。
                  </p>
                </div>
              )}

              {messages.map((msg, idx) => (
                <div key={idx} className={`msg ${msg.role}`}>
                  <div className="msg-avatar">{msg.role === "user" ? "U" : "M"}</div>
                  <div className="msg-bubble">
                    {msg.thinking && <ThinkingBlock content={msg.thinking} />}
                    {msg.toolCalls && <ToolCallsBlock calls={msg.toolCalls} />}
                    {msg.attachments && msg.attachments.length > 0 && (
                      <MessageAttachments
                        attachments={msg.attachments}
                        compact={msg.role === "user"}
                      />
                    )}
                    <MessageContent content={msg.content} />
                  </div>
                </div>
              ))}

              {chatLoading && (
                <div className="msg assistant">
                  <div className="msg-avatar">M</div>
                  <div className="msg-bubble">
                    {streamThinking && (
                      <ThinkingBlock content={streamThinking} streaming />
                    )}
                    {streamToolCalls.length > 0 && (
                      <ToolCallsBlock calls={streamToolCalls} />
                    )}
                    {streamContent ? (
                      <MessageContent content={streamContent} />
                    ) : (
                      !streamThinking &&
                      streamToolCalls.length === 0 && (
                        <span className="stream-cursor">
                          <Loader2 size={14} className="spinner" />
                        </span>
                      )
                    )}
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-wrap">
              {pendingFiles.length > 0 && (
                <div className="chat-pending-files">
                  {pendingFiles.map((item) => (
                    <div key={item.id} className="chat-pending-item">
                      {item.kind === "image" && item.previewUrl ? (
                        <img
                          className="chat-pending-thumb"
                          src={item.previewUrl}
                          alt={item.file.name}
                        />
                      ) : (
                        <div className="chat-pending-icon">
                          <FileText size={16} />
                        </div>
                      )}
                      <div className="chat-pending-meta">
                        <div className="chat-pending-name">{item.file.name}</div>
                        <div className="chat-pending-size">
                          {item.kind.toUpperCase()} · {formatBytes(item.file.size)}
                        </div>
                      </div>
                      <button
                        type="button"
                        className="chat-pending-remove"
                        onClick={() => removePendingFile(item.id)}
                        aria-label={`移除 ${item.file.name}`}
                      >
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {fileError && <div className="chat-file-error">{fileError}</div>}

              <div className="chat-input-bar">
                <button
                  type="button"
                  className="btn-secondary chat-attach-btn"
                  onClick={onPickFiles}
                  disabled={chatLoading || uploadingFiles}
                  aria-label="选择附件"
                >
                  <Paperclip size={16} />
                  上传文件
                </button>

                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept="image/*,application/pdf,.pdf"
                  className="chat-file-input"
                  onChange={onFilePickerChange}
                />

                <input
                  value={chatInput}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    setChatInput(e.target.value)
                  }
                  placeholder="输入问题，或上传图片/PDF..."
                  onKeyDown={onInputKeyDown}
                />
                {chatLoading ? (
                  <button onClick={handleStop} className="btn-stop">
                    <Square size={14} />
                    停止
                  </button>
                ) : (
                  <button onClick={() => void onSendChat()} disabled={!canSend}>
                    {uploadingFiles ? (
                      <>
                        <Loader2 size={16} className="spinner" />
                        上传中
                      </>
                    ) : (
                      <>
                        <Send size={16} />
                        发送
                      </>
                    )}
                  </button>
                )}
              </div>
              <div className="chat-input-hint">
                支持拖拽图片或 PDF 到这里，单次最多上传 6 个文件。
              </div>
            </div>

            {sessionId && (
              <div className="chat-session-label">
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: "var(--success)",
                    display: "inline-block",
                  }}
                />
                新对话{sessionId}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function MessageContent({ content }: { content: string }) {
  if (!content) return null;
  const normalized = preprocessMarkdown(content);
  return (
    <div className="msg-text markdown-body">
      <Markdown remarkPlugins={[remarkGfm]}>{normalized}</Markdown>
    </div>
  );
}

function MessageAttachments({
  attachments,
  compact,
}: {
  attachments: ChatAttachment[];
  compact?: boolean;
}) {
  return (
    <div className={`msg-attachments${compact ? " compact" : ""}`}>
      {attachments.map((item) => (
        <a
          key={item.id}
          className={`msg-attachment msg-attachment-${item.kind}`}
          href={item.downloadUrl}
          target="_blank"
          rel="noreferrer"
          title={item.absolutePath}
        >
          {item.kind === "image" ? (
            <img src={item.downloadUrl} alt={item.name} loading="lazy" />
          ) : (
            <div className="msg-attachment-placeholder">
              <FileText size={16} />
            </div>
          )}
          <div className="msg-attachment-meta">
            <span className="msg-attachment-name">{item.name}</span>
            <span className="msg-attachment-size">{formatBytes(item.size)}</span>
          </div>
        </a>
      ))}
    </div>
  );
}

function ThinkingBlock({
  content,
  streaming,
}: {
  content: string;
  streaming?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="thinking-block">
      <div className="thinking-header" onClick={() => setExpanded((v) => !v)}>
        <BrainCircuit size={14} />
        <span>{streaming ? "生成中..." : "发送"}</span>
        {streaming && <Loader2 size={12} className="spinner" />}
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </div>
      {expanded && <div className="thinking-content">{content}</div>}
    </div>
  );
}

function ToolCallsBlock({ calls }: { calls: ToolCallInfo[] }) {
  return (
    <div className="tool-calls-block">
      {calls.map((tc, i) => (
        <div
          key={i}
          className={`tool-call-item tool-call-${tc.status || "running"}`}
        >
          <div className="tool-call-header">
            {tc.status === "running" ? (
              <Loader2 size={13} className="spinner" />
            ) : tc.status === "error" ? (
              <XCircle size={13} />
            ) : (
              <CheckCircle2 size={13} />
            )}
            <Wrench size={12} />
            <span className="tool-call-name">{tc.name}</span>
          </div>
        </div>
      ))}
    </div>
  );
}




