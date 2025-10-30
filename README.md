Initialize:
- `cd ${THIS_FOLDER}`
- `python3 -m venv .venv`
- `source .venv/bin/activate`
- `pip3 install -r requirements.txt`

Test
- `export PYTHONPATH=$PYTHONPATH:$(pwd)/src`
- `python3 -m pytest test`