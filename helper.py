"""
Python script includes various helper methods
"""
import math
import os
import shutil
from os import walk

import numpy as np
import torch
from torch.autograd import Variable

from vlstm_model import VLSTMModel


class WriteOnceDict(dict):
    """
    One time set dictionary for a exist key
    """

    def __setitem__(self, key, value):
        if not key in self:
            super(WriteOnceDict, self).__setitem__(key, value)


# (1 = social lstm, 2 = obstacle lstm, 3 = vanilla lstm)
def get_method_name(index):
    """
    Return method name given index
    :param index:
    :return:
    """
    return {
        1: 'SOCIALLSTM',
        2: 'OBSTACLELSTM',
        3: 'VANILLALSTM'
    }.get(index, 'SOCIALLSTM')


def get_model(index, arguments, infer=False):
    """
    Return a model given index and arguments
    :param index:
    :param arguments:
    :param infer:
    :return:
    """
    if index == 3:
        return VLSTMModel(arguments, infer)



def getCoef(outputs):
    """
    Extracts the mean, standard deviation and correlation
    :param outputs: Output of the SRNN model
    :return:
    """
    mux, muy, sx, sy, corr = outputs[:, :, 0], outputs[:, :, 1], outputs[:, :, 2], outputs[:, :, 3], outputs[:, :, 4]

    sx = torch.exp(sx)
    sy = torch.exp(sy)
    corr = torch.tanh(corr)
    return mux, muy, sx, sy, corr


def sample_gaussian_2d(mux, muy, sx, sy, corr, nodesPresent, look_up):
    """
    mux, muy, sx, sy, corr : a tensor of shape 1 x numNodes
    Contains x-means, y-means, x-stds, y-stds and correlation
    :param mux:
    :param muy:
    :param sx:
    :param sy:
    :param corr: a tensor of shape 1 x numNodes
    :param nodesPresent: a list of nodeIDs present in the frame
    :param look_up: lookup table for determining which ped is in which array index
    :return:
        next_x, next_y : a tensor of shape numNodes
        Contains sampled values from the 2D gaussian
    """
    o_mux, o_muy, o_sx, o_sy, o_corr = mux[0, :], muy[0, :], sx[0, :], sy[0, :], corr[0, :]

    numNodes = mux.size()[1]
    next_x = torch.zeros(numNodes)
    next_y = torch.zeros(numNodes)
    converted_node_present = [look_up[node] for node in nodesPresent]
    for node in range(numNodes):
        if node not in converted_node_present:
            continue
        mean = [o_mux[node], o_muy[node]]
        cov = [[o_sx[node] * o_sx[node], o_corr[node] * o_sx[node] * o_sy[node]],
               [o_corr[node] * o_sx[node] * o_sy[node], o_sy[node] * o_sy[node]]]

        mean = np.array(mean, dtype='float')
        cov = np.array(cov, dtype='float')
        next_values = np.random.multivariate_normal(mean, cov, 1)
        next_x[node] = next_values[0][0]
        next_y[node] = next_values[0][1]

    return next_x, next_y


# Average displacement error
def get_mean_error(ret_nodes, nodes, assumedNodesPresent, trueNodesPresent, using_cuda, look_up):
    """

    :param ret_nodes: A tensor of shape pred_length x numNodes x 2. Contains the predicted positions for the nodes
    :param nodes: A tensor of shape pred_length x numNodes x 2. Contains the true positions for the nodes
    :param assumedNodesPresent:
    :param trueNodesPresent: A list of lists, of size pred_length. Each list contains the nodeIDs of the nodes present at that time-step
    :param using_cuda:
    :param look_up: lookup table for determining which ped is in which array index
    :return: Error; Mean euclidean distance between predicted trajectory and the true trajectory
    """

    pred_length = ret_nodes.size()[0]
    error = torch.zeros(pred_length)
    if using_cuda:
        error = error.cuda()

    for tstep in range(pred_length):
        counter = 0

        for nodeID in assumedNodesPresent[tstep]:
            nodeID = int(nodeID)

            if nodeID not in trueNodesPresent[tstep]:
                continue

            nodeID = look_up[nodeID]

            pred_pos = ret_nodes[tstep, nodeID, :]
            true_pos = nodes[tstep, nodeID, :]

            error[tstep] += torch.norm(pred_pos - true_pos, p=2)
            counter += 1

        if counter != 0:
            error[tstep] = error[tstep] / counter

    return torch.mean(error)


