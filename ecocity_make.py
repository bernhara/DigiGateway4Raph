#!/usr/bin/python2.4

# calls the DIA provided make.py with the projet specific os.path

from make import *
from EcocityDiaGW import include_project_runtime_path_elements 

DEFAULT_SOURCE = 'EcocityDiaGW.py'

include_project_runtime_path_elements ()

# remove and accidental element containing "crossdev_src" 
crossedev_src_path_elements = [x for x in sys.path if "crossdev_src" in x]
for element in crossedev_src_path_elements:
    sys.path.remove (element)
    
# call DIA provided make
if __name__ == "__main__":
    main()
