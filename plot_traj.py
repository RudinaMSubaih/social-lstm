'''
Draw the full trajectory (x,y) for each pedestrian at all the time frames
'''
from numpy import *
import numpy as np
import os, sys, glob, math
import argparse
import matplotlib.pyplot as plt

def getParserArgs():
    parser = argparse.ArgumentParser(description='Plot trajectory')
    parser.add_argument("-p", "--path", default="./", help='give the path of source file')
    parser.add_argument("-f", "--fps", default="25", type=float, help='give the frame rate of data')
    parser.add_argument("-t", "--type", default="cross", type=str, help='Type of the data: pub, cross')
    args = parser.parse_args()
    return args

if __name__ == '__main__':
    args = getParserArgs()
    path = args.path
    fps = args.fps
    type = args.type
    figname = "rho_v_%s_traj" % (os.path.basename(os.path.splitext(path)[0]))

    plt.rc('xtick', labelsize=25)
    plt.rc('ytick', labelsize=25)
    plt.rc("font", size=30)
    plt.rc('pdf', fonttype=42)
    fig = plt.figure(figsize=(16, 16), dpi=100)

    if type == "pub":
        data=loadtxt(path,usecols = (0,1,2,3))
        plt.plot(data[:,2],data[:,3])
        #plt.axvline(x=-2.5,linestyle="-",linewidth=1,color="r")
    else:
        data = loadtxt(path, usecols=(0, 1, 2, 3, 4))
        plt.plot(data[:, 2], data[:, 3])
        # plt.axvline(x=-2.5,linestyle="-",linewidth=1,color="r")

    plt.xlabel("x [$m$]", size=25)
    plt.ylabel("y [$m$]", size=25)
    plt.savefig("%s/%s" % ("./", figname))
    plt.close()
