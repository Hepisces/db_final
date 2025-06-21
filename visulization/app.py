import streamlit as st
import pandas as pd
import sqlite3
from contextlib import closing
import random
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import sqlparse
import graphviz

# --- Database Setup and Mock Data Generation ---

DB_FILE = "visualization_demo.db"

def create_connection():
    """Create a database connection to the SQLite database."""
    return sqlite3.connect(DB_FILE)

def create_tables(conn):
    """Create tables based on the provided DDL."""
    ddl_script = """
    CREATE TABLE IF NOT EXISTS customer (
        uid   VARCHAR NOT NULL PRIMARY KEY,
        label INTEGER
    );

    CREATE TABLE IF NOT EXISTS devlist (
        uid  VARCHAR REFERENCES customer(uid) ON DELETE SET NULL,
        did  VARCHAR NOT NULL PRIMARY KEY,
        type VARCHAR,
        area VARCHAR
    );

    CREATE TABLE IF NOT EXISTS control (
        uid  VARCHAR,
        did  VARCHAR NOT NULL,
        form VARCHAR NOT NULL,
        data VARCHAR NOT NULL,
        time TIMESTAMP NOT NULL,
        PRIMARY KEY (did, time, form, data),
        FOREIGN KEY (uid) REFERENCES customer(uid)
    );

    CREATE TABLE IF NOT EXISTS devupdata (
        uid  VARCHAR,
        did  VARCHAR NOT NULL,
        time TIMESTAMP NOT NULL,
        data VARCHAR NOT NULL,
        PRIMARY KEY (did, time, data),
        FOREIGN KEY (uid) REFERENCES customer(uid)
    );
    """
    with closing(conn.cursor()) as cursor:
        cursor.executescript(ddl_script)
    conn.commit()

def generate_mock_data(conn, num_customers=10, num_devices_per_customer=3, num_events_per_device=100):
    """Generate and insert mock data into the database."""
    cursor = conn.cursor()

    # Check if data exists
    cursor.execute("SELECT COUNT(*) FROM customer")
    if cursor.fetchone()[0] > 0:
        st.info("数据已存在，跳过生成。")
        return

    st.info("正在生成模拟数据...")

    # Customers
    customers = []
    for i in range(num_customers):
        uid = f"user_{i:03d}"
        customers.append((uid, random.randint(1, 5)))
    cursor.executemany("INSERT INTO customer (uid, label) VALUES (?, ?)", customers)

    # Devices
    devices = []
    device_types = ['light', 'thermostat', 'camera', 'lock', 'sensor']
    areas = ['living_room', 'bedroom', 'kitchen', 'bathroom', 'office']
    device_id_counter = 0
    for uid, _ in customers:
        for _ in range(num_devices_per_customer):
            did = f"device_{device_id_counter:04d}"
            devices.append((uid, did, random.choice(device_types), random.choice(areas)))
            device_id_counter += 1
    cursor.executemany("INSERT INTO devlist (uid, did, type, area) VALUES (?, ?, ?, ?)", devices)

    # Control and DevUpdate Events
    control_events = []
    devupdata_events = []
    now = datetime.now()

    for uid, did, dev_type, area in devices:
        for i in range(num_events_per_device):
            event_time = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
            
            # Control events
            form = random.choice(['app', 'voice', 'auto'])
            if dev_type == 'light':
                data = random.choice(['on', 'off', f"brightness_{random.randint(10,100)}"])
            elif dev_type == 'thermostat':
                data = f"temp_{random.uniform(18.0, 25.0):.1f}"
            else:
                data = random.choice(['locked', 'unlocked', 'recording_on'])
            control_events.append((uid, did, form, data, event_time))
            
            # DevUpdate events (e.g., sensor readings)
            if dev_type in ['thermostat', 'sensor', 'camera']:
                 update_data = f"status_{random.choice(['ok', 'offline', 'triggered'])}_{random.random():.2f}"
                 devupdata_events.append((uid, did, event_time, update_data))


    cursor.executemany("INSERT INTO control (uid, did, form, data, time) VALUES (?, ?, ?, ?, ?)", control_events)
    cursor.executemany("INSERT INTO devupdata (uid, did, time, data) VALUES (?, ?, ?, ?)", devupdata_events)

    conn.commit()
    st.success("模拟数据生成完毕！")

