// Bootstrap the iris database and run all migrations.
// Executed once by the MongoDB Docker entrypoint (mongosh) on first container start.

const SCRIPTS_DIR = "/docker-entrypoint-initdb.d/scripts";

function run(file) {
    print("Running " + file + " ...");
    try {
        load(file);
    } catch (e) {
        print("WARNING: " + file + " exited with errors (may be harmless duplicates): " + e);
    }
}

function runDir(dir) {
    fs.readdirSync(dir)
        .filter(f => /^\d+.*\.mongodb?$/.test(f))
        .sort()
        .forEach(f => run(dir + "/" + f));
}

runDir(SCRIPTS_DIR);
runDir(SCRIPTS_DIR + "/migration");

print("Database initialization complete.");
