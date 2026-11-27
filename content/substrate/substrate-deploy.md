---
title: Substrate 安装部署与使用
slug: substrate-deploy
description: Substrate 的部署前置条件，以及 SandboxConfig、WorkerPool、ActorTemplate、Actor 的配置与使用步骤。
category: substrate
order: 20
draft: false
---

## Substrate安装部署与使用

### 部署

前置条件：

- k8s环境，1.37+
- PostgreSQL数据库 17+
- 对象存储

substrate-install.yaml

```yaml
# Agent Substrate 安装配置，由 operator 维护。
#
#   ate-setup deploy ate-system --config substrate-install.yaml
#   ATE_CONFIG=substrate-install.yaml ate-setup deploy ate-system
#
# 这里的每项设置都可通过环境变量或 flag 提供；完整列表及优先级见
# docs/operator-install.md。
# 未列出的 key 保持声明的默认值，`ate-setup --help` 会打印这些默认值。
# 显式列出的 key 若值为空，则设为空值而非保留默认值，这是清空设置的方式。
apiVersion: install.ate.dev/v1alpha1
kind: SubstrateInstall

# 控制平面部署位置。context 来自当前 kubeconfig。
namespace: ate-system
context: kubernetes-super-admin@kubernetes

# 粗略规模 profile：size0 或 size10。当前 4 节点集群无专用 PostgreSQL 节点，使用 size0。
clusterSize: size0

# ate-setup 只接受 gvisor、microvm；kata 不是合法值。
# 当前非 kind + S3 环境下 microvm 资产上传仍走 GCS，因此使用 gvisor。
sandboxClasses: gvisor

# 占位值：仅用于绕过 ate-setup 的非 kind GCS 预检，S3 模式不使用真实 GCP 身份。
gcp:
  projectID: substrate-local

# 每个 workload 的 readiness 等待时长，使用 Go duration 格式。
rolloutTimeout: 10m0s

# ingress 和 egress dataplane：envoy 或 agentgateway。
atenet:
  dataplane: envoy
  egress:
    credentialProvider: '{"name":"k8s.io"}'

# 允许 kubectl ate proxy actor 使用的客户端身份。
ingressAllowedSPIFFEIDs: spiffe://cluster.local/ns/ate-system/sa/atenet-client

# 使用正式发布镜像；集群需要能访问 ghcr.io。若从源码构建，删除本段。
# 如果镜像拉取失败，则从源码构建
images:
  repo: ghcr.io/agent-substrate/substrate
  tag: v1.0.0

# 快照存储。MinIO bucket ate-snapshots 已创建。
# 本文件只设置 bucket 和 URI；S3 endpoint 与凭据已写入 base manifest 的
# objectstore-plugin initContainer：atelet.yaml 与 ate-api-server.yaml。
storage:
  bucketName: ate-snapshots
  snapshotLocation: s3://ate-snapshots/
  # 占位值：仅用于绕过 ate-setup 的非 kind GCS 预检，S3 模式不使用真实 GSA。
  transferGSAName: ate-snapshot-transfer

ateapi:
  postgres:
    schema: substrate
    # 本地开发：数据库 substrate，登录用户与密码均为 substrate。
    # owner 与 readWrite 连接池共用该登录用户，分别 SET ROLE 到下列角色。
    owner:
      role: substrate_owner
      connectionString: 'postgresql://substrate:substrate@192.168.232.128:5433/substrate?sslmode=disable'
    readWrite:
      role: substrate_readwrite
      connectionString: 'postgresql://substrate:substrate@192.168.232.128:5433/substrate?sslmode=disable'

```

执行下面的命令安装：

```sh
ate-setup  --no-dev-env deploy ate-system --config substrate-install.yaml
```

> `SandboxConfig`（Kubernetes CRD）：集群作用域资源，列出某个沙箱类别（gvisor 或 microvm）的沙箱运行时版本和资产。每个`WorkerPool`为其类别解析一个`SandboxConfig`。

部署substrate后，首先是声明`SandboxConfig`。明确某个沙箱类别的沙箱运行时版本和资产。

部署配置microvm：

```sh
kubectl get sandboxconfigs.ate.dev 
NAME             CLASS     DEFAULT   AGE
gvisor-default   gvisor    v7        3d21h      
```

部署按模板的固定版本把这套资产手工装配并上传了：

- kata-static-4.3.1-amd64.tar.zst 取出 vmlinux、rootfs.img、virtiofsd
- cloud-hypervisor-static v53.0
- 四个文件的 sha256 与 manifests/ate-install/sandboxconfig-microvm.yaml.tmpl 里 amd64 的固定值逐一核对，全部一致
- 上传到 s3://ate-snapshots/microvm-assets/amd64/<sha256></sha256>（就是 ate-setup 在 kind 上用的布局，只做了 amd64）
- 用 s3:// URL 渲染并应用了集群级 microvm SandboxConfig

