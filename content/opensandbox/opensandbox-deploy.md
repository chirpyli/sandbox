---
title: OpenSandbox 安装部署
slug: opensandbox-deploy
description: ''
category: opensandbox
order: 100
draft: false
---
# OpenSandbox 安装部署

部署请参考官方文档：https://github.com/opensandbox-group/OpenSandbox/blob/main/manifests/HELM-DEPLOYMENT.md

## helm方式安装部署

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

KEY=$(openssl rand -base64 32)   # 保存好，部署 server 时复用


# helm 安装
helm install opensandbox opensandbox \
  --namespace opensandbox-system \
  --create-namespace \
  --set ingress-gateway.enabled=true \
  --set fast-sandbox.enabled=true \
  --set ingress-gateway.gateway.providerType=fast-sandbox \
  --set ingress-gateway.gateway.dataplaneNamespace=opensandbox-dataplane
  --set "gateway.secureAccess.keys[0].key_id=a" \
  --set "gateway.secureAccess.keys[0].key=$KEY" 

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

### Fast Sandbox配置
Fast Sandbox不是独立的`runtime.type`，而是在Kubernetes runtime下由 `CompositeSandboxService`分流。

`fastpath_endpoint`这里配置的含义是：告诉OpenSandbox server：Fast Sandbox的FastPath gRPC控制面在哪里。当请求是Fast Sandbox类型时，server通过gRPC调FastPath，提交创建、更新、过期、端点解析、暂停、恢复、快照等操作。文档里`fastpath_endpoint`的默认值是`fast-sandbox-fastpath.opensandbox.svc:9090`，如果当前不是默认值：
```sh
postgres@slpc:~$ kubectl exec -n opensandbox-system deploy/opensandbox-server -- cat /etc/opensandbox/config.toml | tail -20
[runtime]
type = "kubernetes"
execd_image = "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/execd:release-1.3.0-rc.3"

[kubernetes]
kubeconfig_path = ""
namespace = "opensandbox"
informer_resync_seconds = 300
informer_watch_timeout_seconds = 60
workload_provider = "batchsandbox"
batchsandbox_template_file = "/etc/opensandbox/example.batchsandbox-template.yaml"
fastpath_endpoint = "fast-sandbox-fastpath.opensandbox-system.svc:9090"

[egress]
image = "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/egress:release-1.3.0-rc.3"
mode = "dns+nft"


[ingress]
mode = "direct"
postgres@slpc:~$ kubectl get service -n opensandbox-system 
NAME                          TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
dart                          ClusterIP   None            <none>        9000/TCP   15h
fast-sandbox-fastpath         ClusterIP   10.109.77.36    <none>        9090/TCP   15h
opensandbox-ingress-gateway   ClusterIP   10.110.18.30    <none>        80/TCP     15h
opensandbox-server            ClusterIP   10.97.246.187   <none>        80/TCP     15h
```
需要配置server到FastPath的端点配置：
```toml
[server]
host = "0.0.0.0"
port = 80
api_key = ""

[log]
level = "INFO"

[runtime]
type = "kubernetes"
execd_image = "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/execd:release-1.3.0-rc.3"

[kubernetes]
kubeconfig_path = ""
namespace = "opensandbox-dataplane"
informer_resync_seconds = 300
informer_watch_timeout_seconds = 60
workload_provider = "batchsandbox"
batchsandbox_template_file = "/etc/opensandbox/example.batchsandbox-template.yaml"
fastpath_endpoint = "fast-sandbox-fastpath.opensandbox-system.svc:9090"

[egress]
image = "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/egress:release-1.3.0-rc.3"
mode = "dns+nft"
```
执行如下命令：
```sh
helm upgrade opensandbox manifests/charts/opensandbox \
  -n opensandbox-system \
  --reuse-values \
  --set-file opensandbox-server.configToml=/tmp/osb-server-config.toml

kubectl -n opensandbox-system rollout status deploy/opensandbox-server
```


#### 为ingress配置Fast Sandbox provider/endpoint

