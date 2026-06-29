# Hermes QQ Profile Switch

为 Hermes QQ Bot 聊天通道添加 profile 切换功能。让你在 QQ 中直接切换 Hermes profile，无需重启 CLI。

## 功能

- **`/profile`** — 查看当前 profile、列出所有可用 profile
- **`/profile list`** — 列出所有 profile
- **`/profile use <name>`** — 切换到指定 profile（自动重启 gateway）
- **`/profile-switch`** — 备选命令，效果同上

## 工作原理

Hermes 的 profile 机制基于进程级 `HERMES_HOME` 环境变量，切换 profile 需要 **重启 gateway 进程**。

切换流程：
1. Hook 拦截 `/profile use <name>` 命令
2. 写入 `~/.hermes/active_profile` 持久化切换
3. 返回成功消息给 QQ 用户
4. 发送 `SIGUSR1` 给 gateway 进程
5. Gateway 优雅排空现有会话（最多 180s）→ 自动重启加载新 profile

## 安装

### 方式一：快速安装

```bash
git clone https://github.com/suqiguniang/hermes_qq_profile_switch.git
cd hermes_qq_profile_switch
bash install.sh
```

### 方式二：手动安装

```bash
# 1. 安装 Hook（拦截 /profile 命令）
mkdir -p ~/.hermes/hooks/command-profile
cp hooks/command-profile/HOOK.yaml ~/.hermes/hooks/command-profile/
cp hooks/command-profile/handler.py ~/.hermes/hooks/command-profile/

# 2. 安装 Plugin（注册 /profile-switch 命令）
mkdir -p ~/.hermes/plugins/qqbot-profile-switch
cp plugins/qqbot-profile-switch/plugin.yaml ~/.hermes/plugins/qqbot-profile-switch/
cp plugins/qqbot-profile-switch/__init__.py ~/.hermes/plugins/qqbot-profile-switch/

# 3. 启用插件（修改 ~/.hermes/config.yaml）
# 在 plugins.enabled 列表中添加 qqbot-profile-switch
```

### 3. 重启 Gateway

```bash
hermes gateway restart
```

## 使用

在 QQ 对话中发送：

| 命令 | 效果 |
|------|------|
| `/profile` | 显示当前 profile + 可用 profile 列表 |
| `/profile list` | 列出所有可用 profile |
| `/profile use <name>` | 切换到指定 profile（gateway 将重启） |
| `/profile help` | 显示帮助 |
| `/profile-switch ...` | 备选命令，同上 |

### 示例

```
你: /profile
Bot: Current profile: default

Available profiles:
  • coder  (AI agent with coding skills)
  • default  ← current

Usage: /profile use <name>
Tip: Switching profiles will restart the gateway.

你: /profile use coder
Bot: Switched to profile 'coder'. Gateway restarting now...
```

## 前置条件

- 已配置且正常运行 Hermes QQ Bot 通道
- Hermes v0.16.0+
- 至少两个可用 profile（`hermes profile create <name>` 创建）

## 项目结构

```
hermes_qq_profile_switch/
├── hooks/command-profile/          # Gateway Hook
│   ├── HOOK.yaml                   #   事件声明 (command:profile)
│   └── handler.py                  #   拦截处理逻辑
├── plugins/qqbot-profile-switch/   # 用户 Plugin
│   ├── plugin.yaml                 #   插件声明
│   └── __init__.py                 #   注册 /profile-switch 命令
├── install.sh                      # 一键安装脚本
└── README.md
```

## 技术细节

### Hook vs Plugin

- **Hook** (`~/.hermes/hooks/`) — 使用 Hermes Gateway 的 `HookRegistry` 系统拦截 `command:profile` 事件，在**内置 `/profile` 命令之前**执行
- **Plugin** (`~/.hermes/plugins/`) — 使用 `PluginContext.register_command()` 注册 `/profile-switch` 作为无冲突的备选命令

两个组件独立工作，都可以单独使用。

### 如何切换 Profile 后保留插件

切换 profile 后，新 profile 的 `~/.hermes/profiles/<name>/` 目录下的 `hooks/` 和 `plugins/` 是独立的。如需在新 profile 中也保留此功能，请在新 profile 中重复安装步骤。或者在克隆 profile 时包含这些文件。

## License

MIT
