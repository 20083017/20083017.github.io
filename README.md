# BY Blog

这是 `20083017.github.io` 的博客仓库。正式发布的文章放在 `_posts/<category>/`，批量上传的原始笔记先放在 `_patch/` 暂存，整理达标后再移动到 `_posts/` 发布。

## 博客文档上传发布流程

### 1. 批量上传原始笔记

同一专题、同一类型或同一批来源的原始笔记，不要直接提交到 `_posts/`。先使用 `_patch/` 作为暂存区：

```bash
./scripts/upload-patch-notes.sh <topic-name> <file-or-directory> [...]
```

示例：

```bash
./scripts/upload-patch-notes.sh agent-notes ~/notes/agent/*.md
./scripts/upload-patch-notes.sh devops-checklist ~/notes/devops/
```

脚本会：

- 创建 `_patch/<topic-name>/`；
- 复制传入的文件或目录内容；
- 自动维护 `_patch/<topic-name>/00-index.md`，记录待处理资料清单；
- 避免覆盖同名文件。

### 2. 提交 `_patch` 暂存内容

检查暂存区内容后提交：

```bash
git status
git add _patch/
git commit -m "Upload raw notes for <topic-name>"
git push
```

`_patch` 已从 Jekyll 构建中排除，里面的原始资料不会作为正式站点内容发布。

### 3. 触发 Agent 优化文档

当 `_patch/**` 内容被推送到 GitHub 后，`.github/workflows/blog-patch-agent-request.yml` 会自动创建一个处理请求 issue，并尝试把 issue 分配给 Copilot agent。

Agent 的目标是：

1. 阅读 `_patch/<topic-name>/00-index.md` 和原始笔记；
2. 合并重复内容，拆分过长主题；
3. 补齐背景、步骤、风险、FAQ 和发布检查项；
4. 脱敏并移除不适合发布的内容；
5. 生成符合本站规范的 `_posts/<category>/YYYY-MM-DD-title.md`；
6. 通过 PR 提交优化后的发布稿。

如果仓库没有开启 Copilot coding agent，或者默认 assignee 不可用，workflow 会保留 issue，后续可以手动分配给可用的 Agent。

### 4. 审核并发布

收到 Agent PR 后，重点检查：

- Front Matter 是否完整；
- 分类、标签和文件名是否符合本站规范；
- 原始信息是否已经脱敏；
- `_patch` 中已发布的重复稿是否需要清理；
- 构建检查是否通过。

确认无误后合并 PR，即完成发布。

## 相关文档

- `_patch/README.md`：原始笔记暂存区说明；
- `_posts/tools/2026-04-26-blog-agent-skill.md`：Blog Agent Skill 工作规范。
