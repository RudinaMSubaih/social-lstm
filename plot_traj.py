'''
Draw the full trajectory (x,y) for each pedestrian at all the time frames
@Rudina Subaih
'''
from numpy import *
import numpy as np
import os, sys, glob, math
import argparse
import matplotlib.pyplot as plt


def getParserArgs():
    parser = argparse.ArgumentParser(description='Plot trajectory')
    parser.add_argument("-p", "--path", default="./", help='give the path of source file')
    parser.add_argument("-m", "--measurement", default="m", type=str, help='x,y,z data in: m, c')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = getParserArgs()
    path = args.path
    measurement = args.measurement
    figname = "x_y_%s_traj" % (os.path.basename(os.path.splitext(path)[0]))

    plt.rc('xtick', labelsize=25)
    plt.rc('ytick', labelsize=25)
    plt.rc("font", size=30)
    plt.rc('pdf', fonttype=42)
    fig = plt.figure(figsize=(16, 16), dpi=100)

    '''
    The organisation of data in the files is different: public data (fr,pedID,x,y), crossing data (pedID,fr,x,y,z)
    '''
    data = loadtxt(path, usecols=(0, 1, 2, 3))
    if measurement == "m":
        plt.plot(data[:, 2], data[:, 3], 'bo')
    else:
        plt.plot(data[:, 2] / 100, data[:, 3] / 100, 'bo')

    plt.xlabel("x [$m$]", size=25)
    plt.ylabel("y [$m$]", size=25)
    plt.savefig("%s/%s" % ("./", figname))
    plt.close()