1. 创建 shared secure-access key Secret
```sh
KEY_ID=a
KEY_SECRET="$(openssl rand -base64 32 | tr -d '\n')"

# echo $KEY_SECRET 
# NHwidyUUA/pPLyZSPxtc+MxDCd8j7Kc45I03dBq+Jac=

kubectl -n opensandbox-system create secret generic opensandbox-secure-access-keys \
  --from-literal="keys=${KEY_ID}=${KEY_SECRET}" \
  --from-literal="active-key=${KEY_ID}" \
  --dry-run=client -o yaml | kubectl apply -f -
```

2. 配置 server 和 ingress gateway

GW_ADDR 换成客户端实际能访问到的 ingress 地址，不要带 http:// 或 https://。你现在 ingress Service 是 ClusterIP，如果只给集群内客户端用，可以用集群内 DNS：`GW_ADDR=opensandbox-ingress-gateway.opensandbox-system.svc.cluster.local`。如果客户端在集群外，需要先通过 NodePort / Ingress / LoadBalancer 暴露，再填那个地址。例如把GW_ADDR换成实际暴露出来的域名或IP:端口，例如：`GW_ADDR=192.168.232.128:31880`。

执行升级：
```sh
GW_ADDR=opensandbox-ingress-gateway.opensandbox-system.svc.cluster.local

helm upgrade opensandbox /home/postgres/works/opensource/OpenSandbox/manifests/charts/opensandbox \
  -n opensandbox-system \
  --reuse-values \
  --set "opensandbox-server.server.gateway.host=${GW_ADDR}"
```

### 配置为PostgreSQL数据库
OpenSandbox默认使用SQLite作为数据库，生产环境建议配置为PostgreSQL。

创建：
```sh
Host:     192.168.232.128
Port:     5433
Database: opensandbox
User:     opensandbox
Password: opensandbox
```

创建数据库连接Secret：
```
namespace: opensandbox-system
secret:    opensandbox-postgresql
```

opensandbox-server会在数据库中创建如下表：
```sql
opensandbox=# \d
            List of relations
 Schema |   Name    | Type  |    Owner    
--------+-----------+-------+-------------
 public | snapshots | table | opensandbox
 public | templates | table | opensandbox
(2 rows)

opensandbox=# select * from templates ;
-[ RECORD 1 ]-+------------------
template_id   | tpl-3bb08948-0b3e-410b-b405-e96cd1578602
namespace     | opensandbox-dataplane
crd_name      | tpl-3bb08948-0b3e-410b-b405-e96cd1578602
spec_json     | {"env": null, "image": "swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/python:3.12", "format": "native", "machine": {"cpu": "1", "memory": "256Mi"}, "publish": "s3://sandbox-images/publish", "readiness": null, "entrypoint": ["tail", "-f", "/dev/null"], "resourceLimits": {"cpu": "1", "disk": "1Gi", "memory": "256Mi"}}
metadata_json | {"purpose": "fast-sandbox-smoke"}
source_image  | swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/python:3.12
publish       | s3://sandbox-images/publish
format        | native
phase         | Building
manifest_ref  | 
message       | 
created_at    | 2026-11-26 17:09:37.853122+08
updated_at    | 2026-11-26 17:09:37.922609+08


opensandbox=# select * from snapshots ;
 id | source_sandbox_id | namespace | name | description | mode | restore_config | state | reason | message | last_transition_at | created_at | updated_at 
----+-------------------+-----------+------+-------------+------+----------------+-------+--------+---------+--------------------+------------+------------
(0 rows)

```


## 用户使用


### 创建SandboxPool

