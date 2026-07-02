# About Persistent CTF Menu Message

## Data

- ``CTFMENU_CHANNEL_ID`` 決定持久化訊息所在的 Discord text channel。
- ``ctfmenu_message`` table 只有一個 row（``id=1``）：
    - ``message_id``：目前有效的持久化訊息 ID，``-1`` 代表尚未建立
    - ``extra_message``：顯示在 Embed description 的自訂文字
- App lifespan 會確保 singleton row 存在；table schema 由 Alembic migration 管理。

## Message Operations

- ``src.backend.ctfmenu_message.operate_message()`` 支援三種 mode：
    - ``send``：一律發送新訊息，並以新 ``message_id`` 覆蓋 database
    - ``recover``：嘗試取得目前訊息；訊息不存在或 Discord 拒絕讀取訊息時重新發送
    - ``edit``：取得目前訊息並更新 Embed description；訊息不存在或 Discord 拒絕讀取時不進行更新
- 操作前會讀取 cache 中的 ``CTFMENU_CHANNEL_ID``；值為 ``-1``、無法存取 channel、channel 不存在或不是 text channel 時失敗。
- 整個 database transaction 會對 ``ctfmenu_message`` 使用 ``LOCK TABLE ... IN EXCLUSIVE MODE``，包含 Discord fetch/send/edit，刻意序列化跨 process 的訊息操作以避免重複建立或覆寫。
- ``Set description`` 先在一個有 table lock 的 transaction 更新 ``extra_message`` 並 commit，再由 ``operate_message(edit)`` 開啟另一個有 table lock 的 transaction 編輯 Discord 訊息；兩段操作不是同一個 atomic transaction。
- 更新 ``CTFMENU_CHANNEL_ID`` 的 Config post hook 使用 ``send`` mode：
    - post hook 執行時 cache 指向的 channel 會收到新訊息
    - 舊訊息不會自動刪除
    - database 只承認最新的 ``message_id``，所以通過權限檢查的使用者點擊舊訊息按鈕時會回覆 ``Invalid CTFMenu message``

## Interaction

- 持久化訊息有兩個按鈕：
    - ``/ctfmenu``：建立 owner 為點擊者的 ephemeral ``EventMenu``
    - ``Set description``：開啟 modal，更新 ``extra_message`` 後編輯目前訊息
- 兩個按鈕都使用一般 CTFeed user 權限檢查及自動註冊，不限定 Administrator。
- Component callback 會在一個有 table lock 的 transaction 中確認 interaction message 是當下 database 記錄的最新 ``message_id``，但 transaction 會在執行後續 action 前結束。
- ``Set description`` modal submit 不會重新檢查開啟 modal 時的來源 ``message_id``；提交時會更新 database 的 ``extra_message``，再嘗試編輯當下 database 記錄的目前訊息。

## Recovery

- ``src.bgtask.recover_ctfmenu_message._recover_ctfmenu_message()`` 由共用 background loop 呼叫。
- 執行頻率與其他 background tasks 相同，使用 ``CHECK_INTERVAL_MINUTES``。
- Recovery 失敗只記錄 error，不能中止其餘服務。
