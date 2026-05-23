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
    try {
        if (!fs.existsSync(dir)) {
            print("Directory " + dir + " does not exist, skipping...");
            return;
        }
        fs.readdirSync(dir)
            .filter(f => /^\d+.*\.mongodb?$/.test(f))
            .sort()
            .forEach(f => run(dir + "/" + f));
    } catch (e) {
        print("WARNING: Failed to read directory " + dir + ": " + e);
    }
}

// Run core scripts (indexes, but skip bootstrap for development)
run(SCRIPTS_DIR + "/00-indexes.mongodb");

// Run all migrations
runDir(SCRIPTS_DIR + "/migration");

// Development test data is copied directly to scripts/ by the Dockerfile
// Check for dev scripts by filename pattern (00-test-users.mongodb, etc.)
print("Looking for dev test data files...");
try {
    const allFiles = fs.readdirSync(SCRIPTS_DIR);
    const devFiles = allFiles.filter(f => f.includes("test-users") || f.startsWith("00-") && f !== "00-indexes.mongodb");
    if (devFiles.length > 0) {
        print("Found dev files: " + devFiles.join(", "));
        devFiles.sort().forEach(f => run(SCRIPTS_DIR + "/" + f));
    } else {
        print("No dev test files found");
    }
} catch (e) {
    print("WARNING: Failed to scan for dev files: " + e);
}

// Run one facility for integration tests
run(SCRIPTS_DIR + "/20-facility-lcls.mongodb");

print("Database initialization complete.");
