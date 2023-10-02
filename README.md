# new-iris
SLAC's Scientific User and Resource Management System

## initialisation

check out code

    git clone https://github.com/slaclab/new-iris.git

option 1) create a new virtual env with

    virtualenv new-iris
    new-iris/bin/pip install -r new-iris/requirements.txt
    cd new-iris

option 2) create a new conda environment

    sh Miniconda3-latest-Linux-x86_64.sh -f -p new-iris/
    cd new-iris
    ./bin/pip -r requirements.txt

install mongo 

option 1) via conda with:

     ./bin/conda install mongodb

option 2) via yum etc.

and start it with

    mkdir mongodb
    ./bin/mongod --config mongod.conf

then initiate the uvicorn server with

    ./bin/uvicorn main:app  --reload
    
## testing

you can then go to http://localhost:8000/graphql to test the graphql interface and issue queries etc.
