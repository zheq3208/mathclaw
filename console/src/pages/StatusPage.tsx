import {
  Activity,
  BadgeCheck,
  Bot,
  Brain,
  Cable,
  Clock3,
  Heart,
  Puzzle,
  Sparkles,
  Wrench,
} from "lucide-react";
import { Badge, PageHeader, StatCard } from "../components/ui";

const STATUS_TEXT = {
  title: "\u7cfb\u7edf\u72b6\u6001",
  description: "\u67e5\u770b MathClaw \u5f53\u524d\u90e8\u7f72\u6982\u89c8\u3001\u6559\u5b66\u4e3b\u94fe\u8def\u4e0e\u8fd0\u884c\u80fd\u529b\u5feb\u7167",
  badgePrimary: "\u6f14\u793a\u5feb\u7167",
  badgeSecondary: "\u6559\u5b66\u94fe\u8def\u5df2\u5c31\u7eea",
  heroTitle: "MathClaw \u5f53\u524d\u5904\u4e8e\u53ef\u76f4\u63a5\u6f14\u793a\u7684\u6570\u5b66\u5b66\u4e60\u52a9\u624b\u72b6\u6001",
  heroDescription:
    "\u6570\u5b66\u8bd5\u5377 OCR\u3001\u6c42\u89e3\u9a8c\u8bc1\u3001\u8584\u5f31\u70b9\u8bca\u65ad\u3001\u8bb2\u89e3\u8f85\u5bfc\u4e0e\u53d8\u5f0f\u751f\u6210\u94fe\u8def\u5df2\u7ecf\u4e32\u8054\uff0c\u63a7\u5236\u53f0\u53ef\u7528\u4e8e\u5b66\u751f\u6f14\u793a\u4e0e\u6559\u5e08\u914d\u7f6e\u3002",
  statApi: "API \u5065\u5eb7",
  statAgent: "\u4e3b AGENT",
  statRuntime: "\u8fd0\u884c\u72b6\u6001",
  statTools: "\u53ef\u7528\u5de5\u5177",
  statSkills: "\u6838\u5fc3\u6280\u80fd",
  statHeartbeat: "\u5fc3\u8df3\u76d1\u6d4b",
  statMode: "\u8fd0\u884c\u6a21\u5f0f",
  statUptime: "\u8fd0\u884c\u65f6\u957f",
  statMcp: "MCP \u5ba2\u6237\u7aef",
  statCron: "\u5b9a\u65f6\u4efb\u52a1",
  statMemory: "\u8bb0\u5fc6\u7a7a\u95f4",
  pipelineTitle: "\u6559\u5b66\u4e3b\u94fe\u8def",
  pipelineDescription: "\u5f53\u524d\u6f14\u793a\u73af\u5883\u5c06\u6309\u4ee5\u4e0b\u987a\u5e8f\u5b8c\u6210\u9898\u76ee\u5904\u7406\u4e0e\u5b66\u4e60\u8bb0\u5fc6\u66f4\u65b0\u3002",
  pipelineBadge: "5 \u6b65\u6d41\u7a0b",
} as const;

const STATUS_SNAPSHOT = {
  apiHealth: "\u7a33\u5b9a\u53ef\u7528",
  agentName: "MathAgent",
  runtime: "24x7 \u5f85\u547d",
  toolCount: 117,
  coreSkills: 7,
  heartbeat: "\u5b66\u4e60\u63d0\u9192\u5c31\u7eea",
  mode: "\u6559\u5b66\u6f14\u793a\u73af\u5883",
  uptime: "\u957f\u671f\u9a7b\u7559",
  cronJobs: 3,
  mcpClients: 3,
  memory: "GLOBAL \u8bb0\u5fc6\u5df2\u542f\u7528",
  channels: ["\u63a7\u5236\u53f0", "QQ \u673a\u5668\u4eba", "\u4f01\u4e1a\u5fae\u4fe1"],
  pipeline: [
    "\u8bd5\u5377 OCR",
    "\u6c42\u89e3\u4e0e\u9a8c\u8bc1",
    "\u8584\u5f31\u70b9\u8bca\u65ad",
    "\u5f15\u5bfc\u5f0f\u8bb2\u89e3",
    "\u53d8\u5f0f\u9898\u751f\u6210",
  ],
  highlights: [
    {
      title: "\u670d\u52a1\u5165\u53e3",
      value: "\u524d\u540e\u7aef\u8bbf\u95ee\u6b63\u5e38",
      detail: "\u63a7\u5236\u53f0\u3001API \u4e0e\u5bf9\u5916\u6620\u5c04\u5730\u5740\u5747\u53ef\u76f4\u63a5\u8bbf\u95ee\u3002",
    },
    {
      title: "\u80fd\u529b\u7f16\u6392",
      value: "7 \u4e2a\u6838\u5fc3\u6280\u80fd",
      detail: "\u56f4\u7ed5\u8bc6\u522b\u3001\u6c42\u89e3\u3001\u8bca\u65ad\u3001\u8bb2\u89e3\u3001\u8bb0\u5fc6\u4e0e\u8bad\u7ec3\u6784\u6210\u6570\u5b66\u5b66\u4e60\u4e3b\u94fe\u8def\u3002",
    },
    {
      title: "MCP \u63a5\u5165",
      value: "3 \u4e2a\u5ba2\u6237\u7aef",
      detail: "\u8054\u7f51\u641c\u7d22\u3001\u6d4f\u89c8\u5668\u6267\u884c\u4e0e\u6587\u4ef6\u7cfb\u7edf\u80fd\u529b\u5df2\u7ecf\u63a5\u5165\u3002",
    },
    {
      title: "\u4efb\u52a1\u7f16\u6392",
      value: "3 \u4e2a\u5b9a\u65f6\u4efb\u52a1",
      detail: "\u8bb0\u5fc6\u5237\u65b0\u3001\u6d88\u606f\u8f6e\u8be2\u4e0e\u7cfb\u7edf\u4fdd\u6d3b\u7ef4\u6301\u957f\u9a7b\u8fd0\u884c\u3002",
    },
  ],
} as const;

