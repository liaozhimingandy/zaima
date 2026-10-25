# 在吗 · API 文档（V1）

- Base URL：`http://<host>:8000`（本地开发默认 `http://127.0.0.1:8010`）
- 前缀：`/api`
- 交互式文档：`GET /docs`（Swagger UI）、`GET /openapi.json`
- 所有时间为 ISO 8601 UTC，带 `Z` 后缀；字段名为 camelCase

---

## 1. 统一响应

成功：

```json
{
  "code": "OK",
  "message": "success",
  "data": { },
  "requestId": "4b7b092480a2410b"
}
```

失败：

```json
{
  "code": "GUARDIAN_LIMIT",
  "message": "最多只能添加 3 位守护人",
  "data": null,
  "requestId": "951f16600b6144cd"
}
```

参数校验失败额外带 `details.errors`：

```json
{
  "code": "VALIDATION_ERROR",
  "message": "请求参数不合法",
  "data": null,
  "requestId": "...",
  "details": { "errors": [{ "loc": "body.email", "msg": "value is not a valid email address", "type": "value_error" }] }
}
```

### 错误码

| code | HTTP | 说明 |
| --- | --- | --- |
| `OK` | 200/201 | 成功 |
| `VALIDATION_ERROR` | 422 | 参数不合法 |
| `UNAUTHORIZED` | 401 | 凭证缺失、格式错误、无效或账户停用 |
| `NOT_FOUND` | 404 | 资源不存在或不属于当前账户 |
| `CONFLICT` | 409 | 一般冲突 |
| `ACCOUNT_EXISTS` | 409 | 该 `initKey` 已创建过账户 |
| `GUARDIAN_LIMIT` | 409 | 超过守护人数量上限 |
| `GUARDIAN_EMAIL_DUPLICATE` | 409 | 守护人邮箱重复 |
| `INTERNAL_ERROR` | 500 | 服务端未预期异常 |

### 请求追踪

每个响应都带 `X-Request-ID`（未传入则服务端生成）与 `X-Response-Time`（毫秒）。客户端可自定义 `X-Request-ID` 便于串联日志。

### 认证

除 `POST /api/account/init` 与 `GET /api/health` 外，所有接口都需要：

```
Authorization: Bearer zm_<9位数字publicId>.<secret>
```

凭证由服务端生成，**明文只返回一次**，服务端仅保存 `secret` 的 SHA-256。凭证无效统一返回 401，不区分具体原因。

格式：`zm_<9 位数字账户编号>.<secret>`，例如 `zm_481920735.xxxx`。
账户编号是 9 位纯数字（100000000–999999999），方便用户口述；它**不是**自增的，也不能用来推算其他账户。

---

## 2. 账户

### POST /api/account/init

创建匿名账户。`initKey` 由客户端生成并保存，用于幂等。

请求：

```json
{
  "initKey": "init_9f2c1d7a4b8e",
  "platform": "h5",
  "appVersion": "1.0.0",
  "timezone": "Asia/Shanghai"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| initKey | string | 是 | 8–64 字符，客户端本地持久化 |
| platform | string | 否 | `h5` / `app` / `mp-weixin` / `mp-alipay` |
| appVersion | string | 否 | 客户端版本 |
| timezone | string | 否 | IANA 时区，作为默认确认时区 |

响应 `201`：

```json
{
  "code": "OK",
  "message": "账户已创建",
  "data": {
    "accessToken": "zm_481920735.zO_YgahkLcDLS0Zhgp5riaSfN5pZJp90EhQ9yT3wH2o",
    "accountId": "481920735",
    "createdAt": "2026-10-22T22:20:42.997450Z",
    "platform": "h5",
    "isNew": true
  },
  "requestId": "..."
}
```

重复 `initKey` → `409 ACCOUNT_EXISTS`。客户端处理方式：若本地有凭证优先复用；确实丢失则生成新的 `initKey` 重试（会产生新账户）。

### GET /api/account/me

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "account": { "accountId": "481920735", "createdAt": "...", "platform": "h5", "appVersion": "1.0.0", "timezone": "Asia/Shanghai" },
    "setting": { "...": "同 GET /api/checkin/settings 的 data" }
  },
  "requestId": "..."
}
```

