# 0D Database Deployment Guide

## 1. 先说结论

这个项目现在已经是一个可以运行的 Dash 网站原型，不需要从零重新做一个网站。

但如果你要正式部署，并且后续材料数量会增长到几千条，建议分成两步做：

1. 第一阶段：先把当前 Dash 项目上线，尽快有一个可访问的网站。
2. 第二阶段：把数据层从本地 JSON + 本地文件夹，升级成数据库 + 文件存储，保证几千条材料时仍然稳定。

## 2. 当前项目适合什么部署方式

从代码结构看：

- `main.py` 已经是 Dash 网站入口。
- `server = app.server` 已经暴露了 WSGI server，可直接给 Gunicorn 使用。
- 当前数据来自：
  - `ZeroDB_test_data.json`
  - `atomic_radius.json`
  - `ZeroDB_test_data/ZeroDB_test_data/` 下的每个材料目录

这意味着当前项目最短上线路径不是“重写网站”，而是：

1. 把代码和数据放到 Linux 服务器。
2. 用 Conda 建一个空环境，再安装统一的 `requirements.txt`。
3. 用 Gunicorn 跑 `main:server`。
4. 用 Nginx 反向代理到你的域名。

## 3. 第一阶段：当前版本直接上线

### 3.1 推荐部署形态

推荐使用：

- 1 台 Linux 云服务器
- Ubuntu 22.04 或 24.04
- 2 vCPU / 8 GB RAM 起步
- 100 GB SSD 起步

如果你只展示当前这种测试规模，配置可以更低。
如果你后续要放原始 DFT 文件，磁盘要按数据量单独规划。

### 3.2 服务器上要做的事

#### 步骤 1：准备代码目录

```bash
cd /opt
git clone <your-repo-url> zerodb
cd zerodb
```

#### 步骤 2：建立 Conda 环境

