# ============================================================================
# FR Reader ?帆软 FineReport 信息读取模块
# ============================================================================
# 支持离线模式（读文件系统）和在线模式（HTTP API?
# ============================================================================

import os, sys, re, json, shutil
import datetime as dt
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

# ── FR 安装路径 ──
FR_HOME = r"C:\FineReport_11.0"
FR_REPORTLETS = os.path.join(FR_HOME, "webapps", "webroot", "WEB-INF", "reportlets")
FR_RESOURCES = os.path.join(FR_HOME, "webapps", "webroot", "WEB-INF", "resources")
FR_FINEDB = os.path.join(FR_HOME, "webapps", "webroot", "WEB-INF", "embed", "finedb")
FR_LOG_DIR = os.path.join(FR_HOME, "logs")
FR_SERVER_XML = os.path.join(FR_HOME, "server", "conf", "server.xml")
FR_WEB_XML = os.path.join(FR_HOME, "webapps", "webroot", "WEB-INF", "web.xml")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ? SECTION 1 ?系统状?                                                      ?
# ╚══════════════════════════════════════════════════════════════════════════════╝

def get_fr_status() -> Dict[str, Any]:
    """获取 FineReport 运行状态（离线 + 在线检测）"""
    status = {
        "installed": os.path.isdir(FR_HOME),
        "fr_home": FR_HOME,
        "running": False,
        "port": None,
        "version": None,
        "memory_mb": None,
    }
    
    if not status["installed"]:
        return status
    
    # 1. 读取端口 - FR 默认 8075
    status["port"] = 8075
    try:
        with open(FR_SERVER_XML, "r", encoding="utf-8") as f:
            content = f.read()
        # 尝试找非 SSL ?HTTP Connector
        for m in re.finditer(r'<Connector\s+([^>]*?)>', content):
            attrs = m.group(1)
            if 'SSLEnabled' not in attrs and 'protocol="AJP' not in attrs:
                pm = re.search(r'port="(\d+)"', attrs)
                if pm:
                    status["port"] = int(pm.group(1))
                    break
    except Exception:
        pass
    
    port = 8075  # FR 默认使用 8075
    
    # 2. 检测是否运?
    try:
        import urllib.request
        req = urllib.request.Request(f"http://localhost:{port}/webroot/decision", 
                                      headers={"User-Agent": "FR-Assistant"})
        resp = urllib.request.urlopen(req, timeout=3)
        status["running"] = resp.status == 200
    except Exception:
        status["running"] = False
    
    # 3. 读取版本
    try:
        lib_dir = os.path.join(FR_HOME, "lib")
        for f in os.listdir(lib_dir):
            m = re.match(r'fr-core-(\d+\.\d+(?:\.\d+)?)\.jar', f)
            if m:
                status["version"] = m.group(1)
                break
        if not status["version"]:
            for f in os.listdir(lib_dir):
                m = re.match(r'fine-report-engine-(\d+\.\d+(?:\.\d+)?)\.jar', f)
                if m:
                    status["version"] = m.group(1)
                    break
    except Exception:
        pass
    
    # 4. 内存估算
    if status["running"]:
        try:
            import subprocess
            result = subprocess.run(
                ['wmic', 'process', 'where', 'name="java.exe"', 'get', 'WorkingSetSize'], 
                capture_output=True, text=True, shell=True, timeout=5
            )
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip().isdigit()]
            if lines:
                total_bytes = sum(int(l) for l in lines)
                status["memory_mb"] = round(total_bytes / 1024 / 1024, 1)
        except Exception:
            pass
    
    status["checked_at"] = dt.datetime.now().isoformat()
    return status


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ? SECTION 2 ?数据源信?                                                    ?
# ╚══════════════════════════════════════════════════════════════════════════════╝