```yaml
---
apiVersion: sandbox.fast.io/v1alpha2
kind: SandboxPool
metadata:
  name: default-pool
  namespace: opensandbox-dataplane
spec:
  runtime: firecracker
  sandboxResources:
    cpu: "1"
    memory: 1Gi
    pids: 256
  capacity:
    poolMin: 1
    poolMax: 2
    bufferMin: 0
    bufferMax: 1
  maxSandboxesPerPod: 4
  fastletTemplate:
    spec:
      containers:
      - name: fastlet
        image: opensandbox/fsb-fastlet:release-1.3.0-rc.3
        imagePullPolicy: IfNotPresent
        env:
        - name: FAST_SANDBOX_RUNTIME_AGENT_SOCKET
          value: /run/fast-sandbox/firecracker/runtime.sock
        volumeMounts:
        - name: agent-socket
          mountPath: /run/fast-sandbox/firecracker
      volumes:
      - name: agent-socket
        hostPath:
          path: /run/fast-sandbox/firecracker
          type: DirectoryOrCreate
      nodeSelector:
        fast-sandbox.io/firecracker-node: "true"
```

执行`kubectl apply -f sandbox-pool.yaml`后，查看`SandboxPool`：
```sh
postgres@slpc:~$ kubectl get sandboxpools.sandbox.fast.io -n opensandbox-dataplane 
NAME           AGE
default-pool   4m42s
```
查看具体：
```sh
postgres@slpc:~$ kubectl -n opensandbox-dataplane get sandboxpool default-pool -o yaml
apiVersion: sandbox.fast.io/v1alpha2
kind: SandboxPool
metadata:
  annotations:
    kubectl.kubernetes.io/last-applied-configuration: |
      {"apiVersion":"sandbox.fast.io/v1alpha2","kind":"SandboxPool","metadata":{"annotations":{},"name":"default-pool","namespace":"opensandbox-dataplane"},"spec":{"capacity":{"bufferMax":1,"bufferMin":0,"poolMax":2,"poolMin":1},"fastletTemplate":{"spec":{"containers":[{"env":[{"name":"FAST_SANDBOX_RUNTIME_AGENT_SOCKET","value":"/run/fast-sandbox/firecracker/runtime.sock"}],"image":"opensandbox/fsb-fastlet:release-1.3.0-rc.3","imagePullPolicy":"IfNotPresent","name":"fastlet","volumeMounts":[{"mountPath":"/run/fast-sandbox/firecracker","name":"agent-socket"}]}],"nodeSelector":{"fast-sandbox.io/firecracker-node":"true"},"volumes":[{"hostPath":{"path":"/run/fast-sandbox/firecracker","type":"DirectoryOrCreate"},"name":"agent-socket"}]}},"maxSandboxesPerPod":4,"runtime":"firecracker","sandboxResources":{"cpu":"1","memory":"1Gi","pids":256}}}
  creationTimestamp: "2026-11-26T05:27:43Z"
  generation: 1
  name: default-pool
  namespace: opensandbox-dataplane
  resourceVersion: "12654321"
  uid: 5f0c722b-1c87-45f0-bbec-573fbd7020ec
spec:
  capacity:
    bufferMax: 1
    bufferMin: 0
    poolMax: 2
    poolMin: 1
  fastletTemplate:
    spec:
      containers:
      - env:
        - name: FAST_SANDBOX_RUNTIME_AGENT_SOCKET
          value: /run/fast-sandbox/firecracker/runtime.sock
        image: opensandbox/fsb-fastlet:release-1.3.0-rc.3
        imagePullPolicy: IfNotPresent
        name: fastlet
        volumeMounts:
        - mountPath: /run/fast-sandbox/firecracker
          name: agent-socket
      nodeSelector:
        fast-sandbox.io/firecracker-node: "true"
      volumes:
      - hostPath:
          path: /run/fast-sandbox/firecracker
          type: DirectoryOrCreate
        name: agent-socket
  maxSandboxesPerPod: 4
  runtime: firecracker
  sandboxResources:
    cpu: "1"
    memory: 1Gi
    pids: 256
status:
  conditions:
  - lastTransitionTime: "2026-11-26T05:27:43Z"
    message: Registry configuration is valid and the compiled Secret is persisted
    observedGeneration: 1
    reason: RegistryAvailable
    status: "True"
    type: RegistryReady
  - lastTransitionTime: "2026-11-26T05:27:43Z"
    message: Infra Components are valid for the selected runtime
    observedGeneration: 1
    reason: InfraComponentsAvailable
    status: "True"
    type: InfraReady
  - lastTransitionTime: "2026-11-26T05:27:44Z"
    message: Waiting for a child Fastlet heartbeat with a ready runtime
    observedGeneration: 1
    reason: RuntimeCapabilityPending
    status: "False"
    type: RuntimeReady
  - lastTransitionTime: "2026-11-26T05:27:44Z"
    message: Pool replica limits can satisfy the current capacity target
    observedGeneration: 1
    reason: CapacityAvailable
    status: "True"
    type: CapacityAvailable
  currentPods: 1
  fastletRevision: af066e6bd4bc720714a42ead03a9bfc02eb38aad4f51e4833b648d1ca029d17c
  fastlets:
    current: 1
    desired: 1
  infraRevision: sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945
  runtimeRevision: sha256:6610dd0d017e30657619ccbca20307c2d309e85cb57619e8057c3cf0bdfea97f
  sandboxes: {}
  summaryObservedAt: "2026-11-26T05:28:44Z"

```