---

## 3. 确认

### GET /api/checkin/status

首页状态，**所有时间均由服务端计算**。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "stage": "REMINDING",
    "serverTime": "2026-03-02T04:00:00Z",
    "timezone": "Asia/Shanghai",
    "periodDays": 1,
    "checkinTime": "08:00",
    "lastCheckinAt": "2026-03-01T00:00:00Z",
    "nextCheckinAt": "2026-03-02T00:00:00Z",
    "alertAt": "2026-03-03T00:00:00Z",
    "secondsUntilDue": 0,
    "overdueSeconds": 14400,
    "nextReminderAt": "2026-03-02T12:00:00Z",
    "remindersPassed": 2,
    "reminders": [
      { "index": 1, "offsetMinutes": 30, "at": "2026-03-02T00:30:00Z", "localAt": "2026-03-02T08:30:00+08:00", "passed": true, "label": "第 1 次提醒" },
      { "index": 2, "offsetMinutes": 240, "at": "2026-03-02T04:00:00Z", "localAt": "2026-03-02T12:00:00+08:00", "passed": true, "label": "第 2 次提醒" },
      { "index": 3, "offsetMinutes": 720, "at": "2026-03-02T12:00:00Z", "localAt": "2026-03-02T20:00:00+08:00", "passed": false, "label": "第 3 次提醒" }
    ],
    "progressRatio": 0.1667,
    "guardianCount": 1,
    "hasOpenAlert": false,
    "openAlert": null,
    "stageHint": "还没收到你的确认，我们正在提醒你"
  },
  "requestId": "..."
}
```

`stage` 取值：`NORMAL` / `PENDING` / `REMINDING` / `ALERT`。

### POST /api/checkin

点一下「我在」。幂等。

请求：

```json
{ "requestId": "ci_8f2a1c9d4e", "clientTime": "2026-03-02T04:00:05+08:00", "note": null }
```

| 字段 | 说明 |
| --- | --- |
| requestId | 幂等键，8–64 字符；相同 requestId 重复提交返回同一条记录 |
| clientTime | 可选，仅作展示，不参与判定 |
| note | 可选，≤200 字符 |

响应：

```json
{
  "code": "OK",
  "message": "已记录你的确认",
  "data": {
    "record": {
      "id": 12,
      "checkedInAt": "2026-03-02T04:00:00Z",
      "clientTime": "2026-03-02T04:00:05+08:00",
      "dueAt": "2026-03-02T00:00:00Z",
      "source": "manual",
      "note": null
    },
    "duplicated": false,
    "resolvedAlert": true,
    "status": { "...": "同 GET /api/checkin/status" }
  },
  "requestId": "..."
}
```

- `duplicated=true` 表示命中幂等键，`record` 为原记录
- `resolvedAlert=true` 表示本次确认关闭了一条未处理的异常事件（并把待发邮件置为 `cancelled`）

### GET /api/checkin/history

查询参数：`limit`（1–100，默认 20）、`cursor`（上一页返回的 `nextCursor`）。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [ { "id": 12, "checkedInAt": "...", "clientTime": null, "dueAt": "...", "source": "manual", "note": null } ],
    "nextCursor": "eyJ0IjoiMjAyNi0wMy0wMlQwNDowMDowMCswMDowMCIsImlkIjoxMn0",
    "hasMore": true
  },
  "requestId": "..."
}
```

