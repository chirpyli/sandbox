---
title: agent-sandbox产品能力分析
slug: agent-sandbox-production
description: agent-sandbox完全基于k8s进行设计，为Kubernetes定义了Sandbox CRD及控制器。为k8s提供了基础的沙箱能力。属于沙箱编排层，沙箱运行时通过RuntimeClass进行配置，可采用Kata,gVisor。
category: agent-sandbox
order: 40
draft: false
---

## agent-sandbox产品能力分析

agent-sandbox完全基于k8s进行设计，为Kubernetes定义了Sandbox CRD及控制器。为k8s提供了基础的沙箱能力。属于沙箱编排层，沙箱运行时通过RuntimeClass进行配置，可采用Kata,gVisor。



### 当前agent-sandbox具有哪些能力

- SDK： 支持Go，python SDK，支持程序化创建与管理沙箱。
- 支持沙箱模板: SandboxTemplate，定义沙箱的整体形态，包括镜像、运行时、资源限制、网络策略等。
- 支持预热池： SandboxWarmPool，空间换时间，申领沙箱直接从预热池中获取，避免直接冷启动，有效降低了响应时间。将冷启动过程交给预热池进行平滑的冷启动，降低对业务的直接影响。
- 生命周期管理：控制器负责 Pod 创建、定时删除、暂停与恢复。相比Substrate等产品，其生命周期相对简单，checkpoint/快照能力欠缺。
- 持久存储：可挂载重启后依然保留的存储；
- 稳定身份： 每个Sandbox拥有固定主机名与网络身份，重启不换；
- 强隔离： 支持gVisor、Kata等运行时；安全隔离由Kata保证。

### 当前agent-sandbox缺失哪些能力？

- E2B兼容： 当前沙箱产品众多，SDK各不相同，最终SDK是否会收敛标准化？但各产品会有各自不同的特性。类似SQL，但是各数据库都有自己个别独特的语法。（谁是最终标准不确定，E2B也不一定是最终标准）
- 快照： 当前agent-sandbox支持暂停/恢复，对快照的支持弱于OpenSandbox/CubeSandbox/Substrate。OpenSandbox支持快照发布到OCI registry，快照即镜像，可版本化，可分发，可从快照创建新沙箱。Substrate对快照的支持更强大，可配置三种快照级别
- 分支：


> agent-sandbox的暂停卷级休眠，删除Pod释放算力保留PVC，恢复时重建Pod。粒度粗但实现简单可靠。


