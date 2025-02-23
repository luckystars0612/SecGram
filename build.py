import os
import platform
import subprocess
import shutil

# List of services to build, with their entry points
SERVICES = [
    {"name": "bot_service", "entry_point": "bot_service/main.py"},
    {"name": "telegram_scraper", "entry_point": "scraper_service/telegram_scraper.py"},
    # Add more services as needed
]

# Hidden imports that PyInstaller might miss
HIDDEN_IMPORTS = ["telethon", "sqlalchemy"]

# Path to Wine executable (for Linux to build Windows executables)
WINE_PATH = shutil.which("wine")

def run_command(command):
    """Run a shell command and handle errors."""
    try:
        subprocess.check_call(command, shell=True)
        print(f"Successfully ran: {command}")
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}\n{e}")

def build_service(service, os_type):
    """Build a single service for the specified OS."""
    name = service["name"]
    entry_point = service["entry_point"]
    hidden_imports = " ".join([f"--hidden-import={imp}" for imp in HIDDEN_IMPORTS])
    
    if os_type == "linux":
        output_name = name
        command = f"pyinstaller --onefile {hidden_imports} {entry_point} --name {output_name}"
    elif os_type == "windows":
        output_name = f"{name}.exe"
        command = f"pyinstaller --onefile {hidden_imports} {entry_point} --name {output_name}"
    else:
        raise ValueError(f"Unsupported OS type: {os_type}")
    
    print(f"Building {name} for {os_type}...")
    run_command(command)

def build_all():
    """Build all services for the current OS, and for Windows if on Linux with Wine."""
    current_os = platform.system().lower()
    print(f"Detected OS: {current_os}")
    
    for service in SERVICES:
        if current_os == "linux":
            # Build for Linux
            build_service(service, "linux")
            # If Wine is available, build for Windows
            if WINE_PATH:
                print(f"Wine detected at {WINE_PATH}, building Windows executable...")
                wine_command = f"{WINE_PATH} pyinstaller --onefile {hidden_imports} {entry_point} --name {name}.exe"
                run_command(wine_command)
            else:
                print("Wine not found, skipping Windows build.")
        elif current_os == "windows":
            # Build for Windows
            build_service(service, "windows")
        else:
            print(f"Unsupported OS: {current_os}")
            return

if __name__ == "__main__":
    build_all()
"""
1. Service List:
- Define the services to build in the SERVICES list. Each service has:
    +A name (e.g., bot_service).
    + An entry_point (e.g., bot_service/main.py).
- Add more services as needed by extending this list.
2. Hidden Imports:
- Specify libraries that PyInstaller might not detect automatically (e.g., telethon, sqlalchemy) in the HIDDEN_IMPORTS list.
3. OS Detection:
- Use platform.system() to detect whether the script is running on Linux or Windows.
4. Build Logic:
- For each service, build the appropriate executable:
    + On Linux: Build an ELF binary.
    + On Windows: Build a .exe file.
- If running on Linux and Wine is installed, also build Windows executables using Wine.
5. Command Execution:
- Use subprocess.check_call to run PyInstaller commands and capture output.
6. Error Handling:
- Catch and log any errors during the build process.
"""

"""
1. Run the Script:
- From your project root, execute:
```bash
python build_all.py
```
2. Build Output:
- The executables will be generated in the dist/ directory:
    + For Linux builds: ELF binaries (e.g., bot_service).
    + For Windows builds: .exe files (e.g., bot_service.exe).
3. Cross-Platform Builds:
- On Linux:
    + Both Linux and Windows executables will be built if Wine is installed.
- On Windows:
    Only Windows executables will be built.
"""