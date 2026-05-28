"""
visualizer.py
-------------
Module tự động chọn và tạo Plotly chart phù hợp với query result.

Tại sao dùng Plotly thay vì Matplotlib?
- Plotly: interactive (zoom, hover, click) - tốt cho web app
- Matplotlib: static image - tốt cho report/paper
- Streamlit có native support cho Plotly: st.plotly_chart()

Logic "auto-chart":
- 1 cột số + không có group → histogram/bar đơn giản
- 1 cột category + 1 cột số → bar chart
- Cột có chữ "date"/"month"/"year" → line chart (time series)
- 2+ cột số → scatter plot
- Cột "percentage"/"percent"/"pct" → pie chart
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional


# Plotly color scheme nhất quán cho toàn app
CHART_COLORS = px.colors.qualitative.Set2

# Plotly theme: "plotly_white" clean, professional
PLOTLY_TEMPLATE = "plotly_white"


class ChartRecommender:
    """
    Phân tích DataFrame và recommend + tạo chart phù hợp nhất.
    
    Design decision: tách logic recommend vs render
    → Dễ test: test recommend riêng (pure Python)
    → Dễ customize: user có thể override chart type
    """

    @staticmethod
    def _count_numeric_cols(df: pd.DataFrame) -> list[str]:
        """Trả về danh sách tên cột numeric."""
        return df.select_dtypes(include=["number"]).columns.tolist()

    @staticmethod
    def _count_categorical_cols(df: pd.DataFrame) -> list[str]:
        """Trả về danh sách tên cột categorical (object/string)."""
        return df.select_dtypes(include=["object"]).columns.tolist()

    @staticmethod
    def _is_time_series(df: pd.DataFrame) -> Optional[str]:
        """
        Detect nếu có cột time-related.
        Returns: tên cột time nếu có, None nếu không.
        """
        time_keywords = ["date", "month", "year", "week", "quarter", "time", "period"]
        for col in df.columns:
            if any(kw in col.lower() for kw in time_keywords):
                return col
        return None

    def recommend_chart_type(self, df: pd.DataFrame) -> str:
        """
        Logic recommend chart type dựa trên cấu trúc data.
        
        Returns:
            "bar", "line", "pie", "scatter", "histogram", "table"
        """
        if df.empty or len(df) == 0:
            return "table"

        num_rows = len(df)
        numeric_cols = self._count_numeric_cols(df)
        categorical_cols = self._count_categorical_cols(df)
        time_col = self._is_time_series(df)

        # Chỉ có 1 row → table (không có ý nghĩa để chart)
        if num_rows == 1:
            return "table"

        # Có cột time series → line chart
        if time_col and len(numeric_cols) >= 1:
            return "line"

        # Có category + số → bar chart (phổ biến nhất)
        if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
            # Nếu <= 6 categories và có chữ "percent/pct" → pie chart
            first_cat = categorical_cols[0]
            if (num_rows <= 8 and
                any("pct" in c.lower() or "percent" in c.lower() or "share" in c.lower()
                    for c in numeric_cols)):
                return "pie"
            return "bar"

        # Chỉ có numeric → histogram
        if len(numeric_cols) >= 1 and len(categorical_cols) == 0:
            return "histogram"

        # 2+ numeric → scatter
        if len(numeric_cols) >= 2:
            return "scatter"

        return "table"

    def create_chart(self, df: pd.DataFrame, title: str = "", chart_type: Optional[str] = None) -> Optional[go.Figure]:
        """
        Tạo Plotly figure từ DataFrame.
        
        Args:
            df: DataFrame chứa data
            title: Tiêu đề chart (thường là câu hỏi của user)
            chart_type: Override auto-detect nếu muốn ("bar", "line", etc.)
            
        Returns:
            Plotly Figure object, hoặc None nếu không thể chart
        """
        if df.empty:
            return None

        numeric_cols = self._count_numeric_cols(df)
        categorical_cols = self._count_categorical_cols(df)
        time_col = self._is_time_series(df)

        # Auto-detect nếu không override
        if chart_type is None:
            chart_type = self.recommend_chart_type(df)

        fig = None

        try:
            if chart_type == "bar":
                x_col = categorical_cols[0] if categorical_cols else df.columns[0]
                y_col = numeric_cols[0] if numeric_cols else df.columns[1]

                fig = px.bar(
                    df,
                    x=x_col,
                    y=y_col,
                    title=title,
                    color=x_col,              # Mỗi bar 1 màu → dễ phân biệt
                    color_discrete_sequence=CHART_COLORS,
                    template=PLOTLY_TEMPLATE,
                    text=y_col,               # Hiển thị số trên đầu bar
                )
                fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
                fig.update_layout(showlegend=False)  # Legend thừa khi đã có label trục x

            elif chart_type == "line":
                x_col = time_col if time_col else df.columns[0]
                y_col = numeric_cols[0] if numeric_cols else df.columns[1]

                # Sort theo time để line chart có ý nghĩa
                df_sorted = df.sort_values(x_col)

                fig = px.line(
                    df_sorted,
                    x=x_col,
                    y=y_col,
                    title=title,
                    template=PLOTLY_TEMPLATE,
                    markers=True,   # Hiện điểm tròn tại mỗi data point
                )
                fig.update_traces(line_color=CHART_COLORS[0], line_width=2)

            elif chart_type == "pie":
                cat_col = categorical_cols[0] if categorical_cols else df.columns[0]
                val_col = numeric_cols[0] if numeric_cols else df.columns[1]

                fig = px.pie(
                    df,
                    names=cat_col,
                    values=val_col,
                    title=title,
                    color_discrete_sequence=CHART_COLORS,
                    template=PLOTLY_TEMPLATE,
                    hole=0.3,       # Donut chart trông đẹp hơn pie chart thường
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")

            elif chart_type == "scatter":
                x_col = numeric_cols[0]
                y_col = numeric_cols[1]
                color_col = categorical_cols[0] if categorical_cols else None

                fig = px.scatter(
                    df,
                    x=x_col,
                    y=y_col,
                    color=color_col,
                    title=title,
                    template=PLOTLY_TEMPLATE,
                    color_discrete_sequence=CHART_COLORS,
                )

            elif chart_type == "histogram":
                x_col = numeric_cols[0]

                fig = px.histogram(
                    df,
                    x=x_col,
                    title=title,
                    template=PLOTLY_TEMPLATE,
                    color_discrete_sequence=[CHART_COLORS[0]],
                    nbins=min(30, len(df) // 2),  # Tự điều chỉnh số bins
                )

            else:
                # "table" type → không chart, return None
                return None

        except Exception as e:
            # Nếu chart fail vì bất kỳ lý do gì, trả về None
            # App vẫn hoạt động, chỉ không có chart
            print(f"Chart creation failed: {e}")
            return None

        if fig:
            # Styling chung cho tất cả charts
            fig.update_layout(
                title={
                    "text": title[:80] + "..." if len(title) > 80 else title,
                    "x": 0.5,             # Center title
                    "xanchor": "center",
                    "font": {"size": 14}
                },
                margin={"t": 60, "b": 40, "l": 40, "r": 40},
                height=420,
                font={"family": "Arial, sans-serif", "size": 12},
            )

        return fig


# Singleton instance - import và dùng trực tiếp
recommender = ChartRecommender()


def auto_visualize(df: pd.DataFrame, title: str = "", chart_type: Optional[str] = None) -> Optional[go.Figure]:
    """
    Helper function: tạo chart tự động từ DataFrame.
    
    Đây là function chính mà app.py sẽ gọi.
    
    Args:
        df: Query result DataFrame
        title: Câu hỏi của user (dùng làm chart title)
        chart_type: Optional override
        
    Returns:
        Plotly Figure hoặc None
    """
    return recommender.create_chart(df, title=title, chart_type=chart_type)