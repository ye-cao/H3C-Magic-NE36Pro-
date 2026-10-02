# H3C Magic NE36Pro — Home Assistant 集成

把 H3C Magic **NE36Pro** 路由器（AP / 路由模式均可）接入 Home Assistant：
监控工作状态、在线设备、CPU/内存，并可一键**重启**、**开关 WiFi**。

> 实测固件：`NE36ProV100R002`，设备 `192.168.101.247`。
> API 已实机逆向并验证（H3C Magic `esps` JSON-RPC + `wizard` 免登录端点）。

## 功能

| 实体 | 类型 | 说明 |
|---|---|---|
| 固件版本 / CPU 使用率 / 内存使用率 / 运行时间 | sensor | 设备资源状态（需登录） |
| 在线设备数 / 2.4G / 5G / 有线设备数 | sensor | 客户端统计（需登录） |
| WiFi 2.4G SSID / WiFi 5G SSID | sensor | 当前 SSID（需登录） |
| NTP 模式 / 工作模式 | sensor | 网络配置（NTP 需登录，工作模式免登录） |
| WiFi 2.4G 已启用 / WiFi 5G 已启用 / 指示灯 | binary_sensor | 开关状态 |
| WiFi 2.4G / WiFi 5G | switch | 开关 WiFi（保留 SSID/密码，只改启用位） |
| 重启 | button | 触发设备重启 |
| 已连接客户端 | device_tracker | 每客户端一个 presence 实体（自动增删） |

## 安装

### 方式 A：HACS 自定义仓库
1. HACS → 集成 → 右上 ⋮ → **自定义仓库**
2. 仓库地址填本仓库，`类别` 选 **集成**
3. 搜索 **H3C Magic NE36Pro** 并安装，重启 HA

### 方式 B：手动
把 `custom_components/ne36pro/` 整个目录复制到 HA 的 `config/custom_components/ne36pro/`，
重启 HA。

## 配置
设置 → 设备与服务 → 添加集成 → 搜 **H3C Magic NE36Pro**，填入：
- **主机地址**：如 `192.168.101.247`
- **用户名**：默认 `user`
- **密码**：管理密码

> 凭据仅存于 HA 配置项（加密存储），不会写入任何文件。

## 实现要点（给想改的人）
- 认证：`POST /api/login/auth` → `data.session`，后续 `/api/esps` 带 `AUTHENTICATION` 头。
- 读取：`esps` 端点**请求体必须是 JSON 数组** `[{object,method,id,param}]`（裸对象会被拒、返回空体）。
  每个调用单独发一个请求并并发 `gather`（实测 9 个调用的批量数组只回 1 个结果，故逐调用）。
- 免登录：`/api/wizard/getBasicInfo`、`getNetworkStatus` 无需 token。
- 轮询间隔：30 秒（`const.py` 的 `UPDATE_INTERVAL`）。

## 验证
集成 API 客户端已用真实路由器端到端验证：登录、全部读 RPC 解析、WiFi 关/开+恢复均通过。
