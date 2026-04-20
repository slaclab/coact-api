# Wait for MongoDB to be ready and initialized
echo "Waiting for MongoDB initialization..."
timeout 120 bash -c '
until docker exec mongodb-test mongosh iris --eval "
    try {
    const user = db.users.findOne({username: \"regular_user\"});
    const version = db.versions.findOne();
    if (user && version && version.dbschema) {
        print(\"✅ Database ready with version: \" + version.dbschema);
        quit(0);
    }
    quit(1);
    } catch(e) {
    print(\"⏳ Still initializing...\");
    quit(1);
    }
" --quiet 2>/dev/null
do
    sleep 3
done
'