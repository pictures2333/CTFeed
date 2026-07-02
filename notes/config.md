# About Config
- Config 的權限驗證獨立於其他 module，只需要檢查用戶符合以下條件
    - 在指定的 Guild (id=GUILD_ID)
    - 有該 Guild 的 Administrator 權限
- Config 只有一個 Row（儲存 Guild (id=Guild_ID) 的設定）
- Config 有六個設定值 Column（不包含 ``id``）
    - announcement_channel_id: 發送公告的 channel 的 ID
    - ctfmenu_channel_id: 發送持久化 CTF menu 訊息的 channel 的 ID
    - ctf_channel_category_id: CTF 頻道的 Category
    - archive_category_id: 被封存的 CTF 頻道的 Category
    - pm_role_id: 代表 PM 的 Role 的 ID
    - member_role_id: 代表一般成員的 Role 的 ID
- Config 在資料庫不需要加鎖
    - announcement_channel_id 只是發送公告的地方
    - ctf_channel_category_id 跟 archive_category_id 只是頻道**創建**或**移動**到哪而已
    - pm_role_id 跟 member_role_id 只跟權限控管有關，當下是啥值就是啥值
    - ctfmenu_channel_id 只決定持久化 CTF menu 訊息發送到哪個 channel；訊息本身的同步由 ``ctfmenu_message`` table lock 處理
    - 這六個項目本身沒有狀態機，所以 **Config row 在資料庫不需要加鎖**
- Config 會 cache 在記憶體 (存在 settings)
- **存取這六個項目的 cache 需要加鎖**
- ``settings_lock`` 只保護單次 process-local cache 存取，不會包住整個 database update、cache update 與 ``post_func`` 流程；多個 concurrent Config update 之間沒有整體排序保證
- 基本上以 ``src.database.model.config_info`` 為準，``src.database.model.Config``、``src.config.Settings`` 跟進，三者需要同步
- 添加或刪除 Config 項目時需要處理以下地方
    - src.database.model - 添加 Column、註冊 Config 到 ``config_info``，設定 object type、test function 與 post function
    - src.config (Settings) - 添加``settings``(cache)成員、修改 ``settings_lock``註解
    - src.crud.config - 添加``create_or_update_config``參數
    - migrations/versions - 建立 Alembic migration；只修改 ORM model 不會更新既有 PostgreSQL schema
- Config update 的使用者 audit log 在 Discord 或 API 端記錄，因為 backend 沒有使用者資訊；backend 仍會記錄 database、cache 與 post hook 等操作錯誤
- Config update 流程：
    1. 驗證 key、型別及其指向的 Discord object
    2. 更新 database
    3. 更新 cache
    4. 執行該設定的 ``post_func``（若有）
    - ``post_func`` 失敗時設定已經儲存，不會 rollback database 或 cache
    - 更新 ``CTFMENU_CHANNEL_ID`` 後，``post_func`` 會在執行時 cache 指向的 channel 發送一則持久化 CTF menu 訊息
    - ``CTFMENU_CHANNEL_ID`` 的 ``post_func`` 不使用傳入的 ``value``，而是由 ``operate_message()`` 重新讀取當下 cache；若 Config update concurrent 執行，訊息目標以 post hook 執行時讀到的 cache 為準
- Config test 流程：
    - 一律先從 cache 取得完整設定，並確認目前值指向有效的 Discord object
    - 若該設定有 ``test_func``，再執行實際操作測試
    - ``ANNOUNCEMENT_CHANNEL_ID`` / ``CTFMENU_CHANNEL_ID``：發送並刪除測試訊息
    - ``CTF_CHANNEL_CATEGORY_ID``：建立測試 channel、修改 bot overwrite、發送訊息，最後刪除 channel
    - ``ARCHIVE_CATEGORY_ID``：在 CTF category 建立測試 channel，移動到 archive category、同步權限並發送訊息，最後刪除 channel
    - ``PM_ROLE_ID`` / ``MEMBER_ROLE_ID``：目前只驗證 Role object，沒有額外的 ``test_func``
- Discord config menu:
    - 總覽頁列出所有設定，顯示設定 key 與目前值
    - 使用單一 setting select 進入設定 detail，不做分組
    - detail 頁才顯示對應的 Discord object selector 進行更新
    - detail 頁提供 Test 按鈕執行該設定的測試，測試結果以另一則 Discord 訊息回覆
    - Discord channel selector 依 ``config_type`` 限制可選類型：``CHANNEL`` 只顯示 text channel，``CATEGORY`` 只顯示 category
    - 提供 Back / Refresh / Test，不提供 reset/clear
