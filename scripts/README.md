
install with

     pip3 install -r requirements

on a node with slurm installed, where your user has full admin permissiosn in slurm, run with

    python3 jobs2usage.py .

this will dump a json file with yesterdays date.

you can edit the json with jq:

    cat 20220628.json  | jq -c '.[] | select( .username == "ytl")' | jq '.accountName = "20191205-CS14"' | jq --slurp

    cat 20220628.json | jq 'map( if .username | test("ytl") then .accountName = "20191205-CA104" else . end)' | jq --slurp

in order to interact with coact, we first need to obtain an authentication token.

then we just need to load the file into coact (for now, we use a separate service to spit out the cookie, but we should integrate showign the cookie in the coact user home page)

goto https://echo-server.slac.stanford.edu/, under the cookies key, there will be a string that begins with 'slac-vouch=', copy and paste that value into an environment variable

    export VOUCH_COOKIE="H4sIAAAAAAAA_....."

can test with curl (note that -L is important, as is the name of the cookie)

    curl --cookie "slac-vouch=$VOUCH_COOKIE" https://coact-dev.slac.stanford.edu/graphql/ -vvv -L

if that reports back a bunch of javascript rather than redirecting to SAML for authentication (adfs) then you're good.


