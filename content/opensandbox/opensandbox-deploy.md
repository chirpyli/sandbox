---
title: OpenSandbox 安装部署
slug: opensandbox-deploy
description: ''
category: opensandbox
order: 100
lang: zh
draft: false
---

# OpenSandbox 安装部署


### 前置条件
- Kubernetes 1.22+（与 chart 的 kubeVersion 一致）
- Helm 3.0+
- 已配置 kubectl 并能访问目标集群


### helm安装部署

```sh
# 克隆源代码
git clone https://github.com/opensandbox-group/OpenSandbox.git
cd manifests/charts

# 打包子 chart（charts/ 被 git 忽略，每次都会重新构建）
helm dependency build opensandbox

# helm 安装
helm install opensandbox opensandbox \
  --namespace opensandbox-system \
  --create-namespace \
  --set ingress-gateway.enabled=true \
  --set fast-sandbox.enabled=true
NAME: opensandbox
LAST DEPLOYED: Wed Nov 25 17:49:45 2026
NAMESPACE: opensandbox-system
STATUS: deployed
REVISION: 1
DESCRIPTION: Install complete
TEST SUITE: None
NOTES:
OpenSandbox umbrella chart (1.3.0-rc.3) has been deployed to namespace opensandbox-system.

Components:
  - OpenSandbox CRDs + RBAC (base)
  - opensandbox-controller (BatchSandbox/Pool reconciler)
  - opensandbox-server (Lifecycle API server)
  - ingress-gateway (sandbox traffic proxy)
  - fast-sandbox (Firecracker control plane + node runtime)
    Next steps: provision the agent registry Secret
    (fast-sandbox-agent-registry) and KVM-capable nodes; see
    manifests/HELM-DEPLOYMENT.md "fast-sandbox Runtime".

Verify the installation:

  kubectl --namespace opensandbox-system get pods

Server API (port-forward when gateway announcement is off):

  kubectl --namespace opensandbox-system port-forward svc/opensandbox-server 8080:80

Documentation: https://github.com/opensandbox-group/OpenSandbox
```

