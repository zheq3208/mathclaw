import { useEffect, useState } from "react";
import type { ChangeEvent } from "react";
import { Cable, RefreshCw, Plus, Trash2 } from "lucide-react";
import {
  listMcpClients,
  createMcpClient,
  toggleMcpClient,
  deleteMcpClient,
} from "../api";
import type { McpClientItem } from "../types";
import { PageHeader, EmptyState, Badge, Toggle } from "../components/ui";

const MCP_NAME_LABELS: Record<string, string> = {
  tavily: "\u8054\u7f51\u641c\u7d22",
  "Tavily Search": "\u8054\u7f51\u641c\u7d22",
  playwright: "Playwright \u6d4f\u89c8\u5668",
  "Playwright Browser": "Playwright \u6d4f\u89c8\u5668",
  filesystem: "\u6587\u4ef6\u7cfb\u7edf",
  "Exam Filesystem": "\u8bd5\u5377\u6587\u4ef6\u7cfb\u7edf",
};

const MCP_DESCRIPTION_LABELS: Record<string, string> = {
  tavily: "\u7528\u4e8e\u8054\u7f51\u641c\u7d22\u548c\u7f51\u9875\u5185\u5bb9\u63d0\u53d6",
  "Tavily Search": "\u7528\u4e8e\u8054\u7f51\u641c\u7d22\u548c\u7f51\u9875\u5185\u5bb9\u63d0\u53d6",
  "Remote Tavily MCP for web search and extraction.": "\u7528\u4e8e\u8054\u7f51\u641c\u7d22\u548c\u7f51\u9875\u5185\u5bb9\u63d0\u53d6",
  playwright: "\u7528\u4e8e\u52a8\u6001\u6559\u80b2\u7f51\u7ad9\u7684\u6d4f\u89c8\u5668\u81ea\u52a8\u5316",
  "Playwright Browser": "\u7528\u4e8e\u52a8\u6001\u6559\u80b2\u7f51\u7ad9\u7684\u6d4f\u89c8\u5668\u81ea\u52a8\u5316",
  "Browser automation for dynamic exam and education sites.": "\u7528\u4e8e\u52a8\u6001\u6559\u80b2\u7f51\u7ad9\u7684\u6d4f\u89c8\u5668\u81ea\u52a8\u5316",
  filesystem: "\u5b89\u5168\u8bbf\u95ee\u8bd5\u5377\u5f52\u6863\u548c\u5de5\u4f5c\u76ee\u5f55",
  "Exam Filesystem": "\u5b89\u5168\u8bbf\u95ee\u8bd5\u5377\u5f52\u6863\u548c\u5de5\u4f5c\u76ee\u5f55",
  "Safe file access for exam archives and working directories.": "\u5b89\u5168\u8bbf\u95ee\u8bd5\u5377\u5f52\u6863\u548c\u5de5\u4f5c\u76ee\u5f55",
};

const MCP_TRANSPORT_LABELS: Record<string, string> = {
  stdio: "\u6807\u51c6\u8f93\u5165\u8f93\u51fa",
  streamable_http: "\u6d41\u5f0f HTTP",
  http: "HTTP",
  sse: "SSE",
};

function getMcpDisplayName(item: McpClientItem): string {
  return MCP_NAME_LABELS[item.key] || MCP_NAME_LABELS[item.name || ""] || item.name || item.key;
}

function getMcpDescription(item: McpClientItem): string {
  return MCP_DESCRIPTION_LABELS[item.key]
    || MCP_DESCRIPTION_LABELS[item.name || ""]
    || MCP_DESCRIPTION_LABELS[item.description || ""]
    || item.description
    || "";
}

function getTransportLabel(transport?: string): string {
  return MCP_TRANSPORT_LABELS[String(transport || "")] || String(transport || "-");
}

