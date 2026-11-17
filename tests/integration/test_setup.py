import pytest

pytestmark = pytest.mark.integration


def test_schema_and_volume_exist(sql, names):
    c, s, v = names["catalog"], names["schema"], names["volume"]
    schemata = sql(
        f"SELECT schema_name FROM `{c}`.information_schema.schemata WHERE schema_name = :schema",
        {"schema": s},
    )
    assert [r["schema_name"] for r in schemata] == [s]

    volumes = sql(
        f"SELECT volume_name, volume_type FROM `{c}`.information_schema.volumes "
        "WHERE volume_schema = :schema AND volume_name = :volume",
        {"schema": s, "volume": v},
    )
    assert volumes == [{"volume_name": v, "volume_type": "MANAGED"}]
