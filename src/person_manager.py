"""
Person Manager - Core business logic for enrolling and identifying persons
"""

import os
import re
import shutil
from datetime import datetime
import cv2
import numpy as np

from src.camera_manager import take_photo, take_multiple_photos_during_recording
from src.audio_recorder import record_audio
from src.openai_api import transcribe_audio, analyze_text
from src.face_recognizer import get_face_from_frame, get_all_faces_from_frame, get_recognizer, detect_and_crop_face
from src.database_handler import init_db, add_person, update_person, get_person_by_id
from src.identity_matcher import match_identity, THRESHOLD, THRESHOLD_SUGGESTION
from src.speech_output import generate_and_speak_greeting, speak_unknown_person
from src.path_manager import PathManager
from src.sync_manager import SyncManager


def _cleanup_temp_dir(temp_dir: str):
    """
    Löscht einen temporären Ordner sicher.
    DEAKTIVIERT: Temp-Ordner werden nicht mehr automatisch gelöscht.
    
    Args:
        temp_dir: Pfad zum temporären Ordner
    """
    # Deaktiviert: Temp-Ordner werden behalten
    pass


def _format_context_for_storage(analysis, transcript):
    """
    Konvertiert analysis (dict) und transcript zu einem formatierbaren String für die Datenbank.
    
    Args:
        analysis: Dict von analyze_text() oder None
        transcript: String oder None
    
    Returns:
        str: Formatierter Context-String
    """
    parts = []
    
    if analysis and isinstance(analysis, dict):
        # Format analysis dict as readable text
        analysis_parts = []
        if analysis.get('name'):
            analysis_parts.append(f"Name: {analysis['name']}")
        if analysis.get('topic'):
            analysis_parts.append(f"Topic: {analysis['topic']}")
        if analysis.get('mood'):
            analysis_parts.append(f"Mood: {analysis['mood']}")
        if analysis.get('context'):
            analysis_parts.append(f"Context: {analysis['context']}")

        if analysis_parts:
            parts.append("Analysis:\n" + "\n".join(analysis_parts))

    if transcript:
        parts.append(f"Transcript: {transcript}")
    
    return "\n\n".join(parts) if parts else ""


