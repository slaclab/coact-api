use admin;
db.createUser({ user: "coact", roles: [ { db: "iris", role: "readWrite" } ], pwd: passwordPrompt() });
