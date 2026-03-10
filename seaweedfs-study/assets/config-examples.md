# SeaweedFS 配置示例

## 1. Docker Compose 配置

### 1.1 开发环境（单节点）

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  seaweedfs:
    image: chrislusf/seaweedfs:latest
    command: mini -dir=/data
    volumes:
      - ./data:/data
    ports:
      - "9333:9333"   # Master
      - "8888:8888"   # Filer
      - "8333:8333"   # S3
      - "7333:7333"   # WebDAV
      - "23646:23646" # Admin UI
    environment:
      - AWS_ACCESS_KEY_ID=admin
      - AWS_SECRET_ACCESS_KEY=key
    restart: unless-stopped
    networks:
      - seaweedfs

networks:
  seaweedfs:
    driver: bridge
```

### 1.2 生产环境（多节点）

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  master:
    image: chrislusf/seaweedfs:latest
    command: >
      master
      -mdir=/data/master
      -ip=master
      -port=9333
      -volumeSizeLimitMB=1024
      -defaultReplication=001
    volumes:
      - ./data/master:/data/master
    ports:
      - "9333:9333"
    networks:
      - seaweedfs
    deploy:
      replicas: 3
      placement:
        constraints:
          - node.labels.role == master

  volume:
    image: chrislusf/seaweedfs:latest
    command: >
      volume
      -dir=/data/volume
      -master=master:9333
      -port=9340
      -max=0
      -readMode=memory
      -index=memory
    volumes:
      - ./data/volume:/data/volume
    ports:
      - "9340:9340"
    networks:
      - seaweedfs
    deploy:
      replicas: 6
      placement:
        constraints:
          - node.labels.role == storage

  filer:
    image: chrislusf/seaweedfs:latest
    command: >
      filer
      -master=master:9333
      -ip=filer
      -port=8888
    ports:
      - "8888:8888"
    networks:
      - seaweedfs
    deploy:
      replicas: 3
    depends_on:
      - master

  s3:
    image: chrislusf/seaweedfs:latest
    command: >
      s3
      -filer=filer:8888
      -ip=s3
      -port=8333
      -domainName=s3.example.com
    environment:
      - AWS_ACCESS_KEY_ID=admin
      - AWS_SECRET_ACCESS_KEY=key
    ports:
      - "8333:8333"
    networks:
      - seaweedfs
    deploy:
      replicas: 3
    depends_on:
      - filer

networks:
  seaweedfs:
    driver: overlay
```

## 2. Kubernetes 配置

### 2.1 Master StatefulSet

```yaml
# k8s/master-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: seaweedfs-master
  namespace: seaweedfs
spec:
  serviceName: seaweedfs-master
  replicas: 3
  selector:
    matchLabels:
      app: seaweedfs-master
  template:
    metadata:
      labels:
        app: seaweedfs-master
    spec:
      containers:
      - name: master
        image: chrislusf/seaweedfs:latest
        command:
        - weed
        - master
        - -mdir=/data/master
        - -port=9333
        - -volumeSizeLimitMB=1024
        - -defaultReplication=001
        ports:
        - containerPort: 9333
          name: http
        volumeMounts:
        - name: data
          mountPath: /data/master
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "1000m"
            memory: "1Gi"
        livenessProbe:
          httpGet:
            path: /cluster/status
            port: 9333
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /cluster/status
            port: 9333
          initialDelaySeconds: 5
          periodSeconds: 5
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
---
apiVersion: v1
kind: Service
metadata:
  name: seaweedfs-master
  namespace: seaweedfs
spec:
  ports:
  - port: 9333
    targetPort: 9333
    name: http
  clusterIP: None
  selector:
    app: seaweedfs-master
```

### 2.2 Volume StatefulSet