# Final displacement error
def get_final_error(ret_nodes, nodes, assumedNodesPresent, trueNodesPresent, look_up):
    """
    ret_nodes : A tensor of shape pred_length x numNodes x 2
    Contains the predicted positions for the nodes

    nodesPresent lists: A list of lists, of size pred_length
    Each list contains the nodeIDs of the nodes present at that time-step


    :param ret_nodes: A tensor of shape pred_length x numNodes x 2. Contains the predicted positions for the nodes
    :param nodes: A tensor of shape pred_length x numNodes x 2. Contains the true positions for the nodes
    :param assumedNodesPresent:
    :param trueNodesPresent:
    :param look_up: lookup table for determining which ped is in which array index
    :return: Error; Mean final euclidean distance between predicted trajectory and the true trajectory
    """

    pred_length = ret_nodes.size()[0]
    error = 0
    counter = 0

    # Last time-step
    tstep = pred_length - 1
    for nodeID in assumedNodesPresent[tstep]:
        nodeID = int(nodeID)

        if nodeID not in trueNodesPresent[tstep]:
            continue

        nodeID = look_up[nodeID]

        pred_pos = ret_nodes[tstep, nodeID, :]
        true_pos = nodes[tstep, nodeID, :]

        error += torch.norm(pred_pos - true_pos, p=2)
        counter += 1

    if counter != 0:
        error = error / counter

    return error


def Gaussian2DLikelihoodInference(outputs, targets, nodesPresent, pred_length, look_up):
    """
    Computes the likelihood of predicted locations under a bivariate Gaussian distribution at test time
    :param outputs: Torch variable containing tensor of shape seq_length x numNodes x 1 x output_size
    :param targets: Torch variable containing tensor of shape seq_length x numNodes x 1 x input_size
    :param nodesPresent: A list of lists, of size seq_length. Each list contains the nodeIDs that are present in the frame
    :param pred_length:
    :param look_up:
    :return:
    """

    seq_length = outputs.size()[0]
    obs_length = seq_length - pred_length

    # Extract mean, std devs and correlation
    mux, muy, sx, sy, corr = getCoef(outputs)

    # Compute factors
    normx = targets[:, :, 0] - mux
    normy = targets[:, :, 1] - muy
    sxsy = sx * sy

    z = (normx / sx) ** 2 + (normy / sy) ** 2 - 2 * ((corr * normx * normy) / sxsy)
    negRho = 1 - corr ** 2

    # Numerator
    result = torch.exp(-z / (2 * negRho))
    # Normalization factor
    denom = 2 * np.pi * (sxsy * torch.sqrt(negRho))

    # Final PDF calculation
    result = result / denom

    # Numerical stability
    epsilon = 1e-20

    result = -torch.log(torch.clamp(result, min=epsilon))
    # print(result)

    loss = 0
    counter = 0

    for framenum in range(obs_length, seq_length):
        nodeIDs = nodesPresent[framenum]
        nodeIDs = [int(nodeID) for nodeID in nodeIDs]

        for nodeID in nodeIDs:
            nodeID = look_up[nodeID]
            loss = loss + result[framenum, nodeID]
            counter = counter + 1

    if counter != 0:
        return loss / counter
    else:
        return loss


