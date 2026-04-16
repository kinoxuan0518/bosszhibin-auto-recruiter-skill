# bosszhibin-auto-recruiter-skill

Boss直聘自动招聘技能（v7.3，已脱敏，支持飞书多维表格同步协议）。

## 当前版本

- Skill: `v7.3.4-ui-hardening-desensitized`
- 主文件: `SKILL.md`
- 结构: 两层

1. 执行必需：`SKILL.md`
2. 按需参考：`references/` 模板文件与集成说明

## 目录结构

```text
.
├── SKILL.md
├── scripts/
│   └── feishu_candidate_sync.py
├── agents/
│   └── openai.yaml
└── references/
    ├── execution_metrics_template.json
    ├── auto_reflection_report_template.md
    ├── evolution_history_template.json
    └── feishu_bitable_llm_setup.md
```

## 使用方式

1. 把本仓库内容安装到 Codex 全局技能目录（或直接引用）。
2. 启动会话时触发该技能。
3. 执行时优先读取 `SKILL.md`，仅在需要模板时再读取 `references/`。

## 设计要点

- 运行协议内聚在单文件：终止条件、频率退避、幂等、人工中断、流程模式。
- 职位规则走缓存分层：`global_rule_defaults + jobs[].rule_overrides`。
- 模板与结构定义外置：减少每轮执行前的读取开销。
- 新增 UI hardening：筛选面板常驻检测、职位归一化匹配、点击拦截回退、补池轮收口逻辑。
- 新增会话所有权约束：单窗口独占、人工接管前强停、恢复前只读校验。
- 新增飞书同步协议：支持把候选人主档、交互日志、职位漏斗同步到飞书多维表格。
- 所有路径与凭证改为通用变量（如 `${BOSSZHIBIN_CACHE_DIR}`、`FEISHU_*`），不包含私有环境信息。

## 飞书接入

- LLM 工具接入说明：`references/feishu_bitable_llm_setup.md`
- 通用同步脚本：`scripts/feishu_candidate_sync.py`
- 该说明包含：
  - 如何创建自己的飞书应用与多维表格
  - 必要权限与字段设计
  - 幂等写入与重试策略
  - API 调用示例与输入输出通信契约

### 快速使用（脚本）

1. 准备环境变量（`FEISHU_*`）。
2. 干跑校验映射：
```bash
python3 scripts/feishu_candidate_sync.py --dry-run /path/to/session_output.json
```
3. 正式同步：
```bash
python3 scripts/feishu_candidate_sync.py /path/to/session_output.json
```
4. 批量同步多个文件：
```bash
python3 scripts/feishu_candidate_sync.py file1.json file2.json file3.json
```

## 兼容说明

- 历史版本文档（v7.1）已从主分支移除。
- 执行指标模板已增加飞书同步指标字段，可用于复盘告警。
