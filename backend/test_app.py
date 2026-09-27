import os
os.environ['AUTH_SECRET'] = 'test-only-secret'
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from fastapi.testclient import TestClient
from pydantic import ValidationError
import main

class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.medicine = dict(name="O'Brien <test>", dosage='1 tablet', frequency='Once daily', reminder_time='08:00', start_date='2026-09-01', end_date='2026-10-01')

    def test_frontend_served_without_database_credentials(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertIn('Shared transport', self.client.get('/script.js').text)

    def test_passwords_salted_and_verifiable(self):
        first = main.hash_password('secret123')
        self.assertNotEqual(first, main.hash_password('secret123'))
        self.assertTrue(main.verify_password('secret123', first))
        self.assertFalse(main.verify_password('wrong', first))

    def test_user_id_is_not_an_auth_token(self):
        self.assertIsNone(main.get_user_from_token('1'))
        token = main.issue_token(1)
        self.assertIsNone(main.get_user_from_token(token.replace('1.', '2.', 1)))
        with patch.object(main, 'db') as db:
            db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{'id': 1}]
            self.assertEqual(main.get_user_from_token(token)['id'], 1)

    def test_expired_token(self):
        with patch.object(main.time, 'time', return_value=0):
            token = main.issue_token(1)
        self.assertIsNone(main.get_user_from_token(token))

    def test_invalid_dates_and_frequency(self):
        for changes in [{'end_date':'2026-08-01'}, {'reminder_time':'29:00'}, {'frequency':'Twice daily'}, {'name':'   '}]:
            with self.assertRaises(ValidationError):
                main.MedicineCreate(**{**self.medicine, **changes})
        m = main.MedicineCreate(**{**self.medicine, 'frequency':'Twice daily', 'reminder_times':['20:00','08:00']})
        self.assertEqual(m.reminder_times, ['08:00','20:00'])

    def test_foreign_reminder_cannot_be_modified(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
        with patch.object(main, 'get_user_from_token', return_value={'id':1}), patch.object(main,'db',db):
            res = self.client.put('/reminders/99/status', headers={'Authorization':'test'}, json={'status':'taken'})
        self.assertEqual(res.status_code,404)
        db.table.return_value.update.assert_not_called()

    def test_foreign_medicine_cannot_get_reminder(self):
        with patch.object(main,'get_user_from_token',return_value={'id':1}), patch.object(main,'owned_medicine',side_effect=main.HTTPException(404,'Medicine not found')):
            res=self.client.post('/reminders',headers={'Authorization':'test'},json={'medicine_id':2,'scheduled_time':'08:00','scheduled_date':'2026-09-26'})
        self.assertEqual(res.status_code,404)

    def test_schedule_recurrence_and_multiple_times(self):
        medicines = [dict(self.medicine, id=1, reminder_times=['08:00']),
          dict(self.medicine,id=2,frequency='Weekly'),
          dict(self.medicine,id=3,frequency='Every alternate day'),
          dict(self.medicine,id=4,frequency='As needed'),
          dict(self.medicine,id=5,frequency='Twice daily',reminder_times=['08:00','20:00'])]
        db=MagicMock()
        db.table.return_value.select.return_value.eq.return_value.execute.return_value.data=medicines
        with patch.object(main,'db',db): main.ensure_today(1,'2026-09-26')
        args=db.table.return_value.upsert.call_args
        self.assertEqual([(r['medicine_id'],r['scheduled_time']) for r in args.args[0]],[(1,'08:00'),(5,'08:00'),(5,'20:00')])
        self.assertTrue(args.kwargs['ignore_duplicates'])

    def test_status_uses_atomic_database_function(self):
        db=MagicMock()
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data=[{'status':'pending'}]
        connection=MagicMock()
        with patch.object(main,'get_user_from_token',return_value={'id':1}), patch.object(main,'db',db), patch.object(main,'get_supabase',return_value=connection):
            res=self.client.put('/reminders/5/status',headers={'Authorization':'test'},json={'status':'taken','medicine_name':'Forged'})
        self.assertEqual(res.status_code,200)
        connection.rpc.assert_called_once_with('record_dose',{'p_reminder_id':5,'p_user_id':1,'p_status':'taken','p_timezone':main.APP_TIMEZONE})

if __name__ == '__main__': unittest.main()
