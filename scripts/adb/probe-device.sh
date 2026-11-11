#!/system/bin/sh
# 设备能力探测脚本：内核特性 / 容器前提 / 充电控制 / 文件系统
# 用法：
#   adb push scripts/adb/probe-device.sh /data/local/tmp/
#   adb shell sh /data/local/tmp/probe-device.sh
# 或在项目根目录运行：
#   powershell -ExecutionPolicy Bypass -File scripts\adb\probe-device.ps1
# 结果用于判断 "容器是否可行 / 限充是否可做 / 调优节点是否存在"，结论写入 docs/02-可行性分析.md §13。

echo "== identity =="
getprop ro.product.device
getprop ro.board.platform
uname -a

echo "== kernel config (/proc/config.gz) =="
if [ -r /proc/config.gz ]; then
  echo "config.gz: readable"
  zcat /proc/config.gz | grep -E 'CONFIG_(USER_NS|IPC_NS|PID_NS|NET_NS|UTS_NS|NAMESPACES|CGROUPS|CGROUP_BPF|CGROUP_DEVICE|OVERLAY_FS|BINFMT_MISC|SECCOMP|SECCOMP_FILTER|NF_NAT|IP_NF_NAT|IP_NF_FILTER|BRIDGE|VETH|KALLSYMS|MODULES)'
else
  echo "config.gz: not readable (GKI 常见)"
fi

echo "== /proc/self/ns =="
ls -l /proc/self/ns 2>&1

echo "== /proc/filesystems =="
cat /proc/filesystems | grep -E 'overlay|cgroup|binfmt|fuse'

echo "== cgroup mounts =="
mount 2>/dev/null | grep cgroup
echo "-- self cgroup --"
cat /proc/self/cgroup
echo "-- cgroup v2 root --"
ls /sys/fs/cgroup 2>/dev/null | head -30
echo "-- cgroup v2 controllers --"
cat /sys/fs/cgroup/cgroup.controllers 2>/dev/null

echo "== seccomp =="
grep Seccomp /proc/self/status

echo "== namespace runtime test =="
echo -n "unshare -U: "; unshare -U true 2>&1; echo " rc=$?"
echo -n "unshare -m: "; unshare -m true 2>&1; echo " rc=$?"
echo -n "unshare -n: "; unshare -n true 2>&1; echo " rc=$?"
echo -n "unshare -p: "; unshare -p true 2>&1; echo " rc=$?"

echo "== netfilter =="
echo -n "iptables: "; which iptables 2>/dev/null || echo none
echo -n "nft: "; which nft 2>/dev/null || echo none
echo "-- /proc/net/ip_tables_names --"
cat /proc/net/ip_tables_names 2>&1 | head -5

echo "== power supply =="
ls -l /sys/class/power_supply 2>&1
echo "-- battery dir --"
ls /sys/class/power_supply/battery 2>&1 | head -25
for f in charge_control_limit charge_control_limit_max charge_full charge_full_design cycle_count temp capacity status; do
  echo -n "$f="
  cat "/sys/class/power_supply/battery/$f" 2>&1 | head -1
done

echo "== storage / zram =="
cat /proc/swaps 2>&1
ls /sys/block 2>/dev/null | grep -E 'zram|sda|sdb'
echo -n "sda scheduler: "; cat /sys/block/sda/queue/scheduler 2>&1 | head -1

echo "== thermal =="
dumpsys thermalservice 2>/dev/null | head -25

echo "== boot / flash =="
echo -n "slot_suffix="; getprop ro.boot.slot_suffix
echo -n "dynamic_partitions="; getprop ro.boot.dynamic_partitions
echo -n "flash_locked="; getprop ro.boot.flash.locked
echo -n "vbmeta_state="; getprop ro.boot.vbmeta.device_state
echo -n "bootloader="; getprop ro.bootloader
