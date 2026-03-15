import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, BookOpen, Brain, CheckCircle2, History, RefreshCw } from "lucide-react";
import { getMemoryOverview, markMemoryItemMastered } from "../api";
import type { MemoryEntry, MemoryOverview } from "../types";
import { Badge, EmptyState, PageHeader, StatCard } from "../components/ui";

function fmtTime(value?: string): string {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString();
}

function fmtRisk(value?: number): string {
  if (typeof value !== "number") return "-";
  return `${Math.round(value * 100)}%`;
}

function chipList(items?: string[]) {
  return Array.isArray(items) ? items.filter(Boolean).slice(0, 4) : [];
}

export default function MemoryPage() {
  const [studentId, setStudentId] = useState("");
  const [availableStudents, setAvailableStudents] = useState<string[]>([]);
  const [overview, setOverview] = useState<MemoryOverview | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyKey, setBusyKey] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function loadMemory(nextStudentId?: string) {
    setLoading(true);
    try {
      const base = await getMemoryOverview();
      const ids = Array.isArray(base.student_ids) ? base.student_ids : [];
      setAvailableStudents(ids);
      const resolvedStudentId = nextStudentId || studentId || ids[0] || "__global__";
      setStudentId(resolvedStudentId);
      const detail = await getMemoryOverview(resolvedStudentId);
      setOverview(detail);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载记忆失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadMemory();
  }, []);

  const recentEvents = useMemo(() => {
    const items = overview?.memory?.recent_events;
    return Array.isArray(items) ? items.slice().reverse().slice(0, 12) : [];
  }, [overview]);

  async function onMarkMastered(itemType: "knowledge_point" | "weakness", entry: MemoryEntry) {
    if (!overview?.student_id || !entry.name) return;
    const confirmed = window.confirm(`将「${entry.name}」标记为已掌握？
这会把它从活跃记忆中移到已掌握归档。`);
    if (!confirmed) return;
    const actionKey = `${itemType}:${entry.name}`;
    setBusyKey(actionKey);
    setError("");
    setMessage("");
    try {
      await markMemoryItemMastered(overview.student_id, itemType, entry.name, "teacher confirmed mastery");
      setMessage(`已归档：${entry.name}`);
      await loadMemory(overview.student_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新记忆失败");
    } finally {
      setBusyKey("");
    }
  }

  return (
    <div className="panel">
      <PageHeader
        title="全局学习记忆"
        description="独立于单次对话之外，持续记录学生薄弱点、掌握情况与最近学习事件。已掌握的点会移出活跃记忆，进入归档。"
        actions={
          <div className="memory-page-toolbar">
            <select
              className="memory-student-select"
              value={studentId}
              onChange={(e) => void loadMemory(e.target.value)}
            >
              {(availableStudents.length ? availableStudents : ["__global__"]).map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            <button onClick={() => void loadMemory(studentId)}>
              <RefreshCw size={15} />
              刷新记忆
            </button>
          </div>
        }
      />

      {error && <div className="skill-creator-status is-error skill-list-status">{error}</div>}
      {message && <div className="skill-creator-status is-success skill-list-status">{message}</div>}

      {!overview && !loading && (
        <EmptyState
          icon={<Brain size={28} />}
          title="还没有学习记忆"
          description="等学生完成诊断、微测或掌握度更新后，这里会出现跨会话学习画像。"
          action={
            <button onClick={() => void loadMemory(studentId)}>
              <RefreshCw size={15} />
              重新加载
            </button>
          }
        />
      )}

      {overview && (
        <>
          <div className="memory-stats-grid">
            <StatCard label="活跃薄弱点" value={overview.summary?.active_weakness_count ?? 0} icon={<AlertTriangle size={18} />} variant="warning" />
            <StatCard label="活跃知识点" value={overview.summary?.active_knowledge_point_count ?? 0} icon={<Brain size={18} />} variant="brand" />
            <StatCard label="已掌握归档" value={(overview.summary?.mastered_weakness_count ?? 0) + (overview.summary?.mastered_knowledge_point_count ?? 0)} icon={<CheckCircle2 size={18} />} variant="success" />
            <StatCard label="最近事件" value={overview.summary?.recent_event_count ?? 0} icon={<History size={18} />} variant="info" />
          </div>

          <div className="memory-layout-grid">
            <section className="card memory-section">
              <div className="memory-section-head">
                <h3>活跃薄弱点</h3>
                <Badge variant="warning">优先训练</Badge>
              </div>
              {(overview.active_weaknesses || []).length === 0 ? (
                <div className="memory-empty-note">当前没有活跃薄弱点。</div>
              ) : (
                <div className="card-list">
                  {(overview.active_weaknesses || []).map((entry) => (
                    <div key={`weak-${entry.name}`} className="data-row memory-entry-row">
                      <div className="data-row-info">
                        <div className="data-row-title">
                          <span>{entry.name}</span>
                          <Badge variant="warning">严重度 {fmtRisk(entry.severity)}</Badge>
                        </div>
                        <div className="data-row-meta">
                          最近结果：{entry.last_result || "-"} · 最近出现：{fmtTime(entry.last_seen_at)} · 连续掌握：{entry.mastery_streak ?? 0}
                        </div>
                        <div className="memory-chip-row">
                          {chipList(entry.knowledge_points).map((item) => <span key={item} className="memory-chip">{item}</span>)}
                        </div>
                      </div>
                      <div className="data-row-actions">
                        <button
                          disabled={busyKey === `weakness:${entry.name}`}
                          onClick={() => void onMarkMastered("weakness", entry)}
                        >
                          标记已掌握
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="card memory-section">
              <div className="memory-section-head">
                <h3>活跃知识点</h3>
                <Badge variant="info">微测优先使用</Badge>
              </div>
              {(overview.active_knowledge_points || []).length === 0 ? (
                <div className="memory-empty-note">当前没有活跃知识点。</div>
              ) : (
                <div className="card-list">
                  {(overview.active_knowledge_points || []).map((entry) => (
                    <div key={`kp-${entry.name}`} className="data-row memory-entry-row">
                      <div className="data-row-info">
                        <div className="data-row-title">
                          <span>{entry.name}</span>
                          <Badge variant="info">风险 {fmtRisk(entry.risk_score)}</Badge>
                        </div>
                        <div className="data-row-meta">
                          最近结果：{entry.last_result || "-"} · 最近更新：{fmtTime(entry.updated_at)} · 连续掌握：{entry.mastery_streak ?? 0}
                        </div>
                        <div className="memory-chip-row">
                          {chipList(entry.weakness_links).map((item) => <span key={item} className="memory-chip">{item}</span>)}
                        </div>
                      </div>
                      <div className="data-row-actions">
                        <button
                          disabled={busyKey === `knowledge_point:${entry.name}`}
                          onClick={() => void onMarkMastered("knowledge_point", entry)}
                        >
                          标记已掌握
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          <div className="memory-layout-grid">
            <section className="card memory-section">
              <div className="memory-section-head">
                <h3>已掌握归档</h3>
                <Badge variant="success">已移出活跃记忆</Badge>
              </div>
              <div className="memory-archive-grid">
                <div>
                  <h4>知识点</h4>
                  {(overview.mastered_knowledge_points || []).length === 0 ? (
                    <div className="memory-empty-note">暂无已掌握知识点。</div>
                  ) : (
                    (overview.mastered_knowledge_points || []).map((entry) => (
                      <div key={`mkp-${entry.name}`} className="memory-archive-item">
                        <div className="memory-archive-title">{entry.name}</div>
                        <div className="memory-archive-meta">归档于 {fmtTime(entry.mastered_at || entry.updated_at)}</div>
                      </div>
                    ))
                  )}
                </div>
                <div>
                  <h4>薄弱点</h4>
                  {(overview.mastered_weaknesses || []).length === 0 ? (
                    <div className="memory-empty-note">暂无已掌握薄弱点。</div>
                  ) : (
                    (overview.mastered_weaknesses || []).map((entry) => (
                      <div key={`mw-${entry.name}`} className="memory-archive-item">
                        <div className="memory-archive-title">{entry.name}</div>
                        <div className="memory-archive-meta">归档于 {fmtTime(entry.mastered_at || entry.last_seen_at)}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </section>

            <section className="card memory-section">
              <div className="memory-section-head">
                <h3>最近学习事件</h3>
                <Badge variant="neutral">跨会话</Badge>
              </div>
              {recentEvents.length === 0 ? (
                <div className="memory-empty-note">还没有最近事件。</div>
              ) : (
                <div className="memory-event-list">
                  {recentEvents.map((event: any, index) => (
                    <div key={`event-${index}`} className="memory-event-item">
                      <div className="memory-event-title">
                        <BookOpen size={14} />
                        <span>{String(event?.source || "manual")}</span>
                        <Badge variant={String(event?.result || "").includes("pass") || String(event?.result || "") === "correct" ? "success" : String(event?.result || "") === "mastered" ? "info" : "warning"}>
                          {String(event?.result || "-")}
                        </Badge>
                      </div>
                      <div className="memory-event-meta">{fmtTime(String(event?.timestamp || ""))}</div>
                      {Array.isArray(event?.knowledge_points) && event.knowledge_points.length > 0 && (
                        <div className="memory-chip-row">
                          {event.knowledge_points.slice(0, 4).map((item: string) => <span key={item} className="memory-chip">{item}</span>)}
                        </div>
                      )}
                      {typeof event?.note === "string" && event.note.trim() && (
                        <div className="memory-event-note">{event.note}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          <div className="card memory-section">
            <div className="memory-section-head">
              <h3>记忆更新规则</h3>
              <Badge variant="neutral">当前策略</Badge>
            </div>
            <div className="memory-rules">
              <div>1. 新的错题、缺步、微测失败会增加对应薄弱点与知识点的风险。</div>
              <div>2. 连续的正确表现会降低风险，并累计连续掌握次数。</div>
              <div>3. 当知识点风险足够低、且连续掌握达到阈值时，会自动移入已掌握归档。</div>
              <div>4. 老师也可以手动点击“标记已掌握”，立即把该点移出活跃记忆。</div>
              <div>5. 如果后续再次出错，被归档的点会重新回到活跃记忆。</div>
            </div>
            <div className="memory-path-note">记忆文件：{overview.memory_path || "-"}</div>
          </div>
        </>
      )}
    </div>
  );
}