# --- Main App Logic ---

def main():
    st.set_page_config(page_title="SQL查询可视化Demo", layout="wide")
    st.title("🗂️ SQL 查询与可视化平台")
    
    # Initialize database
    conn = create_connection()
    create_tables(conn)
    generate_mock_data(conn)
    
    st.sidebar.header("数据库 Schema")
    st.sidebar.code("""
    customer(uid, label)
    devlist(uid, did, type, area)
    control(uid, did, form, data, time)
    devupdata(uid, did, time, data)
    """, language="sql")
    
    st.sidebar.header("示例查询")
    example_queries = {
        "时序数据: 最近一小时的设备控制记录": "SELECT * FROM control WHERE time >= datetime('now', '-1 hour') ORDER BY time DESC;",
        "GROUP BY: 各区域设备数量统计": "SELECT area, COUNT(did) as device_count FROM devlist GROUP BY area;",
        "JOIN: 查询用户'user_001'的设备及其类型": "SELECT c.uid, d.did, d.type, d.area FROM customer c JOIN devlist d ON c.uid = d.uid WHERE c.uid = 'user_001';",
        "复杂聚合: 不同设备类型每天的平均控制次数": "SELECT d.type, DATE(c.time) as day, COUNT(c.did) as control_count FROM control c JOIN devlist d ON c.did = d.did GROUP BY d.type, day ORDER BY day, control_count DESC;"
    }
    
    query_choice = st.sidebar.selectbox("选择一个示例或在下方输入自定义查询", options=list(example_queries.keys()), index=0)
    
    query_input = st.text_area("SQL 查询", value=example_queries[query_choice], height=150)

    if st.button("🚀 执行查询并可视化"):
        if query_input:
            try:
                # --- Query Plan Visualization ---
                st.subheader("📊 查询计划 (Query Plan)")
                with st.spinner("生成查询计划..."):
                    plan_df = get_query_plan(conn, query_input)
                    plan_graph = create_plan_graph(plan_df)
                    st.graphviz_chart(plan_graph)
                
                # --- Query Result Visualization ---
                st.subheader("📈 查询结果")
                result_df, description = execute_query(conn, query_input)
                
                if not result_df.empty:
                    st.dataframe(result_df)
                    visualize_results(query_input, result_df)
                else:
                    st.info("查询成功，但没有返回任何数据。")

            except Exception as e:
                st.error(f"查询执行出错: {e}")
        else:
            st.warning("请输入有效的SQL查询。")

    conn.close()

def execute_query(conn, query):
    """Execute a SQL query and return the result as a DataFrame."""
    df = pd.read_sql_query(query, conn)
    cursor = conn.cursor()
    cursor.execute(query)
    description = [desc[0] for desc in cursor.description]
    return df, description

def get_query_plan(conn, query):
    """Get the query plan for a SQL query."""
    plan_query = f"EXPLAIN QUERY PLAN {query}"
    plan_df = pd.read_sql_query(plan_query, conn)
    return plan_df

def create_plan_graph(plan_df):
    """Create a graphviz Digraph from the query plan DataFrame."""
    graph = graphviz.Digraph('query_plan', node_attr={'shape': 'record'})
    
    for index, row in plan_df.iterrows():
        node_id = str(row['id'])
        detail = row['detail'].replace('<', '&lt;').replace('>', '&gt;')
        label = f"{{<f0>ID: {row['id']} | {detail}}}"
        graph.node(node_id, label)
        
        parent_id = str(row['parent'])
        if parent_id != '0':
            graph.edge(parent_id, node_id)
            
    return graph

def visualize_results(query, df):
    """Infer query type and visualize results."""
    
    query_type = infer_query_type(query, df)
    st.write(f"自动推断的查询类型: **{query_type}**")

    if query_type == "时间序列":
        visualize_time_series(df)
    elif query_type == "聚合分析":
        visualize_aggregation(df)
    elif query_type == "类别分布":
        visualize_categorical(df)
    else:
        st.write("默认使用表格展示。可尝试修改查询以获得更丰富的可视化效果。")

