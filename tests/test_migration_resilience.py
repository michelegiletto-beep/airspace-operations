"""Fault-injection and migration checks use isolated local databases only."""
import sqlite3
from pathlib import Path
import pytest
from sqlalchemy import select
from airspace.storage import Store, records
from airspace.identity import provision


def test_initial_sql_migration_and_repeated_application(tmp_path):
    path=tmp_path/'migration.db'
    sql=(Path(__file__).resolve().parents[1]/'migrations/001_schema.sqlite.sql').read_text()
    with sqlite3.connect(path) as conn: conn.executescript(sql)
    store=Store('sqlite:///'+str(path),b'isolated-migration-key-long-enough-32')
    store.migrate();store.migrate()
    user=provision(store,'Isolated migration test','migration@test.invalid','viewer','isolated-migration-passphrase')
    assert store.verify_audit(user['organisation_id'])['valid']
    store.engine.dispose()


def test_audit_failure_rolls_back_record_and_outbox(environment,monkeypatch):
    store,client,author,_,_,headers=environment
    h=headers(author['email'])
    def interrupted(*args,**kwargs): raise RuntimeError('Isolated database interruption fault injection')
    monkeypatch.setattr(store,'append_audit',interrupted)
    with pytest.raises(RuntimeError,match='fault injection'):
        client.post('/api/v1/records/case',headers=h,json={'title':'Isolated rollback test'})
    with store.engine.connect() as conn:
        assert conn.execute(select(records).where(records.c.organisation_id==author['organisation_id'])).first() is None
