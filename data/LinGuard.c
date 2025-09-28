#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#include <process.h>
#include <tlhelp32.h>
#else
#include <sys/types.h>
#include <sys/stat.h>
#include <signal.h>
#include <sys/wait.h>
#include <dirent.h>
#endif

const char* detect_environment() {
    #ifdef _WIN32
    return "windows";
    #else
    if (access("/data/data/com.termux/files/usr/bin/node", F_OK) == 0) {
        return "termux";
    }
    if (access("/data/data/com.termux", F_OK) == 0) {
        return "termux";
    }
    return "linux";
    #endif
}

#ifdef _WIN32
int get_current_pid() {
    return (int)GetCurrentProcessId();
}

int find_linguard_processes(int *pids, int max_pids) {
    HANDLE hSnapshot;
    PROCESSENTRY32 pe32;
    int count = 0;
    int current_pid = get_current_pid();
    hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnapshot == INVALID_HANDLE_VALUE) return 0;
    pe32.dwSize = sizeof(PROCESSENTRY32);
    if (Process32First(hSnapshot, &pe32)) {
        do {
            if ((strcmp(pe32.szExeFile, "LinGuard.exe") == 0 || 
                strstr(pe32.szExeFile, "LinGuard") != NULL) &&
                pe32.th32ProcessID != current_pid) {
                if (count < max_pids) {
                    pids[count++] = pe32.th32ProcessID;
                }
            }
        } while (Process32Next(hSnapshot, &pe32));
    }
    CloseHandle(hSnapshot);
    return count;
}

int find_node_processes(int *pids, int max_pids) {
    HANDLE hSnapshot;
    PROCESSENTRY32 pe32;
    int count = 0;
    hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnapshot == INVALID_HANDLE_VALUE) return 0;
    pe32.dwSize = sizeof(PROCESSENTRY32);
    if (Process32First(hSnapshot, &pe32)) {
        do {
            if (strcmp(pe32.szExeFile, "node.exe") == 0) {
                if (count < max_pids) {
                    pids[count++] = pe32.th32ProcessID;
                }
            }
        } while (Process32Next(hSnapshot, &pe32));
    }
    CloseHandle(hSnapshot);
    return count;
}
#else
int get_current_pid() {
    return (int)getpid();
}

int find_linguard_processes(int *pids, int max_pids) {
    DIR *dir;
    struct dirent *entry;
    char path[512];
    char cmdline[1024];
    FILE *fp;
    int count = 0;
    int current_pid = get_current_pid();
    dir = opendir("/proc");
    if (!dir) return 0;
    while ((entry = readdir(dir)) != NULL && count < max_pids) {
        if (entry->d_type == DT_DIR) {
            char *endptr;
            long pid = strtol(entry->d_name, &endptr, 10);
            if (*endptr == '\0' && pid != current_pid) {
                snprintf(path, sizeof(path), "/proc/%ld/cmdline", pid);
                fp = fopen(path, "r");
                if (fp) {
                    if (fgets(cmdline, sizeof(cmdline), fp) != NULL) {
                        if (strstr(cmdline, "LinGuard") != NULL) {
                            pids[count++] = (int)pid;
                        }
                    }
                    fclose(fp);
                }
            }
        }
    }
    closedir(dir);
    return count;
}

int find_node_processes(int *pids, int max_pids) {
    DIR *dir;
    struct dirent *entry;
    char path[512];
    char cmdline[1024];
    char exe_path[512];
    FILE *fp;
    int count = 0;
    dir = opendir("/proc");
    if (!dir) return 0;
    while ((entry = readdir(dir)) != NULL && count < max_pids) {
        if (entry->d_type == DT_DIR) {
            char *endptr;
            long pid = strtol(entry->d_name, &endptr, 10);
            if (*endptr == '\0') {
                snprintf(path, sizeof(path), "/proc/%ld/cmdline", pid);
                fp = fopen(path, "r");
                if (fp) {
                    if (fgets(cmdline, sizeof(cmdline), fp) != NULL) {
                        if (strstr(cmdline, "node") != NULL && strstr(cmdline, "run") != NULL) {
                            pids[count++] = (int)pid;
                        }
                    }
                    fclose(fp);
                }
            }
        }
    }
    closedir(dir);
    return count;
}
#endif

