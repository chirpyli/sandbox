---
title: 沙箱介绍
slug: sandbox-introduction
description: 对比 agent-sandbox、CubeSandbox 与 Substrate 等设计路线，整理主流开源沙箱运行时。
category: overview
order: 100
draft: false
---

# 沙箱介绍

沙箱Sandbox本质是一个隔离的环境（可以是容器、VM或隔离运行时等）。AI智能体可以在沙箱中执行不信任的代码等。

## 应用场景

- **编程智能体** —— 执行模型生成的命令与代码、安装依赖、跑测试，每个任务独享一个可回滚的沙箱。
- **Computer use / 浏览器自动化** —— 预装桌面或浏览器，隔离不可信页面与鼠标键盘操作。
- **Agentic RL 与批量评测** —— 并行拉起数千个短生命周期环境，依赖快照、分叉与快速回收。
- **多租户 SaaS** —— 运行用户上传的代码或插件，租户间强隔离，防止逃逸与数据串扰。
- **CI/CD 与不可信代码执行** —— 隔离构建、测试步骤，避免污染宿主机。
- ...

## 相关术语

- **沙箱（Sandbox）** —— 一种隔离环境（VM、容器或隔离运行时），AI 智能体在其中执行代码，其文件系统、网络和资源访问均受到控制。
- **编程智能体沙箱（Coding agent sandbox）** —— 专为编程智能体闭环构建的沙箱：支持 Shell、文件系统、软件包安装、Git、长会话和快照。
- **微虚拟机（MicroVM）** —— 一种最小化的 KVM 虚拟机（Firecracker、Cloud Hypervisor），启动时间约为 100–300ms；是 2026 年主流的沙箱基础单元。
- **快照 / 检查点（Snapshot / checkpoint）** —— 保存沙箱某一时刻的状态（内存 + 磁盘），之后可恢复或从中分叉。
- **分叉 / 分支（Fork / branch）** —— 将一个*正在运行*的沙箱克隆为独立副本，类似于 VM 的 `git branch`。
- **休眠 / 暂停-恢复（Hibernate / suspend-resume）** —— 暂停沙箱，使其在空闲时几乎不产生费用或完全不计费，然后在内存状态完整保留的情况下恢复。
- **出站控制（Egress control）** —— 对沙箱可访问哪些网络目标（公共互联网、允许列表、元数据端点）施加的策略。
- **凭证代理 / 注入（Credential brokering / injection）** —— 向沙箱提供短期、权限受限的凭证，而不暴露智能体的真实密钥。
- **Computer use** —— 智能体驱动图形桌面（鼠标/键盘/屏幕）；部分沙箱会为此预装桌面环境。
- **强化学习环境（RL env）** —— 用作强化学习训练环境的沙箱（可并行运行数千个环境：Tensorlake、Morph、Beam）。

## 隔离技术

按隔离强度由弱到强：

- **容器（Container）**：本质是共享宿主机内核，靠 namespaces 做视图隔离、cgroups 限资源、seccomp/capabilities 收敛权限；优点是毫秒级启动、开销极低、OCI 生态成熟，缺点是内核是唯一信任边界，内核漏洞或配置不当即可逃逸。
- **gVisor**：本质是用用户态应用内核（Sentry）接管应用系统调用，文件访问等由 Gofer 代理，宿主侧再用 seccomp 收窄；优点是兼容 OCI、隔离强于容器且无需硬件虚拟化，缺点是系统调用在用户态模拟，syscall/IO 密集型负载有明显性能损耗，部分内核特性不支持。
- **MicroVM**：本质是基于KVM的最小化虚拟机，每个沙箱拥有独立Guest内核，只保留 virtio等必要设备；优点是硬件级隔离、启动百毫秒级、单实例内存开销小，缺点是需要 Guest内核与镜像，启动和内存仍高于容器，且依赖KVM，嵌套虚拟化受限。
- **Kata Containers**：本质是 OCI 兼容的轻量虚拟机，containerd 经 shim 为每个 Pod 起一台 MicroVM（QEMU/Cloud Hypervisor/Firecracker/Dragonball等后端），容器进程跑在Guest内核内；优点是接口与runc一致、可平滑替换并获得VM级隔离，缺点是多了VM 与shim一层，启动和内存开销高于容器。
- **VM（传统虚拟机）**：本质是Hypervisor模拟完整硬件，每台VM有独立内核与完整 OS；优点是隔离最强、可运行任意OS与内核模块，缺点是启动秒级、内存占用大、单机密度低，不适合高频短任务。

