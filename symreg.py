#!/usr/bin/env python3
import os
import gencpp

cpp = gencpp.gencpp()
with open('genpy.inc.cpp', 'w') as out:
    out.write(cpp)

os.system('clang++ genpy.cpp -o genpy')
os.system('./genpy')