```yaml
apiVersion: ate.dev/v1
kind: SandboxConfig
metadata:
  name: microvm
  annotations:
    sandboxconfig.ate.dev/is-class-default: "true"
spec:
  sandboxClass: microvm
  defaultVersion: v2
  versions:
  - name: v2
    state: Enabled
    assets:
      amd64:
        cloud-hypervisor:
          url: "s3://ate-snapshots/microvm-assets/amd64/448af3d4e59b22c2987f7df94c213ad40fb53a10d437e42b5ee6c4fce7c29ecc"
          sha256: "448af3d4e59b22c2987f7df94c213ad40fb53a10d437e42b5ee6c4fce7c29ecc"
        virtiofsd:
          url: "s3://ate-snapshots/microvm-assets/amd64/15b2e72a78cc08a9bd8a6943e89fb69c88cb3cbeb63069efceade835342ac7d4"
          sha256: "15b2e72a78cc08a9bd8a6943e89fb69c88cb3cbeb63069efceade835342ac7d4"
        kata-kernel:
          url: "s3://ate-snapshots/microvm-assets/amd64/f87d8359035cb7557b16a319e6431ea09b183e62268aef436bf8dc6530d786b6"
          sha256: "f87d8359035cb7557b16a319e6431ea09b183e62268aef436bf8dc6530d786b6"
        kata-image:
          url: "s3://ate-snapshots/microvm-assets/amd64/6770db2cca5710593f27c9ac5e1d9d7aab836422695a5e5c4807496a92a0f24d"
          sha256: "6770db2cca5710593f27c9ac5e1d9d7aab836422695a5e5c4807496a92a0f24d"
```

```sh
kubectl get sandboxconfigs.ate.dev 
NAME             CLASS     DEFAULT   AGE
gvisor-default   gvisor    v7        3d21h
microvm          microvm   v2        36m        
```

### 使用

创建顺序：SandboxConfig → WorkerPool → ActorTemplate → Actor

#### 创建WorkerPoll

```yaml
# Worker pool for the pgdba Actor.
#
# sandboxClasses[].name selects the substrate sandbox class: gvisor or microvm.
# It is NOT a Kubernetes RuntimeClass: kata-fc/kata-clh are used by the
# agent-sandbox path only. metadata.labels is what ActorTemplate.workerSelector
# matches (see 20-actor-template.yaml.tmpl).
apiVersion: ate.dev/v1
kind: WorkerPool
metadata:
  name: pgdba-pool
  namespace: dba-agent
  labels:
    workload: pgdba
spec:
  replicas: 2   # workerpool中worker pod的数量
  workerImage: ghcr.io/agent-substrate/substrate/ateworker-microvm:v1.0.0 
  sandboxClasses:  # 沙箱类别： 支持gvisor,microvm
    - name: microvm
      configRef:
        name: microvm
  template:
    nodeSelector:
      kubernetes.io/os: linux
    resources:
      limits:
        cpu: "4"
        memory: 3Gi
      requests:
        cpu: "1"
        memory: 1Gi
```

查看WorkerPool，等待Worker Pod就绪

```sh
kubectl get workerpools.ate.dev -A
NAMESPACE   NAME         DESIRED   REPLICAS   READY   SANDBOXCONFIG   RESOLVED   AGE
dba-agent   pgdba-pool   2         2          2       microvm         True       17m
```

#### 创建ActorTemplate

Actor模板

