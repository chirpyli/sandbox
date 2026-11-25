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
创建对象存储：
```sh
minio server miniodata/ --console-address :9001
MinIO Object Storage Server
Copyright: 2015-2023 MinIO, Inc.
License: GNU AGPLv3 <https://www.gnu.org/licenses/agpl-3.0.html>
Version: RELEASE.2023-11-11T08-14-41Z (go1.21.4 linux/amd64)

Status:         1 Online, 0 Offline. 
S3-API: http://192.168.232.128:9000  http://172.17.0.1:9000  http://192.168.122.1:9000  http://10.244.0.0:9000  http://127.0.0.1:9000             
RootUser: minioadmin 
RootPass: minioadmin 

Console: http://192.168.232.128:9001 http://172.17.0.1:9001 http://192.168.122.1:9001 http://10.244.0.0:9001 http://127.0.0.1:9001       
RootUser: minioadmin 
RootPass: minioadmin 

Command-line: https://min.io/docs/minio/linux/reference/minio-mc.html#quickstart
   $ mc alias set 'myminio' 'http://192.168.232.128:9000' 'minioadmin' 'minioadmin'

```
创建桶bucket:
```sh
mc alias set minio http://192.168.232.128:9000 minioadmin minioadmin
Added `minio` successfully.
postgres@slpc:~/works/my-github/sandbox$ mc mb --ignore-existing minio/sandbox-images
Bucket created successfully `minio/sandbox-images`.
postgres@slpc:~/works/my-github/sandbox$ mc ls minio
[2026-11-25 19:15:28 CST]     0B sandbox-images/
```
创建builder使用的凭证Secret ：
> server 创建 SandboxTemplate 时，默认会引用 opensandbox namespace 里的 sandbox-oss-credentials
```sh
kubectl -n opensandbox create secret generic sandbox-oss-credentials \
  --from-literal=accessKeyId=minioadmin \
  --from-literal=secretAccessKey=minioadmin \
  --from-literal=endpoint=http://192.168.232.128:9000 \
  --from-literal=region=us-east-1 \
  --dry-run=client -o yaml | kubectl apply --server-side -f -
```

创建 fast-sandbox-agent-registry Secret
```json
{
  "credentials": [
    {
      "host": "192.168.232.128:9000",
      "username": "minioadmin",
      "password": "minioadmin",
      "endpoint": "http://192.168.232.128:9000",
      "writeUsername": "minioadmin",
      "writePassword": "minioadmin"
    }
  ]
}
```


helm安装部署
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

更新配置：
```sh
cd manifests/charts
helm dependency build opensandbox

helm upgrade opensandbox opensandbox \
  --namespace opensandbox-system \
  --reuse-values \
  --set-string fast-sandbox.artifactStore.endpoint=http://192.168.232.128:9000 \
  --set-string fast-sandbox.artifactStore.store=s3://sandbox-images/publish

# 降低资源
helm upgrade opensandbox opensandbox \
  --namespace opensandbox-system \
  --reuse-values \
  --set opensandbox-server.server.resources.requests.memory=1Gi \
  --set opensandbox-server.server.resources.limits.memory=2Gi \
  --set opensandbox-server.server.resources.requests.cpu=500m \
  --set opensandbox-server.server.resources.limits.cpu=2 \
  --set ingress-gateway.gateway.resources.requests.memory=1Gi \
  --set ingress-gateway.gateway.resources.limits.memory=2Gi \
  --set ingress-gateway.gateway.resources.requests.cpu=500m \
  --set ingress-gateway.gateway.resources.limits.cpu=2
```

为opensandbox-server设置API KEY:
```sh
API_KEY="$(openssl rand -hex 32)"

kubectl -n opensandbox-system create secret generic opensandbox-api-key \
  --from-literal=api-key="$API_KEY" --dry-run=client -o yaml | kubectl apply -f -

helm upgrade opensandbox opensandbox \
  -n opensandbox-system --reuse-values \
  --set 'opensandbox-server.server.env[0].name=OPENSANDBOX_SERVER_API_KEY' \
  --set 'opensandbox-server.server.env[0].valueFrom.secretKeyRef.name=opensandbox-api-key' \
  --set 'opensandbox-server.server.env[0].valueFrom.secretKeyRef.key=api-key'  

kubectl -n opensandbox-system rollout status deploy/opensandbox-server  
```

获取key供客户端使用：
```sh
kubectl -n opensandbox-system get secret opensandbox-api-key -o jsonpath='{.data.api-key}' | base64 -d; echo
# 客户端请求头：OPEN-SANDBOX-API-KEY: <key>
```

最终部署结果：
```sh
kubectl get pods -n opensandbox-system 
NAME                                              READY   STATUS    RESTARTS   AGE
fast-sandbox-controller-5694d9499b-c89jw          1/1     Running   0          126m
firecracker-runtime-5mz6t                         2/2     Running   0          94m
firecracker-runtime-j9b99                         2/2     Running   0          126m
firecracker-runtime-jl79c                         2/2     Running   0          126m
firecracker-runtime-rhzdt                         2/2     Running   0          126m
opensandbox-controller-manager-646fd5bc6f-62n9f   1/1     Running   0          126m
opensandbox-ingress-gateway-ddcf8b866-l9xpb       1/1     Running   0          22m
opensandbox-ingress-gateway-ddcf8b866-mhd9t       1/1     Running   0          22m
opensandbox-server-79854f9b7b-rpl2l               1/1     Running   0          2m15s

```