def get_datasources() -> List[Dict[str, Any]]:
    """读取 FineReport 数据源列表（?finedb HSQLDB 解析?""
    ds_list = []
    
    # 1. 解析 fine_conf.xml（如果有?
    fine_conf = os.path.join(FR_RESOURCES, "fine_conf.xml")
    if os.path.exists(fine_conf):
        try:
            with open(fine_conf, "r", encoding="utf-8") as f:
                content = f.read()
            # 提取数据库连?XML
            for match in re.finditer(r'<DatabaseConnection[^>]*>([\s\S]*?)</DatabaseConnection>', content):
                attrs = match.group(0)
                name = re.search(r'name="([^"]*)"', attrs)
                driver = re.search(r'driver="([^"]*)"', attrs)
                url = re.search(r'url="([^"]*)"', attrs)
                user = re.search(r'user="([^"]*)"', attrs)
                ds_list.append({
                    "name": name.group(1) if name else "unknown",
                    "driver": driver.group(1) if driver else "",
                    "url": url.group(1) if url else "",
                    "user": user.group(1) if user else "",
                    "db_type": _guess_db_type(url.group(1) if url else ""),
                })
        except Exception:
            pass
    
    # 2. 解析 finedb/db.script
    if not ds_list:
        db_script = os.path.join(FR_FINEDB, "db.script")
        if os.path.exists(db_script):
            try:
                with open(db_script, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                # 查找包含 JDBC URL 的行
                for line in content.splitlines():
                    if "jdbc:" in line.lower():
                        url_match = re.search(r"(jdbc:\w+://\S+)", line)
                        if url_match:
                            url = url_match.group(1).rstrip("'")
                            name_match = re.search(r"'([^']*)'\s*,\s*'"+re.escape(url), line)
                            ds_list.append({
                                "name": name_match.group(1) if name_match else "datasource",
                                "driver": _driver_from_url(url),
                                "url": url,
                                "user": "",
                                "db_type": _guess_db_type(url),
                            })
            except Exception:
                pass
    
    # 3. 确保至少有一个内?FRDemo
    if not ds_list:
        ds_list = [{
            "name": "FRDemo", "driver": "com.mysql.jdbc.Driver",
            "url": "jdbc:mysql://localhost:3306/frdemo",
            "user": "root", "db_type": "MySQL"
        }]
    
    return ds_list


def test_datasource_connection(ds_name: str) -> Dict[str, Any]:
    """测试数据源连?""
    ds_list = get_datasources()
    ds = next((d for d in ds_list if d["name"] == ds_name), None)
    
    result = {"name": ds_name, "connected": False, "error": ""}
    
    if not ds:
        result["error"] = f"数据?'{ds_name}' 未找?
        return result
    
    url = ds.get("url", "")
    user = ds.get("user", "root")
    
    if not url:
        result["error"] = "缺少 JDBC URL"
        return result
    
    # 尝试连接
    try:
        db_type = ds.get("db_type", "").lower()
        
        if "mysql" in db_type or "mysql" in url:
            try:
                import pymysql
                # ?JDBC URL 提取 host/port/db
                m = re.search(r'//([^:/]+)(?::(\d+))?/(\w+)', url)
                if m:
                    host, port, db = m.group(1), m.group(2) or "3306", m.group(3)
                    conn = pymysql.connect(host=host, port=int(port), user=user, 
                                           password="", database=db, connect_timeout=3)
                    conn.close()
                    result["connected"] = True
            except ImportError:
                result["error"] = "pymysql not installed"
            except Exception as e:
                result["error"] = str(e)[:200]
        
        elif "hsqldb" in url:
            db_path = re.search(r'//(?:localhost)?/(.+)', url)
            if db_path:
                path = db_path.group(1)
                result["connected"] = os.path.exists(path) or os.path.exists(path + ".script")
                if result["connected"]:
                    result["note"] = "HSQLDB file found"
                else:
                    result["error"] = f"HSQLDB file not found: {path}"
        else:
            result["error"] = f"Unsupported DB type: {db_type}"
    except Exception as e:
        result["error"] = str(e)[:200]
    
    return result


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ? SECTION 3 ?报表列表 & 搜索                                                ?
# ╚══════════════════════════════════════════════════════════════════════════════╝

