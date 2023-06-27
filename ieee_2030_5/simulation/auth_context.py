import os

gridappsd_user = os.environ.get("GRIDAPPSD_USER", "system")
gridappsd_password = os.environ.get("GRIDAPPSD_PASSWORD", "manager")
gridappsd_address = os.environ.get("GRIDAPPSD_ADDRESS", "gridappsd")
gridappsd_port = os.environ.get("GRIDAPPSD_PORT", "61613")

os.environ['GRIDAPPSD_USER'] = gridappsd_user
os.environ['GRIDAPPSD_PASSWORD'] = gridappsd_password
os.environ['GRIDAPPSD_ADDRESS'] = gridappsd_address
os.environ['GRIDAPPSD_PORT'] = gridappsd_port
