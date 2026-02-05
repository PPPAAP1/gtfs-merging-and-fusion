import sys
from pathlib import Path
import yaml

# Import existing script functions
from src.gtfs_merging_and_fusion.read_route_type_gtfs import load_static_gtfs_route
from src.gtfs_merging_and_fusion.fetch_realtime_gtfs import fetch_gtfs_rt_once, plot_delay_trend
from src.gtfs_merging_and_fusion.read_stop_name_gtfs import load_static_gtfs_stop
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
        print("===============================")
        print("Welcome to GTFS Merging and Fusion Working Pannel")
        print("===============================")
        print("It is suggested to do the followings if you already have full dataset(Static + Realtime):")
        print("1. Load and filter Static GTFS by Route Type")
        print("or")
        print("2. Analyse delay by the Stop Name")
        print("===============================")
        print("If you don't have GTFS Real-time data:")
        print("3. Fetch Real-time GTFS-RT data now")
        print("===============================")
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
            print("\n🕒 Preparing for Fetching Real-time GTFS-RT")
            fetch_gtfs_rt_once()

            print(df.head())
        elif choice == "0":
            print("Auf Wiedersehen!")
            break
        else:
            print("Invalid choice, please enter a number 0-2")

if __name__ == "__main__":
    main_menu()
