"""Auditable state-machine lead workflow: research -> qualify -> draft -> approval -> CRM."""
import json, os, sqlite3, uuid
from datetime import datetime,timezone
from pathlib import Path
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,EmailStr,Field
DB=Path(os.getenv('DB_PATH',str(Path(__file__).parent/'leads.db')))
app=FastAPI(title='Agentic Lead Operations')
def connect():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE IF NOT EXISTS workflows (id TEXT PRIMARY KEY, stage TEXT, data TEXT, errors TEXT)')
 c.execute('CREATE TABLE IF NOT EXISTS crm (id TEXT PRIMARY KEY, workflow_id TEXT UNIQUE, company TEXT, contact TEXT, outreach TEXT, created_at TEXT)')
 c.commit();return c
class Lead(BaseModel):
 company:str=Field(min_length=2)
 contact:str=Field(min_length=2)
 email:str=Field(min_length=5)
 industry:str='unknown'
 website:str=''
class Decision(BaseModel):
 approve:bool
 notes:str=''

# The tool registry is explicit: tools cannot send outreach autonomously.
def research_tool(lead:dict):
 knowledge={'Acme Energy':'Energy procurement teams often seek document automation.','Cedar Realty':'Real estate firms process lease and vendor documents.'}
 return {'research_summary':knowledge.get(lead['company'],'No verified background found; requires manual research.'),'source':'local demo research catalog','verified':lead['company'] in knowledge}
def qualify_tool(state):
 return {'qualified':state['lead']['industry'].lower() in {'energy','real estate','finance','healthcare'},'reason':'Demo target-industry rubric; not a purchasing-intent prediction'}
def draft_tool(state):
 lead=state['lead'];research=state['research']
 fallback=f"Hello {lead['contact']}, I work on AI workflow automation. Would a short discussion about your {lead['industry']} operations be useful?"
 if not os.getenv('OPENAI_API_KEY'):return {'subject':'Workflow automation conversation','body':fallback,'mode':'template'}
 try:
  res=__import__('openai').OpenAI().chat.completions.create(model=os.getenv('OPENAI_MODEL','gpt-4o-mini'),temperature=0.2,messages=[{'role':'system','content':'Draft a brief B2B outreach note. Use only provided facts; do not invent achievements, contacts, or personalization.'},{'role':'user','content':json.dumps({'lead':lead,'research':research})}])
  return {'subject':'Potential workflow automation','body':res.choices[0].message.content or fallback,'mode':'llm'}
 except Exception as e: return {'subject':'Workflow automation conversation','body':fallback,'mode':'template_fallback','error_type':type(e).__name__}

def get_row(id):
 c=connect();row=c.execute('SELECT * FROM workflows WHERE id=?',(id,)).fetchone();c.close()
 if not row:raise HTTPException(404,'Workflow not found')
 return {'id':row['id'],'stage':row['stage'],'data':json.loads(row['data']),'errors':json.loads(row['errors'])}
def save(id,stage,data,errors):
 c=connect();c.execute('UPDATE workflows SET stage=?,data=?,errors=? WHERE id=?',(stage,json.dumps(data),json.dumps(errors),id));c.commit();c.close()
@app.post('/workflows')
def start(lead:Lead):
 id=str(uuid.uuid4());state={'lead':lead.model_dump(),'timeline':[]}
 c=connect();c.execute('INSERT INTO workflows VALUES (?,?,?,?)',(id,'created',json.dumps(state),'[]'));c.commit();c.close()
 return run(id)
@app.post('/workflows/{id}/run')
def run(id:str):
 w=get_row(id);s=w['data'];stage=w['stage'];errors=w['errors']
 if stage not in {'created','research_failed'}:return w
 try:
  s['research']=research_tool(s['lead']);s['timeline'].append('research_complete')
  s['qualification']=qualify_tool(s);s['timeline'].append('qualification_complete')
  s['draft']=draft_tool(s);s['timeline'].append('draft_complete')
  stage='awaiting_approval'
 except Exception as exc:
  errors.append({'type':type(exc).__name__,'detail':str(exc)});stage='research_failed'
 save(id,stage,s,errors);return get_row(id)
@app.post('/workflows/{id}/approval')
def approval(id:str,decision:Decision):
 w=get_row(id)
 if w['stage']!='awaiting_approval':raise HTTPException(409,'Workflow is not pending approval')
 s=w['data'];s['approval']={'approved':decision.approve,'notes':decision.notes}
 if not decision.approve:
  save(id,'rejected',s,w['errors']);return get_row(id)
 # Idempotent local CRM write: the only side effect, after explicit approval.
 c=connect()
 with c:
  c.execute('INSERT OR IGNORE INTO crm VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),id,s['lead']['company'],s['lead']['contact'],s['draft']['body'],datetime.now(timezone.utc).isoformat()))
 c.close();save(id,'logged_to_crm',s,w['errors']);return get_row(id)
@app.get('/workflows/{id}')
def status(id:str):return get_row(id)
@app.get('/crm')
def crm():
 c=connect();rows=[dict(row) for row in c.execute('SELECT * FROM crm')];c.close();return rows
@app.get('/health')
def health():return {'status':'ok','external_sends_enabled':False}
