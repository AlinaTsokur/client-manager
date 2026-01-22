"""
Yandex Disk integration service.
"""
import requests
from typing import Optional
from datetime import datetime

from config.settings import settings
from utils.helpers import transliterate


class YandexDiskService:
    """Service for Yandex Disk operations."""
    
    BASE_API_URL = "https://cloud-api.yandex.net/v1/disk"
    BASE_PATH = "/Clients"
    
    def __init__(self):
        self._token = settings.YANDEX_TOKEN
        self._headers = {"Authorization": f"OAuth {self._token}"}
    
    @property
    def is_configured(self) -> bool:
        """Check if service is properly configured."""
        return bool(self._token)
    
    def create_folder(self, folder_name: str) -> str:
        """
        Create a folder on Yandex Disk and return public link.
        
        Args:
            folder_name: Name of the folder to create
            
        Returns:
            Public URL of the created folder or error message
        """
        if not self.is_configured:
            return "Яндекс.Диск не настроен"
        
        path = f"{self.BASE_PATH}/{folder_name}"
        
        try:
            # Ensure base folder exists
            r1 = requests.put(
                f"{self.BASE_API_URL}/resources?path={self.BASE_PATH}",
                headers=self._headers
            )
            if r1.status_code not in (200, 201, 202, 409):
                print(f"Yandex base folder error: {r1.status_code} {r1.text}")
            
            # Create target folder
            r2 = requests.put(
                f"{self.BASE_API_URL}/resources?path={path}",
                headers=self._headers
            )
            if r2.status_code not in (200, 201, 202, 409):
                print(f"Yandex create folder error: {r2.status_code} {r2.text}")
            
            # Publish folder
            r3 = requests.put(
                f"{self.BASE_API_URL}/resources/publish?path={path}",
                headers=self._headers
            )
            if r3.status_code not in (200, 201, 202):
                print(f"Yandex publish error: {r3.status_code} {r3.text}")
            
            # Get public URL
            response = requests.get(
                f"{self.BASE_API_URL}/resources?path={path}",
                headers=self._headers
            )
            meta = response.json()
            
            return meta.get("public_url", "Ссылка не создана")
            
        except Exception as e:
            print(f"Error creating Yandex folder: {e}")
            return "Ошибка создания папки"
    
    def upload_file(self, file_obj, folder_name: str, filename: str) -> bool:
        """
        Upload a file to Yandex Disk.
        
        Args:
            file_obj: File-like object to upload
            folder_name: Target folder name
            filename: Name for the uploaded file
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_configured:
            return False
        
        path = f"{self.BASE_PATH}/{folder_name}/{filename}"
        folder_path = f"{self.BASE_PATH}/{folder_name}"
        
        try:
            # Check if folder exists, create if not
            check = requests.get(
                f"{self.BASE_API_URL}/resources?path={folder_path}",
                headers=self._headers
            )
            if check.status_code != 200:
                self.create_folder(folder_name)
            
            # Get upload URL
            response = requests.get(
                f"{self.BASE_API_URL}/resources/upload?path={path}&overwrite=true",
                headers=self._headers
            )
            upload_url = response.json().get("href")
            
            if upload_url:
                requests.put(upload_url, files={"file": file_obj})
                return True
            
            return False
            
        except Exception as e:
            print(f"Error uploading to Yandex: {e}")
            return False
    
    def get_folder_name_from_link(self, public_link: str) -> Optional[str]:
        """
        Resolve folder name from public link via API.
        """
        if not public_link or not any(x in public_link for x in ("yadi.sk", "disk.yandex.ru")):
            return None

        try:
            api_url = f"{self.BASE_API_URL}/public/resources"
            response = requests.get(
                api_url,
                params={"public_key": public_link},
                headers=self._headers,
                timeout=10
            )

            if response.status_code == 200:
                return response.json().get("name")
            return None

        except Exception as e:
            print(f"Error resolving Yandex link: {e}")
            return None
    
    def get_client_folder_name(self, client: dict) -> str:
        """
        Determine folder name for a client.
        
        Args:
            client: Client data dictionary
            
        Returns:
            Folder name string
        """
        # Try to get from existing link first
        link = client.get("yandex_link")
        if link and link != "Ссылка не создана" and any(x in link for x in ("yadi.sk", "disk.yandex.ru")):
            name = self.get_folder_name_from_link(link)
            if name:
                return name
        
        # Fallback: construct from FIO + date (sanitized)
        fio = client.get("fio", "Client")
        # Sanitize FIO for folder name
        fio = str(fio).strip()
        fio = fio.replace("/", "-").replace("\\", "-").replace(":", "-").replace("?", "").replace("*", "").replace('"', "")
        
        created = client.get("created_at", "")
        
        if not created or str(created).lower() in ("nan", "none", ""):
            created = datetime.now().strftime("%Y-%m-%d")
        elif hasattr(created, "strftime"):
            created = created.strftime("%Y-%m-%d")
        else:
            # Sanitize ISO format: 2024-01-20T10:30:00 → 2024-01-20
            created = str(created).split("T")[0].split(" ")[0]
        
        return f"{fio}_{created}".strip("_") if fio else f"CLIENT_{created}"