准备API调用：
```sh
kubectl -n opensandbox-system port-forward svc/opensandbox-server 8080:80 >/tmp/osb-pf.log 2>&1 &
PF_PID=$!

API_KEY="$(kubectl -n opensandbox-system get secret opensandbox-api-key \
  -o jsonpath='{.data.api-key}' | base64 -d)"

API=http://127.0.0.1:8080/v1
```

创建模板：
```json
curl -sS -X POST "$API/templates" \
  -H "OPEN-SANDBOX-API-KEY: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "image": "python:3.12",
    "publish": "s3://sandbox-images/publish",
    "format": "native",
    "entrypoint": ["tail", "-f", "/dev/null"],
    "metadata": {
      "purpose": "fast-sandbox-smoke"
    }
  }' | tee /tmp/template-create.json | jq .
{
  "templateId": "tpl-851e0091-9283-453f-bb5a-8f0f7f24e91d",
  "image": "python:3.12",
  "entrypoint": [
    "tail",
    "-f",
    "/dev/null"
  ],
  "metadata": {
    "purpose": "fast-sandbox-smoke"
  },
  "publish": "s3://sandbox-images/publish",
  "format": "native",
  "status": {
    "phase": "Pending"
  },
  "createdAt": "2026-11-26T06:57:40.300353Z",
  "updatedAt": "2026-11-26T06:57:40.300353Z"
}
```

查看：
```sh
kubectl get sandboxtemplates.sandbox.fast.io -A
NAMESPACE               NAME                                       AGE
opensandbox-dataplane   tpl-851e0091-9283-453f-bb5a-8f0f7f24e91d   62s
```

查看Pool中的runtime类型：
```sh
kubectl -n opensandbox-dataplane get sandboxpool default-pool \
  -o jsonpath='{.spec.runtime}{"\n"}'
firecracker

kubectl exec -n opensandbox-dataplane default-pool-fastlet-x5tkb -- ps -ef
Defaulted container "fastlet" out of: fastlet, egress, fastlet-proxy
UID          PID    PPID  C STIME TTY          TIME CMD
root           1       0  0 08:30 ?        00:00:09 /workspace/fastlet
root         215       1  0 09:21 ?        00:00:03 /firecracker --id 64c6852c-5d08-4408-9ac3-09347d79 --start-time-us 110555050692 --start-time-cpu-us 2258 --parent-cpu-time-us 1550 --api-sock /api.sock --log-path /fc.log

```


### 安装osb cli

用户使用可通过osb命令行工具或者SDK，MCP等方式。这里以osb为例。

```sh
# 源码方式安装部署
cd /home/postgres/works/opensource/OpenSandbox/cli

uv sync

uv tool install --editable . --force

# 查看是否安装成功
osb --version
opensandbox, version 1.3.0rc3.dev301+ga3d050be6.d20261126
```

