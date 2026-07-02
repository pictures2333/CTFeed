# About Embed
- 在大部分情況下
    - 一般的 Embed 使用 ``discord.Color.green()``
    - 代表成功的 Embed 使用 ``discord.Color.green()``
    - 代表失敗、錯誤的 Embed 使用 ``discord.Color.red()``

- 在 Config 中
    - Config overview 與 detail Embed 固定使用 ``discord.Color.green()``，不依設定值是否有效而改色
    - 讀取 Config 失敗時使用 ``discord.Color.red()``
    - Test 通過使用 ``discord.Color.green()``；Test 拋出錯誤時使用 ``discord.Color.red()``