### GET /api/checkin/settings

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "periodDays": 1,
    "checkinTime": "08:00",
    "timezone": "Asia/Shanghai",
    "remindersEnabled": true,
    "alertOffsetMinutes": 1440,
    "reminders": [
      { "index": 1, "offsetMinutes": 30, "at": "...", "localAt": "...", "passed": false, "label": "第 1 次提醒" }
    ],
    "updatedAt": "2026-10-22T22:20:43Z"
  },
  "requestId": "..."
}
```

### PUT /api/checkin/settings

所有字段可选，只传要改的：

```json
{ "periodDays": 3, "checkinTime": "21:30", "timezone": "Asia/Tokyo", "remindersEnabled": true }
```

- `periodDays` 仅允许 `1, 2, 3, 7`（由 `ALLOWED_PERIOD_DAYS` 控制）
- `checkinTime` 必须 `HH:MM`（24 小时制）
- `timezone` 必须是有效 IANA 时区
- 非法值 → `422 VALIDATION_ERROR`

---

## 4. 守护人

### GET /api/guardians

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [ { "id": 1, "name": "妈妈", "email": "mom@example.com", "relation": "family", "createdAt": "..." } ],
    "maxCount": 3,
    "remaining": 2
  },
  "requestId": "..."
}
```

### POST /api/guardians

```json
{ "name": "妈妈", "email": "mom@example.com", "relation": "family" }
```

- `name`：1–32 字符，去首尾空格后不能为空
- `email`：合法邮箱，统一转小写；同账户内唯一
- `relation`：可选，`family` / `friend` / `partner` / `colleague` / `other`
- 超过 3 位 → `409 GUARDIAN_LIMIT`；邮箱重复 → `409 GUARDIAN_EMAIL_DUPLICATE`

响应 `201`，`data` 为单个守护人对象。

### PUT /api/guardians/{id}

字段可选；操作他人账户的守护人一律 `404 NOT_FOUND`（不泄露存在性）。

### DELETE /api/guardians/{id}

```json
{ "code": "OK", "message": "守护人已删除", "data": { "deleted": true, "id": 1 }, "requestId": "..." }
```

删除守护人不会删除历史通知记录（`notification_record.guardian_id` 置 NULL，收件邮箱快照保留）。

---

## 5. 系统

### GET /api/health

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "status": "ok",
    "version": "1.0.0",
    "env": "dev",
    "database": { "ok": true, "error": null },
    "emailAdapter": "mock",
    "schedulerEnabled": true,
    "serverTime": "2026-10-22T22:00:19.183098Z"
  },
  "requestId": "..."
}
```

数据库不可用时 `status=degraded`、`database.ok=false`，HTTP 仍为 200（供探针区分存活与就绪）。

---

## 6. 开发调试接口（仅非生产环境注册）

### POST /api/dev/scheduler/run

查询参数：`dispatch`（默认 `true`）。请求头 `X-Debug-Now` 可模拟当前时间。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "scan": { "scanned": 1, "alertsCreated": 1, "alertsExisting": 0, "notificationsCreated": 1, "skippedNoGuardian": 0, "errors": [] },
    "dispatch": { "picked": 1, "sent": 1, "simulated": 1, "failed": 0, "retryScheduled": 0, "cancelled": 0, "errors": [] },
    "now": "2026-03-03T00:00:00+00:00"
  },
  "requestId": "..."
}
```

### GET /api/dev/notifications

查看当前账户的邮件任务（排查发送与重试用）。

```json
{
  "data": {
    "adapter": "mock",
    "items": [
      { "id": 1, "alertId": 1, "guardianId": 1, "recipient": "mom@example.com", "status": "sent", "attempts": 1, "maxAttempts": 3, "simulated": true, "lastError": null, "sentAt": "...", "nextAttemptAt": "..." }
    ]
  }
}
```

`status`：`pending` / `sending` / `sent` / `failed` / `cancelled`。

### X-Debug-Now

`ALLOW_TIME_TRAVEL=true` 且 `APP_ENV != prod` 时生效；生产环境该请求头被忽略。

---

## 7. 邮件通知说明

- 只有 `ALERT` 阶段会给守护人发邮件；三次提醒只体现在客户端展示（页面内提醒）
- 生产环境必须配置 SMTP（`EMAIL_ADAPTER=smtp`），否则任务直接标记 `failed` 并写入 `last_error=邮件服务未正确配置：...`，**不会伪造成功**
- 发送失败按 `EMAIL_RETRY_BACKOFF_SECONDS × 尝试次数` 退避重试，超过 `EMAIL_MAX_ATTEMPTS` 置 `failed`
- 模拟发送的任务 `simulated=true`，与真实发送可区分