def Gaussian2DLikelihood(outputs, targets, nodesPresent, look_up):
    """
    assumedNodesPresent : Nodes assumed to be present in each frame in the sequence
    :param outputs: predicted locations
    :param targets: true locations
    :param nodesPresent: True nodes present in each frame in the sequence
    :param look_up: lookup table for determining which ped is in which array index
    :return:
    """

    seq_length = outputs.size()[0]
    # Extract mean, std devs and correlation
    mux, muy, sx, sy, corr = getCoef(outputs)

    # Compute factors
    normx = targets[:, :, 0] - mux
    normy = targets[:, :, 1] - muy
    sxsy = sx * sy

    z = (normx / sx) ** 2 + (normy / sy) ** 2 - 2 * ((corr * normx * normy) / sxsy)
    negRho = 1 - corr ** 2

    # Numerator
    result = torch.exp(-z / (2 * negRho))
    # Normalization factor
    denom = 2 * np.pi * (sxsy * torch.sqrt(negRho))

    # Final PDF calculation
    result = result / denom

    # Numerical stability
    epsilon = 1e-20

    result = -torch.log(torch.clamp(result, min=epsilon))

    loss = 0
    counter = 0

    for framenum in range(seq_length):

        nodeIDs = nodesPresent[framenum]
        nodeIDs = [int(nodeID) for nodeID in nodeIDs]

        for nodeID in nodeIDs:
            nodeID = look_up[nodeID]
            loss = loss + result[framenum, nodeID]
            counter = counter + 1

    if counter != 0:
        return loss / counter
    else:
        return loss


# All the following methods are: Data related methods #

def remove_file_extention(file_name):
    """
    Remove file extension (.txt) given filename
    :param file_name:
    :return:
    """
    return file_name.split('.')[0]


def add_file_extention(file_name, extention):
    """
    Add file extension (.txt) given filename
    :param file_name:
    :param extention:
    :return:
    """

    return file_name + '.' + extention


def clear_folder(path):
    """
    Remove all files in the folder
    :param path:
    :return:
    """

    if os.path.exists(path):
        shutil.rmtree(path)
        print("Folder succesfully removed: ", path)
    else:
        print("No such path: ", path)


def delete_file(path, file_name_list):
    """
    Delete given file list
    :param path:
    :param file_name_list:
    :return:
    """

    for file in file_name_list:
        file_path = os.path.join(path, file)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                print("File succesfully deleted: ", file_path)
            else:  ## Show an error ##
                print("Error: %s file not found" % file_path)
        except OSError as e:  ## if failed, report it back to the user ##
            print("Error: %s - %s." % (e.filename, e.strerror))


def get_all_file_names(path):
    """
    Return all file names given directory
    :param path:
    :return:
    """
    files = []
    for (dirpath, dirnames, filenames) in walk(path):
        files.extend(filenames)
        break
    return files


def create_directories(base_folder_path, folder_list):
    """
    Create folders using a folder list and path
    :param base_folder_path:
    :param folder_list:
    :return:
    """
    for folder_name in folder_list:
        directory = os.path.join(base_folder_path, folder_name)
        if not os.path.exists(directory):
            os.makedirs(directory)


def unique_list(l):
    """
    Get unique elements from list
    :param l:
    :return:
    """
    x = []
    for a in l:
        if a not in x:
            x.append(a)
    return x


def angle_between(p1, p2):
    """
    Return angle between two points
    :param p1:
    :param p2:
    :return:
    """
    ang1 = np.arctan2(*p1[::-1])
    ang2 = np.arctan2(*p2[::-1])
    return ((ang1 - ang2) % (2 * np.pi))


def vectorize_seq(x_seq, PedsList_seq, lookup_seq):
    """
    Subtract first frame value to all frames for a ped. Therefore, convert absolute position to relative position
    :param x_seq:
    :param PedsList_seq:
    :param lookup_seq:
    :return:
    """

    first_values_dict = WriteOnceDict()
    vectorized_x_seq = x_seq.clone()
    for ind, frame in enumerate(x_seq):
        for ped in PedsList_seq[ind]:
            first_values_dict[ped] = frame[lookup_seq[ped], 0:2]
            vectorized_x_seq[ind, lookup_seq[ped], 0:2] = frame[lookup_seq[ped], 0:2] - first_values_dict[ped][0:2]

    return vectorized_x_seq, first_values_dict


