import os
import time
import psutil


def cleanup_driver(driver=None, timeout=5):
    """
    Cleanup Chrome / ChromeDriver processes belonging to current worker.

    Call this AFTER using the driver.

    It will:
      1. driver.quit()
      2. terminate remaining Chrome/ChromeDriver children
      3. kill processes that don't exit
      4. reap zombie children using waitpid()
      5. remove the copied chromedriver binary
    """

    my_pid = os.getpid()

    # ---------------------------------------------------------
    # 1. Normal Selenium cleanup
    # ---------------------------------------------------------
    if driver is not None:
        try:
            #print("[CLEANUP] Calling driver.quit()", flush=True)
            driver.quit()
        except Exception as e:
            pass
            #print(f"[CLEANUP] driver.quit() error: {e}", flush=True)

    # Give ChromeDriver a short time to exit normally
    time.sleep(1)

    # ---------------------------------------------------------
    # 2. Find Chrome / ChromeDriver children
    # ---------------------------------------------------------
    def get_driver_children():
        try:
            parent = psutil.Process(my_pid)

            result = []

            for p in parent.children(recursive=True):
                try:
                    cmdline = p.cmdline()
                    cmd = " ".join(cmdline).lower()

                    name = (p.name() or "").lower()

                    if (
                        "chromedriver" in name
                        or "chromedriver" in cmd
                        or name == "chrome"
                        or "/chrome" in cmd
                    ):
                        result.append(p)

                except (psutil.NoSuchProcess,psutil.AccessDenied,):
                    pass

            return result

        except (psutil.NoSuchProcess,psutil.AccessDenied,):
            return []

    # ---------------------------------------------------------
    # 3. Terminate living Chrome/ChromeDriver processes
    # ---------------------------------------------------------
    children = get_driver_children()

    for p in children:
        try:
            if p.status() == psutil.STATUS_ZOMBIE:
                continue
            #print(f"[CLEANUP] terminate PID={p.pid} PPID={p.ppid()} CMD={' '.join(p.cmdline())}",flush=True,)

            p.terminate()

        except (psutil.NoSuchProcess,psutil.AccessDenied,):
            pass

    # ---------------------------------------------------------
    # 4. Wait for graceful termination
    # ---------------------------------------------------------
    if children:
        _, alive = psutil.wait_procs(
            children,
            timeout=timeout,
        )
    else:
        alive = []

    # ---------------------------------------------------------
    # 5. Force kill anything still alive
    # ---------------------------------------------------------
    for p in alive:
        try:
            if p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
                #print(f"[CLEANUP] kill PID={p.pid}", flush=True,)
                p.kill()

        except (psutil.NoSuchProcess,psutil.AccessDenied,):
            pass

    # ---------------------------------------------------------
    # 6. REAP zombie children
    # ---------------------------------------------------------
    #
    # IMPORTANT:
    # kill()/terminate() cannot remove a zombie.
    # Parent must call waitpid().
    #
    # ---------------------------------------------------------
    reaped = []

    while True:
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
            reaped.append(pid)
            # print(f"[CLEANUP] REAP PID={pid} status={status}",flush=True,)

        except ChildProcessError:
            break

        except OSError:
            break

    # ---------------------------------------------------------
    # 7. Verify remaining zombie children
    # ---------------------------------------------------------
    remaining_zombies = []

    try:
        parent = psutil.Process(my_pid)

        for p in parent.children(recursive=True):
            try:
                if p.status() == psutil.STATUS_ZOMBIE:
                    remaining_zombies.append(p.pid)

            except (psutil.NoSuchProcess,psutil.AccessDenied,):
                pass

    except (psutil.NoSuchProcess,psutil.AccessDenied,):
        pass

    # if remaining_zombies:
    #     print(f"[CLEANUP] WARNING: remaining zombies: {remaining_zombies}", flush=True,)
    # else:
    #     print(f"[CLEANUP] Chrome/ChromeDriver cleanup OK. Reaped={reaped}", flush=True, )
