# MusicWeb Docker 运行包说明

## 适用场景

本目录用于生成、发布和运行 MusicWeb Docker 完整运行包。用户电脑只需要安装 Docker Desktop，不需要复制项目源码、SQL 或模型文件。

公开发布包含两条运行路径：

- Docker Desktop GUI：拉取 `junfu26/musicweb-all-in-one` 后点击 Run。
- 命令行标准版：下载 `docker-compose.release.yml` 与 `.env.release.example`，由 Compose 自动拉取 `junfu26/musicweb-*` 镜像。

运行包包含：

- Java Web 服务
- MySQL 数据库服务
- Redis 缓存服务
- Node.js 统一音乐 API
- QQ 音乐 FastAPI 服务
- UnblockNeteaseMusic 解灰服务
- Python 推荐刷新容器
- `Data/musicweb.sql`
- `Project/MusicMode/Mode` 模型产物

不包含 `Data/kkbox-music-recommendation-challenge.zip`。

## 必填配置

发布版不会内置 `secrets.txt`、网易云 Cookie、QQ 音乐 Cookie、邮箱授权码或 Last.fm Key。用户必须在运行前填写以下配置，任一缺失都会导致容器拒绝启动：

```env
DB_PASSWORD=
MYSQL_ROOT_PASSWORD=
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_FROM=
LASTFM_API_KEY=
LASTFM_SHARED_SECRET=
NETEASE_COOKIE=
QQ_MUSIC_COOKIE=
```

## 隐私与公开发布风险

当前方案按项目要求仅在离线打包脚本中清理 `appeals.contact_email` 字段。`users` 表、播放历史、推荐反馈等业务数据保持当前项目结果。若将该 SQL 公开发布，账号字段和弱口令示例会随运行包分发。此风险必须在 GitHub Release 说明中标红。

## 电脑2 Docker Desktop GUI 运行

1. 打开 Docker Desktop。
2. 左侧进入 `Images`。
3. 搜索并拉取：

```text
junfu26/musicweb-all-in-one
```

4. 点击 `Run`。
5. 端口设置：

```text
Host port: 8082
Container port: 8082
```

6. 在 Environment variables 中添加全部必填配置。
7. 点击 `Run`。
8. 浏览器访问：

```text
http://localhost:8082/musicweb/
```

## 电脑2命令行标准版运行

推荐在 PowerShell 中执行下面这一段命令。脚本会自动创建 `musicweb-docker` 目录，下载发布版 Compose 文件和 `.env` 配置模板，打开记事本让用户填写 Cookie、密钥和邮箱授权码，然后启动容器。

```powershell
Invoke-WebRequest `
  -Uri "https://raw.githubusercontent.com/JF-j-f/Graduation-project-design/main/docker/scripts/install-release.ps1" `
  -OutFile "$env:TEMP\musicweb-install.ps1"

powershell -ExecutionPolicy Bypass -File "$env:TEMP\musicweb-install.ps1"
```

如需手动下载文件，也可以执行：

```powershell
mkdir musicweb-docker
cd musicweb-docker

Invoke-WebRequest `
  -Uri "https://raw.githubusercontent.com/<你的GitHub用户>/<仓库名>/main/docker-compose.release.yml" `
  -OutFile "docker-compose.release.yml"

Invoke-WebRequest `
  -Uri "https://raw.githubusercontent.com/<你的GitHub用户>/<仓库名>/main/docker/.env.release.example" `
  -OutFile ".env"

notepad .env
docker compose --env-file .env -f docker-compose.release.yml up -d
```

访问入口：

```text
http://localhost:8082/musicweb/
```

## 推荐刷新

容器启动后，可手动运行推荐刷新：

```powershell
docker compose --env-file docker/private/.env exec recommender `
  python Project/serving/refresh_song_stats.py

docker compose --env-file docker/private/.env exec recommender `
  python Project/serving/sync_recs_v3.py
```

推荐刷新依赖 `Project/MusicMode/Mode` 下的模型产物。公开下载时建议将模型产物作为单独资源包提供，再解压回同一路径。

## 离线包构建

本地开发版仍可使用 `docker-compose.yml`。公开发布镜像使用：

```powershell
powershell -ExecutionPolicy Bypass -File docker\scripts\build-release.ps1
powershell -ExecutionPolicy Bypass -File docker\scripts\push-release.ps1
```

发布前静态检查：

```powershell
powershell -ExecutionPolicy Bypass -File docker\scripts\test-release.ps1
```

`build-release.ps1` 会：

- 构建 `junfu26/musicweb-*` 镜像
- 复制并清理 `Data/musicweb.sql` 中的 `appeals.contact_email`
- 将 `Project/MusicMode/Mode` 打入 `junfu26/musicweb-data`
- 构建 `junfu26/musicweb-all-in-one`

## 停止服务

```powershell
docker compose --env-file .env -f docker-compose.release.yml down
```
