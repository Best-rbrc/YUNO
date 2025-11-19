"""
Path Manager - Verwaltet die neue Ordnerstruktur für data/
Pro Person gibt es einen eigenen Ordner mit allen zugehörigen Dateien.
"""
import os
import re
from datetime import datetime
from typing import Tuple, Optional


class PathManager:
    """Verwaltet Pfade für die Pro-Person Ordnerstruktur"""
    
    # Basis-Verzeichnisse
    DATA_ROOT = "data"
    DB_DIR = os.path.join(DATA_ROOT, "database")
    PERSONS_DIR = os.path.join(DATA_ROOT, "persons")
    
    # Datenbank Pfad
    DB_PATH = os.path.join(DB_DIR, "memory.db")
    
    @staticmethod
    def init_directories():
        """Erstellt alle benötigten Verzeichnisse"""
        dirs = [
            PathManager.DB_DIR,
            PathManager.PERSONS_DIR
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)
    
    @staticmethod
    def sanitize_name(name: str) -> str:
        """
        Bereinigt Namen für Dateinamen (entfernt Sonderzeichen, Leerzeichen, etc.)
        Beispiel: "Max Mustermann!" -> "MaxMustermann"
        """
        # Entferne Sonderzeichen, behalte nur Buchstaben und Zahlen
        clean = re.sub(r'[^\w\s-]', '', name)
        # Entferne Leerzeichen
        clean = re.sub(r'\s+', '', clean)
        return clean
    
    @staticmethod
    def get_person_dir(person_id: int, person_name: str) -> str:
        """
        Gibt den Ordnerpfad für eine Person zurück.
        Format: data/persons/person_{id}_{name}/
        """
        safe_name = PathManager.sanitize_name(person_name)
        dirname = f"person_{person_id}_{safe_name}"
        return os.path.join(PathManager.PERSONS_DIR, dirname)
    
    @staticmethod
    def create_person_structure(person_id: int, person_name: str) -> dict:
        """
        Erstellt die komplette Ordnerstruktur für eine neue Person.
        
        Returns:
            dict mit allen relevanten Pfaden:
            {
                'base_dir': 'data/persons/person_1_MaxMustermann/',
                'profile_photo': 'data/persons/person_1_MaxMustermann/profile.jpg',
                'audio': 'data/persons/person_1_MaxMustermann/audio.wav',
                'faces_dir': 'data/persons/person_1_MaxMustermann/faces/'
            }
        """
        base_dir = PathManager.get_person_dir(person_id, person_name)
        faces_dir = os.path.join(base_dir, "faces")
        
        # Erstelle Verzeichnisse
        os.makedirs(faces_dir, exist_ok=True)
        
        return {
            'base_dir': base_dir,
            'profile_photo': os.path.join(base_dir, "profile.jpg"),
            'audio': os.path.join(base_dir, "audio.wav"),
            'faces_dir': faces_dir
        }
    
    @staticmethod
    def get_person_paths(person_id: int, person_name: str) -> dict:
        """
        Gibt die Pfade für eine existierende Person zurück (ohne zu erstellen).
        """
        base_dir = PathManager.get_person_dir(person_id, person_name)
        faces_dir = os.path.join(base_dir, "faces")
        
        return {
            'base_dir': base_dir,
            'profile_photo': os.path.join(base_dir, "profile.jpg"),
            'audio': os.path.join(base_dir, "audio.wav"),
            'faces_dir': faces_dir
        }
    
    @staticmethod
    def get_persons_dir() -> str:
        """Gibt das Persons-Verzeichnis zurück"""
        return PathManager.PERSONS_DIR
    
    @staticmethod
    def add_face_to_person(person_id: int, person_name: str, face_img_path: str) -> str:
        """
        Kopiert ein Gesichtsbild in den faces/ Ordner einer Person.
        
        Args:
            person_id: ID der Person
            person_name: Name der Person
            face_img_path: Pfad zum Quell-Bild
            
        Returns:
            Pfad zum kopierten Bild im faces/ Ordner
        """
        import shutil
        
        paths = PathManager.get_person_paths(person_id, person_name)
        faces_dir = paths['faces_dir']
        
        # Erstelle faces/ Ordner falls nicht vorhanden
        os.makedirs(faces_dir, exist_ok=True)
        
        # Zähle existierende Faces
        existing_faces = [f for f in os.listdir(faces_dir) if f.endswith('.jpg')]
        face_num = len(existing_faces) + 1
        
        # Ziel-Pfad
        dest_path = os.path.join(faces_dir, f"face_{face_num:03d}.jpg")
        
        # Kopiere Bild
        if os.path.exists(face_img_path):
            shutil.copy2(face_img_path, dest_path)
        
        return dest_path


# Convenience Funktionen für häufige Operationen
def init_data_structure():
    """Initialisiert die komplette data/ Struktur"""
    PathManager.init_directories()
    print("✅ Data-Struktur initialisiert:")
    print(f"   - Database: {PathManager.DB_DIR}")
    print(f"   - Persons:  {PathManager.PERSONS_DIR}")


def get_db_path() -> str:
    """Gibt den Datenbank-Pfad zurück"""
    return PathManager.DB_PATH


if __name__ == '__main__':
    # Test
    print("Testing PathManager...\n")
    
    # Init structure
    init_data_structure()
    
    # Test person paths
    print("\n📁 Person Paths:")
    paths = PathManager.create_person_structure(1, "Max Mustermann")
    for key, path in paths.items():
        print(f"   {key}: {path}")
    
    print("\n✅ PathManager Test abgeschlossen!")

