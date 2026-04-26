# `_patch` 原始笔记暂存区

`_patch` 用于暂存批量上传的同一专题原始笔记。这里的内容默认不是正式博客文章，也不直接发布。

推荐用法：

1. 每个专题建立一个子目录，例如 `_patch/agent-notes/`；
2. 在专题目录中维护 `00-index.md`，记录资料列表、处理状态、目标分类和预期输出文章；
3. Agent 先在 `_patch/<topic>/` 内完成合并、拆分、脱敏、校对和结构整理；
4. 达到发布标准后，再移动到 `_posts/<category>/YYYY-MM-DD-title.md`；
5. 已发布且无保留价值的重复稿应及时清理。

注意事项：

- 不要在这里提交密钥、账号、token、cookie 或未经脱敏的内部信息；
- `_patch` 已在 Jekyll 配置中排除，不作为正式站点内容；
- `_patch` 中的 Markdown 可以没有 Front Matter，但移入 `_posts` 前必须补齐。
