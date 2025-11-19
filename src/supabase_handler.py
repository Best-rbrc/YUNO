"""
Supabase Handler
Manages connection and operations with Supabase PostgreSQL database.
"""
import os
from typing import Optional, List, Dict, Any
import pickle
import numpy as np
from dotenv import load_dotenv

try:
    from supabase import create_client, Client
except ImportError:
    print("Warning: supabase-py not installed. Run: pip install supabase")
    create_client = None
    Client = None


class SupabaseHandler:
    """Handler for Supabase database operations."""
    
    def __init__(self):
        # Load .env from config directory
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', '.env')
        load_dotenv(dotenv_path=env_path)
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        self.client: Optional[Client] = None
        
        if create_client and self.supabase_url and self.supabase_key:
            try:
                self.client = create_client(self.supabase_url, self.supabase_key)
            except Exception as e:
                print(f"Failed to connect to Supabase: {e}")
    
    def is_connected(self) -> bool:
        """Check if Supabase connection is available."""
        return self.client is not None
    
    def get_database_version(self) -> Optional[str]:
        """
        Get the current database version from Supabase.
        Returns the latest updated_at timestamp as version string.
        """
        if not self.is_connected():
            return None
        
        try:
            # Get the most recent updated_at timestamp as version
            response = self.client.table('persons').select('updated_at').order('updated_at', desc=True).limit(1).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]['updated_at']
            else:
                # Empty database - return a default version
                return "1970-01-01T00:00:00+00:00"
        except Exception as e:
            print(f"Error getting database version: {e}")
            return None
    
    def get_all_persons(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch all persons from Supabase.
        Returns list of person records with all fields.
        """
        if not self.is_connected():
            return None
        
        try:
            response = self.client.table('persons').select('*').execute()
            return response.data
        except Exception as e:
            print(f"Error fetching persons from Supabase: {e}")
            return None
    
    def add_person(self, name: str, context: str, photo_path: str, audio_path: str, 
                   embedding: Optional[np.ndarray], photo_url: str = None, audio_url: str = None, 
                   person_id: int = None) -> Optional[Dict[str, Any]]:
        """
        Add a new person to Supabase (or update if person_id already exists).
        Uses UPSERT to sync the same ID between local and Supabase.
        
        Args:
            person_id: Optional - if provided, will use this ID (UPSERT behavior)
            
        Returns the created/updated record or None on failure.
        """
        if not self.is_connected():
            return None
        
        try:
            # Serialize embedding to bytes and convert to hex string for JSON
            embedding_hex = None
            if embedding is not None:
                embedding_bytes = pickle.dumps(embedding)
                # Convert bytes to hex string for JSON serialization
                embedding_hex = embedding_bytes.hex()
            
            data = {
                'name': name,
                'context': context,
                'photo_path': photo_path,
                'audio_path': audio_path,
                'photo_url': photo_url,
                'audio_url': audio_url,
                'embedding': embedding_hex
            }
            
            # If person_id provided, use UPSERT (insert with explicit ID or update if exists)
            if person_id is not None:
                data['id'] = person_id
                response = self.client.table('persons').upsert(data).execute()
            else:
                # No ID provided, let Supabase auto-generate
                response = self.client.table('persons').insert(data).execute()
            
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error adding person to Supabase: {e}")
            return None
    
    def update_person(self, person_id: str, name: Optional[str] = None, 
                     context: Optional[str] = None, photo_path: Optional[str] = None,
                     audio_path: Optional[str] = None, embedding: Optional[np.ndarray] = None) -> bool:
        """
        Update an existing person in Supabase.
        Returns True on success, False on failure.
        """
        if not self.is_connected():
            return False
        
        try:
            data = {}
            if name is not None:
                data['name'] = name
            if context is not None:
                data['context'] = context
            if photo_path is not None:
                data['photo_path'] = photo_path
            if audio_path is not None:
                data['audio_path'] = audio_path
            if embedding is not None:
                data['embedding'] = pickle.dumps(embedding)
            
            if not data:
                return False
            
            response = self.client.table('persons').update(data).eq('id', person_id).execute()
            return len(response.data) > 0
        except Exception as e:
            print(f"Error updating person in Supabase: {e}")
            return False
    
    def delete_person(self, person_id: str) -> bool:
        """
        Delete a person from Supabase.
        Returns True on success, False on failure.
        """
        if not self.is_connected():
            return False
        
        try:
            response = self.client.table('persons').delete().eq('id', person_id).execute()
            return len(response.data) > 0
        except Exception as e:
            print(f"Error deleting person from Supabase: {e}")
            return False
    
    def get_person_by_id(self, person_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific person by ID from Supabase.
        Returns person record or None if not found.
        """
        if not self.is_connected():
            return None
        
        try:
            response = self.client.table('persons').select('*').eq('id', person_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting person from Supabase: {e}")
            return None
    
    # ==================== FILE STORAGE METHODS ====================
    
    def upload_file(self, bucket: str, file_path: str, destination_path: str) -> Optional[str]:
        """
        Upload a file to Supabase Storage.
        
        Args:
            bucket: Bucket name (e.g. 'person-photos', 'person-audio')
            file_path: Local file path to upload
            destination_path: Remote path in bucket (e.g. 'person_1/profile.jpg')
            
        Returns:
            Public URL of uploaded file or None on failure
        """
        if not self.is_connected():
            return None
        
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return None
        
        try:
            # Read file
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Upload to Supabase Storage
            response = self.client.storage.from_(bucket).upload(
                path=destination_path,
                file=file_data,
                file_options={"content-type": self._get_mime_type(file_path)}
            )
            
            # Get public URL
            public_url = self.client.storage.from_(bucket).get_public_url(destination_path)
            return public_url
            
        except Exception as e:
            print(f"Error uploading file to Supabase: {e}")
            return None
    
    def download_file(self, bucket: str, source_path: str, destination_path: str) -> Optional[str]:
        """
        Download a file from Supabase Storage.
        
        Args:
            bucket: Bucket name
            source_path: Remote path in bucket
            destination_path: Local path to save file
            
        Returns:
            Local file path or None on failure
        """
        if not self.is_connected():
            return None
        
        try:
            # Download from Supabase
            response = self.client.storage.from_(bucket).download(source_path)
            
            # Create directory if needed
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            
            # Save file
            with open(destination_path, 'wb') as f:
                f.write(response)
            
            return destination_path
            
        except Exception as e:
            print(f"Error downloading file from Supabase: {e}")
            return None
    
    def file_exists(self, bucket: str, path: str) -> bool:
        """Check if a file exists in Supabase Storage."""
        if not self.is_connected():
            return False
        
        try:
            files = self.client.storage.from_(bucket).list(os.path.dirname(path))
            filename = os.path.basename(path)
            return any(f['name'] == filename for f in files)
        except Exception as e:
            print(f"Error checking file existence: {e}")
            return False
    
    def delete_file(self, bucket: str, path: str) -> bool:
        """Delete a file from Supabase Storage."""
        if not self.is_connected():
            return False
        
        try:
            self.client.storage.from_(bucket).remove([path])
            return True
        except Exception as e:
            print(f"Error deleting file from Supabase: {e}")
            return False
    
    def _get_mime_type(self, file_path: str) -> str:
        """Get MIME type based on file extension."""
        ext = os.path.splitext(file_path)[1].lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.wav': 'audio/wav',
            '.mp3': 'audio/mpeg',
            '.m4a': 'audio/mp4'
        }
        return mime_types.get(ext, 'application/octet-stream')


if __name__ == '__main__':
    # Test connection
    handler = SupabaseHandler()
    if handler.is_connected():
        print("Successfully connected to Supabase!")
        version = handler.get_database_version()
        print(f"Database version: {version}")
    else:
        print("Failed to connect to Supabase. Check your credentials.")

