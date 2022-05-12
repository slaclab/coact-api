
db.createUser({ user: "coact", roles: [ { db: "iris", role: "readWrite" } ], mechanisms: [ "SCRAM-SHA-1" ] });
