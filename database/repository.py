"""
Database repositories for Supabase operations.
"""
from typing import Optional
import json
import pandas as pd
from supabase import Client

from .supabase_client import get_supabase_client


class ClientRepository:
    """CRUD operations for clients table."""
    
    TABLE_NAME = "clients"
    
    def __init__(self):
        self._client: Client = get_supabase_client()
    
    def load_all(self) -> pd.DataFrame:
        """Load all clients as DataFrame."""
        try:
            response = self._client.table(self.TABLE_NAME).select("*").execute()
            if response.data:
                return pd.DataFrame(response.data)
            return pd.DataFrame()
        except Exception as e:
            print(f"Error loading clients: {e}")
            return pd.DataFrame()
    
    def get_by_id(self, client_id: str) -> Optional[dict]:
        """Get a single client by ID."""
        try:
            response = self._client.table(self.TABLE_NAME).select("*").eq("id", client_id).single().execute()
            return response.data
        except Exception as e:
            print(f"Error getting client {client_id}: {e}")
            return None
    
    def save(self, data: dict) -> bool:
        """Insert or update a client."""
        try:
            # Ensure bank_interactions is JSON string
            if "bank_interactions" in data and isinstance(data["bank_interactions"], list):
                data["bank_interactions"] = json.dumps(data["bank_interactions"], ensure_ascii=False)
            
            # Upsert (insert or update on conflict)
            self._client.table(self.TABLE_NAME).upsert(data).execute()
            return True
        except Exception as e:
            print(f"Error saving client: {e}")
            return False
    
    def save_all(self, df: pd.DataFrame) -> bool:
        """Save entire DataFrame (bulk upsert)."""
        try:
            records = df.to_dict('records')
            # Clean up None values and convert to proper types
            for record in records:
                for key in list(record.keys()):
                    v = record[key]
                    # Handle None first
                    if v is None:
                        continue
                    # Handle list/dict (don't use pd.isna on these)
                    elif isinstance(v, (list, dict)):
                        if key == "bank_interactions":
                            v = json.dumps(v, ensure_ascii=False)
                    # Handle NaN for scalar values
                    elif pd.isna(v):
                        v = None
                    record[key] = v
            
            self._client.table(self.TABLE_NAME).upsert(records).execute()
            return True
        except Exception as e:
            print(f"Error saving all clients: {e}")
            return False
    
    def delete(self, client_id: str) -> bool:
        """Delete a client by ID."""
        try:
            self._client.table(self.TABLE_NAME).delete().eq("id", client_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting client {client_id}: {e}")
            return False


class BankRepository:
    """CRUD operations for banks table."""
    
    TABLE_NAME = "banks"
    
    def __init__(self):
        self._client: Client = get_supabase_client()
    
    def load_all(self) -> pd.DataFrame:
        """Load all banks as DataFrame."""
        try:
            response = self._client.table(self.TABLE_NAME).select("*").execute()
            if response.data:
                return pd.DataFrame(response.data)
            return pd.DataFrame()
        except Exception as e:
            print(f"Error loading banks: {e}")
            return pd.DataFrame()
    
    def get_by_id(self, bank_id: str) -> Optional[dict]:
        """Get a single bank by ID."""
        try:
            response = self._client.table(self.TABLE_NAME).select("*").eq("id", bank_id).single().execute()
            return response.data
        except Exception as e:
            print(f"Error getting bank {bank_id}: {e}")
            return None
    
    def save(self, data: dict) -> bool:
        """Insert or update a bank."""
        try:
            self._client.table(self.TABLE_NAME).upsert(data).execute()
            return True
        except Exception as e:
            print(f"Error saving bank: {e}")
            return False
    
    def save_all(self, df: pd.DataFrame) -> bool:
        """Save entire DataFrame (bulk upsert)."""
        try:
            records = df.to_dict('records')
            # Clean up None values
            for record in records:
                for key in list(record.keys()):
                    v = record[key]
                    if v is None:
                        continue
                    elif isinstance(v, (list, dict)):
                        pass  # Keep as is
                    elif pd.isna(v):
                        record[key] = None
            
            self._client.table(self.TABLE_NAME).upsert(records).execute()
            return True
        except Exception as e:
            print(f"Error saving all banks: {e}")
            return False
    
    def delete(self, bank_id: str) -> bool:
        """Delete a bank by ID."""
        try:
            self._client.table(self.TABLE_NAME).delete().eq("id", bank_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting bank {bank_id}: {e}")
            return False


class ApplicationRepository:
    """CRUD operations for applications table."""
    
    TABLE_NAME = "applications"
    
    def __init__(self):
        self._client: Client = get_supabase_client()
    
    def load_all(self) -> pd.DataFrame:
        """Load all applications as DataFrame."""
        try:
            response = self._client.table(self.TABLE_NAME).select("*").execute()
            if response.data:
                return pd.DataFrame(response.data)
            return pd.DataFrame()
        except Exception as e:
            print(f"Error loading applications: {e}")
            return pd.DataFrame()
    
    def save(self, data: dict) -> bool:
        """Insert or update an application."""
        try:
            self._client.table(self.TABLE_NAME).upsert(data).execute()
            return True
        except Exception as e:
            print(f"Error saving application: {e}")
            return False
