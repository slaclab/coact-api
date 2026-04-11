#!/bin/bash
# Restores the first *.mongodump archive found in /dump, if any.
# Place dump files in ./mongo-seed/ on the host (gitignored).
shopt -s nullglob
dumps=(/dump/*.mongodump)
if [ ${#dumps[@]} -eq 0 ]; then
  echo "No dump files found in /dump, skipping restore."
  return 0
fi
echo "Restoring from ${dumps[0]}"
mongorestore --archive="${dumps[0]}"
