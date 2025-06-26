# Awesql: SQL 查询可视化与分析工具

## 项目概述

`awesql` 是一个基于命令行的 SQL 查询执行、分析与可视化工具。本工具通过提供查询计划分析、结果可视化和数据库结构图生成等功能，辅助数据库研究和分析工作。

本项目采用 Python 语言实现，基于 SQLite 数据库引擎，结合 Typer、Rich、Plotly 和 Mermaid.js 等开源框架构建。

## 技术架构

本工具采用模块化设计，主要包含以下组件：

1. **数据库交互模块**：负责数据库连接、查询执行和结果获取
2. **查询计划分析模块**：解析 SQLite 的 EXPLAIN QUERY PLAN 输出，提供查询执行路径分析
3. **可视化引擎**：根据查询结果自动选择合适的图表类型进行可视化
4. **命令行接口**：提供统一的用户交互入口
5. **自然语言处理模块**（可选）：支持自然语言到 SQL 的转换功能

## 数据准备

数据已经上传到Google Drive, 可以通过以下链接下载, 并和代码文件放到同级目录即可使用

https://drive.google.com/drive/folders/1BCjw3aSsn971_VX0En4KYIbkVaLf0acN?usp=drive_link

## 安装方法

推荐使用 Conda 环境管理工具进行安装：

```bash
# 创建并激活环境
conda create -n awesql python=3.12 -y
conda activate awesql

# 安装选项

# 1. 克隆项目
git clone git@github.com:Hepisces/db_final.git

# 2. 进入项目目录
cd db_final

# 3. 基础安装（核心功能）
pip install -e .

# 4. 完整安装（包含text2sql组件）
pip install -e '.[AI]'

# 5. (推荐)将数据文件放到同级目录
```

## 功能与用法

### 数据库初始化

从 SQL 文件导入数据并初始化数据库, 如果你执行了5. 将数据文件放到同级目录, 则可以不必指定--dir参数, 同时默认的数据库名称为project2025

如果是自定义的数据, 请确保DDL文件的命名方式为`DDL.sql`, 并与其他文件放在同一文件夹下, 同时指定--dir参数为该文件夹路径

```bash
awesql import-data [--dir DATA_DIRECTORY] [--db-name DB_NAME]
```

### 数据库结构分析

列出数据库中的所有表：

```bash
awesql tables [--db-name DB_NAME]
```

生成数据库实体关系图：

```bash
awesql er [--dir DDL_DIRECTORY]
```

### 查询执行与分析

执行 SQL 查询并分析结果：

```bash
awesql run "SQL_QUERY" [--db-name DB_NAME]
```

执行此命令后，系统将：

1. 解析并显示查询计划，包含执行路径和中文解释
2. 执行查询并返回结果（限制显示前 10 行）
3. 根据查询类型自动生成可视化图表（保存为 PNG 格式）

### SQL 查询检查

分析 SQL 查询的正确性与优化空间：

```bash
awesql check "SQL_QUERY"
```

### 自然语言查询（需完整安装）

配置本地模型：

```bash
awesql config set-model-path /path/to/model
awesql config set-ddl-path /path/to/DDL.sql
```

执行自然语言查询：

```bash
awesql ask "自然语言问题"
```

### 数据库管理

重置数据库（需管理员权限）：

```bash
awesql reset-db [--db-name DB_NAME]
```

执行此命令时，系统会提示输入管理员用户名和密码。

**管理员凭证设置：**

默认的管理员凭证为：

- 用户名：`admin`
- 密码：`123`

出于安全考虑，强烈建议通过环境变量修改默认凭证：

```bash
# 在 Linux/macOS 中设置环境变量
export AWESQL_ADMIN_USER="自定义用户名"
export AWESQL_ADMIN_PASS="自定义密码"

# 在 Windows 命令提示符中设置环境变量
set AWESQL_ADMIN_USER=自定义用户名
set AWESQL_ADMIN_PASS=自定义密码

# 在 Windows PowerShell 中设置环境变量
$env:AWESQL_ADMIN_USER="自定义用户名"
$env:AWESQL_ADMIN_PASS="自定义密码"
```

