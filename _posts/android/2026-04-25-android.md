---
layout:     post
title:      Android 开发零散记录
subtitle:   反编译、Gradle 对齐与 debug 构建配置的最小备忘
date:       2026-04-25
author:     BY
header-img: img/post-bg-android.jpg
catalog: true
tags:
    - Android
    - Gradle
    - Debug
---

>把原先几条零散备注整理成“工具入口 + 构建提醒 + 调试配置”三个部分，方便回看时快速定位。

## 1. 反编译工具入口

原始笔记只记了一条：

- `jadx`

因此这篇里把它保留成一个明确提醒：如果当前目的是快速看 APK / dex 的 Java 代码结构，先从 `jadx` 开始，而不是一上来就手动解包所有产物。

## 2. Gradle 版本先看兼容关系

原始记录里的结论是：

> Gradle 版本需要与 XXX 版本对应

虽然当时没把具体版本对照表写下来，但这条提醒本身很有价值：  
**只要 Android 工程在同步、构建或插件加载阶段报错，先确认 Gradle、Android Gradle Plugin 和 JDK 的组合是否匹配。**

回看这条笔记时，优先检查：

1. `gradle-wrapper.properties` 里的 Gradle 版本
2. 工程使用的 Android Gradle Plugin 版本
3. 当前本机或 CI 的 JDK 版本

很多看起来像“脚本写错了”的问题，根因其实是版本不兼容。

## 3. Gradle 脚本调试最小方法

原始笔记里给出的关键词只有一个：

```gradle
println
```

可以把它理解成最小调试手段：  
当你不确定某个变量、任务分支或配置块有没有生效时，先在 Gradle 脚本里用 `println` 打印关键值，快速确认执行路径。

它适合回答这类问题：

- 当前脚本到底有没有被执行
- 某个变量在配置阶段拿到的值是什么
- 某段逻辑走的是哪条分支

## 4. 常用 debug 构建配置

原始记录保留的配置片段如下：

```gradle
debug {
    debuggable true
    jniDebuggable true
    minifyEnabled false
    shrinkResources false
}
```

整理后可以把它理解成一组常见目标：

- `debuggable true`：允许 Java / Kotlin 层调试
- `jniDebuggable true`：允许 Native 层调试
- `minifyEnabled false`：避免混淆影响排查
- `shrinkResources false`：避免资源裁剪让问题现场失真

## 5. 什么时候先回看这篇

这篇笔记适合在下面几类场景里快速翻一下：

1. 想先反编译看 APK 结构时
2. Gradle 同步 / 构建异常，但一时看不出是脚本问题还是版本问题时
3. 需要准备一个更适合调试的 Android debug 构建时
