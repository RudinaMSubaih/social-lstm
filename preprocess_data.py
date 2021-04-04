"""
Rudina:
This script to change the .txt data files structure of the Herms and BaSiGo data to similar structure as the data used by Social-LSTN paper
"""

import argparse
import os

import numpy as np


def getParserArgs():
    parser = argparse.ArgumentParser(description='Plot trajectory')
    parser.add_argument("--path", default="./",
                        help='enter the path of the data file you want to preprocess')
    parser.add_argument('--seq_length', type=int, default=20,
                        help='RNN sequence length')
    # Length of the prediction result
    parser.add_argument('--pred_length', type=int, default=12,
                        help='prediction length')
    args = parser.parse_args()
    return args

def preprocess_dataset_file():
    args= getParserArgs()
    path = args.path
    seq_length= args.seq_length
    pred_length= args.pred_length

    data= np.loadtxt(path, usecols=(0, 1, 2, 3))
    ped_ids= np.unique(data[:, 1])

    for id in ped_ids:
        arr = np.where(data[1] == id)
        print(arr)
        exit()
    print(ped_ids)
    exit()

if __name__ == '__main__':
    preprocess_dataset_file()

    # args = getParserArgs()
    # path = args.path
    #
    # # To find out the number of usable CPUs:
    # print(len(os.sched_getaffinity(0)))
    # new_matrix = np.loadtxt(path, usecols=(1, 0, 3, 2))
    # # ['frame_num','ped_id','y','x']
    #
    # fname = os.path.splitext(os.path.abspath(path))[0] + "_pre.txt"
    # np.savetxt(fname, new_matrix, delimiter='\t', comments='', newline='\r\n', fmt='%d\t%d\t%.4f\t%.4f')

    # args = getParserArgs()
    # path = args.path
    #
    # new_matrix = np.loadtxt(path, usecols=(1, 0, 3, 2))
    # new_matrix[:,2] /= 100.0
    # new_matrix[:, 3] /= 100.0
    # # ['frame_num','ped_id','y','x']
    #
    # np.savetxt(path, new_matrix, delimiter=' ', comments='', newline='\r\n', fmt='%d\t%d\t%.4f\t%.4f')