def _copy_to_person_folder(person_id, person_name, photo_path, audio_path, cropped_photos=None, upload_to_supabase=True):
    """
    Kopiert Fotos und Audio in den Person-Ordner und gibt neue Pfade zurück.
    Optional: Lädt Files auch zu Supabase hoch.
    
    Args:
        person_id: ID der Person in der Datenbank
        person_name: Name der Person
        photo_path: Pfad zum Hauptfoto (wird zu profile.jpg)
        audio_path: Pfad zur Audio-Datei
        cropped_photos: Liste zusätzlicher gecropter Fotos für faces/ Ordner
        upload_to_supabase: Ob Files zu Supabase hochgeladen werden sollen
    
    Returns:
        dict mit neuen Pfaden: {'profile_photo': ..., 'audio': ..., 'photo_url': ..., 'audio_url': ...}
    """
    # Erstelle Person-Struktur
    paths = PathManager.create_person_structure(person_id, person_name)
    
    # Kopiere Hauptfoto als profile.jpg
    if photo_path and os.path.exists(photo_path):
        shutil.copy2(photo_path, paths['profile_photo'])
    
    # Kopiere Audio
    if audio_path and os.path.exists(audio_path):
        shutil.copy2(audio_path, paths['audio'])
    
    # Kopiere zusätzliche gecropte Fotos in faces/ Ordner
    if cropped_photos:
        for i, cropped_photo in enumerate(cropped_photos, start=1):
            if os.path.exists(cropped_photo):
                dest = os.path.join(paths['faces_dir'], f"face_{i:03d}.jpg")
                shutil.copy2(cropped_photo, dest)
    
    print(f"📁 Dateien kopiert nach: {paths['base_dir']}")
    
    result = {
        'profile_photo': paths['profile_photo'],
        'audio': paths['audio'],
        'photo_url': None,
        'audio_url': None
    }
    
    # Upload zu Supabase (optional)
    if upload_to_supabase:
        try:
            sync_manager = SyncManager(auto_sync_on_start=False, sync_files=False)
            if sync_manager.supabase.is_connected():
                print("📤 Uploading to Supabase...")
                
                # 1. Upload Files zu Storage
                urls = sync_manager.upload_person_files(
                    person_id=person_id,
                    person_name=person_name,
                    photo_path=paths['profile_photo'],
                    audio_path=paths['audio']
                )
                result['photo_url'] = urls['photo_url']
                result['audio_url'] = urls['audio_url']
                
                # 2. Speichere Metadaten in Datenbank-Tabelle
                # Hole Embedding und Context aus lokaler DB
                from src.database_handler import get_person_by_id
                import sqlite3
                import pickle
                
                local_person = get_person_by_id(person_id)
                if local_person:
                    # Hole Embedding aus DB
                    conn = sqlite3.connect(sync_manager.local_db_path)
                    c = conn.cursor()
                    c.execute('SELECT embedding FROM persons WHERE id = ?', (person_id,))
                    row = c.fetchone()
                    conn.close()
                    
                    embedding = None
                    if row and row[0]:
                        embedding = pickle.loads(row[0])
                    
                    # Füge zu Supabase Datenbank hinzu (mit derselben ID!)
                    supabase_result = sync_manager.supabase.add_person(
                        name=person_name,
                        context=local_person.get('context', ''),
                        photo_path=result['profile_photo'],
                        audio_path=result['audio'],
                        photo_url=urls['photo_url'],
                        audio_url=urls['audio_url'],
                        embedding=embedding,
                        person_id=person_id  # Wichtig: Dieselbe ID wie lokal!
                    )
                    
                    if supabase_result:
                        print(f"   ✅ Metadaten in Datenbank gespeichert")
                    else:
                        print(f"   ⚠️  Metadaten konnten nicht gespeichert werden")
                
            else:
                print("⚠️  Supabase not connected - files not uploaded")
        except Exception as e:
            print(f"⚠️  Error uploading to Supabase: {e}")
            import traceback
            traceback.print_exc()
    
    return result


