# QUICK-REFERENCE.md - SeaweedFS 快速参考卡

> ⚡ 常用命令、配置和故障排查速查

## 快速启动

### 开发环境（单节点）

```bash
# 下载
wget https://github.com/seaweedfs/seaweedfs/releases/latest/download/linux_amd64.tar.gz
tar -xzf linux_amd64.tar.gz

# 一键启动
./weed mini -dir=/data

# 访问
# Master UI:  http://localhost:9333
# Filer UI:   http://localhost:8888
# S3:         http://localhost:8333
# WebDAV:     http://localhost:7333
# Admin UI:   http://localhost:23646
```

### Docker

```bash
docker run -p 8333:8333 chrislusf/seaweedfs server -s3
```

### 生产环境（多节点）

```bash
# Master
weed master -mdir=/data/master -ip=master-host -port=9333

# Volume Server
weed volume -dir=/data/volume -master=master-host:9333 -port=9340

# Filer
weed filer -master=master-host:9333 -ip=filer-host -port=8888

# S3 Gateway
weed s3 -filer=filer-host:8888 -ip=s3-host -port=8333
```

## S3 客户端配置

### AWS CLI

```bash
aws configure set aws_access_key_id admin
aws configure set aws_secret_access_key key
aws configure set default.region us-east-1
aws configure set default.s3.endpoint_url http://localhost:8333

# 测试
aws s3 ls
aws s3 mb s3://my-bucket
aws s3 cp file.txt s3://my-bucket/
```

### s3cmd

```ini
# ~/.s3cfg
access_key = admin
secret_key = key
host_base = localhost:8333
host_bucket = localhost:8333
use_https = False
```

### mc (MinIO Client)

```bash
mc alias set seaweed http://localhost:8333 admin key
mc ls seaweed/
mc mb seaweed/my-bucket
mc cp file.txt seaweed/my-bucket/
```

### Python (boto3)

```python
import boto3

s3 = boto3.client(
    's3',
    endpoint_url='http://localhost:8333',
    aws_access_key_id='admin',
    aws_secret_access_key='key',
    region_name='us-east-1'
)

s3.create_bucket(Bucket='my-bucket')
s3.upload_file('file.txt', 'my-bucket', 'file.txt')
```

## 常用命令

### Master

```bash
# 查看集群状态
curl http://localhost:9333/cluster/status

# 查看 Volume 分布
curl http://localhost:9333/volume/list

# 手动 Vacuum
curl http://localhost:9333/volume/vacuum
```

### Volume Server

```bash
# 查看 Volume 状态
curl http://localhost:9340/status

# 查看磁盘使用
curl http://localhost:9340/dir/status

# 手动 Compact
curl http://localhost:9340/volume/compact?volumeId=123
```

### Filer

```bash
# 查看目录
curl http://localhost:8888/buckets/

# 查看文件元数据
curl http://localhost:8888/buckets/my-bucket/file.txt
```

### S3 Gateway

```bash
# 查看指标
curl http://localhost:8333/metrics

# 健康检查
curl http://localhost:8333/health
```

## IAM 管理

### 创建用户（Admin UI）

访问 `http://localhost:23646` → IAM → Users → Create User

### 配置文件

```json
// /etc/seaweedfs/iam.json
{
  "users": [
    {
      "name": "app-user",
      "credentials": [
        {
          "accessKey": "AKIAIOSFODNN7EXAMPLE",
          "secretKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        }
      ],
      "policies": ["read-write"]
    }
  ],
  "policies": [
    {
      "name": "read-write",
      "statements": [
        {
          "effect": "allow",
          "actions": ["s3:*"],
          "resources": ["arn:aws:s3:::my-bucket/*"]
        }
      ]
    }
  ]
}
```

### 环境变量

```bash
export AWS_ACCESS_KEY_ID=admin
export AWS_SECRET_ACCESS_KEY=key
```

## 运维命令

### 查看集群状态

```bash
# Master 状态
curl http://master:9333/cluster/status | jq .

# Volume 统计
curl http://master:9333/volume/stats | jq .

# Filer 状态
curl http://filer:8888/health
```

### 添加 Volume Server

```bash
# 在新节点启动 Volume Server
weed volume \
  -dir=/data/volume1 \
  -master=master-host:9333 \
  -port=9340 \
  -max=0
```

### 扩容 Volume

```bash
# 预创建 Volume
weed volume.generate -master=master-host:9333 -count=10

# 或让系统自动创建（max=0）
```

### 数据平衡

```bash
# 触发 Volume 平衡
weed balance -master=master-host:9333

# 或通过 Admin UI 操作
```

### Vacuum（垃圾回收）

```bash
# 手动 Vacuum
weed vacuum -master=master-host:9333 -garbageThreshold=0.3

# 或自动（Master 定期执行）
```

## 监控指标

### Prometheus 指标

```bash
# Master
curl http://localhost:9333/metrics

# Volume
curl http://localhost:9340/metrics

# Filer
curl http://localhost:8888/metrics

# S3
curl http://localhost:8333/metrics
```

### 关键指标

