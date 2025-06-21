# AwesomeSQL (`awesql`)

`awesql` 是一个功能强大的命令行数据库交互工具。它允许用户执行SQL查询、将结果可视化、检查语法以及将自然语言翻译成SQL。

本工具基于 Python、Typer 和 Rich 构建，提供了丰富的现代化终端优先用户体验。

## 核心功能

-   **智能数据导入**: 自动从默认目录 (`Smart_Home_DATA`) 或用户指定的目录中查找并导入数据。
-   **交互式可视化**: 运行查询后，可从菜单中选择多种图表类型 (`matplotlib`/`seaborn`)，以最佳方式展示您的数据。
-   **AI驱动的查询助手**:
    -   `check`: 使用外部API获取SQL查询的修正建议。
    -   `ask`: 使用本地AI模型将自然语言问题翻译成完整的SQL查询。
-   **集中化配置**: 使用 `awesql config` 命令组，轻松管理AI相关功能的路径。

## 安装指南

我们推荐使用 Conda 来管理您的Python环境。

```bash
# 1. 创建并激活 Conda 环境
conda create -n awesql python=3.12 -y
conda activate awesql

# 2. 安装依赖项及本工具（以可编辑模式）
# '.' 指的是当前目录（项目根目录）。
pip install -r requirements.txt
pip install -e .
```
以"可编辑"模式 (`-e`) 安装意味着您对源代码的任何修改都将立即生效，无需重新安装。

## 标准工作流程

推荐的工作流程是先导入数据，然后进行查询。仅当您需要使用AI驱动的 `ask` 和 `check` 命令时，才需要进行配置。

### 1. 导入数据库

此命令会从 `.sql` 数据文件创建并填充数据库。它会自动寻找 `DDL.sql` 文件来创建表结构。**此操作不再需要管理员权限。**

**选项 A: 使用默认目录**
如果您的数据位于 `Smart_Home_DATA` 目录中，只需运行：
```bash
awesql import-data
```

**选项 B: 使用自定义目录**
要从其他目录导入，请使用 `--dir` 标志。
```bash
awesql import-data --dir /path/to/your/data_folder
```

### 2. 查询与分析

数据库导入后，任何用户都可以运行查询。

**只读查询**:
对于 `SELECT` 查询，无需任何权限即可运行。
```bash
awesql run "SELECT type, COUNT(*) FROM devlist GROUP BY type"
```
查询运行后，您将在终端看到一个结果表格，并被提示从一个**交互式菜单中选择可视化图表类型**。

**修改性查询 (需要管理员权限)**:
为了防止意外修改或SQL注入，任何非 `SELECT` 查询 (如 `UPDATE`, `DELETE`, `INSERT`, `DROP` 等) 都需要管理员权限。
```bash
awesql run "DELETE FROM devlist WHERE did = 'some_device_id'"
```
运行此命令时，系统会自动提示您输入管理员用户名和密码。

### 3. (可选) 配置并使用AI功能

`ask` 和 `check` 命令需要一些额外配置。

**A. `ask` (文本到SQL) 命令:**

此功能依赖于一个本地的大型语言模型。您必须先下载该模型，然后告诉 `awesql` 在哪里可以找到它。

-   **第一步: 下载模型**
    推荐使用的模型是 `defog/sqlcoder-7b-2`。您可以在 Hugging Face 上找到它。
    - **模型链接**: [defog/sqlcoder-7b-2 on Hugging Face](https://huggingface.co/defog/sqlcoder-7b-2)
    
    请按照 Hugging Face 页面上的说明，将模型文件下载到您本地机器的一个目录中。

-   **第二步: 配置路径**
    使用 `config set-model-path` 命令，让 `awesql` 指向您保存模型的目录。
    ```bash
    awesql config set-model-path /path/to/your/downloaded_sqlcoder_model
    ```
-   **第三步: 提出问题**
    ```bash
    awesql ask "厨房里有多少个设备?"
    ```

**B. `check` (SQL检查) 与 `ask` (自定义结构) 命令:**

如果您的 `DDL.sql` 文件不在默认的数据目录中，您必须配置其路径，以便AI工具了解您的数据库表结构。
```bash
awesql config set-ddl-path /path/to/your/DDL.sql
```

**C. 验证配置**
您可以随时查看已保存的设置。
```bash
awesql config show
```

### 4. 管理员操作与安全

#### 重置数据库 (仅限管理员)

要删除数据库并从头开始，请使用 `reset-db` 命令。这是一个危险操作，需要管理员权限。
```bash
awesql reset-db
```

#### 配置管理员凭证 (推荐)

为了安全起见，默认的管理员凭证 (`admin`/`123`) 可以在源代码中看到。强烈建议您通过设置**环境变量**来覆盖它们。这是更安全的做法，可以将凭证与代码分离。

在您的 shell 配置文件 (如 `.bashrc`, `.zshrc`) 中添加以下行：
```bash
export AWESQL_ADMIN_USER="您的安全用户名"
export AWESQL_ADMIN_PASS="您的安全密码"
```
保存文件并重新加载您的 shell (`source ~/.zshrc`) 后，`awesql` 将自动使用这些新的、更安全的凭证。 