def enroll_person(name: str = None):
    """
    Enroll a new person or update an existing one.
    Takes multiple photos during audio recording, extracts name from audio if not provided.
    
    Args:
        name: Optional name to use. If None, will try to extract from audio.
    """
    print("\n" + "="*50)
    print("🎯 ENROLL MODUS")
    print("="*50)
    
    # Erstelle temporäre Pfade für Aufnahme
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_dir = os.path.join("data", f"temp_enroll_{ts}")
    os.makedirs(temp_dir, exist_ok=True)
    base_photo_path = os.path.join(temp_dir, ts)
    audio_path = os.path.join(temp_dir, "audio.wav")
    
    print(f"📁 Temp: {temp_dir}")

    # Liste für alle aufgenommenen Fotos
    captured_photos = []
    
    def on_photo_taken(photo_path, frame_num):
        """Callback wenn ein Foto aufgenommen wurde"""
        captured_photos.append(photo_path)
        if frame_num == 1:
            print(f"📸 Foto {frame_num} aufgenommen...")
        elif frame_num % 5 == 0:
            print(f"📸 {frame_num} Fotos aufgenommen...")
    
    # Audio aufnehmen und dabei parallel Fotos machen
    print("🎙️📸 Starte Aufnahme (Audio + Fotos)...")
    photo_callback = take_multiple_photos_during_recording(base_photo_path, on_photo_taken)
    record_audio(audio_path, progress_callback=photo_callback, callback_interval=0.5)
    
    print(f"✅ {len(captured_photos)} Fotos aufgenommen!")

    transcript = None
    analysis = None
    detected_name = None
    
    try:
        transcript = transcribe_audio(audio_path)
        print("\n📝 Transkript:\n", transcript)
    except Exception as e:
        print("⚠️ Transkription fehlgeschlagen:", e)

    try:
        if transcript:
            analysis = analyze_text(transcript)
            print("\n🧠 Analyse:\n", analysis)
            
            # analyze_text gibt jetzt direkt ein Dictionary zurück (Structured Outputs)
            if isinstance(analysis, dict):
                if 'name' in analysis and analysis['name']:
                    detected_name = analysis['name']
                    print(f"🏷️ Name aus Analyse erkannt: {detected_name}")
            
            # Fallback: pattern matching in the transcript if no name from analysis.
            # The capture group allows 1-3 whitespace-separated name parts and uses
            # Unicode word characters so multi-part and non-Western names
            # (e.g. "Wei Ming", "Nur Aisyah", "李明") are captured, not just a
            # single Latin first name.
            if not detected_name:
                # First token: any letters (covers lowercase transcripts and CJK).
                # Continuation tokens must start uppercase so trailing stop-words
                # like "and"/"from" are excluded while multi-part names
                # ("Wei Ming", "Nur Aisyah", "Tan Ah Kow") are kept intact.
                first_tok = r"[^\W\d_]+(?:[-'’][^\W\d_]+)?"
                cont_tok = r"[A-ZÀ-Þ][^\W\d_]*(?:[-'’][^\W\d_]+)?"
                name_group = rf"({first_tok}(?:\s+{cont_tok}){{0,2}})"
                # Longer triggers first so "i'm called" wins over "i'm".
                # Trigger phrases are case-insensitive via scoped (?i:...); the
                # name group stays case-sensitive so the uppercase anchor holds.
                patterns = [
                    rf"(?i:my name is|i'm called|this is|i am|i'm)\s+{name_group}",
                    rf"(?i:ich heiße|mein name ist|ich bin)\s+{name_group}",
                    rf"(?i:hello|hi|hey),?\s+(?i:i'm|i am)\s+{name_group}",
                ]

                for pattern in patterns:
                    match = re.search(pattern, transcript, re.UNICODE)
                    if match:
                        detected_name = match.group(1).strip()
                        print(f"🏷️ Name detected: {detected_name}")
                        break
                    
    except Exception as e:
        print("⚠️ Analyse fehlgeschlagen:", e)

    # Verarbeite alle aufgenommenen Fotos - intelligente Personenerkennung
    print("\n✂️ Verarbeite Fotos...")
    
    recognizer = get_recognizer()
    init_db()
    
    # Analysiere erstes Foto um zu bestimmen welche Person hinzugefügt werden soll
    target_face_embedding = None
    target_face_photo = None
    known_persons_in_frame = []
    unknown_persons_in_frame = []
    
    if len(captured_photos) > 0:
        first_frame = cv2.imread(captured_photos[0])
        if first_frame is not None:
            print("🔍 Analysiere Gesichter im ersten Foto...")
            all_faces = get_all_faces_from_frame(first_frame)
            
            if all_faces:
                print(f"   {len(all_faces)} Gesicht(er) erkannt")
                
                # Prüfe alle Gesichter auf bekannte/unbekannte
                for i, (face_img, bbox) in enumerate(all_faces):
                    if face_img.size == 0:
                        continue
                    
                    try:
                        embedding = recognizer.get_embedding(face_img)
                        if embedding is None:
                            continue
                        
                        match = match_identity(embedding, threshold=THRESHOLD)
                        
                        if match and match["match_found"]:
                            known_persons_in_frame.append({
                                "face_num": i + 1,
                                "name": match["name"],
                                "similarity": match["similarity"],
                                "embedding": embedding,
                                "bbox": bbox
                            })
                            print(f"   ✅ Gesicht {i+1}: {match['name']} (bekannt)")
                        else:
                            unknown_persons_in_frame.append({
                                "face_num": i + 1,
                                "embedding": embedding,
                                "bbox": bbox
                            })
                            print(f"   ❓ Gesicht {i+1}: Unbekannt")
                    except Exception as e:
                        print(f"   ⚠️ Fehler bei Gesicht {i+1}: {e}")
                
                # Entscheide welche Person zu verwenden ist
                if len(unknown_persons_in_frame) == 1:
                    # Genau eine unbekannte Person → verwende diese (auch wenn nicht in der Mitte)
                    target_face_embedding = unknown_persons_in_frame[0]["embedding"]
                    target_bbox = unknown_persons_in_frame[0]["bbox"]
                    print(f"\n✅ Genau eine unbekannte Person gefunden → wird hinzugefügt")
                    
                    # Save cropped face
                    base_path = os.path.splitext(captured_photos[0])[0]
                    target_face_photo = f"{base_path}_target_cropped.jpg"
                    x, y, w, h = target_bbox
                    cropped_face = first_frame[y:y+h, x:x+w]
                    cv2.imwrite(target_face_photo, cropped_face)
                    
                elif len(unknown_persons_in_frame) == 0:
                    # Alle bekannt → verwende Person in der Mitte für Update
                    center_face = get_face_from_frame(first_frame)
                    if center_face:
                        face_img, bbox = center_face
                        target_face_embedding = recognizer.get_embedding(face_img)
                        print(f"\n✅ Alle Personen bekannt → verwende Person in der Mitte für Update")
                        
                        # Save cropped face
                        base_path = os.path.splitext(captured_photos[0])[0]
                        target_face_photo = f"{base_path}_target_cropped.jpg"
                        x, y, w, h = bbox
                        cropped_face = first_frame[y:y+h, x:x+w]
                        cv2.imwrite(target_face_photo, cropped_face)
                    else:
                        print("\n⚠️ Konnte Person in der Mitte nicht bestimmen")
                else:
                    # Mehrere unbekannte → verwende Person in der Mitte
                    center_face = get_face_from_frame(first_frame)
                    if center_face:
                        face_img, bbox = center_face
                        target_face_embedding = recognizer.get_embedding(face_img)
                        print(f"\n✅ {len(unknown_persons_in_frame)} unbekannte Personen → verwende Person in der Mitte")
                        
                        # Save cropped face
                        base_path = os.path.splitext(captured_photos[0])[0]
                        target_face_photo = f"{base_path}_target_cropped.jpg"
                        x, y, w, h = bbox
                        cropped_face = first_frame[y:y+h, x:x+w]
                        cv2.imwrite(target_face_photo, cropped_face)
                    else:
                        print("\n⚠️ Konnte Person in der Mitte nicht bestimmen")
            else:
                # Fallback: verwende Person in der Mitte wie bisher
                center_face = get_face_from_frame(first_frame)
                if center_face:
                    face_img, bbox = center_face
                    target_face_embedding = recognizer.get_embedding(face_img)
                    
                    base_path = os.path.splitext(captured_photos[0])[0]
                    target_face_photo = f"{base_path}_target_cropped.jpg"
                    x, y, w, h = bbox
                    cropped_face = first_frame[y:y+h, x:x+w]
                    cv2.imwrite(target_face_photo, cropped_face)
    
    # Wenn kein Target gefunden, verwende altes Verhalten (Person in der Mitte vom ersten Foto)
    if target_face_embedding is None:
        print("❌ Kein Gesicht in den Fotos erkannt — nichts gespeichert.")
        _cleanup_temp_dir(temp_dir)
        return  # <--- Return: nothing saved at all!
    
    # Sammle zusätzliche Embeddings von allen Fotos für die Zielperson
    print("\n📸 Sammle zusätzliche Fotos für die Zielperson...")
    valid_embeddings = [target_face_embedding]
    cropped_photos = [target_face_photo] if target_face_photo else []
    
    for i, photo_path in enumerate(captured_photos[1:], start=2):  # Skippe erstes Foto, bereits verarbeitet
        try:
            frame = cv2.imread(photo_path)
            if frame is None:
                continue
            
            # Versuche die Zielperson in diesem Foto zu finden
            # Erst versuche Person in der Mitte (schneller)
            face_result = get_face_from_frame(frame)
            if face_result:
                face_img, bbox = face_result
                if face_img.size > 0:
                    try:
                        embedding = recognizer.get_embedding(face_img)
                        if embedding is not None:
                            # Prüfe ob es die Zielperson ist (ähnlich genug)
                            similarity = np.dot(target_face_embedding, embedding)
                            if similarity >= 0.40:  # Mindestähnlichkeit für zusätzliche Fotos
                                valid_embeddings.append(embedding)
                                
                                # Save cropped face
                                cropped_path = detect_and_crop_face(photo_path)
                                if cropped_path:
                                    cropped_photos.append(cropped_path)
                                else:
                                    base_path = os.path.splitext(photo_path)[0]
                                    cropped_path = f"{base_path}_cropped.jpg"
                                    x, y, w, h = bbox
                                    cropped_face = frame[y:y+h, x:x+w]
                                    cv2.imwrite(cropped_path, cropped_face)
                                    cropped_photos.append(cropped_path)
                    except Exception:
                        pass
        except Exception:
            pass
    
    print(f"✅ {len(valid_embeddings)} Fotos für die Zielperson gesammelt")
    
    # Priority: command line name > detected name > "unknown"
    final_name = name or detected_name or "unknown"
    
    # Try to match the target person
    match = match_identity(target_face_embedding, threshold=THRESHOLD)
    if match and match["match_found"]:
        pid = match["person_id"]
        similarity = match["similarity"]
        existing_name = match["name"]
        print(f"\nℹ️ Person bereits bekannt: id={pid}, name={existing_name}, similarity={similarity:.2f}")

        # Update with new name if detected/provided and store ALL embeddings
        update_name = final_name if final_name != "unknown" else None
        
        # Update mit erstem Foto, dann füge weitere hinzu
        context_str = _format_context_for_storage(analysis, transcript)
        ok = update_person(
            pid,
            new_context=context_str if context_str else None,
            photo_path=target_face_photo,
            audio_path=audio_path,
            embedding=target_face_embedding,
            new_name=update_name
        )
        
        # Füge alle anderen Embeddings auch hinzu (als separate Updates)
        for i, (emb, photo) in enumerate(zip(valid_embeddings[1:], cropped_photos[1:]), start=2):
            update_person(pid, photo_path=photo, embedding=emb)
        
        if ok:
            display_name = update_name or existing_name
            # Kopiere neue Fotos in existierenden Person-Ordner
            _copy_to_person_folder(pid, display_name, target_face_photo, audio_path, cropped_photos)
            print(f"✅ Aktualisiert Eintrag id={pid}, name={display_name} mit {len(valid_embeddings)} Fotos")
        else:
            print("⚠️ Aktualisierung fehlgeschlagen — neuer Eintrag wird angelegt.")
            context_str = _format_context_for_storage(analysis, transcript)
            # Erst temporär speichern
            rowid = add_person(final_name, context_str, target_face_photo, audio_path, target_face_embedding)
            # Dann in Person-Ordner kopieren
            new_paths = _copy_to_person_folder(rowid, final_name, target_face_photo, audio_path, cropped_photos)
            # DB mit finalen Pfaden updaten
            update_person(rowid, photo_path=new_paths['profile_photo'], audio_path=new_paths['audio'])
            print(f"✅ Gespeichert als id={rowid}, name={final_name}")
        _cleanup_temp_dir(temp_dir)
        return
    else:
        print(f"\n✅ Neue Person wird hinzugefügt: {final_name}")

    # No match: create new person record with first embedding
    context_str = _format_context_for_storage(analysis, transcript)
    # Erst temporär speichern
    rowid = add_person(final_name, context_str, target_face_photo, audio_path, target_face_embedding)
    
    # Kopiere in Person-Ordner
    new_paths = _copy_to_person_folder(rowid, final_name, target_face_photo, audio_path, cropped_photos)
    
    # Update DB mit finalen Pfaden
    update_person(rowid, photo_path=new_paths['profile_photo'], audio_path=new_paths['audio'])
    
    # Add additional embeddings as updates
    for emb, photo in zip(valid_embeddings[1:], cropped_photos[1:]):
        update_person(rowid, photo_path=photo, embedding=emb)
    
    print(f"✅ Gespeichert als id={rowid}, name={final_name} mit {len(valid_embeddings)} Fotos")
    _cleanup_temp_dir(temp_dir)


