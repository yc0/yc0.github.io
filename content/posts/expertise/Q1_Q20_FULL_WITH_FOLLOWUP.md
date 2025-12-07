---
date: '2025-12-03T19:51:15+08:00'
draft: true
categories:
  - Performance
title: Linux CPU 飆高要如何排查
---
# Q1–Q20 Final Deep Version (with Follow-up Answers)

## Q1. Linux CPU 飆高要如何排查？（含 user/system/hi/si/steal）

### Standard Answer
CPU investigation begins by separating user, system, interrupt, softirq, and steal time. I use `top -H`, `pidstat -t` and `perf` to identify hotspots.

### Advanced Answer
Check CPU distribution with:
```
top -H
vmstat 1
```

Trace threads:
```
pidstat -t 1 5
```

Profile kernel/user hotspots:
```
perf top
```

### Follow-up Answers
- **Throttle vs saturation:** Check `cpu.stat`; increasing `nr_throttled` = throttling.  
- **Softirq storm mitigation:** Enable RPS/RSS; increase NIC queues.  
- **Steal time:** Move VM or use sole-tenant node.


## Q2. Memory OOM 發生時，你如何定位？

### Standard Answer
Check `dmesg -T`, identify the killed process, and inspect RSS/PSS.

### Advanced Answer
```
dmesg -T | grep OOM
cat /proc/<pid>/smaps_rollup
```

### Follow-up Answers
- **Java fragmentation:** Use `jcmd <pid> VM.native_memory summary`.  
- **Page cache vs RSS:** Use `free -h`, `vmstat -m`.


## Q3. RSS / VSS / PSS 差異？哪個影響 OOM？

### Standard Answer
RSS = real memory → triggers OOM; VSS = virtual; PSS = proportionally shared.

### Advanced Answer
```
cat /proc/<pid>/status
cat /proc/<pid>/smaps_rollup
```

### Follow-up Answers
- **Why VSS huge but safe?** Doesn’t consume physical memory.  
- **Why PSS billing?** Because shared memory is divided proportionally.


## Q4. Disk I/O latency 怎麼查？（iostat/queue-depth）

### Standard Answer
Use `iostat -x` to check await, queue depth, %util.

### Advanced Answer
```
iostat -x 1 5
```

### Follow-up Answers
- **Sequential vs random:** Use `blktrace`.  
- **RAID0 for PD:** Stripe multiple PDs with `mdadm`.


## Q5. Linux sysctl：你最常調哪些？為何？

### Standard Answer
Tune memory and TCP network parameters.

### Advanced Answer
```
vm.swappiness=1
net.core.somaxconn=4096
```

### Follow-up Answers
- **somaxconn vs backlog:** kernel vs per-app queue.  
- **Dirty spike impact:** flush stalls cause tail latency.


## Q6. TCP TIME_WAIT 暴增怎麼處理？

### Standard Answer
Use connection pooling and expand port ranges.

### Advanced Answer
```
ss -s | grep timewait
sysctl -w net.ipv4.tcp_tw_reuse=1
```

### Follow-up Answers
- **Why recycle removed?** Breaks NAT.  
- **NAT TIME_WAIT storm:** SNAT device becomes client endpoint.


## Q7. SYN backlog 滿怎麼查？

### Standard Answer
Check dmesg for SYN drops and tune backlog.

### Advanced Answer
```
sysctl net.ipv4.tcp_max_syn_backlog
```

### Follow-up Answers
- **Flood vs overflow:** repeated IP vs distributed clients.


## Q8. conntrack table 滿怎麼查？

### Standard Answer
Check conntrack_count and conntrack_max.

### Advanced Answer
```
conntrack -L | head
```

### Follow-up Answers
- **Tune aging:** adjust `nf_conntrack_tcp_timeout_*`.


## Q9. Web latency 如何分解？（DNS → TCP → TLS → TTFB）

### Standard Answer
Use `curl -w` to split latency.

### Advanced Answer
```
curl -w "@format.txt" -o /dev/null https://example.com
```

### Follow-up Answers
- **Cross-region:** analyze with mtr; verify Anycast POP.


## Q10. TLS handshake 過慢怎麼查？

### Standard Answer
Use openssl to inspect TLS negotiation.

### Advanced Answer
```
openssl s_client -connect example.com:443
```

### Follow-up Answers
- **HTTP/2 helps:** fewer full handshakes due to multiplexing.


## Q11. TCP Retransmission 過高如何排查？

### Standard Answer
Use `ss -ti` and verify MTU and packet loss.

### Advanced Answer
```
tcpdump -ni eth0 host <ip>
```

### Follow-up Answers
- **RTO reduces cwnd:** drops throughput sharply.


## Q12. TCP cwnd 與 throughput 的關係？

### Standard Answer
Throughput ≈ cwnd/RTT.

### Advanced Answer
CUBIC increases faster in high-latency networks.

### Follow-up Answers
- **Why CUBIC?** Better for WAN.


## Q13. 如何 debug Linux DNS latency？

### Standard Answer
Check resolv.conf, CoreDNS logs.

### Advanced Answer
```
kubectl logs -n kube-system -l k8s-app=kube-dns
```

### Follow-up Answers
- **Scale-out DNS:** increase CoreDNS replicas.


## Q14. HTTP 503 與 504 的差異？

### Standard Answer
503 = backend unavailable; 504 = upstream timeout.

### Advanced Answer
503 often from readiness fails.

### Follow-up Answers
- **Autoscaling 503:** warm-up instances.


## Q15. HTTP keep-alive 為什麼重要？

### Standard Answer
Reduces handshake and TIME_WAIT.

### Advanced Answer
Improves conntrack efficiency.

### Follow-up Answers
- **Where to keep-alive?** Prefer LB-level pooling.


## Q16. NAT gateway/SNAT 為什麼會造成 connection reset？

### Standard Answer
SNAT state expiration or port exhaustion.

### Advanced Answer
```
conntrack -L
```

### Follow-up Answers
- **Avoid exhaustion:** add external IPs or NAT gateways.


## Q17. Linux 調度器（CFS）如何影響 latency？

### Standard Answer
Long run queues cause wait time.

### Advanced Answer
Quota forces cgroup freezes.

### Follow-up Answers
- **Why latency spikes?** Cgroup throttling.


## Q18. 為什麼 Pod 可 ping，但 Service 不通？

### Standard Answer
Service relies on kube-proxy rules.

### Advanced Answer
```
kubectl get ep <svc>
```

### Follow-up Answers
- **kube-proxy crash:** ClusterIP fails.


## Q19. Ingress → Pod 的路徑怎麼 debug？

### Standard Answer
Check Ingress logs and test from inside cluster.

### Advanced Answer
Path: LB → NodePort → Ingress → Service → Pod

### Follow-up Answers
- **Timeout layer:** LB logs vs Ingress logs vs Pod latency.


## Q20. 為什麼 Pod readiness probe 常失敗？

### Standard Answer
Probe too strict or app too slow.

### Advanced Answer
```
kubectl describe pod
```

### Follow-up Answers
- **Cascading failure:** unhealthy pods cause overload on others.


