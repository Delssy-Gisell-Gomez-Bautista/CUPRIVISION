"""Servidor local. Ejecutar desde la carpeta raíz: python local/server.py"""
import os
os.environ.setdefault('OPENCV_FFMPEG_LOGLEVEL','-8')
os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT','60')
import base64, threading, time
from pathlib import Path
from urllib.parse import urlsplit
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from engine import Engine, calibration

ROOT=Path(__file__).resolve().parents[1]
app=FastAPI(title='CUPRIVISION local',docs_url=None,redoc_url=None)
ALLOWED={'http://127.0.0.1:8765','http://localhost:8765',
         'https://cuprivision-monitor.lenintorres1105.chatgpt.site'}
# Para una instalación en otro origen, añade únicamente ese origen exacto.
extra=os.environ.get('CUPRI_ALLOWED_ORIGIN')
if extra:ALLOWED.add(extra)
app.add_middleware(CORSMiddleware,allow_origins=sorted(ALLOWED),
                   allow_methods=['GET','POST','OPTIONS'],allow_headers=['Content-Type'])

@app.middleware('http')
async def origin_guard(request:Request,call_next):
    origin=request.headers.get('origin')
    if request.url.path.startswith('/api/') and origin and origin not in ALLOWED:
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':'Origen no autorizado.'},status_code=403)
    if request.headers.get('content-length','0').isdigit() and int(request.headers.get('content-length','0'))>6_000_000:
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':'Petición demasiado grande.'},status_code=413)
    return await call_next(request)

engine=Engine()

class Analysis(BaseModel):
    image:str=Field(max_length=5_000_000)
    time:float
    config:dict
class Authorization(BaseModel):
    id:int=Field(ge=1)
    duration:float=Field(gt=0,le=3600)
    responsible:str=Field(min_length=1,max_length=100)
class CameraSource(BaseModel):
    source:str=Field(min_length=1,max_length=2048)

@app.get('/api/status')
def status():return engine.status()
@app.post('/api/load')
def load():engine.load();return engine.status()
@app.post('/api/reset')
def reset():engine.reset();return {'ok':True}
@app.post('/api/authorize')
def authorize(a:Authorization):
    try:engine.authorize(a.id,a.duration,a.responsible)
    except ValueError as e:raise HTTPException(400,str(e))
    return {'ok':True}
@app.post('/api/calibrate')
def calibrate(c:dict):
    try:return calibration(c)
    except (ValueError,KeyError,TypeError,np.linalg.LinAlgError) as e:raise HTTPException(400,str(e))
@app.post('/api/analyze')
def analyze(a:Analysis):
    try:
        import cv2
        if not a.image.startswith('data:image/jpeg;base64,'):raise ValueError('Se requiere JPEG.')
        raw=base64.b64decode(a.image.split(',',1)[1],validate=True)
        frame=cv2.imdecode(np.frombuffer(raw,dtype=np.uint8),cv2.IMREAD_COLOR)
        if frame is None or frame.shape[0]*frame.shape[1]>4_000_000:raise ValueError('Imagen no válida o demasiado grande.')
        return engine.analyze(frame,a.time,a.config)
    except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
    except ImportError:raise HTTPException(503,'Falta OpenCV. Ejecuta la instalación de dependencias.')
    except Exception:raise HTTPException(500,'Falló la inferencia. Revisa los modelos y reinicia el motor.')

class Camera:
    def __init__(self):
        self.stop=threading.Event();self.frame=None;self.timestamp=0;self.error='';self.lock=threading.Lock()
    def start(self,source):
        u=urlsplit(source)
        if u.scheme not in ('rtsp','rtsps','http','https') or not u.hostname:raise ValueError('Dirección de cámara no válida.')
        threading.Thread(target=self.run,args=(source,),daemon=True).start()
    def run(self,source):
        cap=None
        try:
            import cv2
            cap=cv2.VideoCapture(source,cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,5000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,5000])
            if not cap.isOpened():self.error='No se pudo abrir la cámara. Revisa red y credenciales.';return
            while not self.stop.is_set():
                ok,frame=cap.read()
                if not ok:self.error='Se perdió la conexión con la cámara.';break
                h,w=frame.shape[:2]
                if w>960:frame=cv2.resize(frame,(960,round(h*960/w)))
                ok,encoded=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,75])
                if ok:
                    with self.lock:self.frame=encoded.tobytes();self.timestamp=time.monotonic()
        except Exception:self.error='No se pudo leer la cámara. Verifica OpenCV y la dirección.'
        finally:
            if cap is not None:cap.release()

camera=None
@app.post('/api/camera/open')
def camera_open(s:CameraSource):
    global camera
    if camera is not None:camera.stop.set()
    c=Camera()
    try:c.start(s.source)
    except ValueError as e:raise HTTPException(400,str(e))
    camera=c;engine.reset();return {'ok':True}
@app.post('/api/camera/close')
def camera_close():
    global camera
    if camera is not None:camera.stop.set()
    camera=None;return {'ok':True}
@app.get('/api/camera/frame')
def camera_frame():
    c=camera
    if c is None:raise HTTPException(400,'No hay cámara conectada.')
    # Tiempo acotado de espera del primer fotograma.
    end=time.monotonic()+7
    while c.frame is None and not c.error and time.monotonic()<end:time.sleep(.05)
    if c.error:raise HTTPException(503,c.error)
    with c.lock:
        if c.frame is None or time.monotonic()-c.timestamp>8:raise HTTPException(503,'La cámara no entrega imágenes recientes.')
        return {'image':'data:image/jpeg;base64,'+base64.b64encode(c.frame).decode(),'time':c.timestamp}

@app.get('/downloads/CUPRIVISION.zip')
def source_download():
    import sys
    from fastapi.responses import FileResponse
    sys.path.insert(0,str(ROOT))
    from make_package import build
    path=ROOT/'dist'/'downloads'/'CUPRIVISION.zip'
    if not path.exists():path=build()
    return FileResponse(path,filename='CUPRIVISION.zip',media_type='application/zip')

app.mount('/',StaticFiles(directory=ROOT/'dist',html=True),name='ui')
if __name__=='__main__':
    import uvicorn
    print('\nCUPRIVISION: abre http://127.0.0.1:8765\n')
    uvicorn.run(app,host='127.0.0.1',port=8765,access_log=False)
