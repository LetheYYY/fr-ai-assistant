
# ======================================================================
# WORKFLOW API - 8-Step Pipeline
# ======================================================================
from pipeline import Pipeline
_pipes = {}

@app.post("/api/workflow/start")
def wf_start():
    import uuid
    tid = uuid.uuid4().hex[:12]
    p = Pipeline()
    _pipes[tid] = p
    return JSONResponse({"task_id": tid, "ok": True})

@app.post("/api/workflow/{tid}/ocr")
async def wf_ocr(tid: str, file: UploadFile = File(...), engine: str = Form("auto")):
    p = _pipes.get(tid)
    if not p: raise HTTPException(404, "Task not found")
    tmp = os.path.join(tempfile.gettempdir(), f"ocr_{tid}.jpg")
    with open(tmp, "wb") as f: f.write(await file.read())
    try:
        r = p.step1_ocr(tmp)
        os.remove(tmp)
        return JSONResponse(r)
    except Exception as e:
        if os.path.exists(tmp): os.remove(tmp)
        raise HTTPException(500, str(e))

@app.post("/api/workflow/{tid}/analyze")
def wf_analyze(tid: str):
    p = _pipes.get(tid)
    if not p: raise HTTPException(404, "Task not found")
    return JSONResponse(p.step2_analyze())

@app.post("/api/workflow/{tid}/sql")
def wf_sql(tid: str):
    p = _pipes.get(tid)
    if not p: raise HTTPException(404, "Task not found")
    return JSONResponse(p.step4_generate_sql())

@app.post("/api/workflow/{tid}/exec")
def wf_exec(tid: str):
    p = _pipes.get(tid)
    if not p: raise HTTPException(404, "Task not found")
    return JSONResponse(p.step5_execute_sql())

@app.post("/api/workflow/{tid}/cpt")
def wf_cpt(tid: str):
    p = _pipes.get(tid)
    if not p: raise HTTPException(404, "Task not found")
    return JSONResponse(p.step7_build_cpt())

@app.post("/api/workflow/{tid}/rag")
def wf_rag(tid: str):
    p = _pipes.get(tid)
    if not p: raise HTTPException(404, "Task not found")
    return JSONResponse(p.step6_rag_check())

@app.post("/api/workflow/{tid}/deploy")
def wf_deploy(tid: str):
    p = _pipes.get(tid)
    if not p: raise HTTPException(404, "Task not found")
    return JSONResponse(p.step8_deploy())

@app.get("/api/workflow/{tid}/status")
def wf_status(tid: str):
    p = _pipes.get(tid)
    if not p: raise HTTPException(404, "Task not found")
    s = p.state
    return JSONResponse({"steps": [{"step": k, "status": "done" if v else "pending", "data": v} for k,v in s.__dict__.items()]})

# === Static (must be last) ===
WEB = r'os.path.dirname(os.path.abspath(__file__))\web'
os.makedirs(WEB, exist_ok=True)
if os.path.isfile(os.path.join(WEB, 'index.html')):
    app.mount('/', StaticFiles(directory=WEB, html=True), name='static')

# === Run ===
if __name__ == '__main__':
    import uvicorn
    print(f'FR Digital Employee API v2.0')
    print(f'Docs: http://localhost:8899/docs')
    uvicorn.run(app, host='0.0.0.0', port=8899)
