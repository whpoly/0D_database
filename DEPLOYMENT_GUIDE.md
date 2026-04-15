# 0D Database 从头到尾完整落地指南（Development + Deployment）

本文档是本项目的完整执行手册，目标是让你从一台新服务器开始，最终稳定提供公网访问，并具备后续扩展到几千条材料数据的能力。

文档覆盖：

- 项目级核对结论（基于当前仓库文件）
- 从 0 到上线的逐步命令
- Nginx + Gunicorn 的正确生产拓扑
- 防扫描、防误配、排障与回滚
- 长期扩展（PostgreSQL、缓存、离线预计算）

---

## 1. 项目核对结果（已检查）

下面这些结论来自当前仓库关键文件核对：

1. 入口应用与环境变量
- `main.py` 会自动读取 `.env`，支持 `ZERO_DB_*` 配置。
- 默认开发端口是 `8050`。
- 数据路径支持相对路径或绝对路径。

2. Gunicorn 生产配置
- `gunicorn.conf.py` 当前默认是 `127.0.0.1:8050`。
- 推荐启动方式：`gunicorn -c gunicorn.conf.py` 或 `./scripts/run_prod.sh`。

3. Nginx 模板
- `deploy/nginx/zerodb.conf.example` 已可无域名使用（`server_name _`）。
- 已包含基础限流（`limit_req` / `limit_conn`）和 `/healthz`。

4. systemd 模板
- `deploy/systemd/zerodb.service.example` 可直接复用，但路径需要按你服务器实际路径修改。

5. 文档一致性提示
- `README.md` 中还有旧示例 `ZERO_DB_GUNICORN_BIND=0.0.0.0:80 ...`，生产不建议这样做。
- 生产应坚持：Gunicorn 只监听 `127.0.0.1:8050`，由 Nginx 对外监听。

---

## 2. 目标生产拓扑（必须遵守）

1. 用户访问 `http://<公网IP>/`
2. Nginx 监听 `0.0.0.0:80`（以及后续 `443`）
3. Nginx 反向代理到 `127.0.0.1:8050`
4. Gunicorn 仅监听 `127.0.0.1:8050`

关键原则：

- 不要让 Gunicorn 绑定 `0.0.0.0`
- 不要在安全组/防火墙放行 `8050`

---

## 3. 前置条件与资源建议

系统建议：

- Ubuntu 22.04/24.04
- 2 vCPU / 4-8 GB RAM（起步）
- 磁盘：
  - 20-40 GB：仅 Web + `dos_bs`
  - 100 GB+：同时保存原始 DFT 文件

云侧网络：

- 安全组放行入站：`22`, `80`（后续 HTTPS 再放 `443`）
- 不放行 `8050`

---

## 4. 本地开发（可选）

### 4.1 Linux / macOS

```bash
conda create -n web_2 python=3.11 -y
conda activate web_2
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

访问：

```text
http://127.0.0.1:8050
```

### 4.2 Windows（仓库自带脚本）

```powershell
Copy-Item .env.example .env
.\scripts\run_dev.ps1 -CondaEnv web_2
```

---

## 5. 生产部署：从零到上线

以下步骤按顺序执行即可。

### 5.1 拉代码并安装系统依赖

```bash
cd /root
git clone <你的仓库地址> 0D_database
cd /root/0D_database

sudo apt update
sudo apt install -y nginx
```

### 5.2 创建 Python 环境并安装依赖

```bash
conda create -n web_2 python=3.11 -y
conda activate web_2
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5.3 生成并检查 `.env`

```bash
cd /root/0D_database
cp -n .env.example .env
```

至少确认这些关键值：

```env
ZERO_DB_ENV=production
ZERO_DB_HOST=127.0.0.1
ZERO_DB_PORT=8050
ZERO_DB_DEBUG=0
ZERO_DB_DEV_TOOLS_UI=0

ZERO_DB_DATA_PATH=ZeroDB_test_data.json
ZERO_DB_RADIUS_PATH=atomic_radius.json
ZERO_DB_DFT_ROOT_DIR=ZeroDB_test_data/ZeroDB_test_data
ZERO_DB_DOS_BS_DIR=dos_bs

ZERO_DB_GUNICORN_BIND=127.0.0.1:8050
ZERO_DB_GUNICORN_WORKERS=2
ZERO_DB_GUNICORN_THREADS=1
ZERO_DB_GUNICORN_TIMEOUT=300
ZERO_DB_GUNICORN_ACCESSLOG=-
ZERO_DB_GUNICORN_ERRORLOG=-
ZERO_DB_GUNICORN_LOGLEVEL=info
```

快速校验：

```bash
grep -E '^ZERO_DB_(ENV|HOST|PORT|DEBUG|GUNICORN_BIND)=' .env
```

注意：

- 不建议用不严谨的 `sed` 批量替换 `.env`，容易把值拼坏。

### 5.4 手工启动 Gunicorn 验证

```bash
cd /root/0D_database
conda activate web_2
gunicorn -c gunicorn.conf.py
```

新开终端检查监听：

```bash
ss -lntp | grep 8050
```

期望是：`127.0.0.1:8050`。

### 5.5 启用 Nginx

```bash
cd /root/0D_database
sudo cp deploy/nginx/zerodb.conf.example /etc/nginx/sites-available/zerodb
sudo ln -sf /etc/nginx/sites-available/zerodb /etc/nginx/sites-enabled/zerodb
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl enable nginx
```

常见错误：

```text
cp: cannot stat 'zerodb.conf.example'
```

原因：路径写错，正确路径是 `deploy/nginx/zerodb.conf.example`。

