---
title: "沙箱介绍"
slug: sandbox-introduction
description: "沙箱介绍"
lang: zh
draft: true
---

# 沙箱介绍

当前agent沙箱设计基本上有三派：
- 完全依赖k8s： agent-sandbox
- 完全不依赖k8s: CubeSandbox
- 部分依赖k8s： Substrate



知名的沙箱开源项目：

| 运行时 | 维护者 | 隔离 | 许可证 | 备注 |
|---|---|---|---|---|
| [Firecracker](https://github.com/firecracker-microvm/firecracker) | AWS | KVM 微虚拟机（约 150ms 启动） | Apache-2.0 | 专为无服务器场景构建；支撑 E2B、Vercel Sandbox、Sprites 以及大多数初创公司 |
| [gVisor](https://github.com/google/gvisor) | Google | 用户态应用内核 + seccomp | Apache-2.0 | 支撑 Modal、Beam，以及 Northflank 的可选项 |
| [Kata Containers](https://github.com/kata-containers) | OpenInfra Foundation | 轻量 VM，兼容 OCI | Apache-2.0 | 支持 QEMU/Cloud Hypervisor/Firecracker 后端；支撑 Northflank、Daytona 的 VM 类型 |
| [nsjail](https://github.com/google/nsjail) | Google | 命名空间 + seccomp-bpf，零能力 | Apache-2.0 | 比完整 VM 更轻量；支撑 Baponi |
| [bubblewrap](https://github.com/containers/bubblewrap) | containers 组织 | 用户命名空间 + seccomp | LGPL-2.1 | 源自 Flatpak；常见于开源智能体 harness |
| [microsandbox](https://microsandbox.dev) | microsandbox | libkrun 微虚拟机（KVM/Hypervisor.framework/WSL2） | Apache-2.0 | 可编程微虚拟机，本地优先；托管云处于私有测试阶段 |
| [OpenSandbox](https://open-sandbox.ai) | 阿里巴巴 | Docker/Kubernetes 运行时 | Apache-2.0 | 面向编程智能体、GUI 智能体、评测和强化学习训练的生产级运行时 |
| [SmolVM](https://celesto.ai) | Celesto AI | QEMU 或 Firecracker | OSS | Ubuntu/Windows 客户机、快照、Python SDK + CLI |
| [Minimal](https://minimal.dev) | minimal | libkrun 微虚拟机（macOS）；用户命名空间（Linux） | Apache-2.0 | 用于沙箱化开发环境 + 编程智能体的 CLI；提供 MCP 服务器和 GitHub Action |
| [E2B runtime](https://github.com/e2b-dev/E2B) | E2B | Firecracker 微虚拟机 | Apache-2.0 | 可自托管 E2B 技术栈；支持 BYOC/本地部署 |
| [Beam runtime](https://github.com/beam-cloud) | Beam Cloud | gVisor 或 runc | AGPL-3.0 | 开源 GPU 沙箱运行时（beam.cloud 提供托管云） |
| [OpenHands runtime](https://github.com/All-Hands-AI/OpenHands) | All-Hands AI | Docker 容器（默认） | MIT | 参考级开源编程智能体执行运行时（[openhands.dev](https://openhands.dev)）；与 Daytona 合作提供弹性沙箱 |
| [AgentBox](https://github.com/topics/agent-sandbox) | 社区 | Docker+FUSE 覆盖层（本地）、微虚拟机（云） | MIT | 来自 2026 年供应商比较中的智能体沙箱 |


参考资料：
- [awesome-ai-sandboxes](https://github.com/awesome-llms-labs/awesome-ai-sandboxes.git)