def infer_query_type(query, df):
    """Infer query type to select a suitable visualization method."""
    formatted_query = sqlparse.format(query.strip(), keyword_case='upper')
    
    # Time Series
    time_cols = [c for c in df.columns if 'time' in c.lower() or 'date' in c.lower()]
    if any(pd.api.types.is_datetime64_any_dtype(df[c]) for c in time_cols):
        return "时间序列"
    if time_cols and len(df[time_cols[0]].unique()) > 1:
        return "时间序列"

    # Aggregation
    if 'GROUP BY' in formatted_query:
        return "聚合分析"
    
    agg_funcs = ['COUNT(', 'SUM(', 'AVG(', 'MIN(', 'MAX(']
    if any(func in formatted_query for func in agg_funcs):
         return "聚合分析"
         
    # Categorical
    if len(df.columns) == 2 and pd.api.types.is_numeric_dtype(df.iloc[:, 1]) and pd.api.types.is_string_dtype(df.iloc[:, 0]):
        return "类别分布"

    return "一般查询"


def visualize_time_series(df):
    """Visualize time series data with a line chart."""
    time_col = None
    for col in df.columns:
        if 'time' in col.lower() or 'date' in col.lower():
            try:
                df[col] = pd.to_datetime(df[col])
                time_col = col
                break
            except (ValueError, TypeError):
                continue

    if not time_col:
        st.warning("未找到可解析为时间序列的列。")
        return

    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    if not numeric_cols:
        st.warning("时间序列数据中没有找到数值列用于绘图。")
        return

    st.write("#### 时间序列分析")
    y_axis_options = numeric_cols
    y_axis = st.selectbox("选择Y轴数据", options=y_axis_options)

    if y_axis:
        fig = px.line(df, x=time_col, y=y_axis, title=f"{y_axis} a时间趋势", markers=True)
        fig.update_layout(xaxis_title="时间", yaxis_title=y_axis)
        st.plotly_chart(fig, use_container_width=True)

def visualize_aggregation(df):
    """Visualize aggregation results with bar or pie charts."""
    st.write("#### 聚合分析")
    
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    categorical_cols = df.select_dtypes(exclude=['number']).columns.tolist()

    if not numeric_cols or not categorical_cols:
        st.warning("聚合分析需要至少一个类别列和一个数值列。")
        return
        
    category_col = st.selectbox("选择类别列 (X轴)", options=categorical_cols)
    metric_col = st.selectbox("选择数值列 (Y轴)", options=numeric_cols)

    if len(df) <= 15:
        chart_type = st.radio("选择图表类型", ('条形图', '饼图'))
        if chart_type == '饼图':
            fig = px.pie(df, names=category_col, values=metric_col, title=f"{metric_col} 按 {category_col} 分布")
        else:
            fig = px.bar(df, x=category_col, y=metric_col, title=f"{metric_col} 按 {category_col} 对比")
    else:
        st.info("数据量较大，建议使用条形图。")
        fig = px.bar(df, x=category_col, y=metric_col, title=f"{metric_col} 按 {category_col} 对比")
    
    st.plotly_chart(fig, use_container_width=True)

def visualize_categorical(df):
    """Visualize categorical distribution."""
    st.write("#### 类别分布")
    category_col = df.columns[0]
    metric_col = df.columns[1]

    if len(df) <= 15:
        chart_type = st.radio("选择图表类型", ('条形图', '饼图'))
        if chart_type == '饼图':
            fig = px.pie(df, names=category_col, values=metric_col, title=f"{metric_col} 按 {category_col} 分布")
        else:
            fig = px.bar(df, x=category_col, y=metric_col, title=f"{metric_col} 按 {category_col} 对比")
    else:
        st.info("数据量较大，建议使用条形图。")
        fig = px.bar(df, x=category_col, y=metric_col, title=f"{metric_col} 按 {category_col} 对比")
    
    st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main() 