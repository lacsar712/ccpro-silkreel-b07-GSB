# SilkReel-01 · 江口缫丝坞

缫丝盆环状作业台。登录后看到的是沿汤池围成一圈的盆位，点盆登记汤温并改状态——不是侧栏双列表 CRUD。

## 技术栈

| 层 | 技术 |
| --- | --- |
| Web API | Quart（异步 Flask 族）· Hypercorn |
| 结构 | `repositories.py` 仓储 + `services.py` 门槛，路由不直接拼 SQL |
| 数据 | SQLAlchemy 2 async · asyncpg · PostgreSQL 15 |
| 前端 | Preact 10 · Vite |
| 部署 | Docker Compose |

## 路径与端口

- 前端：http://localhost:4760
- API：http://localhost:8760
- PostgreSQL：localhost:6160

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 管理员 |
| `worker` | `123456` | 缫丝工 |

## 业务规则

盆状态不可标成「已缫完」，除非该盆**最近一条**汤温记录落在 **38～42℃**。规则在 `backend/app/services.py`。

## 已缫完次数台

顶栏在「环盆作业台」之外挂了「已缫完次数台」专页：只统计**今天（服务器自然日）成功把盆态改成已缫完的次数**，页面只读，不能改态、不能登记汤温。

- 每次成功改态与计数流水（`reeled_events` 表）在**同一事务**落库，次数台实时读这张流水，不是盆面历史已缫完颗数。
- 改态用原子条件 UPDATE（`WHERE status != 'reeled'`）：两名工交叉标同一口缫丝中盆，只有一笔成功，另一笔收到 `409`，次数只加 1。

## 快速启动

```bash
cd SilkReel/SilkReel-01
docker compose up --build
```