int check_existing_processes() {
    int linguard_pids[20];
    int node_pids[20];
    int linguard_count, node_count;
    linguard_count = find_linguard_processes(linguard_pids, 20);
    if (linguard_count > 0) {
        return 1;
    }
    node_count = find_node_processes(node_pids, 20);
    if (node_count > 0) {
        return 2;
    }
    return 0;
}

int is_already_running() {
    const char* env = detect_environment();
    char pid_file[256];
    if (strcmp(env, "windows") == 0) {
        sprintf(pid_file, "C:\\Windows\\Temp\\linguard.pid");
    } else {
        sprintf(pid_file, "/tmp/linguard.pid");
    }
    FILE *file = fopen(pid_file, "r");
    if (file) {
        int pid;
        if (fscanf(file, "%d", &pid) == 1) {
            fclose(file);
            #ifdef _WIN32
            HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION, FALSE, pid);
            if (hProcess != NULL) {
                DWORD exitCode;
                if (GetExitCodeProcess(hProcess, &exitCode)) {
                    if (exitCode == STILL_ACTIVE) {
                        CloseHandle(hProcess);
                        return 1;
                    }
                }
                CloseHandle(hProcess);
            }
            #else
            if (kill(pid, 0) == 0) {
                return 1;
            }
            #endif
        } else {
            fclose(file);
        }
    }
    file = fopen(pid_file, "w");
    if (file) {
        fprintf(file, "%d", get_current_pid());
        fclose(file);
        return 0;
    }
    return 0;
}

void cleanup() {
    const char* env = detect_environment();
    char pid_file[256];
    if (strcmp(env, "windows") == 0) {
        sprintf(pid_file, "C:\\Windows\\Temp\\linguard.pid");
    } else {
        sprintf(pid_file, "/tmp/linguard.pid");
    }
    remove(pid_file);
}

void run_node_directly() {
    const char* env = detect_environment();
    #ifdef _WIN32
    STARTUPINFO si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;
    if (CreateProcess(NULL, "node run", NULL, NULL, FALSE, 
                     CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
        WaitForSingleObject(pi.hProcess, INFINITE);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
    }
    #else
    pid_t pid = fork();
    if (pid == 0) {
        setsid();
        freopen("/dev/null", "r", stdin);
        freopen("/dev/null", "w", stdout);
        freopen("/dev/null", "w", stderr);
        if (strcmp(env, "termux") == 0) {
            chdir("/data/data/com.termux/files/usr/bin");
        } else {
            chdir("/usr/bin");
        }
        execlp("node", "node", "run", NULL);
        exit(1);
    } else if (pid > 0) {
        int status;
        waitpid(pid, &status, 0);
    }
    #endif
}

void signal_handler(int sig) {
    cleanup();
    exit(0);
}

int main() {
    int check_result = check_existing_processes();
    if (check_result == 1) {
        exit(0);
    } else if (check_result == 2) {
        exit(0);
    }
    if (is_already_running()) {
        exit(0);
    }
    #ifndef _WIN32
    signal(SIGTERM, signal_handler);
    signal(SIGINT, signal_handler);
    signal(SIGHUP, signal_handler);
    #else
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    #endif
    #ifndef _WIN32
    pid_t pid = fork();
    if (pid > 0) {
        exit(0);
    }
    setsid();
    pid = fork();
    if (pid > 0) exit(0);
    freopen("/dev/null", "r", stdin);
    freopen("/dev/null", "w", stdout);
    freopen("/dev/null", "w", stderr);
    #else
    FreeConsole();
    #endif
    while (1) {
        if (check_existing_processes() != 0) {
            cleanup();
            exit(0);
        }
        run_node_directly();
        #ifdef _WIN32
        Sleep(5000);
        #else
        sleep(5);
        #endif
        if (check_existing_processes() != 0) {
            cleanup();
            exit(0);
        }
    }
    cleanup();
    return 0;
}
