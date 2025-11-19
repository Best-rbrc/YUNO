"""
Data Loader - Fetches all detected persons from Supabase database
"""
import os
import sys
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.supabase_handler import SupabaseHandler


class DataLoader:
    """Loads person data and photos from Supabase."""
    
    def __init__(self):
        """Initialize the data loader with Supabase connection."""
        self.supabase = SupabaseHandler()
        self.cache_dir = Path(__file__).parent / "cache" / "photos"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def is_connected(self) -> bool:
        """Check if Supabase connection is available."""
        return self.supabase.is_connected()
    
    def fetch_all_persons(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch all persons from Supabase database.
        
        Returns:
            List of person dictionaries with all fields, or None on error
        """
        if not self.is_connected():
            print("❌ Cannot fetch persons: Supabase not connected")
            return None
        
        try:
            persons = self.supabase.get_all_persons()
            if persons:
                print(f"✅ Fetched {len(persons)} persons from Supabase")
            else:
                print("ℹ️  No persons found in Supabase")
            return persons
        except Exception as e:
            print(f"❌ Error fetching persons: {e}")
            return None
    
    def download_photo(self, photo_url: str, person_id: int) -> Optional[str]:
        """
        Download a photo from Supabase URL and cache it locally.
        
        Args:
            photo_url: Public URL of the photo
            person_id: Person ID for caching
        
        Returns:
            Local file path to cached photo, or None on error
        """
        if not photo_url:
            return None
        
        # Check cache first
        cache_path = self.cache_dir / f"person_{person_id}.jpg"
        if cache_path.exists():
            return str(cache_path)
        
        # Download using Supabase API method
        try:
            # Extract bucket and path from URL
            # URL format: https://<project>.supabase.co/storage/v1/object/public/<bucket>/<path>
            if '/storage/v1/object/public/' in photo_url:
                url_parts = photo_url.split('/storage/v1/object/public/')
                if len(url_parts) > 1:
                    bucket_and_path = url_parts[1]
                    parts = bucket_and_path.split('/', 1)
                    if len(parts) == 2:
                        bucket = parts[0]
                        remote_path = parts[1]
                        
                        # Use Supabase download_file method
                        local_path = self.supabase.download_file(
                            bucket=bucket,
                            source_path=remote_path,
                            destination_path=str(cache_path)
                        )
                        if local_path and os.path.exists(local_path):
                            print(f"   📥 Downloaded photo for person {person_id} via Supabase API")
                            return local_path
        except Exception as e:
            print(f"   ⚠️  Error downloading photo for person {person_id}: {e}")
            return None
        
        return None
    
    def load_persons_with_photos(self) -> List[Dict[str, Any]]:
        """
        Load all persons from Supabase and download their photos.
        
        Returns:
            List of person dictionaries with local photo paths added
        """
        persons = self.fetch_all_persons()
        if not persons:
            return []
        
        result = []
        for person in persons:
            person_id = person.get('id')
            photo_url = person.get('photo_url')
            
            # Download photo if URL exists
            local_photo_path = None
            if photo_url:
                local_photo_path = self.download_photo(photo_url, person_id)
            
            # Add local photo path to person data
            person_copy = person.copy()
            person_copy['local_photo_path'] = local_photo_path
            
            # Only include persons with valid photos
            if local_photo_path:
                result.append(person_copy)
            else:
                print(f"   ⚠️  Skipping person {person_id} (no photo available)")
        
        return result
    
    def clear_cache(self):
        """Clear the photo cache directory."""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            print("🧹 Photo cache cleared")


if __name__ == "__main__":
    # Test the data loader
    print("Testing Data Loader...")
    loader = DataLoader()
    
    if loader.is_connected():
        persons = loader.load_persons_with_photos()
        print(f"\n✅ Loaded {len(persons)} persons with photos:")
        for person in persons:
            print(f"   - {person.get('name', 'Unknown')} (ID: {person.get('id')})")
    else:
        print("❌ Supabase not connected. Check your configuration.")

