import { useEffect, useState } from "react";
import { Puzzle, RefreshCw } from "lucide-react";
import {
  listSkills,
  listActiveSkills,
  enableSkill,
  disableSkill,
} from "../api";
import type { SkillItem } from "../types";
import { PageHeader, EmptyState, Toggle } from "../components/ui";

const SKILL_LABELS: Record<string, string> = {
  browser_visible: "Browser",
  cron: "Timer",
  difficulty_calibrator: "Level",
  dingtalk_channel: "DingTalk",
  dingtalk_channel_connect: "DingTalk",
  docx: "DOCX",
  experiment_tracker: "Tracker",
  figure_generator: "Figure",
  file_reader: "Reader",
  formula_render_check: "Formula",
  guiding_users: "Guide",
  himalaya: "Himalaya",
  hint_ladder_policy: "Hints",
  information_architecture: "IA",
  knowledge_extractor: "Extract",
  knowledge_synthesizer: "Synth",
  mastery_updater: "Mastery",
  math_solver_verifier: "Verifier",
  micro_quiz: "Quiz",
  multimodal_analysis: "Vision",
  news: "News",
  ocr_document_processor: "OCR",
  pdf: "PDF",
  pptx: "PPT",
  problem_json_normalizer: "JSON",
  remember: "Memory",
  research_notes: "Notes",
  review_scheduler: "Review",
  socratic_math_tutor: "Socratic",
  sympy: "SymPy",
  variant_generator: "Variants",
  vision_transcribe: "Vision OCR",
  weakness_diagnoser: "Diagnose",
  xlsx: "XLSX",
};

const SKILL_DESCRIPTIONS: Record<string, string> = {
  browser_visible: "Open a real browser window.",
  cron: "Run scheduled jobs automatically.",
  difficulty_calibrator: "Estimate problem difficulty.",
  dingtalk_channel: "Connect and publish the DingTalk bot.",
  dingtalk_channel_connect: "Connect and publish the DingTalk bot.",
  docx: "Read and edit Word files.",
  experiment_tracker: "Track experiment logs and results.",
  figure_generator: "Create charts and figures.",
  file_reader: "Read local text files.",
  formula_render_check: "Check formula parsing issues.",
  guiding_users: "Guide the student step by step.",
  himalaya: "Use Himalaya tools.",
  hint_ladder_policy: "Control hint depth.",
  information_architecture: "Organize problem structure.",
  knowledge_extractor: "Extract knowledge points.",
  knowledge_synthesizer: "Summarize key knowledge.",
  mastery_updater: "Update mastery progress.",
  math_solver_verifier: "Verify math solutions.",
  micro_quiz: "Generate quick review quizzes.",
  multimodal_analysis: "Read image and mixed inputs.",
  news: "Track news updates.",
  ocr_document_processor: "OCR docs and screenshots.",
  pdf: "Read PDF files.",
  pptx: "Read and edit slides.",
  problem_json_normalizer: "Normalize to problem JSON.",
  remember: "Save student memory.",
  research_notes: "Write structured notes.",
  review_scheduler: "Schedule spaced review.",
  socratic_math_tutor: "Teach with guided questions.",
  sympy: "Check algebra with SymPy.",
  variant_generator: "Create easier or harder variants.",
  vision_transcribe: "OCR problem images.",
  weakness_diagnoser: "Find weak points.",
  xlsx: "Read and edit Excel files.",
};

function getSkillId(skill: SkillItem, fallback: string) {
  const pathName = skill.path?.split("/").filter(Boolean).pop();
  return pathName || fallback;
}

function getSkillLabel(skillId: string, fallback: string) {
  return SKILL_LABELS[skillId] || SKILL_LABELS[fallback] || fallback;
}

function getSkillDescription(skillId: string, fallback: string, rawName: string) {
  return (
    SKILL_DESCRIPTIONS[skillId]
    || SKILL_DESCRIPTIONS[rawName]
    || fallback
  );
}

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [active, setActive] = useState<string[]>([]);
  const [loaded, setLoaded] = useState(false);

  async function onLoad() {
    setSkills(await listSkills());
    setActive(await listActiveSkills());
    setLoaded(true);
  }

  useEffect(() => {
    void onLoad();
  }, []);

  async function onToggle(skillId: string, nextChecked: boolean) {
    if (nextChecked) {
      await enableSkill(skillId);
    } else {
      await disableSkill(skillId);
    }
    await onLoad();
  }

  return (
    <div className="panel">
      <PageHeader
        title="技能管理"
        description="启用或禁用 Agent 技能（同时影响聊天与 task_type=agent 的定时任务）"
        actions={
          <button onClick={onLoad}>
            <RefreshCw size={15} />
            刷新技能
          </button>
        }
      />

      {!loaded && skills.length === 0 && (
        <EmptyState
          icon={<Puzzle size={28} />}
          title="加载技能列表"
          description="管理 Agent 可用的技能和能力"
          action={
            <button onClick={onLoad}>
              <RefreshCw size={15} />
              加载
            </button>
          }
        />
      )}

      <div className="card-list animate-list">
        {skills.map((skill: SkillItem, idx: number) => {
          const rawName = skill.name || `skill-${idx}`;
          const skillId = getSkillId(skill, rawName);
          const displayName = getSkillLabel(skillId, rawName);
          const description = getSkillDescription(
            skillId,
            skill.description || "",
            rawName,
          );
          const isActive = active.includes(skillId) || skill.enabled === true;
          const title = rawName === skillId ? skillId : `${skillId} · ${rawName}`;
          return (
            <div key={skillId} className="data-row">
              <div className="data-row-info">
                <div className="data-row-title">
                  <Puzzle
                    size={14}
                    style={{ marginRight: 6, verticalAlign: "middle" }}
                  />
                  <span className="skill-name" title={title}>
                    {displayName}
                  </span>
                  <span
                    className={`skill-state-pill ${isActive ? "is-on" : "is-off"}`}
                  >
                    {isActive ? "已启动" : "未启动"}
                  </span>
                </div>
                {description && (
                  <div className="data-row-meta">{description}</div>
                )}
              </div>
              <div className="data-row-actions">
                <Toggle
                  className="skills-toggle"
                  checked={isActive}
                  onChange={(nextChecked) => onToggle(skillId, nextChecked)}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