初始化配置：
```sh
osb config init
osb config set connection.domain localhost:8080
osb config set connection.protocol http
osb config set connection.api_key <your-api-key>

postgres@slpc:~/.opensandbox$ osb config show -o json
{
  "api_key": "94************************************************************d6",
  "domain": "localhost:8080",
  "protocol": "http",
  "request_timeout": 60,
  "use_server_proxy": false,
  "color": true,
  "default_image": null,
  "default_timeout": null,
  "config_path": "/home/postgres/.opensandbox/config.toml",
  "config_file_exists": true
}
```





### 创建沙箱模板

通过osb创建沙箱模板
```sh
osb template --help
Usage: osb template [OPTIONS] [COMMAND] [ARGS]...

  🏗 Manage sandbox templates (golden-image builds).

Options:
  -h, --help  Show this message and exit.

Commands:
  create  Create a template and start its asynchronous golden-image build.
  delete  Delete a template by ID.
  get     Get template details including its latest build status.
  list    List templates.
```

执行：
```sh
osb template create \
  --image swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/python:3.12 \
  --publish s3://sandbox-images/publish \
  --format native \
  --entrypoint=tail \
  --entrypoint=-f \
  --entrypoint=/dev/null \
  --resource cpu=1 \
  --resource memory=256Mi \
  --resource disk=1Gi \
  --metadata purpose=fast-sandbox-smoke \
  -o json
{
  "template_id": "tpl-cf6d119b-4ecb-4559-a662-63e599dce451",
  "image": "swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/python:3.12",
  "status": "Pending"
}
```
查看当前沙箱模板列表：
```sh
osb template list
                                                                                 Templates                                                                                 
╭──────────────────────────────────────────┬───────────┬─────────────────────────────────────────────┬────────┬─────────────────────────────┬─────────────────────────────╮
│ TEMPLATE_ID                              │ STATUS    │ IMAGE                                       │ FORMAT │ CREATED_AT                  │ UPDATED_AT                  │
├──────────────────────────────────────────┼───────────┼─────────────────────────────────────────────┼────────┼─────────────────────────────┼─────────────────────────────┤
│ tpl-cf6d119b-4ecb-4559-a662-63e599dce451 │ Building  │ swr.cn-north-4.myhuaweicloud.com/ddn-k8s/d… │ native │ 2026-11-26T08:01:56.021825Z │ 2026-11-26T08:01:56.176498Z │
│ tpl-c86c778b-cf20-474d-a8a9-93503b65165a │ Succeeded │ sandbox-registry.cn-zhangjiakou.cr.aliyunc… │ native │ 2026-11-26T07:19:41.401575Z │ 2026-11-26T07:20:53.691443Z │
```
处在Building状态的模板，表示正在构建中，可以通过osb template get <template_id>查看构建!
```sh
osb template get tpl-cf6d119b-4ecb-4559-a662-63e599dce451
                                       Template Info                                        
╭─────────────────┬────────────────────────────────────────────────────────────────────────╮
│ Key             │ Value                                                                  │
├─────────────────┼────────────────────────────────────────────────────────────────────────┤
│ template_id     │ tpl-cf6d119b-4ecb-4559-a662-63e599dce451                               │
├─────────────────┼────────────────────────────────────────────────────────────────────────┤
│ image           │ swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/python:3.12 │
├─────────────────┼────────────────────────────────────────────────────────────────────────┤
│ publish         │ s3://sandbox-images/publish                                            │
├─────────────────┼────────────────────────────────────────────────────────────────────────┤
│ format          │ native                                                                 │
├─────────────────┼────────────────────────────────────────────────────────────────────────┤
│ status          │ Succeeded                                                              │
├─────────────────┼────────────────────────────────────────────────────────────────────────┤
│ created_at      │ 2026-11-26T08:01:56.021825Z                                            │
├─────────────────┼────────────────────────────────────────────────────────────────────────┤
│ updated_at      │ 2026-11-26T08:04:44.635415Z                                            │
├─────────────────┼────────────────────────────────────────────────────────────────────────┤
│ resource_limits │ {'cpu': '1', 'disk': '1Gi', 'memory': '256Mi'}                         │
├─────────────────┼────────────────────────────────────────────────────────────────────────┤
│ entrypoint      │ ['tail', '-f', '/dev/null']                                            │
├─────────────────┼────────────────────────────────────────────────────────────────────────┤
│ env             │ -                                                                      │
├─────────────────┼────────────────────────────────────────────────────────────────────────┤
│ metadata        │ {'purpose': 'fast-sandbox-smoke'}                                      │
├─────────────────┼────────────────────────────────────────────────────────────────────────┤
│ readiness       │ -                                                                      │
├─────────────────┼────────────────────────────────────────────────────────────────────────┤
│ manifest_ref    │ s3://sandbox-images/publish/cf64c34f79dcee80/manifest.json             │
╰─────────────────┴────────────────────────────────────────────────────────────────────────╯

```
此时观察pods，会发现会起一个'Pod'，实际上是在创建Golden Image。
```sh
kubectl get pods -n opensandbox-dataplane 
NAME                                               READY   STATUS      RESTARTS   AGE
default-pool-fastlet-vz248                         2/2     Running     0          93m
tpl-c86c778b-cf20-474d-a8a9-93503b65165a-build-1   0/1     Completed   0          43m
tpl-cf6d119b-4ecb-4559-a662-63e599dce451-build-1   1/1     Running     0          78s
```


