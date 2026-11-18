/* Lógica temporal independiente de la interfaz. */
(function(root){
  class Episodes{
    constructor(){this.pending=new Map();this.active=new Map();this.previous=null;}
    close(reason='Fin de observación'){
      const closed=[...this.active.values()].map(e=>({...e,closed:true,closeReason:reason}));
      this.pending.clear();this.active.clear();this.previous=null;return closed;
    }
    update(observations,t,cfg,makeId){
      let changed=[];
      if(this.previous!==null&&(t<this.previous||t-this.previous>cfg.maxGap))changed.push(...this.close('Discontinuidad'));
      this.previous=t;
      const keys=new Set();
      for(const o of observations){
        if(!Number.isInteger(o.id)||o.id<0)continue;
        for(const [dim,reasons] of Object.entries(o.alerts||{})){
          if(!['D1','D2','D3','D4'].includes(dim))continue;
          const key=o.id+':'+dim;keys.add(key);
          let p=this.pending.get(key);
          if(!p||t-p.last>cfg.maxGap)p={start:t,last:t,hits:0};
          p.last=t;p.hits++;this.pending.set(key,p);
          if(p.hits<3||t-p.start<cfg.dwell)continue;
          let e=this.active.get(o.id);
          if(!e){e={id:makeId(),track:o.id,start:p.start,end:t,dimensions:{},status:'pending',principal:'',closed:false,origin:'automatic',created:new Date().toISOString(),notes:'',reviewer:'',audit:[]};this.active.set(o.id,e);}
          e.dimensions[dim]=[...new Set([...(e.dimensions[dim]||[]),...reasons])].slice(0,30);
        }
      }
      for(const key of this.pending.keys())if(!keys.has(key))this.pending.delete(key);
      for(const [id,e] of this.active){
        const o=observations.find(x=>x.id===id);
        if(o&&Object.keys(e.dimensions).some(d=>o.alerts?.[d]))e.end=t;
        if(t-e.end>cfg.release){e.closed=true;e.closeReason='Sin evidencia reciente';this.active.delete(id);}
        changed.push(JSON.parse(JSON.stringify(e)));
      }
      return changed;
    }
  }
  const csvCell=v=>{let s=String(v??'');if(/^[\s]*[=+\-@]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};
  const count=events=>Object.fromEntries(['D1','D2','D3','D4'].map(d=>[d,events.filter(e=>e.status==='confirmed'&&e.principal===d).length]));
  const api={Episodes,csvCell,count};if(typeof module!=='undefined')module.exports=api;else root.CupriRules=api;
})(typeof window!=='undefined'?window:globalThis);
