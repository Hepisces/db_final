import pandas as pd
import sys
import subprocess
import os
import matplotlib.pyplot as plt
import matplotlib as mpl
import seaborn as sns
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
import re
import textwrap
from pathlib import Path

console = Console()

OUTPUT_DIR = "output"

PLAN_EXPLANATIONS = {
    "SCAN": "全表扫描: 从头到尾读取表的每一行。对于大表，这可能效率不高。通常意味着没有使用索引。",
    "SEARCH": "索引搜索: 使用索引来直接定位和读取满足条件的行子集，这通常比全表扫描快得多。",
    "USING INDEX": "使用了命名索引。",
    "USING COVERING INDEX": "使用了覆盖索引: 查询所需的所有数据都包含在索引中，无需访问原始表，效率非常高。",
    "USE TEMP B-TREE FOR": "使用临时B树: 为排序(ORDER BY)或分组(GROUP BY)创建了一个临时内部索引。如果频繁发生，可考虑为相关列添加真实索引来优化。",
    "COMPOUND QUERY": "复合查询: 正在执行一个包含 UNION, EXCEPT, 或 INTERSECT 的查询。",
    "MATERIALIZE": "物化子查询: 将一个子查询的结果存储在一个临时表中。这通常在子查询结果需要被多次使用时发生。",
    "CO-ROUTINE": "使用协程: 将子查询作为协程运行，按需生成行，而不是一次性生成所有结果。这可以减少内存使用。"
}

def get_explanation(detail_str: str) -> str:
    """Finds a human-readable explanation for a query plan detail string."""
    for keyword, explanation in PLAN_EXPLANATIONS.items():
        if keyword in detail_str:
            return f" [dim italic]({explanation})[/dim italic]"
    return ""
    
def draw_query_plan(plan_df: pd.DataFrame):
    """Draw the query plan as a tree in the console using rich, with explanations."""
    console.print("\n[bold cyan]📊 Query Plan[/bold cyan]")
    tree = Tree("[bold]Query Plan[/bold]")
    nodes = {}

    # First pass: add all nodes to the tree and dictionary
    for _, row in plan_df.iterrows():
        explanation = get_explanation(row['detail'])
        node_label = f"[green]ID:{row['id']}[/green] | {row['detail']}{explanation}"
        nodes[row['id']] = {'label': node_label, 'parent': row['parent'], 'children': []}

    # Second pass: build the tree structure
    root_nodes = []
    for node_id, node_data in nodes.items():
        parent_id = node_data['parent']
        if parent_id == 0:
            root_nodes.append(node_id)
        else:
            if parent_id in nodes:
                nodes[parent_id]['children'].append(node_id)

    # Recursive function to add nodes to the rich Tree
    def add_to_tree(tree_node, node_id):
        node_data = nodes[node_id]
        child_tree_node = tree_node.add(node_data['label'])
        for child_id in sorted(node_data['children']):
            add_to_tree(child_tree_node, child_id)

    # Build the tree from root nodes
    for root_id in sorted(root_nodes):
        add_to_tree(tree, root_id)
             
    console.print(tree)

def open_file(filepath):
    """Open a file in the default application for the current platform."""
    try:
        if sys.platform == "win32":
            os.startfile(filepath)
        elif sys.platform == "darwin": # macOS
            subprocess.run(["open", filepath], check=True)
        else: # linux
            subprocess.run(["xdg-open", filepath], check=True)
        console.print(f"✅ Automatically opened [bold white]{filepath}[/bold white]")
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        console.print(f"[bold red]Could not automatically open file:[/bold red] {e}")
        console.print(f"Please find it at: {os.path.abspath(filepath)}")

