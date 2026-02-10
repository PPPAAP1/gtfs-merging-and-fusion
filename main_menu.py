import sys
from pathlib import Path
import yaml

# Import existing script functions
from src.gtfs_scraping_main.read_route_type_gtfs import load_static_gtfs_route
from src.gtfs_scraping_main.fetch_realtime_gtfs import start_fetch_loop
from src.gtfs_scraping_main.read_stop_name_gtfs import load_static_gtfs_stop

from src.gtfs_merging_fusion.fusion_finale import merging_fusion

def load_config():
    cfg_path = Path("config/config.yaml")
    if not cfg_path.exists():
        print(f"❌ Check Config: {cfg_path}")
        sys.exit(1)
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg

def main_menu():
    cfg = load_config()

    while True:
        print("======================================")
        print("++++++++++++++++++++++++++++++++++++++")
        print("Welcome to GTFS Working Pannel")
        print("++++++++++++++++++++++++++++++++++++++")
        print("======================================")
        print("If you already have full dataset(Static + Realtime trip-updates):")
        print("1. Load and filter Static GTFS by Route Type")
        print("and/or")
        print("2. Load, filter and analyse GTFS data by Stop Name")
        print("--------------------------------------")
        print("If you don't have GTFS static data:")
        print("go to OpenDataÖPNV or GovData.de or gtfs.de, See README.md for details")
        print("--------------------------------------")
        print("If you don't have GTFS Real-time Trip Updates:")
        print("3. Fetch Real-time GTFS-RT now.")
        print("--------------------------------------")
        print("If you have set your desired static and real-time trip updates in a certain location:")
        print("4. Run Fusion and Final Analysis")
        print("0. Exit")

        choice = input("Please enter your choice number: ").strip()
        if choice == "1":
            print("\n📂 Running Static GTFS merging script")
            df = load_static_gtfs_route(cfg)
            print(df.head())
        
        elif choice == "2":
            print("\n📂 Running Static GTFS merging script by Stop Name")
            df = load_static_gtfs_stop(cfg)
            print(df.head())

        elif choice == "3":
            print("\n📂 Preparing for Fetching Real-time GTFS-RT")
            start_fetch_loop()
            print(df.head())

        elif choice == "4":
            print("\n📂 Running the test Merging and Fusion Analysis")
            merging_fusion()

        elif choice == "0":
            print("Auf Wiedersehen!")
            break
        else:
            print("Invalid choice, please enter a number 0-4")

if __name__ == "__main__":
    main_menu()