为了使环境变量持久化，建议将这些设置添加到您的 shell 配置文件中（如 `.bashrc`、`.zshrc` 或 Windows 的系统环境变量设置）。

为了更好地展示这一套工具的作用，我们为每个操作都录了演示视频:[查看](demo.md)

## CLI命令

1. 数据库与环境管理

此类命令负责数据库的生命周期、数据导入以及环境配置。

| 命令 / 子命令 | 参数 | 描述 |
| :--- | :--- | :--- |
| `import-data` | `--dir <PATH>`<br>`--db-name <TEXT>` | **创建并填充数据库**。这是系统的主要初始化命令。它会首先删除同名的旧数据库，然后根据指定目录下的 `DDL.sql` 创建表结构，并导入该目录下的所有 `.sql` 数据文件。<br>`--dir` 指定数据源目录。<br>`--db-name` 可自定义数据库文件名。 |
| `reset-db` | `--user <TEXT>`<br>`--pass <TEXT>`<br>`--db-name <TEXT>` | **完全重置系统（需管理员权限）**。这是一个破坏性操作，会删除指定的数据库文件和 `awesql_config.json` 配置文件。<br>执行时会强制提示输入管理员用户名和密码。 |
| `config set-ddl-path` | `PATH` (必需) | **设置DDL文件路径**。为Text-to-SQL功能指定数据库模式定义（`DDL.sql`）文件的绝对路径，供AI理解表结构。 |
| `config set-model-path` | `PATH` (必需) | **设置本地模型路径**。指定一个本地HuggingFace模型目录的绝对路径，用于驱动Text-to-SQL功能。 |
| `config show` | `[无]` | **显示当前配置**。打印出当前 `awesql_config.json` 中保存的所有配置项，如模型路径和DDL文件路径。 |

2. 查询、分析与验证

此类命令是系统的核心功能，用于执行查询、进行AI辅助分析以及保障查询安全。

| 命令 / 子命令 | 参数 | 描述 |
| :--- | :--- | :--- |
| `run` | `QUERY` (必需)<br>`--db-name <TEXT>` | **执行SQL查询并可视化**。执行一个给定的SQL查询，并自动展示查询计划、结果表格，同时启动交互式图表生成流程。<br>使用 `--db-name` 可以指定要查询的数据库文件。 |
| `ask` | `QUESTION` (必需) | **自然语言转SQL**。将一个用自然语言描述的问题发送给大型语言模型（LLM），由其生成相应的SQL查询语句，并自动对生成的SQL进行安全检查。 |
| `check` | `QUERY` (必需)<br>`--db-name <TEXT>` | **检查SQL合法性**。对给定的SQL查询进行静态分析，检查是否存在潜在的危险操作（如`DROP`, `UPDATE`）和语法错误，并验证查询的表和列是否真实存在于数据库中。<br>使用 `--db-name` 指定用于验证的数据库。 |
| `tables` | `--db-name <TEXT>` | **列出所有表**。显示指定数据库中存在的所有数据表的名称。<br>使用 `--db-name` 指定目标数据库。 |

3. 可视化与导出

此类命令专注于数据的可视化呈现和导出。

| 命令 / 子命令 | 参数 | 描述 |
| :--- | :--- | :--- |
| `er` | `--dir <PATH>`<br>`--output <PATH>` | **生成E-R图**。解析指定目录下的 `DDL.sql` 文件，并生成一个基于Mermaid.js的HTML实体关系图。<br>`--dir` 指定DDL文件所在目录。<br>`--output` 指定输出的HTML文件路径。 |
| ( `run` 命令的一部分) | (交互式) | 在 `run` 命令成功执行后，**启动交互式图表生成器**。引导用户选择图表类型（柱状图、折线图等）、X/Y轴数据列以及分类维度，最终生成并保存图表图片。 |

## 技术实现细节

我们已在论文中详细阐述，这里不再赘述。

## 局限性

1. 当前版本仅支持 SQLite 数据库
2. 自然语言到 SQL 的转换功能依赖本地模型，需要较大计算资源
3. 可视化功能针对特定查询类型优化，复杂查询可能需要手动调整
