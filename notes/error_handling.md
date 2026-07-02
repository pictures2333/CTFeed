# About Error Handling
When an unexpected operation error occurs, try to rollback in the ``except`` section and log the primary error at level ERROR.
Expected validation failures, test failures, and Config test cleanup failures may be returned directly without logging.
When locally handled rollback or non-test cleanup fails, log that secondary error at level CRITICAL without replacing the original error or return message.

Here's an example:
```python
try:
    # operations
    ...
except Exception as error:
    logger.error(f"fail to ...: {str(error)}")
    try:
        # rollback
        # ...
    except Exception as rollback_error:
        logger.critical(f"[rollback] fail to ...: {str(rollback_error)}")
finally:
    try:
        # operations
        # for example: unlock
        ...
    except Exception as cleanup_error:
        logger.critical(f"fail to ...: {str(cleanup_error)}")
```

API router 使用 ``HTTPException`` 表達已知的 client/server error。Backend 與 helper 可以使用內部 exception 或 error return；有包覆 backend 呼叫的 router 會保留既有 ``HTTPException``，並將其他已捕捉的 exception 轉成適當的 ``HTTPException``。未捕捉的非預期 exception 由 FastAPI 當作 500 error 處理。
