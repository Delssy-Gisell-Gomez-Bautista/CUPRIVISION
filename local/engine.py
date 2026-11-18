"""CUPRIVISION: inferencia local y reglas observacionales, sin confirmar eventos."""
from __future__ import annotations
import math, time, threading, urllib.request, hashlib, json
from collections import deque
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
MODELS = ROOT / 'models'
MODELS.mkdir(exist_ok=True)
PPE_REPO = 'Hexmon/vyra-yolo-ppe-detection'
MACHINE_URL = ('https://raw.githubusercontent.com/snehilsanyal/'
               'Construction-Site-Safety-PPE-Detection/main/models/best.pt')


def norm(s):
    return ''.join(c for c in s.lower() if c.isalnum())


def gear_class(label):
    s, state = norm(label), 'present'
    for prefix, value in [('incorrect','incorrect'),('improper','incorrect'),
                          ('without','absent'),('missing','absent'),('no','absent')]:
        if s.startswith(prefix):
            s, state = s[len(prefix):], value
            break
    names = {'helmet':'casco','hardhat':'casco','safetyhelmet':'casco',
             'vest':'chaleco','safetyvest':'chaleco','reflectivevest':'chaleco',
             'glasses':'ocular','glass':'ocular','safetyglasses':'ocular',
             'goggles':'ocular','safetygoggles':'ocular','eyeprotection':'ocular',
             'glove':'guantes','gloves':'guantes','safetygloves':'guantes'}
    return (names[s],state) if s in names else None


def inside(point, poly):
    if point is None or poly is None or len(poly)<3:
        return False
    x,y=point; hit=False
    for i,a in enumerate(poly):
        b=poly[(i+1)%len(poly)]
        cross=(x-a[0])*(b[1]-a[1])-(y-a[1])*(b[0]-a[0])
        if abs(cross)<1e-9 and min(a[0],b[0])-1e-9<=x<=max(a[0],b[0])+1e-9 and min(a[1],b[1])-1e-9<=y<=max(a[1],b[1])+1e-9:
            return True
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            hit=not hit
    return hit


def angle(a,b):
    a,b=np.asarray(a),np.asarray(b)
    n=np.linalg.norm(a)*np.linalg.norm(b)
    return None if n<1e-8 else float(np.degrees(np.arccos(np.clip(np.dot(a,b)/n,-1,1))))


def project(p,H):
    if p is None:return None
    r=np.asarray(H)@np.array([p[0],p[1],1.])
    if not np.all(np.isfinite(r)) or abs(r[2])<1e-8:return None
    return r[:2]/r[2]


def calibration(c):
    pts=np.asarray(c['points'],dtype=float)
    w,h,x,y,tol=[float(c[k]) for k in ('width','height','checkX','checkY','tolerance')]
    if pts.shape!=(5,2) or not np.all(np.isfinite(pts)) or np.any(pts<0) or np.any(pts>1):
        raise ValueError('Se requieren cinco puntos normalizados válidos.')
    if not all(math.isfinite(v) for v in (w,h,x,y,tol)) or min(w,h,tol)<=0 or not(0<=x<=w and 0<=y<=h):
        raise ValueError('Medidas reales inválidas.')
    corners=pts[:4]
    crosses=[]
    for i in range(4):
        a,b,d=corners[i],corners[(i+1)%4],corners[(i+2)%4]
        v,u=b-a,d-b;crosses.append(v[0]*u[1]-v[1]*u[0])
    if not(all(z>1e-7 for z in crosses) or all(z< -1e-7 for z in crosses)):
        raise ValueError('Las esquinas deben formar un cuadrilátero convexo ordenado.')
    if not inside(pts[4],corners):raise ValueError('El quinto punto debe estar dentro del área.')
    if min(np.linalg.norm(pts[4]-p) for p in corners)<.01:
        raise ValueError('El quinto punto debe ser independiente de las esquinas.')
    A=[];B=[]
    for (a,b),(X,Y) in zip(corners,[(0,0),(w,0),(w,h),(0,h)]):
        A.extend([[a,b,1,0,0,0,-X*a,-X*b],[0,0,0,a,b,1,-Y*a,-Y*b]])
        B.extend([X,Y])
    if np.linalg.cond(A)>1e10:raise ValueError('Geometría de calibración inestable.')
    H=np.append(np.linalg.solve(A,B),1).reshape(3,3)
    q=project(pts[4],H)
    if q is None:raise ValueError('No se puede proyectar el punto de control.')
    error=float(np.linalg.norm(q-[x,y]))
    if error>tol:raise ValueError(f'Comprobación rechazada: error {error:.3f} m > {tol:.3f} m.')
    return {'H':H.tolist(),'error':error,'checked':True}


