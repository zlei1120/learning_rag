# 数据库排错

## 一、先确认当前依赖关系

当前后端并不是维护自己的独立内容库，而是直接读取：

- `geminiBlog` 的 PostgreSQL `Post` 表

所以数据库问题通常分三类：

1. 连不上 PostgreSQL
2. 能连上，但缺 `pgvector` 或 schema
3. 能连上，也有表，但读不到文章或写不进 RAG 表

## 二、最常见问题排查顺序

### 1. 先看健康检查

```powershell
Invoke-RestMethod -Method GET -Uri http://127.0.0.1:8000/health
```

关注：

- `database`
- `status`

如果返回：

- `database=unavailable`

优先检查数据库连接串和网络可达性。

如果你刚改过 `.env`，要先重启已经运行中的后端服务，再重新调用健康检查。

### 2. 检查 `DATABASE_URL`

确认 `.env` 中的：

- 主机
- 端口
- 数据库名
- 用户名
- 密码

和实际部署一致。

本地通过 SSH 隧道连接云上 PostgreSQL 时，要特别注意端口含义。比如：

```powershell
ssh -N -L 5433:127.0.0.1:5432 ubuntu@服务器地址
```

这表示：

- 本机应用连接 `127.0.0.1:5433`
- SSH 再把流量转发到云服务器上的 `127.0.0.1:5432`

所以 `.env` 应写成本机监听端口：

```env
DATABASE_URL=postgresql+psycopg://blog:真实密码@127.0.0.1:5433/blog
```

如果 `5433` 端口可达，但日志里出现：

- `password authentication failed for user "blog"`

说明隧道和 PostgreSQL 都已经通了，接下来要检查的是远端数据库用户、密码或目标库名。

### 3. 检查博客真源表是否存在

当前代码默认读取：

- `"Post"`

如果博客库结构变化、schema 变化，当前仓储查询会直接受影响。

### 4. 检查 `pgvector`

连接数据库后执行：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

如果报错类似：

- `type "vector" does not exist`
- `extension "vector" is not available`

说明当前 PostgreSQL 实例没有安装 `pgvector`。

你这个项目当前还有一个很关键的上下文：

- `E:\code\geminiBlog\docker-compose.yml` 新版本已经切到 `pgvector/pgvector:pg16`

这意味着：

- 新起的空库可以直接带上 `pgvector`
- 但旧的云上实例、旧的 Docker volume，或者历史上用 `postgres:16` 起过的库，并不会因为你改了 compose 就自动补上扩展
- FastAPI 问答后端即使连上同一个博客库，也会因为缺少 `vector` 类型而无法完成 RAG 表初始化

可选处理方式：

1. 把数据库实例改成带 `pgvector` 的镜像或发行版
2. 如果是 Docker 自建库，进入库里手动执行 `CREATE EXTENSION IF NOT EXISTS vector;`
3. 如果是系统级 PostgreSQL，再为现有实例手动安装 `pgvector`
4. 改为使用一个已经支持 `pgvector` 的托管 PostgreSQL 实例

如果没开 `pgvector`，向量相关查询会退回关键词兜底，但正式效果会明显下降；而首次初始化 `rag` 相关表时也可能直接失败。

### 5. 检查 RAG schema

默认 schema：

- `rag`

如果你修改了 `RAG_SCHEMA`，要确认迁移和运行时写入都对准同一个 schema。

## 三、迁移相关问题

### 建议命令

```powershell
uv run alembic upgrade head
```

### 只想看 SQL

```powershell
uv run alembic upgrade head --sql
```

### 常见故障

- 数据库连接成功，但没有权限创建 schema
- 旧库里缺少会话表迁移
- 本地 `.env` 和实际执行 Alembic 的环境变量不一致
- `DATABASE_URL` 中的密码包含 `@` 等特殊字符，URL 编码后出现 `%40`，如果你在历史脚本或自定义 Alembic 配置里没做转义，仍可能直接报插值错误

## 四、能读取文章但同步失败

优先检查：

1. `rag_ingest_jobs.error_message`
2. 图片地址是否可访问
3. 百炼 Key 是否配置
4. 图片 OCR / caption 是否超时

注意：

- 没有百炼 Key 时，同步链路仍可通过本地回退继续执行
- 但如果图片地址本身不可访问，图片理解仍可能失败

## 五、能问答但效果很差

这通常不是“数据库连不上”，而是以下问题：

- 文章没完成同步
- 向量未正确写入
- 查询退回到了关键词检索
- 图片特征缺失

建议依次核查：

1. `rag_documents`
2. `rag_chunks`
3. `rag_embeddings`
4. `rag_images`
5. `rag_image_features`

## 六、本地和云上环境不一致

你当前场景里常见的坑是：

- 本地 `docker compose` 用的是一个库
- 云上服务连的是另一个库
- 博客后台写入的是第三个环境

建议最少做这几个确认：

1. 后端 `.env` 的 `DATABASE_URL` 指向哪里
2. `geminiBlog` 当前后台连接的是哪里
3. 你实际验证问答时同步的数据来自哪里

只要这三者不是同一环境，就很容易出现“明明刚改了文章，但问答看不到”的错觉。
