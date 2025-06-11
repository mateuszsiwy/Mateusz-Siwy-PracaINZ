import os

_ROOT = os.path.abspath(os.path.dirname(__file__))

def get_example_data_file(path):
    return os.path.join(_ROOT, path)

def get_example_data_dir():
    return _ROOT

# from data import get_example_data as get_data

