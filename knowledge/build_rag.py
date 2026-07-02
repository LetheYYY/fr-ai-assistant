"""FineReport 知识库构建 — 从CPT+本地资源+LLM生成完整文档"""

import json, os, re

OUT_DIR = r'C:\workspace\01_knowledge\rag_docs'
os.makedirs(OUT_DIR, exist_ok=True)

# ======== 知识库大纲（覆盖所有推荐类别）========

KNOWLEDGE_TOPICS = {
    "01_报表设计基础": [
        ("单元格扩展与父子格", "行式报表的纵向扩展(dir=0)、横向扩展(dir=1)、不扩展的区别。父子格关系如何影响数据展示。"),
        ("数据列绑定DSColumn", "如何将数据集字段绑定到单元格，dsName和columnName属性的配置。"),
        ("分组报表FunctionGrouper", "FunctionGrouper实现分组去重，SummaryGrouper实现汇总聚合。"),
        ("交叉报表", "数据双向扩展，行维度+列维度的交叉矩阵报表设计。"),
        ("自由报表", "不规则布局的报表，单元格自由排列。"),
        ("多Sheet报表", "一个WorkBook中包含多个Report，每个Report对应一个Sheet页。"),
        ("聚合报表", "不同数据集的数据在一个报表中聚合展示。"),
    ],
    "02_数据与参数": [
        ("数据集配置", "TableDataMap定义数据源、连接、SQL查询。DSColumn引用数据集字段。"),
        ("参数控件类型", "下拉框(ComboBox)、下拉复选框(CheckBoxGroup)、日期控件(DatePicker)、文本域(TextArea)等控件的XML配置。"),
        ("参数联动", "多个参数控件之间的级联关系，如省→市→区三级联动。"),
        ("动态SQL", "在SQL中使用${参数}实现动态查询条件。"),
        ("参数面板配置", "ReportParameterAttr配置，showWindow、delayPlaying等属性。"),
        ("数据连接配置", "NameDatabaseConnection指向数据连接名，DB/URL/Driver配置。"),
    ],
    "03_图表类型": [
        ("柱形图/条形图", "VanChart+BarChart，用于分类对比。支持堆积、多系列。"),
        ("饼图/环图", "VanChart+PieChart，用于占比分析。支持分离、环形。"),
        ("折线图/面积图", "VanChart+LineChart，用于趋势展示。支持多系列、标记点。"),
        ("散点图/气泡图", "VanChart+ScatterChart，用于相关性分析。"),
        ("雷达图", "VanChart+RadarChart，多维度对比。支持填充、折线两种形态。"),
        ("仪表盘", "VanChart+GaugeChart，进度/指标展示。支持360°/180°。"),
        ("漏斗图", "VanChart+FunnelChart，业务流程转化率。"),
        ("甘特图", "VanChart+GanttChart，项目进度管理。"),
        ("地图", "GIS地图+点位标记，区域数据可视化。"),
    ],
    "04_样式与美化": [
        ("条件属性Condition", "根据数据值动态设置单元格颜色、字体、可见性。ListCondition配置。"),
        ("StyleList样式系统", "定义多套样式，通过s属性引用。FRFont(字体)、Background(背景)、Border(边框)。"),
        ("自定义边框", "Top/Bottom/Left/Right四条边独立设置颜色和线型。"),
        ("图片背景", "ImageBackground+FineImage，base64内嵌图片作为背景。"),
        ("隔行变色", "通过条件属性实现行奇偶不同背景色。"),
        ("预警高亮", "数值超出阈值时自动标红/标黄。"),
    ],
    "05_填报功能": [
        ("填报控件Widget", "ComboBox/CheckBox/DatePicker/TextArea等控件的单元格级配置。"),
        ("数据校验", "填报时的数据格式校验、必填校验。"),
        ("提交入库", "填报数据写入数据库的配置。"),
        ("Excel导入导出", "从Excel批量导入数据，导出为Excel/PDF。"),
    ],
    "06_交互与脚本": [
        ("超链接Hyperlink", "单元格超链接：跳转到URL、其他报表、JavaScript。"),
        ("JavaScript脚本", "报表中的JS事件：加载后、点击时、提交前后。"),
        ("排序属性cellSortAttr", "点击表头排序的配置。"),
        ("移动端适配", "ElementCaseMobileAttr，移动端的缩放、布局配置。"),
        ("Web工具栏", "ReportWebAttr，预览页面的工具栏按钮配置。"),
    ],
    "07_函数参考": [
        ("聚合函数", "SUM/COUNT/AVG/MAX/MIN — 配合SummaryGrouper使用。"),
        ("日期函数", "YEAR/MONTH/DAY/DATEINYEAR — 日期计算与格式化。"),
        ("字符串函数", "CONCATENATE/LEFT/RIGHT/MID/REPLACE — 字符串处理。"),
        ("逻辑函数", "IF/SWITCH/AND/OR — 条件判断。"),
        ("数学函数", "ROUND/ABS/MOD/POWER — 数学计算。"),
    ],
    "08_部署与API": [
        ("FineReport目录结构", "WEB-INF/reportlets存放模板，WEB-INF/lib存放JAR，finedb存放配置。"),
        ("finedb配置数据库", "HSQLDB嵌入式数据库，存储数据连接、用户、权限等配置。"),
        ("REST API", "FineReport提供的HTTP API：模板发布、执行、参数传递。"),
        ("数据连接配置", "JDBC/ODBC数据源的URL、Driver、用户名密码配置。"),
    ],
}