def validate_config(c):
    numeric=['confidence','dwell','maxGap','release','trunk','arm','knee','distance','speed','radius']
    for k in numeric:
        v=c.get(k)
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:
            raise ValueError(f'Valor inválido: {k}')
    if not 0<c['confidence']<1 or min(c['dwell'],c['maxGap'],c['release'])<=0:
        raise ValueError('Confianza o intervalos inválidos.')
    if any(c[k]>180 for k in ['trunk','arm','knee']):raise ValueError('Ángulos fuera de rango.')
    if not isinstance(c.get('gear'),dict) or not isinstance(c.get('zones'),dict):raise ValueError('Perfil incompleto.')
    for name,p in c['zones'].items():
        a=np.asarray(p,dtype=float)
        if name not in ['restricted','approach','position'] or a.ndim!=2 or a.shape[1]!=2 or not 3<=len(a)<=30 or not np.all(np.isfinite(a)) or np.any(a<0) or np.any(a>1):
            raise ValueError('Zona inválida.')
    if c.get('validated') and (not c.get('task') or not c.get('responsible')):raise ValueError('Falta tarea o responsable.')
    return c


class Engine:
    def __init__(self):
        self.pose=self.ppe=self.machines=None
        self.loading=False;self.errors=[];self.map={};self.machine_ids=[];self.fingerprints={}
        self.lock=threading.RLock();self.history={};self.last_seen={};self.auth={};self.last_time=None

    def status(self):
        return {'pose':self.pose is not None,'ppe':self.ppe is not None,
                'machines':self.machines is not None and bool(self.machine_ids),
                'loading':self.loading,'errors':self.errors[:],
                'classes':list(self.map),'models':self.fingerprints.copy(),
                'absence':{g:any(v==(g,'absent') for v in self.map.values()) for g in ['casco','chaleco','ocular','guantes']}}

    def load(self):
        if self.loading:return
        self.loading=True
        threading.Thread(target=self._load,daemon=True).start()

    def _load(self):
        self.errors=[]
        try:
            from ultralytics import YOLO
            jobs=['pose','ppe','machines']
            for name in jobs:
                if getattr(self,name) is not None:continue
                try:
                    if name=='pose':path=MODELS/'yolo11n-pose.pt'
                    elif name=='ppe':
                        path=MODELS/'ppe.pt'
                        if not path.exists():
                            from huggingface_hub import hf_hub_download
                            path=Path(hf_hub_download(PPE_REPO,'best.pt',local_dir=MODELS/'ppe-cache'))
                    else:
                        path=MODELS/'maquinaria.pt'
                        if not path.exists():
                            temp=path.with_suffix('.partial')
                            try:
                                with urllib.request.urlopen(MACHINE_URL,timeout=60) as response,temp.open('wb') as out:
                                    total=0
                                    while chunk:=response.read(1024*1024):
                                        total+=len(chunk)
                                        if total>512*1024*1024:raise ValueError('Modelo demasiado grande.')
                                        out.write(chunk)
                                if total<100_000:raise ValueError('Descarga incompleta.')
                                temp.replace(path)
                            finally:
                                if temp.exists():temp.unlink()
                    model=YOLO(str(path))
                    digest=hashlib.sha256()
                    with path.open('rb') as source:
                        for block in iter(lambda:source.read(1024*1024),b''):digest.update(block)
                    with self.lock:
                        self.fingerprints[name]={'file':path.name,'sha256':digest.hexdigest()}
                        setattr(self,name,model)
                        if name=='ppe':self.map={v:gear_class(v) for v in model.names.values() if gear_class(v)}
                        if name=='machines':
                            accepted={'machinery','vehicle','forklift','truck','bus','car','excavator','loader','tractor'}
                            self.machine_ids=[int(k) for k,v in model.names.items() if norm(v) in accepted]
                    if name=='ppe' and not self.map:self.errors.append('EPP: las clases no corresponden al mapa de equipos.')
                    if name=='machines' and not self.machine_ids:self.errors.append('No hay clases de maquinaria reconocidas.')
                except Exception as exc:
                    self.errors.append(f'{name}: no se pudo cargar ({type(exc).__name__}). Revisa instalación o añade el modelo local.')
        except ImportError:
            self.errors.append('Instala las dependencias de requirements.txt para cargar los modelos.')
        finally:self.loading=False

    def reset(self):
        with self.lock:
            self.history.clear();self.last_seen.clear();self.auth.clear();self.last_time=None
            for model in (self.pose,self.machines):
                predictor=getattr(model,'predictor',None)
                for tracker in getattr(predictor,'trackers',[]):tracker.reset()

    def authorize(self,id,duration,responsible):
        with self.lock:
            if self.last_time is None or id not in self.last_seen:raise ValueError('El ID no está visible en el análisis actual.')
            if not math.isfinite(duration) or not 0<duration<=3600 or not responsible.strip():raise ValueError('Autorización inválida.')
            self.auth[id]={'expires':self.last_time+duration,'responsible':responsible.strip()}

    def velocity(self,key,p,t,gap):
        if p is None:self.history.pop(key,None);return None
        history=self.history.setdefault(key,deque())
        if history and t-history[-1][0]>gap:history.clear()
        history.append((t,np.asarray(p)))
        while len(history)>2 and t-history[0][0]>2:history.popleft()
        if len(history)<3 or history[-1][0]-history[0][0]<.5:return None
        ts=np.array([x[0] for x in history],dtype=float);ts-=ts.mean()
        denom=float(ts@ts)
        return None if denom<1e-8 else (ts[:,None]*np.array([x[1] for x in history])).sum(0)/denom

    def rules(self,p,equipment,c,t,H):
        alerts={};kp=np.asarray(p['kp']);kc=np.asarray(p['kc'])
        def add(d,s):alerts.setdefault(d,[]).append(s)
        for gear,required in c['gear'].items():
            if not required:continue
            evidence=p.get('gear',{}).get(gear,{})
            neg=max(evidence.get('absent',0),evidence.get('incorrect',0));pos=evidence.get('present',0)
            if neg>=c['confidence'] and neg>pos+.05:
                kind='uso incorrecto' if evidence.get('incorrect',0)>=evidence.get('absent',0) else 'ausencia'
                add('D1',f'{gear}: evidencia explícita de {kind}')
        foot=p.get('foot');world=None
        if c.get('geometryValid') and foot is not None:
            restricted=inside(foot,c['zones'].get('restricted'));approach=inside(foot,c['zones'].get('approach'))
            if (restricted or approach) and p['id'] not in self.auth:
                add('D2',('Zona restringida' if restricted else 'Zona de aproximación')+': autorización no acreditada')
            if inside(foot,c['zones'].get('position')):add('D3','Posición dentro de zona definida para la tarea')
            if H is not None and inside(foot,c['calibration']['points'][:4]):world=project(foot,H)
        if c.get('viewOK'):
            if all(kc[i]>=.5 for i in [5,6,11,12]):
                a=angle((kp[5]+kp[6]-kp[11]-kp[12])/2,[0,-1])
                if c['trunk']>0 and a is not None and a>c['trunk']:add('D3','Inclinación 2D del tronco supera el criterio')
            for shoulder,elbow,hip in [(5,7,11),(6,8,12)]:
                if all(kc[i]>=.5 for i in [shoulder,elbow,hip]):
                    a=angle(kp[elbow]-kp[shoulder],kp[hip]-kp[shoulder])
                    if c['arm']>0 and a is not None and a>c['arm']:add('D3','Elevación 2D del brazo supera el criterio')
            for hip,knee,ankle in [(11,13,15),(12,14,16)]:
                if all(kc[i]>=.5 for i in [hip,knee,ankle]):
                    a=angle(kp[hip]-kp[knee],kp[ankle]-kp[knee])
                    if c['knee']>0 and a is not None and a<c['knee']:add('D3','Ángulo 2D de rodilla inferior al criterio')
        vp=self.velocity(('person',p['id']),world,t,c['maxGap'])
        if world is not None and min(c['distance'],c['speed'],c['radius'])>0:
            for e in equipment:
                q,v=e['world'],e['velocity']
                if q is None or v is None or np.linalg.norm(v)<c['speed']:continue
                delta=world-q;margin=float(np.linalg.norm(delta))-c['radius']
                if margin<c['distance']:
                    approach='trayectoria relativa no disponible' if vp is None else ('acercamiento relativo' if np.dot(delta,vp-v)<0 else 'sin acercamiento relativo')
                    add('D4',f'Equipo {e["id"]}: margen estimado {margin:.2f} m; {approach}')
        return alerts if c.get('validated') and p['id']>=0 else {}

    def analyze(self,image,t,c):
        with self.lock:
            if self.pose is None:raise ValueError('Carga el modelo de pose antes de analizar.')
            validate_config(c)
            if not math.isfinite(t) or t<0:raise ValueError('Tiempo inválido.')
            start=time.perf_counter()
            if self.last_time is not None and (t<self.last_time or t-self.last_time>c['maxGap']):self.reset()
            self.last_time=t;h,w=image.shape[:2]
            opts=dict(conf=c['confidence'],verbose=False,imgsz=640,device='cpu')
            r=self.pose.track(image,persist=True,tracker='bytetrack.yaml',**opts)[0]
            persons=[]
            if r.boxes is not None:
                boxes=r.boxes.xyxy.cpu().numpy();ids=r.boxes.id.cpu().numpy().astype(int) if r.boxes.id is not None else [-1]*len(boxes)
                for i,b in enumerate(boxes):
                    kp=r.keypoints.xy[i].cpu().numpy() if r.keypoints is not None else np.zeros((17,2))
                    kc=r.keypoints.conf[i].cpu().numpy() if r.keypoints is not None and r.keypoints.conf is not None else np.zeros(17)
                    box=(b/np.array([w,h,w,h])).tolist();pid=int(ids[i])
                    foot=[(box[0]+box[2])/2,box[3]] if kc[15]>=.5 and kc[16]>=.5 and box[3]<.995 else None
                    persons.append(dict(id=pid,box=box,kp=kp,kc=kc,foot=foot,gear={}))
                    if pid>=0:self.last_seen[pid]=t
            self.last_seen={pid:v for pid,v in self.last_seen.items() if t-v<=c['maxGap']}
            self.auth={pid:v for pid,v in self.auth.items() if v['expires']>=t and pid in self.last_seen}
            if self.ppe is not None:
                r=self.ppe.predict(image,**opts)[0]
                if r.boxes is not None:
                    for b,cls,conf in zip(r.boxes.xyxy.cpu().numpy(),r.boxes.cls.cpu().numpy().astype(int),r.boxes.conf.cpu().numpy()):
                        mapping=self.map.get(r.names[int(cls)])
                        if mapping is None:continue
                        gear,state=mapping;center=(b[:2]+b[2:])/2;candidates=[]
                        for p in persons:
                            if p['id']<0:continue
                            kp,kc=p['kp'],p['kc'];height=max((p['box'][3]-p['box'][1])*h,1)
                            if gear=='casco':
                                visible=[i for i in range(5) if kc[i]>=.5]
                                targets=[kp[visible].mean(0)-[0,.06*height]] if len(visible)>=2 and p['box'][1]>.005 else []
                                limit=.25
                            elif gear=='ocular':targets=[(kp[1]+kp[2])/2] if kc[1]>=.5 and kc[2]>=.5 else [];limit=.15
                            elif gear=='chaleco':targets=[kp[[5,6,11,12]].mean(0)] if all(kc[i]>=.5 for i in [5,6,11,12]) else [];limit=.28
                            else:targets=[kp[i] for i in [9,10] if kc[i]>=.5];limit=.18
                            if targets:
                                distance=min(np.linalg.norm(center-q)/height for q in targets)
                                if distance<=limit:candidates.append((float(distance),p))
                        candidates.sort(key=lambda a:a[0])
                        if candidates and (len(candidates)==1 or candidates[1][0]-candidates[0][0]>=.04):
                            states=candidates[0][1]['gear'].setdefault(gear,{})
                            states[state]=max(states.get(state,0),float(conf))
            H=None;warnings=[]
            if c.get('geometryValid') and c.get('calibration'):
                checked=calibration(c['calibration']);H=checked['H']
            if not self.ppe:warnings.append('D1 sin modelo EPP')
            elif any(c['gear'].get(g) and not any(v==(g,'absent') for v in self.map.values()) for g in c['gear']):warnings.append('D1: clases de ausencia incompletas')
            if not c.get('geometryValid'):warnings.append('D2 sin geometría confirmada')
            if not c.get('viewOK') and not c['zones'].get('position'):warnings.append('D3 sin criterio activo')
            equipment=[]
            enabled=H is not None and min(c['distance'],c['speed'],c['radius'])>0 and self.machines is not None and self.machine_ids
            if enabled:
                r=self.machines.track(image,persist=True,tracker='bytetrack.yaml',classes=self.machine_ids,**opts)[0]
                if r.boxes is not None and r.boxes.id is not None:
                    for b,pid in zip(r.boxes.xyxy.cpu().numpy(),r.boxes.id.cpu().numpy().astype(int)):
                        foot=[(b[0]+b[2])/2/w,b[3]/h]
                        q=project(foot,H) if foot[1]<.995 and inside(foot,c['calibration']['points'][:4]) else None
                        velocity=self.velocity(('machine',int(pid)),q,t,c['maxGap'])
                        equipment.append({'id':int(pid),'world':q,'velocity':velocity})
            else:warnings.append('D4 no evaluable')
            output=[]
            for p in persons:
                alerts=self.rules(p,equipment,c,t,H)
                output.append({'id':p['id'],'box':p['box'],'alerts':alerts,'gear':p['gear']})
            for key in list(self.history):
                if t-self.history[key][-1][0]>c['maxGap']:del self.history[key]
            return {'people':output,'ms':round((time.perf_counter()-start)*1000),'warnings':warnings}