```bash
conda create -n web_2 python=3.11 -y
conda activate web_2
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果你只是想先在本机快速验证应用能不能起来，那么最小安装其实只需要：

```bash
pip install crystal-toolkit
```

正式部署时则建议直接装 `requirements.txt`，这样 `gunicorn` 也会一起到位。

#### 步骤 3：先在服务器本机试跑

```bash
python main.py
```

本地确认能打开：

```text
http://127.0.0.1:8050
```

#### 步骤 4：改成生产启动方式

不要继续用 `python main.py` 作为正式线上服务。

改用：

```bash
conda activate web_2
gunicorn -w 2 -b 0.0.0.0:8050 main:server
```

说明：

- `main` 是模块名，对应 `main.py`
- `server` 是代码里已经暴露出来的 Flask/WGSI server
- `-w 2` 表示先开 2 个 worker，后面可按机器配置调到 2 到 4
- 如果部署环境报 `pourbaix` / `ELEMENTS_HO` 相关错误，再去对应环境的 `crystal_toolkit/components/pourbaix.py` 里补一个 `ELEMENTS_HO = {Element("H"), Element("O")}` 的兼容定义即可

#### 步骤 5：Nginx 反向代理

域名解析到服务器后，用 Nginx 把 80/443 转发到 8050。

示例思路：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8050;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

然后再配 SSL 证书。

### 3.3 第一阶段的优点和局限

优点：

- 改动最小
- 可以最快上线
- 适合先给导师、组内成员或合作方看

局限：

- 首页数据仍然来自本地 JSON
- 详情页仍然直接读本地 DFT 文件
- 数据更新时，通常要重新部署或重启应用
- 后续材料数变成几千条后，维护和性能都会开始吃力

## 4. 第二阶段：几千条材料时应该怎么改

### 4.1 为什么不能长期停留在现在的结构

当前实现有几个天然瓶颈：

1. 网站启动时一次性把 `ZeroDB_test_data.json` 全部读入内存。
2. 首页表格数据在应用启动时一次性生成。
3. 详情页会去材料目录里直接解析 `vasprun.xml` 或 `vasprun.xml.gz`。
4. 原始 DFT 文件和网站程序绑定在同一台机器上，不利于扩容和备份。

如果材料增长到几千条，最容易先出问题的不是“页面能不能打开”，而是：

- 数据更新流程混乱
- 查询越来越慢
- 磁盘越来越大
- 多 worker / 多实例部署时缓存不一致

### 4.2 适合几千条材料的推荐架构

推荐改成下面这个结构：

#### A. 元数据进入 PostgreSQL

把首页和详情页常用字段放进数据库，例如：

- `material_id`
- `pretty_formula`
- `chem_sys`
- `nsites`
- `nelements`
- `final_energy`
- `bandgap_energy`
- `total_magnetic_moment`
- `space_group`
- `structure_json`
- `partition_json`
- `created_at`
- `updated_at`

这样做的好处：

- 可以做真正的后端筛选、排序、分页
- 更新单条材料不需要重新生成整个 JSON
- 后面做 API 和后台管理也更容易

#### B. 原始文件单独存储

原始 DFT 目录不要继续完全依赖应用目录本地保存。

建议放到以下之一：

- 对象存储
- 独立文件服务器
- 实验室 NAS

数据库里只保存：

- 文件路径
- 材料 ID
- 文件类型
- 是否完成解析
- 解析后的摘要文件位置

#### C. BS / DOS 结果预计算

不要让网站每次打开详情页都去解析完整 `vasprun.xml(.gz)`。

更好的做法是离线预处理，生成轻量结果，例如：

- `bandstructure_summary.json`
- `dos_summary.json`
- 或直接生成可前端读取的 Plotly figure JSON

网站详情页只读取已经预处理好的摘要结果。

如果你还需要保留完整 `pdos`，也不要直接放未压缩的 `dos.json`。
当前项目已经可以读取 `bs.json.gz` 和 `dos.json.gz`，建议优先把缓存压缩后再部署。

例如：

```bash
python scripts/export_bs_dos_json.py --gzip-output --backup-dir-suffix ''
```

如果 `dos_bs/` 已经生成好了，也可以直接压缩现有缓存：

```bash
python scripts/compress_bs_dos_cache.py --delete-originals
```

这样会明显降低：

- 页面打开时间
- CPU 占用
- 多用户同时访问时的解析压力
- 硬盘占用

#### D. 首页表格改成后端分页

如果你继续使用 Dash 表格，建议把：

- `page_action="native"`
- `filter_action="native"`
- `sort_action="native"`

逐步改成后端回调驱动。

更进一步，可以直接迁移到 Dash AG Grid。

#### E. 增加缓存层

如果详情页访问较频繁，建议加 Redis 缓存：

- 缓存单个材料详情
- 缓存结构 JSON
- 缓存 BS / DOS 摘要结果

这样多 worker 时也更稳定，不会像 Python 进程内 `lru_cache` 一样各自为战。

## 5. 你这个项目到几千条时，大概要多大

按当前测试数据粗略外推：

- 7 个材料时，主 JSON 约 0.05 MB
- 7 个材料时，DFT 文件目录约 0.371 GB

线性估算：

- 1000 个材料：
  - 元数据约 7.1 MB
  - DFT 文件约 53.0 GB
- 3000 个材料：
  - 元数据约 21.4 MB
  - DFT 文件约 159.0 GB
- 5000 个材料：
  - 元数据约 35.7 MB
  - DFT 文件约 265.0 GB

所以结论很明确：

- 元数据不是主要压力
- 原始 DFT 文件才是主要压力

## 6. 我建议你的实施顺序

### 方案 A：最快上线

适合现在就想先有一个网站地址：

1. 保持当前 Dash 架构不动
2. 上 Linux 服务器
3. 用 Gunicorn + Nginx 部署
4. 先支持几十到几百条材料

### 方案 B：面向几千条材料的正式版本

适合准备长期维护：

1. 保留 Dash 前端界面
2. 把 JSON 迁移到 PostgreSQL
3. 把 DFT 原始文件迁移到独立存储
4. 增加离线解析脚本，预生成 BS / DOS 摘要
5. 把首页表格改成后端分页、后端筛选、后端排序
6. 再做正式线上部署

## 7. 对你这个项目最实用的判断

如果你的目标是：

- 先让老师或合作者能打开网站看数据

那么现在就可以直接部署当前版本。

如果你的目标是：

- 真正做成一个长期维护的 0D 材料数据库网站
- 后面材料数稳定增长到几千条

那么建议你把当前项目看作：

- 一个很好的前端原型
- 一个可以继续沿用的交互雏形
- 但还不是最终的数据架构

## 8. 下一步可以直接做什么

如果你准备继续推进，最推荐的下一步只有两个：

1. 我直接帮你把这个项目补成“可部署版本”
   - 增加 `gunicorn` 启动配置
   - 增加 Nginx 配置样例
   - 增加 `.env` 和路径配置
   - 增加部署文档

2. 我直接帮你开始做“几千材料版改造”
   - 先把 JSON 改成 PostgreSQL
   - 再把首页表格改成后端分页
   - 最后整理 DFT 文件和预处理流程

如果你愿意，我下一步可以直接继续帮你做第 1 套，先把这个项目整理成一个能上线的版本。
