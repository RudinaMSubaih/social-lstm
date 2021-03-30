"""
Draw the individual rho_vel relationship
@Rudina Subaih
"""
import argparse
import os

import matplotlib.pyplot as plt
from numpy import *


def getParserArgs():
    parser = argparse.ArgumentParser(description='Plot trajectory')
    parser.add_argument("-p", "--path", default="./", help='give the path of source file')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = getParserArgs()
    path = args.path
    figname = "x_y_%s_rho_v" % (os.path.basename(os.path.splitext(path)[0]))

    plt.rc('xtick', labelsize=25)
    plt.rc('ytick', labelsize=25)
    plt.rc("font", size=30)
    plt.rc('pdf', fonttype=42)
    fig = plt.figure(figsize=(16, 16), dpi=100)

    data = loadtxt(path, usecols=(0, 1, 2, 3, 4, 5, 6))
    plt.plot(data[:, 5], data[:, 6], 'bo')

    plt.xlabel("density [$m^{-2}$]", size=25)
    plt.ylabel("velocity [$m/s$]", size=25)
    plt.savefig("%s/%s" % ("./", figname))
    plt.close()
