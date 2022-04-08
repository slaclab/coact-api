# new-iris
SLAC's Scientific User and Resource Management System

## initialisation

check out code

    git clone https://github.com/slaclab/new-iris.git

create a new virtual env with

    virtualenv new-iris
    new-iris/bin/pip install -r new-iris/requirements.txt
    cd new-iris

install mongo and start it with

    mkdir mongodb
    mongod --config mongod.conf

then initiate the uvicorn server with

    ./bin/uvicorn main:app  --reload
    
## testing

you can then go to http://localhost:8000/graphql to test the graphql interface and issue queries etc.