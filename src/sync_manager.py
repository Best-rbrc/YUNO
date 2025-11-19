"""
Sync Manager
Handles synchronization between local SQLite and Supabase PostgreSQL using version-based sync.
"""
from typing import Optional
import time
from datetime import datetime, timedelta

from src.supabase_handler import SupabaseHandler
from src.database_handler import (
    init_db,
    get_local_db_version,
    set_local_db_version,
    clear_all_persons,
    bulk_insert_persons
)
from src.path_manager import get_db_path, PathManager
import os
import shutil


class SyncManager:
    """Manages database synchronization between local SQLite and Supabase."""
    
    def __init__(self, local_db_path: str = None, auto_sync_on_start: bool = True, sync_files: bool = True):
        """
        Initialize the sync manager.
        
        Args:
            local_db_path: Path to local SQLite database (None = use default from PathManager)
            auto_sync_on_start: Whether to automatically sync on initialization
            sync_files: Whether to also download files (photos/audio) during sync
        """
        self.local_db_path = local_db_path if local_db_path else get_db_path()
        self.supabase = SupabaseHandler()
        self.sync_files = sync_files
        
        # Initialize local database if needed
        init_db(self.local_db_path)
        
        # Auto-sync on startup if enabled
        if auto_sync_on_start and self.supabase.is_connected():
            print("Checking for database updates...")
            self.sync_from_supabase()
    
    def needs_sync(self) -> bool:
        """
        Check if local database needs to be synced with Supabase.
        Compares local version with remote version.
        
        Returns:
            True if sync is needed, False otherwise
        """
        if not self.supabase.is_connected():
            print("Supabase not connected. Cannot check for updates.")
            return False
        
        local_version = get_local_db_version(self.local_db_path)
        remote_version = self.supabase.get_database_version()
        
        if remote_version is None:
            print("Could not fetch remote database version.")
            return False
        
        if local_version is None:
            print("No local version found. Full sync required.")
            return True
        
        # Compare versions (timestamps)
        if local_version != remote_version:
            print(f"Version mismatch - Local: {local_version}, Remote: {remote_version}")
            return True
        
        print("Database is up to date.")
        return False
    
    def sync_from_supabase(self, force: bool = False) -> bool:
        """
        Sync local database from Supabase (download).
        Only syncs if version has changed, unless force=True.
        
        Args:
            force: Force sync even if versions match
            
        Returns:
            True if sync was performed, False otherwise
        """
        if not self.supabase.is_connected():
            print("Cannot sync: Supabase not connected.")
            return False
        
        # Check if sync is needed
        if not force and not self.needs_sync():
            print("No sync needed.")
            return False
        
        print("Starting database sync from Supabase...")
        start_time = time.time()
        
        try:
            # Step 1: Delete ALL local person folders for clean sync
            print("🗑️  Deleting all local person folders...")
            self._delete_all_person_folders()
            
            # Step 2: Clear local database
            clear_all_persons(self.local_db_path)
            
            # Step 3: Fetch all persons from Supabase
            remote_persons = self.supabase.get_all_persons()
            
            if remote_persons is None:
                print("Failed to fetch data from Supabase.")
                return False
            
            print(f"Fetched {len(remote_persons)} persons from Supabase")
            
            # Step 4: Insert all persons into local database
            bulk_insert_persons(remote_persons, self.local_db_path)
            
            # Step 5: Download files if enabled
            if self.sync_files:
                print(f"\n📥 Downloading files for {len(remote_persons)} persons...")
                self._download_person_files(remote_persons)
            
            # Step 6: Update local version
            remote_version = self.supabase.get_database_version()
            if remote_version:
                set_local_db_version(remote_version, self.local_db_path)
            
            elapsed = time.time() - start_time
            print(f"\n✅ Sync completed successfully in {elapsed:.2f}s")
            return True
            
        except Exception as e:
            print(f"❌ Error during sync: {e}")
            return False
    
    def force_sync(self) -> bool:
        """Force a full sync from Supabase regardless of version."""
        return self.sync_from_supabase(force=True)
    
    def get_sync_status(self) -> dict:
        """
        Get current sync status information.
        
        Returns:
            Dictionary with sync status details
        """
        local_version = get_local_db_version(self.local_db_path)
        remote_version = None
        is_connected = self.supabase.is_connected()
        
        if is_connected:
            remote_version = self.supabase.get_database_version()
        
        needs_update = self.needs_sync() if is_connected else None
        
        return {
            'connected': is_connected,
            'local_version': local_version,
            'remote_version': remote_version,
            'needs_sync': needs_update,
            'in_sync': not needs_update if needs_update is not None else None
        }
    
    def print_sync_status(self):
        """Print current sync status in human-readable format."""
        status = self.get_sync_status()
        
        print("\n" + "="*50)
        print("DATABASE SYNC STATUS")
        print("="*50)
        print(f"Supabase Connection: {'Connected' if status['connected'] else 'Disconnected'}")
        print(f"Local Version:       {status['local_version'] or 'Not synced yet'}")
        print(f"Remote Version:      {status['remote_version'] or 'N/A'}")
        print(f"File Sync:           {'Enabled' if self.sync_files else 'Disabled'}")
        
        if status['needs_sync'] is not None:
            if status['needs_sync']:
                print(f"Status:              OUT OF SYNC - Update required!")
            else:
                print(f"Status:              IN SYNC")
        else:
            print(f"Status:              Unknown (no connection)")
        print("="*50 + "\n")
    
    def sync_database(self):
        """
        User-friendly sync interface - synchronizes database with Supabase.
        Shows status before and after sync.
        """
        print("\n" + "="*60)
        print("🔄 DATENBANK SYNCHRONISATION")
        print("="*60)
        
        # Status anzeigen
        print("\n📊 Aktueller Status:")
        self.print_sync_status()
        
        # Sync durchführen
        if not self.supabase.is_connected():
            print("\n❌ Keine Verbindung zu Supabase!")
            print("   Prüfe Internet-Verbindung und config/.env Datei")
            return False
        
        print("\n🔄 Starte Synchronisation...")
        success = self.sync_from_supabase(force=True)
        
        if success:
            print("\n✅ Synchronisation erfolgreich!")
            print("\n📊 Status nach Sync:")
            self.print_sync_status()
            return True
        else:
            print("\n❌ Synchronisation fehlgeschlagen!")
            return False
    
    def _delete_all_person_folders(self):
        """
        Delete ALL local person folders for a clean sync.
        This ensures that only current Supabase data exists locally.
        """
        persons_dir = PathManager.get_persons_dir()
        
        if not os.path.exists(persons_dir):
            print("   No persons directory found")
            return
        
        deleted_count = 0
        error_count = 0
        
        try:
            # Delete all folders in persons directory
            for folder_name in os.listdir(persons_dir):
                folder_path = os.path.join(persons_dir, folder_name)
                if os.path.isdir(folder_path):
                    try:
                        shutil.rmtree(folder_path)
                        deleted_count += 1
                    except Exception as e:
                        print(f"   ⚠️  Failed to delete {folder_name}: {e}")
                        error_count += 1
            
            print(f"   ✅ Deleted {deleted_count} person folder(s)")
            if error_count > 0:
                print(f"   ❌ Errors: {error_count}")
                
        except Exception as e:
            print(f"   ❌ Error cleaning persons directory: {e}")
    
    def _download_person_files(self, persons_data: list):
        """
        Download photo and audio files for all persons from Supabase Storage.
        
        Args:
            persons_data: List of person records from Supabase
        """
        downloaded = 0
        skipped = 0
        errors = 0
        
        for person in persons_data:
            person_id = person.get('id')
            person_name = person.get('name', f'person_{person_id}')
            photo_url = person.get('photo_url')
            audio_url = person.get('audio_url')
            
            # Create person directory structure
            paths = PathManager.create_person_structure(person_id, person_name)
            
            # Download photo if URL exists
            if photo_url:
                # Extract path from URL (format: .../bucket/path)
                try:
                    photo_path_parts = photo_url.split('/person-photos/')
                    if len(photo_path_parts) > 1:
                        remote_photo_path = photo_path_parts[1]
                        local_photo = self.supabase.download_file(
                            bucket='person-photos',
                            source_path=remote_photo_path,
                            destination_path=paths['profile_photo']
                        )
                        if local_photo:
                            downloaded += 1
                        else:
                            errors += 1
                    else:
                        skipped += 1
                except Exception as e:
                    print(f"   ⚠️  Error downloading photo for {person_name}: {e}")
                    errors += 1
            
            # Download audio if URL exists
            if audio_url:
                try:
                    audio_path_parts = audio_url.split('/person-audio/')
                    if len(audio_path_parts) > 1:
                        remote_audio_path = audio_path_parts[1]
                        local_audio = self.supabase.download_file(
                            bucket='person-audio',
                            source_path=remote_audio_path,
                            destination_path=paths['audio']
                        )
                        if local_audio:
                            downloaded += 1
                        else:
                            errors += 1
                    else:
                        skipped += 1
                except Exception as e:
                    print(f"   ⚠️  Error downloading audio for {person_name}: {e}")
                    errors += 1
        
        print(f"\n📊 File Download Summary:")
        print(f"   ✅ Downloaded: {downloaded} files")
        if skipped > 0:
            print(f"   ⏭️  Skipped: {skipped} files")
        if errors > 0:
            print(f"   ❌ Errors: {errors} files")
    
    def upload_person_files(self, person_id: int, person_name: str, photo_path: str = None, audio_path: str = None) -> dict:
        """
        Upload photo and audio files for a person to Supabase Storage.
        
        Args:
            person_id: Person ID
            person_name: Person name
            photo_path: Local photo path
            audio_path: Local audio path
            
        Returns:
            dict with URLs: {'photo_url': ..., 'audio_url': ...}
        """
        urls = {'photo_url': None, 'audio_url': None}
        
        if not self.supabase.is_connected():
            print("⚠️  Cannot upload files: Supabase not connected")
            return urls
        
        # Upload photo
        if photo_path and os.path.exists(photo_path):
            remote_photo_path = f"person_{person_id}/{PathManager.sanitize_name(person_name)}_profile.jpg"
            photo_url = self.supabase.upload_file(
                bucket='person-photos',
                file_path=photo_path,
                destination_path=remote_photo_path
            )
            if photo_url:
                urls['photo_url'] = photo_url
                print(f"   ✅ Photo uploaded: {remote_photo_path}")
            else:
                print(f"   ❌ Photo upload failed")
        
        # Upload audio
        if audio_path and os.path.exists(audio_path):
            remote_audio_path = f"person_{person_id}/{PathManager.sanitize_name(person_name)}_audio.wav"
            audio_url = self.supabase.upload_file(
                bucket='person-audio',
                file_path=audio_path,
                destination_path=remote_audio_path
            )
            if audio_url:
                urls['audio_url'] = audio_url
                print(f"   ✅ Audio uploaded: {remote_audio_path}")
            else:
                print(f"   ❌ Audio upload failed")
        
        return urls


if __name__ == '__main__':
    # Test sync manager
    print("Testing Sync Manager...")
    sync_manager = SyncManager(auto_sync_on_start=False)
    sync_manager.print_sync_status()
    
    # Ask user if they want to sync
    if sync_manager.needs_sync():
        response = input("\nDatabase update available. Sync now? (y/n): ")
        if response.lower() == 'y':
            sync_manager.sync_from_supabase()
            sync_manager.print_sync_status()

