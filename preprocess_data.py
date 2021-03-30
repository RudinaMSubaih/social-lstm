"""
Rudina:
This script to change the .txt data files structure of the Herms and BaSiGo data to similar structure as the data used by Social-LSTN paper
"""

import argparse
import os

import numpy as np


def getParserArgs():
    parser = argparse.ArgumentParser(description='Plot trajectory')
    parser.add_argument("-p", "--path", default="./", help='enter the path of the data file you want to preprocess')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = getParserArgs()
    path = args.path

    # To find out the number of usable CPUs:
    print(len(os.sched_getaffinity(0)))
    new_matrix = np.loadtxt(path, usecols=(1, 0, 3, 2))
    # ['frame_num','ped_id','y','x']

    fname = os.path.splitext(os.path.abspath(path))[0] + "_pre.txt"
    np.savetxt(fname, new_matrix, delimiter='\t', comments='', newline='\r\n', fmt='%d\t%d\t%.4f\t%.4f')