def generate_er_diagram(ddl_path: str, output_path: str):
    """
    Parses a DDL file to generate a Mermaid ER diagram and saves it as an HTML file.
    """
    try:
        with open(ddl_path, 'r', encoding='utf-8') as f:
            ddl_content = f.read()
    except FileNotFoundError:
        console.print(f"[bold red]错误: DDL文件未找到: {ddl_path}[/bold red]")
        return

    tables = {}
    relationships = []

    # Regex to find tables and their columns
    table_pattern = re.compile(r"CREATE TABLE\s+(\w+)\s+\((.*?)\);", re.S | re.I)
    # Regex to find foreign key constraints
    fk_pattern = re.compile(r"FOREIGN KEY\s+\((.*?)\)\s+REFERENCES\s+(\w+)\s*\((.*?)\)", re.I)

    for match in table_pattern.finditer(ddl_content):
        table_name = match.group(1)
        columns_str = match.group(2)
        
        columns = []
        # Simple split by comma, ignoring commas inside parentheses for data types like NUMERIC(10, 2)
        for col_def in re.split(r',(?![^\(]*\))', columns_str):
            col_def = col_def.strip()
            if not col_def or col_def.lower().startswith(('primary key', 'foreign key', 'constraint')):
                continue
            
            # Extract column name, trying to be robust against various definitions
            parts = col_def.split()
            col_name = parts[0].strip('"`')
            col_type = parts[1] if len(parts) > 1 else ""
            
            # Check for primary key marker
            is_pk = "PRIMARY KEY" in col_def.upper()
            
            columns.append({"name": col_name, "type": col_type, "is_pk": is_pk})
        
        tables[table_name] = columns

        # Find foreign keys within the table definition
        for fk_match in fk_pattern.finditer(columns_str):
            from_col = fk_match.group(1).strip()
            to_table = fk_match.group(2).strip()
            to_col = fk_match.group(3).strip()
            relationships.append(f'    "{table_name}" --o| "{to_table}" : "{from_col} -> {to_col}"')

    # Build Mermaid diagram string
    mermaid_string = "erDiagram\n"
    for table_name, columns in tables.items():
        mermaid_string += f'    "{table_name}" {{\n'
        for col in columns:
            pk_label = " PK" if col["is_pk"] else ""
            mermaid_string += f'        {col["type"]} {col["name"]}{pk_label}\n'
        mermaid_string += '    }\n'
    
    mermaid_string += "\n".join(set(relationships)) # Use set to avoid duplicates

    # HTML template to render the Mermaid diagram
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>数据库 E-R 图</title>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true }});
        </script>
    </head>
    <body>
        <h1>数据库实体关系图 (E-R Diagram)</h1>
        <div class="mermaid">
            {mermaid_string}
        </div>
    </body>
    </html>
    """
    
    try:
        # The output_path is now the full file path, so we get its parent directory
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # Use the full path directly
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(html_template))
            
        console.print(f"E-R 图已成功保存至 [green]{output_path}[/green]")
        open_file(output_path)
    except IOError as e:
        console.print(f"[bold red]无法写入HTML文件: {e}[/bold red]")

def print_results_table(df: pd.DataFrame):
    """Print the query results as a table in the console, limited to 10 rows."""
    console.print("\n[bold cyan]📈 Query Results[/bold cyan]")
    if df.empty:
        console.print("[yellow]Query executed successfully, but returned no data.[/yellow]")
        return
    
    total_rows = len(df)
    display_df = df
    if total_rows > 10:
        console.print(f"[yellow]Total rows: {total_rows}. Showing top 10.[/yellow]")
        display_df = df.head(10)
        
    table = Table(show_header=True, header_style="bold magenta")
    for col in display_df.columns:
        table.add_column(col)
    
    for _, row in display_df.iterrows():
        table.add_row(*[str(item) for item in row])
        
    console.print(table)

def visualize_query_result(df: pd.DataFrame, query: str):
    """
    根据查询结果DataFrame绘制多种图表，用户可交互选择图表类型。
    若选择不匹配，允许重新选择。
    """
    if df.empty:
        console.print("[yellow]查询返回了空结果，跳过可视化。[/yellow]")
        return

    def _prompt_for_column(dframe: pd.DataFrame, purpose: str) -> str | None:
        """Helper function to prompt user to select a column for a specific purpose."""
        console.print(f"\n请选择用作 [bold cyan]'{purpose}'[/bold cyan] 的列:")
        columns = dframe.columns.tolist()
        for i, col in enumerate(columns, 1):
            print(f"{i}. {col}")
        print("0. 取消选择")

        while True:
            try:
                choice = int(input("请输入列的编号: "))
                if choice == 0:
                    return None
                if 1 <= choice <= len(columns):
                    return columns[choice - 1]
                else:
                    console.print(f"[red]无效的选择，请输入 0 到 {len(columns)} 之间的数字。[/red]")
            except ValueError:
                console.print("[red]请输入有效的数字！[/red]")

    def _prompt_for_multiple_columns(dframe: pd.DataFrame, purpose: str, min_selection: int = 1) -> list[str] | None:
        """Helper function to prompt user to select multiple columns."""
        console.print(f"\n请选择用作 [bold cyan]'{purpose}'[/bold cyan] 的列 (可多选，用逗号分隔):")
        columns = dframe.columns.tolist()
        for i, col in enumerate(columns, 1):
            print(f"{i}. {col}")
        print("0. 取消选择")

        while True:
            try:
                choices_str = input("请输入列的编号 (例如: 1, 3, 4): ")
                if choices_str.strip() == '0':
                    return None
                
                choices_indices = [int(c.strip()) for c in choices_str.split(',') if c.strip()]
                
                if all(1 <= i <= len(columns) for i in choices_indices):
                    selected_cols = [columns[i - 1] for i in choices_indices]
                    if len(set(selected_cols)) < min_selection:
                        console.print(f"[red]请至少选择 {min_selection} 个不同的列。[/red]")
                        continue
                    return selected_cols
                else:
                    console.print(f"[red]输入中包含无效的编号，请输入 1 到 {len(columns)} 之间的数字。[/red]")
            except ValueError:
                console.print("[red]请输入有效的、以逗号分隔的数字！[/red]")
                
    # --- 主可视化循环 ---
    while True:
        # --- 图表推荐逻辑 ---
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(exclude=['number']).columns.tolist()
        
        available_charts = {}
        recommendations = []

        # 规则 1: 时间序列图
        if len(numeric_cols) > 0 and any(name in df.columns for name in ['date', 'time', 'timestamp']):
            available_charts[1] = "时间序列折线图"
            recommendations.append(1)
        
        # 规则 2: 成对散点图 & 热力图
        if len(numeric_cols) >= 2:
            available_charts[2] = "成对散点图"
            available_charts[5] = "相关性热力图"
            if len(numeric_cols) > 2: # 多个数值列时更有意义
                 recommendations.append(2)
                 recommendations.append(5)

        # 规则 3: 堆叠柱状图
        if len(categorical_cols) > 0 and len(numeric_cols) > 0:
             available_charts[3] = "堆叠柱状图"

        # 规则 4: 箱线图
        if len(numeric_cols) >= 1:
            available_charts[4] = "箱线图"

        # 规则 6 & 7: 分类图
        if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
            available_charts[6] = "分类柱状图"
            available_charts[7] = "分类饼图"
            if len(df[categorical_cols[0]].unique()) < 15: # 分类较少时推荐
                recommendations.append(6)
                recommendations.append(7)
        
        if not available_charts:
            console.print("[yellow]未找到适用于当前数据的推荐图表类型。[/yellow]")
            break

        # --- 打印菜单 ---
        console.print("\n[bold cyan]🖼️  结果可视化[/bold cyan]")
        console.print("我们根据您的数据推荐以下图表类型:")
        
        for chart_id, name in sorted(available_charts.items()):
            is_recommended = "(推荐)" if chart_id in recommendations else ""
            print(f"{chart_id}. {name} {is_recommended}")
        print("0. 退出可视化")

        try:
            choice_input = input(f"请输入图表类型的编号: ")
            choice = int(choice_input)
            if choice == 0:
                console.print("退出可视化。")
                break
            if choice not in available_charts:
                console.print(f"[red]无效的选择，请输入菜单中可用的编号。[/red]")
                continue
        except ValueError:
            console.print("[red]请输入有效的数字！[/red]")
            continue
            
        # 准备绘图
        plt.style.use('seaborn-v0_8-whitegrid')
        fig, ax = plt.subplots(figsize=(12, 7))
        plot_generated = False

        if choice == 1:
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if not numeric_cols:
                console.print("[bold red]错误：未找到可用于绘图的数值列。[/bold red]")
                plt.close(fig)
                continue

            time_col = _prompt_for_column(df, "时间轴 (X-axis)")
            if not time_col:
                plt.close(fig)
                continue
            
            y_axis_cols = _prompt_for_multiple_columns(df[numeric_cols], "Y轴 (数值)", min_selection=1)
            if not y_axis_cols:
                plt.close(fig)
                continue

            plot_df = df.copy()
            try:
                plot_df[time_col] = pd.to_datetime(plot_df[time_col], errors='raise')
                plot_df = plot_df.sort_values(by=time_col)
            except Exception as e:
                console.print(f"[bold red]无法将列 '{time_col}' 转换为时间格式: {e}[/bold red]")
                console.print("请确保选择的列包含有效的日期/时间数据，或选择其他图表类型。")
                plt.close(fig)
                continue
            
            plot_generated = True
            for col in y_axis_cols:
                ax.plot(plot_df[time_col], plot_df[col], label=col, marker='o', linestyle='-')
            ax.set_title("Time Series Plot", fontsize=16)
            ax.set_xlabel(time_col, fontsize=12)
            ax.set_ylabel("Value", fontsize=12)
            plt.xticks(rotation=45)

        elif choice == 2:
            selected_numeric_cols = _prompt_for_multiple_columns(df[numeric_cols], "成对散点图", min_selection=2)
            if not selected_numeric_cols:
                plt.close(fig)
                continue
            
            plot_generated = True
            plt.close(fig) # Pairplot 创建自己的 figure
            pair_plot = sns.pairplot(df[selected_numeric_cols])
            pair_plot.fig.suptitle("Pairplot of Numerical Values", y=1.02, fontsize=16)

        elif choice == 3:
            categorical_cols = df.select_dtypes(exclude=['number']).columns.tolist()
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    
            if not categorical_cols or not numeric_cols:
                console.print("[bold red]错误：堆叠柱状图需要至少一个非数值列（作X轴）和至少一个数值列。[/bold red]")
                plt.close(fig)
                continue
            
            x_col = _prompt_for_column(df[categorical_cols], "X轴 (类别/时间)")
            if not x_col:
                plt.close(fig)
                continue
            
            y_axis_cols = _prompt_for_multiple_columns(df[numeric_cols], "堆叠的数值", min_selection=1)
            if not y_axis_cols:
                plt.close(fig)
                continue
                
            plot_df = df.copy()
            try:
                # 尝试将X轴转换为datetime以获得更好的排序和显示
                plot_df[x_col] = pd.to_datetime(plot_df[x_col])
                plot_df = plot_df.sort_values(by=x_col)
                # For dates, don't use too many ticks on the bar chart
                if pd.api.types.is_datetime64_any_dtype(plot_df[x_col]):
                    ax.xaxis.set_major_locator(plt.MaxNLocator(15)) # Limit number of date ticks
            except (ValueError, TypeError):
                # 如果不是日期，则按原样处理
                pass
            
            plot_generated = True
            plot_df.set_index(x_col)[numeric_cols].plot(kind="bar", stacked=True, ax=ax, width=0.8)
            ax.set_title("Stacked Bar Plot", fontsize=16)
            ax.set_xlabel(x_col, fontsize=12)
            ax.set_ylabel("Value", fontsize=12)
            plt.xticks(rotation=45, ha='right')

        elif choice == 4 and len(numeric_cols) > 0:
            plot_generated = True
            df[numeric_cols].boxplot(ax=ax)
            ax.set_title("Box Plot of Values", fontsize=16)
            ax.set_ylabel("Value", fontsize=12)

        elif choice == 5:
            selected_numeric_cols = _prompt_for_multiple_columns(df[numeric_cols], "相关性热力图")
            if not selected_numeric_cols:
                plt.close(fig)
                continue

            plot_generated = True
            correlation_matrix = df[selected_numeric_cols].corr()
            sns.heatmap(correlation_matrix, annot=True, cmap="coolwarm", vmin=-1, vmax=1, ax=ax)
            ax.set_title("Correlation Heatmap", fontsize=16)

        elif choice == 6 and len(categorical_cols) > 0 and len(numeric_cols) > 0:
            cat_col = _prompt_for_column(df[categorical_cols], "类别列 (X-axis)")
            if not cat_col:
                plt.close(fig)
            continue
            
            num_col = _prompt_for_column(df[numeric_cols], "数值列 (Y-axis)")
            if not num_col:
                plt.close(fig)
                continue

            plot_generated = True
            sns.barplot(x=cat_col, y=num_col, data=df, ax=ax, palette='viridis')
            ax.set_title(f"Distribution of '{num_col}' by '{cat_col}'", fontsize=16)
            ax.set_xlabel(cat_col, fontsize=12)
            ax.set_ylabel(num_col, fontsize=12)
            plt.xticks(rotation=45)

        elif choice == 7 and len(categorical_cols) > 0 and len(numeric_cols) > 0:
            cat_col = _prompt_for_column(df[categorical_cols], "类别列")
            if not cat_col:
                plt.close(fig)
                continue
            
            num_col = _prompt_for_column(df[numeric_cols], "数值列")
            if not num_col:
                plt.close(fig)
                continue

            plot_generated = True
            # 聚合数据以防分类列中有重复项
            data_for_pie = df.groupby(cat_col)[num_col].sum()
            ax.pie(data_for_pie, labels=data_for_pie.index, autopct='%1.1f%%', colors=sns.color_palette('viridis', len(data_for_pie)))
            ax.set_title(f"Proportion of '{num_col}' by '{cat_col}'", fontsize=16)

        else:
            console.print("[bold red]数据不满足所选图表类型的要求或选择无效，请重新选择。[/bold red]")
            plt.close(fig) # 关闭未使用的figure
            continue
            
        if plot_generated:
            try:
                # 添加图例
                if choice not in [2, 5, 7]: # Pairplot, Heatmap, Pieplot 有自己的图例逻辑
                    ax.legend()
                
                fig.suptitle(query, fontsize=10, y=0.99, wrap=True)
                plt.tight_layout(rect=[0, 0, 1, 0.96])

                os.makedirs(OUTPUT_DIR, exist_ok=True)
                output_file = "visualization.png"
                full_path = os.path.join(OUTPUT_DIR, output_file)
                plt.savefig(full_path, dpi=300)
                plt.close(fig) # 关闭figure释放内存

                console.print(f"[green]✅ 可视化结果已保存至 [bold white]{full_path}[/bold white][/green]")
                open_file(full_path)
                break # 成功生成图表后退出循环

            except Exception as e:
                console.print(f"[red]生成或保存可视化时出错: {e}[/red]")
                plt.close(fig)
                break