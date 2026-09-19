
def clear_all_storage(driver):

    # Chrome-level
    driver.execute_cdp_cmd("Network.clearBrowserCookies", {})
    driver.execute_cdp_cmd("Network.clearBrowserCache", {})

    # Origin-level
    driver.execute_async_script("""
    const callback = arguments[arguments.length - 1];

    (async () => {

        const result = {};

        //
        // localStorage
        //
        try {
            localStorage.clear();
            result.localStorage = true;
        } catch (e) {
            result.localStorage = String(e);
        }

        //
        // sessionStorage
        //
        try {
            sessionStorage.clear();
            result.sessionStorage = true;
        } catch (e) {
            result.sessionStorage = String(e);
        }

        //
        // IndexedDB
        //
        try {

            const dbs = await indexedDB.databases();

            for (const db of dbs) {

                await new Promise(resolve => {

                    const req = indexedDB.deleteDatabase(db.name);

                    req.onsuccess = () => resolve();
                    req.onerror = () => resolve();
                    req.onblocked = () => resolve();
                });
            }

            result.indexedDB = true;

        } catch (e) {

            result.indexedDB = String(e);
        }

        //
        // Cache Storage
        //
        try {

            const names = await caches.keys();

            await Promise.all(
                names.map(name => caches.delete(name))
            );

            result.cacheStorage = true;

        } catch (e) {

            result.cacheStorage = String(e);
        }

        //
        // Service Workers
        //
        try {

            const regs = await navigator.serviceWorker.getRegistrations();

            await Promise.all(
                regs.map(r => r.unregister())
            );

            result.serviceWorkers = true;

        } catch (e) {

            result.serviceWorkers = String(e);
        }

        //
        // Shared Storage
        //
        try {

            if (window.sharedStorage) {

                // enumeration blocked by design
                // clear() not universally supported

                if (window.sharedStorage.clear) {
                    await window.sharedStorage.clear();
                }

                result.sharedStorage = true;

            } else {

                result.sharedStorage = "not_supported";
            }

        } catch (e) {

            result.sharedStorage = String(e);
        }

        //
        // OPFS
        //
        try {

            if (navigator.storage && navigator.storage.getDirectory) {

                const root = await navigator.storage.getDirectory();

                async function removeRecursive(dirHandle) {

                    for await (const [name, handle] of dirHandle.entries()) {

                        await dirHandle.removeEntry(
                            name,
                            { recursive: true }
                        );
                    }
                }

                await removeRecursive(root);

                result.opfs = true;

            } else {

                result.opfs = "not_supported";
            }

        } catch (e) {

            result.opfs = String(e);
        }

        callback(result);

    })();
    """)




def getLocalStorage(driver):
    try:
        local_storage = driver.execute_script("""
                                        let out = {};
                                        for (let i = 0; i < localStorage.length; i++) {
                                          let k = localStorage.key(i);
                                          out[k] = localStorage.getItem(k);
                                        }
                                        return out;
                                        """)
    except:
        local_storage = {}
    return local_storage

def getSessionStorage(driver):
    try:
        session_storage = driver.execute_script("""
                                        let out = {};
                                        for (let i = 0; i < sessionStorage.length; i++) {
                                          let k = sessionStorage.key(i);
                                          out[k] = sessionStorage.getItem(k);
                                        }
                                        return out;
                                        """)
    except:
        session_storage = {}
    return session_storage