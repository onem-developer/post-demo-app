try:
    from .local import *
except ImportError:
    print('You need to create a local.py file. local_example.py is provided as an example')
