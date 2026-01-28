# MusicWeb 服务启动操作手册

本手册将指导您如何启动 MusicWeb 项目的所有服务组件。

## 快速开始

### 方式一：一键启动（推荐）

在项目根目录下，双击运行或在终端执行：

```powershell
scripts\run_services.bat
```

脚本会自动按顺序启动以下服务：

1. **Redis 服务** - 缓存数据库
2. **Python QQ Music API** - QQ音乐接口服务 (端口 8000)
3. **Node.js 音乐 API** - 音乐数据接口 (端口 3000)
4. **Java Web 应用** - 主应用程序 (端口 8082)

当您看到以下输出时，说明所有服务启动成功：

```text
[INFO] Tomcat 10.x.x started on port [8082]
```

### 方式二：分步手动启动

如需分别查看各服务日志，请在**多个终端窗口**中分别执行：

#### 终端 1：启动 Redis

```powershell
scripts\start_redis.bat
```

#### 终端 2：启动 Python QQ Music API

```powershell
scripts\start_qq_api.bat
```

#### 终端 3：启动 Node.js 服务

```powershell
scripts\start.bat
```

#### 终端 4：启动 Java Web 应用

```powershell
scripts\mvnw.cmd package cargo:run
```

---

## 服务地址

| 服务 | 地址 |
|------|------|
| Web 应用 | <http://localhost:8082/musicweb/> |
| QQ Music API | <http://localhost:8000/docs> |
| Node.js API | <http://localhost:3000/health> |

## 测试账号

- **用户名**：`jf`
- **密码**：`123456`

---

## 服务启停

| 操作 | 命令 |
|------|------|
| 启动所有服务 | 双击 `scripts\run_services.bat` |
| 停止所有服务 | 双击 `scripts\stop_services.bat` |

> **提示**：`stop_services.bat` 会自动清理 Redis、Node.js、Python 和 Java 进程。

---

## 常见问题

### Q1: 控制台中文乱码

**A:** 脚本已自动设置 UTF-8 编码（`chcp 65001`）。如仍有乱码，请使用 CMD 命令提示符代替 PowerShell。

### Q2: 无法播放歌曲

**A:**

1. 确认 Node.js 服务 (端口 3000) 正在运行
2. 确认 Python API 服务 (端口 8000) 正在运行
3. 确认歌曲不是 VIP 专属或已下架
4. 检查浏览器控制台 (F12) 是否有报错

### Q3: Redis 连接失败

**A:** 确认 Redis 服务已启动。如未安装 Redis，请先安装后再运行启动脚本。

### Q4: 页面显示500错误

**A:** 可能是 JSP 编译失败，请尝试重启服务或检查 Tomcat 日志。