```yaml
# k8s/volume-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: seaweedfs-volume
  namespace: seaweedfs
spec:
  serviceName: seaweedfs-volume
  replicas: 6
  selector:
    matchLabels:
      app: seaweedfs-volume
  template:
    metadata:
      labels:
        app: seaweedfs-volume
    spec:
      containers:
      - name: volume
        image: chrislusf/seaweedfs:latest
        command:
        - weed
        - volume
        - -dir=/data/volume
        - -master=seaweedfs-master:9333
        - -port=9340
        - -max=0
        - -readMode=memory
        - -index=memory
        ports:
        - containerPort: 9340
          name: http
        volumeMounts:
        - name: data
          mountPath: /data/volume
        resources:
          requests:
            cpu: "1000m"
            memory: "2Gi"
          limits:
            cpu: "2000m"
            memory: "4Gi"
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 100Gi
      storageClassName: fast-ssd
```

### 2.3 S3 Gateway Deployment

```yaml
# k8s/s3-gateway-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: seaweedfs-s3
  namespace: seaweedfs
spec:
  replicas: 3
  selector:
    matchLabels:
      app: seaweedfs-s3
  template:
    metadata:
      labels:
        app: seaweedfs-s3
    spec:
      containers:
      - name: s3
        image: chrislusf/seaweedfs:latest
        command:
        - weed
        - s3
        - -filer=seaweedfs-filer:8888
        - -port=8333
        - -domainName=s3.example.com
        env:
        - name: AWS_ACCESS_KEY_ID
          value: "admin"
        - name: AWS_SECRET_ACCESS_KEY
          value: "key"
        ports:
        - containerPort: 8333
          name: s3
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "1000m"
            memory: "1Gi"
        livenessProbe:
          httpGet:
            path: /health
            port: 8333
          initialDelaySeconds: 10
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: seaweedfs-s3
  namespace: seaweedfs
spec:
  type: LoadBalancer
  ports:
  - port: 8333
    targetPort: 8333
    name: s3
  selector:
    app: seaweedfs-s3
```

## 3. IAM 配置

### 3.1 基础 IAM 配置

```json
// /etc/seaweedfs/iam.json
{
  "users": [
    {
      "name": "admin",
      "credentials": [
        {
          "accessKey": "admin",
          "secretKey": "key"
        }
      ],
      "policies": ["admin"]
    },
    {
      "name": "app-user",
      "credentials": [
        {
          "accessKey": "AKIAIOSFODNN7EXAMPLE",
          "secretKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        }
      ],
      "policies": ["read-write-bucket1"]
    },
    {
      "name": "readonly-user",
      "credentials": [
        {
          "accessKey": "AKIAI44QH8DHBEXAMPLE",
          "secretKey": "je7MtGbClwBF/2Zp9Utk/h3yCo8nvbEXAMPLEKEY"
        }
      ],
      "policies": ["readonly"]
    }
  ],
  "policies": [
    {
      "name": "admin",
      "statements": [
        {
          "effect": "allow",
          "actions": ["s3:*"],
          "resources": ["*"]
        }
      ]
    },
    {
      "name": "read-write-bucket1",
      "statements": [
        {
          "effect": "allow",
          "actions": [
            "s3:GetObject",
            "s3:PutObject",
            "s3:DeleteObject"
          ],
          "resources": ["arn:aws:s3:::bucket1/*"]
        },
        {
          "effect": "allow",
          "actions": ["s3:ListBucket"],
          "resources": ["arn:aws:s3:::bucket1"]
        }
      ]
    },
    {
      "name": "readonly",
      "statements": [
        {
          "effect": "allow",
          "actions": [
            "s3:GetObject",
            "s3:ListBucket"
          ],
          "resources": ["*"]
        }
      ]
    }
  ]
}
```

### 3.2 启动时加载 IAM 配置

```bash
# 方式 1: 指定配置文件
weed s3 -iamConfigPath=/etc/seaweedfs/iam.json ...

# 方式 2: 环境变量
export SEAWEED_IAM_CONFIG=/etc/seaweedfs/iam.json
weed s3 ...
```

## 4. Nginx 反向代理配置

### 4.1 S3 Gateway 代理

