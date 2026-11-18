import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'local'))
from fastapi.testclient import TestClient
from server import app
class API(unittest.TestCase):
 def setUp(self):self.client=TestClient(app)
 def test_starts_without_models(self):
  r=self.client.get('/api/status');self.assertEqual(r.status_code,200);self.assertIn('pose',r.json())
 def test_ui_is_served(self):
  r=self.client.get('/');self.assertEqual(r.status_code,200);self.assertIn('CUPRIVISION',r.text)
 def test_untrusted_origin_rejected(self):
  r=self.client.post('/api/load',headers={'Origin':'https://example.com'});self.assertEqual(r.status_code,403)
 def test_authorization_unknown_id(self):
  r=self.client.post('/api/authorize',json={'id':999,'duration':60,'responsible':'Test'});self.assertEqual(r.status_code,400)
 def test_camera_not_connected(self):self.assertEqual(self.client.get('/api/camera/frame').status_code,400)
 def test_bad_calibration(self):self.assertEqual(self.client.post('/api/calibrate',json={}).status_code,400)
if __name__=='__main__':unittest.main()
