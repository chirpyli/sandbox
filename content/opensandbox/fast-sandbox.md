---
title: Fast Sandbox
slug: fast-sandbox
description: Fast Sandbox 是一个运行时后端，将 OpenSandbox 连接到外部的 fast-sandbox 平台。它在预热的 Fastlet pod 内提供基于模板的 Firecracker microVM 沙箱，从而把每沙箱的 Kub…
category: opensandbox
order: 100
draft: false
---

# Fast Sandbox

Fast Sandbox 是一个运行时后端，将 OpenSandbox 连接到外部的 [fast-sandbox](https://github.com/opensandbox-group/fast-sandbox) 平台。它在预热的 **Fastlet** pod 内提供基于模板的 **Firecracker microVM** 沙箱，从而把每沙箱的 Kubernetes 调度、watch 传播和 kubelet 路径从创建热路径中移除。



**Fast Sandbox是构建在Kubernetes之上的高性能Sandbox运行时，基于Firecracker microVM。**

Fast Sandbox是依赖k8s的，实现中需要fast-sandbox-controller控制器。负责：运行 sandbox.fast.io 的 reconciler/controller，把 CRD 中的期望状态落成现实：模板构建、Fastlet pool、沙箱放置、快照完成等。

Fast Sandbox 将 Firecracker microVM 的虚拟机隔离与快照启动能力带到Kubernetes，面向需要频繁创建和回收执行环境的场景：AI Agent、代码解释器，以及按需开发和测试沙箱。

Kubernetes 管理资源容量和生命周期期望状态。预热的 **Fastlet Pod** 承载多个 Sandbox，Firecracker 运行时从预先构建的快照恢复每个实例。创建 Sandbox 时直接复用已有容量，无需为每次请求重新调度和启动一个 Kubernetes Pod。

安装部署后：
```sh
kubectl get pods -n opensandbox-system 
NAME                                              READY   STATUS    RESTARTS      AGE
fast-sandbox-controller-5694d9499b-c89jw          1/1     Running   0             4h32m
firecracker-runtime-5mz6t                         2/2     Running   0             4h
firecracker-runtime-j9b99                         2/2     Running   0             4h32m
firecracker-runtime-jl79c                         2/2     Running   0             4h32m
firecracker-runtime-rhzdt                         2/2     Running   0             4h32m
opensandbox-controller-manager-646fd5bc6f-62n9f   1/1     Running   1 (45m ago)   4h32m
opensandbox-ingress-gateway-ddcf8b866-l9xpb       1/1     Running   0             168m
opensandbox-ingress-gateway-ddcf8b866-mhd9t       1/1     Running   0             168m
opensandbox-server-79854f9b7b-rpl2l               1/1     Running   0             148m
```


## 动机
Kubernetes运行时的每沙箱路径包含一次API写入、scheduler和watch传播、kubelet reconcile、运行时启动，以及可能的镜像拉取。OpenSandbox已通过BatchSandbox **pool**（`extensions.poolRef`）缓解这一点，它去掉了pod启动，但仍保留K8s API写入和watch传播。对于需要快速供应的 AI agent 和 serverless 工作负载，==fast-sandbox进一步从每沙箱热路径中去掉scheduler/watch/kubelet工作==，同时仍通过同步CRD写入提交持久化意图。其放置是一个内存 Top-K 注册表（先镜像缓存亲和性，再归一化负载，再 stable-hash tiebreak），配合原子 Fastlet admission；运行时通过预热Fastlet pod内的直接containerd socket创建。==K8s保留用于它擅长的事——Fastlet Pod资源核算、集群管理和pool粒度调度==。



Fast Sandbox 在预热的 **Fastlet** pod 内将众多沙箱作为隔离运行时（container / gVisor / Kata / Firecracker）运行，通过 fast-sandbox 的 gRPC Fast-Path 控制面及其带认证的代理数据面访问。该架构把每沙箱的 K8s scheduler、watch 传播和 kubelet 路径从创建热路径中移除；对于需要快速供应的 AI agent 和 serverless 工作负载，fast-sandbox 进一步从每沙箱热路径中去掉 scheduler/watch/kubelet 工作，同时仍通过同步 CRD 写入提交持久化意图。