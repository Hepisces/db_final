# Awesql (`awesql`)

`awesql` 是一款专为智能家居数据库设计的现代化命令行工具。它集数据导入、SQL执行、智能分析和高级可视化于一体，旨在提供一个强大、直观且用户友好的数据库交互体验。

本项目基于 Python, Typer, Rich, Plotly, 和 Mermaid.js 构建。

## 核心功能

-   **🚀 一键式数据管理**: 通过 `import-data` 和 `reset-db` 命令，轻松完成数据库的初始化和重置。
-   **📊 强大的查询与可视化**: 使用 `run` 命令执行任何SQL查询。
    -   自动为 `SELECT` 结果生成**交互式图表** (`.png` 格式)。
    -   以用户友好的树状结构展示**查询计划** (`EXPLAIN QUERY PLAN`)，并附带中文解释。
-   **✍️ AI 驱动的 SQL 助手**:
    -   `check`: 连接到外部API，对您的SQL查询进行语法检查和逻辑分析，并提供优化建议。
    -   `ask`: 利用本地大语言模型（如 `SQLCoder`），将自然语言问题直接转换成SQL查询。
-   **🗺️ 数据库结构洞察**:
    -   `tables`: 快速列出数据库中的所有数据表。
    -   `er`: 自动解析 `DDL.sql` 文件，生成并展示可视化的**实体-关系（E-R）图**。
-   **⚙️ 灵活的配置系统**: 通过 `config` 子命令，轻松管理AI模型和DDL文件路径等高级设置。

## 安装与配置

建议使用 `conda` 管理环境。

```bash
# 1. 创建并激活 Conda 环境
conda create -n awesql python=3.12 -y
conda activate awesql

# 2. 安装本工具 (两种模式可选)

# A) 标准安装 (不包含本地AI问答功能)
# 这将安装运行核心功能所需的所有库。
pip install -e .

# B) 完整安装 (包含所有功能)
# 这将额外安装 torch, transformers 等用于本地AI的库。
pip install -e '.[AI]'
```

> **可编辑模式** (`-e`) 安装后，您对源代码的任何修改都会立刻生效，无需重装。

## 使用指南

### 1. 导入数据
这是使用 `awesql` 的第一步。此命令会创建数据库，并根据 `DDL.sql` 定义的结构，从目录中的 `.sql` 文件导入数据。

```bash
# 从默认的 'Smart_Home_DATA' 目录导入
awesql import-data

# 从指定目录导入
awesql import-data --dir /path/to/your/data
```

### 2. 探索数据库
数据导入后，即可开始探索。

**列出所有表:**
```bash
awesql tables
```

**查看 E-R 图:**
此命令会生成一个 `er_diagram.html` 文件并自动在浏览器中打开。
```bash
awesql er
```

### 3. 执行查询
使用 `run` 命令执行任何标准SQL。

```bash
# 示例：查询不同设备类型的数量
awesql run "SELECT type, COUNT(*) FROM devlist GROUP BY type"
```
- 对于 `SELECT` 查询，工具会自动：
    1.  在终端打印**查询计划树**。
    2.  在终端显示**结果表格**（最多10行）。
    3.  生成一个 **PNG 图表**并自动打开。
- 对于数据修改操作 (如 `UPDATE`, `DELETE`)，需要管理员权限（详见下文）。

### 4. 使用 AI 助手

**检查 SQL (在线服务):**
```bash
awesql check "SELECT * FROM control WHERE status='on' ORDER BY timestamp DESC"
```
> 此功能依赖于一个外部API，无需本地模型。

**自然语言查询 (本地模型):**
此功能需要一个本地的AI模型来将自然语言翻译成SQL。

-   **步骤 1: 下载模型**
    我们推荐使用 `defog/sqlcoder-7b-2` 模型。您可以在 Hugging Face Hub 下载它。
    - **模型链接**: [defog/sqlcoder-7b-2](https://huggingface.co/defog/sqlcoder-7b-2)
    - 请将模型文件下载到本地任意目录。

-   **步骤 2: 配置模型路径**
    告诉 `awesql` 在哪里找到模型。
    ```bash
    # 使用绝对路径
    awesql config set-model-path /path/to/your/downloaded/sqlcoder_model
    ```
-   **步骤 3: 提问**
    ```bash
    awesql ask "近24小时内有多少次开灯操作?"
    ```

### 5. 管理员操作

**重置数据库:**
此操作将**删除**当前数据库文件，需要管理员权限。
```bash
awesql reset-db
```
执行时，系统会提示您输入管理员用户名和密码。

**管理员凭证:**
默认凭证为 `admin`/`123`。为了安全，建议通过设置环境变量来覆盖它们。

在您的 shell 配置文件 (如 `.bashrc`, `.zshrc`) 中添加:
```bash
export AWESQL_ADMIN_USER="your_secure_username"
export AWESQL_ADMIN_PASS="your_secure_password"
```
然后运行 `source ~/.zshrc` (或重启终端) 使其生效。

---
*祝您使用愉快！* 