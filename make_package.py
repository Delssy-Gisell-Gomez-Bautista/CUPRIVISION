from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

def build():
    root=Path(__file__).resolve().parent
    target=root/'dist'/'downloads'/'CUPRIVISION.zip'
    target.parent.mkdir(exist_ok=True)
    names=['README.md','VALIDACION.md','requirements.txt','INICIAR_WINDOWS.bat','make_package.py',
           'dist/index.html','dist/style.css','dist/app.js','dist/rules.js',
           'local/server.py','local/engine.py','tests/test_rules.py','tests/test_api.py','tests/test_episodes.cjs']
    temp=target.with_suffix('.tmp')
    with ZipFile(temp,'w',ZIP_DEFLATED) as z:
        for name in names:z.write(root/name,'CUPRIVISION/'+name)
    temp.replace(target)
    return target
if __name__=='__main__':print(build())