隔离强度与启动/内存开销大体同向递增，选型按威胁模型与启动延迟要求取舍。


## 编排与部署

当前Agent沙箱按“是否必须有k8s”大致分三类：
- 完全依赖k8s（K8s原生，单沙箱≈单Pod）：agent-sandbox
- 不依赖k8s（自带控制面，可直接部署到单机/VM）：CubeSandbox
- 依赖k8s但不把沙箱热路径交给k8s（自有调度 + 预热worker/Fastlet）：Substrate、Fast Sandbox

> 另外，OpenSandbox的运行时是可选的：Docker或Kubernetes后端，K8s侧可对接agent-sandbox或Fast Sandbox。



## 沙箱开源项目：

以下为一些知名的沙箱开源项目（部分项目，未全部列出）：

| 运行时 | 维护者 | 隔离 | 许可证 | 备注 |
|---|---|---|---|---|
| [Firecracker](https://github.com/firecracker-microvm/firecracker) | AWS | KVM 微虚拟机（约 150ms 启动） | Apache-2.0 | 专为无服务器场景构建；支撑 E2B、Vercel Sandbox、Sprites 以及大多数初创公司 |
| [gVisor](https://github.com/google/gvisor) | Google | 用户态应用内核 + seccomp | Apache-2.0 | 支撑 Modal、Beam，以及 Northflank 的可选项 |
| [Kata Containers](https://github.com/kata-containers) | OpenInfra Foundation | 轻量 VM，兼容 OCI | Apache-2.0 | 支持 QEMU/Cloud Hypervisor/Firecracker 后端；支撑 Northflank、Daytona 的 VM 类型 |
| [OpenSandbox](https://open-sandbox.ai) | 阿里巴巴 | Docker/Kubernetes 运行时 | Apache-2.0 | 面向编程智能体、GUI 智能体、评测和强化学习训练的生产级运行时 |
| [Fast Sandbox](https://github.com/opensandbox-group/fast-sandbox) | OpenSandbox 社区 | Firecracker 微虚拟机（独立 Guest 内核），也支持 container/gVisor/Kata | Apache-2.0 | OpenSandbox 的 Kubernetes 运行时后端；预热 Fastlet 复用容量、快照启动，跳过每沙箱的 scheduler/watch/kubelet |
| [CubeSandbox](https://github.com/TencentCloud/CubeSandbox) | 腾讯云 | RustVMM + KVM 微虚拟机（独立 Guest 内核）+ eBPF 网络隔离 | Apache-2.0 | 冷启动约 60ms，单节点可运行数千实例；兼容 E2B/OpenAI SDK，可私有化部署 |
| [Substrate](https://github.com/agent-substrate/substrate) | Google（已捐赠 CNCF） | gVisor 应用内核或 Cloud Hypervisor 微虚拟机，默认拒绝出站 | Apache-2.0 | Kubernetes 原生控制面；空闲 actor 快照挂起后亚秒级恢复，密度约为标准容器的 10 倍 |
| [E2B runtime](https://github.com/e2b-dev/E2B) | E2B | Firecracker 微虚拟机 | Apache-2.0 | 可自托管 E2B 技术栈；支持 BYOC/本地部署 |


参考资料：
- [awesome-ai-sandboxes](https://github.com/awesome-llms-labs/awesome-ai-sandboxes.git)