def add_face(name: str = None):
    """Schnelle Foto-only Funktion (ohne Audio). Matching arcface_test.py approach.
    Wenn mehrere Personen im Bild sind, werden nur unbekannte Personen hinzugefügt."""
    # Erstelle temporäre Pfade
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_dir = os.path.join("data", f"temp_addface_{ts}")
    os.makedirs(temp_dir, exist_ok=True)
    photo_path = os.path.join(temp_dir, "photo.jpg")
    print(f"📁 Temp: {temp_dir}")

    print("📸 Nehme Foto auf...")
    take_photo(photo_path)
    print(f"✅ Foto gespeichert: {photo_path}")

    # Load frame directly (matching arcface_test.py)
    frame = cv2.imread(photo_path)
    if frame is None:
        print("❌ Konnte Foto nicht laden!")
        _cleanup_temp_dir(temp_dir)
        return

    # Extract ALL faces from frame
    print("🔍 Suche Gesichter...")
    all_faces = get_all_faces_from_frame(frame)
    
    if not all_faces:
        print("❌ Kein Gesicht erkannt!")
        _cleanup_temp_dir(temp_dir)
        return
    
    print(f"✅ {len(all_faces)} Gesicht(er) erkannt!")
    
    # Initialize database
    init_db()
    recognizer = get_recognizer()
    
    # Process all faces: check which ones are unknown and add them
    known_persons = []
    unknown_faces = []
    
    for i, (face_img, bbox) in enumerate(all_faces, 1):
        if face_img.size == 0:
            continue
        
        print(f"\n🧮 Verarbeite Gesicht {i}/{len(all_faces)}...")
        
        try:
            embedding = recognizer.get_embedding(face_img)
        except Exception as e:
            print(f"   ⚠️ Fehler beim Embedding: {e}")
            continue
        
        if embedding is None:
            print(f"   ⚠️ Kein Embedding für Gesicht {i}")
            continue
        
        # Check if face already exists in database
        match = match_identity(embedding, threshold=THRESHOLD)
        
        if match and match["match_found"]:
            known_persons.append({
                "face_num": i,
                "name": match["name"],
                "similarity": match["similarity"]
            })
            print(f"   ✅ Bereits bekannt: {match['name']} (Ähnlichkeit: {match['similarity']:.3f})")
        else:
            unknown_faces.append({
                "face_num": i,
                "face_img": face_img,
                "bbox": bbox,
                "embedding": embedding
            })
            print(f"   ❓ Unbekannt - wird hinzugefügt")
    
    # Print summary
    print("\n" + "="*50)
    if known_persons:
        print(f"✅ {len(known_persons)} bekannte Person(en) übersprungen:")
        for person in known_persons:
            print(f"   Gesicht {person['face_num']}: {person['name']}")
        print()
    
    # Add unknown faces
    if not unknown_faces:
        print("ℹ️  Alle Personen sind bereits in der Datenbank.")
        _cleanup_temp_dir(temp_dir)
        return
    
    print(f"📝 Füge {len(unknown_faces)} unbekannte Person(en) hinzu...\n")
    
    for unknown in unknown_faces:
        # Save cropped face for database
        cropped_path = os.path.join(temp_dir, f"face{unknown['face_num']}_cropped.jpg")
        x, y, w, h = unknown['bbox']
        cropped_face = frame[y:y+h, x:x+w]
        cv2.imwrite(cropped_path, cropped_face)
        
        # Store in DB
        final_name = name or "unknown"
        # Erst temporär speichern
        rowid = add_person(final_name, "", cropped_path, None, unknown['embedding'])
        # Dann in Person-Ordner kopieren
        new_paths = _copy_to_person_folder(rowid, final_name, cropped_path, None, [cropped_path])
        # DB updaten mit finalen Pfaden
        update_person(rowid, photo_path=new_paths['profile_photo'])
        print(f"✅ Gesicht {unknown['face_num']} gespeichert als id={rowid}, name={final_name}")
    
    _cleanup_temp_dir(temp_dir)


