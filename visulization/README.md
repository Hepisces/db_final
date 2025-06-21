# SQL Query Visualization Demo

This demo provides an interactive web application to visualize SQL queries on a sample smart home database.

It allows you to:
- Execute arbitrary SQL queries against a pre-defined schema.
- View the SQLite query plan visualized as a graph.
- See the query results in a table.
- Get intelligent visualizations (time-series charts, bar/pie charts) for specific query types.

## How to Run

1.  **Install Dependencies:**
    Make sure you have Python 3.7+ installed. Then, install the required packages using pip:
    ```bash
    pip install -r requirements.txt
    ```
    You also need to install Graphviz on your system if you haven't already.
    - **On macOS (using Homebrew):**
      ```bash
      brew install graphviz
      ```
    - **On Debian/Ubuntu:**
      ```bash
      sudo apt-get install graphviz
      ```

2.  **Run the Streamlit App:**
    Navigate to the `visulization` directory in your terminal and run the following command:
    ```bash
    streamlit run app.py
    ```

3.  **Open in Browser:**
    Your browser should automatically open a new tab with the application running. If not, the terminal will provide a local URL (usually `http://localhost:8501`) that you can open manually. 