```yaml
# ActorTemplate (protojson-shaped ateapi.ActorTemplate).
#
#   kubectl ate create actor-template -f rendered/20-actor-template.yaml
#
# Image must be digest-pinned; scripts/render-ate-manifests.sh injects it.
# The entrypoint resolves the bind address and defaults the port to 80, because
# an Actor has no POD_IP and its default ingress port is 80.
metadata:
  atespace: dba-agent
  name: pgdba-dba-v1
workerSelector:
  matchLabels:
    workload: pgdba
containers:
- name: dsh
  image: 192.168.232.128:5000/pgdba/dsh-db-agent@sha256:ab2b0cb37a3df65fe5fb297dced552d17425bacfe845c2adb1bebd31e26b04ea
  command:
  - /usr/local/bin/dsh-entrypoint
  args:
  - --profile
  - db-agent
  - --no-open
  env:
  - name: PGDBA_RUNTIME
    value: substrate
  - name: PGDBA_SUBSTRATE_ATESPACE
    value: dba-agent
  - name: PGDBA_SUBSTRATE_ACTOR
    value: dba
  - name: PGDBA_DB_TRANSPORT
    value: mcp
  - name: PGDBA_DB_HTTP_ENDPOINT
    value: http://pg-http-bridge.dba-agent.svc:8000
  - name: PGDBA_WEB_TOKEN_SINK
    value: http://dsh-web-auth.dba-agent.svc:8081/v1/dsh-token
  # Turn state (busy/idle/evicted) for the suspend supervisor; a long tool call
  # must not look like an idle browser.
  - name: PGDBA_AGENT_STATE_SINK
    value: http://dsh-web-auth.dba-agent.svc:8081/v1/agent-state
  - name: PGDBA_INGRESS
    value: atenet
  - name: DSH_HOME
    value: /data/dsh
  - name: HOME
    value: /data/dsh
  # The egress gateway terminates TLS for api.deepseek.com to inject x-api-key;
  # Node only trusts it when told about the MitM CA.
  - name: NODE_EXTRA_CA_CERTS
    value: /run/substrate/certs/ca.pem
  # Placeholder: the real key is injected by atenet-egress replaceHeaders.
  - name: DEEPSEEK_API_KEY
    value: ate-egress-injected
  volumeMounts:
  - name: dsh-home
    mountPath: /data/dsh
  - name: dsh-work
    mountPath: /workspace
  - name: trust
    mountPath: /run/substrate/certs
  securityContext:
    capabilities:
      drop: ["ALL"]
# wakeupProbe must see 200; dsh's "/" answers 303/401 without a session token,
# which would make ResumeActor time out. This sidecar is the readiness gate the
# router waits for on every wake.
- name: health
  image: 192.168.232.128:5000/pgdba/dsh-db-agent@sha256:ab2b0cb37a3df65fe5fb297dced552d17425bacfe845c2adb1bebd31e26b04ea
  command:
  - /usr/local/bin/node
  - -e
  - "require('node:http').createServer((q,s)=>{s.writeHead(200,{'content-type':'text/plain'});s.end('ok')}).listen(8082,'0.0.0.0')"
  wakeupProbe:
    httpGet:
      path: /
      port: 8082
    timeoutSeconds: 60
resources:
  limits:
    cpuMillicores: 1000
    memoryBytes: 1073741824
volumes:
- name: dsh-home
  durableDir: {}
- name: dsh-work
  durableDir: {}
- name: trust
  systemInfo:
    dataSources:
    - trustBundle:
        names: [egress-mitm.ate.dev]
        path: ca.pem
snapshotConfig:
  preferredFidelity: SNAPSHOT_FIDELITY_MEMORY   # 快照级别，快照保真度

```

创建命令：

```sh
kubectl ate create actor-template -f rendered/20-actor-template.yaml
```

执行后，会在microvm上生成Golden Snapshot快照。即，在创建`ActorTemplate`时，从工作负载的一次临时Golden启动中一次性捕获的初始检查点。默认情况下，当该快照可用时，改模板的Actor首次会从这个共享快照还原，否则会冷启动。它按模板的`preferredFidelity: SNAPSHOT_FIDELITY_MEMORY`捕获。

```sh
kubectl-ate get actor-template -A
Warning: no --token-file given; acting as the shared identity system:serviceaccount:ate-system:ate-client rather than as yourself. Pass --token-file to act as yourself.
ATESPACE    NAME           GOLDEN TAG                             ERROR   AGE
dba-agent   pgdba-dba-v1   f63de16b-6961-4e12-9819-48e2b5bcb329           10m
```

#### 创建Actor

```sh
kubectl ate get actor -A
ATESPACE    NAME   TEMPLATE                 STATE                   WORKER POD   WORKER IPS   VERSION   AGE
dba-agent   dba    dba-agent/pgdba-dba-v1   ACTOR_STATE_SUSPENDED   <none>                    1         6m53s
```

### PostgreSQL数据库

```sql
substrate=# \d
                               List of relations
  Schema   |            Name             |       Type        |      Owner    
-----------+-----------------------------+-------------------+-----------------
 substrate | actor_egress_policies       | table             | substrate_owner
 substrate | actor_templates             | table             | substrate_owner
 substrate | actors                      | table             | substrate_owner
 substrate | assertion                   | table             | substrate_owner
 substrate | atespace_access_policies    | table             | substrate_owner
 substrate | atespaces                   | table             | substrate_owner
 substrate | authorization_model         | table             | substrate_owner
 substrate | changelog                   | table             | substrate_owner
 substrate | global_access_policy        | table             | substrate_owner
 substrate | leases                      | table             | substrate_owner
 substrate | schema_migrations           | table             | substrate_owner
 substrate | schema_migrations_id_seq    | sequence          | substrate_owner
 substrate | store                       | table             | substrate_owner
 substrate | tags                        | table             | substrate_owner
 substrate | tuple                       | table             | substrate_owner
 substrate | worker_assignments          | table             | substrate_owner
 substrate | worker_outbox               | partitioned table | substrate_owner
 substrate | worker_outbox_default       | table             | substrate_owner
 substrate | worker_outbox_p202611240530 | table             | substrate_owner
 substrate | worker_outbox_p202611240545 | table             | substrate_owner
 substrate | worker_outbox_p202611240600 | table             | substrate_owner
 substrate | worker_outbox_p202611240615 | table             | substrate_owner
 substrate | worker_outbox_trim          | table             | substrate_owner
 substrate | workers                     | table             | substrate_owner
(24 rows)

```