这个目录是一套 Fast Sandbox golden image 制品集，不是普通文件备份。目录名 cf64c34f79dcee80 是构建产物的 content-addressed namespace，manifest.json 是整套制品的元数据和索引。
```sh
# 查看对象存储
postgres@slpc:~/miniodata/sandbox-images/publish$ ls
c461789dd3ad43c4  cf64c34f79dcee80  index
postgres@slpc:~/miniodata/sandbox-images/publish$ cd cf64c34f79dcee80/
postgres@slpc:~/miniodata/sandbox-images/publish/cf64c34f79dcee80$ ls
manifest.json  memory.snap  rootfs.ext4  SHA256SUMS  vmstate.snap
```

解释：

| 文件 | 大小 | 含义 |
| --- | --- | --- |
| manifest.json | 2.6KB | 整套 golden image 的 manifest：文件 digest、机器规格、内核参数、CPU 兼容性、来源镜像等 |
| SHA256SUMS | 664B | rootfs.ext4、memory.snap、vmstate.snap 的 SHA-256 校验和 |
| rootfs.ext4 | 3.0GiB | ext4 根文件系统磁盘镜像，它是一个ext4磁盘镜像 |
| memory.snap | 512MiB | guest物理内存快照 |
| vmstate.snap | 14.5KB | Firecracker VM 的虚拟机和设备状态快照 |

这套组合就是 Fast Sandbox 的 golden image：创建沙箱时直接恢复内存和 VM 状态，而不是重新 boot 操作系统。

### 创建沙箱

