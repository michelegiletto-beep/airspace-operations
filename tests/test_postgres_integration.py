"""Real PostgreSQL checks; skip honestly when the isolated service is absent."""
import os
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import text, select, update
from airspace.storage import Store, records, organisations, now, identifier
from airspace.identity import provision

pytestmark = pytest.mark.skipif(not os.getenv("AIRSPACE_TEST_POSTGRES_URL"), reason="Isolated PostgreSQL service not configured; no PostgreSQL success is simulated")


@pytest.fixture
def pg():
    store = Store(os.environ["AIRSPACE_TEST_POSTGRES_URL"], b"isolated-postgres-software-test-key")
    store.migrate()
    yield store
    store.engine.dispose()


def test_actual_postgis_geodesic_and_vector_extensions(pg):
    with pg.engine.begin() as conn:
        privileges = conn.execute(text("SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=current_user")).one()
        assert privileges == (False, False, False), "The ordinary application role must not be a database administrator"
        distance = conn.execute(text("SELECT ST_Distance(ST_GeogFromText('POINT(0 0)'), ST_GeogFromText('POINT(1 0)'))")).scalar_one()
        assert abs(distance - 111319.49079327357) < 0.00001
        assert conn.execute(text("SELECT '[1,0,0]'::vector <=> '[1,0,0]'::vector")).scalar_one() == 0
        assert conn.execute(text("SELECT '[1,0,0]'::vector <=> '[0,1,0]'::vector")).scalar_one() == 1
        print({"postgis": conn.execute(text("SELECT PostGIS_Lib_Version()")).scalar_one(), "vector": conn.execute(text("SELECT extversion FROM pg_extension WHERE extname='vector'")).scalar_one()})


def test_actual_concurrent_audit_writes_and_tenant_predicates(pg):
    owner = provision(pg, "Isolated PG verification", identifier()+"@test.invalid", "regulatory", "isolated-postgres-password")
    other = provision(pg, "Other isolated PG verification", identifier()+"@test.invalid", "regulatory", "isolated-postgres-password")
    def append(index):
        with pg.engine.begin() as conn:
            pg.append_audit(conn, owner["organisation_id"], owner["id"], "isolated.concurrent", {"index": index})
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(append, range(12)))
    assert pg.verify_audit(owner["organisation_id"])["valid"]
    assert pg.verify_audit(owner["organisation_id"])["count"] == 13
    with pg.engine.begin() as conn:
        row = dict(id=identifier(), organisation_id=owner["organisation_id"], kind="case", title="Isolated SQL tenant predicate check", status="Draft", data={"issuer": "Not an authority instrument"}, version=1, created_by=owner["id"], created_at=now(), updated_at=now())
        conn.execute(records.insert().values(**row))
        assert conn.execute(select(records).where(records.c.id == row["id"], records.c.organisation_id == other["organisation_id"])).first() is None


def test_actual_optimistic_update_and_rollback(pg):
    owner = provision(pg, "Isolated PG rollback", identifier()+"@test.invalid", "regulatory", "isolated-postgres-password")
    row = dict(id=identifier(), organisation_id=owner["organisation_id"], kind="case", title="Isolated concurrency fixture", status="Draft", data={}, version=1, created_by=owner["id"], created_at=now(), updated_at=now())
    with pg.engine.begin() as conn:
        conn.execute(records.insert().values(**row))
    def edit(title):
        with pg.engine.begin() as conn:
            return conn.execute(update(records).where(records.c.id == row["id"], records.c.version == 1, records.c.organisation_id == owner["organisation_id"]).values(title=title, version=2)).rowcount
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(edit, ["first", "second"])) == [0, 1]
    before = pg.verify_audit(owner["organisation_id"])
    with pytest.raises(RuntimeError):
        with pg.engine.begin() as conn:
            pg.append_audit(conn, owner["organisation_id"], owner["id"], "isolated.rollback", {})
            raise RuntimeError("Deliberate isolated transaction failure")
    assert pg.verify_audit(owner["organisation_id"]) == before
