# About Database Schema

## Schema Management

- PostgreSQL schema 由 Alembic migrations 管理，ORM model 不會在 app startup 自動呼叫 ``create_all()``。
- ``migrations/env.py`` 從 ``src.config.settings.DATABASE_URL`` 取得連線 URL，並使用 ``src.database.model.Base.metadata`` 支援 autogenerate。
- 每次修改 ``src/database/model.py`` 中會影響 schema 的 table、column、constraint、index 或 enum，都必須新增並檢查一份 migration。
- 不可只依賴 autogenerate 輸出；migration 必須確認既有資料的 backfill、nullable 切換、constraint 名稱及 downgrade 順序。

## Startup

- ``startup.sh`` 先執行：

```bash
uv run alembic upgrade head
```

- Migration 成功後才用 Uvicorn 啟動 app；migration 失敗時 shell 會直接停止，不會啟動服務。
- 資料庫方面，App lifespan 只初始化 singleton data：
    - ``config`` row
    - ``ctfmenu_message`` row
- App lifespan 不負責建立或修改 table schema。

## Existing Database Adoption

- Initial migration ``6e2b6a2f8874`` 支援採用 Alembic 導入前的 legacy schema。
- 若四個 legacy tables 全部存在且 column 集合完全相符，initial migration 不重新建表，Alembic 會接續後面的 revisions。
- 若只存在部分 legacy tables，或 column 集合不相符，migration 會停止，避免把不明 schema 當成可相容版本。
- 後續 migration ``56604a40e3a6`` 建立 ``ctfmenu_message`` table，並為既有 ``config`` row backfill ``ctfmenu_channel_id=-1`` 後改為 ``NOT NULL``。

## Commands

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Generate a candidate migration after changing models
uv run alembic revision --autogenerate -m "describe schema change"

# Inspect current and latest revisions
uv run alembic current
uv run alembic heads
```
