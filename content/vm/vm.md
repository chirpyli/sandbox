---

---

### 虚拟化

#### 内存虚拟化

guest OS的"物理内存"本质就是宿主OS上的普通内存——由宿主内核分配、由VMM进程持有。虚拟机并没有一块"专属硬件内存"（机密计算场景除外）。guest看到的"物理内存"，在宿主侧只是 VMM 进程虚拟地址空间里的一段 mmap，背后是宿主的物理页。

虚拟机的内存最终都需要映射到物理内存上面，具体的虚拟机中的内存是如何映射到物理内存中的呢？也就是guest访问内存时发生了什么呢？

没有EPT/NPT硬件辅助支持的情况：

1. guest虚拟地址（GVA）--(guest 页表)--> guest物理地址（GPA）   这里的guest物理地址是guest os自己认为的物理地址，其实是host os的虚拟地址
2. Hypervisor将guest物理地址（GPA）转换为host虚机地址（HVA）
3. host虚机地址（HVA）通过host页表转换为host物理地址（HPA）

有EPT/NPT硬件辅助支持的情况：
guest 虚拟地址(GVA) --(guest 页表)--> guest 物理地址(GPA) --(EPT/NPT)--> 宿主物理地址(HPA) --> 宿主物理内存

- 第一级 GVA→GPA 由 guest 自己的页表完成（guest 内核管理）。
- 第二级 GPA→HPA 由 KVM 维护的 EPT/NPT（硬件第二级地址翻译 SLAT）完成，直接得到宿主物理地址(HPA)，

KVM用硬件虚拟化（EPT/NPT）把GPA→HPA的翻译交给CPU，所以guest访问内存几乎没有额外开销。

dbs-address-space是Dragonball的虚拟机物理地址空间管理库。是VMM侧用来"搭建和维护guest物理地址空间"的库。它把guest的整个物理地址空间（RAM + 设备 MMIO + DAX window + 固件区）建模为若干区域，规定布局约束、提供多种内存来源、并统一对内存（含 DAX）的访问视图，还支持区域热插拔。

```rust
dbs_address_space (本 crate)        ← 提供地址空间/区域/布局/内存抽象
         ▲
         │ 使用
src/dragonball/src/address_space_manager.rs   ← AddressSpaceMgr：把区域映射到 KVM、mmap 到进程、管 NUMA/预分配/快照
         ▲
src/dragonball/src/vm/mod.rs                   ← Vm::init_guest_memory 调用
```

内存何时分配：

- 懒分配（默认）：mmap时只保留虚拟地址范围，宿主物理页并不立刻分配；直到guest第一次访问（触发 page fault），宿主内核才分页。这就是内存超分（oversubscription）的基础——guest 声称有 N GB，但实际占用按需增长。
- 预分配：开启 mem_prealloc 时用 MAP_POPULATE 提前触碰所有页：

Kata里的具体体现：

- "谁"拥有guest内存：Dragonball内置VMM模式跑在shim进程内，所以guest内存就是shim进程的匿名内存（memfd/hugetlbfs）。
- guest 侧完全无感：guest 内核启动时通过引导协议（x86 的 E820 或 UEFI 内存映射）得知"我有多少内存"，它以为这是物理内存；实际由宿主兜底。
- 热插拔：VMM 在宿主上新建后备内存 + 新 KVM slot，再通知 guest 上线（OnlineCPUMem / memHotplugByProbe）。
- footprint：guest RAM 不额外复制，所以一台 2GB 的 Kata VM 大致就是宿主上该 VMM 进程的 2GB 内存（除非超分未触碰）。


