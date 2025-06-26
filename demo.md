# AweSQL 使用指南

为了快速上手, 我们给出了一些例子来说明如何使用AweSQL., 并配备了对应的演示视频. 
我们假设您已经下载好了数据并放置在db_final目录下. 

## 基本命令

1. **查看帮助信息**
   ```bash
   awesql --help
   ```

2. **导入数据**
   假设您已经下载好了数据并放置在db_final目录下：
   ```bash
   awesql import-data
   ```

3. **查看数据库表**
   显示当前数据库中的所有表：
   ```bash
   awesql tables
   ```

4. **生成实体关系图**
   可视化数据库的表结构关系：
   ```bash
   awesql er
   ```

5. **SQL语法检查**
   在执行前检查SQL语句的正确性（示例给出的代码错误包括但不限于别名错误、非法字符等）：
   ```bash
   awesql check "SELECT STRFTIME('%Y-%m-%d', d.time) AS date, l.area, COUNT(d.did) AS update.
   count, AVG(d.did) FROM devupdata d JOIN devlist | ON d.did = I.did WHERE I.area IS NOT NULL AND
   STRETIME('%Y-%m-%d', d.time) > 1999-01-01' GROUP BY date, l.area ORDER BY date;"
   ```

6. **执行SQL查询并可视化**
   通过正确性检查后，执行查询并根据交互式命令选择可视化图表类型：
   ```bash
   awesql run "
   SELECT STRFTIME('%Y-%m-%d', d.time) AS date, l.area, COUNT(d.did) AS update_count
   FROM devupdata d JOIN devlist l ON d.did = l.did 
   WHERE l.area IS NOT NULL AND STRFTIME('%Y-%m-%d', d.time) > '2021-01-01' 
   GROUP BY date, l.area ORDER BY date;"
   ```

7. **自然语言查询**
   使用自然语言描述您的查询需求（注：此功能通常耗时较久，推荐在显存大于24GB的显卡上使用）：
   ```bash
   awesql ask "Querying the time column of the devuplist table"
   ```

8. **重置数据库**
   清空数据库（需要管理员权限）：
   ```bash
   awesql reset-db
   ```