```nginx
# /etc/nginx/conf.d/seaweedfs-s3.conf
upstream seaweedfs_s3 {
    least_conn;
    server 10.0.1.1:8333;
    server 10.0.1.2:8333;
    server 10.0.1.3:8333;
    keepalive 32;
}

server {
    listen 80;
    server_name s3.example.com;
    
    # 重定向到 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name s3.example.com;
    
    ssl_certificate /etc/ssl/certs/seaweedfs.crt;
    ssl_certificate_key /etc/ssl/private/seaweedfs.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # 客户端最大上传大小
    client_max_body_size 5G;
    
    # 超时设置
    proxy_connect_timeout 60s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
    
    location / {
        proxy_pass http://seaweedfs_s3;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        
        # 禁用缓冲（适合大文件）
        proxy_buffering off;
        proxy_request_buffering off;
    }
    
    # 健康检查
    location /health {
        proxy_pass http://seaweedfs_s3;
        access_log off;
    }
}
```

### 4.2 Filer UI 代理

```nginx
# /etc/nginx/conf.d/seaweedfs-filer.conf
upstream seaweedfs_filer {
    least_conn;
    server 10.0.2.1:8888;
    server 10.0.2.2:8888;
    server 10.0.2.3:8888;
}

server {
    listen 80;
    server_name filer.example.com;
    
    location / {
        proxy_pass http://seaweedfs_filer;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## 5. Prometheus 监控配置

### 5.1 Prometheus 配置

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'seaweedfs-master'
    static_configs:
      - targets:
        - '10.0.3.1:9333'
        - '10.0.3.2:9333'
        - '10.0.3.3:9333'
    metrics_path: '/metrics'
    
  - job_name: 'seaweedfs-filer'
    static_configs:
      - targets:
        - '10.0.2.1:8888'
        - '10.0.2.2:8888'
        - '10.0.2.3:8888'
    metrics_path: '/metrics'
    
  - job_name: 'seaweedfs-volume'
    static_configs:
      - targets:
        - '10.0.4.1:9340'
        - '10.0.4.2:9340'
        - '10.0.4.3:9340'
        - '10.0.4.4:9340'
        - '10.0.4.5:9340'
        - '10.0.4.6:9340'
    metrics_path: '/metrics'
    
  - job_name: 'seaweedfs-s3'
    static_configs:
      - targets:
        - '10.0.1.1:8333'
        - '10.0.1.2:8333'
        - '10.0.1.3:8333'
    metrics_path: '/metrics'
```

### 5.2 AlertManager 配置

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'feishu'

receivers:
  - name: 'feishu'
    webhook_configs:
      - url: 'http://feishu-webhook-url'
        send_resolved: true

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname']
```

## 6. 系统优化配置

### 6.1 Linux 内核参数

```bash
# /etc/sysctl.d/99-seaweedfs.conf
# 文件描述符
fs.file-max = 1000000

# 网络优化
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.core.netdev_max_backlog = 65535
net.ipv4.tcp_max_tw_buckets = 65535

# TCP 优化
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 1200
net.ipv4.tcp_keepalive_probes = 5
net.ipv4.tcp_keepalive_intvl = 15

# 内存优化
vm.dirty_ratio = 10
vm.dirty_background_ratio = 5
vm.swappiness = 1

# 应用配置
sysctl -p /etc/sysctl.d/99-seaweedfs.conf
```

### 6.2 用户限制

```bash
# /etc/security/limits.d/99-seaweedfs.conf
seaweedfs  soft  nofile  1000000
seaweedfs  hard  nofile  1000000
seaweedfs  soft  nproc   65535
seaweedfs  hard  nproc   65535
seaweedfs  soft  memlock unlimited
seaweedfs  hard  memlock unlimited
```

### 6.3 磁盘挂载选项

```bash
# /etc/fstab
# SSD 优化挂载
/dev/sda1  /data  ext4  noatime,nodiratime,discard  0  2

# 或 NVMe
/dev/nvme0n1p1  /data  ext4  noatime,nodiratime  0  2
```

---

*最后更新：2026-03-10*