def list_reports(keyword: str = "", limit: int = 100, page: int = 1) -> Dict[str, Any]:
    """列出所?CPT 报表文件（支持分页和搜索?""
    reports = []
    
    if not os.path.isdir(FR_REPORTLETS):
        return {"reports": [], "total": 0, "error": f"Reportlets not found: {FR_REPORTLETS}"}
    
    for root, dirs, files in os.walk(FR_REPORTLETS):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'reportlets_versions']
        
        for fname in files:
            if not fname.endswith(".cpt"):
                continue
            
            fpath = os.path.join(root, fname)
            stat = os.stat(fpath)
            rel_path = os.path.relpath(fpath, FR_REPORTLETS)
            
            name_no_ext = fname[:-4]
            
            # 搜索过滤
            if keyword and keyword.lower() not in name_no_ext.lower() and keyword.lower() not in rel_path.lower():
                continue
            
            reports.append({
                "name": fname,
                "path": rel_path,
                "size_kb": round(stat.st_size / 1024, 1),
                "modified": dt.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "folder": os.path.dirname(rel_path) or ".",
            })
    
    # 按修改时间排?
    reports.sort(key=lambda r: r["modified"], reverse=True)
    total = len(reports)
    
    # 分页
    start = (page - 1) * limit
    end = start + limit
    paged = reports[start:end]
    
    return {
        "reports": paged,
        "total": total,
        "page": page,
        "page_size": limit,
        "pages": (total + limit - 1) // limit,
    }


def get_folders() -> List[str]:
    """获取报表目录?""
    folders = set()
    if not os.path.isdir(FR_REPORTLETS):
        return []
    
    for root, dirs, files in os.walk(FR_REPORTLETS):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'reportlets_versions']
        rel = os.path.relpath(root, FR_REPORTLETS)
        if rel != ".":
            folders.add(rel)
    
    return sorted(folders)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ? SECTION 4 ?报表详情 (解析 CPT XML)                                        ?
# ╚══════════════════════════════════════════════════════════════════════════════╝

