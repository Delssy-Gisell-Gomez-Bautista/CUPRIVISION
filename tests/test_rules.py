import sys, copy, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'local'))
import numpy as np
from engine import Engine,calibration,project,gear_class,inside

CFG=dict(task='Prueba técnica',responsible='Test',validated=True,viewOK=False,gear=dict(casco=True,chaleco=True,ocular=True,guantes=True),confidence=.5,dwell=1.5,maxGap=5,release=2,trunk=0,arm=0,knee=0,distance=1,speed=.1,radius=1,zones={},geometryValid=True,calibration=None)
CAL=dict(points=[[0,0],[1,0],[1,1],[0,1],[.5,.5]],width=10,height=10,checkX=5,checkY=5,tolerance=.1)
def person():return dict(id=1,kp=np.zeros((17,2)),kc=np.zeros(17),box=[.2,.1,.4,.8],foot=[.3,.8],gear={})
class Rules(unittest.TestCase):
 def test_absence_is_not_non_detection(self):
  e=Engine();p=person();self.assertEqual(e.rules(p,[],CFG,1,None),{})
  p['gear']={'casco':{'absent':.9}}
  self.assertIn('D1',e.rules(p,[],CFG,1,None))
  p['gear']['casco']['present']=.92
  self.assertNotIn('D1',e.rules(p,[],CFG,1,None))
 def test_class_mapping(self):
  self.assertEqual(gear_class('NO-Safety Vest'),('chaleco','absent'))
  self.assertEqual(gear_class('no_gloves'),('guantes','absent'))
  self.assertIsNone(gear_class('Mask'))
 def test_authorization_suppresses_only_zone(self):
  e=Engine();c=copy.deepcopy(CFG);c['zones']={'restricted':[[0,0],[1,0],[1,1],[0,1]]};p=person()
  self.assertIn('D2',e.rules(p,[],c,0,None));e.auth[1]={'expires':100}
  self.assertNotIn('D2',e.rules(p,[],c,0,None))
 def test_invisible_feet_no_zone_alert(self):
  c=copy.deepcopy(CFG);c['zones']={'restricted':[[0,0],[1,0],[1,1],[0,1]]};p=person();p['foot']=None
  self.assertNotIn('D2',Engine().rules(p,[],c,0,None))
 def test_calibration_independent_check(self):
  r=calibration(CAL);np.testing.assert_allclose(project([.2,.4],r['H']),[2,4],atol=1e-8)
  bad=copy.deepcopy(CAL);bad['checkX']=8
  with self.assertRaises(ValueError):calibration(bad)
  bad=copy.deepcopy(CAL);bad['points'][4]=[0,0]
  with self.assertRaises(ValueError):calibration(bad)
 def test_static_equipment_does_not_alert(self):
  c=copy.deepcopy(CFG);c['calibration']=CAL;H=calibration(CAL)['H'];p=person();e=Engine()
  equipment=[{'id':2,'world':np.array([3,8]),'velocity':np.array([0,0])}]
  self.assertNotIn('D4',e.rules(p,equipment,c,1,H))
  equipment[0]['velocity']=np.array([.3,0]);self.assertIn('D4',e.rules(p,equipment,c,2,H))
 def test_no_extrapolation_outside_calibrated_plane(self):
  c=copy.deepcopy(CFG);c['calibration']=CAL;p=person();p['foot']=[1.2,.8]
  self.assertNotIn('D4',Engine().rules(p,[{'id':2,'world':np.array([12,8]),'velocity':np.array([1,0])}],c,1,calibration(CAL)['H']))
 def test_unreviewed_profile_no_alert(self):
  c=copy.deepcopy(CFG);c['validated']=False;p=person();p['gear']={'casco':{'absent':.99}}
  self.assertEqual(Engine().rules(p,[],c,0,None),{})
 def test_missing_keypoints_no_posture_alert(self):
  c=copy.deepcopy(CFG);c.update(viewOK=True,trunk=10,arm=10,knee=150)
  self.assertNotIn('D3',Engine().rules(person(),[],c,0,None))
 def test_velocity_requires_several_observations(self):
  e=Engine();self.assertIsNone(e.velocity('x',[0,0],0,5));self.assertIsNone(e.velocity('x',[1,0],1,5))
  np.testing.assert_allclose(e.velocity('x',[2,0],2,5),[1,0])
  self.assertIsNone(e.velocity('x',[100,0],20,5))
if __name__=='__main__':unittest.main()
