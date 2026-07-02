"""帆软数字员工 Agent v5 — 三步确认流程

流程:
  上传文件 → ①提取预览 → ②用户确认/修改 → ③生成CPT
"""

import sys, os, json, re

sys.path.insert(0, os.path.dirname(__file__))
from cpt_builder_v4 import build_v10_cpt
from analyze_upload import parse_excel, parse_image, llm_extract_columns

OUTPUT_DIR = r'os.path.dirname(os.path.abspath(__file__))\output'
FR_DIR = r'/path/to/fr/reportlets'
os.makedirs(OUTPUT_DIR, exist_ok=True)


class DigitalEmployee:
    def __init__(self):
        self.context = {}       # 当前会话上下文
        self.pending = None     # 待确认的提取结果

    # ========== 主入口 ==========

    def process(self, user_input):
        user_input = user_input.strip()

        # Route 0: 确认/修改操作
        if self.pending and user_input.startswith("确认"):
            return self._confirm_generate()
        if self.pending and user_input.startswith("修改"):
            return self._apply_modification(user_input)
        if self.pending and user_input.startswith("取消"):
            self.pending = None
            return {"action": "cancelled", "msg": "已取消，可以重新上传"}

        # Route 1: 文件上传
        if os.path.isfile(user_input):
            return self._analyze_file(user_input)

        # Route 2: 自然语言生成
        if self._is_generate_request(user_input):
            return self._generate_from_text(user_input)

        # Route 3: Q&A
        return self._qa(user_input)

    def _is_generate_request(self, text):
        keywords = ['做', '生成', '报表', '创建', '制作', '写', '画', '来个']
        return any(kw in text for kw in keywords)

    # ========== 步骤①: 文件分析提取 ==========

    def _analyze_file(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()

        # 1. 原始解析
        if ext in ('.xlsx', '.xls'):
            raw = parse_excel(filepath)
            if not raw:
                return {"error": "无法解析Excel文件"}
            source_text = self._format_excel_preview(raw)
        elif ext in ('.png', '.jpg', '.jpeg'):
            raw = parse_image(filepath)
            source_text = self._format_image_preview(raw)
        else:
            return {"error": f"不支持的文件格式: {ext}"}

        # 2. LLM 理解并提议
        analysis = self._llm_analyze(source_text)

        # 3. 保存待确认
        self.pending = {
            "file": filepath,
            "raw": raw,
            "analysis": analysis,
            "source_text": source_text,
            "title": analysis.get("title", ""),
            "columns": analysis.get("columns", []),
            "sql": analysis.get("sql", ""),
            "table": analysis.get("table", ""),
        }

        # 4. 输出预览，等用户确认
        return {
            "action": "preview",
            "title": analysis.get("title", ""),
            "table": analysis.get("table", ""),
            "proposed_columns": analysis.get("columns", []),
            "suggested_sql": analysis.get("sql", ""),
            "msg": self._build_preview_message(analysis),
            "awaiting_confirm": True,
            "help": "输入「确认」生成CPT，或「修改:xxx」调整内容，或「取消」放弃",
        }

    def _format_excel_preview(self, data):
        lines = [f"Sheet: {data['sheet_name']}"]
        lines.append(f"表头: {data['headers']}")
        lines.append(f"推断类型: {data['data_types']}")
        lines.append("样本数据:")
        for row in data.get('sample_data', [])[:5]:
            lines.append("  " + " | ".join(row))
        return "\n".join(lines)

    def _format_image_preview(self, data):
        return f"OCR识别文本:\n{data['ocr_text'][:1500]}"

    def _build_preview_message(self, analysis):
        lines = ["=== 提取结果预览 ==="]
        lines.append(f"报表标题: {analysis.get('title', '?')}")
        lines.append(f"数据表: {analysis.get('table', '?')}")
        lines.append("")
        lines.append("列定义:")
        for i, col in enumerate(analysis.get("columns", [])):
            lines.append(f"  {i+1}. {col['name']} -> {col.get('field','?')} ({col.get('type','VARCHAR')})")
        lines.append("")
        lines.append(f"SQL: {analysis.get('sql', '?')}")
        lines.append(f"图表: {'是' if analysis.get('chart_type') else '否'}")
        lines.append("")
        lines.append("请确认以上信息是否正确:")
        lines.append("  · 输入「确认」→ 生成 CPT")
        lines.append("  · 输入「修改:标题改为XXX」→ 修改")
        lines.append("  · 输入「修改:删除第3列」→ 调整列")
        lines.append("  · 输入「取消」→ 重新开始")
        return "\n".join(lines)

    # ========== 步骤②: 用户确认/修改 ==========

    def _confirm_generate(self):
        if not self.pending:
            return {"error": "没有待确认的内容"}

        p = self.pending
        title = p["title"]
        columns = p["columns"]
        table = p.get("table", "report_data")
        sql = p.get("sql", "")

        # 构建CPT
        cpt_xml = build_v10_cpt(title=title, columns=columns, table_name=table, sql=sql)

        safe = re.sub(r'[^\w\u4e00-\u9fff]', '_', title)[:30]
        cpt_path = os.path.join(OUTPUT_DIR, safe + ".cpt")
        with open(cpt_path, "w", encoding="utf-8") as f:
            f.write(cpt_xml)

        import shutil
        shutil.copy2(cpt_path, os.path.join(FR_DIR, safe + ".cpt"))

        self.pending = None

        return {
            "action": "cpt_generated",
            "title": title,
            "columns": len(columns),
            "table": table,
            "sql": sql,
            "cpt_path": cpt_path,
            "preview_url": safe + ".cpt",
            "msg": f"✅ CPT已生成: {cpt_path}\n已在FineReport中可用: {safe}.cpt",
        }

    def _apply_modification(self, user_input):
        if not self.pending:
            return {"error": "没有待确认的内容"}

        mod = user_input.replace("修改:", "").replace("修改：", "").strip()
        analysis = self.pending["analysis"]

        # 用LLM理解修改意图
        from openai import OpenAI
        c = OpenAI(api_key="sk-79778f1a65f1484f81e863beb2ade2ee", base_url="https://api.deepseek.com")
        prompt = f"""用户在确认报表预览后提出了修改要求。根据修改要求更新JSON。

当前预览:
{json.dumps(analysis, ensure_ascii=False, indent=2)}

修改要求: {mod}

输出更新后的完整JSON（和输入格式一致）。"""
        try:
            r = c.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0, max_tokens=600, timeout=15
            )
            raw = r.choices[0].message.content
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                updated = json.loads(m.group())
                analysis.update(updated)
                self.pending["title"] = analysis.get("title", self.pending["title"])
                self.pending["columns"] = analysis.get("columns", self.pending["columns"])
                self.pending["sql"] = analysis.get("sql", self.pending.get("sql", ""))
                self.pending["table"] = analysis.get("table", self.pending.get("table", ""))
        except Exception as e:
            pass

        return {
            "action": "modified",
            "msg": self._build_preview_message(analysis),
            "awaiting_confirm": True,
        }

    # ========== 步骤③: 自然语言直接生成（跳过确认） ==========

    def _generate_from_text(self, text):
        from openai import OpenAI
        c = OpenAI(api_key="sk-79778f1a65f1484f81e863beb2ade2ee", base_url="https://api.deepseek.com")

        # 一次性提取+确认合并（自然语言不需要两步确认）
        prompt = f"""为FineReport生成报表定义。输出JSON:
{{"title":"标题","columns":[{{"name":"中文列","field":"英文","type":"VARCHAR/NUMBER/DATE"}}],"table":"表名","sql":"SELECT语句"}}

需求: {text}"""

        try:
            r = c.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0, max_tokens=600, timeout=15
            )
            raw = r.choices[0].message.content
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            params = json.loads(m.group()) if m else {}
        except:
            params = {"title": text[:20], "columns": [{"name": "列1", "field": "col1"}]}

        if not params.get("columns"):
            return {"error": "无法从需求中提取列信息，请更详细描述"}

        title = params.get("title", "报表")
        columns = params.get("columns", [])
        table = params.get("table", "report_data")
        sql = params.get("sql", f"SELECT * FROM [{table}]")

        cpt_xml = build_v10_cpt(title=title, columns=columns, table_name=table, sql=sql)
        safe = re.sub(r"[^\w\u4e00-\u9fff]", "_", title)[:30]
        cpt_path = os.path.join(OUTPUT_DIR, safe + ".cpt")
        with open(cpt_path, "w", encoding="utf-8") as f:
            f.write(cpt_xml)

        import shutil
        shutil.copy2(cpt_path, os.path.join(FR_DIR, safe + ".cpt"))

        return {
            "action": "cpt_generated",
            "title": title,
            "columns": len(columns),
            "sql": sql,
            "cpt_path": cpt_path,
            "preview_url": safe + ".cpt",
        }

    # ========== 其他 ==========

    def _llm_analyze(self, source_text):
        from openai import OpenAI
        c = OpenAI(api_key="sk-79778f1a65f1484f81e863beb2ade2ee", base_url="https://api.deepseek.com")

        prompt = f"""分析以下表格数据，推断FineReport报表结构。输出JSON:
{{"title":"报表标题","table":"建议表名","columns":[{{"name":"中文列名","field":"英文字段","type":"VARCHAR/NUMBER/DATE"}}],"sql":"SELECT语句","chart_type":null}}

数据:
{source_text[:2000]}"""

        try:
            r = c.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0, max_tokens=600, timeout=15
            )
            raw = r.choices[0].message.content
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            return json.loads(m.group()) if m else {"title": "", "columns": []}
        except:
            return {"title": "", "columns": []}

    def _qa(self, question):
        from openai import OpenAI
        c = OpenAI(api_key="sk-79778f1a65f1484f81e863beb2ade2ee", base_url="https://api.deepseek.com")
        r = c.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是FineReport专家，回答简洁实用，带具体步骤。"},
                {"role": "user", "content": question}
            ],
            temperature=0.3, max_tokens=600, timeout=20
        )
        return {"action": "qa", "question": question, "answer": r.choices[0].message.content}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        emp = DigitalEmployee()
        r = emp.process(" ".join(sys.argv[1:]))
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print("=" * 50)
        print("  帆软数字员工 Agent v5")
        print("  上传文件后先预览确认，再生成CPT")
        print("=" * 50)
        emp = DigitalEmployee()
        while True:
            try:
                u = input("\n> ").strip()
                if u.lower() in ("quit", "exit", "q"):
                    break
                if not u:
                    continue
                r = emp.process(u)
                msg = r.get("msg", "")
                if msg:
                    print(msg)
                elif r.get("answer"):
                    print("\n" + r["answer"])
                elif r.get("error"):
                    print("Error: " + r["error"])
            except KeyboardInterrupt:
                break
            except Exception as e:
                print("Error: " + str(e))
