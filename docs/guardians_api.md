# 监护关系 API（统一版）

本项目将“监护人/被监护人”的申请与审批流程统一为 3 个 API，通过参数区分发起方身份与记录箱（收件箱/发件箱）。

## 鉴权
以下接口均需要 JWT Bearer：
- `Authorization: Bearer <access_token>`

## 1) 发起申请（统一）
**POST** `\/guardians\/requests\/apply`

### Body
- `mode`: `"monitor"` | `"ward"`
  - `"monitor"`：当前用户以**监护人**身份发起申请，目标用户为**被监护人**
  - `"ward"`：当前用户以**被监护人**身份发起申请，目标用户为**监护人**
- `target_username`: 目标用户用户名
- `name`: 关系中显示的姓名
- `relationship`: 关系描述（可选）

### 示例

```json
{
  "mode": "monitor",
  "target_username": "alice",
  "name": "张建国",
  "relationship": "父子"
}
```

## 2) 获取申请记录（统一）
**GET** `\/guardians\/requests?box=incoming|outgoing|all&status=pending|accepted|rejected|all`

### Query
- `box`
  - `incoming`：需要**当前用户处理**的申请
  - `outgoing`：**当前用户发起**的申请
  - `all`：两者合并
- `status`
  - `pending` / `accepted` / `rejected` / `all`

## 3) 批准或拒绝（统一）
**POST** `\/guardians\/requests\/{request_id}\/decision`

### Body
- `decision`: `"accept"` | `"reject"`

### 规则
- 只能由“被申请的一方”处理：
  - 若申请由监护人发起（`requester_id == monitor_id`），则被监护人审批
  - 若申请由被监护人发起（`requester_id == ward_id`），则监护人审批
- 仅 `pending` 状态可处理

## 关系列表（统一）
**GET** `\/guardians\/relations?role=monitor|ward`

### Query
- `role=monitor`：查看“我作为监护人”的关系列表
- `role=ward`：查看“我作为被监护人”的关系列表

### `name` 字段来源说明
- 关系表 `guardians` 不再存储 `name`
- `GET /guardians/relations` 返回的 `name` 来自该关系最近一次 `accepted` 的申请记录（`guardian_link_requests.name`）

