import pytest

pytestmark = pytest.mark.integration


def test_schema_and_volume_exist(sql, names):
    c, s, v = names["catalog"], names["schema"], names["volume"]
    schemata = sql(
        f"SELECT schema_name FROM `{c}`.information_schema.schemata WHERE schema_name = '{s}'"
    )
    assert [r["schema_name"] for r in schemata] == [s]

    volumes = sql(
        f"SELECT volume_name, volume_type FROM `{c}`.information_schema.volumes "
        f"WHERE volume_schema = '{s}' AND volume_name = '{v}'"
    )
    assert volumes == [{"volume_name": v, "volume_type": "MANAGED"}]