export default function McpPage() {
  const [clients, setClients] = useState<McpClientItem[]>([]);
  const [newKey, setNewKey] = useState("");
  const [newName, setNewName] = useState("");
  const [newCommand, setNewCommand] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [loadError, setLoadError] = useState("");

  async function onLoad() {
    try {
      setClients(await listMcpClients());
      setLoadError("");
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "\u52a0\u8f7d MCP \u5ba2\u6237\u7aef\u5931\u8d25");
    } finally {
      setLoaded(true);
    }
  }

  useEffect(() => {
    void onLoad();
  }, []);

  async function onCreate() {
    if (!newKey.trim()) return;
    await createMcpClient(newKey.trim(), {
      name: newName.trim() || newKey.trim(),
      transport: "stdio",
      enabled: true,
      description: "",
      command: newCommand.trim() || "npx",
      args: [],
      url: "",
      env: {},
    });
    setNewKey("");
    setNewName("");
    setNewCommand("");
    setShowAdd(false);
    await onLoad();
  }

  async function onToggle(key: string) {
    await toggleMcpClient(key);
    await onLoad();
  }

  async function onDelete(key: string) {
    await deleteMcpClient(key);
    await onLoad();
  }

  return (
    <div className="panel">
      <PageHeader
        title="MCP 客户端"
        description="管理 Model Context Protocol 客户端连接"
        actions={
          <div className="row">
            <button
              className="btn-secondary"
              onClick={() => setShowAdd(!showAdd)}
            >
              <Plus size={15} />
              新增客户端
            </button>
            <button onClick={onLoad}>
              <RefreshCw size={15} />
              刷新
            </button>
          </div>
        }
      />

      {showAdd && (
        <div
          className="card mb-4"
          style={{
            borderColor: "var(--brand-200)",
            background: "var(--brand-50)",
          }}
        >
          <h3 style={{ marginBottom: 12 }}>
            <Plus
              size={14}
              style={{ marginRight: 6, verticalAlign: "middle" }}
            />
            添加新客户端
          </h3>
          <div className="row wrap" style={{ gap: 10 }}>
            <input
              value={newKey}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setNewKey(e.target.value)
              }
              placeholder="客户端 Key"
              style={{ flex: "1 1 180px" }}
            />
            <input
              value={newName}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setNewName(e.target.value)
              }
              placeholder="显示名称"
              style={{ flex: "1 1 180px" }}
            />
            <input
              value={newCommand}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setNewCommand(e.target.value)
              }
              placeholder="命令 (e.g. npx)"
              style={{ flex: "1 1 150px" }}
            />
            <button onClick={onCreate}>
              <Plus size={15} />
              创建
            </button>
          </div>
        </div>
      )}

      {loadError && (
        <div className="skill-creator-status is-error skill-list-status">
          {loadError}
        </div>
      )}

      {loaded && clients.length === 0 && !loadError && (
        <EmptyState
          icon={<Cable size={28} />}
          title="\u6682\u65e0 MCP \u5ba2\u6237\u7aef"
          description="\u7ba1\u7406 Agent \u7684\u5916\u90e8\u5de5\u5177\u548c\u670d\u52a1\u8fde\u63a5"
          action={
            <button onClick={onLoad}>
              <RefreshCw size={15} />
              \u91cd\u65b0\u52a0\u8f7d
            </button>
          }
        />
      )}

      <div className="card-list animate-list">
        {clients.map((item: McpClientItem) => (
          <div key={item.key} className="data-row">
            <div className="data-row-info">
              <div className="data-row-title">
                <Cable
                  size={14}
                  style={{ marginRight: 6, verticalAlign: "middle" }}
                />
                {getMcpDisplayName(item)}
                <Badge variant={item.enabled ? "success" : "neutral"}>
                  {item.enabled ? "已启用" : "已禁用"}
                </Badge>
              </div>
              {getMcpDescription(item) && (
                <div className="data-row-meta">{getMcpDescription(item)}</div>
              )}
              <div className="data-row-meta">
                标识：{item.key}
                <span style={{ margin: "0 6px" }}>·</span>
                传输：{getTransportLabel(item.transport)}
                {item.command && (
                  <>
                    <span style={{ margin: "0 6px" }}>·</span>
                    命令：{item.command}
                  </>
                )}
              </div>
            </div>
            <div className="data-row-actions">
              <Toggle
                checked={item.enabled ?? true}
                onChange={() => onToggle(item.key)}
              />
              <button
                className="btn-sm danger btn-icon"
                onClick={() => onDelete(item.key)}
                data-tooltip="删除"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
