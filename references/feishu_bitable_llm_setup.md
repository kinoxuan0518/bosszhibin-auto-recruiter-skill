# 飞书多维表格接入说明（给 LLM 工具）

版本：v1.0（适配 bosszhibin-auto-recruiter v7.3+）

## 1. 目标

让任何同学都可以在自己的飞书租户中完成以下能力：
- 建立多维表格（候选人主档、交互日志、职位漏斗）
- 由 LLM 工具自动把招聘执行数据写入飞书
- 通过幂等键避免重复入库

## 2. 总体架构

- 数据源：技能执行产物（如 `session_output_*.json`、`execution_metrics`）
- 通信层：飞书开放平台 Bitable OpenAPI
- 目标表：
  - `candidate_master`（候选人主档）
  - `interaction_log`（每次动作记录）
  - `job_funnel_daily`（职位日统计）

## 3. 第一步：创建飞书应用

1. 打开 [飞书开放平台](https://open.feishu.cn/) 并创建企业自建应用。
2. 在“凭证与基础信息”获取 `App ID` 和 `App Secret`。
3. 在“权限管理”开通以下权限（最小必需）：
   - `bitable:app`
   - `bitable:app:readonly`
   - `bitable:table`
   - `bitable:table:readonly`
   - `bitable:record`
   - `bitable:record:readonly`
4. 发布应用到当前企业租户（未发布会导致接口无权限）。

## 4. 第二步：创建多维表格与字段

先创建一个多维表格（Bitable），记下 `app_token`。然后建立 3 张表：

### 4.1 candidate_master（候选人主档）

建议字段：
- `candidate_fingerprint`（文本，唯一键）
- `name`（文本）
- `job_id`（文本）
- `job_name`（文本）
- `school`（文本）
- `degree`（单选：本科/硕士/博士/其他）
- `experience_years`（数字）
- `company_background`（多行文本）
- `ai_skill_hit`（复选）
- `rule_label`（文本）
- `last_action_time`（日期时间）
- `status`（单选：contacted/skipped/rejected/passed）

### 4.2 interaction_log（交互日志）

建议字段：
- `interaction_fingerprint`（文本，唯一键）
- `candidate_fingerprint`（文本）
- `action_time`（日期时间）
- `action_type`（单选：greet/request_resume/reject/sync）
- `trigger_school`（单选：pass/fail）
- `trigger_ai_skill`（单选：pass/fail）
- `trigger_company`（单选：pass/fail）
- `trigger_experience`（单选：pass/fail）
- `summary`（多行文本）

### 4.3 job_funnel_daily（职位漏斗）

建议字段：
- `date`（日期）
- `job_id`（文本）
- `job_name`（文本）
- `tab_name`（文本）
- `seen_count`（数字）
- `contacted_count`（数字）
- `skipped_count`（数字）
- `pass_rate`（数字）
- `daily_quota_hit`（复选）
- `rate_limit_hits`（数字）
- `parse_quality_anomaly`（复选）

## 5. 第三步：记录 Token 与 Table ID

准备以下配置值：
- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_BITABLE_APP_TOKEN`
- `FEISHU_TABLE_CANDIDATE_MASTER`
- `FEISHU_TABLE_INTERACTION_LOG`
- `FEISHU_TABLE_JOB_FUNNEL_DAILY`

说明：
- 表 ID（table_id）可在多维表格 URL 或 OpenAPI 返回中获取。
- 不要把任何密钥写死到仓库。

## 6. 第四步：数据通信（API）

### 6.1 获取 tenant_access_token

```bash
curl -sS -X POST 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal' \
  -H 'Content-Type: application/json' \
  -d '{
    "app_id": "'$FEISHU_APP_ID'",
    "app_secret": "'$FEISHU_APP_SECRET'"
  }'
```

### 6.2 查询记录（幂等查重）

```bash
curl -sS 'https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records?page_size=100&filter=CurrentValue.[candidate_fingerprint]="xxx"' \
  -H "Authorization: Bearer $TENANT_ACCESS_TOKEN"
```

### 6.3 新增记录

```bash
curl -sS -X POST 'https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records' \
  -H "Authorization: Bearer $TENANT_ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "fields": {
      "candidate_fingerprint": "name|school|company|job_id",
      "name": "张三",
      "job_name": "AI算法工程师",
      "status": "contacted"
    }
  }'
```

### 6.4 更新记录

```bash
curl -sS -X PUT 'https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}' \
  -H "Authorization: Bearer $TENANT_ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "fields": {
      "last_action_time": "2026-03-04T12:00:00+08:00",
      "status": "passed"
    }
  }'
```

## 7. LLM 工具通信契约（推荐）

LLM 工具输入（示例）：

```json
{
  "run_id": "exec_20260304_001",
  "feishu": {
    "app_token": "${FEISHU_BITABLE_APP_TOKEN}",
    "tables": {
      "candidate_master": "${FEISHU_TABLE_CANDIDATE_MASTER}",
      "interaction_log": "${FEISHU_TABLE_INTERACTION_LOG}",
      "job_funnel_daily": "${FEISHU_TABLE_JOB_FUNNEL_DAILY}"
    }
  },
  "candidates": [
    {
      "candidate_fingerprint": "name|school|company|job_id",
      "name": "张三",
      "job_id": "job_001",
      "job_name": "AI算法工程师",
      "rule_label": "experienced_1_5y",
      "trigger_summary": {
        "school": "pass",
        "ai_skill": "pass",
        "company": "pass",
        "experience": "pass"
      },
      "action": "contacted",
      "action_time": "2026-03-04T12:00:00+08:00"
    }
  ],
  "job_funnel": [
    {
      "date": "2026-03-04",
      "job_id": "job_001",
      "job_name": "AI算法工程师",
      "tab_name": "推荐",
      "seen_count": 120,
      "contacted_count": 20,
      "skipped_count": 100,
      "pass_rate": 0.1667,
      "daily_quota_hit": false,
      "rate_limit_hits": 1,
      "parse_quality_anomaly": false
    }
  ]
}
```

LLM 工具输出（示例）：

```json
{
  "success": true,
  "run_id": "exec_20260304_001",
  "upserts": {
    "candidate_master": 20,
    "interaction_log": 20,
    "job_funnel_daily": 1
  },
  "failures": 0,
  "errors": []
}
```

## 8. 幂等与重试建议

- 先查重后写入：命中唯一键则更新，否则新增。
- 429/5xx 使用指数退避：1s、2s、4s（最多 3 次）。
- 连续失败阈值建议 20 条，超过则停止同步并返回错误摘要。
- 保证 `fail_open`：同步失败不影响招聘主流程执行。

## 9. 验收清单

- 能成功获取 `tenant_access_token`。
- 三张表都能新增 1 条测试记录。
- 相同 `candidate_fingerprint` 二次写入会触发更新而非重复新增。
- 触发 429 时能看到重试行为与最终结果。
- 技能总结中可看到飞书同步成功/失败统计。