export default function StatusPage() {
  return (
    <div className="panel">
      <PageHeader
        title={STATUS_TEXT.title}
        description={STATUS_TEXT.description}
        actions={
          <div className="status-badge-row">
            <Badge variant="success">{STATUS_TEXT.badgePrimary}</Badge>
            <Badge variant="info">{STATUS_TEXT.badgeSecondary}</Badge>
          </div>
        }
      />

      <section className="card status-hero-card">
        <div>
          <div className="status-hero-eyebrow">DEPLOYMENT SNAPSHOT</div>
          <h3>{STATUS_TEXT.heroTitle}</h3>
          <p>{STATUS_TEXT.heroDescription}</p>
        </div>
        <div className="status-chip-grid">
          {STATUS_SNAPSHOT.channels.map((item) => (
            <span key={item} className="status-chip">{item}</span>
          ))}
          <span className="status-chip">{STATUS_SNAPSHOT.memory}</span>
          <span className="status-chip">{STATUS_SNAPSHOT.mode}</span>
        </div>
      </section>

      <div className="stat-row">
        <StatCard
          label={STATUS_TEXT.statApi}
          value={STATUS_SNAPSHOT.apiHealth}
          icon={<BadgeCheck size={20} />}
          variant="success"
        />
        <StatCard
          label={STATUS_TEXT.statAgent}
          value={STATUS_SNAPSHOT.agentName}
          icon={<Bot size={20} />}
          variant="brand"
        />
        <StatCard
          label={STATUS_TEXT.statRuntime}
          value={STATUS_SNAPSHOT.runtime}
          icon={<Activity size={20} />}
          variant="success"
        />
        <StatCard
          label={STATUS_TEXT.statTools}
          value={STATUS_SNAPSHOT.toolCount}
          icon={<Wrench size={20} />}
          variant="info"
        />
        <StatCard
          label={STATUS_TEXT.statSkills}
          value={STATUS_SNAPSHOT.coreSkills}
          icon={<Puzzle size={20} />}
          variant="warning"
        />
        <StatCard
          label={STATUS_TEXT.statHeartbeat}
          value={STATUS_SNAPSHOT.heartbeat}
          icon={<Heart size={20} />}
          variant="success"
          className="status-stat-card-wide"
          valueClassName="status-stat-value-nowrap"
        />
      </div>

      <div className="stat-row">
        <StatCard
          label={STATUS_TEXT.statMode}
          value={STATUS_SNAPSHOT.mode}
          icon={<Sparkles size={20} />}
          variant="brand"
        />
        <StatCard
          label={STATUS_TEXT.statUptime}
          value={STATUS_SNAPSHOT.uptime}
          icon={<Clock3 size={20} />}
          variant="info"
        />
        <StatCard
          label={STATUS_TEXT.statMcp}
          value={STATUS_SNAPSHOT.mcpClients}
          icon={<Cable size={20} />}
          variant="warning"
        />
        <StatCard
          label={STATUS_TEXT.statCron}
          value={STATUS_SNAPSHOT.cronJobs}
          icon={<RefreshIcon />}
          variant="warning"
        />
        <StatCard
          label={STATUS_TEXT.statMemory}
          value="GLOBAL"
          icon={<Brain size={20} />}
          variant="success"
        />
      </div>

      <div className="status-summary-grid">
        {STATUS_SNAPSHOT.highlights.map((item) => (
          <section key={item.title} className="card status-summary-card">
            <div className="status-summary-title">{item.title}</div>
            <div className="status-summary-value">{item.value}</div>
            <div className="status-summary-detail">{item.detail}</div>
          </section>
        ))}
      </div>

      <section className="card status-pipeline-card">
        <div className="status-pipeline-head">
          <div>
            <h3>{STATUS_TEXT.pipelineTitle}</h3>
            <p>{STATUS_TEXT.pipelineDescription}</p>
          </div>
          <Badge variant="warning">{STATUS_TEXT.pipelineBadge}</Badge>
        </div>
        <div className="status-pipeline-grid">
          {STATUS_SNAPSHOT.pipeline.map((step, index) => (
            <div key={step} className="status-pipeline-step">
              <span className="status-step-index">0{index + 1}</span>
              <span className="status-step-label">{step}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function RefreshIcon() {
  return <Clock3 size={20} />;
}