# ======== 用LLM为每个主题生成详细文档 ========

def generate_doc(topic_title, topic_desc):
    """用LLM生成结构化知识文档"""
    from openai import OpenAI
    c = OpenAI(api_key='sk-79778f1a65f1484f81e863beb2ade2ee', base_url='https://api.deepseek.com')

    prompt = f"""你是FineReport技术文档专家。请为以下主题生成一份结构化的知识文档。

主题: {topic_title}
背景: {topic_desc}

输出格式（严格遵循Markdown）:

## {topic_title}

### 概述
（2-3句话说明这个功能是什么、用在什么场景）

### 核心XML结构
（给出关键XML代码片段，包含所有必须的元素和属性）

### 关键属性说明
| 属性 | 类型 | 必填 | 说明 |

### 常见配置示例
（给出2-3个实际使用示例）

### 注意事项
- 常见错误1
- 常见错误2

### 相关功能
- 关联功能1
- 关联功能2

要求:
1. XML片段必须是从真实CPT中验证过的正确格式
2. 如果有参数值范围限制，明确说明
3. 控制在500-800字
4. 中文描述，XML保持原样"""

    try:
        r = c.chat.completions.create(
            model='deepseek-chat',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.2, max_tokens=1000, timeout=25
        )
        return r.choices[0].message.content
    except Exception as e:
        return f"# {topic_title}\n\n生成失败: {e}\n\n{topic_desc}"


def main():
    total = sum(len(topics) for topics in KNOWLEDGE_TOPICS.values())
    done = 0
    
    print(f"生成 {total} 篇知识文档到 {OUT_DIR}")
    print("=" * 50)
    
    all_docs = []
    
    for category, topics in KNOWLEDGE_TOPICS.items():
        cat_dir = os.path.join(OUT_DIR, category)
        os.makedirs(cat_dir, exist_ok=True)
        
        for title, desc in topics:
            done += 1
            safe_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', title)[:40]
            filepath = os.path.join(cat_dir, f'{safe_name}.md')
            
            if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
                print(f'  [{done}/{total}] {title} (cached)')
                with open(filepath, 'r', encoding='utf-8') as f:
                    all_docs.append({'title': title, 'category': category, 'content': f.read(), 'path': filepath})
                continue
            
            print(f'  [{done}/{total}] {title} ...', end=' ', flush=True)
            content = generate_doc(title, desc)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            all_docs.append({'title': title, 'category': category, 'content': content, 'path': filepath})
            print(f'OK ({len(content)} chars)')
    
    # 保存索引
    index = [{'title': d['title'], 'category': d['category'], 'path': d['path'], 'chars': len(d['content'])} for d in all_docs]
    with open(os.path.join(OUT_DIR, '_index.json'), 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    total_chars = sum(len(d['content']) for d in all_docs)
    print(f"\n✅ 完成: {len(all_docs)}篇文档, {total_chars:,}字符")
    print(f"目录: {OUT_DIR}")

if __name__ == '__main__':
    main()
