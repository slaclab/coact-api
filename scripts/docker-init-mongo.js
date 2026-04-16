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

// Run core scripts (indexes, but skip bootstrap for development)
run(SCRIPTS_DIR + "/00-indexes.mongodb");

// Run all migrations
runDir(SCRIPTS_DIR + "/migration");

// Run development test data
runDir(SCRIPTS_DIR + "/dev");

// Run one facility for integration tests
run(SCRIPTS_DIR + "/20-facility-lcls.mongodb");

print("Database initialization complete.");
