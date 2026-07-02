import sys,os,json,time,base64,tempfile,shutil,uuid
from fastapi import FastAPI,UploadFile,File,Form,HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse,JSONResponse
from pydantic import BaseModel,Field

app=FastAPI(title='FR Digital Employee v3')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])
sys.path.insert(0,r"os.path.dirname(os.path.abspath(__file__))")

FR=None;OCR=None
class ChatReq(BaseModel):message:str=Field(...,min_length=1)
class BuildReq(BaseModel):title:str;columns:list;data:list=None;db_name:str='FRDemo'

class _FRW:  # wrapper
    def __init__(s):
        import fr_reader as f;s.f=f
    def check_status(s):
        r=s.f.get_fr_status();r['total_reports']=len(s.f.list_reports())
        r['datasources']=s.f.get_datasources();return r
    def list_reports(s,k=''):
        r=s.f.list_reports(k)
        return r['reports'] if isinstance(r,dict) else r
    def read_report_detail(s,n):return s.f.get_report_detail(n)
    def read_datasources(s):return s.f.get_datasources()
    def read_config(s):return s.f.get_fr_config()
    def read_logs(s,t=50):return s.f.get_logs(t)

def gf():
    global FR
    if FR is None:FR=_FRW()
    return FR

def go():
    global OCR
    if OCR is None:
        from ocr_skills import get_analyzer;OCR=get_analyzer()
    return OCR

@app.get('/api/health')
def health():return{'status':'ok'}

@app.get('/api/fr/status')
def fs():
    try:return gf().check_status()
    except Exception as e:raise HTTPException(500,str(e))

@app.get('/api/fr/reports')
def fr(keyword:str='',page:int=1,size:int=50):
    rpts=gf().list_reports(keyword)
    total=len(rpts) if isinstance(rpts,list) else 0
    s=(page-1)*size;sl=rpts[s:s+size] if isinstance(rpts,list) else[]
    return{'total':total,'page':page,'reports':sl}

@app.get('/api/fr/reports/{name:path}')
def fd(name:str):
    d=gf().read_report_detail(name)
    if d.get('error'):raise HTTPException(404,d['error'])
    return d

@app.get('/api/fr/datasources')
def fds():return gf().read_datasources()

@app.get('/api/fr/config')
def fc():return gf().read_config()

@app.post('/api/llm')
def llm(req:ChatReq):
    from openai import OpenAI
    c=OpenAI(api_key='sk-79778f1a65f1484f81e863beb2ade2ee',base_url='https://api.deepseek.com')
    r=c.chat.completions.create(model='deepseek-chat',messages=[{'role':'user','content':req.message}],temperature=0,max_tokens=1500)
    return{'text':r.choices[0].message.content}

@app.post('/api/ocr')
async def ocr(file:UploadFile=File(...),engine:str=Form('auto')):
    ext=os.path.splitext(file.filename or '.jpg')[1]
    tmp=os.path.join(tempfile.gettempdir(),f'ocr_{int(time.time())}{ext}')
    with open(tmp,'wb') as f:f.write(await file.read())
    try:
        pref=None if engine=='auto' else engine
        r=go().analyze(tmp,preferred=pref)
        os.remove(tmp)
        return r.to_dict() if hasattr(r,'to_dict') else{'text':str(r)[:3000]}
    except Exception as e:
        if os.path.exists(tmp):os.remove(tmp)
        raise HTTPException(500,str(e))

@app.post('/api/build')
def build(req:BuildReq):
    from cpt_builder import build_cpt
    r=build_cpt({'title':req.title,'columns':req.columns,'db_name':req.db_name})
    fn=None
    if isinstance(r,dict) and r.get('path'):fn=os.path.basename(r['path'])
    elif isinstance(r,str) and r.endswith('.cpt'):fn=r
    if fn:
        src=os.path.join(r'os.path.dirname(os.path.abspath(__file__))\output',fn)
        dst=os.path.join(r'/path/to/fr/reportlets',fn)
        try:shutil.copy2(src,dst)
        except:pass
        return{'success':True,'filename':fn,'msg':'deployed'}
    return{'success':True,'data':str(r)[:500]}

@app.get('/api/outputs')
def outputs():
    d=r'os.path.dirname(os.path.abspath(__file__))\output'
    fs=[]
    if os.path.isdir(d):
        for f in sorted(os.listdir(d),reverse=True):
            fp=os.path.join(d,f)
            if f.endswith(('.cpt','.json')):fs.append({'name':f,'size':os.path.getsize(fp)})
    return{'files':fs[:30]}

@app.get('/api/download/{name}')
def dl(name:str):
    for p in[r'os.path.dirname(os.path.abspath(__file__))\output',r'/path/to/fr/reportlets']:
        fp=os.path.join(p,name)
        if os.path.exists(fp):return FileResponse(fp,filename=name)
    raise HTTPException(404)

# -- WORKFLOW --
from pipeline import Pipeline;_pipes={}
@app.post('/api/workflow/start')
def ws():
    tid=uuid.uuid4().hex[:12];_pipes[tid]=Pipeline()
    return{'task_id':tid,'ok':True}

@app.post('/api/workflow/{tid}/ocr')
async def wo(tid:str,file:UploadFile=File(...)):
    p=_pipes.get(tid)
    if not p:raise HTTPException(404)
    tmp=os.path.join(tempfile.gettempdir(),f'ocr_{tid}.jpg')
    with open(tmp,'wb') as f:f.write(await file.read())
    try:r=p.step1_ocr(tmp);os.remove(tmp);return r
    except Exception as e:
        if os.path.exists(tmp):os.remove(tmp);raise HTTPException(500,str(e))

@app.post('/api/workflow/{tid}/analyze')
def wa(tid:str):return (_pipes.get(tid) or _404()).step2_analyze()
@app.post('/api/workflow/{tid}/sql')
def wq(tid:str):return (_pipes.get(tid) or _404()).step4_generate_sql()
@app.post('/api/workflow/{tid}/exec')
def we(tid:str):return (_pipes.get(tid) or _404()).step5_execute_sql()
@app.post('/api/workflow/{tid}/cpt')
def wc(tid:str):return (_pipes.get(tid) or _404()).step7_build_cpt()
@app.post('/api/workflow/{tid}/rag')
def wr(tid:str):return (_pipes.get(tid) or _404()).step6_rag_check()
@app.post('/api/workflow/{tid}/deploy')
def wd(tid:str):return (_pipes.get(tid) or _404()).step8_deploy()
@app.get('/api/workflow/{tid}/status')
def wst(tid:str):return{'task_id':tid,'ok':True}
def _404():raise HTTPException(404)

WEB=r'os.path.dirname(os.path.abspath(__file__))\web'
os.makedirs(WEB,exist_ok=True)
if os.path.isfile(os.path.join(WEB,'index.html')):
    app.mount('/',StaticFiles(directory=WEB,html=True),name='static')