def identify_local():
    """
    Identify all persons from a single photo (local only, no speech, no OpenAI calls).
    Only prints the result to console.
    Matching arcface_test.py approach - working directly with frames.
    Can identify multiple persons in the same photo.
    """
    print("\n" + "="*50)
    print("🔍 IDENTIFY LOCAL MODUS (ohne Speech/OpenAI)")
    print("="*50)
    
    # Erstelle temporäre Pfade
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_dir = os.path.join("data", f"temp_identify_{ts}")
    os.makedirs(temp_dir, exist_ok=True)
    photo_path = os.path.join(temp_dir, f"{ts}_identify.jpg")
    print(f"📁 Temp: {temp_dir}")

    print("📸 Nehme Foto auf...")
    take_photo(photo_path)
    print(f"✅ Foto gespeichert: {photo_path}")

    # Load frame directly (matching arcface_test.py)
    frame = cv2.imread(photo_path)
    if frame is None:
        print("❌ Konnte Foto nicht laden!")
        _cleanup_temp_dir(temp_dir)
        return

    # Extract ALL faces from frame
    print("🔍 Suche Gesichter...")
    all_faces = get_all_faces_from_frame(frame)
    
    if not all_faces:
        print("❌ Kein Gesicht erkannt!")
        _cleanup_temp_dir(temp_dir)
        return
    
    print(f"✅ {len(all_faces)} Gesicht(er) erkannt!")
    
    # Initialize database
    init_db()
    recognizer = get_recognizer()
    
    # Process all faces
    recognized_persons = []
    unknown_faces = []
    
    for i, (face_img, bbox) in enumerate(all_faces, 1):
        if face_img.size == 0:
            continue
        
        print(f"\n🧮 Verarbeite Gesicht {i}/{len(all_faces)}...")
        
        try:
            embedding = recognizer.get_embedding(face_img)
        except Exception as e:
            print(f"   ⚠️ Fehler beim Embedding: {e}")
            continue
        
        if embedding is None:
            print(f"   ⚠️ Kein Embedding für Gesicht {i}")
            continue
        
        # Match identity
        match = match_identity(embedding, threshold=THRESHOLD)
        
        if match and match["match_found"]:
            recognized_persons.append({
                "face_num": i,
                "person_id": match["person_id"],
                "name": match["name"],
                "similarity": match["similarity"],
                "bbox": bbox
            })
        else:
            unknown_faces.append({
                "face_num": i,
                "similarity": match["similarity"] if match else 0.0,
                "best_candidate": match["best_candidates"][0] if match and match.get("best_candidates") else None,
                "bbox": bbox
            })
    
    # Print results
    print("\n" + "="*50)
    if recognized_persons:
        print(f"✅ {len(recognized_persons)} bekannte Person(en) erkannt:\n")
        for person in recognized_persons:
            print(f"   Person {person['face_num']}: {person['name']}")
            print(f"      ID: {person['person_id']}")
            print(f"      Ähnlichkeit: {person['similarity']:.3f}")
            
            # Get full person data for display
            person_data = get_person_by_id(person['person_id'])
            if person_data:
                context = person_data.get('context', '')
                created_at = person_data.get('created_at', '')
                if context:
                    print(f"      Kontext: {context[:50]}...")
                if created_at:
                    print(f"      Erstes Treffen: {created_at}")
            print()
    else:
        print("❌ Keine bekannten Personen gefunden")
    
    if unknown_faces:
        print(f"❓ {len(unknown_faces)} unbekannte Person(en):\n")
        for unknown in unknown_faces:
            print(f"   Gesicht {unknown['face_num']}: Unbekannt")
            # Only show best guess if similarity is reasonably close to threshold (>= 0.40)
            if unknown['best_candidate'] and unknown['best_candidate']['similarity'] >= THRESHOLD_SUGGESTION:
                print(f"      Beste Vermutung: {unknown['best_candidate']['name']} (Ähnlichkeit: {unknown['best_candidate']['similarity']:.3f})")
            print()
    
    _cleanup_temp_dir(temp_dir)