def get_report_detail(rel_path: str) -> Dict[str, Any]:
    """读取单个报表详情：数据集 SQL、字段、参?""
    fpath = os.path.join(FR_REPORTLETS, rel_path)
    
    result = {
        "name": os.path.basename(rel_path),
        "path": rel_path,
        "exists": os.path.exists(fpath),
        "size_kb": round(os.path.getsize(fpath) / 1024, 1) if os.path.exists(fpath) else 0,
        "modified": dt.datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M") if os.path.exists(fpath) else "",
        "title": "",
        "datasets": [],
        "sheets": [],
        "error": "",
    }
    
    if not result["exists"]:
        result["error"] = "File not found"
        return result
    
    try:
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        # 解析报表标题（第一?Cell Element?
        title_match = re.search(r'<O><!\[CDATA\[(.*?)\]\]></O>', content)
        if title_match:
            result["title"] = title_match.group(1)
        
        # 解析数据?
        for ds_match in re.finditer(r'<TableData[^>]*name="([^"]*)"[^>]*>([\s\S]*?)</TableData>', content):
            ds_name = ds_match.group(1)
            ds_content = ds_match.group(2)
            
            ds_info = {"name": ds_name, "type": "unknown", "connection": "", "sql": "", "fields": []}
            
            # 数据库连?
            conn_match = re.search(r'<DatabaseName><!\[CDATA\[(.*?)\]\]></DatabaseName>', ds_content)
            if conn_match:
                ds_info["connection"] = conn_match.group(1)
                ds_info["type"] = "database"
            
            # SQL 查询
            sql_match = re.search(r'<Query><!\[CDATA\[(.*?)\]\]></Query>', ds_content)
            if sql_match:
                ds_info["sql"] = sql_match.group(1)
            
            # 内置数据?
            if not ds_info["sql"]:
                builtin_match = re.search(r'class="com\.fr\.data\.impl\.(\w+)"', ds_content)
                if builtin_match:
                    ds_info["type"] = builtin_match.group(1)
            
            result["datasets"].append(ds_info)
        
        # 解析 Sheet 页面
        for sheet_match in re.finditer(r'<Report[^>]*name="([^"]*)"[^>]*>', content):
            result["sheets"].append(sheet_match.group(1))
        
    except Exception as e:
        result["error"] = str(e)[:300]
    
    return result


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ? SECTION 5 ?日志                                                           ?
# ╚══════════════════════════════════════════════════════════════════════════════╝

def get_logs(tail: int = 100, level: str = "") -> Dict[str, Any]:
    """获取 FineReport/Tomcat 最新日?""
    log_files = []
    
    if os.path.isdir(FR_LOG_DIR):
        for fname in sorted(os.listdir(FR_LOG_DIR), reverse=True):
            fpath = os.path.join(FR_LOG_DIR, fname)
            if os.path.isfile(fpath) and fpath.endswith(('.log', '.out', '.txt')):
                size = os.path.getsize(fpath)
                log_files.append({"name": fname, "size_kb": round(size / 1024, 1)})
    
    # 读取最新的日志文件
    lines = []
    if log_files:
        latest = os.path.join(FR_LOG_DIR, log_files[0]["name"])
        try:
            with open(latest, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()
                lines = all_lines[-tail:]
                lines = [l.rstrip() for l in lines]
        except Exception:
            pass
    
    return {
        "files": log_files[:10],
        "latest_file": log_files[0]["name"] if log_files else "",
        "lines": lines,
        "total_lines": len(lines),
    }


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ? SECTION 6 ?配置信息                                                       ?
# ╚══════════════════════════════════════════════════════════════════════════════╝

def get_fr_config() -> Dict[str, Any]:
    """读取 FineReport 关键配置"""
    config = {"port": 8075, "context_path": "/webroot", "memory": {}}
    
    # 端口
    try:
        with open(FR_SERVER_XML, "r", encoding="utf-8") as f:
            m = re.search(r'<Connector\s+port="(\d+)"', f.read())
            if m:
                config["port"] = int(m.group(1))
    except Exception:
        pass
    
    # 上下文路?
    try:
        with open(FR_WEB_XML, "r", encoding="utf-8") as f:
            m = re.search(r'<context-param>\s*<param-name>contextPath</param-name>\s*<param-value>(.*?)</param-value>', f.read(), re.DOTALL)
            if m:
                config["context_path"] = m.group(1)
    except Exception:
        pass
    
    # Tomcat 内存设置
    bat_file = os.path.join(FR_HOME, "bin", "catalina.bat")
    if os.path.exists(bat_file):
        try:
            with open(bat_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            xms = re.search(r'Xms(\d+[kmg])', content, re.I)
            xmx = re.search(r'Xmx(\d+[kmg])', content, re.I)
            if xms: config["memory"]["xms"] = xms.group(1).upper()
            if xmx: config["memory"]["xmx"] = xmx.group(1).upper()
        except Exception:
            pass
    
    # 目录大小
    config["disk_usage"] = {}
    for label, path in [("reportlets", FR_REPORTLETS), ("logs", FR_LOG_DIR)]:
        if os.path.isdir(path):
            total = sum(
                os.path.getsize(os.path.join(r, f))
                for r, _, fs in os.walk(path) for f in fs
            )
            config["disk_usage"][label] = f"{total / 1024 / 1024:.1f} MB"
    
    # CPT 文件统计
    cpt_count = 0
    if os.path.isdir(FR_REPORTLETS):
        cpt_count = sum(1 for r, _, fs in os.walk(FR_REPORTLETS) for f in fs if f.endswith('.cpt'))
    config["total_reports"] = cpt_count
    
    return config


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ? SECTION 7 ?快捷操作                                                       ?
# ╚══════════════════════════════════════════════════════════════════════════════╝

def backup_report(rel_path: str) -> Dict[str, Any]:
    """备份一?CPT 报表"""
    src = os.path.join(FR_REPORTLETS, rel_path)
    if not os.path.exists(src):
        return {"ok": False, "error": f"File not found: {rel_path}"}
    
    backup_dir = os.path.join(os.path.dirname(FR_REPORTLETS), "reportlets_versions")
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = os.path.basename(rel_path)
    dst_name = f"{os.path.splitext(fname)[0]}_{timestamp}.cpt"
    dst = os.path.join(backup_dir, dst_name)
    
    try:
        shutil.copy2(src, dst)
        return {"ok": True, "backup": dst_name, "size_kb": round(os.path.getsize(dst)/1024, 1)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_dashboard_summary() -> Dict[str, Any]:
    """Dashboard 首页汇总信?""
    status = get_fr_status()
    config = get_fr_config()
    reports = list_reports(limit=1)
    
    return {
        "fr_status": status,
        "version": status.get("version", "N/A"),
        "port": config.get("port", 8075),
        "total_reports": config.get("total_reports", 0),
        "datasources": len(get_datasources()),
        "disk_reportlets": config.get("disk_usage", {}).get("reportlets", "0 MB"),
        "disk_logs": config.get("disk_usage", {}).get("logs", "0 MB"),
        "memory_config": config.get("memory", {}),
        "recent_report": reports["reports"][0] if reports["reports"] else None,
    }


# ── 辅助函数 ──

def _guess_db_type(url: str) -> str:
    url_lower = url.lower()
    if "mysql" in url_lower: return "MySQL"
    if "oracle" in url_lower: return "Oracle"
    if "sqlserver" in url_lower: return "SQL Server"
    if "hsqldb" in url_lower: return "HSQLDB"
    if "postgresql" in url_lower: return "PostgreSQL"
    if "sqlite" in url_lower: return "SQLite"
    return "Unknown"


def _driver_from_url(url: str) -> str:
    db = _guess_db_type(url)
    drivers = {
        "MySQL": "com.mysql.jdbc.Driver",
        "Oracle": "oracle.jdbc.OracleDriver",
        "SQL Server": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
        "PostgreSQL": "org.postgresql.Driver",
        "HSQLDB": "org.hsqldb.jdbcDriver",
        "SQLite": "org.sqlite.JDBC",
    }
    return drivers.get(db, "")


# ── CLI ──
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="FR Reader CLI")
    p.add_argument("action", nargs="?", default="status",
                   choices=["status","datasources","reports","report","config","logs","dashboard","backup","test-ds"])
    p.add_argument("--keyword", "-k", default="")
    p.add_argument("--report", "-r", default="")
    p.add_argument("--ds", default="")
    p.add_argument("--tail", type=int, default=50)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true", help="Output JSON only")
    args = p.parse_args()
    
    def out(obj):
        if args.json:
            print(json.dumps(obj, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))
    
    if args.action == "status":
        out(get_fr_status())
    elif args.action == "datasources":
        out(get_datasources())
    elif args.action == "reports":
        out(list_reports(keyword=args.keyword, limit=args.limit))
    elif args.action == "report":
        out(get_report_detail(args.report))
    elif args.action == "config":
        out(get_fr_config())
    elif args.action == "logs":
        out(get_logs(tail=args.tail))
    elif args.action == "dashboard":
        out(get_dashboard_summary())
    elif args.action == "backup":
        out(backup_report(args.report))
    elif args.action == "test-ds":
        out(test_datasource_connection(args.ds))
