import { useEffect, useMemo, useState } from "react";
import { Inbox, Layers3, Radio, RefreshCw } from "lucide-react";
import { getChannels } from "../api";
import type { ChannelItem } from "../types";
import { PageHeader, EmptyState, Badge, StatCard } from "../components/ui";
import { ChannelGlyph, IconBadge } from "../components/icons";

function describeChannel(item: ChannelItem): string {
  if (item.name === "console") {
    return "用于前端页面内查看消息、调试输出和实时结果。";
  }
  if (item.name === "qq") {
    return "用于把 MathClaw 的消息同步到 QQ 会话。";
  }
  if (item.name === "wecom") {
    return "用于把 MathClaw 的消息同步到企业微信。";
  }
  return `用于 ${item.type} 类型的外部消息收发。`;
}

export default function ChannelsPage() {
  const [channels, setChannels] = useState<ChannelItem[]>([]);
  const [loaded, setLoaded] = useState(false);

  async function onLoad() {
    setChannels(await getChannels());
    setLoaded(true);
  }

  useEffect(() => {
    void onLoad();
  }, []);

  const channelTypeCount = useMemo(
    () => new Set(channels.map((item) => item.type)).size,
    [channels],
  );
  const queueChannelCount = useMemo(
    () => channels.filter((item) => Boolean((item as ChannelItem & { has_queue?: boolean }).has_queue)).length,
    [channels],
  );

  return (
    <div className="panel page-stack">
      <PageHeader
        title="频道管理"
        description="查看当前接入的消息通道，并确认哪些入口正在接收或转发 MathClaw 的消息。"
        actions={
          <button onClick={onLoad}>
            <RefreshCw size={15} />
            刷新频道
          </button>
        }
      />

      {!loaded && channels.length === 0 && (
        <EmptyState
          icon={
            <IconBadge tone="blue">
              <Radio size={20} />
            </IconBadge>
          }
          title="点击刷新加载频道"
          description="查看所有已注册的通信频道信息"
          action={
            <button onClick={onLoad}>
              <RefreshCw size={15} />
              加载
            </button>
          }
        />
      )}

      {loaded && channels.length > 0 && (
        <>
          <div className="stat-row">
            <StatCard label="已接入频道" value={channels.length} icon={<Radio size={18} />} variant="brand" />
            <StatCard label="频道类型" value={channelTypeCount} icon={<Layers3 size={18} />} variant="info" />
            <StatCard label="支持队列" value={queueChannelCount} icon={<Inbox size={18} />} variant="success" />
          </div>

          <div className="card">
            <h3>接入说明</h3>
            <div className="helper-list helper-grid">
              {channels.map((item) => (
                <div key={`${item.name}:${item.type}`} className="helper-item">
                  <strong>{item.name}</strong>
                  <span>{describeChannel(item)}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      <div className="card-list animate-list">
        {channels.map((item: ChannelItem, idx: number) => {
          const hasQueue = Boolean((item as ChannelItem & { has_queue?: boolean }).has_queue);
          return (
            <div key={idx} className="data-row">
              <div className="data-row-info">
                <div className="data-row-title">
                  <ChannelGlyph channel={item.name} />
                  {item.name}
                </div>
                <div className="data-row-meta">{describeChannel(item)}</div>
              </div>
              <div className="data-row-actions">
                <Badge variant={hasQueue ? "success" : "neutral"}>
                  {hasQueue ? "支持队列" : "直接收发"}
                </Badge>
                <Badge variant="info">{item.type}</Badge>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
