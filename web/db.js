// 図鑑（ideas）と探究のランキング（records）を IndexedDB に保存する
let dbName = "platon-eye";
let dbPromise = null;

export function useDbName(name) {
  dbName = name;
  dbPromise = null;
}

function open() {
  dbPromise ??= new Promise((resolve, reject) => {
    const req = indexedDB.open(dbName, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      db.createObjectStore("ideas", { keyPath: "id", autoIncrement: true });
      db.createObjectStore("records", { keyPath: "id", autoIncrement: true }).createIndex("word", "word");
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}

async function run(store, mode, fn) {
  const db = await open();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, mode);
    let result;
    const req = fn(tx.objectStore(store));
    if (req) req.onsuccess = () => { result = req.result; };
    tx.oncomplete = () => resolve(result);
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

// ---------------------------------------------------------------- 図鑑
export const addIdea = (rec) => run("ideas", "readwrite", (s) => s.add({ createdAt: Date.now(), ...rec }));
export const getIdea = (id) => run("ideas", "readonly", (s) => s.get(id));
export const deleteIdea = (id) => run("ideas", "readwrite", (s) => s.delete(id));
export const clearIdeas = () => run("ideas", "readwrite", (s) => s.clear());
export async function listIdeas() {
  const all = await run("ideas", "readonly", (s) => s.getAll());
  return all.sort((a, b) => b.createdAt - a.createdAt || b.id - a.id);
}

// ---------------------------------------------------------------- ランキング
export const addRecord = (rec) => run("records", "readwrite", (s) => s.add({ createdAt: Date.now(), ...rec }));
export const clearRecords = () => run("records", "readwrite", (s) => s.clear());

async function ranked(word) {
  const all = await run("records", "readonly", (s) => s.index("word").getAll(word));
  return all.sort((a, b) => a.seconds - b.seconds || a.id - b.id);
}

export async function topRecords(word, n = 5) {
  return (await ranked(word)).slice(0, n);
}

export async function rankOf(word, id) {
  return (await ranked(word)).findIndex((r) => r.id === id) + 1;
}
