---
title: Fast Sandbox
slug: fast-sandbox
description: Fast Sandbox 是一个运行时后端，将 OpenSandbox 连接到外部的 fast-sandbox 平台。它在预热的 Fastlet pod 内提供基于模板的 Firecracker microVM 沙箱，从而把每沙箱的 Kub…
category: opensandbox
order: 100
lang: zh
draft: false
---

# Fast Sandbox

Fast Sandbox 是一个运行时后端，将 OpenSandbox 连接到外部的 [fast-sandbox](https://github.com/opensandbox-group/fast-sandbox) 平台。它在预热的 **Fastlet** pod 内提供基于模板的 **Firecracker microVM** 沙箱，从而把每沙箱的 Kubernetes 调度、watch 传播和 kubelet 路径从创建热路径中移除。

