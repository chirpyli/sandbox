# AI 智能体沙箱

基于 `content/` 目录下的 Markdown 文档构建 GitHub Pages 静态网站，站点地址：<https://chirpyli.github.io/sandbox/>

## 目录结构

```text
content/          文章源文件（日常只需编辑这里）
  assets/         文章图片，构建时复制到站点 assets/content/
  agent-sandbox/  Agent Sandbox 专题
  kata/           Kata Containers 专题
  vm/             虚拟化专题
templates/        站点页面模板与样式
tools/           静态站点生成器
docs/            构建产物（自动生成，已加入 .gitignore）
```

## 写文章

在 `content/` 下新增 Markdown 文件即可，支持任意层级子目录。构建程序会自动补全 frontmatter：标题取首个标题，摘要取首个正文段落，专题取一级目录名，URL 取文件名转换后的 slug。

如果需要把自动生成的元数据固化到源文件（推荐，便于显式维护 `slug`）：

```bash
python3 tools/build_site.py --write-meta
```

可选的 frontmatter 字段：

| 字段 | 作用 | 默认值 |
| --- | --- | --- |
| `title` | 文章标题 | 首个 Markdown 标题 |
| `slug` | 页面 URL，须为小写英文与连字符 | 文件名转换后的 slug |
| `description` | 首页卡片摘要 | 首个正文段落 |
| `category` | 所属专题 | 一级目录名 |
| `order` | 同专题内的排序，越小越靠前 | `100` |
| `tags` | 标签列表 | 空 |
| `draft` | `true` 时不生成页面 | `false` |

页面 URL 由 `slug` 决定，与文件名无关。示例：

```yaml
---
title: "agent-sandbox 核心原理"
slug: agent-sandbox-core-design
description: "沙箱抽象、调度、访问与隔离机制"
category: agent-sandbox
order: 10
tags: [kubernetes, sandbox]
draft: false
---
```

图片放在 `content/assets/`，文章中使用相对路径引用，例如 `![架构图](../assets/agent-sandbox/architecture.png)`，构建时会转换为站点路径。Mermaid 代码块使用 ` ```mermaid ` 围栏即可，页面会按需加载 Mermaid 渲染。

## 本地预览

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 tools/build_site.py
python3 -m http.server 8000 --directory docs
```

浏览器打开 <http://localhost:8000/>。

## 发布

推送到 `master` 分支后，GitHub Actions 会自动构建并发布到 GitHub Pages。首次需要在仓库 `Settings → Pages → Build and deployment` 中将 Source 设置为 `GitHub Actions`。

也可以通过 `workflow_dispatch` 在 Actions 页面手动触发部署。