def identify_person():
    """
    Identify all persons from a single photo.
    Uses speech output to announce who the persons are.
    Matching arcface_test.py approach - working directly with frames.
    Can identify multiple persons in the same photo.
    """
    print("\n" + "="*50)
    print("🔍 IDENTIFY MODUS")
    print("="*50)
    
    # Erstelle temporäre Pfade
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_dir = os.path.join("data", f"temp_identify_{ts}")
    os.makedirs(temp_dir, exist_ok=True)
    photo_path = os.path.join(temp_dir, f"{ts}_identify.jpg")
    print(f"📁 Temp: {temp_dir}")

    print("📸 Nehme Foto auf...")
    take_photo(photo_path)
    print(f"✅ Foto gespeichert: {photo_path}")

    # Load frame directly (matching arcface_test.py)
    frame = cv2.imread(photo_path)
    if frame is None:
        print("❌ Konnte Foto nicht laden!")
        speak_unknown_person()
        _cleanup_temp_dir(temp_dir)
        return

    # Extract ALL faces from frame
    print("🔍 Suche Gesichter...")
    all_faces = get_all_faces_from_frame(frame)
    
    if not all_faces:
        print("❌ Kein Gesicht erkannt!")
        speak_unknown_person()
        _cleanup_temp_dir(temp_dir)
        return
    
    print(f"✅ {len(all_faces)} Gesicht(er) erkannt!")
    
    # Initialize database
    init_db()
    recognizer = get_recognizer()
    
    # Process all faces
    recognized_persons = []
    unknown_faces = []
    
    for i, (face_img, bbox) in enumerate(all_faces, 1):
        if face_img.size == 0:
            continue
        
        print(f"\n🧮 Verarbeite Gesicht {i}/{len(all_faces)}...")
        
        try:
            embedding = recognizer.get_embedding(face_img)
        except Exception as e:
            print(f"   ⚠️ Fehler beim Embedding: {e}")
            continue
        
        if embedding is None:
            print(f"   ⚠️ Kein Embedding für Gesicht {i}")
            continue
        
        # Match identity
        match = match_identity(embedding, threshold=THRESHOLD)
        
        if match and match["match_found"]:
            recognized_persons.append({
                "face_num": i,
                "person_id": match["person_id"],
                "name": match["name"],
                "similarity": match["similarity"],
                "bbox": bbox
            })
        else:
            unknown_faces.append({
                "face_num": i,
                "similarity": match["similarity"] if match else 0.0,
                "best_candidate": match["best_candidates"][0] if match and match.get("best_candidates") else None,
                "bbox": bbox
            })
    
    # Print and speak results
    print("\n" + "="*50)
    if recognized_persons:
        print(f"✅ {len(recognized_persons)} bekannte Person(en) erkannt:\n")
        
        # Speak greeting for each recognized person
        for person in recognized_persons:
            print(f"   Person {person['face_num']}: {person['name']}")
            print(f"      ID: {person['person_id']}")
            print(f"      Ähnlichkeit: {person['similarity']:.2f}")
            
            # Get full person data and speak greeting
            person_data = get_person_by_id(person['person_id'])
            if person_data:
                generate_and_speak_greeting(person_data)
            else:
                print("⚠️ Person data not found")
            print()
    else:
        print("❌ Keine bekannten Personen gefunden")
        speak_unknown_person()
    
    if unknown_faces:
        print(f"❓ {len(unknown_faces)} unbekannte Person(en):\n")
        for unknown in unknown_faces:
            print(f"   Gesicht {unknown['face_num']}: Unbekannt")
            # Only show best guess if similarity is reasonably close to threshold (>= 0.40)
            if unknown['best_candidate'] and unknown['best_candidate']['similarity'] >= THRESHOLD_SUGGESTION:
                print(f"      Beste Vermutung: {unknown['best_candidate']['name']} (Ähnlichkeit: {unknown['best_candidate']['similarity']:.3f})")
            print()
    
    _cleanup_temp_dir(temp_dir)
