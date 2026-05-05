---
layout:     post
title:      Windows / PowerShell 常用命令速查
subtitle:   软链接、环境变量重载、vcpkg 安装与配置
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Windows
    - PowerShell
    - vcpkg
---

>原始笔记是若干个 `### 小标题` 加代码块的列表，软件清单部分没有任何上下文。这里按"软链接 / 环境变量 / vcpkg 安装与配置"四块整理，命令和 JSON 配置保持原样。

## 当前保留内容

### 1. 创建软链接

PowerShell 下用 `New-Item -ItemType SymbolicLink` 创建软链接：

```
New-Item -ItemType SymbolicLink `
 -Path D:\ `
 -Name nvim `
 -Target C:\ProgramData\scoop\apps\neovim\current\bin\nvim.exe

```

### 2. 重启 PowerShell 让环境变量生效

修改完系统环境变量后，新开一个 PowerShell 让其重新加载：

```
Start-Process powershell -ArgumentList "-NoExit"
```

### 3. vcpkg 安装时常配套的工具

按需安装即可，下面这些是配套使用 vcpkg 时常装的：

- gitkraken
- nodejs
- git
- cmake
- ninja

### 4. vcpkg 配置（CMake `CMakeSettings.json` 示例）

针对 VS 14（2015）x86 工具链，配合 Ninja 生成器的一份配置示例：

```
﻿{
  "environments": [
    {
      "environment": "VS_14_x86",
      "VC14INSTALLDIR": "C:\\Program Files (x86)\\Microsoft Visual Studio 14.0\\VC",
      "WINDOWSKITS": "C:\\Program Files (x86)\\Windows Kits",
      "WINDOWSKITS_VERSION": "10.0.17134.0",
      "PATH": "${env.PATH};${env.VC14INSTALLDIR}bin;${env.WINDOWSKITS}\\10\\bin\\x86",
      "INCLUDE": "${env.VC14INSTALLDIR}\\INCLUDE;${env.VC14INSTALLDIR}\\ATLMFC\\INCLUDE;${env.WINDOWSKITS}\\10\\include\\${env.WINDOWSKITS_VERSION}\\ucrt;${env.WINDOWSKITS}\\NETFXSDK\\4.6.1\\include\\um;${env.WINDOWSKITS}\\10\\include\\${env.WINDOWSKITS_VERSION}\\shared;${env.WINDOWSKITS}\\10\\include\\${env.WINDOWSKITS_VERSION}\\um;${env.WINDOWSKITS}\\10\\include\\${env.WINDOWSKITS_VERSION}\\winrt;",
      "LIB": "${env.VC14INSTALLDIR}\\LIB;${env.VC14INSTALLDIR}\\ATLMFC\\LIB;${env.WINDOWSKITS}\\10\\lib\\${env.WINDOWSKITS_VERSION}\\ucrt\\x86;${env.WINDOWSKITS}\\NETFXSDK\\4.6.1\\lib\\um\\x86;${env.WINDOWSKITS}\\10\\lib\\${env.WINDOWSKITS_VERSION}\\um\\x86;",
      "LIBPATH": "C:\\windows\\Microsoft.NET\\Framework\\v4.0.30319;${env.VC14INSTALLDIR}\\LIB;${env.VC14INSTALLDIR}\\ATLMFC\\LIB;${env.WINDOWSKITS}\\10\\UnionMetadata;${env.WINDOWSKITS}\\10\\References;C:\\Program Files (x86)\\Microsoft SDKs\\Windows Kits\\10\\ExtensionSDKs\\Microsoft.VCLibs\\14.0\\References\\CommonConfiguration\\neutral;"
    }
  ],
  "configurations": [
    {
      "name": "x86-Debug",
      "generator": "Ninja",
      "configurationType": "Debug",
      "inheritEnvironments": [ "VS_14_x86" ],
      "buildRoot": "${env.USERPROFILE}\\CMakeBuilds\\${workspaceHash}\\build\\${name}",
      "installRoot": "${env.USERPROFILE}\\CMakeBuilds\\${workspaceHash}\\install\\${name}",
      "cmakeCommandArgs": "",
      "buildCommandArgs": "-v",
      "ctestCommandArgs": ""

    }
  ]
}
```

## 后续可补的方向

- 给"vcpkg 安装清单"补上各工具的实际用途说明（构建、Git GUI、JS 工具链等）
- 把 Windows 与 WSL2 双环境下软链接的差异写清楚（NTFS link vs. WSL symlink）