def translate(x_seq, PedsList_seq, lookup_seq, value):
    """
    Translate al trajectories given x and y values
    :param x_seq:
    :param PedsList_seq:
    :param lookup_seq:
    :param value:
    :return:
    """

    vectorized_x_seq = x_seq.clone()
    for ind, frame in enumerate(x_seq):
        for ped in PedsList_seq[ind]:
            vectorized_x_seq[ind, lookup_seq[ped], 0:2] = frame[lookup_seq[ped], 0:2] - value[0:2]

    return vectorized_x_seq


def revert_seq(x_seq, PedsList_seq, lookup_seq, first_values_dict):
    """
    Convert velocity array to absolute position array
    :param x_seq:
    :param PedsList_seq:
    :param lookup_seq:
    :param first_values_dict:
    :return:
    """

    absolute_x_seq = x_seq.clone()
    for ind, frame in enumerate(x_seq):
        for ped in PedsList_seq[ind]:
            absolute_x_seq[ind, lookup_seq[ped], 0:2] = frame[lookup_seq[ped], 0:2] + first_values_dict[ped][0:2]

    return absolute_x_seq


def rotate(origin, point, angle):
    """
    Rotate a point counterclockwise by a given angle around a given origin. The angle should be given in radians.
    :param origin:
    :param point:
    :param angle:
    :return:
    """

    ox, oy = origin
    px, py = point

    qx = ox + math.cos(angle) * (px - ox) - math.sin(angle) * (py - oy)
    qy = oy + math.sin(angle) * (px - ox) + math.cos(angle) * (py - oy)
    # return torch.cat([qx, qy])
    return [qx, qy]


def time_lr_scheduler(optimizer, epoch, lr_decay=0.5, lr_decay_epoch=10):
    """
    Decay learning rate by a factor of lr_decay every lr_decay_epoch epochs
    :param optimizer:
    :param epoch:
    :param lr_decay:
    :param lr_decay_epoch:
    :return:
    """

    if epoch % lr_decay_epoch:
        return optimizer

    print("Optimizer learning rate has been decreased.")

    for param_group in optimizer.param_groups:
        param_group['lr'] *= (1. / (1. + lr_decay * epoch))
    return optimizer


def sample_validation_data(x_seq, Pedlist, grid, args, net, look_up, num_pedlist, dataloader):
    """
    The validation sample function
    :param x_seq: Input positions
    :param Pedlist: Peds present in each frame
    :param grid:
    :param args: arguments
    :param net: The model
    :param look_up: lookup table for determining which ped is in which array index
    :param num_pedlist: number of peds in each frame
    :param dataloader:
    :return:
    """

    # Number of peds in the sequence
    numx_seq = len(look_up)

    total_loss = 0

    # Construct variables for hidden and cell states
    with torch.no_grad():
        hidden_states = Variable(torch.zeros(numx_seq, net.args.rnn_size))
        if args.use_cuda:
            hidden_states = hidden_states.cuda()
        if not args.gru:
            cell_states = Variable(torch.zeros(numx_seq, net.args.rnn_size))
            if args.use_cuda:
                cell_states = cell_states.cuda()
        else:
            cell_states = None

        ret_x_seq = Variable(torch.zeros(args.seq_length, numx_seq, 2))

        # Initialize the return data structure
        if args.use_cuda:
            ret_x_seq = ret_x_seq.cuda()

        ret_x_seq[0] = x_seq[0]

        # For the observed part of the trajectory
        for tstep in range(args.seq_length - 1):
            loss = 0
            # Do a forward prop
            out_, hidden_states, cell_states = net(x_seq[tstep].view(1, numx_seq, 2), [grid[tstep]], hidden_states,
                                                   cell_states, [Pedlist[tstep]], [num_pedlist[tstep]], dataloader,
                                                   look_up)
            # loss_obs = Gaussian2DLikelihood(out_obs, x_seq[tstep+1].view(1, numx_seq, 2), [Pedlist[tstep+1]])

            # Extract the mean, std and corr of the bivariate Gaussian
            mux, muy, sx, sy, corr = getCoef(out_)
            # Sample from the bivariate Gaussian
            next_x, next_y = sample_gaussian_2d(mux.data, muy.data, sx.data, sy.data, corr.data, Pedlist[tstep],
                                                look_up)
            ret_x_seq[tstep + 1, :, 0] = next_x
            ret_x_seq[tstep + 1, :, 1] = next_y
            loss = Gaussian2DLikelihood(out_[0].view(1, out_.size()[1], out_.size()[2]),
                                        x_seq[tstep].view(1, numx_seq, 2), [Pedlist[tstep]], look_up)
            total_loss += loss

    return ret_x_seq, total_loss / args.seq_length