### 5.6 防火墙与安全组

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status
```

同时确认云安全组放行 `80/443`。

### 5.7 上线验证

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1/healthz

PUBLIC_IP=$(curl -4s https://ifconfig.me)
echo "$PUBLIC_IP"
curl -sS -o /dev/null -w '%{http_code}\n' "http://${PUBLIC_IP}/healthz"

ss -lntp | grep -E '(:80|:8050)\b'
```

期望：

- `:80` 由 Nginx 监听
- `:8050` 仅 `127.0.0.1` 上由 Gunicorn 监听
- 健康检查返回 `200`

外部电脑访问：

```text
http://<公网IP>/
```

---

## 6. systemd 托管（生产推荐）

手工跑通后，交给 systemd：

```bash
cd /root/0D_database
sudo cp deploy/systemd/zerodb.service.example /etc/systemd/system/zerodb.service
sudo nano /etc/systemd/system/zerodb.service
```

重点修改这 5 项：

1. `User`
2. `Group`
3. `WorkingDirectory`
4. `EnvironmentFile`
5. `ExecStart`（必须是你真实 conda 环境里的 gunicorn 绝对路径）

示例（按你当前 root + miniconda 习惯）：

```ini
[Service]
User=root
Group=www-data
WorkingDirectory=/root/0D_database
EnvironmentFile=/root/0D_database/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/root/miniconda3/envs/web_2/bin/gunicorn -c /root/0D_database/gunicorn.conf.py
Restart=always
RestartSec=5
```

启用：

```bash
sudo systemctl daemon-reload
sudo systemctl enable zerodb
sudo systemctl start zerodb
sudo systemctl status zerodb
```

---

## 7. 发布更新与回滚

### 7.1 正常更新流程

```bash
cd /root/0D_database
git pull
conda activate web_2
pip install -r requirements.txt
sudo systemctl restart zerodb
sudo systemctl reload nginx
```

验证：

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1/healthz
```

### 7.2 紧急回滚

```bash
cd /root/0D_database
git checkout <稳定版本tag或commit>
sudo systemctl restart zerodb
```

---

## 8. 实时监控与诊断

CPU/内存热点：

```bash
watch -n 1 "ps -eo pid,user,%cpu,%mem,cmd --sort=-%cpu | head -n 20"
```

80/8050 连接状态：

```bash
watch -n 1 "ss -antp | awk 'NR==1 || /:80\\>|:8050\\>/'"
```

查看 Gunicorn/Nginx 的 ESTABLISHED/CLOSE_WAIT：

```bash
watch -n 1 "lsof -nP -iTCP -sTCP:ESTABLISHED,CLOSE_WAIT | egrep 'COMMAND|gunicorn|nginx'"
```

服务日志：

```bash
sudo journalctl -u nginx -f
sudo journalctl -u zerodb -f
```

---

## 9. 常见问题与修复

### 9.1 Gunicorn 误暴露到公网

现象：`ss -lntp | grep 8050` 显示 `0.0.0.0:8050`。

原因：用了旧命令，例如：

```bash
gunicorn -w 2 -b 0.0.0.0:8050 main:server
```

修复：

1. 停掉旧进程
2. 确认 `.env` 中 `ZERO_DB_GUNICORN_BIND=127.0.0.1:8050`
3. 用 `gunicorn -c gunicorn.conf.py` 或 systemd 重启

### 9.2 外网访问不到

按顺序排查：

1. `systemctl is-active nginx`
2. `sudo nginx -t`
3. `ss -lntp | grep :80`
4. `ufw status` 是否放行 80
5. 云安全组是否放行 80

### 9.3 BS/DOS 页面为空

排查顺序：

1. `dos_bs/<material_id>/bs.json(.gz)` 与 `dos.json(.gz)` 是否存在
2. 若无缓存，检查原始目录是否有 `step_15_band_str_d3` / `step_16_dos_d3`
3. 检查 `vasprun.xml` 或 `vasprun.xml.gz` 是否存在

---

## 10. 数据与性能优化（当前项目可直接做）

### 10.1 压缩缓存文件

导出并压缩：

```bash
python scripts/export_bs_dos_json.py --gzip-output --backup-dir-suffix ''
```

压缩现有缓存：

```bash
python scripts/compress_bs_dos_cache.py --delete-originals
```

收益：

- 降低磁盘占用
- 降低 I/O 压力
- 改善详情页响应

### 10.2 规模增长判断

按当前样本粗估：

1. 1000 材料：DFT 文件约 53 GB
2. 3000 材料：DFT 文件约 159 GB
3. 5000 材料：DFT 文件约 265 GB

结论：核心瓶颈是原始 DFT 文件体积，不是元数据。

---

## 11. 第二阶段（几千材料）长期架构

当数据持续增长时，建议升级到：

1. PostgreSQL 存元数据（筛选/排序/分页）
2. 原始 DFT 文件迁移到对象存储或 NAS
3. BS/DOS 离线预计算，前端只读摘要结果
4. Redis 缓存热点材料详情与图数据
5. 首页改后端分页与服务端筛选

这样可显著提升并发稳定性和维护效率。

---

## 12. 最终上线检查清单

部署完成后逐条核对：

1. `nginx -t` 通过
2. `systemctl is-active nginx` 为 `active`
3. `systemctl is-active zerodb` 为 `active`
4. `ss -lntp` 中 Nginx 在 `:80`
5. `ss -lntp` 中 Gunicorn 仅在 `127.0.0.1:8050`
6. `curl http://127.0.0.1/healthz` 返回 `200`
7. 外部电脑可打开 `http://<公网IP>/`
8. 安全组未放行 `8050`

完成以上 8 项，即可认为生产落地完成。