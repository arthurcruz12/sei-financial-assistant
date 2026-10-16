import unittest
from fastapi.testclient import TestClient
from backend.main import app

class APIContract(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
    def test_health(self):
        self.assertEqual(self.client.get('/health').status_code, 200)
    def test_allocation_and_validation(self):
        r = self.client.post('/portfolio', json={'budget':999.99,'risk':'Moderado','horizon':5})
        self.assertEqual(r.status_code, 200)
        rows = r.json()['allocation']
        self.assertEqual(sum(x['weight'] for x in rows), 100)
        self.assertEqual(round(sum(x['amount'] for x in rows)*100),99999)
        self.assertEqual(self.client.post('/portfolio',json={'budget':-1}).status_code,422)
    def test_forecast(self):
        r=self.client.post('/forecast',json={'values':[1,2,1,3,2]*6,'steps':12})
        self.assertEqual(r.status_code,200)
        steps=r.json()['steps']
        self.assertEqual(len(steps),13)
        self.assertGreater(steps[-1]['high']-steps[-1]['low'],steps[1]['high']-steps[1]['low'])
        self.assertEqual(self.client.post('/forecast',json={'values':[1,2],'steps':12}).status_code,422)
if __name__=='__main__': unittest.main()
