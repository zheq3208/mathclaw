import { useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, Clock3, Heart, RefreshCw } from "lucide-react";
import { getHeartbeat } from "../api";
import { PageHeader, EmptyState, StatCard, Badge } from "../components/ui";

type HeartbeatInfo = {
  enabled?: boolean;
  last_heartbeat?: number;
  age_seconds?: number;
  healthy?: boolean;
  [key: string]: unknown;
};

function formatHeartbeatTime(ts?: number): string {
  if (!ts) return "暂无记录";
  const date = new Date(ts * 1000);
  if (Number.isNaN(date.getTime())) return "暂无记录";
  return date.toLocaleString("zh-CN", { hour12: false });
}

function formatAge(seconds?: number): string {
  if (typeof seconds !== "number" || Number.isNaN(seconds)) return "未知";
  if (seconds < 60) return `${Math.round(seconds)} 秒`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)} 小时`;
  return `${(seconds / 86400).toFixed(1)} 天`;
}

function resolveHeartbeatState(heartbeat: HeartbeatInfo | null) {
  if (!heartbeat) return { label: "未加载", variant: "neutral" as const };
  if (!heartbeat.enabled) return { label: "已关闭", variant: "neutral" as const };
  if (heartbeat.healthy) return { label: "正常", variant: "success" as const };
  return { label: "超时", variant: "warning" as const };
}

export default function HeartbeatPage() {
  const [heartbeat, setHeartbeat] = useState<HeartbeatInfo | null>(null);
  const [loaded, setLoaded] = useState(false);

  async function onLoad() {
    setHeartbeat(await getHeartbeat());
    setLoaded(true);
  }

  useEffect(() => {
    void onLoad();
  }, []);

  const heartbeatState = useMemo(() => resolveHeartbeatState(heartbeat), [heartbeat]);

  return (
    <div className="panel page-stack">
      <PageHeader
        title="心跳检测"
        description="查看心跳任务是否正常运行，以及最近一次心跳距离现在已经过去多久。"
        actions={
          <button onClick={onLoad}>
            <RefreshCw size={15} />
            刷新心跳
          </button>
        }
      />

      {!loaded && !heartbeat && (
        <EmptyState
          icon={<Heart size={28} />}
          title="检测系统心跳"
          description="点击刷新查看各组件的实时状态"
          action={
            <button onClick={onLoad}>
              <RefreshCw size={15} />
              加载
            </button>
          }
        />
      )}

      {heartbeat && (
        <>
          <div className="stat-row">
            <StatCard
              label="心跳状态"
              value={heartbeatState.label}
              icon={<Heart size={18} />}
              variant={heartbeat.healthy ? "success" : "warning"}
            />
            <StatCard
              label="监控开关"
              value={heartbeat.enabled ? "已启用" : "已关闭"}
              icon={<Activity size={18} />}
              variant={heartbeat.enabled ? "brand" : "info"}
            />
            <StatCard
              label="最近心跳"
              value={formatHeartbeatTime(heartbeat.last_heartbeat)}
              icon={<Clock3 size={18} />}
              variant="info"
            />
            <StatCard
              label="距今时长"
              value={formatAge(heartbeat.age_seconds)}
              icon={<AlertTriangle size={18} />}
              variant={heartbeat.healthy ? "success" : "warning"}
            />
          </div>

          <div className="heartbeat-grid">
            <div className="card">
              <h3>运行概览</h3>
              <div className="kv-grid">
                <div className="kv-item">
                  <div className="kv-label">当前状态</div>
                  <div className="kv-value">
                    <Badge variant={heartbeatState.variant}>{heartbeatState.label}</Badge>
                  </div>
                </div>
                <div className="kv-item">
                  <div className="kv-label">任务开关</div>
                  <div className="kv-value">{heartbeat.enabled ? "心跳任务已启用" : "心跳任务已关闭"}</div>
                </div>
                <div className="kv-item">
                  <div className="kv-label">最近心跳时间</div>
                  <div className="kv-value">{formatHeartbeatTime(heartbeat.last_heartbeat)}</div>
                </div>
                <div className="kv-item">
                  <div className="kv-label">当前延迟</div>
                  <div className="kv-value">{formatAge(heartbeat.age_seconds)}</div>
                </div>
              </div>
            </div>

            <div className="card">
              <h3>维护建议</h3>
              <div className="helper-list">
                <div className="helper-item">
                  <strong>状态判断</strong>
                  <span>
                    {heartbeat.enabled
                      ? heartbeat.healthy
                        ? "最近一次心跳仍在正常窗口内，当前不需要额外处理。"
                        : "最近一次心跳已经过久，建议检查后台任务是否仍在运行。"
                      : "当前未启用心跳任务，页面只会显示历史状态。"}
                  </span>
                </div>
                <div className="helper-item">
                  <strong>排查方向</strong>
                  <span>优先检查服务进程、定时任务注册状态，以及心跳文件是否仍在更新。</span>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <h3>原始数据</h3>
            <pre className="pre">{JSON.stringify(heartbeat, null, 2)}</pre>
          </div>
        </>
      )}
    </div>
  );
}
