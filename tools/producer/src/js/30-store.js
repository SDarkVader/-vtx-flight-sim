// =====================================================================================
// LIBRARY STORE: songs and takes kept in this browser (IndexedDB), only if you ask. Nothing leaves the device.
// =====================================================================================
const paths = new WeakMap();
const where = f => paths.get(f) || f.webkitRelativePath || f.name;
function idb() {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open('vtx-sound-studio-2', 1);
    open.onupgradeneeded = () => { open.result.createObjectStore('files'); open.result.createObjectStore('folders', { autoIncrement: true }); };
    open.onerror = () => reject(open.error);
    open.onsuccess = () => resolve(open.result);
  });
}
function tx(storeName, mode, work) {
  return idb().then(db => new Promise((resolve, reject) => {
    const t = db.transaction(storeName, mode), req = work(t.objectStore(storeName));
    t.oncomplete = () => { db.close(); resolve(req?.result); };
    t.onerror = t.onabort = () => { db.close(); reject(t.error); };
  }));
}
const kindRange = kind => IDBKeyRange.bound(kind + '|', kind + '|￿');
const lib = {
  put: (kind, file) => tx('files', 'readwrite', s => s.put({ kind, name: file.name, path: where(file), type: file.type, blob: file }, kind + '|' + where(file))),
  all: async kind => (await tx('files', 'readonly', s => s.getAll(kindRange(kind)))).map(r => {
    const file = new File([r.blob], r.name, { type: r.type || r.blob.type });
    paths.set(file, r.path || r.name);
    return file;
  }),
  remove: (kind, file) => tx('files', 'readwrite', s => s.delete(kind + '|' + where(file))),
  clear: kind => tx('files', 'readwrite', s => s.delete(kindRange(kind))),
  usage: async () => { try { const e = await navigator.storage.estimate(); return e.usage || 0; } catch { return null; } },
};
async function keepPersistent() { try { await navigator.storage?.persist?.(); } catch {} }
