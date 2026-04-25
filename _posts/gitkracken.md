---
layout:     post
title:      GitKraken 自行编译记录
subtitle:   只是把当时尝试 yarn install / build 时遇到的报错记下来
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - GitKraken
    - Node.js
    - yarn
---

>原始笔记是几行命令和一段报错，这里只做格式整理，并明确这是一份失败/未完成的尝试记录，不是可用的步骤。

## 背景

当时想自己拉源码用 Node.js + yarn 走一遍 GitKraken 的构建流程。下面这些命令是按顺序执行的，但卡在了 `yarn install` 这一步。

## 当时执行的步骤

1. 先安装 Node.js（按官方包或 nvm 都行）。
2. 全局安装 yarn：

   ```bash
   npm install --global yarn
   ```

3. 在源码目录执行：

   ```bash
   yarn install
   yarn build
   ```

## 实际遇到的报错

`yarn install` 在 Windows 用户目录下直接报找不到 `package.json`：

```text
yarn run v1.22.22
error Couldn't find a package.json file in "C:\\Users\\roborock"
info Visit https://yarnpkg.com/en/docs/cli/run for documentation about this command.
```

也就是说 yarn 是在当前工作目录而不是仓库根目录下执行的，需要先 `cd` 到含 `package.json` 的源码目录再跑。

## 后续可补的方向

- 明确 GitKraken 哪些版本/哪些组件实际是开源、可自行构建的
- Windows 下用 PowerShell / Git Bash 执行 yarn 时路径上的注意事项
- 完整跑通后的产物路径与运行方式