我们基于沙箱模板创建沙箱，还可以通过镜像或者快照进行创建。
```sh
# 创建沙箱
osb sandbox create \
  --template tpl-3bb08948-0b3e-410b-b405-e96cd1578602 \
  --timeout 30m \
  --ready-timeout 5m \
  --metadata purpose=fast-sandbox-smoke \
  -o json
{
  "id": "fsb-771f9a58-f3de-4d24-8774-ba723c28be53",
  "status": "created",
  "timeout": "0:30:00",
  "template": "tpl-3bb08948-0b3e-410b-b405-e96cd1578602"
}

# 查看沙箱列表
osb sandbox list
                                                                    Sandboxes                                                                    
╭──────────────────────────────────────────┬───────────┬──────────────────────────────────────────┬──────────────────────┬──────────────────────╮
│ ID                                       │ STATUS    │ IMAGE                                    │ CREATED_AT           │ EXPIRES_AT           │
├──────────────────────────────────────────┼───────────┼──────────────────────────────────────────┼──────────────────────┼──────────────────────┤
│ fsb-771f9a58-f3de-4d24-8774-ba723c28be53 │ ● Running │ tpl-3bb08948-0b3e-410b-b405-e96cd1578602 │ 2026-11-26T09:21:43Z │ 2026-11-26T09:51:43Z │
╰──────────────────────────────────────────┴───────────┴──────────────────────────────────────────┴──────────────────────┴──────────────────────╯

# 查看沙箱
kubectl get sandboxes.sandbox.fast.io -n opensandbox-dataplane -o wide
NAME                                       AGE
fsb-771f9a58-f3de-4d24-8774-ba723c28be53   2m43s

# 查看沙箱
osb sandbox get "fsb-771f9a58-f3de-4d24-8774-ba723c28be53" -o json
{
  "id": "fsb-771f9a58-f3de-4d24-8774-ba723c28be53",
  "status": {
    "state": "Running",
    "reason": "Ready",
    "message": "Runtime, data plane, Infra Components, and Action Bindings are Ready",
    "last_transition_at": "2026-11-26T09:21:44Z"
  },
  "entrypoint": [
    "tail",
    "-f",
    "/dev/null"
  ],
  "expires_at": "2026-11-26T09:51:43Z",
  "created_at": "2026-11-26T09:21:43Z",
  "image": {
    "image": "tpl-3bb08948-0b3e-410b-b405-e96cd1578602",
    "auth": null
  },
  "snapshot_id": null,
  "platform": null,
  "allocation": null,
  "metadata": {
    "purpose": "fast-sandbox-smoke"
  },
  "extensions": {
    "poolRef": "default-pool"
  }
}

```
查看沙箱列表：
```sh
postgres@slpc:~/.opensandbox$ osb sandbox list
                                                                    Sandboxes                                                                    
╭──────────────────────────────────────────┬───────────┬──────────────────────────────────────────┬──────────────────────┬──────────────────────╮
│ ID                                       │ STATUS    │ IMAGE                                    │ CREATED_AT           │ EXPIRES_AT           │
├──────────────────────────────────────────┼───────────┼──────────────────────────────────────────┼──────────────────────┼──────────────────────┤
│ fsb-6321be3d-87e3-4452-8000-57571966e6ab │ ● Running │ tpl-3bb08948-0b3e-410b-b405-e96cd1578602 │ 2026-11-26T09:42:46Z │ 2026-11-26T10:12:46Z │
│ fsb-771f9a58-f3de-4d24-8774-ba723c28be53 │ ● Running │ tpl-3bb08948-0b3e-410b-b405-e96cd1578602 │ 2026-11-26T09:21:43Z │ 2026-11-26T09:51:43Z │
╰──────────────────────────────────────────┴───────────┴──────────────────────────────────────────┴──────────────────────┴──────────────────────╯
postgres@slpc:~/.opensandbox$ kubectl exec -n opensandbox-dataplane default-pool-fastlet-x5tkb -- ps -ef
Defaulted container "fastlet" out of: fastlet, egress, fastlet-proxy
UID          PID    PPID  C STIME TTY          TIME CMD
root           1       0  0 08:30 ?        00:00:09 /workspace/fastlet
root         215       1  0 09:21 ?        00:00:04 /firecracker --id 64c6852c-5d08-4408-9ac3-09347d79 --start-time-us 110555050692 --start-time-cpu-us 2258 --parent-cpu-time-us 1550 --api-sock /api.sock --log-path /fc.log
root         271       1  1 09:42 ?        00:00:00 /firecracker --id 2dcd47e8-b627-4803-9170-a29acb0c --start-time-us 111817516511 --start-time-cpu-us 2874 --parent-cpu-time-us 2175 --api-sock /api.sock --log-path /fc.log

```


`osb terminal <sandbox-id>`打开交互式终端：
```sh
bash-5.2# uname -a
Linux sandbox 6.18.36+ #1 SMP PREEMPT_DYNAMIC Wed Jul 29 03:28:15 UTC 2026 x86_64 GNU/Linux
```