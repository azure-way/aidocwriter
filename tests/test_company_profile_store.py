from __future__ import annotations

from azure.core.exceptions import ResourceNotFoundError

from docwriter.company_profile_store import CompanyProfileStore


class FakeTable:
    def __init__(self):
        self.rows = {}

    def create_table(self):
        return None

    def get_entity(self, partition_key, row_key):
        key = (partition_key, row_key)
        if key not in self.rows:
            raise ResourceNotFoundError("not found")
        return self.rows[key]

    def upsert_entity(self, entity, mode="replace"):
        key = (entity["PartitionKey"], entity["RowKey"])
        self.rows[key] = entity


class FakeTableServiceClient:
    def __init__(self, connection_string):
        self.connection_string = connection_string
        self.table = FakeTable()

    @staticmethod
    def from_connection_string(connection_string):
        return FakeTableServiceClient(connection_string)

    def get_table_client(self, table_name):
        return self.table


def test_company_profile_store_round_trip(monkeypatch):
    monkeypatch.setattr("docwriter.company_profile_store.TableServiceClient", FakeTableServiceClient)
    store = CompanyProfileStore("UseDevelopmentStorage=true", "CompanyProfiles")
    profile = {"company_name": "Acme", "overview": "Test", "capabilities": []}
    store.upsert(
        "user-1",
        profile=profile,
        sources=[{"filename": "a.pdf", "blob_path": "blob"}],
        mcp_config={"base_url": "https://mcp.example.com"},
    )
    record = store.get("user-1")
    assert record is not None
    assert record["profile"]["company_name"] == "Acme"
    assert record["mcp_config"]["base_url"] == "https://mcp.example.com"
