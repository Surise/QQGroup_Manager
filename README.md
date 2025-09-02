# 天鱼群管系统

一个基于Python和OneBot协议的QQ群管理工具，提供关键词过滤、自动处理、欢迎新成员等功能。

## 功能特点

- **关键词过滤**: 自动检测并处理包含特定关键词的消息
- **多种处理方式**: 支持撤回消息、禁言用户、踢出群聊、自动回复等操作
- **欢迎新成员**: 自动发送欢迎消息给新加入群聊的成员
- **图形界面**: 基于PyQt5和Web技术的现代化用户界面
- **异步处理**: 使用多线程和队列技术确保高并发处理能力
- **易于配置**: 通过Web界面轻松管理关键词和操作规则

## 系统架构

```
天鱼群管系统
├── PyQt5 GUI (主程序界面)
├── Flask Web服务 (提供管理界面)
├── OneBot API (与QQ机器人通信)
└── JSON配置文件 (存储规则和设置)
```

## 安装说明

### 环境要求

- Python 3.7 或更高版本
- 支持OneBot协议的QQ机器人框架（如go-cqhttp）
- Windows 7 或更高版本

### 安装步骤

1. 克隆或下载本项目到本地
2. 安装依赖包：
   ```bash
   pip install -r requirements.txt
   ```

### 依赖项

- Flask==2.3.2
- requests==2.3.1
- PyQt5==5.15.9
- PyQtWebEngine==5.15.6
- werkzeug==3.1.3

## 使用方法

### 运行程序

```bash
python run.py
```

程序启动后会自动打开图形界面窗口，同时在后台运行Flask Web服务。

### 访问管理界面

在程序运行时，可以通过以下方式访问Web管理界面：
1. 在程序窗口中操作（内嵌浏览器）
2. 直接在浏览器中访问 http://127.0.0.1:8080

### 配置说明

#### 关键词配置 (keywords.json)

```json
[
  {
    "keyword": "关键词内容",
    "action": ["操作类型1", "操作类型2"],
    "reply": "回复内容（当action包含reply时）",
    "duration": 禁言时长（秒，当action包含ban时）
  }
]
```

支持的操作类型：
- `recall`: 撤回消息
- `ban`: 禁言用户
- `kick`: 踢出群聊
- `reply`: 自动回复

#### 欢迎消息配置 (welcome_config.json)

```json
{
  "enabled": true/false,
  "message": "欢迎消息内容"
}
```

### 打包为可执行文件

运行以下命令将程序打包为Windows可执行文件：

```bash
python build_exe.py
```

打包后的exe文件将位于 `dist` 目录中。

## 注意事项

1. 确保OneBot机器人服务正在运行且监听在 `http://localhost:3000`
2. 程序需要管理员权限以确保所有功能正常运行
3. 修改配置文件后可能需要重启程序才能生效
4. 在生产环境中使用时，请注意网络安全和权限控制

## 项目结构

```
src/
├── main.py          # 程序入口和主界面
├── bot.py           # 核心逻辑和API处理
├── run.py           # 运行脚本
├── build_exe.py     # 打包脚本
├── keywords.json    # 关键词配置文件
├── welcome_config.json  # 欢迎消息配置文件
├── requirements.txt # 依赖列表
├── static/          # Web静态资源
├── templates/       # Web模板文件
```

## 许可证

本项目仅供学习和参考使用。