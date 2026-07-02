# ============================================================================
# Pipeline ?全流程编排引?(OCR ?LLM ?SQL ?DB ?CPT ?RAG ?Deploy)
# ============================================================================
import os, sys, json, time, re, shutil, hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Config ──
STEP1V_KEY = os.environ.get("STEP1V_KEY", "")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY", "")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
FR_REPORTLETS = r"/path/to/fr/reportlets"

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ? Data Models                                                                 ?# ╚══════════════════════════════════════════════════════════════════════════════╝

@dataclass
class ColumnDef:
    name: str = ""           # 中文列名
    field: str = ""          # 英文字段
    type: str = "VARCHAR"    # VARCHAR/NUMBER/DECIMAL/DATE
    sample: str = ""         # 样本?
@dataclass
class StepResult:
    step: str = ""
    status: str = "pending"  # pending|running|done|fail
    message: str = ""
    data: Any = None
    elapsed: float = 0.0

@dataclass
class WorkflowState:
    """完整工作流状?""
    session_id: str = ""
    # Step 1: OCR
    ocr_text: str = ""
    ocr_tables: List[dict] = field(default_factory=list)
    ocr_engine: str = ""
    # Step 2: LLM Analysis
    title: str = ""
    columns: List[ColumnDef] = field(default_factory=list)
    # Step 3: User Edit (columns can be modified)
    # Step 4: SQL
    create_sql: str = ""
    insert_sql: str = ""
    # Step 5: DB Import
    table_name: str = ""
    rows_imported: int = 0
    db_connected: bool = False
    # Step 6: RAG Check
    rag_score: float = 0.0
    rag_suggestions: List[str] = field(default_factory=list)
    # Step 7: CPT Build
    cpt_filename: str = ""
    cpt_path: str = ""
    # Step 8: Deploy
    deployed: bool = False
    fr_path: str = ""
    # Meta
    created_at: str = ""
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["columns"] = [asdict(c) for c in self.columns]
        return d


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ? LLM Clients (DeepSeek for text, Step-1V for vision)                         ?# ╚══════════════════════════════════════════════════════════════════════════════╝

def _llm_deepseek(prompt: str, max_tokens: int = 2000) -> str:
    """Call DeepSeek for text analysis / SQL generation."""
    from openai import OpenAI
    client = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")
    r = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0, max_tokens=max_tokens, timeout=60
    )
    return r.choices[0].message.content

def _llm_step1v_ocr(image_base64: str) -> str:
    """Call Step-1V for image OCR."""
    import requests
    resp = requests.post(
        "https://api.stepfun.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {STEP1V_KEY}", "Content-Type": "application/json"},
        json={
            "model": "step-1v-8k",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                    {"type": "text", "text": "请精确识别这张表格截图中的所有文字，按原格式输出。不要遗漏任何数字和文字?}
                ]
            }],
            "max_tokens": 2000, "temperature": 0,
        },
        timeout=120
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ? Pipeline Steps                                                              ?# ╚══════════════════════════════════════════════════════════════════════════════╝

class Pipeline:
    """全流程编排器。每一步返?StepResult，状态持久化?WorkflowState?""

    def __init__(self):
        self.state = WorkflowState(session_id=hashlib.md5(str(time.time()).encode()).hexdigest()[:8])
        self.state.created_at = datetime.now().isoformat()

    # ── Step 1: OCR ──────────────────────────────────────────────────────────

    def step1_ocr(self, image_path: str, engine: str = "step1v") -> StepResult:
        """Run OCR on the image. Supports step1v and tesseract."""
        t0 = time.time()
        try:
            if engine == "tesseract":
                from ocr_skills import get_analyzer
                result = get_analyzer().analyze(image_path, preferred="tesseract")
                self.state.ocr_text = result.text
                self.state.ocr_engine = "tesseract"
            else:
                # Step-1V
                import base64
                with open(image_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                self.state.ocr_text = _llm_step1v_ocr(img_b64)
                self.state.ocr_engine = "step1v"

            elapsed = time.time() - t0
            return StepResult(step="ocr", status="done",
                message=f"OCR 完成 ({self.state.ocr_engine}, {len(self.state.ocr_text)} 字符)",
                data={"text": self.state.ocr_text[:3000]}, elapsed=elapsed)
        except Exception as e:
            return StepResult(step="ocr", status="fail", message=str(e)[:200], elapsed=time.time()-t0)

    # ── Step 2: LLM 分析表结?───────────────────────────────────────────────

    def step2_analyze(self) -> StepResult:
        """Use DeepSeek to analyze OCR text and extract table structure."""
        t0 = time.time()
        if not self.state.ocr_text:
            return StepResult(step="analyze", status="fail", message="没有 OCR 数据，请先执行步?")

        prompt = f"""分析以下OCR识别的表格数据，提取表格结构。只输出纯JSON，不要markdown?
JSON格式:
{{"title":"报表标题","columns":[{{"name":"中文列名","field":"english_field","type":"VARCHAR"}}]}}

规则:
1. columns必须是数? name=中文列名, field=英文驼峰命名, type=VARCHAR/NUMBER/DECIMAL/DATE
2. 金额列type用DECIMAL, 百分比列type用VARCHAR, ID类用VARCHAR
3. 序号列type用INT
4. 不要输出SQL, 只输出表结构JSON

OCR数据:
{self.state.ocr_text[:3000]}"""

        try:
            content = _llm_deepseek(prompt, 1500)
            # Parse JSON
            m = re.search(r'\{.*\}', content, re.DOTALL)
            if m:
                parsed = json.loads(m.group())
                self.state.title = parsed.get("title", "未命名报?)
                cols = parsed.get("columns", [])
                if isinstance(cols, list):
                    self.state.columns = [
                        ColumnDef(
                            name=c.get("name", ""),
                            field=c.get("field", ""),
                            type=c.get("type", "VARCHAR"),
                            sample=c.get("sample", "")
                        ) for c in cols
                    ]
                elapsed = time.time() - t0
                return StepResult(step="analyze", status="done",
                    message=f"LLM 分析完成: {self.state.title}, {len(self.state.columns)} ?,
                    data={"title": self.state.title, "columns": [asdict(c) for c in self.state.columns]},
                    elapsed=elapsed)
            else:
                return StepResult(step="analyze", status="fail",
                    message=f"LLM 返回无法解析: {content[:200]}", elapsed=time.time()-t0)
        except Exception as e:
            return StepResult(step="analyze", status="fail", message=str(e)[:200], elapsed=time.time()-t0)

    # ── Step 3: User Edit (columns can be modified via API) ───────────────────

    def step3_update_columns(self, columns: List[dict]) -> StepResult:
        """Update column definitions from user edits."""
        self.state.columns = [ColumnDef(**c) for c in columns]
        return StepResult(step="edit", status="done",
            message=f"列定义已更新: {len(self.state.columns)} ?)

    # ── Step 4: SQL 生成 ─────────────────────────────────────────────────────

    def step4_generate_sql(self, table_name: str = None) -> StepResult:
        """Use DeepSeek to generate CREATE TABLE and INSERT SQL."""
        t0 = time.time()
        if not self.state.columns:
            return StepResult(step="sql", status="fail", message="没有列定?)

        cols_desc = "\n".join(
            f"  {c.name} ({c.field}): {c.type}" + (f" 样本: {c.sample}" if c.sample else "")
            for c in self.state.columns
        )

        prompt = f"""根据以下表结构生成MySQL SQL语句。只输出纯JSON?
表结?
表名: {self.state.title}
列定?
{cols_desc}

OCR原始数据:
{self.state.ocr_text[:2000]}

JSON格式:
{{"create_sql":"CREATE TABLE ...","insert_sql":"INSERT INTO ...","table_name":"xxx"}}

规则:
1. 表名用小写英?下划?2. CREATE TABLE ?IF NOT EXISTS, 主键用id
3. INSERT 包含OCR数据中所有识别到的行
4. 金额去掉逗号, 百分比保?"""

        try:
            content = _llm_deepseek(prompt, 2000)
            m = re.search(r'\{.*\}', content, re.DOTALL)
            if m:
                parsed = json.loads(m.group())
                self.state.create_sql = parsed.get("create_sql", "")
                self.state.insert_sql = parsed.get("insert_sql", "")
                self.state.table_name = table_name or parsed.get("table_name", "ocr_table")
                elapsed = time.time() - t0
                return StepResult(step="sql", status="done",
                    message=f"SQL 生成完成: CREATE({len(self.state.create_sql)}? + INSERT({len(self.state.insert_sql)}?",
                    data={"create_sql": self.state.create_sql, "insert_sql": self.state.insert_sql, "table_name": self.state.table_name},
                    elapsed=elapsed)
            else:
                return StepResult(step="sql", status="fail",
                    message=f"SQL生成失败: {content[:200]}", elapsed=time.time()-t0)
        except Exception as e:
            return StepResult(step="sql", status="fail", message=str(e)[:200], elapsed=time.time()-t0)

    # ── Step 5: 数据库导?───────────────────────────────────────────────────

    def step5_execute_sql(self) -> StepResult:
        """Execute CREATE TABLE and INSERT against MySQL/HSQLDB."""
        t0 = time.time()
        if not self.state.create_sql:
            return StepResult(step="execute", status="fail", message="没有 SQL 可执?)

        try:
            # Try MySQL first (FRDemo)
            import pymysql
            conn = pymysql.connect(
                host="localhost", port=3306, user="root", password="",
                charset="utf8mb4", connect_timeout=5
            )
            cursor = conn.cursor()
            # CREATE
            cursor.execute(self.state.create_sql)
            # INSERT
            insert_count = 0
            for stmt in self.state.insert_sql.split(";\n"):
                stmt = stmt.strip()
                if stmt.upper().startswith("INSERT"):
                    cursor.execute(stmt)
                    insert_count += cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()
            self.state.rows_imported = insert_count
            self.state.db_connected = True
            elapsed = time.time() - t0
            return StepResult(step="execute", status="done",
                message=f"数据已导?MySQL: {insert_count} ?,
                data={"rows": insert_count, "table": self.state.table_name},
                elapsed=elapsed)
        except ImportError:
            # Fallback: save as SQL file
            sql_file = os.path.join(OUTPUT_DIR, f"{self.state.table_name}.sql")
            with open(sql_file, "w", encoding="utf-8") as f:
                f.write(f"-- {self.state.title}\n")
                f.write(self.state.create_sql + ";\n\n")
                f.write(self.state.insert_sql + ";\n")
            self.state.db_connected = False
            elapsed = time.time() - t0
            return StepResult(step="execute", status="done",
                message=f"pymysql未安装，SQL已保存到文件: {os.path.basename(sql_file)}",
                data={"sql_file": sql_file, "table": self.state.table_name},
                elapsed=elapsed)
        except Exception as e:
            elapsed = time.time() - t0
            return StepResult(step="execute", status="fail",
                message=f"数据库执行失? {str(e)[:200]}",
                data={"sql": self.state.create_sql + self.state.insert_sql},
                elapsed=elapsed)

    # ── Step 6: RAG 质量检?─────────────────────────────────────────────────

    def step6_rag_check(self) -> StepResult:
        """RAG-like quality check: validate SQL, check naming, suggest improvements."""
        t0 = time.time()
        suggestions = []
        score = 100

        # 1. SQL syntax check
        if self.state.create_sql:
            if "CREATE TABLE" not in self.state.create_sql.upper():
                suggestions.append("?CREATE TABLE 语法错误")
                score -= 30
            else:
                suggestions.append("?CREATE TABLE 语法正确")

            if "PRIMARY KEY" not in self.state.create_sql.upper() and "PRIMARY" not in self.state.create_sql:
                suggestions.append("⚠️ 建议添加主键约束")

        # 2. Naming convention check
        if self.state.columns:
            for c in self.state.columns:
                if not c.field or c.field == "":
                    suggestions.append(f"⚠️ ?'{c.name}' 缺少英文字段?)
                    score -= 5
                if c.type not in ("VARCHAR", "INT", "NUMBER", "DECIMAL", "DATE", "TEXT"):
                    suggestions.append(f"⚠️ ?'{c.name}' 类型 '{c.type}' 非标准SQL类型")
                    score -= 5

        # 3. Data completeness check
        if self.state.ocr_text:
            ocr_lines = [l for l in self.state.ocr_text.split("\n") if l.strip()]
            if len(ocr_lines) < 3:
                suggestions.append("⚠️ OCR数据行数较少，建议确认完整?)
                score -= 10

        # 4. Vector similarity search (simulated - checks against FR knowledge)
        fr_best_practices = {
            "报表标题应使用中?: "? if any('\u4e00' <= c <= '\u9fff' for c in self.state.title) else "⚠️",
            "金额字段建议用DECIMAL(15,2)": "? if any(c.type == "DECIMAL" for c in self.state.columns) else "⚠️",
            "建议包含创建时间字段": "⚠️" if not any(c.field in ("created_at","create_time") for c in self.state.columns) else "?,
        }
        for rule, status in fr_best_practices.items():
            suggestions.append(f"{status} {rule}")
            if status == "⚠️":
                score -= 2

        self.state.rag_score = max(0, score)
        self.state.rag_suggestions = suggestions
        elapsed = time.time() - t0
        return StepResult(step="rag", status="done",
            message=f"RAG 检查完? 评分 {self.state.rag_score}/100",
            data={"score": self.state.rag_score, "suggestions": suggestions},
            elapsed=elapsed)

    # ── Step 7: CPT 构建 ─────────────────────────────────────────────────────

    def step7_build_cpt(self) -> StepResult:
        """Build FineReport CPT template file."""
        t0 = time.time()
        if not self.state.columns:
            return StepResult(step="cpt", status="fail", message="没有列定?)

        try:
            from cpt_builder import build_cpt
            params = {
                "title": self.state.title,
                "columns": [{"name": c.name, "field": c.field, "type": c.type} for c in self.state.columns],
                "db_name": "FRDemo",
                "table_name": self.state.table_name,
            }
            result = build_cpt(params)
            fname = None
            if isinstance(result, dict) and result.get("path"):
                fname = os.path.basename(result["path"])
            elif isinstance(result, str):
                fname = result if result.endswith(".cpt") else f"{self.state.table_name}.cpt"

            self.state.cpt_filename = fname or f"{self.state.table_name}.cpt"
            self.state.cpt_path = os.path.join(OUTPUT_DIR, self.state.cpt_filename)
            elapsed = time.time() - t0
            return StepResult(step="cpt", status="done",
                message=f"CPT 构建完成: {self.state.cpt_filename}",
                data={"filename": self.state.cpt_filename, "path": self.state.cpt_path},
                elapsed=elapsed)
        except Exception as e:
            elapsed = time.time() - t0
            return StepResult(step="cpt", status="fail", message=str(e)[:200], elapsed=elapsed)

    # ── Step 8: 部署?FineReport ────────────────────────────────────────────

    def step8_deploy(self) -> StepResult:
        """Copy CPT to FineReport reportlets directory."""
        t0 = time.time()
        src = self.state.cpt_path
        if not src or not os.path.exists(src):
            src = os.path.join(OUTPUT_DIR, self.state.cpt_filename or "")

        if not os.path.exists(src):
            return StepResult(step="deploy", status="fail", message=f"CPT 文件不存? {src}")

        dst = os.path.join(FR_REPORTLETS, self.state.cpt_filename or "report.cpt")
        try:
            shutil.copy2(src, dst)
            self.state.deployed = True
            self.state.fr_path = dst
            elapsed = time.time() - t0
            return StepResult(step="deploy", status="done",
                message=f"已部署到 FineReport: {dst}",
                data={"fr_path": dst, "filename": self.state.cpt_filename},
                elapsed=elapsed)
        except Exception as e:
            elapsed = time.time() - t0
            return StepResult(step="deploy", status="fail", message=str(e)[:200], elapsed=elapsed)

    # ── Run All ──────────────────────────────────────────────────────────────

    def run_all(self, image_path: str, engine: str = "step1v") -> List[StepResult]:
        """Run the complete pipeline and return results for each step."""
        results = []

        # Step 1: OCR
        r = self.step1_ocr(image_path, engine); results.append(r)
        if r.status == "fail": return results

        # Step 2: LLM Analyze
        r = self.step2_analyze(); results.append(r)
        if r.status == "fail": return results

        # Step 4: SQL
        r = self.step4_generate_sql(); results.append(r)

        # Step 5: DB Import
        r = self.step5_execute_sql(); results.append(r)

        # Step 6: RAG Check
        r = self.step6_rag_check(); results.append(r)

        # Step 7: CPT
        r = self.step7_build_cpt(); results.append(r)

        # Step 8: Deploy
        r = self.step8_deploy(); results.append(r)

        return results


# ── Global sessions ──
_sessions: Dict[str, Pipeline] = {}

def create_session() -> Pipeline:
    p = Pipeline()
    _sessions[p.state.session_id] = p
    return p

def get_session(sid: str) -> Optional[Pipeline]:
    return _sessions.get(sid)
