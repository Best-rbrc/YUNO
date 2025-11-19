import argparse
import os

# Suppress warnings and logs
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TensorFlow warnings
os.environ['GLOG_minloglevel'] = '2'  # Suppress MediaPipe/GLOG warnings

from src.person_manager import enroll_person, identify_person, identify_local, add_face
from src.input_handler import start_button_listener
from src.sync_manager import SyncManager
from src.rizz_orchestrator import run_rizz_pipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['enroll', 'identify', 'identify_local', 'add_face', 'button', 'sync', 'rizz'])
    parser.add_argument('--name', type=str, default=None)
    args = parser.parse_args()

    if args.command == 'enroll':
        enroll_person(name=args.name)
    elif args.command == 'identify':
        identify_person()
    elif args.command == 'identify_local':
        identify_local()
    elif args.command == 'add_face':
        add_face(name=args.name)
    elif args.command == 'sync':
        sync_manager = SyncManager(auto_sync_on_start=False)
        sync_manager.sync_database()
    elif args.command == 'button':
        print("🔘 Starte Button Listener für Raspberry Pi...")
        print("   Button:")
        print("     1x Press:  Enroll")
        print("     2x Press:  Identify")
        print("   Heartbeat-Sensor (KY-039):")
        print("     3-5s Finger:  Rizz Mode")
        print("     6s+ Finger:    Sync")
        start_button_listener()
    elif args.command == 'rizz':
        run_rizz_pipeline()


if __name__ == '__main__':
    main()