| 指标 | 说明 | 告警阈值 |
|------|------|---------|
| `master_is_leader` | Master 是否 Leader | 0 |
| `volume_disk_free_bytes` | 磁盘剩余 | < 20% |
| `s3_requests_total` | S3 请求数 | - |
| `s3_errors_total` | S3 错误数 | 错误率 > 1% |
| `filer_active_connections` | Filer 连接数 | > 1000 |

## 故障排查

### 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| **403 Forbidden** | 凭证错误 | 检查 AK/SK |
| **404 Not Found** | Bucket 不存在 | 创建 Bucket |
| **500 Error** | 后端故障 | 检查 Filer/Volume |
| **慢上传** | 网络/磁盘瓶颈 | 检查带宽和 IO |
| **连接超时** | 服务未启动 | 检查服务状态 |

### 诊断命令

```bash
# 检查服务状态
systemctl status seaweedfs-master
systemctl status seaweedfs-volume
systemctl status seaweedfs-filer
systemctl status seaweedfs-s3

# 查看日志
journalctl -u seaweedfs-master -f
tail -f /var/log/seaweedfs/master.log

# 网络连通性
telnet master-host 9333
telnet volume-host 9340
telnet filer-host 8888

# 磁盘空间
df -h
du -sh /data/*
```

### 日志位置

```
默认日志位置:
- Master:  /var/log/seaweedfs/master.log
- Volume:  /var/log/seaweedfs/volume.log
- Filer:   /var/log/seaweedfs/filer.log
- S3:      /var/log/seaweedfs/s3.log

或通过 journald:
journalctl -u seaweedfs-master
journalctl -u seaweedfs-volume
```

## 性能调优

### 系统参数

```bash
# /etc/sysctl.conf
fs.file-max = 1000000
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
vm.dirty_ratio = 10
vm.dirty_background_ratio = 5
```

### 磁盘优化

```bash
# SSD 优化
echo 'deadline' > /sys/block/sda/queue/scheduler

# 挂载选项
mount -o noatime,nodiratime /dev/sda1 /data
```

### SeaweedFS 参数

```bash
# Master 优化
weed master \
  -volumeSizeLimitMB=1024 \
  -garbageThreshold=0.3 \
  -maxParallelVacuumPerServer=4

# Volume 优化
weed volume \
  -readMode=memory \
  -index=memory \
  -cacheCapacityMB=1024

# S3 优化
weed s3 \
  -localFiler=true \
  -iamConfigPath=/etc/seaweedfs/iam.json
```

## 备份恢复

### 备份 Master 元数据

```bash
# Master 元数据自动持久化在 mdir 目录
# 定期备份该目录
tar -czf master-backup-$(date +%Y%m%d).tar.gz /data/master
```

### 备份 Filer 元数据

```bash
# MySQL 备份
mysqldump -u root seaweed_filer > filer-backup-$(date +%Y%m%d).sql

# 或 Redis 备份
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb backup/
```

### 恢复流程

```bash
# 1. 恢复 Master
cp master-backup.tar.gz /data/master
tar -xzf master-backup.tar.gz -C /data/master

# 2. 恢复 Filer
mysql -u root seaweed_filer < filer-backup.sql

# 3. 重启服务
systemctl restart seaweedfs-master
systemctl restart seaweedfs-filer
```

## 安全配置

### 防火墙规则

```bash
# 允许 S3 访问
iptables -A INPUT -p tcp --dport 8333 -j ACCEPT

# 允许 Master 访问（仅内网）
iptables -A INPUT -p tcp -s 10.0.0.0/16 --dport 9333 -j ACCEPT

# 允许 Volume 访问（仅内网）
iptables -A INPUT -p tcp -s 10.0.0.0/16 --dport 9340 -j ACCEPT
```

### TLS 配置

```bash
# 使用反向代理（Nginx）
nginx -c /etc/nginx/seaweedfs-ssl.conf

# Nginx 配置示例
server {
    listen 443 ssl;
    server_name s3.example.com;
    
    ssl_certificate /etc/ssl/certs/seaweedfs.crt;
    ssl_certificate_key /etc/ssl/private/seaweedfs.key;
    
    location / {
        proxy_pass http://localhost:8333;
    }
}
```

## 版本升级

### 升级流程

```bash
# 1. 下载新版本
wget https://github.com/seaweedfs/seaweedfs/releases/download/vX.Y.Z/linux_amd64.tar.gz
tar -xzf linux_amd64.tar.gz

# 2. 备份当前版本
cp weed weed.backup

# 3. 滚动升级（逐个节点）
#   a. 停止服务
#   b. 替换二进制
#   c. 启动服务
#   d. 验证健康

# 4. 验证集群状态
curl http://master:9333/cluster/status
```

## 参考资源

| 资源 | 链接 |
|------|------|
| **GitHub** | https://github.com/seaweedfs/seaweedfs |
| **Wiki** | https://github.com/seaweedfs/seaweedfs/wiki |
| **Slack** | https://join.slack.com/t/seaweedfs/shared_invite/enQtMzI4MTMwMjU2MzA3LTEyYzZmZWYzOGQ3MDJlZWMzYmI0OTE4OTJiZjJjODBmMzUxNmYwODg0YjY3MTNlMjBmZDQ1NzQ5NDJhZWI2ZmY |
| **白皮书** | https://github.com/seaweedfs/seaweedfs/wiki/SeaweedFS_Architecture.pdf |

---

*最后更新：2026-03-10*