def sample_validation_data_vanilla(x_seq, Pedlist, args, net, look_up, num_pedlist, dataloader):
    """
    The validation sample function for vanilla method
    :param x_seq: Input positions
    :param Pedlist: Peds present in each frame
    :param args: arguments
    :param net: The model
    :param look_up: lookup table for determining which ped is in which array index
    :param num_pedlist: number of peds in each frame
    :param dataloader:
    :return:
    """

    # Number of peds in the sequence
    numx_seq = len(look_up)

    total_loss = 0

    # Construct variables for hidden and cell states
    hidden_states = Variable(torch.zeros(numx_seq, net.args.rnn_size), volatile=True)
    if args.use_cuda:
        hidden_states = hidden_states.cuda()
    if not args.gru:
        cell_states = Variable(torch.zeros(numx_seq, net.args.rnn_size), volatile=True)
        if args.use_cuda:
            cell_states = cell_states.cuda()
    else:
        cell_states = None

    ret_x_seq = Variable(torch.zeros(args.seq_length, numx_seq, 2), volatile=True)

    # Initialize the return data structure
    if args.use_cuda:
        ret_x_seq = ret_x_seq.cuda()

    ret_x_seq[0] = x_seq[0]

    # For the observed part of the trajectory
    for tstep in range(args.seq_length - 1):
        loss = 0
        # Do a forward prop
        out_, hidden_states, cell_states = net(x_seq[tstep].view(1, numx_seq, 2), hidden_states, cell_states,
                                               [Pedlist[tstep]], [num_pedlist[tstep]], dataloader, look_up)
        # loss_obs = Gaussian2DLikelihood(out_obs, x_seq[tstep+1].view(1, numx_seq, 2), [Pedlist[tstep+1]])

        # Extract the mean, std and corr of the bivariate Gaussian
        mux, muy, sx, sy, corr = getCoef(out_)
        # Sample from the bivariate Gaussian
        next_x, next_y = sample_gaussian_2d(mux.data, muy.data, sx.data, sy.data, corr.data, Pedlist[tstep], look_up)
        ret_x_seq[tstep + 1, :, 0] = next_x
        ret_x_seq[tstep + 1, :, 1] = next_y
        loss = Gaussian2DLikelihood(out_[0].view(1, out_.size()[1], out_.size()[2]), x_seq[tstep].view(1, numx_seq, 2),
                                    [Pedlist[tstep]], look_up)
        total_loss += loss

    return ret_x_seq, total_loss / args.seq_length


def rotate_traj_with_target_ped(x_seq, angle, PedsList_seq, lookup_seq):
    """
    Rotate sequence given angle
    :param x_seq:
    :param angle:
    :param PedsList_seq:
    :param lookup_seq:
    :return:
    """

    origin = (0, 0)
    vectorized_x_seq = x_seq.clone()
    for ind, frame in enumerate(x_seq):
        for ped in PedsList_seq[ind]:
            point = frame[lookup_seq[ped], 0:2]
            rotated_point = rotate(origin, point, angle)
            vectorized_x_seq[ind, lookup_seq[ped], 0] = rotated_point[0]
            vectorized_x_seq[ind, lookup_seq[ped], 1] = rotated_point[1]
    return vectorized_x_seq
